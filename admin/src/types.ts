export type ApiResult<T> = {
  code: number;
  msg?: string;
  data: T;
};

export type AuthUser = {
  id: number;
  native_user_id?: number;
  username: string;
  display_name: string;
  role: string;
  role_text: string;
  permissions: string[];
  approval_status: string;
  is_admin: number;
  is_active: number;
};

export type DashboardSummary = {
  today_sales_count: number;
  today_sales_amount: string;
  pending_workflow_count: number;
  updated_at: number;
};

export type AnalyticsHotProduct = {
  rank: number;
  product_id: number;
  sku_id: number;
  sku_no?: string;
  title: string;
  color?: string;
  image?: string;
  image_url?: string;
  sold_qty: number;
  amount: string;
  amount_value?: number;
  order_count: number;
  customer_count: number;
  last_sold_at?: string;
};

export type AnalyticsHotProductsResult = {
  period: string;
  dimension: "product" | "sku" | string;
  limit: number;
  category_names?: string[];
  items: AnalyticsHotProduct[];
  source: string;
};

export type AnalyticsSalesOverviewKpi = {
  sales_amount: string;
  sales_amount_value?: number;
  order_count: number;
  item_quantity: number;
  customer_count: number;
  average_order_amount: string;
  average_order_amount_value?: number;
};

export type AnalyticsSalesTrendItem = {
  date: string;
  sales_amount: string;
  sales_amount_value?: number;
  order_count: number;
};

export type AnalyticsRecentSale = {
  id: number;
  sales_no?: string;
  customer_name: string;
  product_summary: string;
  receivable_amount: string;
  receivable_amount_value?: number;
  pay_status?: string;
  pay_status_text?: string;
  pay_type?: string;
  pay_type_text?: string;
  sales_at?: string;
};

export type AnalyticsSalesOverview = {
  period: string;
  kpi: AnalyticsSalesOverviewKpi;
  trend: AnalyticsSalesTrendItem[];
  recent_sales: AnalyticsRecentSale[];
  source: string;
};

export type TaobaoDetailExportJob = {
  job_id: string;
  product_id: number;
  status: "pending" | "running" | "completed" | "failed" | string;
  message?: string;
  filename?: string;
  html_filename?: string;
  taobao_title?: string;
  error?: string;
  download_url?: string;
  created_at?: number;
  updated_at?: number;
  completed_at?: number;
};

export type WorkbenchInventoryColor = {
  product_id?: number;
  color: string;
  total_stock: number;
  warehouses: Record<string, number>;
};

export type WorkbenchInventoryCard = {
  product_id?: number;
  title: string;
  piece_text?: string;
  total_stock: number;
  status_text?: string;
  colors: WorkbenchInventoryColor[];
};

export type InventoryCardsResult = {
  list: WorkbenchInventoryCard[];
  source?: string;
};

export type WorkbenchInventoryLookupWarehouse = {
  id?: number | string | null;
  name: string;
};

export type WorkbenchInventoryLookupRow = {
  product_id?: number | string | null;
  sku_id?: number | string | null;
  spu_id?: number | string | null;
  sku_no?: string;
  title: string;
  color?: string;
  unit_name?: string;
  piece_text?: string;
  is_stock_item?: number;
  warehouses: Record<string, number>;
  warehouse_ids?: Record<string, number | string | null>;
  total_stock: number;
};

export type InventoryLookupResult = {
  list: WorkbenchInventoryLookupRow[];
  warehouses: WorkbenchInventoryLookupWarehouse[];
  total?: number;
  keyword?: string;
  color?: string;
  warehouse_id?: number | string | null;
  source?: string;
};

export type AgentMessageHistoryItem = {
  role: "user" | "assistant" | string;
  content: string;
};

export type AgentSessionSnapshot = {
  has_pending?: boolean;
  pending_intent?: string | null;
  pending_action?: string;
  state?: Record<string, unknown> | null;
  last_extraction?: Record<string, unknown>;
  last_order?: Record<string, unknown>;
};

export type AgentChatResponse = {
  response: string;
  session_id: string;
  session?: AgentSessionSnapshot;
  inventory_lookup?: InventoryLookupResult | null;
};

export type AgentHistoryResult = {
  session_id: string;
  history: AgentMessageHistoryItem[];
  session?: AgentSessionSnapshot;
};

export type AgentImageUploadResult = AgentChatResponse & {
  image_path?: string;
  result?: {
    preview_url?: string;
    image_path?: string;
    mode?: string;
    [key: string]: unknown;
  };
};

