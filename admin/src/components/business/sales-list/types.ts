import type { SalesCard, SalesDetail, SalesPaymentUpdatePayload } from "@/types";

export type SalesPayStatusFilter = "" | "paid" | "monthly" | "unpaid";
export type SalesStatusFilter = "active" | "deleted";
export type SalesDateFilter = "" | "today" | "month";

export type SalesListFilters = {
  keyword: string;
  payStatus: SalesPayStatusFilter;
  status: SalesStatusFilter;
  dateFilter: SalesDateFilter;
};

export type SalesListToolbarProps = {
  filters: SalesListFilters;
  onFiltersChange: (filters: SalesListFilters) => void;
  onSearch: () => void;
  onReset: () => void;
};

export type SalesListActions = {
  busySalesId: number | null;
  onOpenDetail: (id: number) => void;
  onPrint: (id: number) => void;
  onPreview: (id: number) => void;
  onDelete: (order: SalesCard | SalesDetail) => void;
};

export type SalesListTableProps = SalesListActions & {
  orders: SalesCard[];
};

export type SalesMobileCardListProps = SalesListActions & {
  orders: SalesCard[];
};

export type SalesOrderDetailDialogProps = Omit<SalesListActions, "onOpenDetail"> & {
  order: SalesDetail | null;
  onClose: () => void;
  onUpdatePayment: (id: number, payload: SalesPaymentUpdatePayload) => Promise<void>;
};

export type SalesDeleteDialogProps = {
  order: SalesCard | SalesDetail | null;
  busy: boolean;
  onClose: () => void;
  onConfirm: () => void;
};
