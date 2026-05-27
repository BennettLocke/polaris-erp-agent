import { useEffect, useMemo, useState, type KeyboardEvent } from "react";
import {
  ChevronLeft,
  ChevronRight,
  CheckCircle2,
  ClipboardList,
  Eye,
  ImageIcon,
  MoreHorizontal,
  PackageCheck,
  Plus,
  RefreshCw,
  Search,
  Truck
} from "lucide-react";

import { api, type ProcessOrderListQuery } from "@/api";
import { Toolbar } from "@/components/layout/toolbar";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle
} from "@/components/ui/alert-dialog";
import { Badge, type BadgeVariant } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
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
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuTrigger
} from "@/components/ui/dropdown-menu";
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import type {
  ProcessOrder,
  ProcessOrderPayload,
  ProcessOrderRaw,
  ProcessOrderStatusPayload
} from "@/types";

type OrdersView = "board" | "table";
type ProcessOrderFilter = NonNullable<ProcessOrderListQuery["filter"]>;
type OrderStatusField = ProcessOrderStatusPayload["field"];
type OrderFormState = {
  customerName: string;
  customerPhone: string;
  goodsName: string;
  color: string;
  quantity: string;
  screenPrint: boolean;
  completed: boolean;
  remark: string;
};
type OrderStatusGroup = {
  key: "unmade" | "delivery" | "completed";
  title: string;
  description: string;
  orders: ProcessOrder[];
};
type OrderImagePreview = {
  order: ProcessOrder;
  index: number;
} | null;

const ORDER_PAGE_SIZE = 120;
const RECENT_COMPLETED_DAYS = 7;
const GROUP_PAGE_SIZE = 8;

const orderFilters: Array<{ value: ProcessOrderFilter; label: string; hint: string }> = [
  { value: "active", label: "进行中", hint: "默认" },
  { value: "pending", label: "待处理", hint: "制作或配送未完" },
  { value: "unmade", label: "未制作", hint: "制作优先" },
  { value: "all", label: "全部", hint: "含完成" }
];

const emptyForm: OrderFormState = {
  customerName: "",
  customerPhone: "",
  goodsName: "",
  color: "",
  quantity: "1",
  screenPrint: false,
  completed: false,
  remark: ""
};

function textValue(value: unknown, fallback = "") {
  if (value === null || value === undefined) return fallback;
  const text = String(value).trim();
  return text || fallback;
}

function numericValue(value: unknown, fallback = 0) {
  if (value === null || value === undefined || value === "") return fallback;
  const parsed = Number(String(value).replace(/,/g, ""));
  return Number.isFinite(parsed) ? parsed : fallback;
}

function boolValue(value: unknown) {
  return value === true || Number(value || 0) === 1 || value === "1";
}

function parseOrderImages(order_images: ProcessOrderRaw["order_images"]) {
  if (!order_images) return [];
  if (Array.isArray(order_images)) return order_images.map((item) => String(item || "").trim()).filter(Boolean);
  const raw = String(order_images || "").trim();
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw) as unknown;
    if (Array.isArray(parsed)) return parsed.map((item) => String(item || "").trim()).filter(Boolean);
    if (typeof parsed === "string") return parsed ? [parsed] : [];
  } catch {
    // Historical rows may store comma separated URLs instead of JSON.
  }
  return raw.split(",").map((item) => item.trim()).filter(Boolean);
}

function normalizeProcessOrder(raw: ProcessOrderRaw): ProcessOrder {
  const orderType = Number(raw.order_type || 0);
  const completed = orderType === 1 || raw.status === "completed";
  const made = boolValue(raw.is_made);
  const delivered = boolValue(raw.is_delivered);
  const fallbackStatus = completed ? "已完成" : made && !delivered ? "待配送" : made ? "进行中" : "待制作";
  return {
    id: Number(raw.id || raw.order_id || 0),
    raw,
    customerName: textValue(raw.customer_name, "未记录客户"),
    customerPhone: textValue(raw.customer_phone),
    goodsName: textValue(raw.goods_name, "未记录商品"),
    color: textValue(raw.goods_color || raw.color, "未记录颜色"),
    quantity: Math.max(0, numericValue(raw.order_quantity, 1)),
    screenPrint: boolValue(raw.is_screen_print),
    made,
    delivered,
    completed,
    statusText: textValue(raw.status_text, fallbackStatus),
    orderTimeText: textValue(raw.order_time_text, "未记录时间"),
    completeTimeText: textValue(raw.complete_time_text),
    imageUrls: parseOrderImages(raw.order_images),
    creatorName: textValue(raw.created_by_name, "未记录"),
    remark: textValue(raw.remark)
  };
}

function parseOrderDateText(value: string) {
  const text = value.trim();
  if (!text || text === "未记录时间") return null;
  const normalized = text.length <= 10 ? `${text}T00:00:00` : text.replace(" ", "T");
  const date = new Date(normalized);
  return Number.isNaN(date.getTime()) ? null : date;
}

