from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class AdminMiniappImageConfigContractTest(unittest.TestCase):
    def test_webui_exposes_miniapp_image_config_page(self):
        app_source = (ROOT / "admin" / "src" / "App.tsx").read_text(encoding="utf-8")
        api_source = (ROOT / "admin" / "src" / "api.ts").read_text(encoding="utf-8")
        page_source = (
            ROOT
            / "admin"
            / "src"
            / "components"
            / "business"
            / "miniapp-images"
            / "miniapp-images-page.tsx"
        ).read_text(encoding="utf-8")
        types_source = (ROOT / "admin" / "src" / "types.ts").read_text(encoding="utf-8")

        self.assertIn('"miniapp-images"', app_source)
        self.assertIn("MiniappImagesPage", app_source)
        self.assertIn("miniappImageConfig", api_source)
        self.assertIn("/api/miniapp/image-config", api_source)
        self.assertIn("uploadMiniappImage", api_source)
        self.assertIn("/api/miniapp/image-config/upload", api_source)
        self.assertIn("updateMiniappImage", api_source)
        self.assertIn("MiniappImageConfig", types_source)
        self.assertIn("MiniappImageUpdatePayload", types_source)
        self.assertIn("ProductCategory", page_source)
        self.assertIn("home_banner", page_source)
        self.assertIn("bottom_tab", page_source)
        self.assertIn("icon_active", page_source)
        self.assertIn("realistic_images", page_source)
        self.assertIn("big_images", page_source)

    def test_backend_supports_miniapp_image_config_read_update_and_upload(self):
        http_source = (ROOT / "src" / "channels" / "http_api" / "__init__.py").read_text(encoding="utf-8")
        service_source = (ROOT / "src" / "services" / "business" / "miniapp.py").read_text(encoding="utf-8")
        native_source = (ROOT / "src" / "engine" / "native_db.py").read_text(encoding="utf-8")

        self.assertIn('@app.route("/api/miniapp/image-config", methods=["GET"])', http_source)
        self.assertIn('@app.route("/api/miniapp/image-config", methods=["POST", "PATCH"])', http_source)
        self.assertIn('@app.route("/api/miniapp/image-config/upload", methods=["POST"])', http_source)
        self.assertIn('re.compile(r"^/api/miniapp/image-config$")', http_source)
        self.assertIn('re.compile(r"^/api/miniapp/image-config/upload$")', http_source)
        self.assertIn("image_config_payload", service_source)
        self.assertIn("update_image_config", service_source)
        self.assertIn("update_miniapp_asset_image", native_source)
        self.assertIn("update_product_category_image", native_source)
        self.assertIn('{"asset_url", "active_asset_url"}', native_source)
        self.assertIn('{"icon", "icon_active", "realistic_images", "big_images"}', native_source)
        self.assertIn("include_disabled", native_source)


if __name__ == "__main__":
    unittest.main()
