from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class AdminCustomerCardsContractTest(unittest.TestCase):
    def test_customer_page_uses_shadcn_customer_components(self):
        customers_dir = ROOT / "admin" / "src" / "components" / "business" / "customers"
        badge_path = ROOT / "admin" / "src" / "components" / "ui" / "badge.tsx"
        app_source = (ROOT / "admin" / "src" / "App.tsx").read_text(encoding="utf-8")
        css_source = (ROOT / "admin" / "src" / "styles.css").read_text(encoding="utf-8")
        api_source = (ROOT / "admin" / "src" / "api.ts").read_text(encoding="utf-8")
        service_source = (ROOT / "src" / "services" / "business" / "customers.py").read_text(encoding="utf-8")
        http_source = (ROOT / "src" / "channels" / "http_api" / "__init__.py").read_text(encoding="utf-8")
        customer_sources = "\n".join(
            path.read_text(encoding="utf-8")
            for path in customers_dir.glob("*.tsx")
        )

        self.assertTrue(customers_dir.exists())
        self.assertTrue(badge_path.exists())
        badge_source = badge_path.read_text(encoding="utf-8")
        self.assertIn("function Badge", badge_source)
        self.assertIn("BadgeVariant", badge_source)
        self.assertIn("sj-badge--outline", badge_source)

        self.assertIn('from "./components/business/customers"', app_source)
        self.assertIn("<CustomersPage />", app_source)
        self.assertIn("type CustomerListQuery", api_source)
        self.assertIn('params.set("page"', api_source)
        self.assertIn('params.set("page_size"', api_source)
        self.assertIn('params.set("filter"', api_source)
        self.assertIn("updateCustomer:", api_source)
        self.assertIn("customerStatement:", api_source)
        self.assertIn("customerStatementPdfUrl:", api_source)
        self.assertIn("def list_page(", service_source)
        self.assertIn("customer_list_page", service_source)
        self.assertIn("def statement(", service_source)
        self.assertIn("def _statement_pdf_font_name(", service_source)
        self.assertIn("Microsoft YaHei", service_source)
        self.assertIn("C:/Windows/Fonts/msyh.ttc", service_source)
        self.assertIn("SjStatementFont", service_source)
        self.assertIn("肆计包装设计对账单", service_source)
        self.assertNotIn("肆计包装·设计对账单", service_source)
        self.assertNotIn("summary_rows =", service_source)
        self.assertNotIn("ledger_table =", service_source)
        self.assertNotIn("收款/余额流水", service_source)
        self.assertIn("def update_profile(", service_source)
        self.assertIn("filter_value = (request.args.get(\"filter\")", http_source)
        self.assertIn("get_customer_service().list_page", http_source)
        self.assertIn("get_customer_service().update_profile", http_source)
        self.assertIn("/api/customers/<int:customer_id>/statement", http_source)
        self.assertIn("/api/customers/<int:customer_id>/statement.pdf", http_source)

        for component_token in [
            "<Badge",
            "<Button",
            "<Card",
            "<Dialog",
            "<DropdownMenu",
            "<Empty",
            "<Field",
            "<Pagination",
            "<Skeleton",
            "<Tabs",
            "<Table",
            "<Toolbar",
        ]:
            self.assertIn(component_token, customer_sources)

        customers_page = (customers_dir / "customers-page.tsx").read_text(encoding="utf-8")
        self.assertIn("const customerPageSize = 12", customers_page)
        self.assertIn("api.customers({", customers_page)
        self.assertIn("pageSize: customerPageSize", customers_page)
        self.assertIn("filter: nextFilter", customers_page)
        self.assertIn("<CustomerFormDialog", customers_page)
        self.assertIn("customers-page-count", customers_page)
        self.assertIn("customer-warning-strip", customers_page)
        self.assertIn("summary.noPhone", customers_page)
        self.assertIn("summary.normalDebt", customers_page)
        self.assertIn("function goToPage", customers_page)
        self.assertIn("<PaginationPrevious", customers_page)
        self.assertIn("<PaginationNext", customers_page)
        self.assertNotIn("items.filter", customers_page)
        self.assertNotIn(".slice(", customers_page)
        self.assertNotIn("setPage((prev)", customers_page)
        self.assertNotIn("手机号绑定走身份服务", customer_sources)
        self.assertNotIn("电话保存会同步身份绑定", customer_sources)
        self.assertNotIn("IdentityLinkService", customer_sources)
        self.assertNotIn("auth_identity", customer_sources)
        self.assertNotIn(".customer-profile-empty", css_source)
        self.assertIn('<TabsTrigger value="statement">对账单</TabsTrigger>', customer_sources)
        self.assertIn("<CustomerStatementDialog", customer_sources)
        self.assertIn("DatePicker", customer_sources)
        self.assertNotIn('type="date"', customer_sources)
        self.assertIn("ledgerPage", customer_sources)
        self.assertIn("ledgerTotal", customer_sources)
        self.assertIn("loadLedgerPage", customer_sources)
        self.assertIn("ledger-page-count", customer_sources)

        for legacy_token in [
            'className="primary-action"',
            'className="ghost-action"',
            'className="status-badge"',
            'className="panel"',
            "<select",
        ]:
            self.assertNotIn(legacy_token, customer_sources)

        for css_token in [
            ".sj-badge",
            ".sj-badge--outline",
            ".customer-card-grid",
            ".customer-card-new",
            ".customer-card-metrics",
            ".customers-pagination",
            ".customers-page-count",
            ".customer-warning-strip",
            ".customer-detail-dialog",
            ".customer-detail-metrics",
            ".ledger-pagination-row",
            ".customer-action-dialog",
            ".customer-form-dialog",
            ".customer-form-grid",
            ".customer-month-grid",
            ".sj-date-picker-content",
        ]:
            self.assertIn(css_token, css_source)
        self.assertIn("z-index: 120", css_source)


if __name__ == "__main__":
    unittest.main()
