import { Printer, Trash2 } from "lucide-react";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle
} from "@/components/ui/sheet";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from "@/components/ui/table";
import type { SalesDetail } from "@/types";
import { money } from "./utils";

type SalesOrderDetailSheetProps = {
  order: SalesDetail | null;
  busy?: boolean;
  onClose: () => void;
  onPrint: (id: number) => void;
  onDelete?: (order: SalesDetail) => void;
};

function displayDate(value?: string) {
  if (!value) return "-";
  return value.replace("T", " ").slice(0, 16);
}

function SalesOrderDetailSheet({ order, busy = false, onClose, onPrint, onDelete }: SalesOrderDetailSheetProps) {
  const products = order?.detail || order?.items || order?.products || [];
  const orderId = Number(order?.id || order?.sales_id || 0);
  return (
    <Sheet open={Boolean(order)} onOpenChange={(open) => {
      if (!open) onClose();
    }}>
      <SheetContent className="sales-create-detail-sheet">
        <SheetHeader>
          <SheetTitle>{order?.sales_no || "销售单详情"}</SheetTitle>
          <SheetDescription>{order?.customer_name || "未记录客户"}</SheetDescription>
          <div className="sales-create-sheet-badges">
            <Badge variant="outline">{[order?.pay_status_text, order?.pay_type_text].filter(Boolean).join(" / ") || "付款未记录"}</Badge>
            <Badge variant="ghost">{displayDate(order?.sales_at || order?.created_at)}</Badge>
          </div>
        </SheetHeader>

        <div className="sales-create-detail-metrics">
          <div><span>总数量</span><strong>{order?.total_quantity || order?.buy_number_count || 0}</strong></div>
          <div><span>应收金额</span><strong>{money(order?.receivable_amount || order?.total_price)}</strong></div>
          <div><span>开单人</span><strong>{order?.created_by_name || "未记录"}</strong></div>
          <div><span>付款</span><strong>{[order?.pay_status_text, order?.pay_type_text].filter(Boolean).join(" / ") || "-"}</strong></div>
        </div>

        <Table className="sales-create-detail-table">
          <TableHeader>
            <TableRow>
              <TableHead>商品</TableHead>
              <TableHead>颜色</TableHead>
              <TableHead>数量</TableHead>
              <TableHead>单价</TableHead>
              <TableHead>金额</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {products.map((product, index) => (
              <TableRow key={`${product.product_id || product.id || index}-${index}`}>
                <TableCell>{product.title || product.name || "商品"}</TableCell>
                <TableCell>{product.spec || product.color || "默认颜色"}</TableCell>
                <TableCell>x{product.quantity || product.buy_number || 0}</TableCell>
                <TableCell>{money(product.price)}</TableCell>
                <TableCell>{money(product.total_price)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>

        <SheetFooter>
          <Button size="sm" type="button" disabled={!orderId || busy} onClick={() => onPrint(orderId)}>
            <Printer data-icon="inline-start" /> {busy ? "提交中" : "打印"}
          </Button>
          {order && onDelete ? (
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button variant="destructive" size="sm" type="button" disabled={!orderId || busy}>
                  <Trash2 data-icon="inline-start" /> 删除
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>删除销售单</AlertDialogTitle>
                  <AlertDialogDescription>
                    确认删除 {order.sales_no || "这张销售单"}？系统会软删除并回滚这单扣过的库存和余额。
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel disabled={busy}>取消</AlertDialogCancel>
                  <AlertDialogAction disabled={busy} onClick={() => onDelete(order)}>
                    <Trash2 data-icon="inline-start" /> {busy ? "删除中" : "确认删除"}
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          ) : null}
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}

export { SalesOrderDetailSheet };
