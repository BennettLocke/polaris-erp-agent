import { Plus, Search } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Combobox,
  ComboboxContent,
  ComboboxInput,
  ComboboxItem,
  ComboboxList
} from "@/components/ui/combobox";
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { Field, FieldContent, FieldLabel } from "@/components/ui/field";
import type { CustomerItem } from "@/types";
import type { CustomerPickerProps } from "./types";
import { customerDisplayName, customerPhoneText } from "./utils";

function SalesCustomerField({
  customerKeyword,
  customerResults,
  selectedCustomer,
  selectedCustomerName,
  loading,
  searched,
  onKeywordChange,
  onSearch,
  onSelectCustomer,
  onOpenCreateCustomer
}: CustomerPickerProps) {
  return (
    <Field className="sales-create-field sales-create-field--customer">
      <FieldLabel>客户</FieldLabel>
      <FieldContent>
        <div className="sales-create-combo-row">
          <Combobox<CustomerItem>
            items={customerResults}
            inputValue={customerKeyword}
            onInputValueChange={(next) => {
              onKeywordChange(next);
            }}
            onValueChange={onSelectCustomer}
            itemToStringValue={(customer) => customerDisplayName(customer)}
            filterItems={false}
            selectOnEnter={false}
          >
            <ComboboxInput
              placeholder="搜索客户名称或电话"
              onKeyDown={(event) => {
                if (event.key === "Enter") onSearch();
              }}
            />
            {customerResults.length ? (
              <ComboboxContent>
                <ComboboxList<CustomerItem>>
                  {(customer) => (
                    <ComboboxItem key={customer.id} value={customer}>
                      <strong>{customerDisplayName(customer)}</strong>
                      <span>{[customerPhoneText(customer), Number(customer.is_monthly_customer || 0) ? "月结客户" : "普通客户"].filter(Boolean).join(" · ")}</span>
                    </ComboboxItem>
                  )}
                </ComboboxList>
              </ComboboxContent>
            ) : null}
          </Combobox>
          <Button type="button" variant="outline" size="sm" onClick={onSearch}>
            <Search data-icon="inline-start" /> 搜索
          </Button>
          <Button type="button" variant="outline" size="sm" onClick={onOpenCreateCustomer}>
            <Plus data-icon="inline-start" /> 创建
          </Button>
        </div>
        {selectedCustomer ? (
          <div className="sales-create-selected-customer">
            <Badge variant="outline">{Number(selectedCustomer.is_monthly_customer || 0) ? "月结客户" : "普通客户"}</Badge>
            <span>{selectedCustomerName || customerDisplayName(selectedCustomer)}</span>
            {customerPhoneText(selectedCustomer) ? <em>{customerPhoneText(selectedCustomer)}</em> : null}
          </div>
        ) : null}
        {searched && customerKeyword.trim() && !customerResults.length && !selectedCustomer && loading !== "customer" ? (
          <div className="sales-create-search-hint">没有找到客户，可以点创建新客户。</div>
        ) : null}
        {loading === "customer" ? (
          <Empty className="sales-create-inline-empty">
            <EmptyHeader>
              <EmptyTitle>客户搜索中</EmptyTitle>
              <EmptyDescription>正在从客户库匹配名称和电话。</EmptyDescription>
            </EmptyHeader>
          </Empty>
        ) : null}
      </FieldContent>
    </Field>
  );
}

export { SalesCustomerField };
