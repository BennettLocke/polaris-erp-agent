import { useEffect, useMemo, useState } from "react";
import { Download, RefreshCw } from "lucide-react";

import { api, type CustomerStatementQuery } from "@/api";
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
import { DatePicker } from "@/components/ui/date-picker";
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from "@/components/ui/table";
import type { CustomerItem, CustomerStatement } from "@/types";
import { customerName, money, monthOptions, shortDate } from "./utils";

type Props = {
  customer: CustomerItem | null;
  open: boolean;
  initialMonth?: string;
  onOpenChange: (open: boolean) => void;
};

function currentMonthValue() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

function CustomerStatementDialog({ customer, open, initialMonth, onOpenChange }: Props) {
  const months = useMemo(() => monthOptions(), []);
  const [month, setMonth] = useState(initialMonth || currentMonthValue());
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [statement, setStatement] = useState<CustomerStatement | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const query: CustomerStatementQuery = dateFrom || dateTo
    ? { dateFrom, dateTo }
    : { month };

  async function load(nextQuery: CustomerStatementQuery = query) {
    if (!customer?.id) return;
    setLoading(true);
    setError("");
    try {
      setStatement(await api.customerStatement(customer.id, nextQuery));
    } catch (err) {
      setError(err instanceof Error ? err.message : "对账单加载失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!open) return;
    const nextMonth = initialMonth || currentMonthValue();
    setMonth(nextMonth);
    setDateFrom("");
    setDateTo("");
    setStatement(null);
    void load({ month: nextMonth });
  }, [open, customer?.id, initialMonth]);

  function selectMonth(value: string) {
    setMonth(value);
    setDateFrom("");
    setDateTo("");
    void load({ month: value });
  }

  function loadRange() {
    void load({ dateFrom, dateTo });
  }

  function downloadPdf() {
    if (!customer?.id) return;
    window.open(api.customerStatementPdfUrl(customer.id, query), "_blank", "noopener");
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="customer-statement-dialog">
        <DialogHeader>
          <div className="customer-detail-title-row">
            <div>
              <DialogTitle>{customerName(customer) || "客户对账单"}</DialogTitle>
              <DialogDescription className="sj-sr-only">客户对账单预览和下载</DialogDescription>
            </div>
            <Badge variant="outline">{statement?.period_label || month}</Badge>
          </div>
        </DialogHeader>

        <div className="customer-statement-controls">
          <div className="customer-month-grid customer-month-grid--compact">
            {months.map((item) => (
              <Button
                key={item.value}
                type="button"
                variant={!dateFrom && !dateTo && month === item.value ? "default" : "outline"}
                size="sm"
                onClick={() => selectMonth(item.value)}
              >
                {item.label}
              </Button>
            ))}
          </div>
          <FieldGroup className="customer-statement-range">
            <Field>
              <FieldLabel>开始日期</FieldLabel>
              <DatePicker value={dateFrom} onChange={setDateFrom} placeholder="选择开始日期" />
            </Field>
            <Field>
              <FieldLabel>结束日期</FieldLabel>
              <DatePicker value={dateTo} onChange={setDateTo} placeholder="选择结束日期" />
            </Field>
            <Button type="button" variant="outline" onClick={loadRange} disabled={loading || !dateFrom || !dateTo}>
              <RefreshCw data-icon="inline-start" />
              生成
            </Button>
          </FieldGroup>
        </div>

        {error ? <div className="form-error">{error}</div> : null}

        {statement ? (
          <div className="customer-statement-body">
            <div className="customer-statement-metrics">
              <div><span>期初余额</span><strong>{money(statement.opening_balance)}</strong></div>
              <div><span>本期销售</span><strong>{money(statement.sales_amount)}</strong></div>
              <div><span>收款/充值</span><strong>{money(statement.receipt_amount)}</strong></div>
              <div><span>结款</span><strong>{money(statement.settlement_amount)}</strong></div>
              <div><span>未结金额</span><strong>{money(statement.unpaid_amount)}</strong></div>
              <div><span>期末余额</span><strong>{money(statement.ending_balance)}</strong></div>
            </div>

            <section className="customer-statement-section">
              <header>
                <strong>销售明细</strong>
                <span>{statement.sales_count} 单 · {statement.sales_quantity} 套</span>
              </header>
              <div className="customer-table-wrap">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>日期</TableHead>
                      <TableHead>单号</TableHead>
                      <TableHead>商品</TableHead>
                      <TableHead>颜色/规格</TableHead>
                      <TableHead>数量</TableHead>
                      <TableHead>单价</TableHead>
                      <TableHead>金额</TableHead>
                      <TableHead>付款</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {statement.sales.flatMap((order) => {
                      const rows = order.items?.length ? order.items : [{ title: "销售单明细", color: "", quantity: order.total_quantity, unit_price: "", amount: order.receivable_amount }];
                      return rows.map((item, index) => (
                        <TableRow key={`${order.id}-${index}`}>
                          <TableCell>{shortDate(order.sales_at)}</TableCell>
                          <TableCell>{order.sales_no || order.id}</TableCell>
                          <TableCell>{item.title || "商品"}</TableCell>
                          <TableCell>{item.color || "默认颜色"}</TableCell>
                          <TableCell>{item.quantity || 0}</TableCell>
                          <TableCell>{item.unit_price ? money(item.unit_price) : "-"}</TableCell>
                          <TableCell><strong>{money(item.amount || order.receivable_amount)}</strong></TableCell>
                          <TableCell>{[order.pay_status_text, order.pay_type_text].filter(Boolean).join(" / ") || "-"}</TableCell>
                        </TableRow>
                      ));
                    })}
                  </TableBody>
                </Table>
              </div>
              {!statement.sales.length ? (
                <Empty>
                  <EmptyHeader>
                    <EmptyTitle>没有销售明细</EmptyTitle>
                    <EmptyDescription>当前周期没有销售单。</EmptyDescription>
                  </EmptyHeader>
                </Empty>
              ) : null}
            </section>

            <section className="customer-statement-section">
              <header>
                <strong>收款/余额流水</strong>
                <span>{statement.ledger_count} 条</span>
              </header>
              <div className="customer-table-wrap">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>日期</TableHead>
                      <TableHead>类型</TableHead>
                      <TableHead>方式</TableHead>
                      <TableHead>金额</TableHead>
                      <TableHead>抵扣</TableHead>
                      <TableHead>余额影响</TableHead>
                      <TableHead>操作人</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {statement.ledger.map((item) => (
                      <TableRow key={item.id}>
                        <TableCell>{shortDate(item.created_at)}</TableCell>
                        <TableCell>{item.entry_type_text || item.entry_type}</TableCell>
                        <TableCell>{item.pay_type_text || "-"}</TableCell>
                        <TableCell>{money(item.amount)}</TableCell>
                        <TableCell>{money(item.applied_amount)}</TableCell>
                        <TableCell><strong>{money(item.balance_delta)}</strong></TableCell>
                        <TableCell>{item.created_by_name || "未记录"}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
              {!statement.ledger.length ? (
                <Empty>
                  <EmptyHeader>
                    <EmptyTitle>没有余额流水</EmptyTitle>
                    <EmptyDescription>当前周期没有收款、结款或余额调整。</EmptyDescription>
                  </EmptyHeader>
                </Empty>
              ) : null}
            </section>
          </div>
        ) : null}

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>关闭</Button>
          <Button type="button" onClick={downloadPdf} disabled={!statement || loading}>
            <Download data-icon="inline-start" />
            下载PDF
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export { CustomerStatementDialog };
