import type { InventoryListQuery, ProcessOrderListQuery, SalesListQuery } from "../api";

export const queryKeys = {
  customers: {
    root: ["customers"] as const,
    list: (query: unknown) => ["customers", "list", query] as const
  },
  inventory: {
    root: ["inventory"] as const,
    warehouses: () => ["inventory", "warehouses"] as const,
    balances: (query: InventoryListQuery) => ["inventory", "balances", query] as const,
    ledger: (query: InventoryListQuery) => ["inventory", "ledger", query] as const,
    documents: (query: InventoryListQuery) => ["inventory", "documents", query] as const,
    stocktakes: (query: InventoryListQuery) => ["inventory", "stocktakes", query] as const,
    transfers: (query: InventoryListQuery) => ["inventory", "transfers", query] as const
  },
  products: {
    root: ["products"] as const,
    list: (query: unknown) => ["products", "list", query] as const,
    categories: () => ["products", "categories"] as const,
    detail: (id: number) => ["products", "detail", id] as const,
    options: (id?: number) => ["products", "options", id || "global"] as const,
    media: (query: unknown) => ["products", "media", query] as const
  },
  sales: {
    root: ["sales"] as const,
    cards: (query: SalesListQuery) => ["sales", "cards", query] as const,
    detail: (id: number) => ["sales", "detail", id] as const
  },
  settings: {
    root: ["settings"] as const,
    print: () => ["settings", "print"] as const,
    skuNumber: () => ["settings", "sku-number"] as const,
    system: (key: string) => ["settings", "system", key] as const
  },
  workflowOrders: {
    root: ["workflow-orders"] as const,
    list: (query: ProcessOrderListQuery) => ["workflow-orders", "list", query] as const
  }
};
