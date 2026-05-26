import { ReceiptText } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle
} from "@/components/ui/card";
import type { CustomerItem } from "@/types";
import type { PayTypeOption, SalesLoadingKey, SalesPayStatus } from "./types";
import { money, paymentLabel } from "./utils";

type SalesSummaryCardProps = {
  selectedCustomer: CustomerItem | null;
  selectedCustomerName: string;
  payStatus: SalesPayStatus;
  payType: string;
  payTypeOptions: PayTypeOption[];
  totalQty: number;
  totalAmount: number;
  lineCount: number;
  loading: SalesLoadingKey;
  canSubmit: boolean;
  disabledReason: string;
  onSubmit: () => void;
};

function SalesSummaryCard({
  selectedCustomer,
  selectedCustomerName,
  payStatus,
  payType,
  payTypeOptions,
  totalQty,
  totalAmount,
  lineCount,
  loading,
  canSubmit,
  disabledReason,
  onSubmit
}: SalesSummaryCardProps) {
  const balance = Number(selectedCustomer?.balance_amount || 0);
  return (
    <Card className="sales-create-summary">
      <CardHeader>
        <Badge variant="outline">{paymentLabel(payStatus, payType, payTypeOptions)}</Badge>
        <CardTitle>{money(totalAmount)}</CardTitle>
        <CardDescription>确认客户、数量和付款状态后提交。</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="sales-create-summary-grid">
          <div><span>客户</span><strong>{selectedCustomerName || "未选择"}</strong></div>
          <div><span>数量</span><strong>{totalQty} 套</strong></div>
          <div><span>商品行</span><strong>{lineCount}</strong></div>
          <div><span>付款</span><strong>{paymentLabel(payStatus, payType, payTypeOptions)}</strong></div>
          <div><span>余额</span><strong className={balance < 0 ? "danger-text" : "ok-text"}>{money(balance)}</strong></div>
          <div><span>本单应收</span><strong>{money(totalAmount)}</strong></div>
        </div>
        {disabledReason ? (
          <p className="sales-create-disabled-reason">{disabledReason}</p>
        ) : null}
      </CardContent>
      <CardFooter>
        <Button className="sales-create-submit-button" type="button" disabled={loading === "submit" || !canSubmit} onClick={onSubmit}>
          <ReceiptText data-icon="inline-start" /> {loading === "submit" ? "提交中" : "提交开单"}
        </Button>
      </CardFooter>
    </Card>
  );
}

export { SalesSummaryCard };
