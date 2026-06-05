import { useEffect, useMemo, useState } from "react";
import { BarChart3, RefreshCw } from "lucide-react";

import { api } from "@/api";
import { Toolbar } from "@/components/layout/toolbar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle
} from "@/components/ui/card";
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from "@/components/ui/table";
import type {
  AnalyticsHotProduct,
  AnalyticsRecentSale,
  AnalyticsSalesOverview,
  AnalyticsSalesTrendItem
} from "@/types";

const DEFAULT_PERIOD = "7d";

const periodOptions = [
  { value: "today", label: "今日" },
  { value: "week", label: "本周" },
  { value: "month", label: "本月" },
  { value: "7d", label: "近7天" },
  { value: "30d", label: "近30天" }
];

function money(value?: string | number) {
  const num = Number(value ?? 0);
  return Number.isFinite(num) ? `¥${num.toFixed(2)}` : `¥${value || "0.00"}`;
}

function qty(value?: string | number) {
  const num = Number(value ?? 0);
  if (!Number.isFinite(num)) return String(value || 0);
  return Number.isInteger(num) ? String(num) : num.toFixed(2);
}

function shortDate(value?: string) {
  if (!value) return "未记录";
  return value.length > 10 ? value.slice(5, 10) : value;
}

function fullTime(value?: string) {
  if (!value) return "未记录";
  return value.length > 16 ? value.slice(0, 16) : value;
}

function kpiCards(overview: AnalyticsSalesOverview | null) {
  const kpi = overview?.kpi;
  return [
    { label: "销售额", value: money(kpi?.sales_amount), hint: "应收金额" },
    { label: "订单数", value: qty(kpi?.order_count), hint: "有效销售单" },
    { label: "销售件数", value: qty(kpi?.item_quantity), hint: "商品数量" },
    { label: "客户数", value: qty(kpi?.customer_count), hint: "去重客户" },
    { label: "客单价", value: money(kpi?.average_order_amount), hint: "销售额 / 订单数" }
  ];
}

