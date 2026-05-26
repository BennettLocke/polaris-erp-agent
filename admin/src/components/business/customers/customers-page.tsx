import { useEffect, useMemo, useState } from "react";
import { Plus, RefreshCw, Search } from "lucide-react";

import { api } from "@/api";
import { CustomerBalanceActionDialog } from "@/components/business/customers/customer-balance-action-dialog";
import { CustomerCardGrid } from "@/components/business/customers/customer-card-grid";
import { CustomerDetailDialog } from "@/components/business/customers/customer-detail-dialog";
import { CustomerFormDialog } from "@/components/business/customers/customer-form-dialog";
import { Toolbar } from "@/components/layout/toolbar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationNext,
  PaginationPrevious
} from "@/components/ui/pagination";
import type { CustomerBalanceActionPayload, CustomerItem, CustomerListSummary } from "@/types";
import {
  customerFilterOptions,
  money,
  normalizeCustomerSummary,
  type CustomerFilter
} from "./utils";

const customerPageSize = 12;

function CustomersPage() {
  const [keyword, setKeyword] = useState("");
  const [items, setItems] = useState<CustomerItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [remoteSummary, setRemoteSummary] = useState<CustomerListSummary | null>(null);
  const [filter, setFilter] = useState<CustomerFilter>("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [selected, setSelected] = useState<CustomerItem | null>(null);
  const [detailTab, setDetailTab] = useState("overview");
  const [actionTarget, setActionTarget] = useState<CustomerItem | null>(null);
  const [action, setAction] = useState<CustomerBalanceActionPayload["action"] | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const summary = useMemo(() => normalizeCustomerSummary(remoteSummary, items), [remoteSummary, items]);
  const pageCount = Math.max(1, Math.ceil(total / customerPageSize));

  async function load(nextPage = page, nextKeyword = keyword, nextFilter = filter) {
    setLoading(true);
    setError("");
    try {
      const data = await api.customers({
        keyword: nextKeyword,
        page: nextPage,
        pageSize: customerPageSize,
        filter: nextFilter
      });
      const nextList = data.list || [];
      const nextTotal = data.total || 0;
      const nextPageCount = Math.max(1, Math.ceil(nextTotal / customerPageSize));
      if (!nextList.length && nextTotal > 0 && nextPage > nextPageCount) {
        void load(nextPageCount, nextKeyword, nextFilter);
        return;
      }
      setItems(nextList);
      setTotal(nextTotal);
      setRemoteSummary(data.summary || null);
      setPage(data.page || nextPage);
    } catch (err) {
      setError(err instanceof Error ? err.message : "客户加载失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load(1, "", "all");
  }, []);

  useEffect(() => {
    if (page > pageCount) setPage(pageCount);
  }, [page, pageCount]);

  function openDetail(customer: CustomerItem, tab = "overview") {
    setDetailTab(tab);
    setSelected(customer);
  }

  function openAction(customer: CustomerItem, nextAction: CustomerBalanceActionPayload["action"]) {
    setActionTarget(customer);
    setAction(nextAction);
  }

  async function toggleMonthly(customer: CustomerItem) {
    const next = !Number(customer.is_monthly_customer || 0);
    setError("");
    setNotice("");
    try {
      await api.updateCustomerMonthly(customer.id, next);
      await load(page, keyword, filter);
      setNotice(next ? "已设为月结客户" : "已取消月结");
    } catch (err) {
      setError(err instanceof Error ? err.message : "月结设置失败");
    }
  }

  function afterBalanceSaved() {
    setNotice("客户余额已更新");
    void load(page, keyword, filter);
  }

  function searchCustomers() {
    void load(1, keyword, filter);
  }

  function applyFilter(nextFilter: CustomerFilter) {
    setFilter(nextFilter);
    void load(1, keyword, nextFilter);
  }

  function goToPage(nextPage: number) {
    const safePage = Math.max(1, Math.min(pageCount, nextPage));
    void load(safePage, keyword, filter);
  }

  return (
    <Card className="customers-page data-panel">
      <CardHeader className="customers-page-header">
        <Toolbar
          title={(
            <div className="customers-page-title-block">
              <CardTitle>客户工作台</CardTitle>
              <CardDescription>客户余额、月结、销售单和收款动作统一从服务层读取。</CardDescription>
            </div>
          )}
          actions={(
            <CardAction className="customers-page-actions">
              <span className="customers-page-count">第 {Math.min(page, pageCount)} / {pageCount} 页 · 共 {total} 个客户</span>
              <Button variant="outline" size="sm" type="button" onClick={() => load(page, keyword, filter)}>
                <RefreshCw data-icon="inline-start" /> 刷新
              </Button>
              <Button size="sm" type="button" onClick={() => setCreateOpen(true)}>
                <Plus data-icon="inline-start" /> 创建客户
              </Button>
            </CardAction>
          )}
        />
      </CardHeader>
      <CardContent>
        <div className="customer-summary-strip">
          <div><span>当前筛选</span><strong>{summary.total}</strong></div>
          <div><span>月结客户</span><strong>{summary.monthly}</strong></div>
          <div><span>有欠款</span><strong>{summary.debt}</strong></div>
          <div><span>预存余额</span><strong>{money(summary.creditAmount)}</strong></div>
          <div><span>欠款合计</span><strong className="customer-money-negative">{money(summary.debtAmount)}</strong></div>
        </div>

        <div className="customer-warning-strip">
          <Button type="button" variant={summary.normalDebt ? "outline" : "ghost"} size="sm" onClick={() => applyFilter("normal_debt")}>
            <Badge variant={summary.normalDebt ? "destructive" : "outline"}>{summary.normalDebt}</Badge>
            普通客户欠款
          </Button>
          <Button type="button" variant={summary.noPhone ? "outline" : "ghost"} size="sm" onClick={() => applyFilter("no_phone")}>
            <Badge variant={summary.noPhone ? "secondary" : "outline"}>{summary.noPhone}</Badge>
            未绑定电话
          </Button>
          <Button type="button" variant={summary.monthlyDebt ? "outline" : "ghost"} size="sm" onClick={() => applyFilter("debt")}>
            <Badge variant="outline">{summary.monthlyDebt}</Badge>
            月结未结
          </Button>
        </div>

        <form
          className="customer-toolbar"
          onSubmit={(event) => {
            event.preventDefault();
            searchCustomers();
          }}
        >
          <Input
            value={keyword}
            placeholder="搜索客户、电话"
            onChange={(event) => setKeyword(event.target.value)}
          />
          <Button type="submit" variant="outline">
            <Search data-icon="inline-start" /> 搜索
          </Button>
        </form>

        <div className="customer-filter-row">
          {customerFilterOptions.map((item) => (
            <Button
              key={item.value}
              type="button"
              size="sm"
              variant={filter === item.value ? "default" : "outline"}
              onClick={() => applyFilter(item.value)}
            >
              {item.label}
            </Button>
          ))}
        </div>

        {error ? <div className="form-error">{error}</div> : null}
        {notice ? <div className="form-success">{notice}</div> : null}

        <CustomerCardGrid
          customers={items}
          loading={loading}
          onOpenDetail={openDetail}
          onAction={openAction}
          onToggleMonthly={(customer) => void toggleMonthly(customer)}
        />
        <Pagination className="customers-pagination">
          <PaginationContent>
            <PaginationItem>
              <PaginationPrevious disabled={page <= 1 || loading} onClick={() => goToPage(page - 1)}>上一页</PaginationPrevious>
            </PaginationItem>
            <PaginationItem>
              <Badge variant="outline">{Math.min(page, pageCount)} / {pageCount}</Badge>
            </PaginationItem>
            <PaginationItem>
              <PaginationNext disabled={page >= pageCount || loading} onClick={() => goToPage(page + 1)}>下一页</PaginationNext>
            </PaginationItem>
          </PaginationContent>
        </Pagination>
      </CardContent>

      <CustomerDetailDialog
        customer={selected}
        initialTab={detailTab}
        onClose={() => setSelected(null)}
        onChanged={(updated) => {
          if (updated) {
            setItems((prev) => prev.map((item) => (item.id === updated.id ? { ...item, ...updated } : item)));
            setSelected(updated);
            return;
          }
          void load(page, keyword, filter);
        }}
      />
      <CustomerBalanceActionDialog
        action={action}
        customer={actionTarget}
        onClose={() => {
          setAction(null);
          setActionTarget(null);
        }}
        onSaved={afterBalanceSaved}
      />
      <CustomerFormDialog
        mode="create"
        open={createOpen}
        onOpenChange={setCreateOpen}
        onSaved={(created) => {
          setNotice(created?.existed ? "客户已存在，已选中" : "客户已创建");
          void load(1, keyword, filter);
          if (created?.id) {
            setSelected(created);
            setDetailTab("profile");
          }
        }}
      />
    </Card>
  );
}

export { CustomersPage };
