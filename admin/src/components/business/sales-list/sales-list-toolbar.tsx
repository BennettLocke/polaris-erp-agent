import { RotateCcw, Search } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "@/components/ui/select";
import type { SalesDateFilter, SalesListToolbarProps, SalesPayStatusFilter, SalesStatusFilter } from "./types";

function SalesListToolbar({ filters, onFiltersChange, onSearch, onReset }: SalesListToolbarProps) {
  return (
    <form
      className="sales-list-toolbar"
      onSubmit={(event) => {
        event.preventDefault();
        onSearch();
      }}
    >
      <Input
        value={filters.keyword}
        placeholder="搜索客户、商品、单号"
        onChange={(event) => onFiltersChange({ ...filters, keyword: event.target.value })}
      />
      <Select
        value={filters.payStatus || "all"}
        onValueChange={(value) => onFiltersChange({ ...filters, payStatus: (value === "all" ? "" : value) as SalesPayStatusFilter })}
      >
        <SelectTrigger aria-label="付款">
          <SelectValue placeholder="付款" />
        </SelectTrigger>
        <SelectContent>
          <SelectGroup>
            <SelectItem value="all">付款：全部</SelectItem>
            <SelectItem value="paid">已付</SelectItem>
            <SelectItem value="monthly">月结</SelectItem>
            <SelectItem value="unpaid">未付</SelectItem>
          </SelectGroup>
        </SelectContent>
      </Select>
      <Select
        value={filters.dateFilter || "all"}
        onValueChange={(value) => onFiltersChange({ ...filters, dateFilter: (value === "all" ? "" : value) as SalesDateFilter })}
      >
        <SelectTrigger aria-label="日期">
          <SelectValue placeholder="日期" />
        </SelectTrigger>
        <SelectContent>
          <SelectGroup>
            <SelectItem value="all">日期：全部</SelectItem>
            <SelectItem value="today">今天</SelectItem>
            <SelectItem value="month">本月</SelectItem>
          </SelectGroup>
        </SelectContent>
      </Select>
      <Select
        value={filters.status}
        onValueChange={(value) => onFiltersChange({ ...filters, status: value as SalesStatusFilter })}
      >
        <SelectTrigger aria-label="单据状态">
          <SelectValue placeholder="状态" />
        </SelectTrigger>
        <SelectContent>
          <SelectGroup>
            <SelectItem value="active">正常销售单</SelectItem>
            <SelectItem value="deleted">已删除销售单</SelectItem>
          </SelectGroup>
        </SelectContent>
      </Select>
      <Button type="submit" variant="outline" size="sm">
        <Search data-icon="inline-start" /> 搜索
      </Button>
      <Button type="button" variant="ghost" size="sm" onClick={onReset}>
        <RotateCcw data-icon="inline-start" /> 重置
      </Button>
    </form>
  );
}

export { SalesListToolbar };
