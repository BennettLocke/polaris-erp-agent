import { Eye, Printer, RotateCcw, UserPlus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import type { SalesLoadingKey, SalesResultLite } from "./types";
import { salesResultId } from "./utils";

type SalesResultCardProps = {
  result: SalesResultLite;
  loading: SalesLoadingKey;
  onPrint: () => void;
  onOpenDetail: () => void;
  onPreview: () => void;
  onContinueSameCustomer: () => void;
  onStartNewCustomerOrder: () => void;
};

function SalesResultCard({
  result,
  loading,
  onPrint,
  onOpenDetail,
  onPreview,
  onContinueSameCustomer,
  onStartNewCustomerOrder
}: SalesResultCardProps) {
  if (!result) return null;
  const id = salesResultId(result);
  return (
    <Card className="sales-create-result" size="sm">
      <CardHeader>
        <CardTitle>开单成功</CardTitle>
        <span>{result.sales_no || result.order_no || `销售单 ${id}`}</span>
      </CardHeader>
      <CardContent className="sales-create-result-actions">
        <Button variant="outline" size="sm" type="button" onClick={onOpenDetail} disabled={!id || loading === "detail-last"}>
          <Eye data-icon="inline-start" /> 详情
        </Button>
        <Button variant="outline" size="sm" type="button" onClick={onPrint} disabled={!id || loading === "print-last"}>
          <Printer data-icon="inline-start" /> 打印
        </Button>
        <Button variant="outline" size="sm" type="button" onClick={onPreview} disabled={!id}>
          <Eye data-icon="inline-start" /> 预览
        </Button>
      </CardContent>
      <CardFooter className="sales-create-result-next">
        <Button variant="secondary" size="sm" type="button" onClick={onContinueSameCustomer}>
          <RotateCcw data-icon="inline-start" /> 继续给该客户开单
        </Button>
        <Button variant="outline" size="sm" type="button" onClick={onStartNewCustomerOrder}>
          <UserPlus data-icon="inline-start" /> 开新客户单
        </Button>
      </CardFooter>
    </Card>
  );
}

export { SalesResultCard };
