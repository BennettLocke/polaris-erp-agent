import { useEffect, useState } from "react";
import { CircleDollarSign, Eye, Files, Pencil, Printer, Trash2, WalletCards } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from "@/components/ui/dialog";
import { Field, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "@/components/ui/select";
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
import type { SalesDetail, SalesPaymentUpdatePayload, SalesPriceUpdatePayload, SalesProduct } from "@/types";
import { displayDate, money, payText, salesAmount, salesOrderId, salesQuantity, stockRuleText } from "./utils";
import type { SalesOrderDetailDialogProps } from "./types";

type PaymentStatus = SalesPaymentUpdatePayload["pay_status"];

const PAYMENT_STATUS_OPTIONS: Array<{ value: PaymentStatus; label: string }> = [
  { value: "paid", label: "已付" },
  { value: "monthly", label: "月结" },
  { value: "unpaid", label: "未付" },
  { value: "partial", label: "部分付款" }
];

const PAY_TYPE_OPTIONS = [
  { value: "wechat", label: "微信" },
  { value: "cash", label: "现金" },
  { value: "balance", label: "余额" },
  { value: "bank", label: "转账" },
  { value: "alipay", label: "支付宝" },
  { value: "account", label: "账户" }
];

function normalizePayStatus(value?: string): PaymentStatus {
  if (value === "paid" || value === "monthly" || value === "unpaid" || value === "partial") return value;
  return "paid";
}

function normalizePayType(status: PaymentStatus, value?: string) {
  if (status === "monthly") return "monthly";
  if (status !== "paid") return "";
  const clean = String(value || "").trim();
  if (clean && clean !== "monthly") return clean;
  return "wechat";
}

type SalesPaymentEditDialogProps = {
  order: SalesDetail | null;
  open: boolean;
  busy: boolean;
  onOpenChange: (open: boolean) => void;
  onSave: (payload: SalesPaymentUpdatePayload) => Promise<void>;
};

function SalesPaymentEditDialog({ order, open, busy, onOpenChange, onSave }: SalesPaymentEditDialogProps) {
  const [payStatus, setPayStatus] = useState<PaymentStatus>("paid");
  const [payType, setPayType] = useState("wechat");
  const [note, setNote] = useState("");
  const [localError, setLocalError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const nextStatus = normalizePayStatus(order?.pay_status);
    setPayStatus(nextStatus);
    setPayType(normalizePayType(nextStatus, order?.pay_type));
    setNote("");
    setLocalError("");
  }, [order, open]);

  function handleStatusChange(value: PaymentStatus) {
    setPayStatus(value);
    setPayType((current) => normalizePayType(value, current));
  }

  async function handleSave() {
    if (!order) return;
    const nextPayType = normalizePayType(payStatus, payType);
    if (payStatus === "paid" && !nextPayType) {
      setLocalError("请选择收款方式");
      return;
    }
    setLocalError("");
    setSaving(true);
    try {
      await onSave({
        pay_status: payStatus,
        pay_type: nextPayType,
        note: note.trim()
      });
      onOpenChange(false);
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : "收款方式保存失败");
    } finally {
      setSaving(false);
    }
  }

  const disabled = busy || saving;
  const showPayType = payStatus === "paid";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sales-payment-edit-dialog">
        <DialogHeader>
          <DialogTitle>编辑收款方式</DialogTitle>
          <DialogDescription>
            只修改这张销售单的结款状态和收款方式，余额扣款与退回由后端事务处理。
          </DialogDescription>
        </DialogHeader>

        <div className="sales-payment-edit-grid">
          <Field>
            <FieldLabel>结款状态</FieldLabel>
            <Select value={payStatus} onValueChange={(value) => handleStatusChange(value as PaymentStatus)}>
              <SelectTrigger>
                <SelectValue placeholder="选择结款状态" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  {PAYMENT_STATUS_OPTIONS.map((item) => (
                    <SelectItem key={item.value} value={item.value}>{item.label}</SelectItem>
                  ))}
                </SelectGroup>
              </SelectContent>
            </Select>
          </Field>

          {showPayType ? (
            <Field>
              <FieldLabel>收款方式</FieldLabel>
              <Select value={payType} onValueChange={setPayType}>
                <SelectTrigger>
                  <SelectValue placeholder="选择收款方式" />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    {PAY_TYPE_OPTIONS.map((item) => (
                      <SelectItem key={item.value} value={item.value}>{item.label}</SelectItem>
                    ))}
                  </SelectGroup>
                </SelectContent>
              </Select>
            </Field>
          ) : null}

          <Field className="full">
            <FieldLabel>备注</FieldLabel>
            <Textarea
              rows={3}
              value={note}
              onChange={(event) => setNote(event.target.value)}
              placeholder="例如：客户改用余额付款、微信改现金"
            />
          </Field>

          <div className="sales-payment-warning full">
            <WalletCards data-icon="inline-start" />
            保存后会按后端余额规则扣款或退回，余额不足时不会保存。
          </div>
          {localError ? <div className="form-error full">{localError}</div> : null}
        </div>

        <DialogFooter>
          <Button variant="outline" type="button" disabled={disabled} onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button type="button" disabled={disabled} onClick={() => void handleSave()}>
            {disabled ? "保存中" : "保存"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

type SalesPriceEditDialogProps = {
  order: SalesDetail | null;
  open: boolean;
  busy: boolean;
  onOpenChange: (open: boolean) => void;
  onSave: (payload: SalesPriceUpdatePayload) => Promise<void>;
};

function productPriceGroupKey(product: SalesProduct, index: number) {
  if (product.spu_id && product.unit_id) return `${product.spu_id}:${product.unit_id}`;
  return `item:${product.item_id || index}`;
}

function priceNumber(value: string | number | undefined) {
  const parsed = Number(value || 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

function SalesPriceEditDialog({ order, open, busy, onOpenChange, onSave }: SalesPriceEditDialogProps) {
  const products = order?.detail || order?.items || order?.products || [];
  const [prices, setPrices] = useState<Record<number, string>>({});
  const [note, setNote] = useState("");
  const [localError, setLocalError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const nextPrices: Record<number, string> = {};
    products.forEach((product) => {
      const itemId = Number(product.item_id || 0);
      if (itemId) nextPrices[itemId] = priceNumber(product.price).toFixed(2);
    });
    setPrices(nextPrices);
    setNote("");
    setLocalError("");
  }, [order, open]);

  function handlePriceChange(product: SalesProduct, index: number, value: string) {
    const groupKey = productPriceGroupKey(product, index);
    setPrices((current) => {
      const next = { ...current };
      products.forEach((candidate, candidateIndex) => {
        const itemId = Number(candidate.item_id || 0);
        if (itemId && productPriceGroupKey(candidate, candidateIndex) === groupKey) {
          next[itemId] = value;
        }
      });
      return next;
    });
  }

  async function handleSave() {
    const payloadItems: SalesPriceUpdatePayload["items"] = [];
    for (const product of products) {
      const itemId = Number(product.item_id || 0);
      const value = String(prices[itemId] ?? "").trim();
      if (!itemId) {
        setLocalError("销售明细信息不完整，请刷新后重试");
        return;
      }
      if (!/^\d+(?:\.\d{1,2})?$/.test(value) || priceNumber(value) <= 0) {
        setLocalError("单价必须大于0，最多保留两位小数");
        return;
      }
      payloadItems.push({ item_id: itemId, unit_price: priceNumber(value) });
    }
    setLocalError("");
    setSaving(true);
    try {
      await onSave({ items: payloadItems, note: note.trim() });
      onOpenChange(false);
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : "销售单价格保存失败");
    } finally {
      setSaving(false);
    }
  }

  const newGoodsAmount = products.reduce((total, product) => {
    const itemId = Number(product.item_id || 0);
    return total + priceNumber(product.quantity || product.buy_number) * priceNumber(prices[itemId]);
  }, 0);
  const disabled = busy || saving;

  return (
    <Dialog open={open} onOpenChange={(nextOpen) => {
      if (!disabled) onOpenChange(nextOpen);
    }}>
      <DialogContent className="sales-price-edit-dialog">
        <DialogHeader>
          <DialogTitle>编辑销售价格</DialogTitle>
          <DialogDescription>
            只修改商品单价。数量不可修改，商品、颜色、仓库和库存流水均保持不变。
          </DialogDescription>
        </DialogHeader>

        <div className="sales-price-edit-body">
          <Table className="sales-price-edit-table">
            <TableHeader>
              <TableRow>
                <TableHead>商品</TableHead>
                <TableHead>颜色/规格</TableHead>
                <TableHead>数量</TableHead>
                <TableHead>原单价</TableHead>
                <TableHead>新单价</TableHead>
                <TableHead>新金额</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {products.map((product, index) => {
                const itemId = Number(product.item_id || 0);
                const quantity = priceNumber(product.quantity || product.buy_number);
                const nextPrice = prices[itemId] ?? "";
                return (
                  <TableRow key={itemId || index}>
                    <TableCell>{product.title || product.name || "商品"}</TableCell>
                    <TableCell>{product.spec || product.color || "默认颜色"}</TableCell>
                    <TableCell>{product.quantity || product.buy_number || 0}</TableCell>
                    <TableCell>{money(product.price)}</TableCell>
                    <TableCell>
                      <Input
                        type="number"
                        min="0.01"
                        step="0.01"
                        inputMode="decimal"
                        value={nextPrice}
                        disabled={disabled}
                        aria-label={`${product.title || product.name || "商品"}新单价`}
                        onChange={(event) => handlePriceChange(product, index, event.target.value)}
                      />
                    </TableCell>
                    <TableCell>{money(quantity * priceNumber(nextPrice))}</TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>

          <div className="sales-price-edit-summary">
            <span>修改后商品金额</span>
            <strong>{money(newGoodsAmount)}</strong>
          </div>

          <Field>
            <FieldLabel>修改备注</FieldLabel>
            <Textarea
              rows={3}
              value={note}
              disabled={disabled}
              onChange={(event) => setNote(event.target.value)}
              placeholder="例如：客户议价、录入价格修正"
            />
          </Field>

          <div className="sales-payment-warning">
            <CircleDollarSign data-icon="inline-start" />
            同款不同颜色会同步价格；余额付款会自动补扣或退回差额，符合规则的商品会更新客户历史价。
          </div>
          {localError ? <div className="form-error">{localError}</div> : null}
        </div>

        <DialogFooter>
          <Button variant="outline" type="button" disabled={disabled} onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button type="button" disabled={disabled || products.length === 0} onClick={() => void handleSave()}>
            {disabled ? "保存中" : "保存价格"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function SalesOrderDetailDialog({
  order,
  busySalesId,
  onClose,
  onPrint,
  onPreview,
  onMergePreview,
  onUpdatePayment,
  onUpdatePrices,
  onDelete
}: SalesOrderDetailDialogProps) {
  const [paymentEditOpen, setPaymentEditOpen] = useState(false);
  const [priceEditOpen, setPriceEditOpen] = useState(false);
  const products = order?.detail || order?.items || order?.products || [];
  const orderId = salesOrderId(order);
  const busy = Boolean(orderId && busySalesId === orderId);

  useEffect(() => {
    if (!order) {
      setPaymentEditOpen(false);
      setPriceEditOpen(false);
    }
  }, [order]);

  return (
    <>
      <Dialog
        open={Boolean(order)}
        onOpenChange={(open) => {
          if (!open) {
            setPaymentEditOpen(false);
            setPriceEditOpen(false);
            onClose();
          }
        }}
      >
        <DialogContent className="sales-order-detail-dialog">
          <DialogHeader>
            <div className="sales-detail-title-row">
              <div>
                <DialogTitle>{order?.customer_name || "销售单详情"}</DialogTitle>
                <DialogDescription>{order?.sales_no || "未记录单号"}</DialogDescription>
              </div>
              {order ? (
                <div className="sales-detail-badges">
                  <Badge variant="outline">{order.status_text || "正常"}</Badge>
                  <Badge variant="outline">{payText(order)}</Badge>
                  <Badge variant="secondary">{displayDate(order.sales_at || order.created_at)}</Badge>
                </div>
              ) : null}
            </div>
          </DialogHeader>

          {order ? (
            <div className="sales-detail-dialog-body">
              <div className="sales-detail-metrics">
                <div><span>总数量</span><strong>{salesQuantity(order)}</strong></div>
                <div><span>应收金额</span><strong>{salesAmount(order)}</strong></div>
                <div><span>开单人</span><strong>{order.created_by_name || "未记录"}</strong></div>
                <div><span>付款</span><strong>{payText(order)}</strong></div>
              </div>

              <Tabs defaultValue="detail" className="sales-detail-tabs">
                <TabsList>
                  <TabsTrigger value="detail">明细</TabsTrigger>
                  <TabsTrigger value="payment">付款</TabsTrigger>
                  <TabsTrigger value="log">操作记录</TabsTrigger>
                </TabsList>
                <TabsContent value="detail">
                  <div className="sales-detail-section-header">
                    <div>
                      <strong>销售商品</strong>
                      <span>{order.price_editable === false ? order.price_edit_block_reason : "只允许修改单价，数量和库存不会变化。"}</span>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      type="button"
                      disabled={!orderId || busy || order.price_editable !== true}
                      title={order.price_editable === false ? order.price_edit_block_reason : undefined}
                      onClick={() => setPriceEditOpen(true)}
                    >
                      <Pencil data-icon="inline-start" /> 编辑价格
                    </Button>
                  </div>
                  <div className="sales-detail-table-wrap">
                    <Table className="sales-detail-table">
                      <TableHeader>
                        <TableRow>
                          <TableHead>商品</TableHead>
                          <TableHead>颜色/规格</TableHead>
                          <TableHead>数量</TableHead>
                          <TableHead>仓库</TableHead>
                          <TableHead>单价</TableHead>
                          <TableHead>金额</TableHead>
                          <TableHead>库存规则</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {products.map((product, index) => (
                          <TableRow key={`${product.product_id || product.id || index}-${index}`}>
                            <TableCell>{product.title || product.name || "商品"}</TableCell>
                            <TableCell>{product.spec || product.color || "默认颜色"}</TableCell>
                            <TableCell>{product.quantity || product.buy_number || 0}</TableCell>
                            <TableCell>{product.warehouse_name || "-"}</TableCell>
                            <TableCell>{money(product.price)}</TableCell>
                            <TableCell>{money(product.total_price)}</TableCell>
                            <TableCell><Badge variant="outline">{stockRuleText(product)}</Badge></TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                </TabsContent>
                <TabsContent value="payment">
                  <section className="sales-payment-panel">
                    <div className="sales-payment-panel-header">
                      <div>
                        <strong>收款信息</strong>
                        <span>修改余额付款时会自动校验并写余额流水。</span>
                      </div>
                      <Button variant="outline" size="sm" type="button" disabled={!orderId || busy} onClick={() => setPaymentEditOpen(true)}>
                        <Pencil data-icon="inline-start" /> 编辑收款
                      </Button>
                    </div>
                    <div className="sales-detail-note-grid">
                      <div><span>结款状态</span><strong>{order.pay_status_text || "-"}</strong></div>
                      <div><span>付款方式</span><strong>{order.pay_type_text || "-"}</strong></div>
                      <div><span>商品金额</span><strong>{money(order.goods_amount || order.total_price)}</strong></div>
                      <div><span>应收金额</span><strong>{salesAmount(order)}</strong></div>
                      <div className="full"><span>备注</span><strong>{order.note || "-"}</strong></div>
                    </div>
                  </section>
                </TabsContent>
                <TabsContent value="log">
                  <div className="sales-detail-note-grid">
                    <div><span>创建人</span><strong>{order.created_by_name || "未记录"}</strong></div>
                    <div><span>创建时间</span><strong>{displayDate(order.created_at || order.sales_at)}</strong></div>
                    <div><span>删除人</span><strong>{order.deleted_by_name || "-"}</strong></div>
                    <div><span>删除时间</span><strong>{displayDate(order.deleted_at)}</strong></div>
                    <div className="full"><span>删除说明</span><strong>{order.delete_reason || "库存和余额回滚由服务层处理"}</strong></div>
                    <div className="full"><span>收款备注</span><strong>{order.note || "-"}</strong></div>
                  </div>
                  {order.price_change_logs?.length ? (
                    <div className="sales-price-log-list">
                      <strong>价格修改记录</strong>
                      {order.price_change_logs.map((log) => (
                        <div className="sales-price-log-item" key={log.id}>
                          <div>
                            <strong>{log.title} · {log.color}</strong>
                            <span>{displayDate(log.created_at)} · {log.operator_name || "未记录操作人"}</span>
                          </div>
                          <div>
                            <strong>{money(log.old_unit_price)} → {money(log.new_unit_price)}</strong>
                            <span>{log.note || "未填写备注"}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : null}
                </TabsContent>
              </Tabs>
            </div>
          ) : null}

          <DialogFooter>
            {onMergePreview ? (
              <Button
                variant="outline"
                size="sm"
                type="button"
                disabled={!orderId || busy || ["deleted", "canceled"].includes(String(order?.status || ""))}
                onClick={() => onMergePreview(orderId)}
              >
                <Files data-icon="inline-start" /> 合并预览
              </Button>
            ) : null}
            <Button variant="outline" size="sm" type="button" disabled={!orderId} onClick={() => onPreview(orderId)}>
              <Eye data-icon="inline-start" /> 打印预览
            </Button>
            <Button size="sm" type="button" disabled={!orderId || busy} onClick={() => onPrint(orderId)}>
              <Printer data-icon="inline-start" /> {busy ? "提交中" : "打印"}
            </Button>
            {order ? (
              <Button variant="destructive" size="sm" type="button" disabled={!orderId || busy} onClick={() => onDelete(order)}>
                <Trash2 data-icon="inline-start" /> 删除
              </Button>
            ) : null}
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <SalesPaymentEditDialog
        order={order}
        open={paymentEditOpen}
        busy={busy}
        onOpenChange={setPaymentEditOpen}
        onSave={(payload) => orderId ? onUpdatePayment(orderId, payload) : Promise.resolve()}
      />
      <SalesPriceEditDialog
        order={order}
        open={priceEditOpen}
        busy={busy}
        onOpenChange={setPriceEditOpen}
        onSave={(payload) => orderId ? onUpdatePrices(orderId, payload) : Promise.resolve()}
      />
    </>
  );
}

export { SalesOrderDetailDialog };
