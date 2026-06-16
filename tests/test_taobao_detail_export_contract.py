import io
import tempfile
import zipfile
from pathlib import Path
from unittest import TestCase


ROOT = Path(__file__).resolve().parents[1]


class FakeProductService:
    DEFAULT_PRODUCT = {
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

    def __init__(self, product=None):
        self.product = {**self.DEFAULT_PRODUCT, **(product or {})}

    def info(self, product_id):
        if product_id != self.product["id"]:
            return None
        return dict(self.product)

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


class FakeMainImageRenderer:
    def __init__(self):
        self.calls = []

    def render(self, context, image_bytes, source_filename):
        self.calls.append({
            "context": context,
            "image_bytes": image_bytes,
            "source_filename": source_filename,
        })
        base = Path(tempfile.mkdtemp(prefix="taobao-test-main_"))
        path = base / "generated-main.png"
        path.write_bytes(b"fake-taobao-main-png")
        return path


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
    def _rendered_capacity_for_title(self, title: str) -> list[str]:
        from src.services.business.taobao_detail import TaobaoDetailExportService

        renderer = FakeRenderer()
        service = TaobaoDetailExportService(
            product_service=FakeProductService({"title": title}),
            uploader=FakeUploader(),
            renderer=renderer,
            title_generator=FakeTaobaoTitleGenerator(),
            image_fetcher=fake_fetch,
            dimension_recognizer=lambda urls: {"text": "35×22.3×7.2CM"},
        )

        service.export_zip(9)
        return renderer.rendered_payloads[0]["product"]["capacity"]

    def test_export_zip_contains_only_color_and_detail_images(self):
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
                "详情页/原产品详情图-1.jpg",
                "详情页/原产品详情图-2.jpg",
                "详情页/详情页-01.jpg",
                "详情页/详情页-02.jpg",
                "详情页/详情页-03.jpg",
                "详情页/详情页-04.jpg",
                "详情页/详情页-05.jpg",
                "颜色图/红色-1.jpg",
                "颜色图/蓝色-2.jpg",
            ])
            self.assertFalse(any(name.startswith("主图/") for name in names))
            self.assertFalse(any(name.lower().endswith((".html", ".htm", ".txt")) for name in names))
        self.assertEqual(result.html_filename, "SJ1587 喜悦半斤茶叶礼品盒大红袍岩茶包装空盒定制logo高端公司红茶订做.html")
        self.assertEqual(result.template_image_urls, [
            "https://img.513sjbz.com/taobao/detail-01.jpg",
            "https://img.513sjbz.com/taobao/detail-02.jpg",
            "https://img.513sjbz.com/taobao/detail-03.jpg",
            "https://img.513sjbz.com/taobao/detail-04.jpg",
            "https://img.513sjbz.com/taobao/detail-05.jpg",
        ])
        self.assertEqual(result.detail_image_urls, [
            "https://img.513sjbz.com/detail/detail-1.jpg",
            "https://img.513sjbz.com/detail/detail-2.jpg",
        ])

    def test_export_zip_can_include_generated_taobao_main_image(self):
        from src.services.business.taobao_detail import TaobaoDetailExportService

        main_renderer = FakeMainImageRenderer()
        service = TaobaoDetailExportService(
            product_service=FakeProductService(),
            uploader=FakeUploader(),
            renderer=FakeRenderer(),
            main_image_renderer=main_renderer,
            title_generator=FakeTaobaoTitleGenerator(),
            image_fetcher=fake_fetch,
            dimension_recognizer=lambda urls: {"text": "35×22.3×7.2CM"},
        )

        result = service.export_zip(
            9,
            main_image={"filename": "box.png", "content": b"uploaded-png"},
        )

        self.assertEqual(len(main_renderer.calls), 1)
        self.assertEqual(main_renderer.calls[0]["image_bytes"], b"uploaded-png")
        self.assertEqual(main_renderer.calls[0]["source_filename"], "box.png")
        self.assertEqual(main_renderer.calls[0]["context"]["series"], "喜悦")
        self.assertEqual(main_renderer.calls[0]["context"]["spec_text"], "30套/件")
        with zipfile.ZipFile(io.BytesIO(result.content)) as archive:
            names = archive.namelist()
            self.assertTrue(any(name.startswith("淘宝主图/") and name.endswith(".png") for name in names))
            main_name = next(name for name in names if name.startswith("淘宝主图/"))
            self.assertEqual(archive.read(main_name), b"fake-taobao-main-png")

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
            names = archive.namelist()
            self.assertNotIn(result.html_filename, names)
            self.assertFalse(any(name.lower().endswith((".html", ".htm", ".txt")) for name in names))

    def test_export_capacity_lines_follow_box_spec(self):
        self.assertEqual(self._rendered_capacity_for_title("【喜悦】半斤"), [
            "15CM款岩茶泡袋：30泡",
            "11CM款红茶泡袋：50泡",
        ])
        self.assertEqual(self._rendered_capacity_for_title("【云岭】二三两"), [
            "15CM款岩茶泡袋：18/12泡",
            "11CM款红茶泡袋：30/20泡",
        ])
        self.assertEqual(self._rendered_capacity_for_title("【岩彩】2大盒"), [
            "15CM款岩茶泡袋：12泡",
            "11CM款红茶泡袋：20泡",
        ])
        self.assertEqual(self._rendered_capacity_for_title("【视觉】6小盒"), [
            "15CM款岩茶泡袋：12泡",
            "11CM款红茶泡袋：20泡",
        ])
        self.assertEqual(self._rendered_capacity_for_title("【出彩】1两"), [
            "15CM款岩茶泡袋：6泡",
        ])
        self.assertEqual(self._rendered_capacity_for_title("【名岩】3小盒"), [
            "15CM款岩茶泡袋：6泡",
        ])


