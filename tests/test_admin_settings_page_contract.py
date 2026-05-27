from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class AdminSettingsPageContractTest(unittest.TestCase):
    def test_settings_page_owns_settings_media_and_miniapp_sections(self):
        app_source = (ROOT / "admin" / "src" / "App.tsx").read_text(encoding="utf-8")
        api_source = (ROOT / "admin" / "src" / "api.ts").read_text(encoding="utf-8")
        settings_page_path = ROOT / "admin" / "src" / "components" / "business" / "settings" / "settings-page.tsx"
        settings_index_path = ROOT / "admin" / "src" / "components" / "business" / "settings" / "index.ts"
        self.assertTrue(settings_page_path.exists(), "SettingsPage must live in components/business/settings")
        self.assertTrue(settings_index_path.exists(), "SettingsPage must be exported from a local index.ts")

        settings_source = settings_page_path.read_text(encoding="utf-8")
        settings_index = settings_index_path.read_text(encoding="utf-8")

        self.assertIn('from "./components/business/settings"', app_source)
        self.assertIn("<SettingsPage />", app_source)
        self.assertIn('route === "media"', app_source)
        self.assertIn('route === "miniapp-images"', app_source)
        self.assertIn('new URLSearchParams(window.location.search)', settings_source)
        self.assertIn("section=media", app_source)
        self.assertIn("section=miniapp", app_source)
        self.assertNotIn('label: "图片资产"', app_source)
        self.assertNotIn('label: "小程序图片"', app_source)
        self.assertIn('export { SettingsPage } from "./settings-page"', settings_index)

        for component_name in [
            "SettingsPage",
            "SettingsShell",
            "SettingsNav",
            "SettingsSectionHeader",
            "SettingsSaveBar",
            "SettingListEditor",
            "NumberSettingsPanel",
            "ProductBasicPanel",
            "InventoryRulesPanel",
            "PaymentRulesPanel",
            "MediaSettingsPanel",
            "MiniappSettingsPanel",
            "UserPermissionsPanel",
            "PrintSettingsPanel",
        ]:
            self.assertIn(component_name, settings_source)

        for shadcn_component in [
            "Card",
            "Badge",
            "Tabs",
            "Button",
            "Input",
            "SelectTrigger",
            "Switch",
            "Table",
            "Skeleton",
            "Empty",
            "AlertDialog",
            "FieldGroup",
        ]:
            self.assertIn(shadcn_component, settings_source)

        for api_method in [
            "skuNumberSettings",
            "saveSkuNumberSettings",
            "systemSetting",
            "saveSystemSetting",
            "saveProductCategory",
            "salesPrintSettings",
            "saveSalesPrintSettings",
            "users",
            "updateUser",
            "productMedia",
            "uploadProductImage",
            "deleteProductMedia",
            "miniappImageConfig",
            "uploadMiniappImage",
            "updateMiniappImage",
        ]:
            self.assertIn(api_method, settings_source)
            self.assertIn(api_method, api_source)

        self.assertIn("保存并继续", settings_source)
        self.assertIn("放弃修改", settings_source)
        self.assertIn("取消", settings_source)
        self.assertNotIn("window.confirm", settings_source)
        self.assertNotIn("window.alert", settings_source)

    def test_settings_page_can_manage_categories_and_inventory_rules(self):
        settings_source = (ROOT / "admin" / "src" / "components" / "business" / "settings" / "settings-page.tsx").read_text(encoding="utf-8")
        api_source = (ROOT / "admin" / "src" / "api.ts").read_text(encoding="utf-8")
        types_source = (ROOT / "admin" / "src" / "types.ts").read_text(encoding="utf-8")

        self.assertIn("新增分类", settings_source)
        self.assertIn("编辑分类", settings_source)
        self.assertIn("api.saveProductCategory", settings_source)
        self.assertIn("分类库存策略", settings_source)
        self.assertIn("扣库存关键词", settings_source)
        self.assertIn("不扣库存关键词", settings_source)
        self.assertIn("non_stock_category_keywords", settings_source)
        self.assertIn("stock_category_keywords", settings_source)
        self.assertIn('"/api/product/categories"', api_source)
        self.assertIn("ProductCategorySavePayload", types_source)

    def test_print_settings_has_print_preview_dialog(self):
        settings_source = (ROOT / "admin" / "src" / "components" / "business" / "settings" / "settings-page.tsx").read_text(encoding="utf-8")
        print_source = settings_source.split("function PrintSettingsPanel", 1)[1].split("function MiniappImageConfigTable", 1)[0]

        self.assertIn("打印预览", print_source)
        self.assertIn("latest_print_url", print_source)
        self.assertIn("previewUrl", print_source)
        self.assertIn("<iframe", print_source)
        self.assertIn("DialogTitle", print_source)
        self.assertIn("没有最近销售单时不能预览", print_source)

    def test_media_and_miniapp_settings_are_separate_panels(self):
        settings_source = (ROOT / "admin" / "src" / "components" / "business" / "settings" / "settings-page.tsx").read_text(encoding="utf-8")
        media_source = settings_source.split("function MediaSettingsPanel", 1)[1].split("function MiniappSettingsPanel", 1)[0]
        miniapp_source = settings_source.split("function MiniappSettingsPanel", 1)[1].split("function UserPermissionsPanel", 1)[0]

        self.assertIn("图片资产", media_source)
        self.assertIn("上传待绑定图片", media_source)
        self.assertIn("productMedia", media_source)
        self.assertIn("uploadProductImage", media_source)
        self.assertIn("deleteProductMedia", media_source)
        self.assertIn("thumbnailUrl", media_source)
        self.assertIn("x-oss-process", media_source)
        self.assertIn("AlertDialogContent", media_source)
        self.assertNotIn("miniappImageConfig", media_source)
        self.assertNotIn("updateMiniappImage", media_source)

        self.assertIn("小程序设置", miniapp_source)
        self.assertIn("首页轮播", miniapp_source)
        self.assertIn("商品分类图标", miniapp_source)
        self.assertIn("底部导航图标", miniapp_source)
        self.assertIn("miniappImageConfig", miniapp_source)
        self.assertIn("uploadMiniappImage", miniapp_source)
        self.assertIn("updateMiniappImage", miniapp_source)
        self.assertNotIn("productMedia", miniapp_source)
        self.assertNotIn("deleteProductMedia", miniapp_source)


if __name__ == "__main__":
    unittest.main()
