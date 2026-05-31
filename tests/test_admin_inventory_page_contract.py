from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class AdminInventoryPageContractTest(unittest.TestCase):
    def test_inventory_stock_number_click_opens_stocktake_with_original_quantity(self):
        inventory_source = (
            ROOT / "admin" / "src" / "components" / "business" / "inventory" / "inventory-page.tsx"
        ).read_text(encoding="utf-8")
        style_source = (ROOT / "admin" / "src" / "styles.css").read_text(encoding="utf-8")

        matrix_section = inventory_source.split("function InventoryOverviewMatrix", 1)[1].split("function InventoryBalanceTable", 1)[0]
        balance_section = inventory_source.split("function InventoryBalanceTable", 1)[1].split("function InventoryLedgerTable", 1)[0]
        dialog_section = inventory_source.split("function InventoryActionDialog", 1)[1].split("function InventoryRiskConfirmDialog", 1)[0]

        self.assertIn('onAction("stocktake", row)', matrix_section)
        self.assertIn("disabled={!row || !canStocktakeInventory}", matrix_section)
        self.assertIn('aria-label={`盘点 ${sku.color} ${warehouse.label} 当前库存 ${quantityText(qty)}`}', matrix_section)
        self.assertIn("inventory-stocktake-link", balance_section)
        self.assertIn('onAction("stocktake", row)', balance_section)
        self.assertIn('disabled={!tracksStock || !canStocktakeInventory}', balance_section)
        self.assertIn("inventory-stocktake-origin", dialog_section)
        self.assertIn("原库存", dialog_section)
        self.assertIn("rowQuantity(selectedRow)", dialog_section)
        self.assertIn("仓库", dialog_section)
        self.assertIn("新盘点数量", dialog_section)
        self.assertIn(".inventory-stocktake-origin", style_source)

    def test_inventory_ledger_uses_exact_filters_and_risk_confirmation(self):
        api_source = (ROOT / "admin" / "src" / "api.ts").read_text(encoding="utf-8")
        inventory_page_path = ROOT / "admin" / "src" / "components" / "business" / "inventory" / "inventory-page.tsx"
        inventory_source = inventory_page_path.read_text(encoding="utf-8")
        http_source = (ROOT / "src" / "channels" / "http_api" / "__init__.py").read_text(encoding="utf-8")
        service_source = (ROOT / "src" / "services" / "business" / "inventory.py").read_text(encoding="utf-8")
        db_source = (ROOT / "src" / "engine" / "native_db.py").read_text(encoding="utf-8")
        style_source = (ROOT / "admin" / "src" / "styles.css").read_text(encoding="utf-8")

        self.assertIn("skuId?: number | string", api_source)
        self.assertIn('params.set("sku_id", String(options.skuId))', api_source)
        self.assertIn("api.inventoryLedger({ skuId:", inventory_source)
        self.assertIn("warehouseId: row.warehouse_id", inventory_source)
        ledger_drawer_source = inventory_source.split("function InventoryLedgerDrawer", 1)[1].split("function InventoryActionDialog", 1)[0]
        self.assertNotIn("keyword: row.sku_no", ledger_drawer_source)

        self.assertIn('sku_id = request.args.get("sku_id", type=int)', http_source)
        self.assertIn('warehouse_id = request.args.get("warehouse_id", type=int)', http_source)
        ledger_route_source = http_source.split("def native_inventory_ledger_api", 1)[1].split("\n\n@app.route", 1)[0]
        self.assertIn("get_inventory_service().ledger(", ledger_route_source)
        self.assertIn("sku_id=sku_id", ledger_route_source)
        self.assertIn("warehouse_id=warehouse_id", ledger_route_source)
        self.assertIn("def ledger(", service_source)
        self.assertIn("sku_id: int | None = None", service_source)
        self.assertIn("warehouse_id: int | None = None", service_source)
        self.assertIn("inventory_ledger(", service_source)
        self.assertIn("sku_id=sku_id", service_source)
        self.assertIn("warehouse_id=warehouse_id", service_source)
        self.assertIn("def inventory_ledger(", db_source)
        self.assertIn("sku_id: int | None = None", db_source)
        self.assertIn("warehouse_id: int | None = None", db_source)
        self.assertIn("l.sku_id=%s", db_source)
        self.assertIn("l.warehouse_id=%s", db_source)

        for token in [
            "AlertDialogContent",
            "type InventoryRiskConfirm",
            "buildInventoryRisk",
            "InventoryRiskConfirmDialog",
            "riskConfirm",
            "setRiskConfirm",
            "executeAction",
            "transfer_over_stock",
            "stocktake_large_delta",
            "变更后库存",
            "影响仓库",
            "inventory-risk-grid",
        ]:
            self.assertIn(token, inventory_source)
        self.assertIn(".inventory-risk-grid", style_source)

    def test_inventory_status_filter_is_server_side_paginated(self):
        api_source = (ROOT / "admin" / "src" / "api.ts").read_text(encoding="utf-8")
        inventory_source = (
            ROOT / "admin" / "src" / "components" / "business" / "inventory" / "inventory-page.tsx"
        ).read_text(encoding="utf-8")
        http_source = (ROOT / "src" / "channels" / "http_api" / "__init__.py").read_text(encoding="utf-8")
        service_source = (ROOT / "src" / "services" / "business" / "inventory.py").read_text(encoding="utf-8")
        db_source = (ROOT / "src" / "engine" / "native_db.py").read_text(encoding="utf-8")

        self.assertIn("stockStatus?: string", api_source)
        self.assertIn('params.set("stock_status", options.stockStatus)', api_source)
        self.assertIn("function changeStatus", inventory_source)
        self.assertIn("stockStatus: nextStatus", inventory_source)
        self.assertIn("onStatusChange={changeStatus}", inventory_source)
        self.assertNotIn('status !== "all" ? 1 : pageCount', inventory_source)
        self.assertIn('stock_status = (request.args.get("stock_status") or "").strip()', http_source)
        self.assertIn("stock_status=stock_status", http_source)
        self.assertIn("stock_status: str = \"\"", service_source)
        self.assertIn("stock_status=stock_status", service_source)
        self.assertIn("stock_status: str = \"\"", db_source)
        self.assertIn("quantity_expr", db_source)
        self.assertIn("stock_status == \"zero\"", db_source)
        self.assertIn("stock_status == \"negative\"", db_source)

    def test_inventory_action_dialog_searches_product_level_sku_candidates(self):
        api_source = (ROOT / "admin" / "src" / "api.ts").read_text(encoding="utf-8")
        inventory_source = (
            ROOT / "admin" / "src" / "components" / "business" / "inventory" / "inventory-page.tsx"
        ).read_text(encoding="utf-8")
        style_source = (ROOT / "admin" / "src" / "styles.css").read_text(encoding="utf-8")
        dialog_section = inventory_source.split("function InventoryActionDialog", 1)[1].split("function InventoryRiskConfirmDialog", 1)[0]

        self.assertIn("pageSize?: number", api_source)
        self.assertIn("INVENTORY_ACTION_LOOKUP_PAGE_SIZE", inventory_source)
        self.assertIn("function inventoryActionLookupKeyword", inventory_source)
        self.assertIn('const nextLookupKeyword = row ? inventoryActionLookupKeyword(row) : ""', dialog_section)
        self.assertIn("setLookupKeyword(nextLookupKeyword)", dialog_section)
        self.assertIn("pageSize: INVENTORY_ACTION_LOOKUP_PAGE_SIZE", dialog_section)
        self.assertIn('stockStatus: "all"', dialog_section)
        self.assertNotIn("rowTitle(row)} ${rowColor(row)", dialog_section)
        self.assertNotIn("!action?.row ?", dialog_section)
        self.assertIn("rowWarehouseLabel(row)", dialog_section)
        self.assertIn("inventory-action-result-main", dialog_section)
        self.assertIn("inventory-action-result-meta", dialog_section)
        self.assertIn(".inventory-action-result-main", style_source)
        self.assertIn(".inventory-action-result-meta", style_source)

    def test_inventory_overview_pages_by_product_to_keep_colors_together(self):
        api_source = (ROOT / "admin" / "src" / "api.ts").read_text(encoding="utf-8")
        inventory_source = (
            ROOT / "admin" / "src" / "components" / "business" / "inventory" / "inventory-page.tsx"
        ).read_text(encoding="utf-8")
        http_source = (ROOT / "src" / "channels" / "http_api" / "__init__.py").read_text(encoding="utf-8")
        service_source = (ROOT / "src" / "services" / "business" / "inventory.py").read_text(encoding="utf-8")
        db_source = (ROOT / "src" / "engine" / "native_db.py").read_text(encoding="utf-8")

        self.assertIn("groupByProduct?: boolean", api_source)
        self.assertIn('params.set("group_by_product", "1")', api_source)
        self.assertIn('groupByProduct: nextTab === "overview"', inventory_source)
        self.assertIn('group_by_product = request.args.get("group_by_product", "0")', http_source)
        self.assertIn("group_by_product=group_by_product", http_source)
        self.assertIn("group_by_product: bool = False", service_source)
        self.assertIn("group_by_product=group_by_product", service_source)
        self.assertIn("group_by_product: bool = False", db_source)
        self.assertIn("page_spu", db_source)
        self.assertIn("sp.id IN", db_source)

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
        self.assertIn("<InventoryPage currentUser={user} />", app_source)
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
