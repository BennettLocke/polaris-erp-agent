import { Eye, MoreHorizontal, Printer, Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger
} from "@/components/ui/dropdown-menu";
import { displayDate, payText, productSummary, salesAmount, salesQuantity } from "./utils";
import type { SalesMobileCardListProps } from "./types";

function SalesMobileCardList({ orders, busySalesId, onOpenDetail, onPrint, onPreview, onDelete }: SalesMobileCardListProps) {
  return (
    <div className="sales-mobile-card-list">
      {orders.map((order) => {
        const summary = productSummary(order);
        const busy = busySalesId === order.id;
        return (
          <Card className="sales-mobile-card" key={order.id}>
            <CardHeader>
              <div>
                <CardTitle>{order.customer_name || "未记录客户"}</CardTitle>
                <span>{order.sales_no || order.id}</span>
              </div>
              <Badge variant="outline">{payText(order)}</Badge>
            </CardHeader>
            <CardContent>
              <div className="sales-list-summary">
                {summary.lines.length ? summary.lines.map((line) => <span key={line}>{line}</span>) : <span>{order.product_summary || "没有商品明细"}</span>}
                {summary.extra ? <em>+{summary.extra} 个商品</em> : null}
              </div>
              <div className="sales-mobile-metrics">
                <div><span>数量</span><strong>{salesQuantity(order)}</strong></div>
                <div><span>金额</span><strong>{salesAmount(order)}</strong></div>
                <div><span>开单人</span><strong>{order.created_by_name || "未记录"}</strong></div>
                <div><span>时间</span><strong>{displayDate(order.sales_at)}</strong></div>
              </div>
            </CardContent>
            <CardFooter>
              <Button type="button" variant="outline" size="sm" onClick={() => onOpenDetail(order.id)}>详情</Button>
              <Button type="button" variant="outline" size="sm" disabled={busy} onClick={() => onPrint(order.id)}>
                <Printer data-icon="inline-start" /> {busy ? "提交中" : "打印"}
              </Button>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button type="button" variant="ghost" size="sm">
                    <MoreHorizontal data-icon="inline-start" /> 更多
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem onSelect={() => onPreview(order.id)}>
                    <Eye data-icon="inline-start" /> 打印预览
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem className="sales-list-danger" onSelect={() => onDelete(order)}>
                    <Trash2 data-icon="inline-start" /> 删除
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </CardFooter>
          </Card>
        );
      })}
    </div>
  );
}

export { SalesMobileCardList };
