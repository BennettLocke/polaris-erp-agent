import { Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { Input } from "@/components/ui/input";
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
import { inputNoWheel, money, warehouseName } from "./utils";

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
                <Input
                  type="number"
                  min="1"
                  value={line.buy_number}
                  onWheel={inputNoWheel}
                  onChange={(event) => onUpdateLine(index, "buy_number", event.target.value)}
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
                <Input
                  type="number"
                  min="0"
                  step="0.01"
                  value={line.price}
                  onWheel={inputNoWheel}
                  onChange={(event) => onUpdateLine(index, "price", event.target.value)}
                />
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
  );
}

export { SalesLineTable };
