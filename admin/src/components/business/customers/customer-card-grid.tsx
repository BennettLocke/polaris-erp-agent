import { CreditCard, MoreHorizontal, ReceiptText, WalletCards } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle
} from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger
} from "@/components/ui/dropdown-menu";
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";
import type { CustomerBalanceActionPayload, CustomerItem } from "@/types";
import { customerName, customerPhone, displayDate, money, moneyNumber } from "./utils";

type Props = {
  customers: CustomerItem[];
  loading: boolean;
  gridRef?: (node: HTMLDivElement | null) => void;
  onOpenDetail: (customer: CustomerItem, tab?: string) => void;
  onAction: (customer: CustomerItem, action: CustomerBalanceActionPayload["action"]) => void;
  onToggleMonthly: (customer: CustomerItem) => void;
};

function CustomerCardGrid({ customers, loading, gridRef, onOpenDetail, onAction, onToggleMonthly }: Props) {
  if (loading) {
    return (
      <div className="customer-card-grid">
        {Array.from({ length: 8 }).map((_, index) => (
          <Skeleton className="customer-card-skeleton" key={index} />
        ))}
      </div>
    );
  }

  if (!customers.length) {
    return (
      <Empty className="customer-empty">
        <EmptyHeader>
          <EmptyTitle>没有匹配客户</EmptyTitle>
          <EmptyDescription>换个客户名、手机号或筛选条件再查。</EmptyDescription>
        </EmptyHeader>
      </Empty>
    );
  }

  return (
    <div className="customer-card-grid" ref={gridRef}>
      {customers.map((customer) => {
        const name = customerName(customer);
        const phone = customerPhone(customer);
        const balance = moneyNumber(customer.balance_amount);
        const isMonthly = Number(customer.is_monthly_customer || 0) === 1;
        return (
          <Card size="sm" className="customer-card-new" key={customer.id}>
            <CardHeader>
              <div>
                <CardTitle>{name}</CardTitle>
                <CardDescription>{phone || "未绑定电话"}</CardDescription>
              </div>
              <CardAction>
                <Badge variant={isMonthly ? "secondary" : "outline"}>{isMonthly ? "月结" : "普通"}</Badge>
              </CardAction>
            </CardHeader>

            <CardContent>
              <div className="customer-card-metrics">
                <div><span>最近下单</span><strong>{displayDate(customer.latest_order_at)}</strong></div>
                <div><span>最近金额</span><strong>{money(customer.latest_order_amount)}</strong></div>
                <div><span>近1年消费</span><strong>{money(customer.year_amount)}</strong></div>
                <div><span>余额</span><strong className={balance < 0 ? "customer-money-negative" : ""}>{money(customer.balance_amount)}</strong></div>
              </div>
            </CardContent>

            <CardFooter>
              <Button size="sm" type="button" variant="outline" onClick={() => onOpenDetail(customer)}>
                详情
              </Button>
              <Button size="sm" type="button" variant="outline" onClick={() => onAction(customer, "receipt")}>
                <ReceiptText data-icon="inline-start" /> 收款
              </Button>
              <Button size="sm" type="button" variant="outline" onClick={() => onAction(customer, "settlement")}>
                <CreditCard data-icon="inline-start" /> 结款
              </Button>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button size="icon-sm" type="button" variant="ghost" aria-label="更多客户操作">
                    <MoreHorizontal />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuGroup>
                    <DropdownMenuItem onSelect={() => onAction(customer, "recharge")}>
                      <WalletCards data-icon="inline-start" /> 充值
                    </DropdownMenuItem>
                    <DropdownMenuItem onSelect={() => onAction(customer, "adjust")}>调余额</DropdownMenuItem>
                    <DropdownMenuItem onSelect={() => onOpenDetail(customer, "ledger")}>余额明细</DropdownMenuItem>
                    <DropdownMenuItem onSelect={() => onOpenDetail(customer, "sales")}>销售单</DropdownMenuItem>
                  </DropdownMenuGroup>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onSelect={() => onToggleMonthly(customer)}>
                    {isMonthly ? "取消月结" : "设为月结"}
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

export { CustomerCardGrid };