export type RecentSale = {
  id?: number;
  sales_no?: string;
  customer_name?: string;
  product_summary?: string;
  total_quantity?: number;
  receivable_amount?: string;
  date_text?: string;
};

export type RecentWorkflow = {
  id?: number;
  customer_name?: string;
  goods_name?: string;
  goods_color?: string;
  order_quantity?: number;
  status_text?: string;
};

export type ProcessOrderRaw = {
  id: number;
  order_id?: number;
  workflow_no?: string;
  customer_name?: string;
  customer_phone?: string;
  goods_name?: string;
  goods_color?: string;
  color?: string;
  order_quantity?: string | number;
  is_screen_print?: number | boolean;
  is_screen_print_text?: string;
  is_made?: number | boolean;
  is_delivered?: number | boolean;
  order_type?: number | string;
  status?: string;
  status_text?: string;
  order_time_text?: string;
  complete_time_text?: string;
  order_images?: string[] | string | null;
  remark?: string;
  created_by_user_id?: number | null;
  created_by_name?: string;
};

export type ProcessOrder = {
  id: number;
  raw: ProcessOrderRaw;
  customerName: string;
  customerPhone: string;
  goodsName: string;
  color: string;
  quantity: number;
  screenPrint: boolean;
  made: boolean;
  delivered: boolean;
  completed: boolean;
  statusText: string;
  orderTimeText: string;
  completeTimeText: string;
  imageUrls: string[];
  creatorName: string;
  remark: string;
};

export type ProcessOrderListResult = ListResult<ProcessOrderRaw> & {
  filter?: string;
};

export type ProcessOrderPayload = {
  order_id?: number;
  customer_name: string;
  customer_phone?: string;
  goods_name: string;
  color?: string;
  order_quantity?: number | string;
  is_screen_print?: number | boolean;
  is_made?: number;
  is_delivered?: number;
  order_type?: number;
  order_images?: string[];
  remark?: string;
};

export type ProcessOrderStatusPayload = {
  field: "is_made" | "is_delivered" | "order_type";
  value: number;
};

export type CustomerItem = {
  id: number;
  customer_id?: number;
  name?: string;
  customer_name?: string;
  company_name?: string;
  contacts_name?: string;
  phone?: string;
  mobile?: string;
  contacts_tel?: string;
  address?: string;
  is_monthly_customer?: number;
  existed?: boolean;
  latest_order_at?: string;
  latest_order_amount?: string;
  year_amount?: string;
  balance_amount?: string;
  sales_count?: number;
};

export type CustomerListSummary = {
  total: number;
  monthly: number;
  debt: number;
  normal_debt?: number;
  monthly_debt?: number;
  no_phone?: number;
  credit?: number;
  credit_amount: string;
  debt_amount: string;
};

export type CustomerListResult = ListResult<CustomerItem> & {
  filter?: string;
  summary?: CustomerListSummary;
};

export type CustomerSalesItem = {
  id: number;
  sales_no?: string;
  status?: string;
  status_text?: string;
  pay_type?: string;
  pay_type_text?: string;
  pay_status?: string;
  pay_status_text?: string;
  total_quantity?: string | number;
  goods_amount?: string;
  receivable_amount?: string;
  sales_at?: string;
  created_by_name?: string;
  items_preview?: string;
  note?: string;
};

export type CustomerSalesSummary = {
  period?: string;
  label?: string;
  total: number;
  total_amount: string;
  unpaid_amount: string;
  balance_amount: string;
};

export type CustomerSalesResult = ListResult<CustomerSalesItem> & {
  summary: CustomerSalesSummary;
};

export type CustomerBalanceLedgerItem = {
  id: number;
  ledger_no: string;
  customer_id: number;
  entry_type: string;
  entry_type_text: string;
  pay_type?: string;
  pay_type_text?: string;
  amount: string;
  applied_amount: string;
  balance_delta: string;
  related_month?: string;
  note?: string;
  created_by_name?: string;
  created_at?: string;
};

export type CustomerBalanceSummary = {
  customer_id: number;
  customer_name: string;
  wallet_amount: string;
  debt_amount: string;
  balance_amount: string;
};

export type CustomerBalanceLedgerResult = ListResult<CustomerBalanceLedgerItem> & {
  summary: CustomerBalanceSummary;
};

export type CustomerStatementSalesLine = {
  line_no?: number;
  sku_no?: string;
  title?: string;
  color?: string;
  quantity?: string;
  unit_price?: string;
  amount?: string;
  warehouse_name?: string;
};

