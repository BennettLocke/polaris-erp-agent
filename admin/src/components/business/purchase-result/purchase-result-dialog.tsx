import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { formatPurchaseResult, type PurchaseBatchResult } from "./purchase-result";
import { PurchaseResultCopyButton } from "./purchase-result-copy-button";

export type PurchaseResultDialogProps = {
  result: PurchaseBatchResult | null;
  onClose: () => void;
};

const salesStatusText: Record<PurchaseBatchResult["salesStatus"], string> = {
  created: "销售单已创建",
  failed: "销售单创建失败",
  not_created: "销售单未创建",
  uncertain: "销售单结果待核实，请先核对销售记录，勿重复开单。"
};

export function PurchaseResultDialog({ result, onClose }: PurchaseResultDialogProps) {
  return (
    <Dialog open={Boolean(result)} onOpenChange={(open) => { if (!open) onClose(); }}>
      {result ? (
        <DialogContent className="sales-purchase-result-dialog">
          <DialogHeader>
            <DialogTitle>进货结果</DialogTitle>
            <DialogDescription>已确认入库 {result.items.length} 项</DialogDescription>
          </DialogHeader>
          <ScrollArea className="sales-purchase-result-scroll">
            <div className="sales-purchase-result-body">
              <section aria-label="销售单状态">
                <h3>{salesStatusText[result.salesStatus]}</h3>
                {result.salesNo ? <p>销售单号：{result.salesNo}</p> : null}
                {result.error ? <p className="sales-purchase-result-error">{result.error}</p> : null}
              </section>
              <section aria-label="已确认入库">
                <h3>已确认入库</h3>
                {result.items.length ? result.items.map((item, index) => (
                  <div className="sales-purchase-result-item" key={`${item.productId}_${item.warehouseId}_${index}`}>
                    <pre>{formatPurchaseResult([item])}</pre>
                    {item.docNo ? <p className="sales-purchase-result-docno">入库单号：{item.docNo}</p> : null}
                  </div>
                )) : <p>暂无已确认入库的商品。</p>}
              </section>
              {result.failedItems.length ? (
                <section aria-label="未成功及待核实项目">
                  <h3>未成功及待核实项目</h3>
                  {result.failedItems.map((item, index) => (
                    <div className="sales-purchase-result-item" key={index}>
                      <p>{item.productName} · {item.color} · {item.warehouseName}</p>
                      <p className="sales-purchase-result-error">
                        {item.uncertain ? "入库结果待核实" : "进货失败"}：{item.message}
                      </p>
                      {item.uncertain ? <p>请先核对入库记录，勿重复进货。</p> : null}
                    </div>
                  ))}
                </section>
              ) : null}
              {result.unprocessedCount > 0 ? <p>尚未处理：{result.unprocessedCount} 项</p> : null}
            </div>
          </ScrollArea>
          <DialogFooter>
            {result.items.length ? <PurchaseResultCopyButton text={formatPurchaseResult(result.items)} /> : null}
            <Button type="button" onClick={onClose}>关闭</Button>
          </DialogFooter>
        </DialogContent>
      ) : null}
    </Dialog>
  );
}