function isRecentCompletedOrder(order: ProcessOrder, now = new Date()) {
  if (!order.completed && !(order.made && order.delivered)) return false;
  const completedAt = parseOrderDateText(order.completeTimeText || order.orderTimeText);
  if (!completedAt) return false;
  const start = new Date(now);
  start.setHours(0, 0, 0, 0);
  start.setDate(start.getDate() - RECENT_COMPLETED_DAYS + 1);
  return completedAt >= start && completedAt <= now;
}

function groupOrdersByStatus(orders: ProcessOrder[]): OrderStatusGroup[] {
  const unmade: ProcessOrder[] = [];
  const delivery: ProcessOrder[] = [];
  const completed: ProcessOrder[] = [];

  orders.forEach((order) => {
    if (isRecentCompletedOrder(order)) completed.push(order);
    else if (order.completed || (order.made && order.delivered)) return;
    else if (!order.made) unmade.push(order);
    else delivery.push(order);
  });

  const groups: OrderStatusGroup[] = [
    { key: "unmade", title: "待制作", description: "先处理未制作的订单", orders: unmade },
    { key: "delivery", title: "待配送", description: "已制作但还没配送", orders: delivery },
    { key: "completed", title: "最近完成", description: "只看最近 7 天完成", orders: completed }
  ];
  return groups;
}

function statusVariant(order: ProcessOrder): BadgeVariant {
  if (order.completed) return "secondary";
  if (!order.made) return "destructive";
  if (!order.delivered) return "outline";
  return "ghost";
}

function statusLabel(order: ProcessOrder) {
  if (order.completed) return "已完成";
  if (!order.made) return "待制作";
  if (!order.delivered) return "待配送";
  return order.statusText || "进行中";
}

function formFromOrder(order: ProcessOrder | null): OrderFormState {
  if (!order) return emptyForm;
  return {
    customerName: order.customerName === "未记录客户" ? "" : order.customerName,
    customerPhone: order.customerPhone,
    goodsName: order.goodsName === "未记录商品" ? "" : order.goodsName,
    color: order.color === "未记录颜色" ? "" : order.color,
    quantity: String(order.quantity || 1),
    screenPrint: order.screenPrint,
    completed: order.completed,
    remark: order.remark
  };
}

function payloadFromForm(form: OrderFormState, order?: ProcessOrder | null): ProcessOrderPayload {
  return {
    order_id: order?.id || undefined,
    customer_name: form.customerName.trim(),
    customer_phone: form.customerPhone.trim(),
    goods_name: form.goodsName.trim(),
    color: form.color.trim(),
    order_quantity: Math.max(1, numericValue(form.quantity, 1)),
    is_screen_print: form.screenPrint ? 1 : 0,
    order_type: form.completed ? 1 : 0,
    order_images: order?.imageUrls || [],
    remark: form.remark.trim()
  };
}

function primaryImageUrl(order: ProcessOrder) {
  return order.imageUrls[0] || "";
}

function OrderThumbnail({
  compact = false,
  order,
  onClick
}: {
  compact?: boolean;
  order: ProcessOrder;
  onClick?: () => void;
}) {
  const imageUrl = primaryImageUrl(order);
  const extraCount = Math.max(0, order.imageUrls.length - 1);
  return (
    <div
      className={compact ? "process-order-thumbnail process-order-thumbnail--compact orders-table-thumb" : "process-order-thumbnail"}
      role={onClick ? "button" : "img"}
      tabIndex={onClick ? 0 : undefined}
      aria-label={`${order.goodsName}图片`}
      onClick={(event) => {
        event.stopPropagation();
        onClick?.();
      }}
      onKeyDown={(event) => {
        if (!onClick) return;
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          event.stopPropagation();
          onClick();
        }
      }}
    >
      {imageUrl ? (
        <img src={imageUrl} alt={`${order.goodsName}订单图片`} loading="lazy" />
      ) : (
        <div className="process-order-thumbnail-empty">
          <ImageIcon />
        </div>
      )}
      {extraCount > 0 ? <span className="process-order-thumbnail-count">+{extraCount}</span> : null}
    </div>
  );
}

function OrdersSummaryStrip({ orders, total }: { orders: ProcessOrder[]; total: number }) {
  const summary = useMemo(() => ({
    unmade: orders.filter((order) => !order.completed && !order.made).length,
    delivery: orders.filter((order) => !order.completed && order.made && !order.delivered).length,
    completed: orders.filter((order) => order.completed).length,
    screenPrint: orders.filter((order) => order.screenPrint).length
  }), [orders]);
  return (
    <div className="orders-summary-strip">
      <Card size="sm">
        <CardContent>
          <span>订单</span>
          <strong>{total}</strong>
        </CardContent>
      </Card>
      <Card size="sm">
        <CardContent>
          <span>本页待制作</span>
          <strong>{summary.unmade}</strong>
        </CardContent>
      </Card>
      <Card size="sm">
        <CardContent>
          <span>本页待配送</span>
          <strong>{summary.delivery}</strong>
        </CardContent>
      </Card>
      <Card size="sm">
        <CardContent>
          <span>本页完成</span>
          <strong>{summary.completed}</strong>
        </CardContent>
      </Card>
      <Card size="sm">
        <CardContent>
          <span>丝印</span>
          <strong>{summary.screenPrint}</strong>
        </CardContent>
      </Card>
    </div>
  );
}