export type CustomerStatementSalesItem = {
  id: number;
  sales_no?: string;
  sales_at?: string;
  pay_status?: string;
  pay_status_text?: string;
  pay_type?: string;
  pay_type_text?: string;
  total_quantity?: string;
  goods_amount?: string;
  receivable_amount?: string;
  created_by_name?: string;
  items?: CustomerStatementSalesLine[];
};

export type CustomerStatement = {
  customer: CustomerItem & {
    contact_name?: string;
    is_monthly_customer?: number;
  };
  period_label: string;
  month?: string;
  date_from: string;
  date_to: string;
  generated_at?: string;
  opening_balance: string;
  sales_amount: string;
  receipt_amount: string;
  settlement_amount: string;
  adjust_amount: string;
  ledger_delta?: string;
  unpaid_amount: string;
  ending_balance: string;
  sales_quantity: string;
  sales_count: number;
  ledger_count: number;
  sales: CustomerStatementSalesItem[];
  ledger: CustomerBalanceLedgerItem[];
};

export type CustomerBalanceActionPayload = {
  action: "receipt" | "recharge" | "settlement" | "adjust";
  amount: string;
  pay_type?: string;
  month?: string;
  note?: string;
};

export type SalesProduct = {
  id?: number;
  product_id?: number;
  spu_id?: number;
  unit_id?: number;
  name?: string;
  title?: string;
  series?: string;
  size_label?: string;
  product_type?: string;
  default_supplier_id?: number | string | null;
  default_supplier_name?: string;
  default_supplier_status?: string;
  manufacturer_id?: number | string | null;
  manufacturer_name?: string;
  color?: string;
  spec?: string;
  coding?: string;
  sku_no?: string;
  color_count?: number;
  color_names?: string[];
  color_text?: string;
  available_colors?: string[];
  quantity?: string | number;
  buy_number?: string | number;
  price?: string | number;
  min_price?: string | number;
  max_price?: string | number;
  total_price?: string;
  warehouse_name?: string;
  warehouse_id?: number;
  image?: string;
  images?: string;
  main_images?: string;
  spu_main_image_url?: string;
  spec_image_url?: string;
  inventory?: string | number;
  is_stock_item?: number;
  is_listed?: number;
  system_goods_is_shelves?: number;
  listed_sku_count?: number;
  unlisted_sku_count?: number;
  status_text?: string;
  product_category_text?: string;
  piece_text?: string;
  case_pack_qty?: string | number;
  purchase_policy?: string;
  is_one_case_purchase?: number;
  product_group_data?: SalesProduct[];
  product_category_ids?: number[];
  simple_desc?: string;
  content?: string;
  content_html?: string;
  detail_image_urls?: string[] | string;
  main_images_list?: string[];
  primary_category_id?: string | number;
  media_assets?: ProductMediaAsset[];
  base?: Array<{
    id?: number;
    unit_id?: number;
    coding?: string;
    barcode?: string;
    price?: string | number;
    cost_price?: string | number;
    images?: string;
    is_stock_item?: number;
  }>;
};

export type ProductItem = SalesProduct;

export type ProductStatusOption = {
  value: string | number;
  name: string;
};

export type ProductOptions = {
  data?: ProductItem;
  product_category?: ProductCategory[];
  unit_list?: ProductUnit[];
  product_status_list?: ProductStatusOption[];
  manufacturer_list?: ProductManufacturer[];
  media_assets?: ProductMediaAsset[];
};

export type ProductSavePayload = {
  id?: string | number;
  title: string;
  product_type?: string;
  product_category_id: Array<string | number>;
  default_supplier_id?: string | number | null;
  status?: string | number;
  purchase_policy: "one_case" | "order_qty";
  simple_desc?: string;
  content?: string;
  main_images: string[];
  base: Record<string, {
    images?: string;
    spec?: string;
    coding?: string;
    is_stock_item?: number;
    unit: Record<string, {
      unit_id: string | number;
      unit_number: number;
      coding?: string;
      barcode?: string;
      weight: number;
      volume: number;
      price: string | number;
      cost_price: string | number;
      extends: string;
    }>;
  }>;
};

export type ProductUploadResult = {
  url?: string;
  full_url?: string;
  images?: string;
  path?: string;
};

export type MiniappAssetImageItem = {
  id: number;
  scene: string;
  name: string;
  title?: string;
  asset_url?: string;
  active_asset_url?: string;
  link_type?: string;
  link_value?: string;
  badge_text?: string;
  subtitle?: string;
  sort_order?: number;
  enabled?: number;
};

