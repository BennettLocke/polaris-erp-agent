import { useEffect, useMemo, useState } from "react";

import { api } from "@/api";
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
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import type { CustomerBalanceActionPayload, CustomerItem, CustomerSalesSummary } from "@/types";
import { balanceActionLabels, customerName, money, moneyNumber, monthOptions, payTypeOptions } from "./utils";

type Props = {
  action: CustomerBalanceActionPayload["action"] | null;
  customer: CustomerItem | null;
  onClose: () => void;
  onSaved: () => void;
};

function currentMonthValue() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

function CustomerBalanceActionDialog({ action, customer, onClose, onSaved }: Props) {
  const [amount, setAmount] = useState("");
  const [payType, setPayType] = useState("wechat");
  const [month, setMonth] = useState(currentMonthValue);
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [preview, setPreview] = useState<CustomerSalesSummary | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const months = useMemo(() => monthOptions(), []);
  const title = action ? balanceActionLabels[action] : "";
  const isSettlement = action === "settlement";
  const isAdjust = action === "adjust";
  const balance = moneyNumber(customer?.balance_amount);
  const settlementAmount = moneyNumber(preview?.unpaid_amount);
  const incomingAmount = moneyNumber(amount);
  const settlementDiff = incomingAmount - settlementAmount;

  useEffect(() => {
    if (!action) return;
    setAmount("");
    setPayType("wechat");
    setMonth(currentMonthValue());
    setNote("");
    setError("");
    setPreview(null);
  }, [action]);

  useEffect(() => {
    if (!isSettlement || !customer?.id || !month) return;
    setPreviewLoading(true);
    api.customerSales(customer.id, { page: 1, pageSize: 1, month })
      .then((data) => setPreview(data.summary || null))
      .catch(() => setPreview(null))
      .finally(() => setPreviewLoading(false));
  }, [customer?.id, isSettlement, month]);

  function validateAction() {
    const parsedAmount = Number(amount.trim());
    if (!Number.isFinite(parsedAmount) || parsedAmount === 0 || (!isAdjust && parsedAmount < 0)) {
      setError("请输入有效金额");
      return false;
    }
    if (isAdjust && !note.trim()) {
      setError("请填写调整原因");
      return false;
    }
    return true;
  }

  async function submit() {
    if (!action || !customer) return;
    if (!validateAction()) return;
    setSaving(true);
    setError("");
    try {
      await api.applyCustomerBalance(customer.id, {
        action,
        amount,
        pay_type: isAdjust ? undefined : payType,
        month: isSettlement ? month : undefined,
        note
      });
      onSaved();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : `${title}失败`);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog
      open={Boolean(action)}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent className="customer-action-dialog">
        <DialogHeader>
          <DialogTitle>{title || "余额动作"}</DialogTitle>
          <DialogDescription>
            {customerName(customer) || "客户"} · 当前余额 {money(balance)}
          </DialogDescription>
        </DialogHeader>

        <FieldGroup>
          {isSettlement ? (
            <Field>
              <FieldLabel>结款月份</FieldLabel>
              <div className="customer-month-grid">
                {months.map((item) => (
                  <Button
                    key={item.value}
                    type="button"
                    variant={month === item.value ? "default" : "outline"}
                    size="sm"
                    onClick={() => setMonth(item.value)}
                  >
                    {item.label}
                  </Button>
                ))}
              </div>
            </Field>
          ) : null}

          {isSettlement ? (
            <div className="customer-settlement-preview">
              <div>
                <span>本月单数</span>
                <strong>{previewLoading ? "查询中" : `${preview?.total || 0} 单`}</strong>
              </div>
              <div>
                <span>应结金额</span>
                <strong>{money(settlementAmount)}</strong>
              </div>
              <div>
                <span>实收差额</span>
                <strong className={settlementDiff < 0 ? "customer-money-negative" : ""}>{money(settlementDiff)}</strong>
              </div>
            </div>
          ) : null}

          <div className="customer-action-form-grid">
            <Field>
              <FieldLabel>金额</FieldLabel>
              <Input
                value={amount}
                inputMode="decimal"
                placeholder={action === "adjust" ? "可输入正负金额" : "输入金额"}
                onChange={(event) => setAmount(event.target.value)}
              />
            </Field>
            {action !== "adjust" ? (
              <Field>
                <FieldLabel>收款方式</FieldLabel>
                <Select value={payType} onValueChange={setPayType}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectGroup>
                      {payTypeOptions.map((item) => (
                        <SelectItem value={item.value} key={item.value}>{item.label}</SelectItem>
                      ))}
                    </SelectGroup>
                  </SelectContent>
                </Select>
              </Field>
            ) : null}
          </div>

          <Field>
            <FieldLabel>{isAdjust ? "调整原因" : "备注"}</FieldLabel>
            <Textarea
              value={note}
              rows={3}
              required={isAdjust}
              placeholder={isAdjust ? "必须填写为什么调整余额，方便以后查账" : "可填写备注，方便以后查账"}
              onChange={(event) => setNote(event.target.value)}
            />
          </Field>
        </FieldGroup>

        {isSettlement && settlementDiff !== 0 && amount ? (
          <Badge variant="outline" className="customer-dialog-hint">
            {settlementDiff > 0 ? "实收多于应结，多出的金额会进入客户余额。" : "实收少于应结，差额会继续表现为负余额。"}
          </Badge>
        ) : null}
        {error ? <div className="form-error">{error}</div> : null}

        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose}>取消</Button>
          <Button type="button" disabled={saving} onClick={submit}>
            {saving ? "保存中" : `确认${title}`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export { CustomerBalanceActionDialog };
