import type { WheelEvent } from "react";

import type { CustomerItem, SalesProduct, Warehouse } from "@/types";
import type { PayTypeOption, SalesPayStatus, SalesResultLite } from "./types";

export function defaultDateTimeValue() {
  const now = new Date();
  now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
  return now.toISOString().slice(0, 16);
}

export function money(value: unknown) {
  const num = Number(value || 0);
  return `¥${num.toFixed(2)}`;
}

export function customerDisplayName(customer?: CustomerItem | null) {
  return customer?.customer_name || customer?.company_name || customer?.name || (customer?.id ? `客户${customer.id}` : "");
}

export function productVariants(product: SalesProduct) {
  const variants = product.product_group_data || [];
  return variants.length ? variants : [product];
}

export function productDisplayTitle(product?: SalesProduct | null) {
  return product?.title || product?.name || "商品";
}

export function productSearchText(product?: SalesProduct | null) {
  if (!product) return "";
  return [
    productDisplayTitle(product),
    product.product_category_text,
    product.color_text,
    product.sku_no,
    product.coding
  ].filter(Boolean).join(" ");
}

export function productDisplaySpec(product?: SalesProduct | null) {
  return product?.spec || product?.color || "默认颜色";
}

export function toNumber(value: unknown, fallback = 0) {
  const num = Number(value ?? fallback);
  return Number.isFinite(num) ? num : fallback;
}

export function inputNoWheel(event: WheelEvent<HTMLInputElement>) {
  event.currentTarget.blur();
}

export function salesResultId(result: SalesResultLite) {
  return Number(result?.id || result?.sales_id || 0);
}

export function warehouseName(warehouse?: Warehouse | null) {
  return warehouse?.name || warehouse?.warehouse_name || (warehouse?.id ? `仓库${warehouse.id}` : "仓库");
}

export function paymentLabel(payStatus: SalesPayStatus, payType: string, payTypeOptions: PayTypeOption[]) {
  if (payStatus === "monthly") return "月结";
  if (payStatus === "unpaid") return "未付";
  return payTypeOptions.find((item) => item.value === payType)?.label || "已付";
}

export function customerPhoneText(customer?: CustomerItem | null) {
  return customer?.phone || customer?.mobile || customer?.contacts_tel || "";
}

export function productColorCount(product: SalesProduct) {
  return Number(product.color_count || product.product_group_data?.length || 1) || 1;
}