export type MiniappImageConfig = {
  assets: MiniappAssetImageItem[];
  categories: ProductCategory[];
};

export type MiniappImageUpdatePayload = {
  target_type: "miniapp_asset" | "category";
  id: number;
  field: "asset_url" | "active_asset_url" | "icon" | "icon_active";
  url: string;
};

export type MiniappImageCreatePayload = {
  scene: "home_banner";
  name?: string;
  asset_url?: string;
  link_type?: string;
  link_value?: string;
};

export type SalesCard = {
  id: number;
  sales_id?: number;
  sales_no?: string;
  customer_id?: number;
  customer_name?: string;
  status?: string;
  status_text?: string;
  pay_status?: string;
  pay_status_text?: string;
  pay_type?: string;
  pay_type_text?: string;
  receivable_amount?: string;
  total_price?: string;
  total_quantity?: string | number;
  buy_number_count?: string | number;
  sales_at?: string;
  date_text?: string;
  created_by_name?: string;
  product_summary?: string;
  products?: SalesProduct[];
};

export type SalesDetail = SalesCard & {
  sales_id?: number;
  goods_amount?: string;
  created_at?: string;
  updated_at?: string;
  deleted_at?: string;
  delete_reason?: string;
  deleted_by_name?: string;
  note?: string;
  detail?: SalesProduct[];
  items?: SalesProduct[];
};

export type SalesPrintTask = {
  id?: number;
  task_id?: number;
  job_no?: string;
  sales_id?: number;
  sales_no?: string;
  customer_name?: string;
  status?: string;
  copies?: number;
  print_url?: string;
  created_at?: string;
  updated_at?: string;
  printed_at?: string;
};

export type SalesOrderLinePayload = {
  product_id: number;
  unit_id: number;
  warehouse_id: number;
  buy_number: number;
  price: number;
};

export type SalesOrderPayload = {
  customer_id: number;
  customer_name?: string;
  warehouse_id: number;
  create_time: string;
  pay_status: "paid" | "monthly" | "unpaid";
  pay_type?: string;
  allow_negative_stock?: boolean | number;
  products: SalesOrderLinePayload[];
};

export type SalesPaymentUpdatePayload = {
  pay_status: "paid" | "monthly" | "unpaid" | "partial";
  pay_type?: string;
  note?: string;
};

export type SalesOrderResult = {
  id?: number;
  sales_id?: number;
  sales_no?: string;
  order_no?: string;
};

export type ProductCategory = {
  id?: number;
  pid?: number;
  parent_id?: number;
  code?: string;
  name: string;
  product_type?: string;
  inventory_policy?: string;
  icon?: string;
  icon_active?: string;
  sort_order?: number;
  is_enabled?: number;
  total?: number;
};

export type ProductCategorySavePayload = {
  id?: number;
  parent_id?: number;
  pid?: number;
  code?: string;
  name: string;
  product_type?: string;
  inventory_policy?: string;
  sort_order?: number;
  is_enabled?: number;
};

export type ProductUnit = {
  id?: number;
  name: string;
  code?: string;
};

export type ProductManufacturer = {
  id: number;
  manufacturer_id?: number;
  name: string;
  kind?: string;
  contact_name?: string;
  phone?: string;
  address?: string;
  note?: string;
  status?: string;
  is_enabled?: number;
  product_count?: number;
};

export type ManufacturerSavePayload = {
  id?: number;
  manufacturer_id?: number;
  name: string;
  contact_name?: string;
  phone?: string;
  address?: string;
  note?: string;
  status?: string;
};

export type Warehouse = {
  id: number;
  warehouse_id?: number;
  code?: string;
  name: string;
  warehouse_name?: string;
  type?: string;
  is_default_sales?: number;
  is_default_inbound?: number;
};

export type InventoryBalance = {
  id?: number;
  sku_id?: number;
  product_id?: number;
  spu_id?: number;
  sku_no?: string;
  title?: string;
  name?: string;
  color?: string;
  spec?: string;
  warehouse_id?: number;
  warehouse_name?: string;
  unit_id?: number;
  unit_name?: string;
  quantity?: string | number;
  inventory?: string | number;
  stock?: string | number;
  available_qty?: string | number;
  reserved_qty?: string | number;
  is_stock_item?: number;
  last_ledger_at?: string;
  last_biz_type?: string;
  simple_desc?: string;
};

export type InventorySummary = {
  total_sku?: number;
  in_stock?: number;
  zero_stock?: number;
  negative_stock?: number;
  warehouse_id?: number;
};

