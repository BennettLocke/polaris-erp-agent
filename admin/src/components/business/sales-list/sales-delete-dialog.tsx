import { Trash2 } from "lucide-react";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle
} from "@/components/ui/alert-dialog";
import type { SalesDeleteDialogProps } from "./types";

function SalesDeleteDialog({ order, busy, onClose, onConfirm }: SalesDeleteDialogProps) {
  return (
    <AlertDialog open={Boolean(order)} onOpenChange={(open) => {
      if (!open && !busy) onClose();
    }}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>删除销售单</AlertDialogTitle>
          <AlertDialogDescription>
            确认删除 {order?.sales_no || "这张销售单"}？系统会软删除销售单，并按服务层规则回滚这单扣过的库存和余额。不扣库存的商品不会恢复库存。
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={busy} onClick={onClose}>取消</AlertDialogCancel>
          <AlertDialogAction disabled={busy} onClick={onConfirm}>
            <Trash2 data-icon="inline-start" /> {busy ? "删除中" : "确认删除"}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

export { SalesDeleteDialog };
