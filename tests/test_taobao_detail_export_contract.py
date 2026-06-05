import io
import tempfile
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
            "sku_no": "SJ1587",
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
        return {"url": f"https://img.513sjbz.com/taobao/detail-{len(self.uploaded):02d}.jpg"}


class FakeRenderer:
    def __init__(self):
        self.rendered_payloads = []

    def render(self, product_data):
        self.rendered_payloads.append(product_data)
        base = Path(tempfile.mkdtemp(prefix="taobao-test-render_"))
        base.mkdir(parents=True, exist_ok=True)
        paths = []
        for index in range(1, 6):
            path = base / f"detail-{index:02d}.jpg"
            path.write_bytes(b"fake-jpg")
            paths.append(path)
        return paths


class FakeTaobaoTitleGenerator:
    def __init__(self):
        self.calls = []

    def __call__(self, product):
        self.calls.append(product)
        return "喜悦半斤茶叶礼品盒大红袍岩茶包装空盒定制logo高端公司红茶订做"


class FailingTaobaoTitleGenerator:
    def __call__(self, product):
        raise RuntimeError("LLM unavailable")


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
        renderer = FakeRenderer()
        title_generator = FakeTaobaoTitleGenerator()
        service = TaobaoDetailExportService(
            product_service=FakeProductService(),
            uploader=uploader,
            renderer=renderer,
            title_generator=title_generator,
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
        self.assertEqual(len(uploader.uploaded), 5)
        self.assertEqual(len(renderer.rendered_payloads), 1)
        self.assertEqual(len(title_generator.calls), 1)
        self.assertEqual(title_generator.calls[0]["sku_no"], "SJ1587")
        rendered_product = renderer.rendered_payloads[0]["product"]
        self.assertEqual(rendered_product["capacity"], [
            "15CM款岩茶泡袋：30泡",
            "11CM款红茶泡袋：50泡",
        ])
        self.assertEqual(rendered_product["name"], "喜悦半斤茶叶礼盒（空）")
        self.assertEqual(rendered_product["size"], "35×22.3×7.2CM")
        with zipfile.ZipFile(io.BytesIO(result.content)) as archive:
            names = sorted(archive.namelist())
            self.assertEqual(names, [
                "SJ1587 喜悦半斤茶叶礼品盒大红袍岩茶包装空盒定制logo高端公司红茶订做.html",
                "主图/main-1.jpg",
                "颜色图/红色-1.jpg",
                "颜色图/蓝色-2.jpg",
            ])
            self.assertNotIn("detail.html", names)
            detail_html = archive.read(names[0]).decode("utf-8")
        self.assertEqual(result.html_filename, "SJ1587 喜悦半斤茶叶礼品盒大红袍岩茶包装空盒定制logo高端公司红茶订做.html")
        self.assertIn("https://img.513sjbz.com/taobao/detail-01.jpg", detail_html)
        self.assertIn("https://img.513sjbz.com/taobao/detail-05.jpg", detail_html)
        self.assertNotIn("https://img.513sjbz.com/taobao/detail-01.png", detail_html)
        self.assertIn("https://img.513sjbz.com/detail/detail-1.jpg", detail_html)
        self.assertIn("https://img.513sjbz.com/detail/detail-2.jpg", detail_html)
        self.assertIn("width:800px", detail_html)
        self.assertNotIn("width:750px", detail_html)
        self.assertNotIn("喜悦半斤茶叶礼品盒", detail_html)
        self.assertNotIn("<p><img", detail_html)

    def test_export_html_filename_falls_back_when_llm_title_generation_fails(self):
        from src.services.business.taobao_detail import TaobaoDetailExportService

        service = TaobaoDetailExportService(
            product_service=FakeProductService(),
            uploader=FakeUploader(),
            renderer=FakeRenderer(),
            title_generator=FailingTaobaoTitleGenerator(),
            image_fetcher=fake_fetch,
            dimension_recognizer=lambda urls: {"text": "35×22.3×7.2CM"},
        )

        result = service.export_zip(9)

        self.assertEqual(
            result.html_filename,
            "SJ1587 喜悦半斤茶叶礼品盒大红袍岩茶包装空盒定制logo高端公司红茶订做.html",
        )
        with zipfile.ZipFile(io.BytesIO(result.content)) as archive:
            self.assertIn(result.html_filename, archive.namelist())
            self.assertNotIn("detail.html", archive.namelist())


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

    def test_export_uses_original_playwright_renderer_contract(self):
        service_source = (ROOT / "src" / "services" / "business" / "taobao_detail.py").read_text(encoding="utf-8")
        renderer_source = (ROOT / "scripts" / "taobao_detail" / "render_taobao_detail.mjs").read_text(encoding="utf-8")
        template_source = (ROOT / "assets" / "taobao_detail" / "detail-template.html").read_text(encoding="utf-8")

        self.assertIn("OriginalTaobaoDetailRenderer", service_source)
        self.assertIn("playwright-core", renderer_source)
        self.assertIn("TAOBAO_DETAIL_CHROMIUM_PATH", renderer_source)
        self.assertIn("AlibabaPuHuiTi-3-55-Regular.woff2", renderer_source)
        self.assertIn("detail-05.jpg", renderer_source)
        self.assertIn('type: "jpeg"', renderer_source)
        self.assertIn("quality: 100", renderer_source)
        self.assertIn('font-family: "AlibabaPuhuiEditable"', template_source)
