import { useEffect, useMemo, useState } from "react";
import * as Tabs from "@radix-ui/react-tabs";
import {
  Boxes,
  ClipboardList,
  Home,
  Package,
  ReceiptText,
  Settings,
  ShoppingCart,
  Users
} from "lucide-react";
import { ApiError, api } from "./api";
import {
  CustomersPage,
} from "./components/business/customers";
import { InventoryPage } from "./components/business/inventory";
import { OrdersPage } from "./components/business/orders";
import { ProductsPage } from "./components/business/products";
import { SettingsPage } from "./components/business/settings";
import { WorkbenchPage } from "./components/business/workbench";
import {
  CreateCustomerDialog,
  SalesCustomerField,
  SalesLineTable,
  SalesOrderDetailSheet,
  SalesPaymentFields,
  SalesProductSearch,
  SalesResultCard,
  SalesSummaryCard,
  type SalesFormLine
} from "./components/business/sales-create";
import {
  SalesDeleteDialog,
  SalesListEmpty,
  SalesListTable,
  SalesListToolbar,
  SalesMobileCardList,
  SalesOrderDetailDialog,
  type SalesListFilters
} from "./components/business/sales-list";
import { AppShell } from "./components/layout/app-shell";
import type { AppNavGroup } from "./components/layout/app-sidebar";
import { PageHeader } from "./components/layout/page-header";
import { Toolbar } from "./components/layout/toolbar";
import { hasPermission } from "./lib/permissions";
import { Badge } from "./components/ui/badge";
import { Button } from "./components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle
} from "./components/ui/card";
import {
  Combobox,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxInput,
  ComboboxItem,
  ComboboxList
} from "./components/ui/combobox";
import { DateTimePicker } from "./components/ui/date-time-picker";
import { Field, FieldContent, FieldGroup, FieldLabel } from "./components/ui/field";
import { Input } from "./components/ui/input";
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationNext,
  PaginationPrevious
} from "./components/ui/pagination";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "./components/ui/select";
import type {
  AuthUser,
  CustomerItem,
  SalesCard,
  SalesDetail,
  SalesOrderPayload,
  SalesProduct,
  Warehouse
} from "./types";

type RouteKey = "dashboard" | "sales-new" | "sales" | "customers" | "products" | "media" | "miniapp-images" | "inventory" | "orders" | "settings";

const navItems: Array<{ key: RouteKey; label: string; icon: typeof Home; badge?: string }> = [
  { key: "dashboard", label: "工作台", icon: Home },
  { key: "sales-new", label: "开单", icon: ShoppingCart },
  { key: "sales", label: "销售单", icon: ReceiptText },
  { key: "customers", label: "客户", icon: Users },
  { key: "products", label: "商品", icon: Package },
  { key: "inventory", label: "库存", icon: Boxes },
  { key: "orders", label: "订单", icon: ClipboardList },
  { key: "settings", label: "设置", icon: Settings }
];

const navGroups: Array<AppNavGroup<RouteKey>> = [
  { label: "主业务", items: navItems.filter((item) => ["dashboard", "sales-new", "sales", "customers"].includes(item.key)) },
  { label: "资产", items: navItems.filter((item) => ["products", "inventory", "orders"].includes(item.key)) },
  { label: "系统", items: navItems.filter((item) => ["settings"].includes(item.key)) }
];

const pageMap: Record<RouteKey, { title: string; desc: string; status: string }> = {
  dashboard: { title: "工作台", desc: "AI 对话、结构化确认和最近业务记录。", status: "已接入" },
  "sales-new": { title: "开单", desc: "选择客户、商品、结款状态并创建销售单。", status: "已接入基础版" },
  sales: { title: "销售单", desc: "查看销售单卡片和账单详情。", status: "已接入基础版" },
  customers: { title: "客户", desc: "查看客户卡片、最近消费和余额。", status: "已接入基础版" },
  products: { title: "商品", desc: "维护商品 SPU、SKU、颜色、件规、价格、上下架和图片绑定。", status: "已接入" },
  media: { title: "图片资产", desc: "在设置页集中维护图片上传、裁切、绑定、删除和小程序图片。", status: "已整合到设置" },
  "miniapp-images": { title: "小程序图片", desc: "维护首页、分类和底部导航使用的图片地址。", status: "已接入" },
  inventory: { title: "库存", desc: "查看库存总览、明细、流水、出入库、盘点和调拨。", status: "已接入" },
  orders: { title: "订单", desc: "跟进客户订单、制作、发货和完成状态。", status: "已接入基础版" },
  settings: { title: "设置", desc: "编号、商品基础、库存规则、收款结款、图片、用户和打印。", status: "已接入" }
};

