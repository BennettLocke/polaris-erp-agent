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
        self.assertIn('@app.route("/api/miniapp/image-config/assets", methods=["POST"])', http_source)
        self.assertIn('@app.route("/api/miniapp/image-config/assets/<int:asset_id>", methods=["DELETE"])', http_source)
        self.assertIn('@app.route("/api/miniapp/image-config/upload", methods=["POST"])', http_source)
        self.assertIn('re.compile(r"^/api/miniapp/image-config$")', http_source)
        self.assertIn('re.compile(r"^/api/miniapp/image-config/assets$")', http_source)
        self.assertIn('re.compile(r"^/api/miniapp/image-config/assets/\\d+$")', http_source)
        self.assertIn('re.compile(r"^/api/miniapp/image-config/upload$")', http_source)
        self.assertIn("image_config_payload", service_source)
        self.assertIn("update_image_config", service_source)
        self.assertIn("create_image_asset", service_source)
        self.assertIn("delete_image_asset", service_source)
        self.assertIn("update_miniapp_asset_image", native_source)
        self.assertIn("create_miniapp_asset", native_source)
        self.assertIn("delete_miniapp_asset", native_source)
        self.assertIn("update_product_category_image", native_source)
        self.assertIn('{"asset_url", "active_asset_url"}', native_source)
        self.assertIn('{"icon", "icon_active"}', native_source)
        self.assertIn("include_disabled", native_source)

    def test_admin_image_config_is_grouped_and_only_exposes_needed_fields(self):
        page_source = (
            ROOT / "admin" / "src" / "components" / "business" / "miniapp-images" / "miniapp-images-page.tsx"
        ).read_text(encoding="utf-8")
        type_source = (ROOT / "admin" / "src" / "types.ts").read_text(encoding="utf-8")

        self.assertIn("ImageConfigTable", page_source)
        self.assertIn("visibleAssetScenes", page_source)
        self.assertIn("首页轮播图", page_source)
        self.assertIn("新增轮播", page_source)
        self.assertIn("删除轮播", page_source)
        self.assertIn("商品分类图标", page_source)
        self.assertIn("底部导航图标", page_source)
        self.assertIn('field: "icon", label: "未选中图标"', page_source)
        self.assertIn('field: "icon_active", label: "选中图标"', page_source)
        self.assertIn('field: "asset_url", label: "未选中图标"', page_source)
        self.assertIn('field: "active_asset_url", label: "选中图标"', page_source)
        self.assertNotIn("CategoryCard", page_source)
        self.assertNotIn("AssetCard", page_source)
        self.assertNotIn("写实图", page_source)
        self.assertNotIn("高清大图", page_source)
        self.assertNotIn("realistic_images", type_source)
        self.assertNotIn("big_images", type_source)

    def test_settings_page_can_add_and_delete_home_banners(self):
        page_source = (
            ROOT / "admin" / "src" / "components" / "business" / "settings" / "settings-page.tsx"
        ).read_text(encoding="utf-8")
        api_source = (ROOT / "admin" / "src" / "api.ts").read_text(encoding="utf-8")
        type_source = (ROOT / "admin" / "src" / "types.ts").read_text(encoding="utf-8")

        self.assertIn("createMiniappImageAsset", api_source)
        self.assertIn("deleteMiniappImageAsset", api_source)
        self.assertIn("MiniappImageCreatePayload", type_source)
        self.assertIn("新增轮播", page_source)
        self.assertIn("删除轮播", page_source)
        self.assertIn('scene: "home_banner"', page_source)


if __name__ == "__main__":
    unittest.main()