export type InventoryBalanceResult = ListResult<InventoryBalance> & {
  summary?: InventorySummary;
};

export type InventoryLedgerItem = {
  id: number;
  ledger_no?: string;
  sku_id?: number;
  sku_no_snapshot?: string;
  title?: string;
  color?: string;
  warehouse_id?: number;
  warehouse_name?: string;
  unit_id?: number;
  unit_name?: string;
  change_qty?: string | number;
  before_qty?: string | number;
  after_qty?: string | number;
  biz_type?: string;
  biz_id?: number;
  counterparty_warehouse_id?: number;
  operator_name?: string;
  operator_username?: string;
  note?: string;
  occurred_at?: string;
};

export type StockDocumentItem = {
  id: number;
  doc_no?: string;
  doc_type?: string;
  direction?: string;
  warehouse_id?: number;
  warehouse_name?: string;
  status?: string;
  total_quantity?: string | number;
  note?: string;
  created_by_name?: string;
  created_by_username?: string;
  created_at?: string;
  confirmed_at?: string;
};

export type StocktakeItem = {
  id: number;
  stocktake_no?: string;
  warehouse_id?: number;
  warehouse_name?: string;
  status?: string;
  total_diff_qty?: string | number;
  note?: string;
  created_by_name?: string;
  created_by_username?: string;
  created_at?: string;
  confirmed_at?: string;
};

export type TransferItem = {
  id: number;
  transfer_no?: string;
  from_warehouse_id?: number;
  from_warehouse_name?: string;
  to_warehouse_id?: number;
  to_warehouse_name?: string;
  status?: string;
  total_quantity?: string | number;
  note?: string;
  created_by_name?: string;
  created_by_username?: string;
  created_at?: string;
  confirmed_at?: string;
};

export type InventoryActionPayload = {
  product_id: number;
  sku_id?: number;
  unit_id?: number;
  warehouse_id?: number;
  out_warehouse_id?: number;
  enter_warehouse_id?: number;
  quantity: string | number;
  note?: string;
};

export type InventoryActionResult = {
  id?: number;
  doc_no?: string;
  transfer_no?: string;
  stocktake_no?: string;
};

export type MediaSummary = {
  total: number;
  pending: number;
  main: number;
  detail: number;
  color: number;
};

export type ProductMediaAsset = {
  id?: number | null;
  sku_id?: number | null;
  spu_id?: number | null;
  media_type: string;
  media_type_text?: string;
  url: string;
  product_name?: string;
  binding_text?: string;
  category_name?: string;
  asset_group_key?: string;
  asset_group_text?: string;
  sku_no?: string;
  sku_color?: string;
  source_text?: string;
  created_at?: string;
};

export type SystemSetting = {
  key: string;
  value: Record<string, unknown>;
  categories?: ProductCategory[];
  units?: ProductUnit[];
  warehouses?: Warehouse[];
  media_summary?: MediaSummary;
};

export type NumberSequenceLog = {
  id: number;
  old_code: string;
  new_code: string;
  note?: string;
  operator_user_id?: number | null;
  created_at?: string;
};

export type NumberSequenceSettings = {
  sequence_key: string;
  prefix: string;
  start_number: number;
  next_number: number;
  pad_width: number;
  next_code: string;
  start_code: string;
  configured_code: string;
  skipped_numbers: number[];
  skipped_numbers_text: string;
  used_count: number;
  numeric_used_count: number;
  used_min_code: string;
  used_max_code: string;
  total_sku_count: number;
  note?: string;
  updated_at?: string;
  change_logs?: NumberSequenceLog[];
};

export type PrintSettings = {
  id?: number;
  name: string;
  paper_size: string;
  orientation: string;
  font_size: number;
  copies: number;
  show_logo?: number;
  show_operator?: number;
  show_customer_phone?: number;
  show_payment?: number;
  show_note?: number;
  header_text: string;
  footer_text?: string;
  custom_css?: string;
  latest_sales_id?: number;
  latest_sales_no?: string;
  latest_print_url?: string;
};

export type UserListItem = {
  id: number;
  username: string;
  account_display?: string;
  display_name?: string;
  phone?: string | null;
  role: string;
  role_text?: string;
  linked_party_id?: number | null;
  party_name?: string | null;
  approval_status?: string;
  is_active: number;
  is_admin?: number;
};

export type ListResult<T> = {
  list: T[];
  total: number;
  page?: number;
  page_size?: number;
  source?: string;
};
