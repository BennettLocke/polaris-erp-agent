import { DateTimePicker } from "@/components/ui/date-time-picker";
import { Field, FieldLabel } from "@/components/ui/field";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "@/components/ui/select";
import type { PaymentFieldsProps, SalesPayStatus } from "./types";
import { warehouseName } from "./utils";

function SalesPaymentFields({
  createTime,
  payStatus,
  payType,
  payTypeOptions,
  warehouses,
  defaultWarehouseId,
  onCreateTimeChange,
  onPayStatusChange,
  onPayTypeChange,
  onDefaultWarehouseChange
}: PaymentFieldsProps) {
  return (
    <>
      <Field className="sales-create-field">
        <FieldLabel>开单时间</FieldLabel>
        <DateTimePicker value={createTime} onChange={onCreateTimeChange} />
      </Field>
      <Field className="sales-create-field">
        <FieldLabel>付款状态</FieldLabel>
        <Select value={payStatus} onValueChange={(value) => onPayStatusChange(value as SalesPayStatus)}>
          <SelectTrigger>
            <SelectValue placeholder="选择付款状态" />
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              <SelectItem value="paid">已付</SelectItem>
              <SelectItem value="monthly">月结</SelectItem>
              <SelectItem value="unpaid">未付</SelectItem>
            </SelectGroup>
          </SelectContent>
        </Select>
      </Field>
      {payStatus === "paid" ? (
        <Field className="sales-create-field">
          <FieldLabel>收款方式</FieldLabel>
          <Select value={payType} onValueChange={onPayTypeChange}>
            <SelectTrigger>
              <SelectValue placeholder="选择收款方式" />
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                {payTypeOptions.map((item) => <SelectItem key={item.value} value={item.value}>{item.label}</SelectItem>)}
              </SelectGroup>
            </SelectContent>
          </Select>
        </Field>
      ) : null}
      <Field className="sales-create-field">
        <FieldLabel>默认仓库</FieldLabel>
        <Select value={String(defaultWarehouseId)} onValueChange={(value) => onDefaultWarehouseChange(Number(value || 2))}>
          <SelectTrigger>
            <SelectValue placeholder="选择仓库" />
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              {warehouses.length ? warehouses.map((warehouse) => (
                <SelectItem key={warehouse.id} value={String(warehouse.id)}>
                  {warehouseName(warehouse)}
                </SelectItem>
              )) : <SelectItem value="2">百鑫仓库</SelectItem>}
            </SelectGroup>
          </SelectContent>
        </Select>
      </Field>
    </>
  );
}

export { SalesPaymentFields };
