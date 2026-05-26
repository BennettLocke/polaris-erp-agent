import type { CustomerItem } from "@/types";

export const customerFilterOptions = [
  { value: "all", label: "全部" },
  { value: "monthly", label: "月结" },
  { value: "normal", label: "普通" },
  { value: "debt", label: "有欠款" },
  { value: "normal_debt", label: "普通欠款" },
  { value: "credit", label: "有余额" },
  { value: "no_phone", label: "未绑定电话" }
] as const;

export const balanceActionLabels = {
  receipt: "收款",
  recharge: "充值",
  settlement: "结款",
  adjust: "调余额"
} as const;

export const payTypeOptions = [
  { value: "wechat", label: "微信" },
  { value: "cash", label: "现金" },
  { value: "balance", label: "余额" },
  { value: "transfer", label: "转账" }
] as const;

export type CustomerFilter = (typeof customerFilterOptions)[number]["value"];

export function customerName(customer?: CustomerItem | null) {
  return customer?.customer_name || customer?.company_name || customer?.name || (customer?.id ? `客户${customer.id}` : "");
}

export function customerPhone(customer?: CustomerItem | null) {
  return customer?.phone || customer?.mobile || customer?.contacts_tel || "";
}

export function money(value?: string | number | null) {
  const raw = value === undefined || value === null || value === "" ? "0" : String(value);
  const num = Number(raw);
  return Number.isFinite(num) ? `¥${num.toFixed(2)}` : `¥${raw}`;
}

export function moneyNumber(value?: string | number | null) {
  const num = Number(value ?? 0);
  return Number.isFinite(num) ? num : 0;
}

export function displayDate(value?: string | null) {
  if (!value) return "未记录";
  return value.replace("T", " ").slice(0, 16);
}

export function shortDate(value?: string | null) {
  if (!value) return "未记录";
  return value.replace("T", " ").slice(0, 10);
}

export function monthOptions(year = new Date().getFullYear()) {
  return Array.from({ length: 12 }, (_, index) => {
    const month = index + 1;
    return {
      label: `${month}月`,
      value: `${year}-${String(month).padStart(2, "0")}`
    };
  });
}

export function customerMatchesFilter(customer: CustomerItem, filter: CustomerFilter) {
  const balance = moneyNumber(customer.balance_amount);
  const isMonthly = Number(customer.is_monthly_customer || 0) === 1;
  if (filter === "monthly") return isMonthly;
  if (filter === "normal") return !isMonthly;
  if (filter === "debt") return balance < 0;
  if (filter === "normal_debt") return !isMonthly && balance < 0;
  if (filter === "credit") return balance > 0;
  if (filter === "no_phone") return !customerPhone(customer);
  return true;
}

export function customerSummary(items: CustomerItem[]) {
  return {
    total: items.length,
    monthly: items.filter((item) => Number(item.is_monthly_customer || 0) === 1).length,
    debt: items.filter((item) => moneyNumber(item.balance_amount) < 0).length,
    normalDebt: items.filter((item) => Number(item.is_monthly_customer || 0) !== 1 && moneyNumber(item.balance_amount) < 0).length,
    monthlyDebt: items.filter((item) => Number(item.is_monthly_customer || 0) === 1 && moneyNumber(item.balance_amount) < 0).length,
    noPhone: items.filter((item) => !customerPhone(item)).length,
    creditAmount: items.reduce((sum, item) => {
      const balance = moneyNumber(item.balance_amount);
      return sum + (balance > 0 ? balance : 0);
    }, 0),
    debtAmount: items.reduce((sum, item) => {
      const balance = moneyNumber(item.balance_amount);
      return sum + (balance < 0 ? Math.abs(balance) : 0);
    }, 0)
  };
}

export function normalizeCustomerSummary(summary: unknown, fallbackItems: CustomerItem[]) {
  const fallback = customerSummary(fallbackItems);
  if (!summary || typeof summary !== "object") return fallback;
  const data = summary as Record<string, string | number | undefined>;
  return {
    total: Number(data.total ?? fallback.total),
    monthly: Number(data.monthly ?? fallback.monthly),
    debt: Number(data.debt ?? fallback.debt),
    normalDebt: Number(data.normal_debt ?? fallback.normalDebt),
    monthlyDebt: Number(data.monthly_debt ?? fallback.monthlyDebt),
    noPhone: Number(data.no_phone ?? fallback.noPhone),
    creditAmount: moneyNumber(data.credit_amount ?? fallback.creditAmount),
    debtAmount: moneyNumber(data.debt_amount ?? fallback.debtAmount)
  };
}
