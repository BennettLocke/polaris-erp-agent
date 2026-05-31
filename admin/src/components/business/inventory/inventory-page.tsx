import { useEffect, useMemo, useState, type WheelEvent } from "react";
import {
  ArrowRightLeft,
  ClipboardCheck,
  History,
  MoreHorizontal,
  PackagePlus,
  RefreshCw,
  RotateCcw,
  Search
} from "lucide-react";

import { api } from "@/api";
import { Toolbar } from "@/components/layout/toolbar";
import { Badge, type BadgeVariant } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle
} from "@/components/ui/alert-dialog";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuTrigger
} from "@/components/ui/dropdown-menu";
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationNext,
  PaginationPrevious
} from "@/components/ui/pagination";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "@/components/ui/select";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { hasPermission } from "@/lib/permissions";
import { cn } from "@/lib/utils";
import type {
  AuthUser,
  InventoryActionPayload,
  InventoryActionResult,
  InventoryBalance,
  InventoryLedgerItem,
  InventorySummary,
  StockDocumentItem,
  StocktakeItem,
  TransferItem,
  Warehouse
} from "@/types";

type InventoryTab = "overview" | "balances" | "ledger" | "documents" | "stocktakes" | "transfers";
type InventoryStatusFilter = "all" | "in_stock" | "zero" | "negative";
type InventoryActionMode = "purchase" | "transfer" | "stocktake";
type InventoryActionTarget = {
  mode: InventoryActionMode;
  row?: InventoryBalance | null;
};
type InventoryRiskConfirm = {
  type: "transfer_over_stock" | "stocktake_large_delta";
  title: string;
  description: string;
  currentQty: number;
  changeQty: number;
  afterQty: number;
  warehouseName: string;
  payload: InventoryActionPayload;
} | null;
type InventoryMatrixWarehouse = {
  key: string;
  label: string;
};
type InventoryMatrixSku = {
  key: string;
  color: string;
  skuNo: string;
  unitName: string;
  total: number;
  primaryRow: InventoryBalance | null;
  warehouseRows: Record<string, InventoryBalance>;
};
type InventoryMatrixProduct = {
  key: string;
  title: string;
  total: number;
  skus: InventoryMatrixSku[];
};

const INVENTORY_PAGE_SIZE_MIN = 20;
const INVENTORY_PAGE_SIZE_MAX = 80;
const INVENTORY_TABLE_ROW_HEIGHT = 46;
const INVENTORY_PAGE_SIZE_RESIZE_DELAY = 160;
const INVENTORY_ACTION_LOOKUP_PAGE_SIZE = 120;
const STOCKTAKE_RISK_ABSOLUTE = 20;
const STOCKTAKE_RISK_RATIO = 0.5;

const inventoryTabs: Array<{ value: InventoryTab; label: string }> = [
  { value: "overview", label: "库存总览" },
  { value: "balances", label: "明细表" },
  { value: "ledger", label: "库存流水" },
  { value: "documents", label: "出入库单" },
  { value: "stocktakes", label: "盘点单" },
  { value: "transfers", label: "调拨单" }
];

const statusFilters: Array<{ value: InventoryStatusFilter; label: string }> = [
  { value: "all", label: "全部" },
  { value: "in_stock", label: "有库存" },
  { value: "zero", label: "零库存" },
  { value: "negative", label: "负库存" }
];

function clampInventoryPageSize(value: number) {
  return Math.min(INVENTORY_PAGE_SIZE_MAX, Math.max(INVENTORY_PAGE_SIZE_MIN, value));
}

function calculateInventoryPageSize() {
  if (typeof window === "undefined") return 40;
  const availableHeight = Math.max(460, window.innerHeight - 420);
  return clampInventoryPageSize(Math.floor(availableHeight / INVENTORY_TABLE_ROW_HEIGHT) + 8);
}

function quantityNumber(value: unknown) {
  if (value === null || value === undefined || value === "") return 0;
  const parsed = Number(String(value).replace(/,/g, ""));
  return Number.isFinite(parsed) ? parsed : 0;
}

function quantityText(value: unknown) {
  const numeric = quantityNumber(value);
  if (!Number.isFinite(numeric)) return "0";
  return String(Number(numeric.toFixed(3))).replace(/\.0+$/, "");
}

function rowQuantity(row?: InventoryBalance | null) {
  return quantityNumber(row?.quantity ?? row?.inventory ?? row?.stock);
}

function rowProductId(row?: InventoryBalance | null) {
  return Number(row?.sku_id || row?.product_id || row?.id || 0);
}

function rowSpuId(row?: InventoryBalance | null) {
  return Number(row?.spu_id || 0);
}

function rowTitle(row?: InventoryBalance | null) {
  return row?.title || row?.name || "商品";
}

function rowColor(row?: InventoryBalance | null) {
  return row?.color || row?.spec || "默认颜色";
}

function inventoryActionLookupKeyword(row?: InventoryBalance | null) {
  return row ? rowTitle(row) : "";
}

function rowUnit(row?: InventoryBalance | null) {
  return row?.unit_name || "单位";
}

function warehouseLabel(warehouse?: Warehouse | null) {
  return warehouse?.name || warehouse?.warehouse_name || (warehouse?.id ? `仓库${warehouse.id}` : "仓库");
}

function rowWarehouseKey(row?: InventoryBalance | null) {
  return String(row?.warehouse_id || row?.warehouse_name || "unknown");
}

function rowWarehouseLabel(row?: InventoryBalance | null) {
  return row?.warehouse_name || (row?.warehouse_id ? `仓库${row.warehouse_id}` : "未记录仓库");
}

function warehouseNameById(warehouses: Warehouse[], id: number | string | undefined) {
  const matched = warehouses.find((warehouse) => String(warehouse.id) === String(id));
  return warehouseLabel(matched || null);
}

function buildInventoryRisk({
  mode,
  selectedRow,
  quantity,
  warehouseId,
  outWarehouseId,
  warehouseOptions,
  payload
}: {
  mode: InventoryActionMode;
  selectedRow: InventoryBalance;
  quantity: number;
  warehouseId: string;
  outWarehouseId: string;
  warehouseOptions: Warehouse[];
  payload: InventoryActionPayload;
}): InventoryRiskConfirm {
  const currentQty = rowQuantity(selectedRow);
  if (mode === "transfer" && quantity > currentQty) {
    return {
      type: "transfer_over_stock",
      title: "调货数量超过当前库存",
      description: "确认后会继续生成调拨单，可能让调出仓库出现负库存。",
      currentQty,
      changeQty: -quantity,
      afterQty: currentQty - quantity,
      warehouseName: warehouseNameById(warehouseOptions, outWarehouseId),
      payload
    };
  }
  if (mode === "stocktake") {
    const changeQty = quantity - currentQty;
    const largeAbsolute = Math.abs(changeQty) >= STOCKTAKE_RISK_ABSOLUTE;
    const largeRatio = currentQty > 0 && Math.abs(changeQty) / currentQty >= STOCKTAKE_RISK_RATIO;
    if (largeAbsolute || largeRatio) {
      return {
        type: "stocktake_large_delta",
        title: "盘点差异较大",
        description: "请确认账面库存、实盘库存和影响仓库无误，确认后会直接写入库存流水。",
        currentQty,
        changeQty,
        afterQty: quantity,
        warehouseName: warehouseNameById(warehouseOptions, warehouseId),
        payload
      };
    }
  }
  return null;
}