function OrderNotice({ notice }: { notice: string }) {
  if (!notice) return null;
  return (
    <div className="orders-toast-viewport" aria-live="polite" aria-atomic="true">
      <div className="orders-toast" role="status">
        <span>操作提示</span>
        <strong>{notice}</strong>
      </div>
    </div>
  );
}

type OrderActions = {
  busyOrderId: number | null;
  onStatusChange: (order: ProcessOrder, field: OrderStatusField, checked: boolean) => void;
  onOpenDetail: (order: ProcessOrder) => void;
  onOpenImages: (order: ProcessOrder, index?: number) => void;
  onEdit: (order: ProcessOrder) => void;
  onDelete: (order: ProcessOrder) => void;
};

function OrderStatusSwitch({
  checked,
  disabled,
  icon: Icon,
  label,
  onCheckedChange
}: {
  checked: boolean;
  disabled: boolean;
  icon: typeof PackageCheck;
  label: string;
  onCheckedChange: (checked: boolean) => void;
}) {
  return (
    <label className="order-status-switch">
      <span>
        <Icon />
        {label}
      </span>
      <Switch checked={checked} disabled={disabled} onCheckedChange={onCheckedChange} aria-label={label} />
    </label>
  );
}

function ProcessOrderCard({
  order,
  busyOrderId,
  onStatusChange,
  onOpenDetail,
  onOpenImages,
  onEdit,
  onDelete
}: { order: ProcessOrder } & OrderActions) {
  const busy = busyOrderId === order.id;
  function openDetailFromKeyboard(event: KeyboardEvent) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onOpenDetail(order);
    }
  }

  return (
    <Card size="sm" className="process-order-card">
      <CardHeader
        className="process-order-card-click-zone"
        role="button"
        tabIndex={0}
        onClick={() => onOpenDetail(order)}
        onKeyDown={openDetailFromKeyboard}
      >
        <div className="process-order-card-title">
          <CardTitle>{order.customerName}</CardTitle>
          <Badge variant={statusVariant(order)}>{statusLabel(order)}</Badge>
        </div>
        <CardDescription>{order.customerPhone || "未记录电话"} · {order.orderTimeText}</CardDescription>
      </CardHeader>
      <CardContent
        className="process-order-card-click-zone"
        role="button"
        tabIndex={0}
        onClick={() => onOpenDetail(order)}
        onKeyDown={openDetailFromKeyboard}
      >
        <div className="process-order-card-body">
          <OrderThumbnail order={order} onClick={() => onOpenImages(order)} />
          <div className="process-order-card-copy">
            <div className="process-order-main">
              <strong>{order.goodsName}</strong>
              <span>{order.color} · {order.quantity} 套</span>
            </div>
            <div className="process-order-meta">
              {order.screenPrint ? <Badge variant="outline">丝印</Badge> : <Badge variant="ghost">无丝印</Badge>}
              <span>创建人 {order.creatorName}</span>
            </div>
            {order.remark ? <p className="process-order-remark">{order.remark}</p> : null}
          </div>
        </div>
      </CardContent>
      <CardFooter>
        <div className="process-order-switches">
          <OrderStatusSwitch
            checked={order.made}
            disabled={busy}
            icon={PackageCheck}
            label={order.made ? "已制作" : "标记制作"}
            onCheckedChange={(checked) => onStatusChange(order, "is_made", checked)}
          />
          <OrderStatusSwitch
            checked={order.delivered}
            disabled={busy}
            icon={Truck}
            label={order.delivered ? "已配送" : "标记配送"}
            onCheckedChange={(checked) => onStatusChange(order, "is_delivered", checked)}
          />
        </div>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" aria-label="订单操作">
              <MoreHorizontal />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuGroup>
              <DropdownMenuItem onClick={() => onOpenDetail(order)}>
                <Eye />
                查看详情
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => onEdit(order)}>
                <ClipboardList />
                编辑订单
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => onStatusChange(order, "order_type", !order.completed)}>
                <CheckCircle2 />
                {order.completed ? "取消完成" : "标记完成"}
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => onDelete(order)}>删除订单</DropdownMenuItem>
            </DropdownMenuGroup>
          </DropdownMenuContent>
        </DropdownMenu>
      </CardFooter>
    </Card>
  );
}

