from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
APP_SOURCE = (ROOT / "admin" / "src" / "App.tsx").read_text(encoding="utf-8-sig")
HTTP_SOURCE = (ROOT / "src" / "channels" / "http_api" / "__init__.py").read_text(encoding="utf-8")
SALES_SERVICE_SOURCE = (ROOT / "src" / "services" / "business" / "sales.py").read_text(encoding="utf-8")
NATIVE_SOURCE = (ROOT / "src" / "engine" / "native_db.py").read_text(encoding="utf-8")


class SalesStockPreflightContractTest(unittest.TestCase):
    def test_manual_sales_prechecks_stock_and_offers_purchase_before_submit(self):
        self.assertIn("type SalesStockShortage", APP_SOURCE)
        self.assertIn("ensureSalesStockBeforeSubmit", APP_SOURCE)
        self.assertIn("api.inventoryBalances", APP_SOURCE)
        self.assertIn("setStockShortage", APP_SOURCE)
        self.assertIn("submitSalesOrderAfterStockReady", APP_SOURCE)
        self.assertIn("api.createInventoryPurchase", APP_SOURCE)
        self.assertIn("allow_negative_stock: false", APP_SOURCE)
        self.assertIn("先进货并开单", APP_SOURCE)
        self.assertIn("库存不足", APP_SOURCE)
        self.assertIn("allow_negative_stock = body.get", HTTP_SOURCE)
        self.assertIn("allow_negative_stock=allow_negative_stock", SALES_SERVICE_SOURCE)
        self.assertIn("allow_negative_stock: Any | None = None", NATIVE_SOURCE)


if __name__ == "__main__":
    unittest.main()
