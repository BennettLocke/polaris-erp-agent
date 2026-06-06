import { useEffect, useMemo, useRef, useState, type ChangeEvent, type ClipboardEvent, type KeyboardEvent } from "react";
import {
  Bot,
  Check,
  History,
  Image as ImageIcon,
  Loader2,
  MessageSquarePlus,
  Paperclip,
  RefreshCw,
  Send,
  Sparkles,
  Upload,
  X
} from "lucide-react";

import { api } from "@/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from "@/components/ui/dialog";
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import type {
  AgentMessageHistoryItem,
  AgentSessionSnapshot,
  AnalyticsHotProduct,
  DashboardSummary,
  InventoryCardsResult,
  InventoryLookupResult,
  WorkbenchInventoryCard,
  WorkbenchInventoryLookupRow
} from "@/types";

type ChatRole = "user" | "assistant";

type ChatMessage = {
  id: string;
  role: ChatRole;
  content: string;
  createdAt: string;
  status?: "sending" | "error";
};

type BusinessHistoryItem = {
  id: string;
  type: "inventory" | "sales" | "workflow" | "purchase" | "transfer" | "stocktaking" | "print" | "customer" | "agent";
  resultType: WorkbenchResultType;
  title: string;
  label: string;
  summary: string;
  response: string;
  createdAt: string;
  businessKey?: string;
  inventoryCards?: WorkbenchInventoryCard[];
  inventoryLookup?: InventoryLookupResult | null;
  inventorySource?: string;
};

type WorkbenchResultType = "agent" | "inventory" | "image";

type WorkbenchResult = {
  id: string;
  type: WorkbenchResultType;
  title: string;
  label: string;
  summary: string;
  response: string;
  createdAt: string;
  inventoryCards?: WorkbenchInventoryCard[];
  inventoryLookup?: InventoryLookupResult | null;
  inventorySource?: string;
};

type ResultSource = "text" | "image";

type BusinessHistoryExtras = {
  inventoryCards?: WorkbenchInventoryCard[];
  inventoryLookup?: InventoryLookupResult | null;
  inventorySource?: string;
};

type PendingField = {
  path: string;
  label: string;
  value: unknown;
};

type PendingConfirmKind =
  | "sales"
  | "workflow"
  | "productMatch"
  | "purchase"
  | "transfer"
  | "stocktaking"
  | "bagUpload"
  | "generic";

type ConfirmField = PendingField & {
  inputMode?: "text" | "numeric" | "decimal";
  readOnly?: boolean;
};

type ConfirmSection = {
  title: string;
  description?: string;
  fields: ConfirmField[];
};

type ConfirmFieldOptions = Pick<ConfirmField, "inputMode" | "readOnly">;

const SESSION_KEY = "sj_admin_agent_session_id";
const MESSAGE_KEY_PREFIX = "sj_admin_agent_messages_";
const BUSINESS_KEY_PREFIX = "sj_admin_business_history_";
const MAX_BUSINESS_HISTORY = 5;
const DASHBOARD_SUMMARY_REFRESH_MS = 8000;

const COMMANDS = ["开单", "查库存", "进货", "调货", "盘点", "工作流", "上传泡袋"];

const WELCOME_MESSAGE: ChatMessage = {
  id: "welcome",
  role: "assistant",
  content: "你好，我是北极星。可以直接说开单、查库存、进货、盘点、调货，也可以上传订单图或设计稿。",
  createdAt: new Date().toISOString()
};

function newSessionId() {
  return `web_${Date.now()}_${Math.random().toString(16).slice(2, 8)}`;
}

function newMessageId(prefix = "msg") {
  return `${prefix}_${Date.now()}_${Math.random().toString(16).slice(2)}`;
}

function hasStorage() {
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
}

function readStoredSessionId() {
  if (!hasStorage()) return newSessionId();
  const stored = window.localStorage.getItem(SESSION_KEY);
  if (stored) return stored;
  const next = newSessionId();
  window.localStorage.setItem(SESSION_KEY, next);
  return next;
}

function messageStorageKey(sessionId: string) {
  return `${MESSAGE_KEY_PREFIX}${sessionId}`;
}

function businessStorageKey(sessionId: string) {
  return `${BUSINESS_KEY_PREFIX}${sessionId}`;
}