function formatDate(value?: string) {
  if (!value) return "未记录";
  return String(value).replace("T", " ").slice(0, 19);
}

function bizTypeText(value?: string) {
  const map: Record<string, string> = {
    sales_out: "销售出库",
    sales_delete: "删除销售单回滚",
    sales_cancel: "销售取消",
    stock_in: "入库",
    stock_out: "出库",
    stocktake: "盘点修正",
    stocktake_adjust: "盘点修正",
    transfer_out: "调拨出库",
    transfer_in: "调拨入库",
    migration_init: "迁移初始库存"
  };
  return map[value || ""] || "其他变动";
}

function documentTypeText(value?: string) {
  const map: Record<string, string> = {
    purchase_in: "采购入库",
    other_enter: "其他入库",
    other_in: "其他入库",
    return_in: "退货入库",
    other_out: "其他出库",
    loss_out: "报损出库"
  };
  return map[value || ""] || value || "未记录";
}

function statusText(value?: string) {
  const map: Record<string, string> = {
    confirmed: "已确认",
    draft: "草稿",
    canceled: "已取消",
    deleted: "已删除"
  };
  return map[value || ""] || value || "未记录";
}

function stockBadgeVariant(row: InventoryBalance): BadgeVariant {
  const qty = rowQuantity(row);
  if (qty < 0) return "destructive";
  if (qty === 0) return "secondary";
  return "outline";
}

function stockBadgeText(row: InventoryBalance) {
  const qty = rowQuantity(row);
  if (qty < 0) return "负库存";
  if (qty === 0) return "零库存";
  return "有库存";
}

function inputNoWheel(event: WheelEvent<HTMLInputElement>) {
  event.currentTarget.blur();
}

function stockTracksInventory(row?: InventoryBalance | null) {
  return Number(row?.is_stock_item ?? 1) !== 0;
}

function filterStockTrackedBalances(rows: InventoryBalance[]) {
  return rows.filter(stockTracksInventory);
}

function filterBalances(rows: InventoryBalance[], status: InventoryStatusFilter) {
  const stockRows = filterStockTrackedBalances(rows);
  if (status === "all") return stockRows;
  return stockRows.filter((row) => {
    const qty = rowQuantity(row);
    if (status === "in_stock") return qty > 0;
    if (status === "zero") return qty === 0;
    return qty < 0;
  });
}

function isBalanceTab(tab: InventoryTab) {
  return tab === "overview" || tab === "balances";
}

function buildMatrixWarehouses(rows: InventoryBalance[], warehouses: Warehouse[], selectedWarehouseId: string): InventoryMatrixWarehouse[] {
  const byKey = new Map<string, InventoryMatrixWarehouse>();
  const addWarehouse = (key: string, label: string) => {
    if (!byKey.has(key)) byKey.set(key, { key, label });
  };
  if (selectedWarehouseId !== "all") {
    const selected = warehouses.find((warehouse) => String(warehouse.id) === selectedWarehouseId);
    addWarehouse(selectedWarehouseId, warehouseLabel(selected || ({ id: Number(selectedWarehouseId) } as Warehouse)));
  } else {
    warehouses.forEach((warehouse) => addWarehouse(String(warehouse.id), warehouseLabel(warehouse)));
  }
  rows.forEach((row) => addWarehouse(rowWarehouseKey(row), rowWarehouseLabel(row)));
  return Array.from(byKey.values());
}

function buildInventoryMatrix(rows: InventoryBalance[], warehouseColumns: InventoryMatrixWarehouse[]): InventoryMatrixProduct[] {
  const products = new Map<string, InventoryMatrixProduct>();
  rows.forEach((row) => {
    const productKey = String(rowSpuId(row) || rowTitle(row));
    let product = products.get(productKey);
    if (!product) {
      product = { key: productKey, title: rowTitle(row), total: 0, skus: [] };
      products.set(productKey, product);
    }
    const skuKey = String(rowProductId(row) || row.sku_no || `${rowTitle(row)}-${rowColor(row)}`);
    let sku = product.skus.find((item) => item.key === skuKey);
    if (!sku) {
      sku = {
        key: skuKey,
        color: rowColor(row),
        skuNo: row.sku_no || `SKU${rowProductId(row)}`,
        unitName: rowUnit(row),
        total: 0,
        primaryRow: row,
        warehouseRows: {}
      };
      product.skus.push(sku);
    }
    const warehouseKey = rowWarehouseKey(row);
    sku.warehouseRows[warehouseKey] = row;
    sku.primaryRow = rowQuantity(row) > rowQuantity(sku.primaryRow) ? row : sku.primaryRow || row;
  });
  products.forEach((product) => {
    product.skus.forEach((sku) => {
      sku.total = warehouseColumns.reduce((sum, warehouse) => {
        const row = sku.warehouseRows[warehouse.key];
        return sum + (row ? rowQuantity(row) : 0);
      }, 0);
    });
    product.total = product.skus.reduce((sum, sku) => sum + sku.total, 0);
    product.skus.sort((a, b) => a.color.localeCompare(b.color, "zh-Hans-CN"));
  });
  return Array.from(products.values()).sort((a, b) => a.title.localeCompare(b.title, "zh-Hans-CN"));
}

function buildPageSummary(rows: InventoryBalance[], remoteSummary: InventorySummary | null): InventorySummary {
  if (remoteSummary && Object.keys(remoteSummary).length) return remoteSummary;
  return {
    total_sku: rows.length,
    in_stock: rows.filter((row) => rowQuantity(row) > 0).length,
    zero_stock: rows.filter((row) => rowQuantity(row) === 0).length,
    negative_stock: rows.filter((row) => rowQuantity(row) < 0).length
  };
}

