from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class AdminInventoryPageContractTest(unittest.TestCase):
    def test_react_inventory_page_follows_inventory_handbook_contract(self):
        app_source = (ROOT / "admin" / "src" / "App.tsx").read_text(encoding="utf-8")
        api_source = (ROOT / "admin" / "src" / "api.ts").read_text(encoding="utf-8")
        type_source = (ROOT / "admin" / "src" / "types.ts").read_text(encoding="utf-8")
        inventory_page_path = ROOT / "admin" / "src" / "components" / "business" / "inventory" / "inventory-page.tsx"
        inventory_index_path = ROOT / "admin" / "src" / "components" / "business" / "inventory" / "index.ts"
        self.assertTrue(inventory_page_path.exists(), "InventoryPage must live in components/business/inventory")
        self.assertTrue(inventory_index_path.exists(), "InventoryPage must be exported from a local index.ts")
        inventory_source = inventory_page_path.read_text(encoding="utf-8")
        inventory_index = inventory_index_path.read_text(encoding="utf-8")
        http_source = (ROOT / "src" / "channels" / "http_api" / "__init__.py").read_text(encoding="utf-8")
        db_source = (ROOT / "src" / "engine" / "native_db.py").read_text(encoding="utf-8")
        style_source = (ROOT / "admin" / "src" / "styles.css").read_text(encoding="utf-8")

        self.assertIn('from "./components/business/inventory"', app_source)
        self.assertIn("<InventoryPage />", app_source)
        self.assertIn('export { InventoryPage } from "./inventory-page"', inventory_index)

        for type_name in [
            "InventoryBalance",
            "InventoryLedgerItem",
            "InventoryActionPayload",
            "InventoryActionResult",
            "InventorySummary",
            "StockDocumentItem",
            "StocktakeItem",
            "TransferItem",
        ]:
            self.assertIn(f"export type {type_name}", type_source)

        for method, endpoint in [
            ("inventoryBalances", "/api/inventory/balances"),
            ("inventoryLedger", "/api/inventory/ledger"),
            ("stockDocuments", "/api/stock-documents"),
            ("stocktakes", "/api/stocktakes"),
            ("transfers", "/api/transfers"),
            ("createInventoryPurchase", "/api/inventory/purchase"),
            ("createInventoryTransfer", "/api/inventory/transfer"),
            ("createInventoryStocktake", "/api/inventory/stocktaking"),
        ]:
            self.assertIn(method, api_source)
            self.assertIn(endpoint, api_source)

        for component_name in [
            "InventoryPage",
            "InventoryToolbar",
            "InventorySummaryStrip",
            "InventoryOverviewMatrix",
            "InventoryBalanceTable",
            "InventoryLedgerDrawer",
            "InventoryActionDialog",
            "buildInventoryMatrix",
        ]:
            self.assertIn(component_name, inventory_source)

        for shadcn_component in [
            "Table",
            "Tabs",
            "DialogContent",
            "DialogTitle",
            "SheetContent",
            "SheetTitle",
            "SelectTrigger",
            "Badge",
            "Pagination",
            "Skeleton",
            "Empty",
            "DropdownMenu",
            "FieldGroup",
        ]:
            self.assertIn(shadcn_component, inventory_source)

        self.assertIn("商品/SKU", inventory_source)
        self.assertIn("库存总览", inventory_source)
        self.assertIn("明细表", inventory_source)
        self.assertIn("inventory-matrix-grid", inventory_source)
        self.assertIn("inventory-product-card", inventory_source)
        self.assertIn("inventory-stock-cell", inventory_source)
        self.assertIn("gridTemplateColumns", inventory_source)
        self.assertIn("sku.primaryRow = rowQuantity(row) > rowQuantity(sku.primaryRow)", inventory_source)
        self.assertIn("单 SKU 流水", inventory_source)
        self.assertIn("sku_no", inventory_source)
        self.assertIn("is_stock_item", inventory_source)
        self.assertIn("不扣库存", inventory_source)
        self.assertIn("本页", inventory_source)
        self.assertIn("onWheel={inputNoWheel}", inventory_source)
        self.assertIn("createInventoryPurchase", inventory_source)
        self.assertIn("createInventoryTransfer", inventory_source)
        self.assertIn("createInventoryStocktake", inventory_source)
        self.assertIn("filterStockTrackedBalances", inventory_source)
        self.assertIn("Number(row?.is_stock_item ?? 1) !== 0", inventory_source)
        self.assertIn("setLookupRows(filterStockTrackedBalances(data.list || []))", inventory_source)
        self.assertNotIn("<img", inventory_source)
        self.assertNotIn("window.confirm", inventory_source)
        self.assertNotIn("<select", inventory_source)
        self.assertNotIn("<button", inventory_source)
        self.assertNotIn("<input", inventory_source)

        inventory_rows_source = db_source.split("def _inventory_rows", 1)[1].split("def get_product_inventory", 1)[0]
        inventory_balances_source = db_source.split("def inventory_balances", 1)[1].split("def inventory_ledger", 1)[0]
        self.assertIn("sp.id AS spu_id", inventory_rows_source)
        self.assertIn('"spu_id"', inventory_rows_source)
        self.assertIn("s.is_stock_item", inventory_rows_source)
        self.assertIn('"is_stock_item"', inventory_rows_source)
        self.assertIn('stock_mode="stock"', inventory_balances_source)
        self.assertIn("FROM product_sku s", inventory_balances_source)
        self.assertIn("CROSS JOIN warehouse w", inventory_balances_source)
        self.assertIn("LEFT JOIN inventory_balance b", inventory_balances_source)
        self.assertIn("COALESCE(b.quantity, 0)", inventory_balances_source)
        self.assertIn("w.is_enabled=1", inventory_balances_source)

        matrix_style = style_source.split(".inventory-matrix-grid", 1)[1].split(".inventory-product-card", 1)[0]
        self.assertIn("column-width", matrix_style)
        self.assertIn("column-gap", matrix_style)
        self.assertNotIn("grid-template-columns", matrix_style)
        self.assertIn("break-inside: avoid", style_source)

        self.assertIn("def _inventory_action_response", http_source)
        self.assertGreaterEqual(http_source.count("return _inventory_action_response(result)"), 3)
        for function_name in ["inventory_transfer_api", "inventory_purchase_api", "inventory_stocktaking_api"]:
            action_source = http_source.split(f"def {function_name}", 1)[1].split("\n@app.route", 1)[0]
            self.assertNotIn('"data": result})', action_source)


if __name__ == "__main__":
    unittest.main()
