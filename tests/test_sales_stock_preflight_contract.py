from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
APP_SOURCE = (ROOT / "admin" / "src" / "App.tsx").read_text(encoding="utf-8-sig")
HTTP_SOURCE = (ROOT / "src" / "channels" / "http_api" / "__init__.py").read_text(encoding="utf-8")
INVENTORY_SERVICE_SOURCE = (ROOT / "src" / "services" / "business" / "inventory.py").read_text(encoding="utf-8")
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

    def test_inventory_preflight_balance_lookup_accepts_sku_id(self):
        self.assertIn('request.args.get("sku_id", type=int)', HTTP_SOURCE)
        self.assertIn("sku_id=sku_id", HTTP_SOURCE)
        self.assertIn("sku_id: int | None = None", INVENTORY_SERVICE_SOURCE)
        self.assertIn("sku_id=sku_id", INVENTORY_SERVICE_SOURCE)
        self.assertIn("resolved_sku_id = self.resolve_sku_id", NATIVE_SOURCE)
        self.assertIn("AND s.id=%s", NATIVE_SOURCE)

    def test_manual_sales_one_case_purchase_uses_case_pack_plan(self):
        self.assertIn("salesShortagePurchasePlan", APP_SOURCE)
        self.assertIn("purchase_policy", APP_SOURCE)
        self.assertIn("case_pack_qty", APP_SOURCE)
        self.assertIn("purchaseQuantity: caseCount * casePackQty", APP_SOURCE)
        self.assertIn("quantity: item.purchaseQuantity", APP_SOURCE)
        self.assertNotIn("quantity: item.shortage", APP_SOURCE)

    def test_inventory_purchase_api_keeps_decimal_quantity(self):
        purchase_source = HTTP_SOURCE.split("def inventory_purchase_api", 1)[1].split("\n@app.route", 1)[0]
        self.assertIn("Decimal(str(quantity", purchase_source)
        self.assertNotIn("quantity = int(quantity or 0)", purchase_source)


if __name__ == "__main__":
    unittest.main()
