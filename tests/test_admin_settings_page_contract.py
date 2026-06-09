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
        self.assertIn("<SettingsPage currentUser={user} />", app_source)
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
        product_source = settings_source.split("function ProductBasicPanel", 1)[1].split("function InventoryRulesPanel", 1)[0]
        inventory_source = settings_source.split("function InventoryRulesPanel", 1)[1].split("function PaymentRulesPanel", 1)[0]
        self.assertIn("库存规则由库存规则页统一维护", product_source)
        self.assertIn("去库存规则设置", product_source)
        self.assertNotIn("<FieldLabel>分类库存策略</FieldLabel>", product_source)
        self.assertNotIn("onValueChange={(next) => setCategoryDraft({ ...categoryDraft, inventory_policy: next })}", product_source)
        self.assertIn("唯一编辑入口", inventory_source)
        self.assertIn("新分类自动判断规则", inventory_source)
        self.assertIn("扣库存关键词", settings_source)
        self.assertIn("不扣库存关键词", settings_source)
        self.assertIn("non_stock_category_keywords", settings_source)
        self.assertIn("stock_category_keywords", settings_source)
        self.assertIn('"/api/product/categories"', api_source)
        self.assertIn("ProductCategorySavePayload", types_source)

    def test_settings_page_can_manage_manufacturers(self):
        settings_source = (ROOT / "admin" / "src" / "components" / "business" / "settings" / "settings-page.tsx").read_text(encoding="utf-8")
        api_source = (ROOT / "admin" / "src" / "api.ts").read_text(encoding="utf-8")
        types_source = (ROOT / "admin" / "src" / "types.ts").read_text(encoding="utf-8")

        self.assertIn('"manufacturers"', settings_source)
        self.assertIn("ManufacturersPanel", settings_source)
        self.assertIn("manufacturerDraft", settings_source)
        self.assertIn("api.manufacturers", settings_source)
        self.assertIn("api.saveManufacturer", settings_source)
        self.assertIn("api.updateManufacturerStatus", settings_source)
        self.assertIn("product_count", settings_source)
        self.assertIn("/api/settings/manufacturers", api_source)
        self.assertIn("saveManufacturer", api_source)
        self.assertIn("updateManufacturerStatus", api_source)
        self.assertIn("ProductManufacturer", types_source)
        self.assertIn("ManufacturerSavePayload", types_source)

    def test_print_settings_has_print_preview_dialog(self):
        settings_source = (ROOT / "admin" / "src" / "components" / "business" / "settings" / "settings-page.tsx").read_text(encoding="utf-8")
        print_source = settings_source.split("function PrintSettingsPanel", 1)[1].split("function MiniappImageConfigTable", 1)[0]

        self.assertIn("打印预览", print_source)
        self.assertIn("latest_print_url", print_source)
        self.assertIn("previewUrl", print_source)
        self.assertIn("<iframe", print_source)
        self.assertIn("previewFrameRef", print_source)
        self.assertIn("chrome=0", print_source)
        self.assertIn("contentWindow?.print", print_source)
        self.assertIn("DialogTitle", print_source)
        self.assertIn("没有最近销售单时不能预览", print_source)
        self.assertNotIn("新窗口打开", print_source)
        self.assertNotIn("window.open(previewUrl", print_source)

    def test_media_and_miniapp_settings_are_separate_panels(self):
        settings_source = (ROOT / "admin" / "src" / "components" / "business" / "settings" / "settings-page.tsx").read_text(encoding="utf-8")
        media_source = settings_source.split("function MediaSettingsPanel", 1)[1].split("function MiniappSettingsPanel", 1)[0]
        miniapp_source = settings_source.split("function MiniappSettingsPanel", 1)[1].split("function UserPermissionsPanel", 1)[0]

        self.assertIn("图片资产", media_source)
        self.assertIn("上传待绑定图片", media_source)
        self.assertIn("productMedia", media_source)
        self.assertIn("uploadProductImage", media_source)
        self.assertIn("multiple", media_source)
        self.assertIn("uploadPendingImages", media_source)
        self.assertIn("deleteProductMedia", media_source)
        self.assertIn("deletePendingProductMedia", media_source)
        self.assertIn("selectedMediaIds", media_source)
        self.assertIn("toggleMediaSelection", media_source)
        self.assertIn("deleteSelectedProductMedia", media_source)
        self.assertIn("删除选中的未绑定图片", media_source)
        self.assertIn("settings-media-select", media_source)
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

    def test_media_settings_can_edit_upload_rules(self):
        settings_source = (ROOT / "admin" / "src" / "components" / "business" / "settings" / "settings-page.tsx").read_text(encoding="utf-8")
        media_source = settings_source.split("function MediaSettingsPanel", 1)[1].split("function MiniappSettingsPanel", 1)[0]
        css_source = (ROOT / "admin" / "src" / "styles.css").read_text(encoding="utf-8")

        for token in [
            "mediaRules",
            "patchMediaRule",
            "saveImageRules",
            "registerSave(\"media\", saveImageRules)",
            "api.saveSystemSetting(\"image_rules\"",
            "settings-media-rules",
            "settings-media-rule-grid",
            "上传规则",
            "OSS 路径",
            "压缩规则",
            "待绑定清理天数",
            "1:1 主图规则",
            "max_image_upload_mb",
            "pending_cleanup_days",
            "require_square_main_image",
        ]:
            self.assertIn(token, media_source)
        self.assertIn(".settings-media-rules", css_source)
        self.assertIn(".settings-media-rule-grid", css_source)

    def test_product_media_has_pending_batch_delete_boundary(self):
        settings_source = (ROOT / "admin" / "src" / "components" / "business" / "settings" / "settings-page.tsx").read_text(encoding="utf-8")
        api_source = (ROOT / "admin" / "src" / "api.ts").read_text(encoding="utf-8")
        http_source = (ROOT / "src" / "channels" / "http_api" / "__init__.py").read_text(encoding="utf-8")
        native_source = (ROOT / "src" / "engine" / "native_db.py").read_text(encoding="utf-8")
        media_source = settings_source.split("function MediaSettingsPanel", 1)[1].split("function MiniappSettingsPanel", 1)[0]

        self.assertIn("deletePendingProductMedia", api_source)
        self.assertIn("/api/product/media/pending", api_source)
        self.assertIn("api.deletePendingProductMedia(selectedPendingMediaIds)", media_source)
        self.assertIn('@app.route("/api/product/media/pending", methods=["DELETE", "POST"])', http_source)
        self.assertIn("delete_pending_media", http_source)
        self.assertIn("delete_pending_product_media", native_source)
        self.assertIn("media_type='pending'", native_source)
        self.assertIn("sku_id IS NULL", native_source)
        self.assertIn("spu_id IS NULL", native_source)

    def test_user_permissions_protect_current_admin_in_ui(self):
        settings_source = (ROOT / "admin" / "src" / "components" / "business" / "settings" / "settings-page.tsx").read_text(encoding="utf-8")
        app_source = (ROOT / "admin" / "src" / "App.tsx").read_text(encoding="utf-8")
        user_source = settings_source.split("function UserPermissionsPanel", 1)[1].split("function PrintSettingsPanel", 1)[0]

        self.assertIn("currentUser={user}", app_source)
        self.assertIn("AuthUser", settings_source)
        self.assertIn("type SettingsPageProps", settings_source)
        self.assertIn("currentUser?: AuthUser | null", settings_source)
        self.assertIn("UserPermissionsPanel {...callbacks} currentUser={currentUser}", settings_source)
        self.assertIn("type UserPermissionsPanelProps", settings_source)
        self.assertIn("UserPermissionsPanelProps", user_source)
        self.assertIn("isSelfUser", user_source)
        self.assertIn("currentUser?.native_user_id", user_source)
        self.assertIn("roleGuarded", user_source)
        self.assertIn("statusGuarded", user_source)
        self.assertIn("当前账号", user_source)
        self.assertIn("settings-user-guard-note", user_source)
        self.assertIn("最后一个管理员", user_source)


if __name__ == "__main__":
    unittest.main()
