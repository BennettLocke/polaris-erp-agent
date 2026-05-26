from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
ADMIN = ROOT / "admin" / "src"
SALES_LIST = ADMIN / "components" / "business" / "sales-list"


class AdminSalesPageRedesignContractTest(unittest.TestCase):
    def test_sales_list_business_components_exist(self):
        for filename in [
            "types.ts",
            "utils.ts",
            "sales-list-toolbar.tsx",
            "sales-list-table.tsx",
            "sales-mobile-card-list.tsx",
            "sales-order-detail-dialog.tsx",
            "sales-delete-dialog.tsx",
            "sales-list-empty.tsx",
            "index.ts",
        ]:
            self.assertTrue((SALES_LIST / filename).exists(), filename)

    def test_sales_page_uses_sales_list_business_components(self):
        app_source = (ADMIN / "App.tsx").read_text(encoding="utf-8")
        sales_page = app_source.split("function SalesPage()", 1)[1].split("function productImageUrl", 1)[0]

        self.assertIn("./components/business/sales-list", app_source)
        for component_name in [
            "SalesListToolbar",
            "SalesListTable",
            "SalesMobileCardList",
            "SalesOrderDetailDialog",
            "SalesDeleteDialog",
            "SalesListEmpty",
        ]:
            self.assertIn(component_name, app_source)
            self.assertIn(f"<{component_name}", sales_page)

        self.assertNotIn("function SalesDetailDialog", app_source)
        self.assertNotIn("function SalesDeleteConfirmDialog", app_source)

    def test_sales_list_components_follow_page_design_rules(self):
        toolbar = (SALES_LIST / "sales-list-toolbar.tsx").read_text(encoding="utf-8")
        table = (SALES_LIST / "sales-list-table.tsx").read_text(encoding="utf-8")
        mobile_cards = (SALES_LIST / "sales-mobile-card-list.tsx").read_text(encoding="utf-8")
        detail_dialog = (SALES_LIST / "sales-order-detail-dialog.tsx").read_text(encoding="utf-8")
        delete_dialog = (SALES_LIST / "sales-delete-dialog.tsx").read_text(encoding="utf-8")

        self.assertIn("<form", toolbar)
        self.assertIn("onSubmit", toolbar)
        self.assertIn("重置", toolbar)
        self.assertIn("付款", toolbar)
        self.assertIn("日期", toolbar)
        self.assertNotIn("ComboboxEmpty", toolbar)

        self.assertIn("Table", table)
        self.assertIn("DropdownMenu", table)
        self.assertIn("复制单号", table)
        self.assertIn("商品摘要", table)

        self.assertIn("Card", mobile_cards)
        self.assertIn("更多", mobile_cards)

        self.assertIn("Dialog", detail_dialog)
        self.assertIn("Tabs", detail_dialog)
        self.assertIn("Table", detail_dialog)
        self.assertIn("sales-order-detail-dialog", detail_dialog)
        self.assertNotIn("Sheet", detail_dialog)
        self.assertNotIn("drawer-content", detail_dialog)

        self.assertIn("AlertDialog", delete_dialog)
        self.assertIn("软删除", delete_dialog)
        self.assertIn("不扣库存", delete_dialog)

    def test_sales_api_uses_structured_query_options(self):
        api_source = (ADMIN / "api.ts").read_text(encoding="utf-8")

        self.assertIn("SalesListQuery", api_source)
        self.assertIn("payStatus", api_source)
        self.assertIn("dateFrom", api_source)
        self.assertIn("dateTo", api_source)
        self.assertIn("URLSearchParams", api_source)

    def test_sales_page_header_is_compact(self):
        app_source = (ADMIN / "App.tsx").read_text(encoding="utf-8")
        sales_page = app_source.split("function SalesPage()", 1)[1].split("function productImageUrl", 1)[0]
        sales_header = sales_page.split('<CardContent className="sales-page-content">', 1)[0]

        self.assertIn("sales-page-header", sales_page)
        self.assertIn("sales-page-count", sales_page)
        self.assertNotIn("<Badge", sales_header)


if __name__ == "__main__":
    unittest.main()
