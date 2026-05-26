import type { SalesCard, SalesProduct } from "@/types";

function money(value: unknown) {
  const num = Number(value ?? 0);
  return `¥${Number.isFinite(num) ? num.toFixed(2) : "0.00"}`;
}

function displayDate(value?: string) {
  if (!value) return "-";
  return value.replace("T", " ").slice(0, 16);
}

function salesOrderId(order?: SalesCard | null) {
  return Number(order?.id || order?.sales_id || 0);
}

function salesAmount(order: SalesCard) {
  return money(order.receivable_amount || order.total_price);
}

function salesQuantity(order: SalesCard) {
  return order.total_quantity || order.buy_number_count || 0;
}

function payText(order: SalesCard) {
  const status = order.pay_status_text || (order.pay_status === "monthly" ? "月结" : order.pay_status === "unpaid" ? "未付" : "已付款");
  const type = order.pay_type_text || "";
  if (status === "月结" || !type) return status || "-";
  return `${status} / ${type}`;
}

function productLine(product: SalesProduct) {
  const title = product.title || product.name || "商品";
  const spec = product.spec || product.color || "默认颜色";
  const quantity = product.quantity || product.buy_number || 0;
  return `${title} ${spec} x${quantity}`;
}

function productSummary(order: SalesCard, limit = 2) {
  const products = order.products || [];
  const lines = products.slice(0, limit).map(productLine);
  const extra = Math.max(0, products.length - limit);
  return { lines, extra };
}

function stockRuleText(product: SalesProduct) {
  return Number(product.is_stock_item ?? 1) === 0 ? "不扣库存" : "扣库存";
}

export {
  displayDate,
  money,
  payText,
  productLine,
  productSummary,
  salesAmount,
  salesOrderId,
  salesQuantity,
  stockRuleText
};
