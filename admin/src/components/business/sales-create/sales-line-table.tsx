import { Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { Input } from "@/components/ui/input";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from "@/components/ui/table";
import type { LineTableProps } from "./types";
import { SalesNumberInput } from "./sales-number-input";
import { inputNoWheel, money, warehouseName } from "./utils";

function priceSourceText(source?: string) {
  if (source === "customer_history") return "历史价";
  if (source === "manual_override") return "手动";
  return "零售价";
}

function priceHint(line: LineTableProps["lines"][number]) {
  const shortParts = [priceSourceText(line.price_source)];
  const detailParts = [
    line.price_source === "customer_history"
      ? "已使用客户历史价格"
      : line.price_source === "manual_override"
        ? "当前单价已手工修改"
        : "当前使用商品零售价"
  ];
  if (line.price_policy === "suggest" && line.suggested_history_price) {
    shortParts.push(`建议 ${money(line.suggested_history_price)}`);
    detailParts.push(`建议历史价 ${money(line.suggested_history_price)}`);
  }
  if (line.price_policy !== "off") {
    shortParts.push("自动记忆");
    detailParts.push("成交后自动记忆整款商品价格");
  }
  if (line.price_warning) {
    shortParts.push("提醒");
    detailParts.push(line.price_warning);
  }
  return { short: shortParts.join(" · "), detail: detailParts.join("；") };
}

function SalesLineTable({ lines, warehouses, onUpdateLine, onRemoveLine }: LineTableProps) {
  if (!lines.length) {
    return (
      <Empty className="sales-create-empty-table">
        <EmptyHeader>
          <EmptyTitle>还没有销售明细</EmptyTitle>
          <EmptyDescription>先搜索礼盒并选择颜色。</EmptyDescription>
        </EmptyHeader>
      </Empty>
    );
  }

  return (
    <TooltipProvider>
      <Table className="sales-create-line-table">
      <TableHeader>
        <TableRow>
          <TableHead>商品</TableHead>
          <TableHead>颜色/规格</TableHead>
          <TableHead>数量</TableHead>
          <TableHead>仓库</TableHead>
          <TableHead>单价</TableHead>
          <TableHead>金额</TableHead>
          <TableHead>操作</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {lines.map((line, index) => {
          const stockItem = Number(line.is_stock_item ?? 1) === 1;
          const hint = priceHint(line);
          return (
            <TableRow key={`${line.product_id}-${line.warehouse_id}-${index}`}>
              <TableCell>
                <div className="sales-create-line-title">
                  <strong>{line.title}</strong>
                  <span>{line.coding || `ID ${line.product_id}`}</span>
                </div>
              </TableCell>
              <TableCell>{line.spec || "默认颜色"}</TableCell>
              <TableCell>
                <SalesNumberInput
                  ariaLabel={`${line.title}数量`}
                  value={line.buy_number}
                  onValueChange={(value) => onUpdateLine(index, "buy_number", String(value))}
                />
              </TableCell>
              <TableCell>
                {stockItem ? (
                  <Select value={String(line.warehouse_id)} onValueChange={(value) => onUpdateLine(index, "warehouse_id", value)}>
                    <SelectTrigger>
                      <SelectValue placeholder="仓库" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectGroup>
                        {warehouses.length ? warehouses.map((warehouse) => (
                          <SelectItem key={warehouse.id} value={String(warehouse.id)}>{warehouseName(warehouse)}</SelectItem>
                        )) : <SelectItem value="2">百鑫仓库</SelectItem>}
                      </SelectGroup>
                    </SelectContent>
                  </Select>
                ) : (
                  <Badge variant="outline">不扣库存</Badge>
                )}
              </TableCell>
              <TableCell>
                <div className="sales-create-price-field">
                  <Input
                    type="number"
                    min="0"
                    step="0.01"
                    value={line.price}
                    onWheel={inputNoWheel}
                    onChange={(event) => onUpdateLine(index, "price", event.target.value)}
                  />
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <span className="sales-create-price-hint">{hint.short}</span>
                    </TooltipTrigger>
                    <TooltipContent>{hint.detail}</TooltipContent>
                  </Tooltip>
                </div>
              </TableCell>
              <TableCell><strong>{money(line.buy_number * line.price)}</strong></TableCell>
              <TableCell>
                <Button variant="ghost" size="icon-sm" type="button" aria-label="删除明细" onClick={() => onRemoveLine(index)}>
                  <Trash2 />
                </Button>
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
      </Table>
    </TooltipProvider>
  );
}

export { SalesLineTable };
