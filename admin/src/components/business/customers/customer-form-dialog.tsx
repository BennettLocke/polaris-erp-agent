import { useEffect, useState } from "react";
import { Save } from "lucide-react";

import { api } from "@/api";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogTitle
} from "@/components/ui/dialog";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import type { CustomerItem } from "@/types";
import { customerName, customerPhone } from "./utils";

type Props = {
  customer?: CustomerItem | null;
  mode: "create" | "edit";
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSaved: (customer?: CustomerItem) => void;
};

function CustomerFormDialog({ customer, mode, open, onOpenChange, onSaved }: Props) {
  const [name, setName] = useState("");
  const [contact, setContact] = useState("");
  const [phone, setPhone] = useState("");
  const [address, setAddress] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const isEdit = mode === "edit";

  useEffect(() => {
    if (!open) return;
    setName(isEdit ? customerName(customer) : "");
    setContact(isEdit ? customer?.contacts_name || "" : "");
    setPhone(isEdit ? customerPhone(customer) : "");
    setAddress(isEdit ? customer?.address || "" : "");
    setError("");
  }, [open, isEdit, customer?.id]);

  async function save() {
    const cleanName = name.trim();
    if (!cleanName) {
      setError("请输入客户名称");
      return;
    }
    setBusy(true);
    setError("");
    try {
      if (isEdit && customer?.id) {
        await api.updateCustomer(customer.id, {
          name: cleanName,
          contacts_name: contact.trim(),
          phone: phone.trim(),
          address: address.trim()
        });
        onSaved({ ...customer, name: cleanName, customer_name: cleanName, contacts_name: contact.trim(), phone: phone.trim(), contacts_tel: phone.trim(), address: address.trim() });
      } else {
        const created = await api.createCustomer({
          name: cleanName,
          contacts_name: contact.trim(),
          contacts_tel: phone.trim()
        });
        onSaved(created);
      }
      onOpenChange(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "客户保存失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(next) => !busy && onOpenChange(next)}>
      <DialogContent className="customer-form-dialog">
        <DialogTitle>{isEdit ? "编辑客户资料" : "创建客户"}</DialogTitle>
        <DialogDescription className="sj-sr-only">
          {isEdit ? "编辑客户资料" : "创建客户"}
        </DialogDescription>
        {error ? <div className="form-error">{error}</div> : null}
        <FieldGroup className="customer-form-grid">
          <Field className="full">
            <FieldLabel>客户名称</FieldLabel>
            <Input value={name} onChange={(event) => setName(event.target.value)} />
          </Field>
          <Field>
            <FieldLabel>联系人</FieldLabel>
            <Input value={contact} onChange={(event) => setContact(event.target.value)} />
          </Field>
          <Field>
            <FieldLabel>电话</FieldLabel>
            <Input value={phone} onChange={(event) => setPhone(event.target.value)} />
          </Field>
          {isEdit ? (
            <Field className="full">
              <FieldLabel>地址</FieldLabel>
              <Input value={address} onChange={(event) => setAddress(event.target.value)} />
            </Field>
          ) : null}
        </FieldGroup>
        <DialogFooter>
          <DialogClose asChild>
            <Button variant="outline" disabled={busy}>取消</Button>
          </DialogClose>
          <Button type="button" disabled={busy} onClick={() => void save()}>
            <Save data-icon="inline-start" /> {busy ? "保存中" : isEdit ? "保存资料" : "创建客户"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export { CustomerFormDialog };
