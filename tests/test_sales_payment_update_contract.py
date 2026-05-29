from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
NATIVE_SOURCE = (ROOT / "src" / "engine" / "native_db.py").read_text(encoding="utf-8")
SERVICE_SOURCE = (ROOT / "src" / "services" / "business" / "sales.py").read_text(encoding="utf-8")
HTTP_SOURCE = (ROOT / "src" / "channels" / "http_api" / "__init__.py").read_text(encoding="utf-8")
API_SOURCE = (ROOT / "admin" / "src" / "api.ts").read_text(encoding="utf-8")
DETAIL_DIALOG_SOURCE = (
    ROOT / "admin" / "src" / "components" / "business" / "sales-list" / "sales-order-detail-dialog.tsx"
).read_text(encoding="utf-8")


class SalesPaymentUpdateContractTests(unittest.TestCase):
    def test_backend_payment_update_is_transactional_and_balance_safe(self):
        self.assertIn("def update_sales_order_payment", NATIVE_SOURCE)
        method_source = NATIVE_SOURCE.split("def update_sales_order_payment", 1)[1].split("def delete_sales_order", 1)[0]

        self.assertIn("FOR UPDATE", method_source)
        self.assertIn("old_is_balance_paid", method_source)
        self.assertIn("new_is_balance_paid", method_source)
        self.assertIn("'balance_pay'", method_source)
        self.assertIn("'balance_refund'", method_source)
        self.assertIn("id<>%s", method_source)
        self.assertIn("settlement_ledger_id=NULL", method_source)

    def test_sales_payment_update_is_exposed_to_service_api_and_dialog(self):
        self.assertIn("def update_payment", SERVICE_SOURCE)
        self.assertIn('/api/sales/<int:sales_id>/payment', HTTP_SOURCE)
        self.assertIn(r're.compile(r"^/api/sales/\d+/payment$")', HTTP_SOURCE)
        self.assertIn('"调余额"', HTTP_SOURCE)
        self.assertIn("updateSalesPayment", API_SOURCE)
        self.assertIn("SalesPaymentEditDialog", DETAIL_DIALOG_SOURCE)
        self.assertIn("保存后会按后端余额规则扣款或退回", DETAIL_DIALOG_SOURCE)


if __name__ == "__main__":
    unittest.main()
