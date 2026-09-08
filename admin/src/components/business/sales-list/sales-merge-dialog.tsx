import { useEffect, useMemo, useState } from "react";
import { Files, LoaderCircle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from "@/components/ui/table";
import type { SalesMergeCandidates, SalesMergeOrder } from "@/types";
import { money } from "./utils";

type SalesMergeDialogProps = {
  open: boolean;
  loading: boolean;
  error?: string;
  candidates: SalesMergeCandidates | null;
  onOpenChange: (open: boolean) => void;
  onGenerate: (selectedIds: number[]) => void;
};

function numberValue(value: unknown) {
  const parsed = Number(value ?? 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

function dateOnly(value?: string) {
  return String(value || "-").replace("T", " ").slice(0, 10);
}

function orderProductSummary(order: SalesMergeOrder) {
  const lines = order.items.slice(0, 2).map((item) => `${item.title} ${item.color}`);
  const extra = Math.max(0, order.items.length - lines.length);
  return `${lines.join("；") || "暂无商品明细"}${extra ? `；另有 ${extra} 项` : ""}`;
}

function SalesMergeDialog({
  open,
  loading,
  error,
  candidates,
  onOpenChange,
  onGenerate
}: SalesMergeDialogProps) {
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const orders = candidates?.orders || [];

  useEffect(() => {
    if (!open || !candidates) return;
    setSelectedIds(new Set([candidates.base_sales_id]));
  }, [open, candidates]);

  const selectedOrders = useMemo(
    () => orders.filter((order) => selectedIds.has(order.id)),
    [orders, selectedIds]
  );
  const selectedQuantity = selectedOrders.reduce((sum, order) => sum + numberValue(order.total_quantity), 0);
  const selectedAmount = selectedOrders.reduce((sum, order) => sum + numberValue(order.receivable_amount), 0);
  const allSelected = Boolean(orders.length) && selectedIds.size === orders.length;
  const someSelected = selectedIds.size > 0 && !allSelected;

  function toggleOrder(orderId: number, checked: boolean) {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (checked) next.add(orderId);
      else next.delete(orderId);
      return next;
    });
  }

  function toggleAll(checked: boolean) {
    setSelectedIds(checked ? new Set(orders.map((order) => order.id)) : new Set());
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sales-merge-dialog">
        <DialogHeader>
          <DialogTitle>选择要合并预览的销售单</DialogTitle>
          <DialogDescription>
            {candidates
              ? `${candidates.customer.name} · ${candidates.date_from} 至 ${candidates.date_to}`
              : "正在读取当前客户7天内的销售单"}
          </DialogDescription>
        </DialogHeader>

        {error ? <div className="form-error">{error}</div> : null}
        {loading ? (
          <div className="sales-merge-loading">
            <LoaderCircle />
            <span>正在加载可合并订单</span>
          </div>
        ) : candidates ? (
          <>
            <div className="sales-merge-select-all">
              <label htmlFor="sales-merge-select-all">
                <Checkbox
                  id="sales-merge-select-all"
                  checked={allSelected ? true : someSelected ? "indeterminate" : false}
                  onCheckedChange={(checked) => toggleAll(checked === true)}
                />
                <span>全部选择</span>
              </label>
              <Badge variant="outline">共 {orders.length} 张</Badge>
            </div>
            <div className="sales-merge-table-wrap">
              <Table className="sales-merge-table">
                <TableHeader>
                  <TableRow>
                    <TableHead>选择</TableHead>
                    <TableHead>日期</TableHead>
                    <TableHead>单号</TableHead>
                    <TableHead>商品摘要</TableHead>
                    <TableHead>付款</TableHead>
                    <TableHead>数量</TableHead>
                    <TableHead>金额</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {orders.map((order) => {
                    const checked = selectedIds.has(order.id);
                    return (
                      <TableRow key={order.id} data-selected={checked || undefined}>
                        <TableCell>
                          <Checkbox
                            checked={checked}
                            aria-label={`选择销售单 ${order.sales_no}`}
                            onCheckedChange={(value) => toggleOrder(order.id, value === true)}
                          />
                        </TableCell>
                        <TableCell>{dateOnly(order.sales_at)}</TableCell>
                        <TableCell>{order.sales_no}</TableCell>
                        <TableCell>{orderProductSummary(order)}</TableCell>
                        <TableCell>{[order.pay_status_text, order.pay_type_text].filter(Boolean).join(" / ") || "-"}</TableCell>
                        <TableCell>{order.total_quantity}</TableCell>
                        <TableCell>{money(order.receivable_amount)}</TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
            <div className="sales-merge-selection-summary" aria-live="polite">
              <span>已选 <strong>{selectedOrders.length}</strong> 单</span>
              <span>总数量 <strong>{selectedQuantity}</strong></span>
              <span>合计 <strong>{money(selectedAmount)}</strong></span>
            </div>
          </>
        ) : null}

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>取消</Button>
          <Button
            type="button"
            disabled={loading || !candidates || selectedOrders.length === 0}
            onClick={() => onGenerate(selectedOrders.map((order) => order.id))}
          >
            <Files data-icon="inline-start" /> 生成合并预览
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export { SalesMergeDialog };
export type { SalesMergeDialogProps };
