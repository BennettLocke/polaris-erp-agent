import type {
  ApiResult,
  CustomerBalanceActionPayload,
  CustomerBalanceLedgerResult,
  AuthUser,
  CustomerItem,
  CustomerListResult,
  CustomerSalesResult,
  CustomerStatement,
  DashboardSummary,
  ListResult,
  MiniappImageConfig,
  MiniappImageUpdatePayload,
  NumberSequenceSettings,
  PrintSettings,
  ProductCategory,
  ProductItem,
  ProductMediaAsset,
  ProductOptions,
  ProductSavePayload,
  ProductUploadResult,
  RecentSale,
  RecentWorkflow,
  SalesCard,
  SalesDetail,
  SalesOrderPayload,
  SalesOrderResult,
  SalesPrintTask,
  SalesProduct,
  SystemSetting,
  UserListItem,
  Warehouse
} from "./types";

export type SalesListQuery = {
  keyword?: string;
  page?: number;
  pageSize?: number;
  payStatus?: "paid" | "monthly" | "unpaid" | "";
  status?: "active" | "deleted" | "";
  dateFrom?: string;
  dateTo?: string;
};

export type CustomerListQuery = {
  keyword?: string;
  page?: number;
  pageSize?: number;
  filter?: "all" | "monthly" | "normal" | "debt" | "normal_debt" | "credit" | "no_phone";
};

export type CustomerStatementQuery = {
  month?: string;
  dateFrom?: string;
  dateTo?: string;
};

export class ApiError extends Error {
  status: number;
  code: number;

  constructor(message: string, status: number, code = -1) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {})
    },
    ...init
  });
  const payload = (await response.json().catch(() => null)) as ApiResult<T> | null;
  if (!response.ok || !payload || payload.code !== 0) {
    throw new ApiError(payload?.msg || response.statusText || "请求失败", response.status, payload?.code ?? -1);
  }
  return payload.data;
}

async function requestForm<T>(path: string, form: FormData): Promise<T> {
  const response = await fetch(path, {
    method: "POST",
    credentials: "include",
    body: form
  });
  const payload = (await response.json().catch(() => null)) as ApiResult<T> | null;
  if (!response.ok || !payload || payload.code !== 0) {
    throw new ApiError(payload?.msg || response.statusText || "请求失败", response.status, payload?.code ?? -1);
  }
  return payload.data;
}

function customerStatementParams(options: CustomerStatementQuery = {}) {
  const params = new URLSearchParams();
  if (options.month) params.set("month", options.month);
  if (options.dateFrom) params.set("date_from", options.dateFrom);
  if (options.dateTo) params.set("date_to", options.dateTo);
  return params.toString();
}