function InventoryToolbar({
  keyword,
  warehouseId,
  warehouses,
  loading,
  page,
  pageCount,
  pageSize,
  total,
  activeTab,
  onKeywordChange,
  onWarehouseChange,
  onSearch,
  onReset,
  onRefresh,
  onAction,
  canAdjustInventory,
  canTransferInventory,
  canStocktakeInventory
}: {
  keyword: string;
  warehouseId: string;
  warehouses: Warehouse[];
  loading: boolean;
  page: number;
  pageCount: number;
  pageSize: number;
  total: number;
  activeTab: InventoryTab;
  onKeywordChange: (value: string) => void;
  onWarehouseChange: (value: string) => void;
  onSearch: () => void;
  onReset: () => void;
  onRefresh: () => void;
  onAction: (mode: InventoryActionMode) => void;
  canAdjustInventory: boolean;
  canTransferInventory: boolean;
  canStocktakeInventory: boolean;
}) {
  const totalText = isBalanceTab(activeTab) ? `本页 ${pageSize} 条 / 当前结果 ${total}` : `第 ${page}/${pageCount} 页 / 共 ${total} 条`;
  return (
    <Toolbar
      className="inventory-toolbar"
      title={(
        <div className="inventory-title-block">
          <CardTitle>库存工作台</CardTitle>
          <CardDescription>按 SKU、仓库和流水追溯库存，常用进货、调拨、盘点从这里处理。</CardDescription>
          <span>{totalText}</span>
        </div>
      )}
      actions={(
        <div className="inventory-page-actions">
          <Button type="button" variant="outline" size="sm" disabled={loading} onClick={onRefresh}>
            <RefreshCw data-icon="inline-start" /> 刷新
          </Button>
          <Button type="button" variant="outline" size="sm" disabled={!canAdjustInventory} onClick={() => onAction("purchase")}>
            <PackagePlus data-icon="inline-start" /> 进货
          </Button>
          <Button type="button" variant="outline" size="sm" disabled={!canTransferInventory} onClick={() => onAction("transfer")}>
            <ArrowRightLeft data-icon="inline-start" /> 调拨
          </Button>
          <Button type="button" size="sm" disabled={!canStocktakeInventory} onClick={() => onAction("stocktake")}>
            <ClipboardCheck data-icon="inline-start" /> 盘点
          </Button>
        </div>
      )}
    >
      <div className="inventory-toolbar-controls">
        <Input
          value={keyword}
          placeholder="搜索商品、颜色、编号、仓库"
          onChange={(event) => onKeywordChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") onSearch();
          }}
        />
        <Select value={warehouseId} onValueChange={onWarehouseChange}>
          <SelectTrigger>
            <SelectValue placeholder="全部仓库" />
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              <SelectItem value="all">全部仓库</SelectItem>
              {warehouses.map((warehouse) => (
                <SelectItem key={warehouse.id} value={String(warehouse.id)}>{warehouseLabel(warehouse)}</SelectItem>
              ))}
            </SelectGroup>
          </SelectContent>
        </Select>
        <Button type="button" size="sm" onClick={onSearch}>
          <Search data-icon="inline-start" /> 搜索
        </Button>
        <Button type="button" variant="outline" size="sm" onClick={onReset}>
          <RotateCcw data-icon="inline-start" /> 重置
        </Button>
      </div>
    </Toolbar>
  );
}

function InventoryStatusFilter({
  status,
  onStatusChange
}: {
  status: InventoryStatusFilter;
  onStatusChange: (value: InventoryStatusFilter) => void;
}) {
  return (
    <Tabs value={status} onValueChange={(value) => onStatusChange(value as InventoryStatusFilter)}>
      <TabsList className="inventory-status-tabs">
        {statusFilters.map((filter) => (
          <TabsTrigger key={filter.value} value={filter.value}>{filter.label}</TabsTrigger>
        ))}
      </TabsList>
    </Tabs>
  );
}

function InventorySummaryStrip({
  summary,
  warehouseName,
  loading
}: {
  summary: InventorySummary;
  warehouseName: string;
  loading: boolean;
}) {
  const items = [
    ["本页 SKU", summary.total_sku || 0],
    ["有库存", summary.in_stock || 0],
    ["零库存", summary.zero_stock || 0],
    ["负库存", summary.negative_stock || 0],
    ["当前仓库", warehouseName]
  ];
  return (
    <div className="inventory-summary-strip">
      {items.map(([label, value]) => (
        <div key={label}>
          <span>{label}</span>
          {loading ? <Skeleton /> : <strong>{value}</strong>}
        </div>
      ))}
    </div>
  );
}

