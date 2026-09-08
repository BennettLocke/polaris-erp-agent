import { useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Download, LoaderCircle, Printer, X } from "lucide-react";
import { toPng } from "html-to-image";

import { Button } from "@/components/ui/button";
import { api } from "@/api";
import { queryKeys } from "@/lib/admin-query";
import type { SalesMergeOrder } from "@/types";
import { money } from "./utils";

function parsePositiveIds(value: string | null) {
  return Array.from(new Set(
    String(value || "")
      .split(",")
      .map((item) => Number(item.trim()))
      .filter((item) => Number.isInteger(item) && item > 0)
  ));
}

function numberValue(value: unknown) {
  const parsed = Number(value ?? 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

function dateOnly(value?: string) {
  return String(value || "-").replace("T", " ").slice(0, 10);
}

function paymentText(order: SalesMergeOrder) {
  const status = String(order.pay_status_text || "").trim();
  const type = String(order.pay_type_text || "").trim();
  if (!type || status === type || status === "月结") return status || type || "-";
  return `${status} / ${type}`;
}

function safeFileName(value: string) {
  return value.replace(/[\\/:*?"<>|]/g, "-").replace(/\s+/g, " ").trim() || "客户";
}

function SalesMergePreviewPage() {
  const params = useMemo(() => new URLSearchParams(window.location.search), []);
  const baseSalesId = Number(params.get("base") || 0);
  const selectedIds = useMemo(() => parsePositiveIds(params.get("ids")), [params]);
  const documentRef = useRef<HTMLDivElement>(null);
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState("");

  const query = useQuery({
    queryKey: queryKeys.sales.mergeCandidates(baseSalesId),
    queryFn: ({ signal }) => api.salesMergeCandidates(baseSalesId, { signal }),
    enabled: baseSalesId > 0,
    staleTime: 0
  });

  const candidateIds = useMemo(
    () => new Set((query.data?.orders || []).map((order) => order.id)),
    [query.data]
  );
  const invalidIds = selectedIds.filter((id) => !candidateIds.has(id));
  const selectedOrders = (query.data?.orders || []).filter((order) => selectedIds.includes(order.id));
  const detailRows = selectedOrders.flatMap((order) =>
    order.items.map((item) => ({ order, item }))
  );
  const paymentKinds = Array.from(new Set(selectedOrders.map(paymentText)));
  const paymentSummary = paymentKinds.length > 1 ? "包含多种付款方式" : paymentKinds[0] || "-";
  const totalQuantity = selectedOrders.reduce((sum, order) => sum + numberValue(order.total_quantity), 0);
  const totalAmount = selectedOrders.reduce((sum, order) => sum + numberValue(order.receivable_amount), 0);
  const notes = selectedOrders.filter((order) => String(order.note || "").trim());
  const loadError = !baseSalesId
    ? "缺少基准销售单，无法生成预览。"
    : !selectedIds.length
      ? "没有选择要合并预览的销售单。"
      : query.error instanceof Error
        ? query.error.message
        : query.error
          ? "合并预览加载失败。"
          : invalidIds.length
            ? "所选销售单已不在本客户的7天范围内，请关闭后重新选择。"
            : "";

  function closePreview() {
    if (window.opener) {
      window.close();
      return;
    }
    window.location.assign("/admin/sales");
  }

  async function downloadLongImage() {
    if (!documentRef.current || !query.data || loadError) return;
    setDownloading(true);
    setDownloadError("");
    try {
      const dataUrl = await toPng(documentRef.current, {
        backgroundColor: "#ffffff",
        cacheBust: true,
        pixelRatio: 2,
        width: 1200,
        style: {
          width: "1200px",
          maxWidth: "1200px",
          margin: "0"
        }
      });
      const link = document.createElement("a");
      link.download = `${safeFileName(query.data.customer.name)}-${query.data.date_from}至${query.data.date_to}-销售明细.png`;
      link.href = dataUrl;
      link.click();
    } catch (error) {
      setDownloadError(error instanceof Error ? error.message : "长图生成失败，请重试。 ");
    } finally {
      setDownloading(false);
    }
  }

  if (query.isLoading) {
    return (
      <main className="sales-merge-preview-page sales-merge-preview-state">
        <LoaderCircle className="sales-merge-preview-spinner" />
        <span>正在生成合并预览</span>
      </main>
    );
  }

  if (loadError || !query.data) {
    return (
      <main className="sales-merge-preview-page sales-merge-preview-state">
        <strong>无法生成合并预览</strong>
        <p>{loadError || "销售单数据不存在。"}</p>
        <Button type="button" onClick={closePreview}>返回销售单</Button>
      </main>
    );
  }

  return (
    <main className="sales-merge-preview-page">
      <div className="sales-merge-preview-actions">
        <div>
          <strong>合并销售单预览</strong>
          <span>已选 {selectedOrders.length} 张销售单，明细保持原样连续排列</span>
        </div>
        <div className="sales-merge-preview-buttons">
          <Button type="button" variant="outline" onClick={closePreview}>
            <X data-icon="inline-start" /> 关闭
          </Button>
          <Button type="button" variant="outline" disabled={downloading} onClick={() => void downloadLongImage()}>
            {downloading ? <LoaderCircle className="sales-merge-preview-spinner" data-icon="inline-start" /> : <Download data-icon="inline-start" />}
            {downloading ? "正在生成" : "下载长图"}
          </Button>
          <Button type="button" onClick={() => window.print()}>
            <Printer data-icon="inline-start" /> 打印
          </Button>
        </div>
      </div>
      {downloadError ? <div className="sales-merge-preview-download-error">{downloadError}</div> : null}

      <div ref={documentRef} className="sales-merge-preview-document">
        <header className="sales-merge-preview-header">
          <div>
            <h1>销售明细汇总</h1>
            <p>{query.data.customer.name}</p>
          </div>
          <div className="sales-merge-preview-header-meta">
            <span>日期：{query.data.date_from} 至 {query.data.date_to}</span>
            <span>付款：{paymentSummary}</span>
          </div>
        </header>

        <section className="sales-merge-preview-customer">
          <span><strong>客户</strong>{query.data.customer.name}</span>
          {query.data.customer.contact_name ? <span><strong>联系人</strong>{query.data.customer.contact_name}</span> : null}
          {query.data.customer.phone ? <span><strong>电话</strong>{query.data.customer.phone}</span> : null}
          {query.data.customer.address ? <span className="sales-merge-preview-customer-address"><strong>地址</strong>{query.data.customer.address}</span> : null}
        </section>

        <section className="sales-merge-preview-table-section">
          <div className="sales-merge-preview-section-title">连续明细</div>
          <table className="sales-merge-preview-table">
            <thead>
              <tr>
                <th>#</th>
                <th>日期</th>
                <th>原单号</th>
                <th>商品</th>
                <th>颜色/规格</th>
                <th>数量</th>
                <th>单价</th>
                <th>金额</th>
              </tr>
            </thead>
            <tbody>
              {detailRows.map(({ order, item }, index) => (
                <tr key={`${order.id}-${item.item_id}-${index}`}>
                  <td>{index + 1}</td>
                  <td>{dateOnly(order.sales_at)}</td>
                  <td>{order.sales_no}</td>
                  <td>{item.title}</td>
                  <td>{item.color || "默认颜色"}</td>
                  <td>{item.quantity}</td>
                  <td>{money(item.unit_price)}</td>
                  <td>{money(item.amount)}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <th colSpan={5}>共计：{selectedOrders.length} 单</th>
                <th>{totalQuantity}</th>
                <th>应收金额</th>
                <th>{money(totalAmount)}</th>
              </tr>
            </tfoot>
          </table>
        </section>

        {notes.length ? (
          <section className="sales-merge-preview-notes">
            <strong>备注</strong>
            <div>
              {notes.map((order) => (
                <p key={order.id}>{order.sales_no}：{order.note}</p>
              ))}
            </div>
          </section>
        ) : null}

        <footer className="sales-merge-preview-footer">
          北极星智能体 · 销售明细汇总
        </footer>
      </div>
    </main>
  );
}

export { SalesMergePreviewPage };