export const api = {
  me: () => request<{ user: AuthUser }>("/api/web-auth/me"),
  login: (username: string, password: string) =>
    request<{ user: AuthUser }>("/api/web-auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password })
    }),
  logout: () => request<Record<string, never>>("/api/web-auth/logout", { method: "POST" }),
  dashboardSummary: () => request<DashboardSummary>("/api/dashboard/summary"),
  recentOrders: (limit = 6) =>
    request<{ sales: RecentSale[]; workflows: RecentWorkflow[] }>(`/api/orders/recent?limit=${limit}`),
  customers: (query: CustomerListQuery | string = "", limit = 80) => {
    if (typeof query === "string") {
      return request<CustomerListResult>(
        `/api/customers?keyword=${encodeURIComponent(query)}&limit=${limit}`
      );
    }
    const params = new URLSearchParams();
    params.set("keyword", query.keyword || "");
    params.set("page", String(query.page || 1));
    params.set("page_size", String(query.pageSize || 18));
    params.set("filter", query.filter || "all");
    return request<CustomerListResult>(`/api/customers?${params.toString()}`);
  },
  quickCustomers: (keyword = "") =>
    request<CustomerItem[]>(`/api/customer/list?keyword=${encodeURIComponent(keyword)}`),
  createCustomer: (payload: { name: string; contacts_name?: string; contacts_tel?: string }) =>
    request<CustomerItem>("/api/customer/create", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  updateCustomerMonthly: (id: number, isMonthlyCustomer: boolean) =>
    request<{ id: number; is_monthly_customer: number }>(`/api/customers/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ is_monthly_customer: isMonthlyCustomer ? 1 : 0 })
    }),
  updateCustomer: (id: number, payload: { name?: string; contacts_name?: string; phone?: string; address?: string }) =>
    request<Record<string, unknown>>(`/api/customers/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
  customerSales: (id: number, options: { page?: number; pageSize?: number; period?: string; month?: string } = {}) => {
    const params = new URLSearchParams();
    params.set("page", String(options.page || 1));
    params.set("page_size", String(options.pageSize || 20));
    if (options.period) params.set("period", options.period);
    if (options.month) params.set("month", options.month);
    return request<CustomerSalesResult>(`/api/customers/${id}/sales?${params.toString()}`);
  },
  customerBalanceLedger: (id: number, page = 1, pageSize = 20) =>
    request<CustomerBalanceLedgerResult>(
      `/api/customers/${id}/balance-ledger?page=${page}&page_size=${pageSize}`
    ),
  customerStatement: (id: number, options: CustomerStatementQuery = {}) => {
    const query = customerStatementParams(options);
    return request<CustomerStatement>(`/api/customers/${id}/statement${query ? `?${query}` : ""}`);
  },
  customerStatementPdfUrl: (id: number, options: CustomerStatementQuery = {}) => {
    const query = customerStatementParams(options);
    return `/api/customers/${id}/statement.pdf${query ? `?${query}` : ""}`;
  },
  applyCustomerBalance: (id: number, payload: CustomerBalanceActionPayload) =>
    request<Record<string, unknown>>(`/api/customers/${id}/balance`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  salesCards: (query: SalesListQuery | string = "", page = 1, pageSize = 20) => {
    const options: SalesListQuery = typeof query === "string" ? { keyword: query, page, pageSize } : query;
    const params = new URLSearchParams();
    params.set("keyword", options.keyword || "");
    params.set("page", String(options.page || 1));
    params.set("page_size", String(options.pageSize || 20));
    if (options.payStatus) params.set("pay_status", options.payStatus);
    if (options.status) params.set("status", options.status);
    if (options.dateFrom) params.set("date_from", options.dateFrom);
    if (options.dateTo) params.set("date_to", options.dateTo);
    return request<ListResult<SalesCard>>(`/api/sales/cards?${params.toString()}`);
  },
  salesDetail: (id: number) => request<SalesDetail>(`/api/sales/${id}/detail`),
  searchProductsForSales: (keyword: string, pageSize = 20) =>
    request<ListResult<SalesProduct>>(
      `/api/product/list?keyword=${encodeURIComponent(keyword)}&page=1&page_size=${pageSize}&group=1`
    ),
  productList: (options: {
    keyword?: string;
    page?: number;
    pageSize?: number;
    categoryId?: string | number;
    productType?: string;
    listedState?: string;
    stockMode?: string;
    quality?: string;
  } = {}) => {
    const params = new URLSearchParams();
    params.set("keyword", options.keyword || "");
    params.set("page", String(options.page || 1));
    params.set("page_size", String(options.pageSize || 20));
    params.set("group", "1");
    if (options.categoryId) params.set("category_id", String(options.categoryId));
    if (options.productType) params.set("product_type", options.productType);
    if (options.listedState) params.set("listed_state", options.listedState);
    if (options.stockMode) params.set("stock_mode", options.stockMode);
    if (options.quality) params.set("quality", options.quality);
    return request<ListResult<ProductItem>>(`/api/product/list?${params.toString()}`);
  },
  productCategories: () => request<ListResult<ProductCategory>>("/api/product/categories"),
  productDetail: (id: number) => request<ProductItem>(`/api/product/${id}`),
  productOptions: (id?: number) => request<ProductOptions>(`/api/product/options${id ? `?id=${id}` : ""}`),
  saveProduct: (payload: ProductSavePayload) =>
    request<{ id?: number; sku_ids?: number[]; spu_id?: number }>("/api/product/save", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  deleteProduct: (ids: Array<number | string> | number | string) =>
    request<{ ids?: number[]; sku_ids?: number[]; spu_ids?: number[]; affected?: number }>("/api/product/delete", {
      method: "POST",
      body: JSON.stringify({ ids: Array.isArray(ids) ? ids : [ids] })
    }),
  updateProductShelves: (id: number, state: number) =>
    request<{ id?: number; spu_id?: number; sku_ids?: number[]; is_listed: number; affected?: number }>(
      `/api/product/${id}/shelves`,
      {
        method: "POST",
        body: JSON.stringify({ state })
      }
    ),
  uploadProductImage: (file: File) => {
    const form = new FormData();
    form.append("image", file, file.name || `product_${Date.now()}.jpg`);
    return requestForm<ProductUploadResult>("/api/product/upload", form);
  },
  miniappImageConfig: () => request<MiniappImageConfig>("/api/miniapp/image-config"),
  uploadMiniappImage: (file: File) => {
    const form = new FormData();
    form.append("image", file, file.name || `miniapp_${Date.now()}.jpg`);
    return requestForm<ProductUploadResult>("/api/miniapp/image-config/upload", form);
  },
  updateMiniappImage: (payload: MiniappImageUpdatePayload) =>
    request<{ id: number; affected?: number }>("/api/miniapp/image-config", {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
  productMedia: (options: { page?: number; pageSize?: number; mediaType?: string; productId?: number } = {}) => {
    const params = new URLSearchParams();
    params.set("page", String(options.page || 1));
    params.set("page_size", String(options.pageSize || 24));
    if (options.mediaType) params.set("media_type", options.mediaType);
    if (options.productId) params.set("product_id", String(options.productId));
    return request<ListResult<ProductMediaAsset>>(`/api/product/media?${params.toString()}`);
  },
  deleteProductMedia: (id: number) =>
    request<{ id: number; affected: number }>(`/api/product/media/${id}`, {
      method: "DELETE"
    }),
  customerPrice: (customerId: number, productId: number) =>
    request<{ price: number | string | null }>(
      `/api/customer/price?customer_id=${customerId}&product_id=${productId}`
    ),
  retailPrice: (productId: number) =>
    request<{ price: number | string | null }>(`/api/product/retail-price?product_id=${productId}`),
  createSalesOrder: (payload: SalesOrderPayload) =>
    request<SalesOrderResult>("/api/sales/add", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  createSalesPrintTask: (id: number) =>
    request<SalesPrintTask>(`/api/sales/${id}/print-task`, {
      method: "POST",
      body: JSON.stringify({})
    }),
  deleteSales: (id: number) =>
    request<{ id: number }>(`/api/sales/${id}`, {
      method: "DELETE"
    }),
  skuNumberSettings: () => request<NumberSequenceSettings>("/api/settings/number/sku"),
  saveSkuNumberSettings: (payload: Partial<NumberSequenceSettings>) =>
    request<NumberSequenceSettings>("/api/settings/number/sku", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  systemSetting: (key: string) => request<SystemSetting>(`/api/settings/system/${encodeURIComponent(key)}`),
  saveSystemSetting: (key: string, payload: { value: Record<string, unknown> }) =>
    request<SystemSetting>(`/api/settings/system/${encodeURIComponent(key)}`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  salesPrintSettings: () => request<PrintSettings>("/api/settings/print/sales"),
  saveSalesPrintSettings: (payload: Partial<PrintSettings>) =>
    request<PrintSettings>("/api/settings/print/sales", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  users: (keyword = "", page = 1, pageSize = 20) =>
    request<ListResult<UserListItem>>(
      `/api/users?keyword=${encodeURIComponent(keyword)}&page=${page}&page_size=${pageSize}`
    ),
  updateUser: (id: number, payload: Partial<Pick<UserListItem, "role" | "is_active">>) =>
    request<{ affected: number; id: number }>(`/api/users/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
  warehouses: () => request<ListResult<Warehouse>>("/api/warehouses")
};
