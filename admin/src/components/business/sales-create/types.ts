import type {
  CustomerItem,
  SalesOrderPayload,
  SalesProduct,
  Warehouse
} from "@/types";

export type SalesFormLine = {
  product_id: number;
  unit_id: number;
  title: string;
  spec: string;
  coding?: string;
  buy_number: number;
  price: number;
  warehouse_id: number;
  inventory?: string | number;
  is_stock_item?: number;
};

export type SalesLoadingKey = "" | "customer" | "create-customer" | "product" | "submit" | "print-last" | "detail-last" | string;

export type SalesPayStatus = SalesOrderPayload["pay_status"];

export type SalesResultLite = {
  id?: number;
  sales_id?: number;
  sales_no?: string;
  order_no?: string;
} | null;

export type PayTypeOption = {
  value: string;
  label: string;
};

export type CustomerPickerProps = {
  customerKeyword: string;
  customerResults: CustomerItem[];
  selectedCustomer: CustomerItem | null;
  selectedCustomerName: string;
  loading: SalesLoadingKey;
  searched: boolean;
  onKeywordChange: (value: string) => void;
  onSearch: () => void;
  onSelectCustomer: (customer: CustomerItem) => void;
  onOpenCreateCustomer: () => void;
};

export type PaymentFieldsProps = {
  createTime: string;
  payStatus: SalesPayStatus;
  payType: string;
  payTypeOptions: PayTypeOption[];
  warehouses: Warehouse[];
  defaultWarehouseId: number;
  onCreateTimeChange: (value: string) => void;
  onPayStatusChange: (value: SalesPayStatus) => void;
  onPayTypeChange: (value: string) => void;
  onDefaultWarehouseChange: (value: number) => void;
};

export type ProductSearchProps = {
  productKeyword: string;
  productResults: SalesProduct[];
  lineQty: number;
  loading: SalesLoadingKey;
  onKeywordChange: (value: string) => void;
  onQtyChange: (value: number) => void;
  onSearchProducts: () => void;
  addedProductIds?: number[];
  onAddLine: (product: SalesProduct, variant?: SalesProduct) => void;
};

export type LineTableProps = {
  lines: SalesFormLine[];
  warehouses: Warehouse[];
  onUpdateLine: (index: number, field: "buy_number" | "price" | "warehouse_id", value: string) => void;
  onRemoveLine: (index: number) => void;
};