function routeFromLocation(): RouteKey {
  const segment = window.location.pathname.replace(/^\/admin\/?/, "").split("/")[0];
  const route = segment || "dashboard";
  if (route === "sales-new") return "sales-new";
  if (route === "workflow") return "orders";
  if (route === "media") return "media";
  if (route === "miniapp-images") return "miniapp-images";
  return navItems.some((item) => item.key === route) ? (route as RouteKey) : "dashboard";
}

function LoginView({ onLogin }: { onLogin: (user: AuthUser) => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const data = await api.login(username, password);
      onLogin(data.user);
      window.history.replaceState({}, "", "/admin");
    } catch (err) {
      setError(err instanceof Error ? err.message : "登录失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="login-shell">
      <section className="login-panel">
        <div className="brand-mark">北</div>
        <h1>北极星后台</h1>
        <p>使用北极星账号登录新的 React 后台。</p>
        <form onSubmit={submit} className="login-form">
          <label>
            账号
            <input value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" />
          </label>
          <label>
            密码
            <input
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              type="password"
              autoComplete="current-password"
            />
          </label>
          {error ? <div className="form-error">{error}</div> : null}
          <button type="submit" className="primary-action" disabled={loading}>
            {loading ? "登录中" : "登录"}
          </button>
        </form>
      </section>
    </main>
  );
}

function money(value?: string | number) {
  const raw = value === undefined || value === null || value === "" ? "0" : String(value);
  const num = Number(raw);
  return Number.isFinite(num) ? `¥${num.toFixed(2)}` : `¥${raw}`;
}

function displayDate(value?: string) {
  if (!value) return "未记录";
  return value.length > 16 ? value.slice(0, 16) : value;
}

const payTypeOptions = [
  { value: "wechat", label: "微信" },
  { value: "cash", label: "现金" },
  { value: "balance", label: "余额" },
  { value: "transfer", label: "转账" }
];

function defaultDateTimeValue() {
  const now = new Date();
  now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
  return now.toISOString().slice(0, 16);
}

function customerDisplayName(customer?: CustomerItem | null) {
  return customer?.customer_name || customer?.company_name || customer?.name || (customer?.id ? `客户${customer.id}` : "");
}

function productVariants(product: SalesProduct) {
  const variants = product.product_group_data || [];
  return variants.length ? variants : [product];
}

function productDisplayTitle(product?: SalesProduct | null) {
  return product?.title || product?.name || "商品";
}

function productSearchText(product?: SalesProduct | null) {
  if (!product) return "";
  return [
    productDisplayTitle(product),
    product.product_category_text,
    product.color_text,
    product.sku_no,
    product.coding
  ].filter(Boolean).join(" ");
}

function productDisplaySpec(product?: SalesProduct | null) {
  return product?.spec || product?.color || "默认颜色";
}

function toNumber(value: unknown, fallback = 0) {
  const num = Number(value ?? fallback);
  return Number.isFinite(num) ? num : fallback;
}

function inputNoWheel(event: React.WheelEvent<HTMLInputElement>) {
  event.currentTarget.blur();
}

function salesResultId(result: { id?: number; sales_id?: number } | null) {
  return Number(result?.id || result?.sales_id || 0);
}

function SalesNewPage() {
  const [customerKeyword, setCustomerKeyword] = useState("");
  const [customerResults, setCustomerResults] = useState<CustomerItem[]>([]);
  const [customerSearched, setCustomerSearched] = useState(false);
  const [selectedCustomer, setSelectedCustomer] = useState<CustomerItem | null>(null);
  const [createCustomerOpen, setCreateCustomerOpen] = useState(false);
  const [newCustomerName, setNewCustomerName] = useState("");
  const [newCustomerContact, setNewCustomerContact] = useState("");
  const [newCustomerPhone, setNewCustomerPhone] = useState("");
  const [productKeyword, setProductKeyword] = useState("");
  const [productResults, setProductResults] = useState<SalesProduct[]>([]);
  const [warehouses, setWarehouses] = useState<Warehouse[]>([]);
  const [defaultWarehouseId, setDefaultWarehouseId] = useState(2);
  const [lines, setLines] = useState<SalesFormLine[]>([]);
  const [lineQty, setLineQty] = useState(1);
  const [createTime, setCreateTime] = useState(defaultDateTimeValue);
  const [payStatus, setPayStatus] = useState<SalesOrderPayload["pay_status"]>("paid");
  const [payType, setPayType] = useState("wechat");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState("");
  const [lastResult, setLastResult] = useState<{ id?: number; sales_id?: number; sales_no?: string; order_no?: string } | null>(null);
  const [detailOrder, setDetailOrder] = useState<SalesDetail | null>(null);

  const totalQty = lines.reduce((sum, line) => sum + toNumber(line.buy_number), 0);
  const totalAmount = lines.reduce((sum, line) => sum + toNumber(line.buy_number) * toNumber(line.price), 0);
  const selectedCustomerName = customerDisplayName(selectedCustomer);
  const canSubmit = Boolean(selectedCustomer?.id && lines.length && createTime);
  const disabledReason = !selectedCustomer?.id
    ? "请先选择客户"
    : !lines.length
      ? "请先加入商品明细"
      : !createTime
        ? "请选择开单时间"
        : "";

  useEffect(() => {
    api.warehouses()
      .then((data) => {
        const list = data.list || [];
        setWarehouses(list);
        const defaultWarehouse = list.find((item) => Number(item.is_default_sales || 0) === 1) || list[0];
        if (defaultWarehouse?.id) setDefaultWarehouseId(Number(defaultWarehouse.id));
      })
      .catch(() => undefined);
  }, []);

  function selectCustomer(customer: CustomerItem) {
    setSelectedCustomer(customer);
    setCustomerKeyword(customerDisplayName(customer));
    setCustomerResults([]);
    setCustomerSearched(false);
    if (Number(customer.is_monthly_customer || 0)) {
      setPayStatus("monthly");
      setPayType("monthly");
    } else {
      setPayStatus("paid");
      setPayType("wechat");
    }
  }

  async function searchCustomers() {
    const keyword = customerKeyword.trim();
    if (!keyword) {
      setCustomerResults([]);
      setCustomerSearched(false);
      return;
    }
    setLoading("customer");
    setError("");
    try {
      const list = await api.quickCustomers(keyword);
      const nextList = (list || []).slice(0, 12);
      setCustomerResults(nextList);
      setCustomerSearched(true);
      if (nextList.length === 1) selectCustomer(nextList[0]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "客户搜索失败");
    } finally {
      setLoading("");
    }
  }

  async function createCustomer() {
    const name = (newCustomerName || customerKeyword).trim();
    if (!name) {
      setError("请输入客户名称");
      return;
    }
    setLoading("create-customer");
    setError("");
    try {
      const customer = await api.createCustomer({
        name,
        contacts_name: newCustomerContact.trim(),
        contacts_tel: newCustomerPhone.trim()
      });
      selectCustomer(customer);
      setCreateCustomerOpen(false);
      setNewCustomerName("");
      setNewCustomerContact("");
      setNewCustomerPhone("");
      setNotice(customer ? "客户已选中" : "客户已创建");
    } catch (err) {
      setError(err instanceof Error ? err.message : "客户创建失败");
    } finally {
      setLoading("");
    }
  }

  async function searchProducts() {
    const keyword = productKeyword.trim();
    if (!keyword) {
      setProductResults([]);
      return;
    }
    setLoading("product");
    setError("");
    try {
      const data = await api.searchProductsForSales(keyword, 24);
      setProductResults(data.list || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "商品搜索失败");
    } finally {
      setLoading("");
    }
  }

  async function addSalesLine(product: SalesProduct, variant: SalesProduct = product) {
    const productId = Number(variant.id || variant.product_id || product.id || product.product_id || 0);
    if (!productId) {
      setError("没有取到商品编号，不能加入明细");
      return;
    }
    setLoading(`line-${productId}`);
    setError("");
    try {
      let price = toNumber(variant.price || variant.min_price || product.price || product.min_price);
      if (selectedCustomer?.id) {
        try {
          const history = await api.customerPrice(Number(selectedCustomer.id), productId);
          if (history.price !== null && history.price !== undefined && history.price !== "") {
            price = toNumber(history.price, price);
          }
        } catch {
          const retail = await api.retailPrice(productId).catch(() => null);
          if (retail?.price !== null && retail?.price !== undefined && retail?.price !== "") {
            price = toNumber(retail.price, price);
          }
        }
      }
      const warehouseId = defaultWarehouseId || Number(warehouses[0]?.id || 2);
      const nextLine: SalesFormLine = {
        product_id: productId,
        unit_id: Number(variant.unit_id || product.unit_id || 1),
        title: productDisplayTitle(product),
        spec: productDisplaySpec(variant),
        coding: variant.coding || product.coding || "",
        buy_number: Math.max(1, Number(lineQty || 1)),
        price,
        warehouse_id: warehouseId,
        inventory: variant.inventory ?? product.inventory ?? "",
        is_stock_item: Number(variant.is_stock_item ?? product.is_stock_item ?? 1)
      };
      setLines((prev) => {
        const index = prev.findIndex((line) => line.product_id === nextLine.product_id && line.warehouse_id === nextLine.warehouse_id);
        if (index < 0) return [...prev, nextLine];
        return prev.map((line, lineIndex) => (
          lineIndex === index
            ? { ...line, buy_number: toNumber(line.buy_number) + nextLine.buy_number, price: nextLine.price }
            : line
        ));
      });
      setLineQty(1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加入商品失败");
    } finally {
      setLoading("");
    }
  }

  function updateLine(index: number, field: "buy_number" | "price" | "warehouse_id", value: string) {
    setLines((prev) => prev.map((line, lineIndex) => {
      if (lineIndex !== index) return line;
      const clean = field === "price" ? Math.max(0, toNumber(value)) : Math.max(1, toNumber(value, 1));
      return { ...line, [field]: clean };
    }));
  }

  async function submitSalesOrder() {
    if (!selectedCustomer?.id) {
      setError("请先选择客户");
      return;
    }
    if (!lines.length) {
      setError("请先加入商品明细");
      return;
    }
    if (!createTime) {
      setError("请选择开单时间");
      return;
    }
    setLoading("submit");
    setError("");
    setNotice("");
    try {
      const cleanPayType = payStatus === "paid" ? payType : payStatus;
      const result = await api.createSalesOrder({
        customer_id: Number(selectedCustomer.id),
        customer_name: selectedCustomerName,
        warehouse_id: defaultWarehouseId || Number(lines[0]?.warehouse_id || 2),
        create_time: `${createTime.replace("T", " ")}:00`,
        pay_status: payStatus,
        pay_type: cleanPayType,
        products: lines.map((line) => ({
          product_id: line.product_id,
          unit_id: line.unit_id || 1,
          warehouse_id: Number(line.warehouse_id || defaultWarehouseId || 2),
          buy_number: Number(line.buy_number || 1),
          price: Number(line.price || 0)
        }))
      });
      setLastResult(result);
      setNotice(`开单成功${result.sales_no ? `：${result.sales_no}` : ""}`);
      setLines([]);
      setProductResults([]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "开单失败");
    } finally {
      setLoading("");
    }
  }

  async function printSalesById(id: number) {
    if (!id) return;
    setLoading("print-last");
    setError("");
    try {
      await api.createSalesPrintTask(id);
      setNotice("打印任务已创建，等待本地打印程序处理");
    } catch (err) {
      setError(err instanceof Error ? err.message : "打印任务创建失败");
    } finally {
      setLoading("");
    }
  }

  async function printLastSales() {
    await printSalesById(salesResultId(lastResult));
  }

  function previewLastSales() {
    const id = salesResultId(lastResult);
    if (!id) return;
    window.open(`/api/sales/${id}/print-html?auto=0`, "_blank", "noopener");
  }

  async function openLastSalesDetail() {
    const id = salesResultId(lastResult);
    if (!id) return;
    setLoading("detail-last");
    setError("");
    try {
      const detail = await api.salesDetail(id);
      setDetailOrder(detail);
    } catch (err) {
      setError(err instanceof Error ? err.message : "销售单详情加载失败");
    } finally {
      setLoading("");
    }
  }

  async function deleteDetailSales(order: SalesDetail) {
    const id = Number(order.id || order.sales_id || 0);
    if (!id) return;
    setLoading(`delete-${id}`);
    setError("");
    try {
      await api.deleteSales(id);
      setDetailOrder(null);
      setLastResult(null);
      setNotice("销售单已删除，库存和余额已按规则处理");
    } catch (err) {
      setError(err instanceof Error ? err.message : "删除销售单失败");
    } finally {
      setLoading("");
    }
  }

  function continueSameCustomer() {
    setProductKeyword("");
    setProductResults([]);
    setLines([]);
    setLineQty(1);
    setCreateTime(defaultDateTimeValue());
    setLastResult(null);
    setNotice("");
    setError("");
  }

  function startNewCustomerOrder() {
    clearForm();
  }

  function clearForm() {
    setSelectedCustomer(null);
    setCustomerKeyword("");
    setCustomerResults([]);
    setCustomerSearched(false);
    setProductKeyword("");
    setProductResults([]);
    setLines([]);
    setLineQty(1);
    setPayStatus("paid");
    setPayType("wechat");
    setCreateTime(defaultDateTimeValue());
    setLastResult(null);
    setNotice("");
    setError("");
  }

  return (
    <section className="sales-create-page">
      <div className="sales-create-main">
        <Card className="sales-create-card">
          <CardHeader>
            <Toolbar
              title={(
                <div className="sales-create-heading">
                  <Badge variant="outline">
                    {selectedCustomer ? (Number(selectedCustomer.is_monthly_customer || 0) ? "月结客户" : "普通客户") : "待选择客户"}
                  </Badge>
                  <CardTitle>开单</CardTitle>
                </div>
              )}
              actions={<Button variant="outline" size="sm" onClick={clearForm}>清空</Button>}
            />
          </CardHeader>
          {notice ? <div className="form-success">{notice}</div> : null}
          {error ? <div className="form-error">{error}</div> : null}

          <CardContent className="sales-create-content">
            <section className="sales-create-section">
              <div className="section-title">
                <h3>基础信息</h3>
                <span>{selectedCustomerName || "未选择客户"}</span>
              </div>
              <FieldGroup className="sales-create-basic-grid">
                <SalesCustomerField
                  customerKeyword={customerKeyword}
                  customerResults={customerResults}
                  selectedCustomer={selectedCustomer}
                  selectedCustomerName={selectedCustomerName}
                  loading={loading}
                  searched={customerSearched}
                  onKeywordChange={(next) => {
                    setCustomerKeyword(next);
                    setCustomerSearched(false);
                    if (selectedCustomer && next !== selectedCustomerName) setSelectedCustomer(null);
                  }}
                  onSearch={() => void searchCustomers()}
                  onSelectCustomer={selectCustomer}
                  onOpenCreateCustomer={() => {
                    setNewCustomerName(customerKeyword);
                    setCreateCustomerOpen(true);
                  }}
                />
                <SalesPaymentFields
                  createTime={createTime}
                  payStatus={payStatus}
                  payType={payType}
                  payTypeOptions={payTypeOptions}
                  warehouses={warehouses}
                  defaultWarehouseId={defaultWarehouseId}
                  onCreateTimeChange={setCreateTime}
                  onPayStatusChange={(next) => {
                    setPayStatus(next);
                    setPayType(next === "paid" ? "wechat" : next);
                  }}
                  onPayTypeChange={setPayType}
                  onDefaultWarehouseChange={setDefaultWarehouseId}
                />
              </FieldGroup>
            </section>

            <section className="sales-create-section">
              <div className="section-title">
                <h3>销售明细</h3>
                <span>{lines.length} 行 · {totalQty} 套 · {money(totalAmount)}</span>
              </div>
              <SalesProductSearch
                productKeyword={productKeyword}
                productResults={productResults}
                lineQty={lineQty}
                loading={loading}
                onKeywordChange={setProductKeyword}
                onQtyChange={setLineQty}
                onSearchProducts={() => void searchProducts()}
                addedProductIds={lines.map((line) => line.product_id)}
                onAddLine={(product, variant) => void addSalesLine(product, variant)}
              />
              <SalesLineTable
                lines={lines}
                warehouses={warehouses}
                onUpdateLine={updateLine}
                onRemoveLine={(index) => setLines((prev) => prev.filter((_, lineIndex) => lineIndex !== index))}
              />
            </section>
          </CardContent>
        </Card>
      </div>

      <aside className="sales-create-side">
        <SalesSummaryCard
          selectedCustomer={selectedCustomer}
          selectedCustomerName={selectedCustomerName}
          payStatus={payStatus}
          payType={payType}
          payTypeOptions={payTypeOptions}
          totalQty={totalQty}
          totalAmount={totalAmount}
          lineCount={lines.length}
          loading={loading}
          canSubmit={canSubmit}
          disabledReason={disabledReason}
          onSubmit={() => void submitSalesOrder()}
        />
        <SalesResultCard
          result={lastResult}
          loading={loading}
          onPrint={() => void printLastSales()}
          onOpenDetail={() => void openLastSalesDetail()}
          onPreview={previewLastSales}
          onContinueSameCustomer={continueSameCustomer}
          onStartNewCustomerOrder={startNewCustomerOrder}
        />
      </aside>

      <CreateCustomerDialog
        open={createCustomerOpen}
        name={newCustomerName}
        contact={newCustomerContact}
        phone={newCustomerPhone}
        loading={loading === "create-customer"}
        onOpenChange={setCreateCustomerOpen}
        onNameChange={setNewCustomerName}
        onContactChange={setNewCustomerContact}
        onPhoneChange={setNewCustomerPhone}
        onSubmit={() => void createCustomer()}
      />
      <SalesOrderDetailSheet
        order={detailOrder}
        busy={loading.startsWith("delete-")}
        onClose={() => setDetailOrder(null)}
        onPrint={(id) => void printSalesById(id)}
        onDelete={(order) => void deleteDetailSales(order)}
      />
    </section>
  );
}

const defaultSalesFilters: SalesListFilters = {
  keyword: "",
  payStatus: "",
  status: "active",
  dateFilter: ""
};

function localDateString(date: Date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function salesDateRange(dateFilter: SalesListFilters["dateFilter"]) {
  const now = new Date();
  if (dateFilter === "today") {
    const today = localDateString(now);
    return { dateFrom: today, dateTo: today };
  }
  if (dateFilter === "month") {
    return {
      dateFrom: localDateString(new Date(now.getFullYear(), now.getMonth(), 1)),
      dateTo: localDateString(new Date(now.getFullYear(), now.getMonth() + 1, 0))
    };
  }
  return {};
}

function SalesPage() {
  const [filters, setFilters] = useState<SalesListFilters>(defaultSalesFilters);
  const [page, setPage] = useState(1);
  const [items, setItems] = useState<SalesCard[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [detail, setDetail] = useState<SalesDetail | null>(null);
  const [busySalesId, setBusySalesId] = useState<number | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<SalesCard | SalesDetail | null>(null);

  async function load(nextPage = page, nextFilters = filters) {
    setLoading(true);
    setError("");
    try {
      const data = await api.salesCards({
        keyword: nextFilters.keyword.trim(),
        page: nextPage,
        pageSize: 20,
        payStatus: nextFilters.payStatus,
        status: nextFilters.status,
        ...salesDateRange(nextFilters.dateFilter)
      });
      setItems(data.list || []);
      setTotal(data.total || 0);
      setPage(nextPage);
    } catch (err) {
      setError(err instanceof Error ? err.message : "销售单加载失败");
    } finally {
      setLoading(false);
    }
  }

  async function openDetail(id: number) {
    setError("");
    try {
      setDetail(await api.salesDetail(id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "销售单详情加载失败");
    }
  }

  async function handlePrint(id: number) {
    if (!id) return;
    setError("");
    setNotice("");
    setBusySalesId(id);
    try {
      await api.createSalesPrintTask(id);
      setNotice("打印任务已创建，等待本地打印程序处理");
    } catch (err) {
      setError(err instanceof Error ? err.message : "打印任务创建失败");
    } finally {
      setBusySalesId(null);
    }
  }

  function handlePreview(id: number) {
    if (!id) return;
    window.open(`/api/sales/${encodeURIComponent(id)}/print-html?auto=0`, "_blank", "noopener");
  }

  function handleDelete(order: SalesCard | SalesDetail) {
    setError("");
    setNotice("");
    setDeleteTarget(order);
  }

  async function confirmDeleteSales() {
    const id = Number(deleteTarget?.id || deleteTarget?.sales_id || 0);
    if (!id) return;
    setError("");
    setNotice("");
    setBusySalesId(id);
    try {
      await api.deleteSales(id);
      setNotice("销售单已删除，库存和余额已按服务层规则回滚");
      setDeleteTarget(null);
      if (detail && Number(detail.id || detail.sales_id || 0) === id) {
        setDetail(null);
      }
      await load(page, filters);
    } catch (err) {
      setError(err instanceof Error ? err.message : "销售单删除失败");
    } finally {
      setBusySalesId(null);
    }
  }

  useEffect(() => {
    void load(1, defaultSalesFilters);
  }, []);

  const pageCount = Math.max(1, Math.ceil(total / 20));

  return (
    <Card className="data-panel sales-list-page">
      <CardHeader className="sales-page-header">
        <Toolbar
          title={(
            <div className="sales-page-title-block">
              <CardTitle>销售单</CardTitle>
              <CardDescription>查单、看明细、补打和删除错误单。</CardDescription>
            </div>
          )}
          actions={(
            <div className="sales-page-header-actions">
              <span className="sales-page-count">第 {page} / {pageCount} 页 · 共 {total} 单</span>
              <Button type="button" size="sm" onClick={() => window.location.assign("/admin/sales-new")}>
                新建开单
              </Button>
            </div>
          )}
        />
      </CardHeader>
      <CardContent className="sales-page-content">
      {notice ? <div className="form-success">{notice}</div> : null}
      {error ? <div className="form-error">{error}</div> : null}
      <SalesListToolbar
        filters={filters}
        onFiltersChange={setFilters}
        onSearch={() => void load(1, filters)}
        onReset={() => {
          setFilters(defaultSalesFilters);
          void load(1, defaultSalesFilters);
        }}
      />
      {loading || !items.length ? (
        <SalesListEmpty loading={loading} />
      ) : (
        <>
          <SalesListTable
            orders={items}
            busySalesId={busySalesId}
            onOpenDetail={(id) => void openDetail(id)}
            onPrint={(id) => void handlePrint(id)}
            onPreview={handlePreview}
            onDelete={handleDelete}
          />
          <SalesMobileCardList
            orders={items}
            busySalesId={busySalesId}
            onOpenDetail={(id) => void openDetail(id)}
            onPrint={(id) => void handlePrint(id)}
            onPreview={handlePreview}
            onDelete={handleDelete}
          />
        </>
      )}
      <Pagination>
        <PaginationContent>
          <PaginationItem>
            <PaginationPrevious disabled={page <= 1 || loading} onClick={() => load(page - 1, filters)}>上一页</PaginationPrevious>
          </PaginationItem>
          <PaginationItem>
            <Badge variant="outline">{page} / {pageCount}</Badge>
          </PaginationItem>
          <PaginationItem>
            <PaginationNext disabled={page >= pageCount || loading} onClick={() => load(page + 1, filters)}>下一页</PaginationNext>
          </PaginationItem>
        </PaginationContent>
      </Pagination>
      </CardContent>
      <SalesOrderDetailDialog
        order={detail}
        onClose={() => setDetail(null)}
        busySalesId={busySalesId}
        onPrint={handlePrint}
        onPreview={handlePreview}
        onDelete={handleDelete}
      />
      <SalesDeleteDialog
        order={deleteTarget}
        busy={Boolean(busySalesId && Number(deleteTarget?.id || deleteTarget?.sales_id || 0) === busySalesId)}
        onClose={() => setDeleteTarget(null)}
        onConfirm={confirmDeleteSales}
      />
    </Card>
  );
}

function PlaceholderPage({ route }: { route: RouteKey }) {
  const page = pageMap[route];
  return (
    <section className="panel placeholder-panel">
      <div>
        <span className="pill">{page.status}</span>
        <h1>{page.title}</h1>
        <p>{page.desc}</p>
      </div>
      <Tabs.Root defaultValue="contract" className="tabs">
        <Tabs.List className="tabs-list">
          <Tabs.Trigger value="contract">接口合同</Tabs.Trigger>
          <Tabs.Trigger value="plan">开发顺序</Tabs.Trigger>
        </Tabs.List>
        <Tabs.Content value="contract" className="tab-content">
          当前页面会按 `docs/react_admin_api_contract.md` 接入，不在前端重写业务规则。
        </Tabs.Content>
        <Tabs.Content value="plan" className="tab-content">
          先完成登录和工作台，再迁设置、客户销售、商品图片、库存。
        </Tabs.Content>
      </Tabs.Root>
    </section>
  );
}

function AdminArea({ user, onLogout }: { user: AuthUser; onLogout: () => void }) {
  const [route, setRoute] = useState<RouteKey>(routeFromLocation);
  const allowedNavGroups = useMemo(() => navGroups
    .map((group) => ({
      ...group,
      items: group.items.filter((item) => item.key !== "settings" || hasPermission(user, "设置"))
    }))
    .filter((group) => group.items.length > 0), [user]);

  useEffect(() => {
    if (route === "media") {
      window.history.replaceState({}, "", "/admin/settings?section=media");
      setRoute("settings");
    }
    if (route === "miniapp-images") {
      window.history.replaceState({}, "", "/admin/settings?section=miniapp");
      setRoute("settings");
    }
  }, [route]);

  useEffect(() => {
    if (route === "settings" && !hasPermission(user, "设置")) {
      setRoute("dashboard");
      window.history.replaceState({}, "", "/admin");
    }
  }, [route, user]);

  const activePage = useMemo(() => pageMap[route], [route]);

  function navigate(next: RouteKey) {
    setRoute(next);
    window.history.pushState({}, "", next === "dashboard" ? "/admin" : `/admin/${next}`);
  }

  async function logout() {
    await api.logout().catch(() => undefined);
    onLogout();
    window.history.replaceState({}, "", "/admin/login");
  }

  return (
    <AppShell activeRoute={route} navGroups={allowedNavGroups} onNavigate={navigate} user={user}>
      <PageHeader title={activePage.title} onLogout={logout} />
      {route === "dashboard" ? (
        <WorkbenchPage />
      ) : route === "settings" || route === "media" || route === "miniapp-images" ? (
        <SettingsPage currentUser={user} />
      ) : route === "customers" ? (
        <CustomersPage currentUser={user} />
      ) : route === "sales-new" ? (
        <SalesNewPage />
      ) : route === "sales" ? (
        <SalesPage />
      ) : route === "products" ? (
        <ProductsPage />
      ) : route === "inventory" ? (
        <InventoryPage currentUser={user} />
      ) : route === "orders" ? (
        <OrdersPage />
      ) : (
        <PlaceholderPage route={route} />
      )}
    </AppShell>
  );
}
export default function App() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [needsLogin, setNeedsLogin] = useState(window.location.pathname.startsWith("/admin/login"));

  useEffect(() => {
    api
      .me()
      .then((data) => {
        setUser(data.user);
        setNeedsLogin(false);
        if (window.location.pathname.startsWith("/admin/login")) {
          window.history.replaceState({}, "", "/admin");
        }
      })
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) {
          setNeedsLogin(true);
          if (!window.location.pathname.startsWith("/admin/login")) {
            window.history.replaceState({}, "", "/admin/login");
          }
        }
      })
      .finally(() => setLoading(false));
  }, []);

  function handleLogin(nextUser: AuthUser) {
    setUser(nextUser);
    setNeedsLogin(false);
  }

  if (loading) {
    return <div className="loading-screen">北极星后台加载中</div>;
  }

  if (needsLogin || !user) {
    return <LoginView onLogin={handleLogin} />;
  }

  return <AdminArea user={user} onLogout={() => setUser(null)} />;
}
