from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class MiniappImageConfigContractTest(unittest.TestCase):
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
