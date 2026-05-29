import { useEffect, useMemo, useState } from "react";
import { Eye, Printer, Trash2 } from "lucide-react";

import { api } from "@/api";
import {
  SalesDeleteDialog,
  SalesOrderDetailDialog
} from "@/components/business/sales-list";
import { hasPermission } from "@/lib/permissions";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle
} from "@/components/ui/dialog";
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationNext,
  PaginationPrevious
} from "@/components/ui/pagination";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from "@/components/ui/table";
import type {
  AuthUser,
  CustomerBalanceActionPayload,
  CustomerBalanceLedgerItem,
  CustomerBalanceSummary,
  CustomerItem,
  CustomerSalesItem,
  CustomerSalesSummary,
  SalesCard,
  SalesDetail,
  SalesPaymentUpdatePayload
} from "@/types";
import { CustomerBalanceActionDialog } from "./customer-balance-action-dialog";
import { CustomerFormDialog } from "./customer-form-dialog";
import { CustomerStatementDialog } from "./customer-statement-dialog";
import {
  customerName,
  customerPhone,
  displayDate,
  money,
  moneyNumber,
  monthOptions,
  shortDate
} from "./utils";

const ledgerPageSize = 12;
const salesPageSize = 12;
type CustomerSalesPayStatus = "all" | "unsettled" | "paid" | "monthly" | "unpaid";

type Props = {
  customer: CustomerItem | null;
  currentUser?: AuthUser;
  initialTab?: string;
  onClose: () => void;
  onChanged: (customer?: CustomerItem) => void;
};