function DataKpiGrid({ overview, loading }: { overview: AnalyticsSalesOverview | null; loading: boolean }) {
  return (
    <div className="data-kpi-grid">
      {kpiCards(overview).map((item) => (
        <Card className="data-kpi-card" key={item.label}>
          <CardContent>
            <span>{item.label}</span>
            {loading ? <Skeleton className="data-kpi-skeleton" /> : <strong>{item.value}</strong>}
            <em>{item.hint}</em>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function TrendTable({ items }: { items: AnalyticsSalesTrendItem[] }) {
  const maxAmount = useMemo(
    () => Math.max(...items.map((item) => Number(item.sales_amount_value ?? item.sales_amount ?? 0)), 1),
    [items]
  );
  if (!items.length) {
    return (
      <Empty>
        <EmptyHeader>
          <EmptyTitle>暂无趋势数据</EmptyTitle>
          <EmptyDescription>当前周期还没有有效销售单。</EmptyDescription>
        </EmptyHeader>
      </Empty>
    );
  }
  return (
    <Table className="data-trend-table">
      <TableHeader>
        <TableRow>
          <TableHead>日期</TableHead>
          <TableHead>销售额</TableHead>
          <TableHead>订单</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {items.map((item) => {
          const amount = Number(item.sales_amount_value ?? item.sales_amount ?? 0);
          const width = `${Math.max(6, Math.round((amount / maxAmount) * 100))}%`;
          return (
            <TableRow key={item.date}>
              <TableCell>{shortDate(item.date)}</TableCell>
              <TableCell>
                <div className="data-trend-amount">
                  <span style={{ width }} />
                  <strong>{money(item.sales_amount)}</strong>
                </div>
              </TableCell>
              <TableCell>{item.order_count}</TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}

function HotProductsTable({ items }: { items: AnalyticsHotProduct[] }) {
  if (!items.length) {
    return (
      <Empty>
        <EmptyHeader>
          <EmptyTitle>暂无热销商品</EmptyTitle>
          <EmptyDescription>当前周期还没有可统计的商品销量。</EmptyDescription>
        </EmptyHeader>
      </Empty>
    );
  }
  return (
    <Table className="data-hot-products-table">
      <TableHeader>
        <TableRow>
          <TableHead>商品</TableHead>
          <TableHead>颜色/SKU</TableHead>
          <TableHead>销量</TableHead>
          <TableHead>金额</TableHead>
          <TableHead>订单</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {items.map((item) => (
          <TableRow key={`${item.rank}-${item.product_id}-${item.sku_id}`}>
            <TableCell>
              <div className="data-product-cell">
                <strong>{item.title}</strong>
                <span>#{item.rank}</span>
              </div>
            </TableCell>
            <TableCell>
              <div className="data-muted-stack">
                <span>{item.color || "默认颜色"}</span>
                <em>{item.sku_no || "无编号"}</em>
              </div>
            </TableCell>
            <TableCell>{qty(item.sold_qty)}</TableCell>
            <TableCell>{money(item.amount)}</TableCell>
            <TableCell>{item.order_count}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function RecentSalesList({ items }: { items: AnalyticsRecentSale[] }) {
  if (!items.length) {
    return (
      <Empty>
        <EmptyHeader>
          <EmptyTitle>暂无最近销售</EmptyTitle>
          <EmptyDescription>当前周期还没有销售单。</EmptyDescription>
        </EmptyHeader>
      </Empty>
    );
  }
  return (
    <div className="data-recent-sales">
      {items.map((item) => (
        <button
          type="button"
          className="data-recent-sale"
          key={item.id || item.sales_no}
          onClick={() => {
            if (item.id) window.location.assign(`/admin/sales?keyword=${encodeURIComponent(item.sales_no || "")}`);
          }}
        >
          <span>
            <strong>{item.customer_name}</strong>
            <em>{item.product_summary}</em>
          </span>
          <span>
            <strong>{money(item.receivable_amount)}</strong>
            <em>{fullTime(item.sales_at)}</em>
          </span>
          <Badge variant="outline">{item.pay_status_text || "未记录"}</Badge>
        </button>
      ))}
    </div>
  );
}

export function DataPage() {
  const [period, setPeriod] = useState(DEFAULT_PERIOD);
  const [overview, setOverview] = useState<AnalyticsSalesOverview | null>(null);
  const [hotGiftBoxes, setHotGiftBoxes] = useState<AnalyticsHotProduct[]>([]);
  const [hotBags, setHotBags] = useState<AnalyticsHotProduct[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load(nextPeriod = period) {
    setLoading(true);
    setError("");
    try {
      const [overviewData, giftBoxData, bagData] = await Promise.all([
        api.analyticsSalesOverview(nextPeriod),
        api.analyticsHotProducts({ period: nextPeriod, limit: 8, dimension: "sku", categoryNames: ["礼盒"] }),
        api.analyticsHotProducts({ period: nextPeriod, limit: 8, dimension: "sku", categoryNames: ["泡袋"] })
      ]);
      setOverview(overviewData);
      setHotGiftBoxes(giftBoxData.items || []);
      setHotBags(bagData.items || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "销售数据加载失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load(DEFAULT_PERIOD);
  }, []);

  function changePeriod(nextPeriod: string) {
    setPeriod(nextPeriod);
    void load(nextPeriod);
  }

  return (
    <section className="data-page-shell">
      <Toolbar
        title={(
          <div className="data-page-title">
            <CardTitle>销售数据</CardTitle>
            <CardDescription>销售额、订单、客户和热销商品。</CardDescription>
          </div>
        )}
        actions={(
          <Button type="button" variant="outline" size="sm" onClick={() => void load(period)} disabled={loading}>
            <RefreshCw data-icon="inline-start" />
            刷新
          </Button>
        )}
      />

      <Card className="data-period-card">
        <CardContent>
          <div className="data-period-tabs" aria-label="销售数据周期">
            {periodOptions.map((item) => (
              <Button
                key={item.value}
                type="button"
                size="sm"
                variant={period === item.value ? "default" : "outline"}
                onClick={() => changePeriod(item.value)}
                disabled={loading && period === item.value}
              >
                {item.label}
              </Button>
            ))}
          </div>
          <Badge variant="secondary">
            <BarChart3 data-icon="inline-start" />
            {periodOptions.find((item) => item.value === period)?.label || "近7天"}
          </Badge>
        </CardContent>
      </Card>

      {error ? <div className="form-error">{error}</div> : null}
      <DataKpiGrid overview={overview} loading={loading} />

      <div className="data-main-grid">
        <Card className="data-section-card">
          <CardHeader>
            <CardTitle>最近趋势</CardTitle>
            <CardDescription>按天查看销售额和订单数。</CardDescription>
          </CardHeader>
          <CardContent>
            {loading ? <Skeleton className="data-table-skeleton" /> : <TrendTable items={overview?.trend || []} />}
          </CardContent>
        </Card>

        <Card className="data-section-card">
          <CardHeader>
            <CardTitle>最近销售单</CardTitle>
            <CardDescription>当前周期内最近产生的销售记录。</CardDescription>
          </CardHeader>
          <CardContent>
            {loading ? <Skeleton className="data-table-skeleton" /> : <RecentSalesList items={overview?.recent_sales || []} />}
          </CardContent>
        </Card>
      </div>

      <div className="data-hot-products-grid">
        <Card className="data-section-card">
          <CardHeader>
            <CardTitle>礼盒热销</CardTitle>
            <CardDescription>按 SKU 统计当前周期礼盒销量。</CardDescription>
          </CardHeader>
          <CardContent>
            {loading ? <Skeleton className="data-table-skeleton" /> : <HotProductsTable items={hotGiftBoxes} />}
          </CardContent>
        </Card>

        <Card className="data-section-card">
          <CardHeader>
            <CardTitle>泡袋热销</CardTitle>
            <CardDescription>按 SKU 统计当前周期泡袋销量。</CardDescription>
          </CardHeader>
          <CardContent>
            {loading ? <Skeleton className="data-table-skeleton" /> : <HotProductsTable items={hotBags} />}
          </CardContent>
        </Card>
      </div>
    </section>
  );
}
