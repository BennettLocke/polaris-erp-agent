export type PurchaseResultItem = {
  productId: number;
  productName: string;
  color: string;
  quantity: number;
  unitName: string;
  caseCount?: number;
  warehouseId: number;
  warehouseName: string;
  docNo?: string;
};

export type PurchaseBatchResult = {
  items: PurchaseResultItem[];
  failedItems: {
    productName: string;
    color: string;
    warehouseName: string;
    message: string;
    uncertain: boolean;
  }[];
  unprocessedCount: number;
  salesStatus: "created" | "failed" | "not_created" | "uncertain";
  salesNo?: string;
  error?: string;
};

export function formatPurchaseResult(items: PurchaseResultItem[]): string {
  return items.map((item) => {
    const name = item.productName.replace(/[【】\s]/g, "");
    const amount = item.caseCount !== undefined && item.caseCount > 0
      ? `${item.caseCount}件`
      : `${item.quantity}${item.unitName}`;
    const warehouse = item.warehouseName.trim().replace(/仓库$/, "");
    return `商品：${name}\n颜色：${item.color}\n进货：${amount}\n备注：送至${warehouse}`;
  }).join("\n\n");
}
