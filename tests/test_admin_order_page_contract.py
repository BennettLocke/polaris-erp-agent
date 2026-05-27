from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class AdminOrderPageContractTest(unittest.TestCase):
    def test_react_order_page_follows_order_handbook_contract(self):
        app_source = (ROOT / "admin" / "src" / "App.tsx").read_text(encoding="utf-8")
        api_source = (ROOT / "admin" / "src" / "api.ts").read_text(encoding="utf-8")
        type_source = (ROOT / "admin" / "src" / "types.ts").read_text(encoding="utf-8")
        order_page_path = ROOT / "admin" / "src" / "components" / "business" / "orders" / "orders-page.tsx"
        order_index_path = ROOT / "admin" / "src" / "components" / "business" / "orders" / "index.ts"
        http_source = (ROOT / "src" / "channels" / "http_api" / "__init__.py").read_text(encoding="utf-8")
        style_source = (ROOT / "admin" / "src" / "styles.css").read_text(encoding="utf-8")
        self.assertTrue(order_page_path.exists(), "OrdersPage must live in components/business/orders")
        self.assertTrue(order_index_path.exists(), "OrdersPage must be exported from a local index.ts")
        order_source = order_page_path.read_text(encoding="utf-8")
        order_index = order_index_path.read_text(encoding="utf-8")

        self.assertIn('from "./components/business/orders"', app_source)
        self.assertIn("<OrdersPage />", app_source)
        self.assertIn('"orders"', app_source)
        self.assertIn('route === "workflow"', app_source)
        self.assertIn('label: "订单"', app_source)
        self.assertNotIn('label: "工作流"', app_source)
        self.assertIn('export { OrdersPage } from "./orders-page"', order_index)

        for type_name in [
            "ProcessOrderRaw",
            "ProcessOrder",
            "ProcessOrderListResult",
            "ProcessOrderPayload",
            "ProcessOrderStatusPayload",
        ]:
            self.assertIn(f"export type {type_name}", type_source)

        for method, endpoint in [
            ("workflowOrders", "/api/workflow/orders"),
            ("saveWorkflowOrder", "/api/workflow/orders"),
            ("updateWorkflowOrderStatus", "/api/workflow/orders/${id}/status"),
            ("deleteWorkflowOrder", "/api/workflow/orders/${id}"),
        ]:
            self.assertIn(method, api_source)
            self.assertIn(endpoint, api_source)
        self.assertIn('params.set("filter"', api_source)
        self.assertNotIn('params.set("status", query.filter', api_source)

        for component_name in [
            "OrdersPage",
            "OrdersToolbar",
            "OrdersSummaryStrip",
            "OrdersBoard",
            "OrdersTable",
            "OrderNotice",
            "OrderThumbnail",
            "OrderImageDialog",
            "OrderFormDialog",
            "OrderDetailDialog",
            "OrderDeleteDialog",
            "normalizeProcessOrder",
            "parseOrderImages",
            "isRecentCompletedOrder",
            "groupOrdersByStatus",
        ]:
            self.assertIn(component_name, order_source)

        for shadcn_component in [
            "Card",
            "Badge",
            "Tabs",
            "DialogContent",
            "DialogTitle",
            "AlertDialogContent",
            "DropdownMenu",
            "Table",
            "Switch",
            "Skeleton",
            "Empty",
            "FieldGroup",
        ]:
            self.assertIn(shadcn_component, order_source)

        self.assertIn("订单看板", order_source)
        self.assertIn("明细表", order_source)
        self.assertIn("待制作", order_source)
        self.assertIn("待配送", order_source)
        self.assertIn("最近完成", order_source)
        self.assertIn("RECENT_COMPLETED_DAYS = 7", order_source)
        self.assertIn("GROUP_PAGE_SIZE", order_source)
        self.assertIn("groupPages", order_source)
        self.assertIn("setGroupPages", order_source)
        self.assertIn("orders-board-pagination", order_source)
        self.assertIn(".orders-board-pagination", style_source)
        self.assertNotIn("<Pagination>", order_source)
        self.assertNotIn("PaginationContent", order_source)
        self.assertNotIn("pageCount", order_source)
        self.assertNotIn("发货", order_source)
        self.assertNotIn("disabled={busy || order.completed}", order_source)
        self.assertIn("process-order-card-click-zone", order_source)
        self.assertIn("order-image-dialog", order_source)
        self.assertIn("order-image-thumbs", order_source)
        self.assertIn("onOpenImages", order_source)
        self.assertIn("event.stopPropagation()", order_source)
        self.assertNotIn("其他进行中", order_source)
        self.assertNotIn('"other"', order_source)
        self.assertIn("order_type", order_source)
        self.assertIn("completed", order_source)
        self.assertIn("raw.order_type", order_source)
        self.assertIn("order_images", order_source)
        self.assertIn("is_made", order_source)
        self.assertIn("is_delivered", order_source)
        self.assertIn("field: field", order_source)
        self.assertIn("workflowOrders({", order_source)
        self.assertIn("updateWorkflowOrderStatus", order_source)
        self.assertIn("saveWorkflowOrder", order_source)
        self.assertIn("deleteWorkflowOrder", order_source)
        self.assertIn("orders-summary-strip", order_source)
        self.assertIn("orders-toast-viewport", order_source)
        self.assertIn("orders-toast", order_source)
        self.assertIn('role="status"', order_source)
        self.assertIn('window.setTimeout(() => setNotice(""), 2400)', order_source)
        self.assertNotIn('<div className="form-success">{notice}</div>', order_source)
        self.assertNotIn("orders-inline-notice", order_source)
        self.assertIn(".orders-toast-viewport", style_source)
        toast_style = style_source.split(".orders-toast-viewport", 1)[1].split(".orders-toast", 1)[0]
        self.assertIn("position: fixed", toast_style)
        self.assertIn("right: 24px", toast_style)
        self.assertIn("bottom: 24px", toast_style)
        self.assertIn("orders-board", order_source)
        self.assertIn("process-order-thumbnail", order_source)
        self.assertIn("process-order-card", order_source)
        self.assertIn("orders-table-thumb", order_source)
        self.assertIn("orders-table", order_source)
        self.assertIn("primaryImageUrl", order_source)
        self.assertIn("order.imageUrls[0]", order_source)
        self.assertNotIn("不会扣库存", order_source)
        self.assertNotIn("SheetContent", order_source)
        self.assertNotIn("SheetTitle", order_source)
        self.assertNotIn("OrderDetailSheet", order_source)
        self.assertNotIn(" 图", order_source)
        self.assertNotIn(" 张", order_source)
        self.assertNotIn("<select", order_source)
        self.assertNotIn("<button", order_source)
        self.assertNotIn("<input", order_source)
        self.assertNotIn("window.confirm", order_source)

        self.assertIn('@app.route("/api/workflow/orders", methods=["GET", "POST"])', http_source)
        self.assertIn('@app.route("/api/workflow/orders/<int:order_id>/status", methods=["POST"])', http_source)
        self.assertIn('@app.route("/api/workflow/orders/<int:order_id>", methods=["DELETE"])', http_source)
        self.assertIn('request.args.get("filter"', http_source)


if __name__ == "__main__":
    unittest.main()