function InventoryOverviewMatrix({
  rows,
  warehouses,
  warehouseId,
  loading,
  status,
  onAction,
  onOpenLedger,
  onReset,
  canAdjustInventory,
  canTransferInventory,
  canStocktakeInventory
}: {
  rows: InventoryBalance[];
  warehouses: Warehouse[];
  warehouseId: string;
  loading: boolean;
  status: InventoryStatusFilter;
  onAction: (mode: InventoryActionMode, row: InventoryBalance) => void;
  onOpenLedger: (row: InventoryBalance) => void;
  onReset: () => void;
  canAdjustInventory: boolean;
  canTransferInventory: boolean;
  canStocktakeInventory: boolean;
}) {
  const displayRows = filterBalances(rows, status);
  const warehouseColumns = buildMatrixWarehouses(displayRows, warehouses, warehouseId);
  const products = buildInventoryMatrix(displayRows, warehouseColumns);
  const matrixStyle = {
    gridTemplateColumns: `minmax(128px, 1.35fr) repeat(${Math.max(1, warehouseColumns.length)}, minmax(74px, 0.8fr)) minmax(94px, auto)`
  };
  if (loading) {
    return (
      <div className="inventory-matrix-grid">
        {Array.from({ length: 6 }, (_, index) => (
          <div key={index} className="inventory-product-card">
            <Skeleton />
            <Skeleton />
            <Skeleton />
          </div>
        ))}
      </div>
    );
  }
  if (!products.length) {
    return (
      <Empty>
        <EmptyHeader>
          <EmptyTitle>没有匹配的库存</EmptyTitle>
          <EmptyDescription>换个商品、颜色、仓库或库存状态再看。</EmptyDescription>
        </EmptyHeader>
        <Button type="button" variant="outline" size="sm" onClick={onReset}>重置筛选</Button>
      </Empty>
    );
  }
  return (
    <div className="inventory-matrix-grid">
      {products.map((product) => (
        <section key={product.key} className="inventory-product-card">
          <div className="inventory-product-card-header">
            <div>
              <h3>{product.title}</h3>
              <span>{product.skus.length} 个颜色/SKU</span>
            </div>
            <Badge variant={product.total > 0 ? "outline" : "secondary"}>合计 {quantityText(product.total)}</Badge>
          </div>
          <div className="inventory-matrix-table" style={matrixStyle}>
            <div className="inventory-matrix-head">颜色/SKU</div>
            {warehouseColumns.map((warehouse) => (
              <div key={warehouse.key} className="inventory-matrix-head inventory-matrix-number">{warehouse.label}</div>
            ))}
            <div className="inventory-matrix-head inventory-matrix-actions-head">操作</div>
            {product.skus.map((sku) => (
              <div key={`${product.key}-${sku.key}`} className="inventory-matrix-row">
                <div className="inventory-matrix-sku">
                  <strong>{sku.color}</strong>
                  <span>{sku.skuNo}</span>
                </div>
                {warehouseColumns.map((warehouse) => {
                  const row = sku.warehouseRows[warehouse.key];
                  const qty = row ? rowQuantity(row) : 0;
                  return (
                    <Button
                      key={`${sku.key}-${warehouse.key}`}
                      type="button"
                      variant="ghost"
                      size="sm"
                      className={cn(
                        "inventory-stock-cell",
                        qty < 0 && "is-negative",
                        qty === 0 && "is-zero"
                      )}
                      disabled={!row || !canStocktakeInventory}
                      aria-label={`盘点 ${sku.color} ${warehouse.label} 当前库存 ${quantityText(qty)}`}
                      onClick={() => {
                        if (row) onAction("stocktake", row);
                      }}
                    >
                      <strong>{quantityText(qty)}</strong>
                      <span>{sku.unitName}</span>
                    </Button>
                  );
                })}
                <div className="inventory-matrix-actions">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    disabled={!sku.primaryRow}
                    onClick={() => {
                      if (sku.primaryRow) onOpenLedger(sku.primaryRow);
                    }}
                  >
                    <History data-icon="inline-start" /> 流水
                  </Button>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button type="button" variant="ghost" size="icon-sm" aria-label="库存操作" disabled={!sku.primaryRow}>
                        <MoreHorizontal />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuGroup>
                        <DropdownMenuItem disabled={!sku.primaryRow || !canAdjustInventory} onSelect={() => sku.primaryRow && onAction("purchase", sku.primaryRow)}>
                          <PackagePlus data-icon="inline-start" /> 进货
                        </DropdownMenuItem>
                        <DropdownMenuItem disabled={!sku.primaryRow || !canTransferInventory} onSelect={() => sku.primaryRow && onAction("transfer", sku.primaryRow)}>
                          <ArrowRightLeft data-icon="inline-start" /> 调拨
                        </DropdownMenuItem>
                        <DropdownMenuItem disabled={!sku.primaryRow || !canStocktakeInventory} onSelect={() => sku.primaryRow && onAction("stocktake", sku.primaryRow)}>
                          <ClipboardCheck data-icon="inline-start" /> 盘点
                        </DropdownMenuItem>
                      </DropdownMenuGroup>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </div>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

function InventoryBalanceTable({
  rows,
  loading,
  status,
  onAction,
  onOpenLedger,
  onReset,
  canAdjustInventory,
  canTransferInventory,
  canStocktakeInventory
}: {
  rows: InventoryBalance[];
  loading: boolean;
  status: InventoryStatusFilter;
  onAction: (mode: InventoryActionMode, row: InventoryBalance) => void;
  onOpenLedger: (row: InventoryBalance) => void;
  onReset: () => void;
  canAdjustInventory: boolean;
  canTransferInventory: boolean;
  canStocktakeInventory: boolean;
}) {
  const displayRows = filterBalances(rows, status);
  if (loading) {
    return (
      <div className="inventory-table-skeleton">
        {Array.from({ length: 10 }, (_, index) => <Skeleton key={index} />)}
      </div>
    );
  }
  if (!displayRows.length) {
    return (
      <Empty>
        <EmptyHeader>
          <EmptyTitle>没有匹配的库存</EmptyTitle>
          <EmptyDescription>换个关键词、仓库或库存状态再试。</EmptyDescription>
        </EmptyHeader>
        <Button type="button" variant="outline" size="sm" onClick={onReset}>重置筛选</Button>
      </Empty>
    );
  }
  return (
    <Table className="inventory-balance-table">
      <TableHeader>
        <TableRow>
          <TableHead>商品/SKU</TableHead>
          <TableHead>仓库</TableHead>
          <TableHead>当前库存</TableHead>
          <TableHead>可用</TableHead>
          <TableHead>已占用</TableHead>
          <TableHead>单位</TableHead>
          <TableHead>状态</TableHead>
          <TableHead>操作</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {displayRows.map((row) => {
          const skuId = rowProductId(row);
          const tracksStock = Number(row.is_stock_item ?? 1) !== 0;
          return (
            <TableRow key={`${skuId}-${row.warehouse_id || "warehouse"}`}>
              <TableCell>
                <div className="inventory-sku-cell">
                  <strong>{rowTitle(row)}</strong>
                  <span>{rowColor(row)} · {row.sku_no || `SKU${skuId}`}</span>
                </div>
              </TableCell>
              <TableCell>{row.warehouse_name || "未记录仓库"}</TableCell>
              <TableCell className="inventory-number-cell">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className={cn(
                    "inventory-stocktake-link",
                    rowQuantity(row) < 0 && "is-negative",
                    rowQuantity(row) === 0 && "is-zero"
                  )}
                  disabled={!tracksStock || !canStocktakeInventory}
                  aria-label={`盘点 ${rowTitle(row)} ${rowColor(row)} ${row.warehouse_name || "未记录仓库"} 当前库存 ${quantityText(row.quantity ?? row.inventory ?? row.stock)}`}
                  onClick={() => onAction("stocktake", row)}
                >
                  <strong>{quantityText(row.quantity ?? row.inventory ?? row.stock)}</strong>
                </Button>
              </TableCell>
              <TableCell className="inventory-number-cell">{quantityText(row.available_qty ?? row.quantity ?? row.inventory)}</TableCell>
              <TableCell className="inventory-number-cell">{quantityText(row.reserved_qty)}</TableCell>
              <TableCell>{rowUnit(row)}</TableCell>
              <TableCell>
                <div className="inventory-status-cell">
                  <Badge variant={stockBadgeVariant(row)}>{stockBadgeText(row)}</Badge>
                  {!tracksStock ? <Badge variant="secondary">不扣库存</Badge> : null}
                </div>
              </TableCell>
              <TableCell>
                <div className="inventory-row-actions">
                  <Button type="button" variant="outline" size="sm" onClick={() => onOpenLedger(row)}>
                    <History data-icon="inline-start" /> 流水
                  </Button>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button type="button" variant="ghost" size="icon-sm" aria-label="库存操作">
                        <MoreHorizontal />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuGroup>
                        <DropdownMenuItem disabled={!tracksStock || !canAdjustInventory} onSelect={() => onAction("purchase", row)}>
                          <PackagePlus data-icon="inline-start" /> 进货
                        </DropdownMenuItem>
                        <DropdownMenuItem disabled={!tracksStock || !canTransferInventory} onSelect={() => onAction("transfer", row)}>
                          <ArrowRightLeft data-icon="inline-start" /> 调拨
                        </DropdownMenuItem>
                        <DropdownMenuItem disabled={!tracksStock || !canStocktakeInventory} onSelect={() => onAction("stocktake", row)}>
                          <ClipboardCheck data-icon="inline-start" /> 盘点
                        </DropdownMenuItem>
                      </DropdownMenuGroup>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}

function InventoryLedgerTable({ rows, loading }: { rows: InventoryLedgerItem[]; loading: boolean }) {
  if (loading) return <div className="inventory-table-skeleton">{Array.from({ length: 8 }, (_, index) => <Skeleton key={index} />)}</div>;
  if (!rows.length) {
    return (
      <Empty>
        <EmptyHeader>
          <EmptyTitle>没有库存流水</EmptyTitle>
          <EmptyDescription>当前筛选下还没有库存变动记录。</EmptyDescription>
        </EmptyHeader>
      </Empty>
    );
  }
  return (
    <Table className="inventory-ledger-table">
      <TableHeader>
        <TableRow>
          <TableHead>时间</TableHead>
          <TableHead>商品</TableHead>
          <TableHead>仓库</TableHead>
          <TableHead>变化</TableHead>
          <TableHead>变化前</TableHead>
          <TableHead>变化后</TableHead>
          <TableHead>来源</TableHead>
          <TableHead>操作人</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((row) => (
          <TableRow key={row.id}>
            <TableCell>{formatDate(row.occurred_at)}</TableCell>
            <TableCell>
              <div className="inventory-sku-cell">
                <strong>{row.title || "商品"}</strong>
                <span>{row.color || "默认颜色"} · {row.sku_no_snapshot || row.sku_id}</span>
              </div>
            </TableCell>
            <TableCell>{row.warehouse_name || "未记录仓库"}</TableCell>
            <TableCell className="inventory-number-cell"><strong>{quantityText(row.change_qty)}</strong></TableCell>
            <TableCell className="inventory-number-cell">{quantityText(row.before_qty)}</TableCell>
            <TableCell className="inventory-number-cell">{quantityText(row.after_qty)}</TableCell>
            <TableCell>{bizTypeText(row.biz_type)}</TableCell>
            <TableCell>{row.operator_name || row.operator_username || "未记录"}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function StockDocumentTable({ rows, loading }: { rows: StockDocumentItem[]; loading: boolean }) {
  if (loading) return <div className="inventory-table-skeleton">{Array.from({ length: 8 }, (_, index) => <Skeleton key={index} />)}</div>;
  if (!rows.length) {
    return (
      <Empty>
        <EmptyHeader>
          <EmptyTitle>没有出入库单</EmptyTitle>
          <EmptyDescription>当前筛选下还没有出入库记录。</EmptyDescription>
        </EmptyHeader>
      </Empty>
    );
  }
  return (
    <Table className="inventory-document-table">
      <TableHeader>
        <TableRow>
          <TableHead>单号</TableHead>
          <TableHead>类型</TableHead>
          <TableHead>方向</TableHead>
          <TableHead>仓库</TableHead>
          <TableHead>总数量</TableHead>
          <TableHead>状态</TableHead>
          <TableHead>创建人</TableHead>
          <TableHead>时间</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((row) => (
          <TableRow key={row.id}>
            <TableCell><strong>{row.doc_no || row.id}</strong></TableCell>
            <TableCell>{documentTypeText(row.doc_type)}</TableCell>
            <TableCell>{row.direction === "out" ? "出库" : "入库"}</TableCell>
            <TableCell>{row.warehouse_name || "未记录仓库"}</TableCell>
            <TableCell className="inventory-number-cell">{quantityText(row.total_quantity)}</TableCell>
            <TableCell>{statusText(row.status)}</TableCell>
            <TableCell>{row.created_by_name || row.created_by_username || "未记录"}</TableCell>
            <TableCell>{formatDate(row.created_at)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function StocktakeTable({ rows, loading }: { rows: StocktakeItem[]; loading: boolean }) {
  if (loading) return <div className="inventory-table-skeleton">{Array.from({ length: 8 }, (_, index) => <Skeleton key={index} />)}</div>;
  if (!rows.length) {
    return (
      <Empty>
        <EmptyHeader>
          <EmptyTitle>没有盘点单</EmptyTitle>
          <EmptyDescription>当前筛选下还没有盘点记录。</EmptyDescription>
        </EmptyHeader>
      </Empty>
    );
  }
  return (
    <Table className="inventory-document-table">
      <TableHeader>
        <TableRow>
          <TableHead>盘点单号</TableHead>
          <TableHead>仓库</TableHead>
          <TableHead>差异数量</TableHead>
          <TableHead>状态</TableHead>
          <TableHead>创建人</TableHead>
          <TableHead>时间</TableHead>
          <TableHead>备注</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((row) => (
          <TableRow key={row.id}>
            <TableCell><strong>{row.stocktake_no || row.id}</strong></TableCell>
            <TableCell>{row.warehouse_name || "未记录仓库"}</TableCell>
            <TableCell className="inventory-number-cell">{quantityText(row.total_diff_qty)}</TableCell>
            <TableCell>{statusText(row.status)}</TableCell>
            <TableCell>{row.created_by_name || row.created_by_username || "未记录"}</TableCell>
            <TableCell>{formatDate(row.created_at)}</TableCell>
            <TableCell>{row.note || "无"}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function TransferTable({ rows, loading }: { rows: TransferItem[]; loading: boolean }) {
  if (loading) return <div className="inventory-table-skeleton">{Array.from({ length: 8 }, (_, index) => <Skeleton key={index} />)}</div>;
  if (!rows.length) {
    return (
      <Empty>
        <EmptyHeader>
          <EmptyTitle>没有调拨单</EmptyTitle>
          <EmptyDescription>当前筛选下还没有调拨记录。</EmptyDescription>
        </EmptyHeader>
      </Empty>
    );
  }
  return (
    <Table className="inventory-document-table">
      <TableHeader>
        <TableRow>
          <TableHead>调拨单号</TableHead>
          <TableHead>调出仓</TableHead>
          <TableHead>调入仓</TableHead>
          <TableHead>总数量</TableHead>
          <TableHead>状态</TableHead>
          <TableHead>创建人</TableHead>
          <TableHead>时间</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((row) => (
          <TableRow key={row.id}>
            <TableCell><strong>{row.transfer_no || row.id}</strong></TableCell>
            <TableCell>{row.from_warehouse_name || "未记录"}</TableCell>
            <TableCell>{row.to_warehouse_name || "未记录"}</TableCell>
            <TableCell className="inventory-number-cell">{quantityText(row.total_quantity)}</TableCell>
            <TableCell>{statusText(row.status)}</TableCell>
            <TableCell>{row.created_by_name || row.created_by_username || "未记录"}</TableCell>
            <TableCell>{formatDate(row.created_at)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function InventoryLedgerDrawer({
  row,
  onClose
}: {
  row: InventoryBalance | null;
  onClose: () => void;
}) {
  const [items, setItems] = useState<InventoryLedgerItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!row) return;
    setLoading(true);
    setError("");
    api.inventoryLedger({ skuId: row.sku_id || rowProductId(row), warehouseId: row.warehouse_id, page: 1, pageSize: 30 })
      .then((data) => setItems(data.list || []))
      .catch((err) => setError(err instanceof Error ? err.message : "库存流水加载失败"))
      .finally(() => setLoading(false));
  }, [row]);

  return (
    <Sheet open={Boolean(row)} onOpenChange={(open) => {
      if (!open) onClose();
    }}>
      <SheetContent side="right" className="inventory-ledger-drawer">
        <SheetHeader>
          <SheetTitle>单 SKU 流水</SheetTitle>
          <SheetDescription>
            {row ? `${rowTitle(row)} · ${rowColor(row)} · ${row.sku_no || rowProductId(row)}` : "选择库存行查看最近变动"}
          </SheetDescription>
        </SheetHeader>
        {error ? <div className="form-error">{error}</div> : null}
        <InventoryLedgerTable rows={items} loading={loading} />
      </SheetContent>
    </Sheet>
  );
}

function InventoryActionDialog({
  action,
  warehouses,
  onClose,
  onSaved
}: {
  action: InventoryActionTarget | null;
  warehouses: Warehouse[];
  onClose: () => void;
  onSaved: (mode: InventoryActionMode, result: InventoryActionResult) => void;
}) {
  const [selectedRow, setSelectedRow] = useState<InventoryBalance | null>(null);
  const [lookupKeyword, setLookupKeyword] = useState("");
  const [lookupRows, setLookupRows] = useState<InventoryBalance[]>([]);
  const [warehouseId, setWarehouseId] = useState("2");
  const [outWarehouseId, setOutWarehouseId] = useState("2");
  const [enterWarehouseId, setEnterWarehouseId] = useState("1");
  const [quantity, setQuantity] = useState("");
  const [note, setNote] = useState("");
  const [loadingLookup, setLoadingLookup] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [riskConfirm, setRiskConfirm] = useState<InventoryRiskConfirm>(null);
  const mode = action?.mode || "purchase";
  const open = Boolean(action);
  const warehouseOptions = useMemo(
    () => warehouses.length ? warehouses : [{ id: 2, name: "默认仓库" } as Warehouse],
    [warehouses]
  );

  useEffect(() => {
    if (!action) return;
    const row = action.row || null;
    const defaultWarehouseId = String(row?.warehouse_id || warehouseOptions[0]?.id || 2);
    const nextEnterWarehouse = String(warehouseOptions.find((warehouse) => String(warehouse.id) !== defaultWarehouseId)?.id || defaultWarehouseId);
    const nextLookupKeyword = row ? inventoryActionLookupKeyword(row) : "";
    setSelectedRow(row);
    setLookupKeyword(nextLookupKeyword);
    setLookupRows(row ? [row] : []);
    setWarehouseId(defaultWarehouseId);
    setOutWarehouseId(defaultWarehouseId);
    setEnterWarehouseId(nextEnterWarehouse);
    setQuantity(mode === "stocktake" && row ? quantityText(row.quantity ?? row.inventory ?? row.stock) : "");
    setNote("");
    setError("");
    setRiskConfirm(null);
    if (nextLookupKeyword) {
      void searchSkuRows(nextLookupKeyword);
    }
  }, [action, mode, warehouseOptions]);

  async function searchSkuRows(nextKeyword = lookupKeyword) {
    const keyword = nextKeyword.trim();
    if (!keyword) {
      setLookupRows([]);
      return;
    }
    setLoadingLookup(true);
    setError("");
    try {
      const data = await api.inventoryBalances({
        keyword,
        stockStatus: "all",
        page: 1,
        pageSize: INVENTORY_ACTION_LOOKUP_PAGE_SIZE
      });
      setLookupRows(filterStockTrackedBalances(data.list || []));
    } catch (err) {
      setError(err instanceof Error ? err.message : "商品/SKU 搜索失败");
    } finally {
      setLoadingLookup(false);
    }
  }

  async function submitAction() {
    if (!selectedRow) {
      setError("请先选择具体 SKU");
      return;
    }
    const productId = rowProductId(selectedRow);
    if (!productId) {
      setError("当前库存行缺少 SKU ID");
      return;
    }
    const amount = Number(quantity);
    if (!Number.isFinite(amount) || amount < 0 || (mode !== "stocktake" && amount <= 0)) {
      setError(mode === "stocktake" ? "实盘库存必须大于等于 0" : "数量必须大于 0");
      return;
    }
    if (mode === "transfer" && outWarehouseId === enterWarehouseId) {
      setError("调出仓库和调入仓库不能相同");
      return;
    }
    const payload: InventoryActionPayload = {
      product_id: productId,
      sku_id: productId,
      unit_id: Number(selectedRow.unit_id || 1),
      quantity: amount,
      note: note.trim()
    };
    if (mode === "purchase") payload.warehouse_id = Number(warehouseId);
    if (mode === "stocktake") payload.warehouse_id = Number(warehouseId);
    if (mode === "transfer") {
      payload.out_warehouse_id = Number(outWarehouseId);
      payload.enter_warehouse_id = Number(enterWarehouseId);
    }
    const risk = buildInventoryRisk({
      mode,
      selectedRow,
      quantity: amount,
      warehouseId,
      outWarehouseId,
      warehouseOptions,
      payload
    });
    if (risk) {
      setRiskConfirm(risk);
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      const result = mode === "purchase"
        ? await api.createInventoryPurchase(payload)
        : mode === "transfer"
          ? await api.createInventoryTransfer(payload)
          : await api.createInventoryStocktake(payload);
      onSaved(mode, result);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "库存操作失败");
    } finally {
      setSubmitting(false);
    }
  }

  const title = mode === "purchase" ? "进货入库" : mode === "transfer" ? "仓库调拨" : "盘点修正";
  async function executeAction(payload: InventoryActionPayload) {
    setSubmitting(true);
    setError("");
    try {
      const result = mode === "purchase"
        ? await api.createInventoryPurchase(payload)
        : mode === "transfer"
          ? await api.createInventoryTransfer(payload)
          : await api.createInventoryStocktake(payload);
      onSaved(mode, result);
      setRiskConfirm(null);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "库存操作失败");
    } finally {
      setSubmitting(false);
    }
  }

  const selectedSummary = selectedRow ? `${rowTitle(selectedRow)} · ${rowColor(selectedRow)} · ${selectedRow.sku_no || rowProductId(selectedRow)}` : "尚未选择 SKU";
  const selectedOriginalQty = selectedRow ? rowQuantity(selectedRow) : 0;
  const selectedWarehouseLabel = selectedRow ? rowWarehouseLabel(selectedRow) : "";

  return (
    <>
    <Dialog open={open} onOpenChange={(nextOpen) => {
      if (!nextOpen) onClose();
    }}>
      <DialogContent className="inventory-action-dialog">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>库存动作必须锁定到商品/SKU、颜色、编号和仓库，保存后由服务层写流水。</DialogDescription>
        </DialogHeader>
        {error ? <div className="form-error">{error}</div> : null}
        <FieldGroup>
          <Field>
            <FieldLabel>商品/SKU</FieldLabel>
            <div className="inventory-action-selected">
              <strong>{selectedSummary}</strong>
              <span>{selectedRow ? `单位：${rowUnit(selectedRow)}，当前库存：${quantityText(selectedRow.quantity ?? selectedRow.inventory ?? selectedRow.stock)}` : "从库存行进入会自动带入，右上角动作需要先搜索选择。"}</span>
              {mode === "stocktake" && selectedRow ? (
                <div className="inventory-stocktake-origin">
                  <div>
                    <span>原库存</span>
                    <strong>{quantityText(selectedOriginalQty)} {rowUnit(selectedRow)}</strong>
                  </div>
                  <div>
                    <span>仓库</span>
                    <strong>{selectedWarehouseLabel}</strong>
                  </div>
                </div>
              ) : null}
            </div>
          </Field>
          <Field>
            <FieldLabel>搜索 SKU</FieldLabel>
            <div className="inventory-action-search">
              <Input
                value={lookupKeyword}
                placeholder="输入商品、颜色或 SJ 编号"
                onChange={(event) => setLookupKeyword(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") void searchSkuRows();
                }}
              />
              <Button type="button" variant="outline" size="sm" disabled={loadingLookup} onClick={() => void searchSkuRows()}>
                <Search data-icon="inline-start" /> 搜索
              </Button>
            </div>
            {lookupRows.length ? (
              <div className="inventory-action-results">
                {lookupRows.map((row) => (
                  <Button
                    key={`${rowProductId(row)}-${row.warehouse_id || "warehouse"}`}
                    type="button"
                    variant={selectedRow === row ? "default" : "outline"}
                    size="sm"
                    className="inventory-action-result-button"
                    onClick={() => {
                      setSelectedRow(row);
                      setWarehouseId(String(row.warehouse_id || warehouseId));
                      setOutWarehouseId(String(row.warehouse_id || outWarehouseId));
                    }}
                  >
                    <span className="inventory-action-result-main">
                      {rowTitle(row)} · {rowColor(row)} · {row.sku_no || rowProductId(row)}
                    </span>
                    <span className="inventory-action-result-meta">
                      {rowWarehouseLabel(row)} · 当前 {quantityText(row.quantity ?? row.inventory ?? row.stock)} {rowUnit(row)}
                    </span>
                  </Button>
                ))}
              </div>
            ) : null}
          </Field>
          {mode === "transfer" ? (
            <div className="inventory-action-two-cols">
              <Field>
                <FieldLabel>调出仓</FieldLabel>
                <Select value={outWarehouseId} onValueChange={setOutWarehouseId}>
                  <SelectTrigger><SelectValue placeholder="选择调出仓" /></SelectTrigger>
                  <SelectContent>
                    <SelectGroup>
                      {warehouseOptions.map((warehouse) => (
                        <SelectItem key={warehouse.id} value={String(warehouse.id)}>{warehouseLabel(warehouse)}</SelectItem>
                      ))}
                    </SelectGroup>
                  </SelectContent>
                </Select>
              </Field>
              <Field>
                <FieldLabel>调入仓</FieldLabel>
                <Select value={enterWarehouseId} onValueChange={setEnterWarehouseId}>
                  <SelectTrigger><SelectValue placeholder="选择调入仓" /></SelectTrigger>
                  <SelectContent>
                    <SelectGroup>
                      {warehouseOptions.map((warehouse) => (
                        <SelectItem key={warehouse.id} value={String(warehouse.id)}>{warehouseLabel(warehouse)}</SelectItem>
                      ))}
                    </SelectGroup>
                  </SelectContent>
                </Select>
              </Field>
            </div>
          ) : (
            <Field>
              <FieldLabel>{mode === "stocktake" ? "盘点仓库" : "入库仓库"}</FieldLabel>
              <Select value={warehouseId} onValueChange={setWarehouseId}>
                <SelectTrigger><SelectValue placeholder="选择仓库" /></SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    {warehouseOptions.map((warehouse) => (
                      <SelectItem key={warehouse.id} value={String(warehouse.id)}>{warehouseLabel(warehouse)}</SelectItem>
                    ))}
                  </SelectGroup>
                </SelectContent>
              </Select>
            </Field>
          )}
          <Field>
            <FieldLabel>{mode === "stocktake" ? "新盘点数量" : "数量"}</FieldLabel>
            <Input
              value={quantity}
              type="number"
              min={mode === "stocktake" ? 0 : 1}
              placeholder={mode === "stocktake" ? "输入实际盘点库存" : "输入数量"}
              onWheel={inputNoWheel}
              onChange={(event) => setQuantity(event.target.value)}
            />
            {mode === "stocktake" && selectedRow ? (
              <FieldDescription>账面库存 {quantityText(selectedRow.quantity ?? selectedRow.inventory ?? selectedRow.stock)}，差异 {quantityText(Number(quantity || 0) - rowQuantity(selectedRow))}</FieldDescription>
            ) : null}
          </Field>
          <Field>
            <FieldLabel>备注</FieldLabel>
            <Textarea value={note} placeholder="可填写原因，方便后续查账" onChange={(event) => setNote(event.target.value)} />
          </Field>
        </FieldGroup>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose}>取消</Button>
          <Button type="button" disabled={submitting} onClick={() => void submitAction()}>
            {submitting ? "提交中" : "确认保存"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
    <InventoryRiskConfirmDialog
      risk={riskConfirm}
      submitting={submitting}
      onCancel={() => setRiskConfirm(null)}
      onConfirm={() => {
        if (riskConfirm) void executeAction(riskConfirm.payload);
      }}
    />
    </>
  );
}

function InventoryRiskConfirmDialog({
  risk,
  submitting,
  onCancel,
  onConfirm
}: {
  risk: InventoryRiskConfirm;
  submitting: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  return (
    <AlertDialog open={Boolean(risk)} onOpenChange={(open) => {
      if (!open) onCancel();
    }}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{risk?.title || "确认库存变更"}</AlertDialogTitle>
          <AlertDialogDescription>
            {risk?.description || "请确认库存变更信息无误。"}
          </AlertDialogDescription>
        </AlertDialogHeader>
        {risk ? (
          <div className="inventory-risk-grid">
            <span>当前库存</span>
            <strong>{quantityText(risk.currentQty)}</strong>
            <span>变更数量</span>
            <strong>{quantityText(risk.changeQty)}</strong>
            <span>变更后库存</span>
            <strong>{quantityText(risk.afterQty)}</strong>
            <span>影响仓库</span>
            <strong>{risk.warehouseName}</strong>
          </div>
        ) : null}
        <AlertDialogFooter>
          <AlertDialogCancel disabled={submitting}>取消</AlertDialogCancel>
          <AlertDialogAction disabled={submitting} onClick={(event) => {
            event.preventDefault();
            onConfirm();
          }}>
            {submitting ? "提交中" : "确认继续"}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

function InventoryPager({
  page,
  pageCount,
  loading,
  onPrevious,
  onNext
}: {
  page: number;
  pageCount: number;
  loading: boolean;
  onPrevious: () => void;
  onNext: () => void;
}) {
  return (
    <Pagination>
      <PaginationContent>
        <PaginationItem>
          <PaginationPrevious aria-disabled={page <= 1 || loading} onClick={() => {
            if (page > 1 && !loading) onPrevious();
          }} />
        </PaginationItem>
        <PaginationItem>
          <Badge variant="outline">{page} / {pageCount}</Badge>
        </PaginationItem>
        <PaginationItem>
          <PaginationNext aria-disabled={page >= pageCount || loading} onClick={() => {
            if (page < pageCount && !loading) onNext();
          }} />
        </PaginationItem>
      </PaginationContent>
    </Pagination>
  );
}

export function InventoryPage({ currentUser }: { currentUser?: AuthUser } = {}) {
  const [keyword, setKeyword] = useState("");
  const [warehouseId, setWarehouseId] = useState("all");
  const [status, setStatus] = useState<InventoryStatusFilter>("all");
  const [activeTab, setActiveTab] = useState<InventoryTab>("overview");
  const [balances, setBalances] = useState<InventoryBalance[]>([]);
  const [ledger, setLedger] = useState<InventoryLedgerItem[]>([]);
  const [documents, setDocuments] = useState<StockDocumentItem[]>([]);
  const [stocktakes, setStocktakes] = useState<StocktakeItem[]>([]);
  const [transfers, setTransfers] = useState<TransferItem[]>([]);
  const [warehouses, setWarehouses] = useState<Warehouse[]>([]);
  const [remoteSummary, setRemoteSummary] = useState<InventorySummary | null>(null);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [pageSize, setPageSize] = useState(calculateInventoryPageSize);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [ledgerRow, setLedgerRow] = useState<InventoryBalance | null>(null);
  const [actionTarget, setActionTarget] = useState<InventoryActionTarget | null>(null);
  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  const currentWarehouse = warehouses.find((warehouse) => String(warehouse.id) === warehouseId);
  const summary = useMemo(() => buildPageSummary(balances, remoteSummary), [balances, remoteSummary]);
  const canAdjustInventory = hasPermission(currentUser, "调库存");
  const canTransferInventory = hasPermission(currentUser, "调拨");
  const canStocktakeInventory = hasPermission(currentUser, "盘点");

  async function loadTab(
    nextTab = activeTab,
    nextPage = page,
    nextKeyword = keyword,
    nextWarehouseId = warehouseId,
    nextPageSize = pageSize,
    nextStatus = status
  ) {
    setLoading(true);
    setError("");
    try {
      if (isBalanceTab(nextTab)) {
        const data = await api.inventoryBalances({
          keyword: nextKeyword,
          warehouseId: nextWarehouseId,
          stockStatus: nextStatus,
          groupByProduct: nextTab === "overview",
          page: nextPage,
          pageSize: nextPageSize
        });
        const stockRows = filterStockTrackedBalances(data.list || []);
        setBalances(stockRows);
        setRemoteSummary(data.summary || null);
        setTotal(data.total || 0);
        setPage(data.page || nextPage);
      } else if (nextTab === "ledger") {
        const data = await api.inventoryLedger({ keyword: nextKeyword, page: nextPage, pageSize: nextPageSize });
        setLedger(data.list || []);
        setTotal(data.total || 0);
        setPage(data.page || nextPage);
      } else if (nextTab === "documents") {
        const data = await api.stockDocuments({ keyword: nextKeyword, page: nextPage, pageSize: nextPageSize });
        setDocuments(data.list || []);
        setTotal(data.total || 0);
        setPage(data.page || nextPage);
      } else if (nextTab === "stocktakes") {
        const data = await api.stocktakes({ keyword: nextKeyword, page: nextPage, pageSize: nextPageSize });
        setStocktakes(data.list || []);
        setTotal(data.total || 0);
        setPage(data.page || nextPage);
      } else {
        const data = await api.transfers({ keyword: nextKeyword, page: nextPage, pageSize: nextPageSize });
        setTransfers(data.list || []);
        setTotal(data.total || 0);
        setPage(data.page || nextPage);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "库存加载失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    api.warehouses()
      .then((data) => setWarehouses(data.list || []))
      .catch(() => undefined);
    void loadTab("overview", 1, "", "all", pageSize, "all");
  }, []);

  useEffect(() => {
    let resizeTimer = 0;
    const syncPageSize = () => {
      window.clearTimeout(resizeTimer);
      resizeTimer = window.setTimeout(() => {
        const nextPageSize = calculateInventoryPageSize();
        setPageSize((current) => current === nextPageSize ? current : nextPageSize);
      }, INVENTORY_PAGE_SIZE_RESIZE_DELAY);
    };
    syncPageSize();
    window.addEventListener("resize", syncPageSize);
    return () => {
      window.clearTimeout(resizeTimer);
      window.removeEventListener("resize", syncPageSize);
    };
  }, []);

  useEffect(() => {
    void loadTab(activeTab, 1, keyword, warehouseId, pageSize, status);
  }, [pageSize]);

  function refreshCurrent() {
    void loadTab(activeTab, page, keyword, warehouseId, pageSize, status);
  }

  function searchInventory() {
    void loadTab(activeTab, 1, keyword, warehouseId, pageSize, status);
  }

  function resetFilters() {
    setKeyword("");
    setWarehouseId("all");
    setStatus("all");
    void loadTab(activeTab, 1, "", "all", pageSize, "all");
  }

  function changeWarehouse(nextWarehouseId: string) {
    setWarehouseId(nextWarehouseId);
    void loadTab(activeTab, 1, keyword, nextWarehouseId, pageSize, status);
  }

  function changeStatus(nextStatus: InventoryStatusFilter) {
    setStatus(nextStatus);
    void loadTab(activeTab, 1, keyword, warehouseId, pageSize, nextStatus);
  }

  function switchTab(nextTab: string) {
    const tab = nextTab as InventoryTab;
    setActiveTab(tab);
    void loadTab(tab, 1, keyword, warehouseId, pageSize, status);
  }

  function afterActionSaved(mode: InventoryActionMode, result: InventoryActionResult) {
    const docNo = result.doc_no || result.transfer_no || result.stocktake_no || result.id || "";
    const actionText = mode === "purchase" ? "进货已保存" : mode === "transfer" ? "调拨已保存" : "盘点已保存";
    setNotice(docNo ? `${actionText}：${docNo}` : actionText);
    void loadTab("overview", 1, keyword, warehouseId, pageSize, status);
    setActiveTab("overview");
  }

  return (
    <Card className="inventory-page data-panel">
      <CardHeader className="inventory-page-header">
        <InventoryToolbar
          keyword={keyword}
          warehouseId={warehouseId}
          warehouses={warehouses}
          loading={loading}
          page={page}
          pageCount={pageCount}
          pageSize={pageSize}
          total={total}
          activeTab={activeTab}
          onKeywordChange={setKeyword}
          onWarehouseChange={changeWarehouse}
          onSearch={searchInventory}
          onReset={resetFilters}
          onRefresh={refreshCurrent}
          onAction={(mode) => setActionTarget({ mode })}
          canAdjustInventory={canAdjustInventory}
          canTransferInventory={canTransferInventory}
          canStocktakeInventory={canStocktakeInventory}
        />
      </CardHeader>
      <CardContent className="inventory-page-content">
        <InventoryStatusFilter status={status} onStatusChange={changeStatus} />
        <InventorySummaryStrip
          summary={summary}
          warehouseName={warehouseId === "all" ? "全部仓库" : warehouseLabel(currentWarehouse)}
          loading={loading && isBalanceTab(activeTab)}
        />
        <div className="inventory-rule-notice">
          <Badge variant="secondary">不扣库存</Badge>
          <span>不扣库存商品已从当前库存列表和库存操作搜索里排除。</span>
        </div>
        {error ? <div className="form-error">{error}</div> : null}
        {notice ? <div className="form-success">{notice}</div> : null}
        <Tabs value={activeTab} onValueChange={switchTab} className="inventory-tabs">
          <TabsList className="inventory-tab-list">
            {inventoryTabs.map((tab) => (
              <TabsTrigger key={tab.value} value={tab.value}>{tab.label}</TabsTrigger>
            ))}
          </TabsList>
          <TabsContent value="overview">
            <InventoryOverviewMatrix
              rows={balances}
              warehouses={warehouses}
              warehouseId={warehouseId}
              loading={loading}
              status={status}
              onAction={(mode, row) => setActionTarget({ mode, row })}
              onOpenLedger={setLedgerRow}
              onReset={resetFilters}
              canAdjustInventory={canAdjustInventory}
              canTransferInventory={canTransferInventory}
              canStocktakeInventory={canStocktakeInventory}
            />
          </TabsContent>
          <TabsContent value="balances">
            <InventoryBalanceTable
              rows={balances}
              loading={loading}
              status={status}
              onAction={(mode, row) => setActionTarget({ mode, row })}
              onOpenLedger={setLedgerRow}
              onReset={resetFilters}
              canAdjustInventory={canAdjustInventory}
              canTransferInventory={canTransferInventory}
              canStocktakeInventory={canStocktakeInventory}
            />
          </TabsContent>
          <TabsContent value="ledger">
            <InventoryLedgerTable rows={ledger} loading={loading} />
          </TabsContent>
          <TabsContent value="documents">
            <StockDocumentTable rows={documents} loading={loading} />
          </TabsContent>
          <TabsContent value="stocktakes">
            <StocktakeTable rows={stocktakes} loading={loading} />
          </TabsContent>
          <TabsContent value="transfers">
            <TransferTable rows={transfers} loading={loading} />
          </TabsContent>
        </Tabs>
        <InventoryPager
          page={page}
          pageCount={pageCount}
          loading={loading}
          onPrevious={() => void loadTab(activeTab, page - 1, keyword, warehouseId, pageSize, status)}
          onNext={() => void loadTab(activeTab, page + 1, keyword, warehouseId, pageSize, status)}
        />
      </CardContent>
      <InventoryLedgerDrawer row={ledgerRow} onClose={() => setLedgerRow(null)} />
      <InventoryActionDialog
        action={actionTarget}
        warehouses={warehouses}
        onClose={() => setActionTarget(null)}
        onSaved={afterActionSaved}
      />
    </Card>
  );
}