function OrdersBoard({ orders, ...actions }: { orders: ProcessOrder[] } & OrderActions) {
  const [groupPages, setGroupPages] = useState<Record<OrderStatusGroup["key"], number>>({
    unmade: 1,
    delivery: 1,
    completed: 1
  });
  const groups = useMemo(() => groupOrdersByStatus(orders), [orders]);
  useEffect(() => setGroupPages({ unmade: 1, delivery: 1, completed: 1 }), [orders]);
  return (
    <div className="orders-board">
      {groups.map((group) => {
        const groupPageCount = Math.max(1, Math.ceil(group.orders.length / GROUP_PAGE_SIZE));
        const currentGroupPage = Math.min(groupPages[group.key] || 1, groupPageCount);
        const visibleOrders = group.orders.slice(
          (currentGroupPage - 1) * GROUP_PAGE_SIZE,
          currentGroupPage * GROUP_PAGE_SIZE
        );
        return (
          <section className="orders-board-column" key={group.key}>
            <div className="orders-board-column-header">
              <div>
                <h3>{group.title}</h3>
                <span>{group.description}</span>
              </div>
              <Badge variant="outline">{group.orders.length}</Badge>
            </div>
            <div className="orders-board-list">
              {visibleOrders.length ? (
                visibleOrders.map((order) => <ProcessOrderCard key={order.id} order={order} {...actions} />)
              ) : (
                <Empty className="orders-board-empty">
                  <EmptyHeader>
                    <EmptyTitle>暂无订单</EmptyTitle>
                    <EmptyDescription>当前分组没有需要处理的订单。</EmptyDescription>
                  </EmptyHeader>
                </Empty>
              )}
            </div>
            {groupPageCount > 1 ? (
              <div className="orders-board-pagination">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={currentGroupPage <= 1}
                  onClick={() => setGroupPages((value) => ({
                    ...value,
                    [group.key]: Math.max(1, currentGroupPage - 1)
                  }))}
                >
                  上一页
                </Button>
                <Badge variant="secondary">{currentGroupPage} / {groupPageCount}</Badge>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={currentGroupPage >= groupPageCount}
                  onClick={() => setGroupPages((value) => ({
                    ...value,
                    [group.key]: Math.min(groupPageCount, currentGroupPage + 1)
                  }))}
                >
                  下一页
                </Button>
              </div>
            ) : null}
          </section>
        );
      })}
    </div>
  );
}

