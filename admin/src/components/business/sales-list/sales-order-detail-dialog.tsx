import { Eye, Printer, Trash2 } from "lucide-react";

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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from "@/components/ui/table";
import { displayDate, money, payText, salesAmount, salesOrderId, salesQuantity, stockRuleText } from "./utils";
import type { SalesOrderDetailDialogProps } from "./types";

function SalesOrderDetailDialog({
  order,
  busySalesId,
  onClose,
  onPrint,
  onPreview,
  onDelete
}: SalesOrderDetailDialogProps) {
  const products = order?.detail || order?.items || order?.products || [];
  const orderId = salesOrderId(order);
  const busy = Boolean(orderId && busySalesId === orderId);

  return (
    <Dialog
      open={Boolean(order)}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent className="sales-order-detail-dialog">
        <DialogHeader>
          <div className="sales-detail-title-row">
            <div>
              <DialogTitle>{order?.customer_name || "销售单详情"}</DialogTitle>
              <DialogDescription>{order?.sales_no || "未记录单号"}</DialogDescription>
            </div>
            {order ? (
              <div className="sales-detail-badges">
                <Badge variant="outline">{order.status_text || "正常"}</Badge>
                <Badge variant="outline">{payText(order)}</Badge>
                <Badge variant="secondary">{displayDate(order.sales_at || order.created_at)}</Badge>
              </div>
            ) : null}
          </div>
        </DialogHeader>

        {order ? (
          <div className="sales-detail-dialog-body">
            <div className="sales-detail-metrics">
              <div><span>总数量</span><strong>{salesQuantity(order)}</strong></div>
              <div><span>应收金额</span><strong>{salesAmount(order)}</strong></div>
              <div><span>开单人</span><strong>{order.created_by_name || "未记录"}</strong></div>
              <div><span>付款</span><strong>{payText(order)}</strong></div>
            </div>

            <Tabs defaultValue="detail" className="sales-detail-tabs">
              <TabsList>
                <TabsTrigger value="detail">明细</TabsTrigger>
                <TabsTrigger value="payment">付款</TabsTrigger>
                <TabsTrigger value="log">操作记录</TabsTrigger>
              </TabsList>
              <TabsContent value="detail">
                <div className="sales-detail-table-wrap">
                  <Table className="sales-detail-table">
                    <TableHeader>
                      <TableRow>
                        <TableHead>商品</TableHead>
                        <TableHead>颜色/规格</TableHead>
                        <TableHead>数量</TableHead>
                        <TableHead>仓库</TableHead>
                        <TableHead>单价</TableHead>
                        <TableHead>金额</TableHead>
                        <TableHead>库存规则</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {products.map((product, index) => (
                        <TableRow key={`${product.product_id || product.id || index}-${index}`}>
                          <TableCell>{product.title || product.name || "商品"}</TableCell>
                          <TableCell>{product.spec || product.color || "默认颜色"}</TableCell>
                          <TableCell>{product.quantity || product.buy_number || 0}</TableCell>
                          <TableCell>{product.warehouse_name || "-"}</TableCell>
                          <TableCell>{money(product.price)}</TableCell>
                          <TableCell>{money(product.total_price)}</TableCell>
                          <TableCell><Badge variant="outline">{stockRuleText(product)}</Badge></TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </TabsContent>
              <TabsContent value="payment">
                <div className="sales-detail-note-grid">
                  <div><span>结款状态</span><strong>{order.pay_status_text || "-"}</strong></div>
                  <div><span>付款方式</span><strong>{order.pay_type_text || "-"}</strong></div>
                  <div><span>商品金额</span><strong>{money(order.goods_amount || order.total_price)}</strong></div>
                  <div><span>应收金额</span><strong>{salesAmount(order)}</strong></div>
                </div>
              </TabsContent>
              <TabsContent value="log">
                <div className="sales-detail-note-grid">
                  <div><span>创建人</span><strong>{order.created_by_name || "未记录"}</strong></div>
                  <div><span>创建时间</span><strong>{displayDate(order.created_at || order.sales_at)}</strong></div>
                  <div><span>删除人</span><strong>{order.deleted_by_name || "-"}</strong></div>
                  <div><span>删除时间</span><strong>{displayDate(order.deleted_at)}</strong></div>
                  <div className="full"><span>删除说明</span><strong>{order.delete_reason || "库存和余额回滚由服务层处理"}</strong></div>
                </div>
              </TabsContent>
            </Tabs>
          </div>
        ) : null}

        <DialogFooter>
          <Button variant="outline" size="sm" type="button" disabled={!orderId} onClick={() => onPreview(orderId)}>
            <Eye data-icon="inline-start" /> 打印预览
          </Button>
          <Button size="sm" type="button" disabled={!orderId || busy} onClick={() => onPrint(orderId)}>
            <Printer data-icon="inline-start" /> {busy ? "提交中" : "打印"}
          </Button>
          {order ? (
            <Button variant="destructive" size="sm" type="button" disabled={!orderId || busy} onClick={() => onDelete(order)}>
              <Trash2 data-icon="inline-start" /> 删除
            </Button>
          ) : null}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export { SalesOrderDetailDialog };
