from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
HTTP_API_SOURCE = (ROOT / "src" / "channels" / "http_api" / "__init__.py").read_text(encoding="utf-8")


class MiniappSalesOrdersContractTest(unittest.TestCase):
    def test_miniapp_sales_orders_are_user_scoped(self):
        self.assertIn('@app.route("/api/mini/sales-orders", methods=["GET", "POST"])', HTTP_API_SOURCE)
        start = HTTP_API_SOURCE.index("def mini_sales_orders_api")
        next_route = HTTP_API_SOURCE.index("@app.route", start + 1)
        source = HTTP_API_SOURCE[start:next_route]

        self.assertIn("_mini_request_user()", source)
        self.assertIn("_mini_order_customer_id(user)", source)
        self.assertIn("_mini_order_user_can_edit(user)", source)
        self.assertIn("_db_sales_cards", source)
        self.assertIn("customer_id=customer_id", source)
        self.assertIn('"bound_customer_id"', source)
        self.assertNotIn("_db_workflow_orders", source)


if __name__ == "__main__":
    unittest.main()
