import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
HTTP_SOURCE = ROOT / "src" / "channels" / "http_api" / "__init__.py"
SERVICE_SOURCE = ROOT / "src" / "services" / "business" / "analytics.py"
SERVICE_INIT_SOURCE = ROOT / "src" / "services" / "business" / "__init__.py"


class AnalyticsApiContractTests(unittest.TestCase):
    def test_hot_products_service_contract(self):
        source = SERVICE_SOURCE.read_text(encoding="utf-8")

        self.assertIn("class AnalyticsService", source)
        self.assertIn("def hot_products", source)
        self.assertIn("FROM sales_order_item i", source)
        self.assertIn("JOIN sales_order s", source)
        self.assertIn("status NOT IN ('canceled', 'deleted')", source)
        self.assertIn("sku.deleted_at IS NULL", source)
        self.assertIn("sp.deleted_at IS NULL", source)
        self.assertIn("sku.status = 'active'", source)
        self.assertIn("sku.is_listed = 1", source)
        self.assertIn("SUM(i.quantity)", source)
        self.assertIn("SUM(i.amount)", source)
        self.assertIn("GROUP BY", source)

    def test_hot_products_supports_calendar_week_period(self):
        source = SERVICE_SOURCE.read_text(encoding="utf-8")

        self.assertIn('"week"', source)
        self.assertIn("WEEKDAY(CURDATE())", source)
        self.assertIn("DATE_SUB(CURDATE(), INTERVAL WEEKDAY(CURDATE()) DAY)", source)

    def test_hot_products_can_be_filtered_by_category_names(self):
        source = SERVICE_SOURCE.read_text(encoding="utf-8")
        http_source = HTTP_SOURCE.read_text(encoding="utf-8")

        self.assertIn("category_names", source)
        self.assertIn("product_category pc", source)
        self.assertIn("pc.name IN", source)
        self.assertIn("sku.primary_category_id = pc.id", source)
        self.assertIn("JSON_CONTAINS(sku.category_ids, CAST(pc.id AS CHAR))", source)
        self.assertIn("category_names", http_source)
        self.assertIn("categoryNames", http_source)
        self.assertIn("categories", http_source)
        self.assertIn("category_names=category_names", http_source)

    def test_hot_products_api_routes_are_exposed(self):
        source = HTTP_SOURCE.read_text(encoding="utf-8")
        init_source = SERVICE_INIT_SOURCE.read_text(encoding="utf-8")

        self.assertIn("get_analytics_service", init_source)
        self.assertIn('@app.route("/api/analytics/hot-products", methods=["GET"])', source)
        self.assertIn('@app.route("/api/mini/analytics/hot-products", methods=["GET", "POST"])', source)
        self.assertIn('"/api/mini/analytics/hot-products"', source)
        self.assertIn("get_analytics_service().hot_products", source)


if __name__ == "__main__":
    unittest.main()