function CustomerDetailDialog({ customer, currentUser, initialTab = "overview", onClose, onChanged }: Props) {
  const [current, setCurrent] = useState<CustomerItem | null>(customer);
  const [tab, setTab] = useState(initialTab);
  const [sales, setSales] = useState<CustomerSalesItem[]>([]);
  const [salesSummary, setSalesSummary] = useState<CustomerSalesSummary | null>(null);
  const [salesPage, setSalesPage] = useState(1);
  const [salesTotal, setSalesTotal] = useState(0);
  const [salesPayStatus, setSalesPayStatus] = useState<CustomerSalesPayStatus>("all");
  const [ledger, setLedger] = useState<CustomerBalanceLedgerItem[]>([]);
  const [ledgerSummary, setLedgerSummary] = useState<CustomerBalanceSummary | null>(null);
  const [ledgerPage, setLedgerPage] = useState(1);
  const [ledgerTotal, setLedgerTotal] = useState(0);
  const [period, setPeriod] = useState("");
  const [month, setMonth] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [action, setAction] = useState<CustomerBalanceActionPayload["action"] | null>(null);
  const [detail, setDetail] = useState<SalesDetail | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<SalesCard | SalesDetail | null>(null);
  const [busySalesId, setBusySalesId] = useState<number | null>(null);
  const [editOpen, setEditOpen] = useState(false);
  const [statementOpen, setStatementOpen] = useState(false);
  const months = useMemo(() => monthOptions(), []);
  const selected = current || customer;
  const selectedName = customerName(selected);
  const balance = moneyNumber(ledgerSummary?.balance_amount || selected?.balance_amount);
  const canAdjustBalance = hasPermission(currentUser, "调余额");
  const salesPageCount = Math.max(1, Math.ceil(salesTotal / salesPageSize));
  const ledgerPageCount = Math.max(1, Math.ceil(ledgerTotal / ledgerPageSize));

  async function loadDetail(
    nextPeriod = period,
    nextMonth = month,
    target = selected,
    nextSalesPage = 1,
    nextPayStatus: CustomerSalesPayStatus = salesPayStatus
  ) {
    if (!target) return;
    setLoading(true);
    setError("");
    try {
      const [salesData, ledgerData] = await Promise.all([
        api.customerSales(target.id, {
          page: nextSalesPage,
          pageSize: salesPageSize,
          period: nextPeriod,
          month: nextMonth,
          payStatus: nextPayStatus
        }),
        api.customerBalanceLedger(target.id, 1, ledgerPageSize)
      ]);
      setSales(salesData.list || []);
      setSalesSummary(salesData.summary || null);
      setSalesPage(salesData.page || nextSalesPage);
      setSalesTotal(salesData.total || 0);
      setLedger(ledgerData.list || []);
      setLedgerSummary(ledgerData.summary || null);
      setLedgerPage(1);
      setLedgerTotal(ledgerData.total || 0);
      if (ledgerData.summary) {
        setCurrent((prev) => (
          prev && prev.id === target.id
            ? { ...prev, balance_amount: ledgerData.summary.balance_amount }
            : prev
        ));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "客户详情加载失败");
    } finally {
      setLoading(false);
    }
  }

  async function loadSalesPage(
    nextPage: number,
    target = selected,
    nextPeriod = period,
    nextMonth = month,
    nextPayStatus: CustomerSalesPayStatus = salesPayStatus
  ) {
    if (!target) return;
    const safePage = Math.max(1, Math.min(salesPageCount, nextPage));
    setLoading(true);
    setError("");
    try {
      const salesData = await api.customerSales(target.id, {
        page: safePage,
        pageSize: salesPageSize,
        period: nextPeriod,
        month: nextMonth,
        payStatus: nextPayStatus
      });
      setSales(salesData.list || []);
      setSalesSummary(salesData.summary || null);
      setSalesPage(salesData.page || safePage);
      setSalesTotal(salesData.total || 0);
    } catch (err) {
      setError(err instanceof Error ? err.message : "销售记录加载失败");
    } finally {
      setLoading(false);
    }
  }

  async function loadLedgerPage(nextPage: number, target = selected) {
    if (!target) return;
    const safePage = Math.max(1, Math.min(ledgerPageCount, nextPage));
    setLoading(true);
    setError("");
    try {
      const ledgerData = await api.customerBalanceLedger(target.id, safePage, ledgerPageSize);
      setLedger(ledgerData.list || []);
      setLedgerSummary(ledgerData.summary || null);
      setLedgerPage(ledgerData.page || safePage);
      setLedgerTotal(ledgerData.total || 0);
      if (ledgerData.summary) {
        setCurrent((prev) => (
          prev && prev.id === target.id
            ? { ...prev, balance_amount: ledgerData.summary.balance_amount }
            : prev
        ));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "余额明细加载失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    setCurrent(customer);
    setPeriod("");
    setMonth("");
    setSales([]);
    setLedger([]);
    setSalesSummary(null);
    setLedgerSummary(null);
    setSalesPage(1);
    setSalesTotal(0);
    setSalesPayStatus("all");
    setLedgerPage(1);
    setLedgerTotal(0);
    setNotice("");
    setTab(initialTab || "overview");
    if (customer) void loadDetail("", "", customer, 1, "all");
  }, [customer?.id, initialTab]);

  function changePeriod(nextPeriod: string, nextMonth = "") {
    setPeriod(nextPeriod);
    setMonth(nextMonth);
    setSalesPage(1);
    void loadDetail(nextPeriod, nextMonth, selected, 1, salesPayStatus);
  }

  function changeSalesPayStatus(nextPayStatus: CustomerSalesPayStatus) {
    setSalesPayStatus(nextPayStatus);
    setSalesPage(1);
    void loadDetail(period, month, selected, 1, nextPayStatus);
  }

  async function toggleMonthly() {
    if (!selected) return;
    const next = !Number(selected.is_monthly_customer || 0);
    setError("");
    setNotice("");
    try {
      await api.updateCustomerMonthly(selected.id, next);
      const updated = { ...selected, is_monthly_customer: next ? 1 : 0 };
      setCurrent(updated);
      onChanged(updated);
      setNotice(next ? "已设为月结客户" : "已取消月结");
    } catch (err) {
      setError(err instanceof Error ? err.message : "月结设置失败");
    }
  }

  async function openSalesDetail(id: number) {
    if (!id) return;
    setError("");
    try {
      setDetail(await api.salesDetail(id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "销售单详情加载失败");
    }
  }

  async function printSales(id: number) {
    if (!id) return;
    setBusySalesId(id);
    setError("");
    setNotice("");
    try {
      await api.createSalesPrintTask(id);
      setNotice("打印任务已创建，等待本地打印程序处理");
    } catch (err) {
      setError(err instanceof Error ? err.message : "打印任务创建失败");
    } finally {
      setBusySalesId(null);
    }
  }

  function previewSales(id: number) {
    if (!id) return;
    window.open(`/api/sales/${encodeURIComponent(id)}/print-html?auto=0`, "_blank", "noopener");
  }

  async function updateSalesPayment(id: number, payload: SalesPaymentUpdatePayload) {
    if (!id) return;
    setBusySalesId(id);
    setError("");
    setNotice("");
    try {
      const result = await api.updateSalesPayment(id, payload);
      const paymentText = [result.pay_status_text, result.pay_type_text].filter(Boolean).join(" / ") || "已更新";
      setNotice(`销售单收款方式已更新：${paymentText}`);
      setDetail(await api.salesDetail(id));
      await loadDetail(period, month, selected, salesPage, salesPayStatus);
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "收款方式更新失败");
      throw err;
    } finally {
      setBusySalesId(null);
    }
  }

  async function confirmDeleteSales() {
    const id = Number(deleteTarget?.id || deleteTarget?.sales_id || 0);
    if (!id) return;
    setBusySalesId(id);
    setError("");
    setNotice("");
    try {
      await api.deleteSales(id);
      setNotice("销售单已删除，库存和余额已按服务层规则回滚");
      setDeleteTarget(null);
      if (detail && Number(detail.id || detail.sales_id || 0) === id) setDetail(null);
      await loadDetail(period, month, selected, salesPage, salesPayStatus);
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "销售单删除失败");
    } finally {
      setBusySalesId(null);
    }
  }

  function afterBalanceSaved() {
    void loadDetail(period, month, selected, salesPage, salesPayStatus);
    onChanged();
  }

  return (
    <Dialog
      open={Boolean(customer)}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent className="customer-detail-dialog">
        <DialogHeader>
          <div className="customer-detail-title-row">
            <div>
              <DialogTitle>{selectedName || "客户详情"}</DialogTitle>
              <DialogDescription>{customerPhone(selected) || "未绑定电话"}</DialogDescription>
            </div>
            <div className="customer-detail-badges">
              <Badge variant={Number(selected?.is_monthly_customer || 0) ? "secondary" : "outline"}>
                {Number(selected?.is_monthly_customer || 0) ? "月结客户" : "普通客户"}
              </Badge>
              <Badge variant={balance < 0 ? "destructive" : "outline"}>{money(balance)}</Badge>
            </div>
          </div>
        </DialogHeader>

        {error ? <div className="form-error">{error}</div> : null}
        {notice ? <div className="form-success">{notice}</div> : null}

        <Tabs value={tab} onValueChange={setTab} className="customer-detail-tabs">
          <TabsList>
            <TabsTrigger value="overview">概览</TabsTrigger>
            <TabsTrigger value="sales">销售单</TabsTrigger>
            <TabsTrigger value="statement">对账单</TabsTrigger>
            <TabsTrigger value="ledger">余额明细</TabsTrigger>
            <TabsTrigger value="profile">资料</TabsTrigger>
          </TabsList>

          <TabsContent value="overview">
            <div className="customer-detail-metrics">
              <div><span>最近下单</span><strong>{displayDate(selected?.latest_order_at)}</strong></div>
              <div><span>最近金额</span><strong>{money(selected?.latest_order_amount)}</strong></div>
              <div><span>近1年消费</span><strong>{money(selected?.year_amount)}</strong></div>
              <div><span>当前余额</span><strong className={balance < 0 ? "customer-money-negative" : ""}>{money(balance)}</strong></div>
              <div><span>钱包余额</span><strong>{money(ledgerSummary?.wallet_amount)}</strong></div>
              <div><span>未结欠款</span><strong>{money(ledgerSummary?.debt_amount)}</strong></div>
            </div>
            <div className="customer-detail-actions">
              <Button type="button" variant="outline" onClick={() => setAction("receipt")}>收款</Button>
              <Button type="button" variant="outline" onClick={() => setAction("recharge")}>充值</Button>
              <Button type="button" onClick={() => setAction("settlement")}>结款</Button>
              <Button type="button" variant="outline" disabled={!canAdjustBalance} onClick={() => setAction("adjust")}>调余额</Button>
              <Button type="button" variant="outline" onClick={toggleMonthly}>
                {Number(selected?.is_monthly_customer || 0) ? "取消月结" : "设为月结"}
              </Button>
            </div>
          </TabsContent>

          <TabsContent value="sales">
            <div className="customer-tab-header">
              <div>
                <strong>{salesSummary?.label || "全部销售单"}</strong>
                <span>共 {salesTotal || salesSummary?.total || 0} 单 · 第 {Math.min(salesPage, salesPageCount)}/{salesPageCount} 页 · 合计 {money(salesSummary?.total_amount)} · 未结 {money(salesSummary?.unpaid_amount)}</span>
              </div>
              <Button type="button" variant="outline" size="sm" onClick={() => setStatementOpen(true)}>
                导出账单
              </Button>
            </div>
            <div className="customer-filter-row">
              <Button size="sm" type="button" variant={!period && !month ? "default" : "outline"} onClick={() => changePeriod("", "")}>全部</Button>
              <Button size="sm" type="button" variant={period === "1m" ? "default" : "outline"} onClick={() => changePeriod("1m", "")}>近1个月</Button>
              <Button size="sm" type="button" variant={period === "3m" ? "default" : "outline"} onClick={() => changePeriod("3m", "")}>近3个月</Button>
            </div>
            <div className="customer-filter-row customer-filter-row--compact">
              <Button size="sm" type="button" variant={salesPayStatus === "all" ? "default" : "outline"} onClick={() => changeSalesPayStatus("all")}>全部状态</Button>
              <Button size="sm" type="button" variant={salesPayStatus === "unsettled" ? "default" : "outline"} onClick={() => changeSalesPayStatus("unsettled")}>未结</Button>
              <Button size="sm" type="button" variant={salesPayStatus === "paid" ? "default" : "outline"} onClick={() => changeSalesPayStatus("paid")}>已付款</Button>
              <Button size="sm" type="button" variant={salesPayStatus === "monthly" ? "default" : "outline"} onClick={() => changeSalesPayStatus("monthly")}>月结</Button>
              <Button size="sm" type="button" variant={salesPayStatus === "unpaid" ? "default" : "outline"} onClick={() => changeSalesPayStatus("unpaid")}>未付款</Button>
            </div>
            <div className="customer-month-grid customer-month-grid--compact">
              {months.map((item) => (
                <Button
                  key={item.value}
                  type="button"
                  variant={month === item.value ? "default" : "outline"}
                  size="sm"
                  onClick={() => changePeriod("", item.value)}
                >
                  {item.label}
                </Button>
              ))}
            </div>
            <div className="customer-table-wrap">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>单号</TableHead>
                    <TableHead>时间</TableHead>
                    <TableHead>商品摘要</TableHead>
                    <TableHead>数量</TableHead>
                    <TableHead>金额</TableHead>
                    <TableHead>付款</TableHead>
                    <TableHead>开单人</TableHead>
                    <TableHead>操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {sales.map((order) => (
                    <TableRow key={order.id} className="customer-sales-row" onClick={() => openSalesDetail(order.id)}>
                      <TableCell>{order.sales_no || order.id}</TableCell>
                      <TableCell>{shortDate(order.sales_at)}</TableCell>
                      <TableCell>{order.items_preview || "销售单明细"}</TableCell>
                      <TableCell>{order.total_quantity || 0}</TableCell>
                      <TableCell><strong>{money(order.receivable_amount)}</strong></TableCell>
                      <TableCell>{[order.pay_status_text, order.pay_type_text].filter(Boolean).join(" / ") || "-"}</TableCell>
                      <TableCell>{order.created_by_name || "未记录"}</TableCell>
                      <TableCell>
                        <div className="customer-row-actions" onClick={(event) => event.stopPropagation()}>
                          <Button size="icon-sm" variant="ghost" aria-label="详情" onClick={() => openSalesDetail(order.id)}><Eye /></Button>
                          <Button size="icon-sm" variant="ghost" aria-label="打印" onClick={() => printSales(order.id)}><Printer /></Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
            {!loading && !sales.length ? (
              <Empty>
                <EmptyHeader>
                  <EmptyTitle>当前筛选没有销售单</EmptyTitle>
                  <EmptyDescription>换一个月份或查看全部销售单。</EmptyDescription>
                </EmptyHeader>
              </Empty>
            ) : null}
            <Pagination className="sales-pagination-row">
              <PaginationContent>
                <PaginationItem>
                  <PaginationPrevious disabled={salesPage <= 1 || loading} onClick={() => void loadSalesPage(salesPage - 1)}>上一页</PaginationPrevious>
                </PaginationItem>
                <PaginationItem>
                  <Badge className="sales-page-count" variant="outline">{Math.min(salesPage, salesPageCount)} / {salesPageCount}</Badge>
                </PaginationItem>
                <PaginationItem>
                  <PaginationNext disabled={salesPage >= salesPageCount || loading} onClick={() => void loadSalesPage(salesPage + 1)}>下一页</PaginationNext>
                </PaginationItem>
              </PaginationContent>
            </Pagination>
          </TabsContent>

          <TabsContent value="statement">
            <div className="customer-statement-tab">
              <div className="customer-detail-metrics">
                <div><span>当前筛选</span><strong>{salesSummary?.label || "全部销售单"}</strong></div>
                <div><span>销售单</span><strong>{salesSummary?.total || 0} 单</strong></div>
                <div><span>合计金额</span><strong>{money(salesSummary?.total_amount)}</strong></div>
                <div><span>未结金额</span><strong className="customer-money-negative">{money(salesSummary?.unpaid_amount)}</strong></div>
              </div>
              <div className="customer-detail-actions">
                <Button type="button" onClick={() => setStatementOpen(true)}>打开对账单</Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => {
                    if (!selected?.id) return;
                    const query = month ? { month } : undefined;
                    window.open(api.customerStatementPdfUrl(selected.id, query), "_blank", "noopener");
                  }}
                >
                  下载PDF
                </Button>
              </div>
            </div>
          </TabsContent>

          <TabsContent value="ledger">
            <div className="customer-tab-header">
              <div>
                <strong>余额明细</strong>
                <span>钱包 {money(ledgerSummary?.wallet_amount)} · 欠款 {money(ledgerSummary?.debt_amount)} · 余额 {money(ledgerSummary?.balance_amount)} · 共 {ledgerTotal} 条</span>
              </div>
            </div>
            <div className="customer-table-wrap">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>类型</TableHead>
                    <TableHead>月份/方式</TableHead>
                    <TableHead>金额</TableHead>
                    <TableHead>余额影响</TableHead>
                    <TableHead>操作人</TableHead>
                    <TableHead>时间</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {ledger.map((item) => (
                    <TableRow key={item.id}>
                      <TableCell>{item.entry_type_text || item.entry_type}</TableCell>
                      <TableCell>{[item.related_month, item.pay_type_text].filter(Boolean).join(" / ") || "-"}</TableCell>
                      <TableCell>{money(item.amount || item.applied_amount)}</TableCell>
                      <TableCell><strong className={moneyNumber(item.balance_delta) < 0 ? "customer-money-negative" : ""}>{money(item.balance_delta)}</strong></TableCell>
                      <TableCell>{item.created_by_name || "未记录"}</TableCell>
                      <TableCell>{displayDate(item.created_at)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
            <Pagination className="ledger-pagination-row">
              <PaginationContent>
                <PaginationItem>
                  <PaginationPrevious disabled={ledgerPage <= 1 || loading} onClick={() => void loadLedgerPage(ledgerPage - 1)}>上一页</PaginationPrevious>
                </PaginationItem>
                <PaginationItem>
                  <Badge className="ledger-page-count" variant="outline">{Math.min(ledgerPage, ledgerPageCount)} / {ledgerPageCount}</Badge>
                </PaginationItem>
                <PaginationItem>
                  <PaginationNext disabled={ledgerPage >= ledgerPageCount || loading} onClick={() => void loadLedgerPage(ledgerPage + 1)}>下一页</PaginationNext>
                </PaginationItem>
              </PaginationContent>
            </Pagination>
            {!loading && !ledger.length ? (
              <Empty>
                <EmptyHeader>
                  <EmptyTitle>还没有余额流水</EmptyTitle>
                  <EmptyDescription>收款、充值、结款或调余额后会出现在这里。</EmptyDescription>
                </EmptyHeader>
              </Empty>
            ) : null}
          </TabsContent>

          <TabsContent value="profile">
            <div className="customer-tab-header">
              <div>
                <strong>客户资料</strong>
              </div>
              <Button type="button" variant="outline" size="sm" onClick={() => setEditOpen(true)}>
                编辑资料
              </Button>
            </div>
            <div className="customer-profile-grid">
              <div><span>客户名称</span><strong>{selectedName || "-"}</strong></div>
              <div><span>联系人</span><strong>{selected?.contacts_name || "-"}</strong></div>
              <div><span>手机号</span><strong>{customerPhone(selected) || "未绑定"}</strong></div>
              <div><span>客户类型</span><strong>{Number(selected?.is_monthly_customer || 0) ? "月结客户" : "普通客户"}</strong></div>
              <div><span>销售单数</span><strong>{selected?.sales_count || 0} 单</strong></div>
              <div><span>地址</span><strong>{selected?.address || "-"}</strong></div>
            </div>
          </TabsContent>
        </Tabs>

        <CustomerBalanceActionDialog
          action={action}
          customer={selected}
          onClose={() => setAction(null)}
          onSaved={afterBalanceSaved}
        />
        <CustomerFormDialog
          mode="edit"
          open={editOpen}
          customer={selected}
          onOpenChange={setEditOpen}
          onSaved={(updated) => {
            if (updated) {
              setCurrent(updated);
              onChanged(updated);
              void loadDetail(period, month, updated, salesPage, salesPayStatus);
            }
          }}
        />
        <CustomerStatementDialog
          customer={selected || null}
          open={statementOpen}
          initialMonth={month || undefined}
          onOpenChange={setStatementOpen}
        />
        <SalesOrderDetailDialog
          order={detail}
          busySalesId={busySalesId}
          onClose={() => setDetail(null)}
          onPrint={(id) => void printSales(id)}
          onPreview={previewSales}
          onUpdatePayment={updateSalesPayment}
          onDelete={(order) => setDeleteTarget(order)}
        />
        <SalesDeleteDialog
          order={deleteTarget}
          busy={Boolean(deleteTarget && busySalesId === Number(deleteTarget.id || deleteTarget.sales_id || 0))}
          onClose={() => setDeleteTarget(null)}
          onConfirm={() => void confirmDeleteSales()}
        />
        {busySalesId && !detail ? <Badge className="customer-floating-badge">处理中</Badge> : null}
      </DialogContent>
    </Dialog>
  );
}

export { CustomerDetailDialog };
