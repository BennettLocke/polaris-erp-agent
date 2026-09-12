from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
ADMIN = ROOT / "admin" / "src"
SALES_CREATE = ADMIN / "components" / "business" / "sales-create"


class AdminSalesNewRedesignContractTest(unittest.TestCase):
    def test_sales_new_business_components_exist(self):
        for filename in [
            "types.ts",
            "utils.ts",
            "sales-customer-field.tsx",
            "sales-payment-fields.tsx",
            "sales-product-search.tsx",
            "sales-line-table.tsx",
            "sales-summary-card.tsx",
            "sales-result-card.tsx",
            "create-customer-dialog.tsx",
            "sales-order-detail-sheet.tsx",
            "index.ts",
        ]:
            self.assertTrue((SALES_CREATE / filename).exists(), filename)

    def test_sales_new_page_uses_business_components(self):
        app_source = (ADMIN / "App.tsx").read_text(encoding="utf-8")
        section = app_source.split("function SalesNewPage()", 1)[1].split("function SalesDetailDialog", 1)[0]

        self.assertIn("./components/business/sales-create", app_source)
        for component_name in [
            "SalesCustomerField",
            "SalesPaymentFields",
            "SalesProductSearch",
            "SalesLineTable",
            "SalesSummaryCard",
            "SalesResultCard",
            "CreateCustomerDialog",
            "SalesOrderDetailSheet",
        ]:
            self.assertIn(component_name, app_source)
            self.assertIn(f"<{component_name}", section)

        self.assertIn("continueSameCustomer", section)
        self.assertIn("startNewCustomerOrder", section)
        self.assertIn("onOpenDetail", section)

    def test_sales_create_components_follow_page_design_rules(self):
        customer_field = (SALES_CREATE / "sales-customer-field.tsx").read_text(encoding="utf-8")
        line_table = (SALES_CREATE / "sales-line-table.tsx").read_text(encoding="utf-8")
        product_search = (SALES_CREATE / "sales-product-search.tsx").read_text(encoding="utf-8")
        summary = (SALES_CREATE / "sales-summary-card.tsx").read_text(encoding="utf-8")
        result = (SALES_CREATE / "sales-result-card.tsx").read_text(encoding="utf-8")
        detail_sheet = (SALES_CREATE / "sales-order-detail-sheet.tsx").read_text(encoding="utf-8")

        self.assertNotIn("ComboboxEmpty", customer_field)
        self.assertIn("customerResults.length", customer_field)
        self.assertIn("没有找到客户", customer_field)
        self.assertIn("searched", customer_field)
        self.assertIn("不扣库存", line_table)
        self.assertIn("onWheel", line_table)
        self.assertIn("商品搜索结果", product_search)
        self.assertIn("已加入", product_search)
        self.assertNotIn("ComboboxContent", product_search)
        self.assertIn("余额", summary)
        self.assertNotIn("Separator", summary)
        self.assertIn("继续给该客户开单", result)
        self.assertIn("开新客户单", result)
        self.assertIn("Sheet", detail_sheet)
        self.assertIn("Table", detail_sheet)
        self.assertIn("AlertDialog", detail_sheet)

    def test_product_search_keeps_case_pack_visible(self):
        product_search = (SALES_CREATE / "sales-product-search.tsx").read_text(encoding="utf-8")
        styles = (ADMIN / "styles.css").read_text(encoding="utf-8")

        self.assertIn('className="sales-create-product-meta"', product_search)
        self.assertIn('className="sales-create-product-piece"', product_search)
        self.assertNotIn('product.piece_text ? `件规：${product.piece_text}` : ""].filter(Boolean).join(" · ")', product_search)
        self.assertIn(".sales-create-product-piece", styles)
        self.assertIn("white-space: nowrap", styles.split(".sales-create-product-piece", 1)[1].split("}", 1)[0])

    def test_price_hint_is_compact_and_quantity_inputs_share_draft_behavior(self):
        line_table = (SALES_CREATE / "sales-line-table.tsx").read_text(encoding="utf-8")
        product_search = (SALES_CREATE / "sales-product-search.tsx").read_text(encoding="utf-8")
        styles = (ADMIN / "styles.css").read_text(encoding="utf-8")

        self.assertIn("SalesNumberInput", line_table)
        self.assertIn("SalesNumberInput", product_search)
        self.assertIn('className="sales-create-price-hint"', line_table)
        self.assertIn("TooltipContent", line_table)

        price_field = styles.split(".sales-create-price-field", 1)[1].split("}", 1)[0]
        price_hint = styles.split(".sales-create-price-hint", 1)[1].split("}", 1)[0]
        self.assertIn("display: flex", price_field)
        self.assertIn("align-items: center", price_field)
        self.assertIn("white-space: nowrap", price_hint)


if __name__ == "__main__":
    unittest.main()
