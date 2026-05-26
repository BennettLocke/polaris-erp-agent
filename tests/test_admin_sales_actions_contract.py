from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
ADMIN = ROOT / "admin" / "src"
SALES_LIST = ADMIN / "components" / "business" / "sales-list"


class AdminSalesActionsContractTest(unittest.TestCase):
    def test_react_sales_page_exposes_print_and_delete_actions(self):
        api_source = (ADMIN / "api.ts").read_text(encoding="utf-8")
        app_source = (ADMIN / "App.tsx").read_text(encoding="utf-8")
        detail_source = (SALES_LIST / "sales-order-detail-dialog.tsx").read_text(encoding="utf-8")
        table_source = (SALES_LIST / "sales-list-table.tsx").read_text(encoding="utf-8")
        delete_source = (SALES_LIST / "sales-delete-dialog.tsx").read_text(encoding="utf-8")

        self.assertIn("createSalesPrintTask", api_source)
        self.assertIn("/api/sales/${id}/print-task", api_source)
        self.assertIn('method: "POST"', api_source)
        self.assertIn("deleteSales", api_source)
        self.assertIn("/api/sales/${id}", api_source)
        self.assertIn('method: "DELETE"', api_source)

        self.assertIn("handlePrint", app_source)
        self.assertIn("handleDelete", app_source)
        self.assertIn("打印预览", detail_source + table_source)
        self.assertIn("打印任务", app_source)
        self.assertIn("删除销售单", delete_source)

    def test_sales_delete_confirm_uses_alert_dialog_component_layer(self):
        delete_source = (SALES_LIST / "sales-delete-dialog.tsx").read_text(encoding="utf-8")

        self.assertIn("AlertDialog", delete_source)
        self.assertIn("AlertDialogContent", delete_source)
        self.assertIn("AlertDialogAction", delete_source)
        self.assertIn("软删除", delete_source)
        self.assertNotIn("dialog-content action-dialog", delete_source)

    def test_sales_page_uses_shadcn_component_layer(self):
        app_source = (ADMIN / "App.tsx").read_text(encoding="utf-8")
        sales_page = app_source.split("function SalesPage()", 1)[1].split("function productImageUrl", 1)[0]
        sales_components = "\n".join(
            (SALES_LIST / filename).read_text(encoding="utf-8")
            for filename in [
                "sales-list-toolbar.tsx",
                "sales-list-table.tsx",
                "sales-mobile-card-list.tsx",
                "sales-order-detail-dialog.tsx",
                "sales-delete-dialog.tsx",
                "sales-list-empty.tsx",
            ]
        )

        for import_path in [
            "./components/business/sales-list",
            "@/components/ui/alert-dialog",
            "@/components/ui/badge",
            "@/components/ui/button",
            "@/components/ui/card",
            "@/components/ui/empty",
            "@/components/ui/input",
            "./components/ui/pagination",
            "@/components/ui/dialog",
            "@/components/ui/table",
            "./components/layout/toolbar",
        ]:
            self.assertIn(import_path, app_source + sales_components)

        for source_name, source in [("app", sales_page), ("components", sales_components)]:
            self.assertIn("<Button", source)
            self.assertIn("<Badge", source)
            self.assertNotIn("primary-action", source)
            self.assertNotIn("ghost-action", source)
            self.assertNotIn("status-badge", source)
            class_values = []
            for chunk in source.split('className="')[1:]:
                class_values.append(chunk.split('"', 1)[0])
            used_tokens = {token for value in class_values for token in value.split()}
            if source_name == "components":
                self.assertNotIn("panel", used_tokens)

        self.assertIn("<Pagination", sales_page)
        self.assertIn("<Input", sales_components)
        self.assertIn("<Toolbar", sales_page)
        self.assertIn("<Empty", sales_components)
        self.assertIn("<Table", sales_components)
        self.assertIn("<Dialog", sales_components)
        self.assertNotIn("<Sheet", sales_components)


if __name__ == "__main__":
    unittest.main()
