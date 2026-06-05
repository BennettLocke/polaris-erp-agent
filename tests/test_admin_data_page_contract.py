from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class AdminDataPageContractTest(unittest.TestCase):
    def test_admin_navigation_exposes_data_page(self):
        app_source = (ROOT / "admin" / "src" / "App.tsx").read_text(encoding="utf-8")

        self.assertIn('"data"', app_source)
        self.assertIn('{ key: "data", label: "数据"', app_source)
        self.assertIn('["dashboard", "sales-new", "sales", "data", "customers"]', app_source)
        self.assertIn('data: { title: "数据"', app_source)
        self.assertIn("<DataPage />", app_source)

    def test_data_page_api_and_component_contract(self):
        api_source = (ROOT / "admin" / "src" / "api.ts").read_text(encoding="utf-8")
        types_source = (ROOT / "admin" / "src" / "types.ts").read_text(encoding="utf-8")
        page_path = ROOT / "admin" / "src" / "components" / "business" / "data" / "data-page.tsx"
        index_path = ROOT / "admin" / "src" / "components" / "business" / "data" / "index.ts"
        styles_source = (ROOT / "admin" / "src" / "styles.css").read_text(encoding="utf-8")

        self.assertTrue(page_path.exists(), "DataPage must live in components/business/data")
        self.assertTrue(index_path.exists(), "DataPage must be exported from data/index.ts")
        page_source = page_path.read_text(encoding="utf-8")
        index_source = index_path.read_text(encoding="utf-8")

        self.assertIn("AnalyticsSalesOverview", types_source)
        self.assertIn("analyticsSalesOverview", api_source)
        self.assertIn('"/api/analytics/sales-overview"', api_source)
        self.assertIn("api.analyticsSalesOverview", page_source)
        self.assertIn("api.analyticsHotProducts", page_source)
        self.assertIn('categoryNames: ["礼盒"]', page_source)
        self.assertIn('categoryNames: ["泡袋"]', page_source)
        self.assertIn("hotGiftBoxes", page_source)
        self.assertIn("hotBags", page_source)
        self.assertIn("礼盒热销", page_source)
        self.assertIn("泡袋热销", page_source)
        self.assertIn('const DEFAULT_PERIOD = "7d"', page_source)
        self.assertIn("data-page-shell", page_source)
        self.assertIn("data-kpi-grid", page_source)
        self.assertIn("data-hot-products-grid", page_source)
        self.assertIn("data-trend-table", page_source)
        self.assertIn("data-hot-products-table", page_source)
        self.assertIn("data-recent-sales", page_source)
        self.assertIn('export { DataPage } from "./data-page"', index_source)
        self.assertIn(".data-page-shell", styles_source)
        self.assertIn(".data-kpi-grid", styles_source)
        self.assertIn(".data-hot-products-grid", styles_source)


if __name__ == "__main__":
    unittest.main()
