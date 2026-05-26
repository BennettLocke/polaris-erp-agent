import { useCallback, useEffect, useMemo, useState } from "react";
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

const CUSTOMER_CARD_MIN_WIDTH = 300;
const CUSTOMER_GRID_GAP = 12;
const CUSTOMER_PAGE_SIZE_MIN = 18;
const CUSTOMER_PAGE_SIZE_MAX = 72;
const CUSTOMER_PAGE_SIZE_BUFFER_ROWS = 1;
const CUSTOMER_CARD_ESTIMATED_HEIGHT = 220;
const CUSTOMER_GRID_TOP_FALLBACK = 430;
const CUSTOMER_PAGE_SIZE_RESIZE_DELAY = 160;

type CustomerPageSizeMetrics = {
  gridWidth: number;
  viewportHeight: number;
  gridTop: number;
  cardHeight?: number;
};

function clampCustomerPageSize(value: number) {
  return Math.min(CUSTOMER_PAGE_SIZE_MAX, Math.max(CUSTOMER_PAGE_SIZE_MIN, value));
}

function calculateCustomerPageSize({
  gridWidth,
  viewportHeight,
  gridTop,
  cardHeight = CUSTOMER_CARD_ESTIMATED_HEIGHT
}: CustomerPageSizeMetrics) {
  const safeCardHeight = Math.max(160, cardHeight);
  const columns = Math.max(
    1,
    Math.floor((Math.max(1, gridWidth) + CUSTOMER_GRID_GAP) / (CUSTOMER_CARD_MIN_WIDTH + CUSTOMER_GRID_GAP))
  );
  const availableHeight = Math.max(safeCardHeight, viewportHeight - gridTop - 72);
  const visibleRows = Math.max(2, Math.ceil(availableHeight / safeCardHeight));
  return clampCustomerPageSize(columns * (visibleRows + CUSTOMER_PAGE_SIZE_BUFFER_ROWS));
}

function initialCustomerPageSize() {
  if (typeof window === "undefined") return CUSTOMER_PAGE_SIZE_MIN;
  return calculateCustomerPageSize({
    gridWidth: Math.max(CUSTOMER_CARD_MIN_WIDTH, window.innerWidth - 320),
    viewportHeight: window.innerHeight,
    gridTop: CUSTOMER_GRID_TOP_FALLBACK
  });
}

function measuredCustomerPageSize(gridElement: HTMLDivElement | null) {
  if (typeof window === "undefined" || !gridElement) return CUSTOMER_PAGE_SIZE_MIN;
  const gridRect = gridElement.getBoundingClientRect();
  const firstCard = gridElement.querySelector(".customer-card-new") as HTMLElement | null;
  const cardHeight = firstCard?.getBoundingClientRect().height || CUSTOMER_CARD_ESTIMATED_HEIGHT;
  return calculateCustomerPageSize({
    gridWidth: gridRect.width,
    viewportHeight: window.innerHeight,
    gridTop: gridRect.top,
    cardHeight
  });
}

function customerPageRangeText(page: number, customerPageSize: number, total: number) {
  if (!total) return "共 0 个客户";
  const safePage = Math.max(1, page);
  const safePageSize = Math.max(1, customerPageSize);
  const start = Math.min(total, (safePage - 1) * safePageSize + 1);
  const end = Math.min(total, safePage * safePageSize);
  return `第 ${start}-${end} 位 / 共 ${total} 位`;
}

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
  const [customerPageSize, setCustomerPageSize] = useState(initialCustomerPageSize);
  const [gridElement, setGridElement] = useState<HTMLDivElement | null>(null);
  const gridRef = useCallback((node: HTMLDivElement | null) => {
    setGridElement(node);
  }, []);
  const summary = useMemo(() => normalizeCustomerSummary(remoteSummary, items), [remoteSummary, items]);
  const pageCount = Math.max(1, Math.ceil(total / customerPageSize));

  async function load(nextPage = page, nextKeyword = keyword, nextFilter = filter, nextPageSize = customerPageSize) {
    setLoading(true);
    setError("");
    try {
      const data = await api.customers({
        keyword: nextKeyword,
        page: nextPage,
        pageSize: nextPageSize,
        filter: nextFilter
      });
      const nextList = data.list || [];
      const nextTotal = data.total || 0;
      const nextPageCount = Math.max(1, Math.ceil(nextTotal / nextPageSize));
      if (!nextList.length && nextTotal > 0 && nextPage > nextPageCount) {
        void load(nextPageCount, nextKeyword, nextFilter, nextPageSize);
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

  useEffect(() => {
    if (!gridElement) return undefined;

    let resizeTimer = 0;
    const syncPageSize = () => {
      const nextPageSize = measuredCustomerPageSize(gridElement);
      setCustomerPageSize((currentPageSize) => {
        if (currentPageSize === nextPageSize) return currentPageSize;
        const firstItemIndex = Math.max(1, (page - 1) * currentPageSize + 1);
        const nextPage = Math.max(1, Math.ceil(firstItemIndex / nextPageSize));
        void load(nextPage, keyword, filter, nextPageSize);
        return nextPageSize;
      });
    };
    const scheduleSync = () => {
      window.clearTimeout(resizeTimer);
      resizeTimer = window.setTimeout(syncPageSize, CUSTOMER_PAGE_SIZE_RESIZE_DELAY);
    };

    scheduleSync();
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(scheduleSync);
    observer?.observe(gridElement);
    window.addEventListener("resize", scheduleSync);
    return () => {
      window.clearTimeout(resizeTimer);
      observer?.disconnect();
      window.removeEventListener("resize", scheduleSync);
    };
  }, [gridElement, items.length, page, keyword, filter]);

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
              <span className="customers-page-count">
                {customerPageRangeText(Math.min(page, pageCount), customerPageSize, total)} · 第 {Math.min(page, pageCount)}/{pageCount} 页 · 每页 {customerPageSize}
              </span>
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
          gridRef={gridRef}
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
              <Badge variant="outline">{customerPageRangeText(Math.min(page, pageCount), customerPageSize, total)}</Badge>
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
