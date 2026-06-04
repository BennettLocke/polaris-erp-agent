import io
import zipfile
from pathlib import Path
from unittest import TestCase


ROOT = Path(__file__).resolve().parents[1]


class FakeProductService:
    def info(self, product_id):
        if product_id != 9:
            return None
        return {
            "id": 9,
            "spu_id": 3,
            "title": "【喜悦】半斤",
            "piece_text": "1件30套",
            "case_pack_qty": "30",
            "available_colors": ["红色", "蓝色"],
            "detail_image_urls": [
                "https://img.513sjbz.com/detail/detail-1.jpg",
                "https://img.513sjbz.com/detail/detail-2.jpg",
            ],
        }

    def media_assets(self, **kwargs):
        media_type = kwargs.get("media_type")
        if media_type == "main_image":
            return [{"url": "https://img.513sjbz.com/main/main.jpg", "media_type": "main_image"}]
        if media_type == "color_image":
            return [
                {"url": "https://img.513sjbz.com/color/red.jpg", "sku_color": "红色", "media_type": "color_image"},
                {"url": "https://img.513sjbz.com/color/blue.jpg", "sku_color": "蓝色", "media_type": "color_image"},
            ]
        if media_type == "detail_image":
            return [
                {"url": "https://img.513sjbz.com/detail/detail-1.jpg", "media_type": "detail_image"},
                {"url": "https://img.513sjbz.com/detail/detail-2.jpg", "media_type": "detail_image"},
            ]
        return []


class FakeUploader:
    def __init__(self):
        self.uploaded = []

    def upload(self, local_path):
        self.uploaded.append(local_path)
        return {"url": f"https://img.513sjbz.com/taobao/template-{len(self.uploaded)}.jpg"}


def fake_fetch(url: str) -> bytes:
    from PIL import Image

    image = Image.new("RGB", (24, 24), "white")
    buffer = io.BytesIO()
    image.save(buffer, "JPEG")
    return buffer.getvalue()


class TaobaoDetailExportServiceTest(TestCase):
    def test_export_zip_contains_main_color_images_and_detail_html_only(self):
        from src.services.business.taobao_detail import TaobaoDetailExportService

        uploader = FakeUploader()
        service = TaobaoDetailExportService(
            product_service=FakeProductService(),
            uploader=uploader,
            image_fetcher=fake_fetch,
            dimension_recognizer=lambda urls: {
                "text": "35×22.3×7.2CM",
                "length": "35CM",
                "width": "22.3CM",
                "height": "7.2CM",
            },
        )

        result = service.export_zip(9)

        self.assertTrue(result.filename.endswith(".zip"))
        self.assertEqual(len(uploader.uploaded), 4)
        with zipfile.ZipFile(io.BytesIO(result.content)) as archive:
            names = sorted(archive.namelist())
            self.assertEqual(names, [
                "detail.html",
                "主图/main-1.jpg",
                "颜色图/红色-1.jpg",
                "颜色图/蓝色-2.jpg",
            ])
            detail_html = archive.read("detail.html").decode("utf-8")
        self.assertIn("https://img.513sjbz.com/taobao/template-1.jpg", detail_html)
        self.assertIn("https://img.513sjbz.com/taobao/template-4.jpg", detail_html)
        self.assertIn("https://img.513sjbz.com/detail/detail-1.jpg", detail_html)
        self.assertIn("https://img.513sjbz.com/detail/detail-2.jpg", detail_html)
        self.assertIn("35×22.3×7.2CM", detail_html)


class TaobaoDetailExportContractTest(TestCase):
    def test_backend_route_and_frontend_entry_are_wired(self):
        http_source = (ROOT / "src" / "channels" / "http_api" / "__init__.py").read_text(encoding="utf-8")
        api_source = (ROOT / "admin" / "src" / "api.ts").read_text(encoding="utf-8")
        product_source = (
            ROOT / "admin" / "src" / "components" / "business" / "products" / "products-page.tsx"
        ).read_text(encoding="utf-8")

        self.assertIn('/api/product/<int:product_id>/taobao-detail-export', http_source)
        self.assertIn("TaobaoDetailExportService", http_source)
        self.assertIn("Content-Disposition", http_source)
        self.assertIn("exportProductTaobaoDetail", api_source)
        self.assertIn("导出淘宝详情页", product_source)
        self.assertIn("onExportTaobaoDetail", product_source)

    def test_linux_export_font_prefers_cjk_before_dejavu(self):
        service_source = (ROOT / "src" / "services" / "business" / "taobao_detail.py").read_text(encoding="utf-8")

        regular_noto = service_source.index("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")
        regular_dejavu = service_source.index("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
        bold_noto = service_source.index("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc")
        bold_dejavu = service_source.index("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
        self.assertLess(regular_noto, regular_dejavu)
        self.assertLess(bold_noto, bold_dejavu)