function restoreMessages(sessionId: string): ChatMessage[] {
  if (!hasStorage()) return [];
  try {
    const parsed = JSON.parse(window.localStorage.getItem(messageStorageKey(sessionId)) || "[]");
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function restoreBusinessHistory(sessionId: string): BusinessHistoryItem[] {
  if (!hasStorage()) return [];
  try {
    const parsed = JSON.parse(window.localStorage.getItem(businessStorageKey(sessionId)) || "[]");
    return Array.isArray(parsed) ? parsed.slice(0, MAX_BUSINESS_HISTORY) : [];
  } catch {
    return [];
  }
}

function saveJson(key: string, value: unknown) {
  if (!hasStorage()) return;
  window.localStorage.setItem(key, JSON.stringify(value));
}

function historyToMessages(history: AgentMessageHistoryItem[]): ChatMessage[] {
  return history
    .filter((item) => item.content)
    .map((item, index) => ({
      id: `history_${index}_${item.role}`,
      role: item.role === "user" ? "user" : "assistant",
      content: item.content,
      createdAt: new Date().toISOString()
    }));
}

function isConfirmablePending(session?: AgentSessionSnapshot | null) {
  const action = String(session?.pending_action || "");
  return Boolean(session?.has_pending && action.includes("confirm_"));
}

function pendingTitle(session?: AgentSessionSnapshot | null) {
  const action = String(session?.pending_action || "");
  const intent = String(session?.pending_intent || "");
  if (intent.includes("bag_upload") || action.includes("bag_")) return "泡袋上传确认";
  if (action.includes("confirm_image_workflow_orders")) return "OCR 识别结果";
  if (action.includes("confirm_image_sales")) return "是否继续开销售单";
  if (action.includes("confirm_product_name")) return "商品匹配确认";
  if (action.includes("transfer")) return "调货确认";
  if (action.includes("purchase")) return "进货确认";
  if (action.includes("stocktaking") || intent.includes("stocktaking")) return "盘点确认";
  if (action.includes("workflow") || intent.includes("workflow")) return "工作流订单确认";
  if (action.includes("sales") || action.includes("order") || intent.includes("order")) return "销售单确认";
  return "AI 业务确认";
}

function isWarehousePath(path = "") {
  return /(^|\.)(warehouse_id|purchase_warehouse_id|out_warehouse_id|enter_warehouse_id|from_wh|to_wh)$/.test(path);
}

function warehouseNameFromId(value: unknown) {
  const text = String(value ?? "").trim();
  if (!text) return "未填写";
  if (text === "1") return "自己店里";
  if (text === "2") return "百鑫仓库";
  return text;
}

function warehouseIdFromName(value: string) {
  const text = value.trim();
  if (!text) return null;
  if (/^\d+$/.test(text)) return Number(text);
  if (text.includes("自己") || text.includes("店里") || text.includes("门店")) return 1;
  if (text.includes("百鑫")) return 2;
  return null;
}

function displayConfirmValue(field: ConfirmField) {
  if (isWarehousePath(field.path)) return warehouseNameFromId(field.value);
  return field.value === undefined || field.value === null ? "" : String(field.value);
}

function valueLabel(value: unknown, path = "") {
  if (isWarehousePath(path)) return warehouseNameFromId(value);
  if (value === null || value === undefined || value === "") return "未填写";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function labelFromPath(path: string) {
  const parts = path.split(".").filter(Boolean);
  const last = parts.length ? parts[parts.length - 1] : path;
  const labels: Record<string, string> = {
    customer: "客户",
    customer_name: "客户",
    name: "商品",
    product_name: "商品",
    goods_name: "商品",
    color: "颜色",
    spec: "颜色/规格",
    goods_color: "颜色",
    qty: "数量",
    quantity: "数量",
    order_quantity: "数量",
    price: "单价",
    warehouse_id: "仓库",
    purchase_warehouse_id: "入库仓库",
    from_wh: "调出仓库",
    to_wh: "调入仓库",
    remark: "备注",
    pending_action: "动作"
  };
  return labels[last] || last;
}

function flattenState(value: unknown, prefix = "", rows: PendingField[] = []): PendingField[] {
  if (rows.length >= 18) return rows;
  if (Array.isArray(value)) {
    value.slice(0, 6).forEach((item, index) => flattenState(item, prefix ? `${prefix}.${index}` : String(index), rows));
    return rows;
  }
  if (value && typeof value === "object") {
    Object.entries(value as Record<string, unknown>).forEach(([key, item]) => {
      if (rows.length >= 18) return;
      const path = prefix ? `${prefix}.${key}` : key;
      if (item && typeof item === "object") {
        flattenState(item, path, rows);
      } else {
        rows.push({ path, label: labelFromPath(path), value: item });
      }
    });
    return rows;
  }
  if (prefix) rows.push({ path: prefix, label: labelFromPath(prefix), value });
  return rows;
}

function isPlainRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function isEditableValue(value: unknown) {
  return value === null || value === undefined || ["string", "number", "boolean"].includes(typeof value);
}

function readValueByPath(source: unknown, path: string) {
  if (!path) return undefined;
  let ref: any = source;
  for (const part of path.split(".").filter(Boolean)) {
    if (ref === null || ref === undefined) return undefined;
    const key = /^\d+$/.test(part) ? Number(part) : part;
    ref = ref[key];
  }
  return ref;
}

function confirmKindForSession(session?: AgentSessionSnapshot | null): PendingConfirmKind {
  const action = String(session?.pending_action || "");
  const intent = String(session?.pending_intent || "");
  if (intent.includes("bag_upload") || action.includes("bag_")) return "bagUpload";
  if (action.includes("confirm_product_name")) return "productMatch";
  if (action.includes("transfer") || intent.includes("transfer")) return "transfer";
  if (action.includes("purchase") || intent.includes("purchase")) return "purchase";
  if (action.includes("stocktaking") || intent.includes("stocktaking")) return "stocktaking";
  if (action.includes("workflow") || intent.includes("workflow")) return "workflow";
  if (action.includes("sales") || action.includes("order") || intent.includes("order")) return "sales";
  return "generic";
}

function makeConfirmField(path: string, label: string, value: unknown, options: ConfirmFieldOptions = {}): ConfirmField {
  return { path, label, value, ...options };
}

function firstConfirmField(
  state: Record<string, unknown>,
  paths: string[],
  label: string,
  options: ConfirmFieldOptions = {}
): ConfirmField {
  for (const path of paths) {
    const value = readValueByPath(state, path);
    if (value !== undefined && value !== null && value !== "" && isEditableValue(value)) {
      return makeConfirmField(path, label, value, options);
    }
  }
  for (const path of paths) {
    const value = readValueByPath(state, path);
    if (value !== undefined && isEditableValue(value)) {
      return makeConfirmField(path, label, value, options);
    }
  }
  return makeConfirmField(paths[0], label, "", options);
}

function optionalConfirmField(
  state: Record<string, unknown>,
  paths: string[],
  label: string,
  options: ConfirmFieldOptions = {}
): ConfirmField | null {
  for (const path of paths) {
    const value = readValueByPath(state, path);
    if (value !== undefined && isEditableValue(value)) {
      return makeConfirmField(path, label, value, options);
    }
  }
  return null;
}

function compactConfirmFields(fields: Array<ConfirmField | null | undefined>) {
  const seen = new Set<string>();
  return fields.filter((field): field is ConfirmField => {
    if (!field || !field.path || seen.has(field.path)) return false;
    seen.add(field.path);
    return true;
  });
}

function confirmFieldsForPrefix(
  state: Record<string, unknown>,
  prefix: string,
  configs: Array<{ paths: string[]; label: string; options?: ConfirmFieldOptions; required?: boolean }>
) {
  return compactConfirmFields(
    configs.map((config) => {
      const paths = config.paths.map((path) => `${prefix}.${path}`);
      return config.required === false
        ? optionalConfirmField(state, paths, config.label, config.options)
        : firstConfirmField(state, paths, config.label, config.options);
    })
  );
}

function confirmSection(title: string, description: string | undefined, fields: Array<ConfirmField | null | undefined>) {
  const compacted = compactConfirmFields(fields);
  return compacted.length ? { title, description, fields: compacted } : null;
}

function arrayConfirmSections(
  state: Record<string, unknown>,
  paths: string[],
  title: string,
  configs: Array<{ paths: string[]; label: string; options?: ConfirmFieldOptions; required?: boolean }>
) {
  for (const path of paths) {
    const rows = readValueByPath(state, path);
    if (!Array.isArray(rows) || !rows.length) continue;
    return rows.slice(0, 8).flatMap((_, index) => {
      const fields = confirmFieldsForPrefix(state, `${path}.${index}`, configs);
      return fields.length ? [{ title: `${title} ${index + 1}`, fields }] : [];
    });
  }
  return [];
}

function fallbackConfirmSections(state: Record<string, unknown>, title = "原始字段") {
  const fields = flattenState(state).slice(0, 18).map((field) => ({ ...field }));
  const section = confirmSection(title, "未识别到专用结构，先展示可编辑原始字段。", fields);
  return section ? [section] : [];
}

function buildConfirmSections(session: AgentSessionSnapshot | null): ConfirmSection[] {
  const state = isPlainRecord(session?.state) ? session.state : {};
  const kind = confirmKindForSession(session);
  const pendingAction = String(state.pending_action || "");
  const productConfigs = [
    { paths: ["title", "name", "product_name", "goods_name"], label: "商品" },
    { paths: ["color", "goods_color", "spec"], label: "颜色/规格" },
    { paths: ["qty", "quantity", "order_quantity", "buy_number"], label: "数量", options: { inputMode: "decimal" as const } },
    { paths: ["unit", "unit_name"], label: "单位", required: false },
    { paths: ["price", "unit_price"], label: "单价", options: { inputMode: "decimal" as const }, required: false },
    { paths: ["warehouse_name", "warehouse_id"], label: "仓库", required: false }
  ];

  if (kind === "sales") {
    const orderParamsPrefix = pendingAction === "confirm_image_sales" ? "order_params." : "";
    const salesCustomerPaths = pendingAction === "confirm_image_sales"
      ? ["order_params.customer", "order_params.customer_name", "customer_name", "customer", "customer_id"]
      : ["customer_name", "customer", "customer_id"];
    const salesProductPaths = pendingAction === "confirm_image_sales"
      ? ["order_params.products", "products", "items", "detail"]
      : ["products", "items", "detail"];
    const sections = [
      confirmSection("销售单明细", "核对客户、仓库和付款信息。", [
        firstConfirmField(state, salesCustomerPaths, "客户"),
        optionalConfirmField(state, [`${orderParamsPrefix}warehouse_name`, `${orderParamsPrefix}warehouse_id`, "warehouse_name", "warehouse_id"], "仓库"),
        optionalConfirmField(state, [`${orderParamsPrefix}pay_status`, `${orderParamsPrefix}payment_status`, "pay_status", "payment_status"], "付款状态"),
        optionalConfirmField(state, [`${orderParamsPrefix}pay_type`, `${orderParamsPrefix}payment_type`, "pay_type", "payment_type"], "付款方式"),
        optionalConfirmField(state, [`${orderParamsPrefix}remark`, `${orderParamsPrefix}note`, "remark", "note"], "备注")
      ]),
      ...arrayConfirmSections(state, salesProductPaths, "销售商品", productConfigs)
    ].filter(Boolean) as ConfirmSection[];
    return sections.length ? sections : fallbackConfirmSections(state, "销售单明细");
  }

  if (kind === "workflow") {
    const workflowRowSections = arrayConfirmSections(state, ["parsed_list", "orders", "workflow_orders"], "工作流订单", [
      { paths: ["customer_name", "customer"], label: "客户" },
      { paths: ["goods_name", "product_name", "name"], label: "商品" },
      { paths: ["goods_color", "color", "spec"], label: "颜色/规格", required: false },
      { paths: ["order_quantity", "quantity", "qty"], label: "数量", options: { inputMode: "decimal" as const }, required: false },
      { paths: ["remark", "note"], label: "备注", required: false }
    ]);
    const hasWorkflowRows = workflowRowSections.length > 0;
    if (pendingAction === "confirm_image_workflow_orders" && hasWorkflowRows) {
      return workflowRowSections;
    }

    const sections = [
      confirmSection("工作流订单", "确认客户、商品、颜色和制作数量。", [
        firstConfirmField(state, ["customer_name", "customer"], "客户"),
        firstConfirmField(state, ["goods_name", "product_name", "name"], "商品"),
        optionalConfirmField(state, ["goods_color", "color", "spec"], "颜色/规格"),
        optionalConfirmField(state, ["order_quantity", "quantity", "qty"], "数量", { inputMode: "decimal" }),
        optionalConfirmField(state, ["remark", "note"], "备注")
      ]),
      ...workflowRowSections
    ].filter(Boolean) as ConfirmSection[];
    return sections.length ? sections : fallbackConfirmSections(state, "工作流订单");
  }

  if (kind === "productMatch") {
    const section = confirmSection("商品匹配", "确认 AI 识别到的商品名称和匹配结果。", [
      firstConfirmField(state, ["query", "input_name", "goods_name", "product_name", "name"], "识别商品"),
      firstConfirmField(state, ["matched_name", "candidate_name", "matched_product_name", "product.name"], "匹配商品"),
      optionalConfirmField(state, ["sku_no", "coding", "product.sku_no"], "SKU"),
      optionalConfirmField(state, ["color", "spec", "product.color"], "颜色/规格")
    ]);
    return section ? [section] : fallbackConfirmSections(state, "商品匹配");
  }

  if (kind === "purchase") {
    const sections = [
      confirmSection("进货信息", "确认入库仓库和备注。", [
        firstConfirmField(state, ["warehouse_name", "purchase_warehouse_id", "warehouse_id"], "入库仓库"),
        optionalConfirmField(state, ["supplier_name", "supplier"], "供应商"),
        optionalConfirmField(state, ["remark", "note"], "备注")
      ]),
      ...arrayConfirmSections(state, ["items", "products"], "进货明细", [
        { paths: ["title", "name", "product_name", "goods_name"], label: "商品" },
        { paths: ["color", "spec", "goods_color"], label: "颜色/规格", required: false },
        { paths: ["qty", "quantity", "purchase_qty", "buy_number"], label: "数量", options: { inputMode: "decimal" as const } },
        { paths: ["unit", "unit_name"], label: "单位", required: false }
      ])
    ].filter(Boolean) as ConfirmSection[];
    return sections.length ? sections : fallbackConfirmSections(state, "进货明细");
  }

  if (kind === "transfer") {
    const sections = [
      confirmSection("调货方向", "确认调出、调入仓库。", [
        firstConfirmField(state, ["from_warehouse_name", "from_wh", "out_warehouse_id"], "调出仓库"),
        firstConfirmField(state, ["to_warehouse_name", "to_wh", "enter_warehouse_id"], "调入仓库"),
        optionalConfirmField(state, ["remark", "note"], "备注")
      ]),
      ...arrayConfirmSections(state, ["items", "products"], "调货明细", [
        { paths: ["title", "name", "product_name", "goods_name"], label: "商品" },
        { paths: ["color", "spec", "goods_color"], label: "颜色/规格", required: false },
        { paths: ["qty", "quantity", "transfer_number", "buy_number"], label: "数量", options: { inputMode: "decimal" as const } },
        { paths: ["unit", "unit_name"], label: "单位", required: false }
      ])
    ].filter(Boolean) as ConfirmSection[];
    return sections.length ? sections : fallbackConfirmSections(state, "调货明细");
  }

  if (kind === "stocktaking") {
    const sections = [
      confirmSection("盘点仓库", "确认盘点仓库和备注。", [
        firstConfirmField(state, ["warehouse_name", "warehouse_id"], "仓库"),
        optionalConfirmField(state, ["remark", "note"], "备注")
      ]),
      ...arrayConfirmSections(state, ["items", "products"], "盘点明细", [
        { paths: ["title", "name", "product_name", "goods_name"], label: "商品" },
        { paths: ["color", "spec", "goods_color"], label: "颜色/规格", required: false },
        { paths: ["stock", "current_stock", "before_qty"], label: "账面库存", options: { inputMode: "decimal" as const }, required: false },
        { paths: ["qty", "quantity", "number", "actual_qty"], label: "盘点数量", options: { inputMode: "decimal" as const } },
        { paths: ["unit", "unit_name"], label: "单位", required: false }
      ])
    ].filter(Boolean) as ConfirmSection[];
    return sections.length ? sections : fallbackConfirmSections(state, "盘点明细");
  }

  if (kind === "bagUpload") {
    return fallbackConfirmSections(state, "泡袋上传确认");
  }

  return fallbackConfirmSections(state);
}

function cloneState(state: AgentSessionSnapshot["state"]) {
  if (!state || typeof state !== "object") return {};
  return JSON.parse(JSON.stringify(state)) as Record<string, unknown>;
}

function coerceValue(raw: string, original: unknown) {
  if (typeof original === "number") {
    const numberValue = Number(raw);
    return Number.isFinite(numberValue) ? numberValue : original;
  }
  if (typeof original === "boolean") {
    return ["1", "true", "是", "已"].includes(raw.trim().toLowerCase());
  }
  return raw;
}

function coerceConfirmValue(raw: string, field: ConfirmField) {
  if (isWarehousePath(field.path)) {
    const warehouseId = warehouseIdFromName(raw);
    if (warehouseId) return warehouseId;
  }
  return coerceValue(raw, field.value);
}

function setValueByPath(target: Record<string, unknown>, path: string, value: unknown) {
  const parts = path.split(".").filter(Boolean);
  if (!parts.length) return;
  let ref: any = target;
  for (let index = 0; index < parts.length - 1; index += 1) {
    const key = /^\d+$/.test(parts[index]) ? Number(parts[index]) : parts[index];
    const nextKey = parts[index + 1];
    if (ref[key] === undefined || ref[key] === null) {
      ref[key] = /^\d+$/.test(nextKey) ? [] : {};
    }
    ref = ref[key];
  }
  const last = parts.length ? parts[parts.length - 1] : "";
  ref[/^\d+$/.test(last) ? Number(last) : last] = value;
}

function inferHistoryType(text: string, session?: AgentSessionSnapshot | null): BusinessHistoryItem["type"] {
  const lastOrder = session?.last_order || {};
  const type = String(lastOrder.type || "");
  if (type === "sales") return "sales";
  if (type === "workflow") return "workflow";
  if (/库存/.test(text)) return "inventory";
  if (/进货/.test(text)) return "purchase";
  if (/调货|调拨/.test(text)) return "transfer";
  if (/盘点/.test(text)) return "stocktaking";
  if (/打印/.test(text)) return "print";
  if (/客户/.test(text)) return "customer";
  return "agent";
}

function titleForHistory(type: BusinessHistoryItem["type"]) {
  const titles: Record<BusinessHistoryItem["type"], string> = {
    inventory: "库存查询",
    sales: "销售单",
    workflow: "工作流订单",
    purchase: "进货",
    transfer: "调货",
    stocktaking: "盘点",
    print: "打印",
    customer: "客户",
    agent: "AI 结果"
  };
  return titles[type];
}

function resultTypeFor(historyType: BusinessHistoryItem["type"], source: ResultSource): WorkbenchResultType {
  if (source === "image") return "image";
  if (historyType === "inventory") return "inventory";
  return "agent";
}

function buildHistoryItem(
  response: string,
  session?: AgentSessionSnapshot | null,
  source: ResultSource = "text",
  extras: BusinessHistoryExtras = {}
): BusinessHistoryItem {
  const type = inferHistoryType(response, session);
  const firstLine = response.split(/\r?\n/).map((line) => line.trim()).find(Boolean) || "已处理";
  const lastOrder = session?.last_order || {};
  const businessKey = [type, lastOrder.id, lastOrder.order_id, lastOrder.sales_no].filter(Boolean).join(":") || undefined;
  return {
    id: newMessageId("biz"),
    type,
    resultType: resultTypeFor(type, source),
    businessKey,
    title: titleForHistory(type),
    label: type === "agent" ? "已回复" : "已处理",
    summary: firstLine,
    response,
    createdAt: new Date().toISOString(),
    ...extras
  };
}

function resultFromHistory(item: BusinessHistoryItem): WorkbenchResult {
  return {
    id: item.id,
    type: item.resultType || resultTypeFor(item.type, "text"),
    title: item.title,
    label: item.label,
    summary: item.summary,
    response: item.response || item.summary,
    createdAt: item.createdAt,
    inventoryCards: item.inventoryCards,
    inventoryLookup: item.inventoryLookup,
    inventorySource: item.inventorySource
  };
}

function shouldOpenResultDialog(item: BusinessHistoryItem) {
  return item.resultType === "image" || item.type !== "agent";
}

function isImageLine(line: string) {
  const clean = line.trim();
  if (clean.startsWith("/api/images/file/")) return true;
  if (!clean.startsWith("http://") && !clean.startsWith("https://")) return false;
  return /\.(png|jpe?g|webp|gif)(\?.*)?$/i.test(clean);
}

function inventoryKeywordFromMessage(message: string) {
  return message
    .replace(/[，。！？、,!?]/g, " ")
    .replace(/查一下|看一下|查下|看下|查询|搜索|显示|统计/g, " ")
    .replace(/库存查询|查询库存|查库存|查仓库|仓库查询|查询仓库|库存|仓库/g, " ")
    .replace(/百鑫|自己店里|自己店|店里|自己|门店/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function textParam(value: unknown) {
  return typeof value === "string" || typeof value === "number" ? String(value).trim() : "";
}

function recordParam(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function inventoryWarehouseIdFromMessage(message: string) {
  if (/自己店里|自己店|店里|自己|门店/.test(message)) return 1;
  if (/百鑫仓库|百鑫仓|百鑫/.test(message)) return 2;
  return undefined;
}

function inventoryColorFromMessage(message: string) {
  const colors = ["橄榄绿", "深咖色", "香槟金", "古铜色", "卡其色", "红色", "黄色", "橙色", "蓝色", "绿色", "咖色", "黑色", "白色", "紫色", "粉色"];
  return colors.find((color) => message.includes(color)) || "";
}

function inventoryLookupQueryFromMessage(message: string, session?: AgentSessionSnapshot | null) {
  const extraction = recordParam(session?.last_extraction);
  const params = recordParam(extraction.params);
  const keyword = textParam(params.product_name || params.keyword) || inventoryKeywordFromMessage(message);
  const color = textParam(params.color) || inventoryColorFromMessage(message);
  const messageWarehouseId = inventoryWarehouseIdFromMessage(message);
  const warehouseId = messageWarehouseId !== undefined ? messageWarehouseId : undefined;
  return {
    keyword,
    color,
    warehouseId,
    limit: 40
  };
}

function normalizeInventoryWarehouseName(value: string) {
  const text = value.trim();
  if (/自己店里|自己店|店里|自己|门店/.test(text)) return "自己店里";
  if (/百鑫仓库|百鑫仓|百鑫/.test(text)) return "百鑫仓库";
  return text;
}

function inventoryLookupFromResponse(response: string, query: ReturnType<typeof inventoryLookupQueryFromMessage>): InventoryLookupResult | null {
  const rows = new Map<string, WorkbenchInventoryLookupRow>();
  const warehouses = new Map<string, { id?: number | string | null; name: string }>();
  response.split(/\r?\n/).forEach((line) => {
    const cells = line.split("|").map((cell) => cell.trim()).filter(Boolean);
    if (cells.length < 4) return;
    const [warehouseCell, titleCell, colorCell, quantityCell] = cells;
    if (
      /仓库/.test(titleCell)
      || /^-+$/.test(warehouseCell.replace(/:/g, ""))
      || titleCell === "产品"
      || colorCell === "颜色"
      || titleCell.includes("合计")
      || colorCell.includes("记录")
    ) {
      return;
    }
    const warehouseName = normalizeInventoryWarehouseName(warehouseCell);
    if (!warehouseName || !/自己店里|百鑫仓库/.test(warehouseName)) return;
    const quantityMatch = quantityCell.replace(/,/g, "").match(/-?\d+(?:\.\d+)?/);
    if (!quantityMatch) return;
    const quantity = Number(quantityMatch[0]);
    if (!Number.isFinite(quantity)) return;
    const warehouseId = warehouseName === "自己店里" ? 1 : warehouseName === "百鑫仓库" ? 2 : null;
    warehouses.set(warehouseName, { id: warehouseId, name: warehouseName });
    const key = `${titleCell}|${colorCell}`;
    const current = rows.get(key) || {
      sku_no: "",
      title: titleCell,
      color: colorCell,
      unit_name: "套",
      piece_text: "",
      warehouses: {},
      warehouse_ids: {},
      total_stock: 0
    };
    current.warehouses[warehouseName] = Number(current.warehouses[warehouseName] || 0) + quantity;
    if (current.warehouse_ids) current.warehouse_ids[warehouseName] = warehouseId;
    current.total_stock = Number(current.total_stock || 0) + quantity;
    rows.set(key, current);
  });
  const list = Array.from(rows.values()).filter((row) => Number(row.total_stock || 0) > 0);
  if (!list.length || !warehouses.size) return null;
  const warehouseList = Array.from(warehouses.values()).sort((a, b) => {
    const order = (name: string) => (name === "自己店里" ? 0 : name === "百鑫仓库" ? 1 : 9);
    return order(a.name) - order(b.name);
  });
  list.forEach((row) => {
    warehouseList.forEach((warehouse) => {
      row.warehouses[warehouse.name] = Number(row.warehouses[warehouse.name] || 0);
    });
  });
  return {
    list,
    warehouses: warehouseList,
    total: list.length,
    keyword: query.keyword,
    color: query.color,
    warehouse_id: query.warehouseId,
    source: "agent_response"
  };
}

function shouldLoadInventoryCards(message: string, response: string, session?: AgentSessionSnapshot | null) {
  return inferHistoryType(response, session) === "inventory" || /库存|仓库/.test(message);
}

async function loadInventoryLookupForMessage(message: string, response: string, session?: AgentSessionSnapshot | null): Promise<InventoryLookupResult | null> {
  if (!shouldLoadInventoryCards(message, response, session)) return null;
  const query = inventoryLookupQueryFromMessage(message, session);
  if (!query.keyword && !query.color) return null;
  const responseLookup = inventoryLookupFromResponse(response, query);
  if (responseLookup) return responseLookup;
  try {
    return await api.inventoryLookup(query);
  } catch {
    return null;
  }
}

async function loadInventoryCardsForMessage(message: string, response: string, session?: AgentSessionSnapshot | null): Promise<InventoryCardsResult | null> {
  if (!shouldLoadInventoryCards(message, response, session)) return null;
  try {
    return await api.inventoryCards({
      keyword: inventoryKeywordFromMessage(message),
      onlyInStock: false,
      limit: 12
    });
  } catch {
    return null;
  }
}

function formatTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
}

export function WorkbenchPage() {
  const [sessionId, setSessionId] = useState(readStoredSessionId);
  const [messages, setMessages] = useState<ChatMessage[]>(() => restoreMessages(readStoredSessionId()));
  const [businessHistory, setBusinessHistory] = useState<BusinessHistoryItem[]>(() =>
    restoreBusinessHistory(readStoredSessionId())
  );
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(true);
  const [sessionSnapshot, setSessionSnapshot] = useState<AgentSessionSnapshot | null>(null);
  const [hotProducts, setHotProducts] = useState<AnalyticsHotProduct[]>([]);
  const [hotProductsLoading, setHotProductsLoading] = useState(true);
  const [resultDialog, setResultDialog] = useState<WorkbenchResult | null>(null);
  const [input, setInput] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState("");
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const summaryRequestRef = useRef(0);
  const summaryMountedRef = useRef(true);

  async function refreshSummary(showLoading = false) {
    const requestId = summaryRequestRef.current + 1;
    summaryRequestRef.current = requestId;
    if (showLoading) setSummaryLoading(true);
    try {
      const data = await api.dashboardSummary();
      if (summaryMountedRef.current && summaryRequestRef.current === requestId) {
        setSummary(data);
      }
    } catch {
      // Keep the previous dashboard values if a background refresh fails.
    } finally {
      if (summaryMountedRef.current && summaryRequestRef.current === requestId) {
        setSummaryLoading(false);
      }
    }
  }

  useEffect(() => {
    if (!hasStorage()) return;
    window.localStorage.setItem(SESSION_KEY, sessionId);
  }, [sessionId]);

  useEffect(() => {
    saveJson(messageStorageKey(sessionId), messages.slice(-120));
  }, [messages, sessionId]);

  useEffect(() => {
    saveJson(businessStorageKey(sessionId), businessHistory.slice(0, MAX_BUSINESS_HISTORY));
  }, [businessHistory, sessionId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ block: "end" });
  }, [messages]);

  useEffect(() => {
    let active = true;
    const stored = restoreMessages(sessionId);
    setMessages(stored.length ? stored : [WELCOME_MESSAGE]);
    setBusinessHistory(restoreBusinessHistory(sessionId));
    api
      .agentHistory(sessionId)
      .then((data) => {
        if (!active) return;
        if (Array.isArray(data.history) && data.history.length) {
          setMessages(historyToMessages(data.history));
        }
        if (data.session) {
          setSessionSnapshot(data.session);
          setConfirmOpen(isConfirmablePending(data.session));
        }
      })
      .catch((err) => {
        if (active) setError(err instanceof Error ? err.message : "会话历史加载失败");
      });
    return () => {
      active = false;
    };
  }, [sessionId]);

  useEffect(() => {
    summaryMountedRef.current = true;
    void refreshSummary(true);
    const timer = window.setInterval(() => {
      if (!document.hidden) void refreshSummary(false);
    }, DASHBOARD_SUMMARY_REFRESH_MS);
    const refreshOnFocus = () => {
      void refreshSummary(false);
    };
    const refreshOnVisibility = () => {
      if (!document.hidden) void refreshSummary(false);
    };
    window.addEventListener("focus", refreshOnFocus);
    document.addEventListener("visibilitychange", refreshOnVisibility);
    return () => {
      summaryMountedRef.current = false;
      window.clearInterval(timer);
      window.removeEventListener("focus", refreshOnFocus);
      document.removeEventListener("visibilitychange", refreshOnVisibility);
    };
  }, []);

  useEffect(() => {
    let active = true;
    setHotProductsLoading(true);
    api.analyticsHotProducts({ period: "7d", limit: 5 })
      .then((data) => {
        if (active) setHotProducts(data.items || []);
      })
      .catch(() => {
        if (active) setHotProducts([]);
      })
      .finally(() => {
        if (active) setHotProductsLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const pendingRows = useMemo(() => flattenState(sessionSnapshot?.state || {}).slice(0, 8), [sessionSnapshot]);

  function appendMessage(role: ChatRole, content: string, status?: ChatMessage["status"]) {
    const id = newMessageId(role);
    setMessages((current) => [
      ...current,
      {
        id,
        role,
        content,
        status,
        createdAt: new Date().toISOString()
      }
    ]);
    return id;
  }

  function updateMessage(id: string, content: string, status?: ChatMessage["status"]) {
    setMessages((current) =>
      current.map((message) => (message.id === id ? { ...message, content, status } : message))
    );
  }

  function openResultDialog(item: BusinessHistoryItem) {
    if (shouldOpenResultDialog(item)) {
      setResultDialog(resultFromHistory(item));
    }
  }

  function pushBusinessHistory(
    response: string,
    nextSession?: AgentSessionSnapshot | null,
    source: ResultSource = "text",
    extras: BusinessHistoryExtras = {}
  ) {
    const item = buildHistoryItem(response, nextSession, source, extras);
    setBusinessHistory((current) => {
      const rest = item.businessKey ? current.filter((row) => row.businessKey !== item.businessKey) : current;
      return [item, ...rest].slice(0, MAX_BUSINESS_HISTORY);
    });
    return item;
  }

  async function sendTextMessage(message: string) {
    const pendingId = appendMessage("assistant", "正在处理中...", "sending");
    const data = await api.agentChat({ message, session_id: sessionId, user_id: "web_user" });
    const responseText = data.response || "已处理";
    updateMessage(pendingId, responseText);
    const nextSession = data.session || null;
    setSessionSnapshot(nextSession);
    if (isConfirmablePending(nextSession)) {
      setConfirmOpen(true);
    } else {
      setConfirmOpen(false);
      const inventoryLookup = await loadInventoryLookupForMessage(message, responseText, nextSession);
      const inventoryResult = inventoryLookup ? null : await loadInventoryCardsForMessage(message, responseText, nextSession);
      const historyItem = pushBusinessHistory(responseText, nextSession, "text", {
        inventoryCards: inventoryResult?.list || [],
        inventoryLookup,
        inventorySource: inventoryLookup?.source || inventoryResult?.source
      });
      openResultDialog(historyItem);
    }
    void refreshSummary(false);
  }

  async function uploadImageFile(file: File) {
    const userMessageId = appendMessage("user", `上传图片：${file.name || "图片"}`);
    const pendingId = appendMessage("assistant", "正在识别图片...", "sending");
    const data = await api.uploadAgentImage(file, sessionId);
    const previewUrl = data.result?.preview_url;
    const responseText = data.response || "图片已识别";
    const displayText = previewUrl ? `${responseText}\n${previewUrl}` : responseText;
    if (previewUrl) {
      updateMessage(userMessageId, `上传图片：${file.name || "图片"}\n${previewUrl}`);
    }
    updateMessage(pendingId, displayText);
    const nextSession = data.session || null;
    setSessionSnapshot(nextSession);
    if (isConfirmablePending(nextSession)) {
      setConfirmOpen(true);
    } else {
      const historyItem = pushBusinessHistory(displayText, nextSession, "image");
      openResultDialog(historyItem);
    }
    void refreshSummary(false);
  }

  async function sendMessage(explicitText?: string) {
    if (isSending) return;
    const message = (explicitText ?? input).trim();
    const uploadFiles = [...files];
    if (!message && !uploadFiles.length) return;
    setError("");
    setInput("");
    setFiles([]);
    setIsSending(true);
    try {
      for (const file of uploadFiles) {
        await uploadImageFile(file);
      }
      if (message) {
        appendMessage("user", message);
        await sendTextMessage(message);
      }
    } catch (err) {
      const text = err instanceof Error ? err.message : "处理失败";
      setError(text);
      appendMessage("assistant", `处理失败：${text}`, "error");
    } finally {
      setIsSending(false);
    }
  }

  async function confirmPending(nextState: Record<string, unknown>) {
    setConfirming(true);
    try {
      const data = await api.updateSessionPending(sessionId, nextState);
      setSessionSnapshot(data.session);
      setConfirmOpen(false);
      await sendMessage("确认");
    } catch (err) {
      setError(err instanceof Error ? err.message : "确认失败");
    } finally {
      setConfirming(false);
    }
  }

  async function cancelPending() {
    setConfirmOpen(false);
    await sendMessage("取消");
  }

  function createNewSession() {
    const next = newSessionId();
    setSessionId(next);
    setSessionSnapshot(null);
    setResultDialog(null);
    setInput("");
    setFiles([]);
    setConfirmOpen(false);
  }

  function chooseFiles(event: ChangeEvent<HTMLInputElement>) {
    const selected = Array.from(event.target.files || []).filter((file) => file.type.startsWith("image/"));
    setFiles((current) => [...current, ...selected].slice(0, 6));
    event.target.value = "";
  }

  function removeFile(index: number) {
    setFiles((current) => current.filter((_, itemIndex) => itemIndex !== index));
  }

  function insertCommand(command: string) {
    if (command === "上传泡袋") {
      void sendMessage("上传泡袋");
      return;
    }
    setInput((current) => {
      const clean = current.trim();
      const prefixPattern = /^(开单|查库存|进货|调货|盘点|工作流)\b/;
      return clean ? (prefixPattern.test(clean) ? clean.replace(prefixPattern, command) : `${command} ${clean}`) : `${command} `;
    });
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void sendMessage();
    }
  }

  function handlePaste(event: ClipboardEvent<HTMLInputElement>) {
    const pasted = Array.from(event.clipboardData.files || []).filter((file) => file.type.startsWith("image/"));
    if (pasted.length) setFiles((current) => [...current, ...pasted].slice(0, 6));
  }

  return (
    <section
      className="workbench-page"
      onDragOver={(event) => event.preventDefault()}
      onDrop={(event) => {
        event.preventDefault();
        const dropped = Array.from(event.dataTransfer.files || []).filter((file) => file.type.startsWith("image/"));
        if (dropped.length) setFiles((current) => [...current, ...dropped].slice(0, 6));
      }}
    >
      {error ? <div className="form-error">{error}</div> : null}
      <WorkbenchStatusStrip summary={summary} loading={summaryLoading} session={sessionSnapshot} />
      <div className="workbench-shell">
        <ConversationPanel
          messages={messages}
          files={files}
          input={input}
          isSending={isSending}
          messagesEndRef={messagesEndRef}
          fileInputRef={fileInputRef}
          onInput={setInput}
          onSend={() => void sendMessage()}
          onKeyDown={handleKeyDown}
          onPaste={handlePaste}
          onChooseFiles={chooseFiles}
          onRemoveFile={removeFile}
          onInsertCommand={insertCommand}
          onNewSession={createNewSession}
        />
        <BusinessContextPanel
          history={businessHistory}
          session={sessionSnapshot}
          pendingRows={pendingRows}
          hotProducts={hotProducts}
          hotProductsLoading={hotProductsLoading}
          onOpenPending={() => setConfirmOpen(true)}
          onCancelPending={() => void cancelPending()}
          onOpenHistory={(item) => setResultDialog(resultFromHistory(item))}
          onNewSession={createNewSession}
        />
      </div>
      <WorkbenchResultDialog result={resultDialog} onOpenChange={(open) => !open && setResultDialog(null)} />
      <AgentConfirmDialog
        open={confirmOpen}
        session={sessionSnapshot}
        confirming={confirming || isSending}
        onOpenChange={setConfirmOpen}
        onConfirm={(state) => void confirmPending(state)}
        onCancel={() => void cancelPending()}
      />
    </section>
  );
}

function WorkbenchStatusStrip({
  summary,
  loading,
  session
}: {
  summary: DashboardSummary | null;
  loading: boolean;
  session: AgentSessionSnapshot | null;
}) {
  const cards = [
    { label: "今日销售单", value: summary ? `${summary.today_sales_count} 张` : "--" },
    { label: "今日销售额", value: summary ? `¥${summary.today_sales_amount}` : "--" },
    { label: "待完成订单", value: summary ? `${summary.pending_workflow_count} 单` : "--" },
    { label: "当前会话", value: session?.has_pending ? "待确认" : "可对话" }
  ];
  return (
    <div className="workbench-status-strip">
      {cards.map((card) => (
        <Card size="sm" key={card.label} className="workbench-status-card">
          <CardContent>
            <span>{card.label}</span>
            {loading && card.label !== "当前会话" ? <Skeleton className="workbench-status-skeleton" /> : <strong>{card.value}</strong>}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function ConversationPanel({
  messages,
  files,
  input,
  isSending,
  messagesEndRef,
  fileInputRef,
  onInput,
  onSend,
  onKeyDown,
  onPaste,
  onChooseFiles,
  onRemoveFile,
  onInsertCommand,
  onNewSession
}: {
  messages: ChatMessage[];
  files: File[];
  input: string;
  isSending: boolean;
  messagesEndRef: React.RefObject<HTMLDivElement | null>;
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  onInput: (value: string) => void;
  onSend: () => void;
  onKeyDown: (event: KeyboardEvent<HTMLInputElement>) => void;
  onPaste: (event: ClipboardEvent<HTMLInputElement>) => void;
  onChooseFiles: (event: ChangeEvent<HTMLInputElement>) => void;
  onRemoveFile: (index: number) => void;
  onInsertCommand: (command: string) => void;
  onNewSession: () => void;
}) {
  return (
    <Card className="workbench-panel conversation-panel">
      <CardHeader>
        <div>
          <CardTitle>AI 业务工作台</CardTitle>
          <CardDescription>开单、查库存、改订单、进货调货，都从这里开始。</CardDescription>
        </div>
        <CardAction>
          <div className="workbench-head-actions">
            <Badge variant="outline">
              <Sparkles data-icon="inline-start" />
              智能体在线
            </Badge>
            <Button variant="outline" size="sm" onClick={onNewSession}>
              <MessageSquarePlus data-icon="inline-start" />
              新会话
            </Button>
          </div>
        </CardAction>
      </CardHeader>
      <CardContent className="conversation-content">
        <MessageList messages={messages} messagesEndRef={messagesEndRef} />
      </CardContent>
      <CardFooter className="conversation-footer">
        <CommandStrip onInsertCommand={onInsertCommand} />
        <ChatComposer
          input={input}
          files={files}
          isSending={isSending}
          fileInputRef={fileInputRef}
          onInput={onInput}
          onSend={onSend}
          onKeyDown={onKeyDown}
          onPaste={onPaste}
          onChooseFiles={onChooseFiles}
          onRemoveFile={onRemoveFile}
        />
      </CardFooter>
    </Card>
  );
}

function MessageList({
  messages,
  messagesEndRef
}: {
  messages: ChatMessage[];
  messagesEndRef: React.RefObject<HTMLDivElement | null>;
}) {
  return (
    <ScrollArea className="workbench-message-scroll">
      <div className="workbench-messages">
        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}
        <div ref={messagesEndRef} />
      </div>
    </ScrollArea>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const lines = message.content.split(/\r?\n/);
  return (
    <div className={`workbench-message workbench-message--${message.role}`} data-role={message.role}>
      <div className="workbench-message-bubble">
        {message.status === "sending" ? <Loader2 className="workbench-spin" data-icon="inline-start" /> : null}
        {lines.map((line, index) =>
          isImageLine(line) ? (
            <img className="workbench-message-image" src={line.trim()} alt="上传图片" key={`${line}_${index}`} />
          ) : (
            <p key={`${line}_${index}`}>{line || " "}</p>
          )
        )}
      </div>
      <span className="workbench-message-meta">{message.role === "user" ? "你" : "北极星"} · {formatTime(message.createdAt)}</span>
    </div>
  );
}

function CommandStrip({ onInsertCommand }: { onInsertCommand: (command: string) => void }) {
  return (
    <div className="workbench-command-strip" aria-label="快捷指令">
      {COMMANDS.map((command) => (
        <Button variant="outline" size="sm" key={command} onClick={() => onInsertCommand(command)}>
          {command}
        </Button>
      ))}
    </div>
  );
}

function ChatComposer({
  input,
  files,
  isSending,
  fileInputRef,
  onInput,
  onSend,
  onKeyDown,
  onPaste,
  onChooseFiles,
  onRemoveFile
}: {
  input: string;
  files: File[];
  isSending: boolean;
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  onInput: (value: string) => void;
  onSend: () => void;
  onKeyDown: (event: KeyboardEvent<HTMLInputElement>) => void;
  onPaste: (event: ClipboardEvent<HTMLInputElement>) => void;
  onChooseFiles: (event: ChangeEvent<HTMLInputElement>) => void;
  onRemoveFile: (index: number) => void;
}) {
  return (
    <div className="workbench-composer">
      {files.length ? (
        <div className="workbench-attachment-list">
          {files.map((file, index) => (
            <Badge variant="secondary" key={`${file.name}_${index}`}>
              <ImageIcon data-icon="inline-start" />
              {file.name || "图片"}
              <button className="workbench-attachment-remove" type="button" onClick={() => onRemoveFile(index)} aria-label="移除图片">
                <X />
              </button>
            </Badge>
          ))}
        </div>
      ) : null}
      <div className="workbench-composer-main">
        <input ref={fileInputRef} className="workbench-file-input" type="file" accept="image/*" multiple onChange={onChooseFiles} />
        <Button variant="outline" size="icon" onClick={() => fileInputRef.current?.click()} aria-label="上传图片">
          <Paperclip data-icon="icon" />
        </Button>
        <Input
          className="workbench-chat-input"
          value={input}
          onChange={(event) => onInput(event.target.value)}
          onKeyDown={onKeyDown}
          onPaste={onPaste}
          placeholder="输入业务指令，或粘贴订单图片"
        />
        <Button onClick={onSend} disabled={isSending || (!input.trim() && !files.length)}>
          {isSending ? <Loader2 className="workbench-spin" data-icon="inline-start" /> : <Send data-icon="inline-start" />}
          发送
        </Button>
      </div>
    </div>
  );
}

function PendingStatusCard({
  session,
  rows,
  onOpenConfirm,
  onCancelPending
}: {
  session: AgentSessionSnapshot;
  rows: PendingField[];
  onOpenConfirm: () => void;
  onCancelPending: () => void;
}) {
  return (
    <div className="pending-status-card">
      <div className="pending-status-head">
        <div>
          <strong>{pendingTitle(session)}</strong>
          <span>结构化确认后才会写入系统。</span>
        </div>
        <Badge variant="secondary">{session.pending_intent || "pending"}</Badge>
      </div>
      <div className="pending-field-list">
        {rows.length ? (
          rows.map((row) => (
            <div className="pending-field-row" key={row.path}>
              <span>{row.label}</span>
              <strong>{valueLabel(row.value, row.path)}</strong>
            </div>
          ))
        ) : (
          <div className="pending-field-row">
            <span>状态</span>
            <strong>等待确认</strong>
          </div>
        )}
      </div>
      <div className="pending-status-actions">
        <Button variant="outline" onClick={onCancelPending}>
          取消
        </Button>
        <Button onClick={onOpenConfirm}>
          <Check data-icon="inline-start" />
          打开确认
        </Button>
      </div>
    </div>
  );
}

function BusinessContextPanel({
  history,
  session,
  pendingRows,
  hotProducts,
  hotProductsLoading,
  onOpenPending,
  onCancelPending,
  onOpenHistory,
  onNewSession
}: {
  history: BusinessHistoryItem[];
  session: AgentSessionSnapshot | null;
  pendingRows: PendingField[];
  hotProducts: AnalyticsHotProduct[];
  hotProductsLoading: boolean;
  onOpenPending: () => void;
  onCancelPending: () => void;
  onOpenHistory: (item: BusinessHistoryItem) => void;
  onNewSession: () => void;
}) {
  return (
    <Card className="workbench-panel business-context-panel">
      <CardHeader>
        <div>
          <CardTitle>最近业务记录</CardTitle>
          <CardDescription>待确认动作和当前会话最近 5 条结果。</CardDescription>
        </div>
        <CardAction>
          <Button variant="outline" size="icon-sm" onClick={onNewSession} aria-label="新会话">
            <RefreshCw data-icon="icon" />
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent>
        {session?.has_pending ? (
          <PendingStatusCard
            session={session}
            rows={pendingRows}
            onOpenConfirm={onOpenPending}
            onCancelPending={onCancelPending}
          />
        ) : null}
        <HotProductsMiniPanel products={hotProducts} loading={hotProductsLoading} />
        <div className="business-history-list">
          {history.length ? (
            history.map((item) => (
              <Card size="sm" key={item.id} className="business-history-card">
                <CardHeader>
                  <div>
                    <CardTitle>{item.title}</CardTitle>
                    <CardDescription>{formatTime(item.createdAt)}</CardDescription>
                  </div>
                  <Badge variant="outline">{item.label}</Badge>
                </CardHeader>
                <CardContent>
                  <p>{item.summary}</p>
                </CardContent>
                <CardFooter>
                  <Button variant="outline" size="sm" onClick={() => onOpenHistory(item)}>
                    查看
                  </Button>
                </CardFooter>
              </Card>
            ))
          ) : (
            <Empty className="business-history-empty">
              <EmptyContent>
                <History />
                <EmptyTitle>暂无记录</EmptyTitle>
                <EmptyDescription>查询、开单、工作流处理后会自动记录。</EmptyDescription>
              </EmptyContent>
            </Empty>
          )}
        </div>
      </CardContent>
      <CardFooter className="business-session-footer">
        <Badge variant="ghost">
          <Bot data-icon="inline-start" />
          {session?.has_pending ? "当前有待确认操作" : "当前无待确认操作"}
        </Badge>
      </CardFooter>
    </Card>
  );
}

function HotProductsMiniPanel({
  products,
  loading
}: {
  products: AnalyticsHotProduct[];
  loading: boolean;
}) {
  return (
    <section className="workbench-hot-products">
      <header>
        <div>
          <strong>7 天热销</strong>
          <span>按商品聚合</span>
        </div>
        <Badge variant="outline">TOP {Math.max(products.length, loading ? 5 : 0)}</Badge>
      </header>
      {loading ? (
        <div className="workbench-hot-list">
          {Array.from({ length: 5 }, (_, index) => <Skeleton key={index} />)}
        </div>
      ) : products.length ? (
        <div className="workbench-hot-list">
          {products.map((product) => (
            <div className="workbench-hot-row" key={`${product.rank}-${product.product_id}-${product.sku_id}`}>
              <span>{product.rank}</span>
              <div>
                <strong>{product.title}</strong>
                <em>{product.color || product.sku_no || "默认规格"}</em>
              </div>
              <b>{product.sold_qty} 件</b>
            </div>
          ))}
        </div>
      ) : (
        <p>最近 7 天还没有可统计的销售商品。</p>
      )}
    </section>
  );
}

function WorkbenchResultDialog({
  result,
  onOpenChange
}: {
  result: WorkbenchResult | null;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Dialog open={Boolean(result)} onOpenChange={onOpenChange}>
      {result ? (
        <DialogContent className="workbench-result-dialog">
          <DialogHeader>
            <DialogTitle>{result.title}</DialogTitle>
            <DialogDescription>
              {result.label} · {formatTime(result.createdAt)}
            </DialogDescription>
          </DialogHeader>
          {result.type === "inventory" ? (
            <InventoryResultDialog result={result} />
          ) : result.type === "image" ? (
            <ImageOcrResultDialog result={result} />
          ) : (
            <AgentResultDialog result={result} />
          )}
          <DialogFooter>
            <Button onClick={() => onOpenChange(false)}>关闭</Button>
          </DialogFooter>
        </DialogContent>
      ) : null}
    </Dialog>
  );
}

function AgentResultDialog({ result }: { result: WorkbenchResult }) {
  return (
    <div className="agent-result-dialog workbench-result-body">
      <div className="workbench-result-summary">
        <Badge variant="outline">{result.title}</Badge>
        <p>{result.summary}</p>
      </div>
      <ResultLineTable response={result.response} />
    </div>
  );
}

function InventoryResultDialog({ result }: { result: WorkbenchResult }) {
  const cards = result.inventoryCards || [];
  const lookup = result.inventoryLookup || null;
  return (
    <div className="inventory-result-dialog workbench-result-body">
      <div className="workbench-result-summary">
        <Badge>库存查询结果</Badge>
        <p>{result.summary}</p>
      </div>
      {lookup ? (
        <InventoryLookupTable lookup={lookup} />
      ) : cards.length ? (
        <InventoryCardGrid cards={cards} />
      ) : (
        <ResultLineTable response={result.response} />
      )}
    </div>
  );
}

function ImageOcrResultDialog({ result }: { result: WorkbenchResult }) {
  return (
    <div className="image-ocr-result-dialog workbench-result-body">
      <div className="workbench-result-summary">
        <Badge variant="secondary">图片识别结果</Badge>
        <p>{result.summary}</p>
      </div>
      <ResultLineTable response={result.response} />
    </div>
  );
}

function ResultLineTable({ response }: { response: string }) {
  const lines = response.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  return (
    <ScrollArea className="workbench-result-scroll">
      <div className="workbench-result-table">
        {lines.length ? (
          lines.map((line, index) =>
            isImageLine(line) ? (
              <img className="workbench-result-image" src={line} alt="图片识别预览" key={`${line}_${index}`} />
            ) : (
              <div className="workbench-result-row" key={`${line}_${index}`}>
                <span>{index + 1}</span>
                <p>{line}</p>
              </div>
            )
          )
        ) : (
          <div className="workbench-result-row">
            <span>1</span>
            <p>暂无结果内容</p>
          </div>
        )}
      </div>
    </ScrollArea>
  );
}

function inventoryQuantityText(value: unknown) {
  const numberValue = Number(value || 0);
  if (!Number.isFinite(numberValue)) return "0";
  return String(Number(numberValue.toFixed(3))).replace(/\.0+$/, "");
}

function inventoryLookupWarehousesFromRows(rows: WorkbenchInventoryLookupRow[]) {
  const names = new Set<string>();
  rows.forEach((row) => Object.keys(row.warehouses || {}).forEach((name) => names.add(name)));
  return Array.from(names).map((name) => ({ name }));
}

const DEFAULT_INVENTORY_LOOKUP_WAREHOUSES = [
  { id: 1, name: "自己店里" },
  { id: 2, name: "百鑫仓库" }
];

function inventoryLookupWarehouses(lookup: InventoryLookupResult, rows: WorkbenchInventoryLookupRow[]) {
  const source = lookup.warehouses?.length ? lookup.warehouses : inventoryLookupWarehousesFromRows(rows);
  if (lookup.warehouse_id !== undefined && lookup.warehouse_id !== null && lookup.warehouse_id !== "") {
    return source;
  }
  const merged = new Map<string, { id?: number | string | null; name: string }>();
  DEFAULT_INVENTORY_LOOKUP_WAREHOUSES.forEach((warehouse) => merged.set(warehouse.name, warehouse));
  source.forEach((warehouse) => merged.set(warehouse.name, warehouse));
  return Array.from(merged.values());
}

function inventoryLookupWarehouseName(lookup: InventoryLookupResult) {
  if (String(lookup.warehouse_id || "") === "1") return "自己店里";
  if (String(lookup.warehouse_id || "") === "2") return "百鑫仓库";
  return lookup.warehouses?.length === 1 ? lookup.warehouses[0].name : "";
}

function inventoryLookupEmptyTitle(lookup: InventoryLookupResult) {
  const warehouse = inventoryLookupWarehouseName(lookup);
  return warehouse ? `${warehouse}暂无匹配库存` : "没有匹配库存";
}

function InventoryLookupTable({ lookup }: { lookup: InventoryLookupResult }) {
  const rows = lookup.list || [];
  const warehouses = inventoryLookupWarehouses(lookup, rows);
  if (!rows.length) {
    return (
      <Empty className="workbench-inventory-lookup-empty">
        <EmptyHeader>
          <EmptyTitle>{inventoryLookupEmptyTitle(lookup)}</EmptyTitle>
          <EmptyDescription>当前查询没有找到对应的库存 SKU。</EmptyDescription>
        </EmptyHeader>
      </Empty>
    );
  }
  return (
    <ScrollArea className="workbench-result-scroll workbench-inventory-lookup-scroll">
      <table className="workbench-inventory-lookup-table">
        <thead>
          <tr>
            <th>商品/SKU</th>
            <th>颜色/规格</th>
            {warehouses.map((warehouse) => (
              <th key={warehouse.name}>{warehouse.name}</th>
            ))}
            <th>合计</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={`${row.product_id || row.sku_no || row.title}-${row.color || ""}`}>
              <td>
                <strong>{row.title}</strong>
                <span>{row.sku_no || "未编号"}</span>
              </td>
              <td>
                <strong>{row.color || "默认颜色"}</strong>
                <span>{row.piece_text || row.unit_name || "单位"}</span>
              </td>
              {warehouses.map((warehouse) => {
                const qty = Number(row.warehouses?.[warehouse.name] || 0);
                return (
                  <td key={`${row.product_id || row.sku_no}-${warehouse.name}`} className={qty === 0 ? "workbench-inventory-lookup-zero" : ""}>
                    {inventoryQuantityText(qty)}
                    <span>{row.unit_name || "套"}</span>
                  </td>
                );
              })}
              <td>
                <strong>{inventoryQuantityText(row.total_stock)}</strong>
                <span>{row.unit_name || "套"}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </ScrollArea>
  );
}

function orderedWarehouseEntries(warehouses: Record<string, number>) {
  const preferred = ["百鑫仓库", "店里仓库"];
  const entries = Object.entries(warehouses || {});
  const ordered = preferred
    .filter((name) => entries.some(([key]) => key === name))
    .map((name) => [name, warehouses[name]] as [string, number]);
  entries.forEach(([name, value]) => {
    if (!preferred.includes(name)) ordered.push([name, value]);
  });
  return ordered;
}

function InventoryCardGrid({ cards }: { cards: WorkbenchInventoryCard[] }) {
  return (
    <ScrollArea className="workbench-result-scroll workbench-inventory-card-scroll">
      <div className="workbench-inventory-card-grid">
        {cards.map((card) => {
          const colors = card.colors || [];
          return (
            <section key={`${card.product_id || card.title}-${card.title}`} className="workbench-inventory-card">
              <header>
                <div>
                  <h3>{card.title}</h3>
                  <span>{colors.length} 个颜色/SKU{card.piece_text ? ` · ${card.piece_text}` : ""}</span>
                </div>
                <Badge variant={Number(card.total_stock || 0) > 0 ? "outline" : "secondary"}>
                  合计 {inventoryQuantityText(card.total_stock)}
                </Badge>
              </header>
              <div className="workbench-inventory-color-list">
                {colors.length ? (
                  colors.map((color) => (
                    <div key={`${card.title}-${color.product_id || color.color}-${color.color}`} className="workbench-inventory-color-row">
                      <div className="workbench-inventory-color-name">
                        <strong>{color.color || "默认颜色"}</strong>
                        <span>合计 {inventoryQuantityText(color.total_stock)}</span>
                      </div>
                      <div className="workbench-inventory-warehouse-grid">
                        {orderedWarehouseEntries(color.warehouses).map(([warehouse, qty]) => (
                          <div key={`${color.color}-${warehouse}`}>
                            <span>{warehouse}</span>
                            <strong>{inventoryQuantityText(qty)}</strong>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="workbench-inventory-color-row">
                    <div className="workbench-inventory-color-name">
                      <strong>暂无颜色</strong>
                      <span>没有匹配库存记录</span>
                    </div>
                  </div>
                )}
              </div>
            </section>
          );
        })}
      </div>
    </ScrollArea>
  );
}

function AgentConfirmDialog({
  open,
  session,
  confirming,
  onOpenChange,
  onConfirm,
  onCancel
}: {
  open: boolean;
  session: AgentSessionSnapshot | null;
  confirming: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: (state: Record<string, unknown>) => void;
  onCancel: () => void;
}) {
  const sections = useMemo(() => buildConfirmSections(session), [session]);
  const fields = useMemo(() => sections.flatMap((section) => section.fields), [sections]);
  const fieldKey = fields.map((field) => field.path).join("|");
  const stateKey = JSON.stringify(session?.state || {});
  const [values, setValues] = useState<Record<string, string>>({});

  useEffect(() => {
    const next = Object.fromEntries(fields.map((field) => [field.path, displayConfirmValue(field)]));
    setValues(next);
  }, [stateKey, fieldKey]);

  function submit() {
    const nextState = cloneState(session?.state);
    fields.forEach((field) => {
      const nextValue = values[field.path] ?? "";
      const originalDisplay = displayConfirmValue(field);
      if (nextValue !== String(field.value ?? "") && nextValue !== originalDisplay) {
        setValueByPath(nextState, field.path, coerceConfirmValue(nextValue, field));
      }
    });
    onConfirm(nextState);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="workbench-confirm-dialog">
        <DialogHeader>
          <DialogTitle>{pendingTitle(session)}</DialogTitle>
          <DialogDescription>结构化确认：可以先改字段，再点确认执行。关闭弹窗不会取消当前 pending。</DialogDescription>
        </DialogHeader>
        {fields.length ? (
          <ScrollArea className="workbench-confirm-scroll">
            <div className="confirm-section-list">
              {sections.map((section) => (
                <ConfirmSectionEditor
                  key={section.title}
                  section={section}
                  values={values}
                  onValueChange={(path, value) => setValues((current) => ({ ...current, [path]: value }))}
                />
              ))}
            </div>
          </ScrollArea>
        ) : (
          <Empty>
            <EmptyHeader>
              <EmptyTitle>没有可编辑字段</EmptyTitle>
              <EmptyDescription>可直接确认，按聊天内容继续执行。</EmptyDescription>
            </EmptyHeader>
          </Empty>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={onCancel} disabled={confirming}>
            取消
          </Button>
          <Button onClick={submit} disabled={confirming}>
            {confirming ? <Loader2 className="workbench-spin" data-icon="inline-start" /> : <Check data-icon="inline-start" />}
            确认执行
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function ConfirmSectionEditor({
  section,
  values,
  onValueChange
}: {
  section: ConfirmSection;
  values: Record<string, string>;
  onValueChange: (path: string, value: string) => void;
}) {
  return (
    <section className="confirm-section-card">
      <div className="confirm-section-title">
        <strong>{section.title}</strong>
        {section.description ? <span>{section.description}</span> : null}
      </div>
      <FieldGroup className="confirm-field-grid">
        {section.fields.map((field) => (
          <Field key={field.path}>
            <FieldLabel>{field.label}</FieldLabel>
            <Input
              value={values[field.path] ?? ""}
              inputMode={field.inputMode}
              readOnly={field.readOnly}
              onChange={(event) => onValueChange(field.path, event.target.value)}
            />
          </Field>
        ))}
      </FieldGroup>
    </section>
  );
}