class TaobaoDetailExportContractTest(TestCase):
    def test_backend_route_and_frontend_entry_are_wired(self):
        http_source = (ROOT / "src" / "channels" / "http_api" / "__init__.py").read_text(encoding="utf-8")
        api_source = (ROOT / "admin" / "src" / "api.ts").read_text(encoding="utf-8")
        product_source = (
            ROOT / "admin" / "src" / "components" / "business" / "products" / "products-page.tsx"
        ).read_text(encoding="utf-8")

        self.assertIn('/api/product/<int:product_id>/taobao-detail-export', http_source)
        self.assertIn('/api/product/<int:product_id>/taobao-detail-export/jobs', http_source)
        self.assertIn('/api/product/taobao-detail-export/jobs/<job_id>', http_source)
        self.assertIn('/api/product/taobao-detail-export/jobs/<job_id>/download', http_source)
        self.assertIn("TaobaoDetailExportService", http_source)
        self.assertIn("get_taobao_detail_export_job_manager", http_source)
        self.assertIn("Content-Disposition", http_source)
        self.assertIn("exportProductTaobaoDetail", api_source)
        self.assertIn("startProductTaobaoDetailExport", api_source)
        self.assertIn("productTaobaoDetailExportJob", api_source)
        self.assertIn("downloadProductTaobaoDetailExportJob", api_source)
        self.assertIn("导出淘宝详情页", product_source)
        self.assertIn("onExportTaobaoDetail", product_source)
        self.assertIn("已开始后台生成淘宝详情页资料包", product_source)
        self.assertIn("waitForTaobaoDetailExportJob", product_source)

    def test_optional_main_image_export_is_wired_through_job_and_dialog(self):
        http_source = (ROOT / "src" / "channels" / "http_api" / "__init__.py").read_text(encoding="utf-8")
        jobs_source = (ROOT / "src" / "services" / "business" / "taobao_detail_jobs.py").read_text(encoding="utf-8")
        api_source = (ROOT / "admin" / "src" / "api.ts").read_text(encoding="utf-8")
        product_source = (
            ROOT / "admin" / "src" / "components" / "business" / "products" / "products-page.tsx"
        ).read_text(encoding="utf-8")

        self.assertIn('request.files.get("main_image")', http_source)
        self.assertIn("include_main_image", http_source)
        self.assertIn("main_image=", http_source)
        self.assertIn("main_image: dict | None = None", jobs_source)
        self.assertIn("export_zip(self._job_product_id(job_id), main_image=job.main_image)", jobs_source)
        self.assertIn("TaobaoDetailExportStartOptions", api_source)
        self.assertIn("mainImageFile", api_source)
        self.assertIn('form.append("main_image"', api_source)
        self.assertIn("TaobaoExportDialog", product_source)
        self.assertIn("导出淘宝资料", product_source)
        self.assertIn("同时制作淘宝主图", product_source)
        self.assertIn('accept="image/png"', product_source)

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
        self.assertNotIn("preview.html", renderer_source)
        self.assertNotIn("taobao-code-local.txt", renderer_source)
        self.assertNotIn("taobao-code-oss-template.txt", renderer_source)
        self.assertIn('font-family: "AlibabaPuhuiEditable"', template_source)
        self.assertNotIn("color: #1a1a1a", template_source)
        self.assertNotIn("color: #231815", template_source)
        self.assertNotIn("color: #111", template_source)
        self.assertNotIn('fill="#231815"', template_source)
        self.assertNotIn('stroke="#231815"', template_source)
