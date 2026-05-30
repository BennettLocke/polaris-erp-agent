from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


def extract_function_section(source: str, name: str) -> str:
    signature_index = source.index(f"function {name}(")
    paren_depth = 0
    body_start = -1
    for index in range(source.index("(", signature_index), len(source)):
        char = source[index]
        if char == "(":
            paren_depth += 1
        elif char == ")":
            paren_depth -= 1
        elif char == "{" and paren_depth == 0:
            body_start = index
            break
    if body_start < 0:
        raise AssertionError(f"Could not find body for function {name}")
    depth = 0
    for index in range(body_start, len(source)):
        char = source[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[signature_index:index + 1]
    raise AssertionError(f"Could not extract function {name}")


class AdminWorkbenchPageContractTest(unittest.TestCase):
    def test_admin_home_is_ai_workbench_not_dashboard(self):
        app_source = (ROOT / "admin" / "src" / "App.tsx").read_text(encoding="utf-8")
        api_source = (ROOT / "admin" / "src" / "api.ts").read_text(encoding="utf-8")
        types_source = (ROOT / "admin" / "src" / "types.ts").read_text(encoding="utf-8")
        workbench_page_path = ROOT / "admin" / "src" / "components" / "business" / "workbench" / "workbench-page.tsx"
        workbench_index_path = ROOT / "admin" / "src" / "components" / "business" / "workbench" / "index.ts"

        self.assertTrue(workbench_page_path.exists(), "WorkbenchPage must live in components/business/workbench")
        self.assertTrue(workbench_index_path.exists(), "WorkbenchPage must be exported from a local index.ts")

        workbench_source = workbench_page_path.read_text(encoding="utf-8")
        workbench_index = workbench_index_path.read_text(encoding="utf-8")

        self.assertIn('from "./components/business/workbench"', app_source)
        self.assertIn("<WorkbenchPage />", app_source)
        self.assertIn('dashboard: { title: "工作台", desc: "AI 对话、结构化确认和最近业务记录。"', app_source)
        self.assertNotIn("function DashboardCards", app_source)
        self.assertNotIn("function RecentList", app_source)
        self.assertIn('export { WorkbenchPage } from "./workbench-page"', workbench_index)

        for type_name in [
            "AgentSessionSnapshot",
            "AgentChatResponse",
            "AgentHistoryResult",
            "AgentImageUploadResult",
        ]:
            self.assertIn(type_name, types_source)

        for api_method in [
            "agentChat",
            "agentHistory",
            "updateSessionPending",
            "uploadAgentImage",
            "dashboardSummary",
        ]:
            self.assertIn(api_method, api_source)

        for endpoint in [
            '"/api/agent/chat"',
            '"/api/session/pending"',
            '"/api/images/upload"',
            '"/api/agent/history',
        ]:
            self.assertIn(endpoint, api_source)

    def test_workbench_reads_hot_products_for_dashboard_preview(self):
        api_source = (ROOT / "admin" / "src" / "api.ts").read_text(encoding="utf-8")
        types_source = (ROOT / "admin" / "src" / "types.ts").read_text(encoding="utf-8")
        workbench_source = (
            ROOT / "admin" / "src" / "components" / "business" / "workbench" / "workbench-page.tsx"
        ).read_text(encoding="utf-8")
        styles_source = (ROOT / "admin" / "src" / "styles.css").read_text(encoding="utf-8")

        self.assertIn("AnalyticsHotProduct", types_source)
        self.assertIn("AnalyticsHotProductsResult", types_source)
        self.assertIn("analyticsHotProducts", api_source)
        self.assertIn('"/api/analytics/hot-products"', api_source)
        self.assertIn("hotProducts", workbench_source)
        self.assertIn("setHotProducts", workbench_source)
        self.assertIn("HotProductsMiniPanel", workbench_source)
        self.assertIn('api.analyticsHotProducts({ period: "7d", limit: 5 })', workbench_source)
        self.assertIn("workbench-hot-products", workbench_source)
        self.assertIn(".workbench-hot-products", styles_source)

    def test_workbench_only_renders_real_image_urls_as_images(self):
        workbench_source = (
            ROOT / "admin" / "src" / "components" / "business" / "workbench" / "workbench-page.tsx"
        ).read_text(encoding="utf-8")
        image_line_section = extract_function_section(workbench_source, "isImageLine")

        self.assertIn('if (clean.startsWith("/api/images/file/")) return true;', image_line_section)
        self.assertIn('if (!clean.startsWith("http://") && !clean.startsWith("https://")) return false;', image_line_section)
        self.assertIn('/\\.(png|jpe?g|webp|gif)(\\?.*)?$/i.test(clean)', image_line_section)
        self.assertNotIn('return clean.startsWith("/api/images/file/") || /\\.(png|jpe?g|webp|gif)(\\?.*)?$/i.test(clean);', image_line_section)

    def test_workbench_uses_dialog_input_and_agent_sections(self):
        workbench_source = (
            ROOT / "admin" / "src" / "components" / "business" / "workbench" / "workbench-page.tsx"
        ).read_text(encoding="utf-8")
        styles_source = (ROOT / "admin" / "src" / "styles.css").read_text(encoding="utf-8")

        for component_name in [
            "WorkbenchPage",
            "WorkbenchStatusStrip",
            "ConversationPanel",
            "MessageList",
            "CommandStrip",
            "ChatComposer",
            "WorkbenchResultDialog",
            "AgentResultDialog",
            "InventoryResultDialog",
            "ImageOcrResultDialog",
            "PendingStatusCard",
            "BusinessContextPanel",
            "AgentConfirmDialog",
        ]:
            self.assertIn(component_name, workbench_source)

        for ui_component in [
            "Card",
            "Badge",
            "Button",
            "Input",
            "ScrollArea",
            "DialogContent",
            "DialogTitle",
            "Skeleton",
            "Empty",
        ]:
            self.assertIn(ui_component, workbench_source)

        for label in [
            "AI 业务工作台",
            "最近业务记录",
            "结构化确认",
            "上传图片",
            "确认执行",
            "新会话",
        ]:
            self.assertIn(label, workbench_source)

        for label in [
            "agent-result-dialog",
            "inventory-result-dialog",
            "image-ocr-result-dialog",
            "workbench-result-dialog",
            "pending-status-card",
            "onOpenHistory",
        ]:
            self.assertIn(label, workbench_source)

        self.assertIn('className="workbench-chat-input"', workbench_source)
        self.assertIn(".conversation-panel .conversation-footer", styles_source)
        self.assertIn("grid-template-columns: 1fr", styles_source)
        self.assertIn("grid-template-columns: auto minmax(0, 1fr) auto", styles_source)
        self.assertIn(".workbench-composer-main {", styles_source)
        self.assertIn("width: 100%", styles_source)
        self.assertIn("height: 42px", styles_source)
        self.assertNotIn("Textarea", workbench_source)
        self.assertNotIn("rows={3}", workbench_source)
        self.assertNotIn(".workbench-composer-main .sj-textarea", styles_source)
        self.assertNotIn("max-height: 180px", styles_source)
        self.assertNotIn("function ExecutionPanel", workbench_source)
        self.assertNotIn("function PendingIntentCard", workbench_source)
        self.assertNotIn("Sheet", workbench_source)
        self.assertNotIn("Drawer", workbench_source)
        self.assertNotIn("window.alert", workbench_source)
        self.assertNotIn("window.confirm", workbench_source)

    def test_workbench_confirm_dialog_uses_typed_business_sections(self):
        workbench_source = (
            ROOT / "admin" / "src" / "components" / "business" / "workbench" / "workbench-page.tsx"
        ).read_text(encoding="utf-8")
        styles_source = (ROOT / "admin" / "src" / "styles.css").read_text(encoding="utf-8")
        dialog_section = extract_function_section(workbench_source, "AgentConfirmDialog")

        for symbol in [
            "type PendingConfirmKind",
            "confirmKindForSession",
            "buildConfirmSections",
            "ConfirmSectionEditor",
            "confirm-section-title",
        ]:
            self.assertIn(symbol, workbench_source)

        for business_label in [
            "销售单明细",
            "调货明细",
            "进货明细",
            "盘点明细",
            "工作流订单",
            "商品匹配",
        ]:
            self.assertIn(business_label, workbench_source)

        self.assertIn("buildConfirmSections(session)", dialog_section)
        self.assertIn("<ConfirmSectionEditor", dialog_section)
        self.assertNotIn("flattenState(session?.state", dialog_section)

        for selector in [
            ".confirm-section-list",
            ".confirm-section-card",
            ".confirm-field-grid",
            ".confirm-section-title",
        ]:
            self.assertIn(selector, styles_source)

    def test_workbench_upload_keeps_image_visible_in_user_message(self):
        workbench_source = (
            ROOT / "admin" / "src" / "components" / "business" / "workbench" / "workbench-page.tsx"
        ).read_text(encoding="utf-8")
        http_source = (ROOT / "src" / "channels" / "http_api" / "__init__.py").read_text(encoding="utf-8")
        upload_section = extract_function_section(workbench_source, "uploadImageFile")

        self.assertIn('const userMessageId = appendMessage("user"', upload_section)
        self.assertIn("updateMessage(userMessageId", upload_section)
        self.assertIn("previewUrl", upload_section)
        self.assertIn("upload_user_text", http_source)
        self.assertIn("session.save_turn(upload_user_text, response_text)", http_source)

    def test_workbench_inventory_result_uses_inventory_cards(self):
        api_source = (ROOT / "admin" / "src" / "api.ts").read_text(encoding="utf-8")
        types_source = (ROOT / "admin" / "src" / "types.ts").read_text(encoding="utf-8")
        workbench_source = (
            ROOT / "admin" / "src" / "components" / "business" / "workbench" / "workbench-page.tsx"
        ).read_text(encoding="utf-8")
        styles_source = (ROOT / "admin" / "src" / "styles.css").read_text(encoding="utf-8")

        self.assertIn("WorkbenchInventoryCard", types_source)
        self.assertIn("InventoryCardsResult", types_source)
        self.assertIn("inventoryCards", api_source)
        self.assertIn('"/api/inventory/cards"', api_source)
        self.assertIn("inventoryKeywordFromMessage", workbench_source)
        self.assertIn("loadInventoryCardsForMessage", workbench_source)
        self.assertIn("InventoryCardGrid", workbench_source)
        self.assertIn("inventoryCards", workbench_source)
        self.assertIn(".workbench-inventory-card-grid", styles_source)
        self.assertIn(".workbench-inventory-card", styles_source)

    def test_workbench_image_workflow_confirm_skips_empty_root_section(self):
        workbench_source = (
            ROOT / "admin" / "src" / "components" / "business" / "workbench" / "workbench-page.tsx"
        ).read_text(encoding="utf-8")
        confirm_sections = extract_function_section(workbench_source, "buildConfirmSections")

        self.assertIn("hasWorkflowRows", confirm_sections)
        self.assertIn("workflowRowSections", confirm_sections)
        self.assertIn("return workflowRowSections;", confirm_sections)
        self.assertIn('pendingAction === "confirm_image_workflow_orders"', confirm_sections)

    def test_workbench_image_sales_confirm_reads_nested_order_params_customer(self):
        workbench_source = (
            ROOT / "admin" / "src" / "components" / "business" / "workbench" / "workbench-page.tsx"
        ).read_text(encoding="utf-8")
        confirm_sections = extract_function_section(workbench_source, "buildConfirmSections")

        self.assertIn('pendingAction === "confirm_image_sales"', confirm_sections)
        self.assertIn("orderParamsPrefix", confirm_sections)
        self.assertIn('"order_params.customer"', confirm_sections)
        self.assertIn('"order_params.customer_name"', confirm_sections)
        self.assertIn('["order_params.products", "products", "items", "detail"]', confirm_sections)

    def test_workbench_confirm_dialog_displays_warehouse_names_instead_of_numeric_ids(self):
        workbench_source = (
            ROOT / "admin" / "src" / "components" / "business" / "workbench" / "workbench-page.tsx"
        ).read_text(encoding="utf-8")
        confirm_sections = extract_function_section(workbench_source, "buildConfirmSections")
        dialog_section = extract_function_section(workbench_source, "AgentConfirmDialog")

        self.assertIn("warehouseNameFromId", workbench_source)
        self.assertIn("isWarehousePath", workbench_source)
        self.assertIn("displayConfirmValue", workbench_source)
        self.assertIn("coerceConfirmValue", workbench_source)
        self.assertIn("valueLabel(row.value, row.path)", workbench_source)
        self.assertIn('["warehouse_name", "warehouse_id"]', confirm_sections)
        self.assertIn('["warehouse_name", "purchase_warehouse_id", "warehouse_id"]', confirm_sections)
        self.assertNotIn('["purchase_warehouse_id", "warehouse_id", "warehouse_name"]', confirm_sections)
        self.assertIn("displayConfirmValue(field)", dialog_section)
        self.assertIn("coerceConfirmValue(nextValue, field)", dialog_section)


if __name__ == "__main__":
    unittest.main()
