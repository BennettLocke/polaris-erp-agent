from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
NATIVE_SOURCE = (ROOT / "src" / "engine" / "native_db.py").read_text(encoding="utf-8")
SERVICE_SOURCE = (ROOT / "src" / "services" / "business" / "sales.py").read_text(encoding="utf-8")
HTTP_SOURCE = (ROOT / "src" / "channels" / "http_api" / "__init__.py").read_text(encoding="utf-8")
SCHEMA_SOURCE = (ROOT / "database" / "schema" / "002_business_core.sql").read_text(encoding="utf-8")
API_SOURCE = (ROOT / "admin" / "src" / "api.ts").read_text(encoding="utf-8")
TYPES_SOURCE = (ROOT / "admin" / "src" / "types.ts").read_text(encoding="utf-8")
APP_SOURCE = (ROOT / "admin" / "src" / "App.tsx").read_text(encoding="utf-8")
DETAIL_DIALOG_SOURCE = (
    ROOT / "admin" / "src" / "components" / "business" / "sales-list" / "sales-order-detail-dialog.tsx"
).read_text(encoding="utf-8")


class SalesPriceUpdateContractTests(unittest.TestCase):
    def test_price_update_is_transactional_and_never_changes_inventory(self):
        self.assertIn("def update_sales_order_prices", NATIVE_SOURCE)
        method_source = NATIVE_SOURCE.split("def update_sales_order_prices", 1)[1].split(
            "def update_sales_order_payment", 1
        )[0]

        self.assertIn("FOR UPDATE", method_source)
        self.assertIn("settlement_ledger_id", method_source)
        self.assertIn("UPDATE sales_order_item", method_source)
        self.assertIn("unit_price=%s", method_source)
        self.assertIn("amount=%s", method_source)
        self.assertIn("UPDATE sales_order", method_source)
        self.assertIn("goods_amount=%s", method_source)
        self.assertIn("receivable_amount=%s", method_source)
        self.assertIn("customer_price_memory", method_source)
        self.assertIn("sales_order_price_log", method_source)
        self.assertIn("balance_pay", method_source)
        self.assertIn("balance_refund", method_source)
        self.assertNotIn("_change_inventory", method_source)

    def test_price_change_log_and_detail_context_are_available(self):
        self.assertIn("CREATE TABLE IF NOT EXISTS sales_order_price_log", SCHEMA_SOURCE)
        self.assertIn('"item_id": item.get("id")', NATIVE_SOURCE)
        self.assertIn('"spu_id": item.get("spu_id")', NATIVE_SOURCE)
        self.assertIn('"unit_id": item.get("unit_id")', NATIVE_SOURCE)
        self.assertIn('"price_change_logs": price_change_logs', NATIVE_SOURCE)
        self.assertIn('"price_editable": price_editable', NATIVE_SOURCE)

    def test_price_update_is_exposed_through_service_api_and_dialog(self):
        self.assertIn("def update_prices", SERVICE_SOURCE)
        self.assertIn('/api/sales/<int:sales_id>/prices', HTTP_SOURCE)
        self.assertIn(r're.compile(r"^/api/sales/\d+/prices$")', HTTP_SOURCE)
        self.assertIn("updateSalesPrices", API_SOURCE)
        self.assertIn("SalesPriceUpdatePayload", TYPES_SOURCE)
        self.assertIn("SalesPriceEditDialog", DETAIL_DIALOG_SOURCE)
        self.assertIn("数量不可修改", DETAIL_DIALOG_SOURCE)
        self.assertIn("handleUpdatePrices", APP_SOURCE)


if __name__ == "__main__":
    unittest.main()
