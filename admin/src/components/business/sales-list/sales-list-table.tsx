import { Copy, Eye, MoreHorizontal, Printer, Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger
} from "@/components/ui/dropdown-menu";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from "@/components/ui/table";
import { displayDate, payText, productSummary, salesAmount, salesQuantity } from "./utils";
import type { SalesListTableProps } from "./types";

function copySalesNo(salesNo?: string) {
  if (!salesNo || !navigator.clipboard) return;
  void navigator.clipboard.writeText(salesNo);
}

function SalesListTable({ orders, busySalesId, onOpenDetail, onPrint, onPreview, onDelete }: SalesListTableProps) {
  return (
    <div className="sales-list-table-wrap">
      <Table className="sales-list-table">
        <TableHeader>
          <TableRow>
            <TableHead>客户</TableHead>
            <TableHead>单号</TableHead>
            <TableHead>商品摘要</TableHead>
            <TableHead>数量</TableHead>
            <TableHead>金额</TableHead>
            <TableHead>付款</TableHead>
            <TableHead>开单人</TableHead>
            <TableHead>时间</TableHead>
            <TableHead>操作</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {orders.map((order) => {
            const summary = productSummary(order);
            const busy = busySalesId === order.id;
            return (
              <TableRow key={order.id} className="sales-list-row" onClick={() => onOpenDetail(order.id)}>
                <TableCell>
                  <strong>{order.customer_name || "未记录客户"}</strong>
                  <Badge variant="outline">{order.status_text || "正常"}</Badge>
                </TableCell>
                <TableCell>{order.sales_no || order.id}</TableCell>
                <TableCell>
                  <div className="sales-list-summary">
                    {summary.lines.length ? summary.lines.map((line) => <span key={line}>{line}</span>) : <span>{order.product_summary || "没有商品明细"}</span>}
                    {summary.extra ? <em>+{summary.extra} 个商品</em> : null}
                  </div>
                </TableCell>
                <TableCell>{salesQuantity(order)}</TableCell>
                <TableCell><strong>{salesAmount(order)}</strong></TableCell>
                <TableCell>{payText(order)}</TableCell>
                <TableCell>{order.created_by_name || "未记录"}</TableCell>
                <TableCell>{displayDate(order.sales_at)}</TableCell>
                <TableCell>
                  <div className="sales-list-actions" onClick={(event) => event.stopPropagation()}>
                    <Button type="button" variant="outline" size="sm" onClick={() => onOpenDetail(order.id)}>详情</Button>
                    <Button type="button" variant="outline" size="sm" disabled={busy} onClick={() => onPrint(order.id)}>
                      <Printer data-icon="inline-start" /> {busy ? "提交中" : "打印"}
                    </Button>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button type="button" variant="ghost" size="icon-sm" aria-label="更多操作">
                          <MoreHorizontal />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onSelect={() => onPreview(order.id)}>
                          <Eye data-icon="inline-start" /> 打印预览
                        </DropdownMenuItem>
                        <DropdownMenuItem onSelect={() => copySalesNo(order.sales_no)}>
                          <Copy data-icon="inline-start" /> 复制单号
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem className="sales-list-danger" onSelect={() => onDelete(order)}>
                          <Trash2 data-icon="inline-start" /> 删除
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
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

export { SalesListTable };