function OrdersTable({ orders, ...actions }: { orders: ProcessOrder[] } & OrderActions) {
  return (
    <div className="orders-table">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>图片</TableHead>
            <TableHead>客户</TableHead>
            <TableHead>商品</TableHead>
            <TableHead>数量</TableHead>
            <TableHead>状态</TableHead>
            <TableHead>制作</TableHead>
            <TableHead>配送</TableHead>
            <TableHead>时间</TableHead>
            <TableHead>操作</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {orders.map((order) => {
            const busy = actions.busyOrderId === order.id;
            return (
              <TableRow key={order.id}>
                <TableCell>
                  <OrderThumbnail compact order={order} onClick={() => actions.onOpenImages(order)} />
                </TableCell>
                <TableCell>
                  <strong>{order.customerName}</strong>
                  <span>{order.customerPhone || "未记录电话"}</span>
                </TableCell>
                <TableCell>
                  <strong>{order.goodsName}</strong>
                  <span>{order.color}</span>
                </TableCell>
                <TableCell>{order.quantity} 套</TableCell>
                <TableCell>
                  <Badge variant={statusVariant(order)}>{statusLabel(order)}</Badge>
                </TableCell>
                <TableCell>
                  <Switch
                    checked={order.made}
                    disabled={busy}
                    onCheckedChange={(checked) => actions.onStatusChange(order, "is_made", checked)}
                    aria-label="制作状态"
                  />
                </TableCell>
                <TableCell>
                  <Switch
                    checked={order.delivered}
                    disabled={busy}
                    onCheckedChange={(checked) => actions.onStatusChange(order, "is_delivered", checked)}
                    aria-label="配送状态"
                  />
                </TableCell>
                <TableCell>{order.orderTimeText}</TableCell>
                <TableCell>
                  <div className="orders-table-actions">
                    <Button variant="outline" size="sm" onClick={() => actions.onOpenDetail(order)}>详情</Button>
                    <Button variant="outline" size="sm" onClick={() => actions.onEdit(order)}>编辑</Button>
                  </div>
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}

function OrdersToolbar({
  filter,
  keyword,
  loading,
  total,
  onCreate,
  onFilterChange,
  onKeywordChange,
  onRefresh,
  onReset,
  onSearch
}: {
  filter: ProcessOrderFilter;
  keyword: string;
  loading: boolean;
  total: number;
  onCreate: () => void;
  onFilterChange: (filter: ProcessOrderFilter) => void;
  onKeywordChange: (keyword: string) => void;
  onRefresh: () => void;
  onReset: () => void;
  onSearch: () => void;
}) {
  return (
    <div className="orders-toolbar">
      <Toolbar
        title={(
          <div className="orders-title-block">
            <CardTitle>订单工作台</CardTitle>
            <CardDescription>跟进客户订单、制作、配送和完成状态。</CardDescription>
          </div>
        )}
        actions={(
          <div className="orders-header-actions">
            <Badge variant="outline">共 {total} 单</Badge>
            <Button type="button" size="sm" onClick={onCreate}>
              <Plus data-icon="inline-start" />
              新建订单
            </Button>
          </div>
        )}
      />
      <div className="orders-filter-row">
        <div className="orders-search-box">
          <Input
            value={keyword}
            placeholder="搜索客户、手机号、商品、颜色"
            onChange={(event) => onKeywordChange(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") onSearch();
            }}
          />
          <Button type="button" variant="outline" size="sm" onClick={onSearch} disabled={loading}>
            <Search data-icon="inline-start" />
            搜索
          </Button>
        </div>
        <div className="orders-filter-buttons">
          {orderFilters.map((item) => (
            <Button
              key={item.value}
              type="button"
              size="sm"
              variant={filter === item.value ? "default" : "outline"}
              onClick={() => onFilterChange(item.value)}
            >
              {item.label}
              <span>{item.hint}</span>
            </Button>
          ))}
        </div>
        <div className="orders-filter-actions">
          <Button type="button" variant="outline" size="sm" onClick={onReset} disabled={loading}>重置</Button>
          <Button type="button" variant="outline" size="sm" onClick={onRefresh} disabled={loading}>
            <RefreshCw data-icon="inline-start" />
            刷新
          </Button>
        </div>
      </div>
    </div>
  );
}

function OrdersSkeleton() {
  return (
    <div className="orders-skeleton">
      {Array.from({ length: 6 }).map((_, index) => (
        <Skeleton key={index} className="orders-skeleton-card" />
      ))}
    </div>
  );
}

function OrderFormDialog({
  editingOrder,
  form,
  loading,
  open,
  onFormChange,
  onOpenChange,
  onSubmit
}: {
  editingOrder: ProcessOrder | null;
  form: OrderFormState;
  loading: boolean;
  open: boolean;
  onFormChange: (form: OrderFormState) => void;
  onOpenChange: (open: boolean) => void;
  onSubmit: () => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="order-form-dialog">
        <DialogHeader>
          <DialogTitle>{editingOrder ? "编辑订单" : "新建订单"}</DialogTitle>
          <DialogDescription>保存后用于跟进制作、配送和完成状态。</DialogDescription>
        </DialogHeader>
        <FieldGroup>
          <div className="order-form-grid">
            <Field>
              <FieldLabel htmlFor="orderCustomerName">客户名</FieldLabel>
              <Input
                id="orderCustomerName"
                value={form.customerName}
                onChange={(event) => onFormChange({ ...form, customerName: event.target.value })}
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="orderCustomerPhone">手机号</FieldLabel>
              <Input
                id="orderCustomerPhone"
                value={form.customerPhone}
                onChange={(event) => onFormChange({ ...form, customerPhone: event.target.value })}
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="orderGoodsName">商品</FieldLabel>
              <Input
                id="orderGoodsName"
                value={form.goodsName}
                onChange={(event) => onFormChange({ ...form, goodsName: event.target.value })}
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="orderColor">颜色</FieldLabel>
              <Input
                id="orderColor"
                value={form.color}
                onChange={(event) => onFormChange({ ...form, color: event.target.value })}
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="orderQuantity">数量</FieldLabel>
              <Input
                id="orderQuantity"
                type="number"
                min="1"
                value={form.quantity}
                onChange={(event) => onFormChange({ ...form, quantity: event.target.value })}
              />
            </Field>
            <Field className="order-form-switch-field">
              <FieldLabel>是否丝印</FieldLabel>
              <Switch
                checked={form.screenPrint}
                onCheckedChange={(checked) => onFormChange({ ...form, screenPrint: checked })}
                aria-label="是否丝印"
              />
            </Field>
            <Field className="order-form-switch-field">
              <FieldLabel>完成状态</FieldLabel>
              <Switch
                checked={form.completed}
                onCheckedChange={(checked) => onFormChange({ ...form, completed: checked })}
                aria-label="完成状态"
              />
            </Field>
          </div>
          <Field>
            <FieldLabel htmlFor="orderRemark">备注</FieldLabel>
            <Textarea
              id="orderRemark"
              value={form.remark}
              onChange={(event) => onFormChange({ ...form, remark: event.target.value })}
            />
            <FieldDescription>这里记录客户要求、设计说明或交付提醒。</FieldDescription>
          </Field>
        </FieldGroup>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={loading}>取消</Button>
          <Button type="button" onClick={onSubmit} disabled={loading || !form.customerName.trim() || !form.goodsName.trim()}>
            {loading ? "保存中" : "保存订单"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function OrderImageDialog({
  preview,
  onClose,
  onIndexChange
}: {
  preview: OrderImagePreview;
  onClose: () => void;
  onIndexChange: (index: number) => void;
}) {
  const order = preview?.order || null;
  const imageCount = order?.imageUrls.length || 0;
  const activeIndex = Math.min(preview?.index || 0, Math.max(0, imageCount - 1));
  const imageUrl = order?.imageUrls[activeIndex] || "";
  return (
    <Dialog open={Boolean(order && imageUrl)} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="order-image-dialog">
        <DialogHeader>
          <DialogTitle>{order?.goodsName || "查看图片"}</DialogTitle>
          <DialogDescription>{order?.color || "查看订单设计稿"}</DialogDescription>
        </DialogHeader>
        {order && imageUrl ? (
          <div className="order-image-preview">
            <div className="order-image-preview-main">
              {imageCount > 1 ? (
                <Button
                  type="button"
                  variant="outline"
                  size="icon"
                  aria-label="上一张"
                  disabled={activeIndex <= 0}
                  onClick={() => onIndexChange(Math.max(0, activeIndex - 1))}
                >
                  <ChevronLeft />
                </Button>
              ) : null}
              <img src={imageUrl} alt={`${order.goodsName}订单图片`} />
              {imageCount > 1 ? (
                <Button
                  type="button"
                  variant="outline"
                  size="icon"
                  aria-label="下一张"
                  disabled={activeIndex >= imageCount - 1}
                  onClick={() => onIndexChange(Math.min(imageCount - 1, activeIndex + 1))}
                >
                  <ChevronRight />
                </Button>
              ) : null}
            </div>
            {imageCount > 1 ? (
              <div className="order-image-thumbs">
                {order.imageUrls.map((url, index) => (
                  <a
                    href={url}
                    key={`${url}-${index}`}
                    className={index === activeIndex ? "is-active" : ""}
                    aria-label="切换图片"
                    onClick={(event) => {
                      event.preventDefault();
                      onIndexChange(index);
                    }}
                  >
                    <img src={url} alt={`${order.goodsName}订单缩略图`} />
                  </a>
                ))}
              </div>
            ) : null}
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

function OrderDetailDialog({
  order,
  busyOrderId,
  onClose,
  onEdit,
  onOpenImages,
  onStatusChange
}: {
  order: ProcessOrder | null;
  busyOrderId: number | null;
  onClose: () => void;
  onEdit: (order: ProcessOrder) => void;
  onOpenImages: (order: ProcessOrder, index?: number) => void;
  onStatusChange: (order: ProcessOrder, field: OrderStatusField, checked: boolean) => void;
}) {
  const busy = Boolean(order && busyOrderId === order.id);
  return (
    <Dialog open={Boolean(order)} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="order-detail-dialog">
        <DialogHeader>
          <DialogTitle>{order?.goodsName || "订单详情"}</DialogTitle>
          <DialogDescription>查看客户订单、制作、配送和完成状态。</DialogDescription>
        </DialogHeader>
        {order ? (
          <div className="order-detail-content">
            <div className="order-detail-title-row">
              <div>
                <strong>{order.customerName}</strong>
                <span>{order.customerPhone || "未记录电话"}</span>
              </div>
              <Badge variant={statusVariant(order)}>{statusLabel(order)}</Badge>
            </div>
            <div className="order-detail-grid">
              <div>
                <span>商品</span>
                <strong>{order.goodsName}</strong>
              </div>
              <div>
                <span>颜色</span>
                <strong>{order.color}</strong>
              </div>
              <div>
                <span>数量</span>
                <strong>{order.quantity} 套</strong>
              </div>
              <div>
                <span>丝印</span>
                <strong>{order.screenPrint ? "需要" : "不需要"}</strong>
              </div>
              <div>
                <span>下单时间</span>
                <strong>{order.orderTimeText}</strong>
              </div>
              <div>
                <span>创建人</span>
                <strong>{order.creatorName}</strong>
              </div>
            </div>
            <div className="order-detail-status-row">
              <OrderStatusSwitch
                checked={order.made}
                disabled={busy}
                icon={PackageCheck}
                label={order.made ? "已制作" : "标记制作"}
                onCheckedChange={(checked) => onStatusChange(order, "is_made", checked)}
              />
              <OrderStatusSwitch
                checked={order.delivered}
                disabled={busy}
                icon={Truck}
                label={order.delivered ? "已配送" : "标记配送"}
                onCheckedChange={(checked) => onStatusChange(order, "is_delivered", checked)}
              />
              <OrderStatusSwitch
                checked={order.completed}
                disabled={busy}
                icon={CheckCircle2}
                label={order.completed ? "已完成" : "标记完成"}
                onCheckedChange={(checked) => onStatusChange(order, "order_type", checked)}
              />
            </div>
            {order.remark ? (
              <div className="order-detail-note">
                <span>备注</span>
                <p>{order.remark}</p>
              </div>
            ) : null}
            <div className="order-detail-images">
              <div className="order-detail-section-title">
                <strong>图片</strong>
              </div>
              {order.imageUrls.length ? (
                <div className="order-image-grid">
                  {order.imageUrls.map((url, index) => (
                    <a
                      href={url}
                      key={`${url}-${index}`}
                      onClick={(event) => {
                        event.preventDefault();
                        onOpenImages(order, index);
                      }}
                    >
                      <img src={url} alt={`${order.goodsName}订单图片`} />
                    </a>
                  ))}
                </div>
              ) : (
                <Empty className="order-image-empty">
                  <EmptyHeader>
                    <EmptyTitle>没有图片</EmptyTitle>
                    <EmptyDescription>图片资产仍保留在原上传记录里。</EmptyDescription>
                  </EmptyHeader>
                </Empty>
              )}
            </div>
            <div className="order-detail-actions">
              <Button type="button" variant="outline" onClick={() => onEdit(order)}>编辑订单</Button>
            </div>
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

function OrderDeleteDialog({
  busy,
  order,
  onClose,
  onConfirm
}: {
  busy: boolean;
  order: ProcessOrder | null;
  onClose: () => void;
  onConfirm: () => void;
}) {
  return (
    <AlertDialog open={Boolean(order)} onOpenChange={(open) => !open && onClose()}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>删除订单</AlertDialogTitle>
          <AlertDialogDescription>
            删除后会从订单页隐藏，但保留过程订单日志。
          </AlertDialogDescription>
        </AlertDialogHeader>
        <div className="order-delete-target">
          <strong>{order?.goodsName || "订单"}</strong>
          <span>{order?.customerName || ""}</span>
        </div>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={busy}>取消</AlertDialogCancel>
          <AlertDialogAction disabled={busy} onClick={onConfirm}>{busy ? "删除中" : "确认删除"}</AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

function OrdersPage() {
  const [orders, setOrders] = useState<ProcessOrder[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [filter, setFilter] = useState<ProcessOrderFilter>("active");
  const [keyword, setKeyword] = useState("");
  const [view, setView] = useState<OrdersView>("board");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busyOrderId, setBusyOrderId] = useState<number | null>(null);
  const [detailOrder, setDetailOrder] = useState<ProcessOrder | null>(null);
  const [imagePreview, setImagePreview] = useState<OrderImagePreview>(null);
  const [deleteOrder, setDeleteOrder] = useState<ProcessOrder | null>(null);
  const [editingOrder, setEditingOrder] = useState<ProcessOrder | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [form, setForm] = useState<OrderFormState>(emptyForm);
  const [formSaving, setFormSaving] = useState(false);

  async function load(nextPage = page, nextKeyword = keyword, nextFilter = filter) {
    setLoading(true);
    setError("");
    try {
      const data = await api.workflowOrders({
        keyword: nextKeyword.trim(),
        page: nextPage,
        pageSize: ORDER_PAGE_SIZE,
        filter: nextFilter
      });
      const normalized = (data.list || []).map(normalizeProcessOrder).filter((order) => order.id);
      setOrders(normalized);
      setTotal(data.total || 0);
      setPage(data.page || nextPage);
    } catch (err) {
      setError(err instanceof Error ? err.message : "订单加载失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load(1, "", "active");
  }, []);

  useEffect(() => {
    if (!notice) return undefined;
    const timer = window.setTimeout(() => setNotice(""), 2400);
    return () => window.clearTimeout(timer);
  }, [notice]);

  function applyFilter(nextFilter: ProcessOrderFilter) {
    setFilter(nextFilter);
    void load(1, keyword, nextFilter);
  }

  function resetSearch() {
    setKeyword("");
    setFilter("active");
    void load(1, "", "active");
  }

  function openCreate() {
    setEditingOrder(null);
    setForm(emptyForm);
    setFormOpen(true);
  }

  function openEdit(order: ProcessOrder) {
    setEditingOrder(order);
    setForm(formFromOrder(order));
    setFormOpen(true);
  }

  function openImages(order: ProcessOrder, index = 0) {
    if (!order.imageUrls.length) return;
    setImagePreview({ order, index });
  }

  async function saveOrder() {
    setError("");
    setNotice("");
    setFormSaving(true);
    try {
      await api.saveWorkflowOrder(payloadFromForm(form, editingOrder));
      setNotice(editingOrder ? "订单已保存" : "订单已创建");
      setFormOpen(false);
      setEditingOrder(null);
      await load(page, keyword, filter);
    } catch (err) {
      setError(err instanceof Error ? err.message : "订单保存失败");
    } finally {
      setFormSaving(false);
    }
  }

  async function updateOrderStatus(order: ProcessOrder, field: OrderStatusField, checked: boolean) {
    const value = checked ? 1 : 0;
    setBusyOrderId(order.id);
    setError("");
    setNotice("");
    try {
      await api.updateWorkflowOrderStatus(order.id, { field: field, value });
      setOrders((current) => current.map((item) => {
        if (item.id !== order.id) return item;
        const raw: ProcessOrderRaw = { ...item.raw, [field]: value };
        if (field === "order_type") raw.status = value === 1 ? "completed" : "pending";
        return normalizeProcessOrder(raw);
      }));
      setDetailOrder((current) => {
        if (!current || current.id !== order.id) return current;
        const raw: ProcessOrderRaw = { ...current.raw, [field]: value };
        if (field === "order_type") raw.status = value === 1 ? "completed" : "pending";
        return normalizeProcessOrder(raw);
      });
      setNotice("订单状态已更新");
    } catch (err) {
      setError(err instanceof Error ? err.message : "订单状态更新失败");
    } finally {
      setBusyOrderId(null);
    }
  }

  async function confirmDeleteOrder() {
    if (!deleteOrder) return;
    setBusyOrderId(deleteOrder.id);
    setError("");
    setNotice("");
    try {
      await api.deleteWorkflowOrder(deleteOrder.id);
      setNotice("订单已删除");
      setDeleteOrder(null);
      setDetailOrder((current) => current?.id === deleteOrder.id ? null : current);
      setImagePreview((current) => current?.order.id === deleteOrder.id ? null : current);
      await load(page, keyword, filter);
    } catch (err) {
      setError(err instanceof Error ? err.message : "订单删除失败");
    } finally {
      setBusyOrderId(null);
    }
  }

  const actions: OrderActions = {
    busyOrderId,
    onStatusChange: (order, field, checked) => void updateOrderStatus(order, field, checked),
    onOpenDetail: setDetailOrder,
    onOpenImages: openImages,
    onEdit: openEdit,
    onDelete: setDeleteOrder
  };

  return (
    <Card className="orders-page data-panel">
      <CardHeader className="orders-page-header">
        <OrdersToolbar
          filter={filter}
          keyword={keyword}
          loading={loading}
          total={total}
          onCreate={openCreate}
          onFilterChange={applyFilter}
          onKeywordChange={setKeyword}
          onRefresh={() => void load(page, keyword, filter)}
          onReset={resetSearch}
          onSearch={() => void load(1, keyword, filter)}
        />
      </CardHeader>
      <CardContent className="orders-page-content">
        <OrderNotice notice={notice} />
        {error ? <div className="form-error">{error}</div> : null}
        <OrdersSummaryStrip orders={orders} total={total} />
        <Tabs value={view} onValueChange={(value) => setView(value as OrdersView)} className="orders-tabs">
          <TabsList>
            <TabsTrigger value="board">订单看板</TabsTrigger>
            <TabsTrigger value="table">明细表</TabsTrigger>
          </TabsList>
          <TabsContent value="board">
            {loading ? (
              <OrdersSkeleton />
            ) : orders.length ? (
              <OrdersBoard orders={orders} {...actions} />
            ) : (
              <Empty className="orders-empty">
                <EmptyHeader>
                  <EmptyTitle>没有订单</EmptyTitle>
                  <EmptyDescription>当前筛选没有过程订单，可以新建或重置筛选。</EmptyDescription>
                </EmptyHeader>
              </Empty>
            )}
          </TabsContent>
          <TabsContent value="table">
            {loading ? (
              <OrdersSkeleton />
            ) : orders.length ? (
              <OrdersTable orders={orders} {...actions} />
            ) : (
              <Empty className="orders-empty">
                <EmptyHeader>
                  <EmptyTitle>没有明细</EmptyTitle>
                  <EmptyDescription>换一个关键词或筛选条件再试。</EmptyDescription>
                </EmptyHeader>
              </Empty>
            )}
          </TabsContent>
        </Tabs>
      </CardContent>
      <OrderFormDialog
        editingOrder={editingOrder}
        form={form}
        loading={formSaving}
        open={formOpen}
        onFormChange={setForm}
        onOpenChange={setFormOpen}
        onSubmit={() => void saveOrder()}
      />
      <OrderDetailDialog
        order={detailOrder}
        busyOrderId={busyOrderId}
        onClose={() => setDetailOrder(null)}
        onEdit={openEdit}
        onOpenImages={openImages}
        onStatusChange={(order, field, checked) => void updateOrderStatus(order, field, checked)}
      />
      <OrderImageDialog
        preview={imagePreview}
        onClose={() => setImagePreview(null)}
        onIndexChange={(index) => setImagePreview((current) => current ? { ...current, index } : current)}
      />
      <OrderDeleteDialog
        busy={Boolean(deleteOrder && busyOrderId === deleteOrder.id)}
        order={deleteOrder}
        onClose={() => setDeleteOrder(null)}
        onConfirm={() => void confirmDeleteOrder()}
      />
    </Card>
  );
}

export { OrdersPage };
