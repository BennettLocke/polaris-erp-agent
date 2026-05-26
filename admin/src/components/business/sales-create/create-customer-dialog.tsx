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

type CreateCustomerDialogProps = {
  open: boolean;
  name: string;
  contact: string;
  phone: string;
  loading: boolean;
  onOpenChange: (open: boolean) => void;
  onNameChange: (value: string) => void;
  onContactChange: (value: string) => void;
  onPhoneChange: (value: string) => void;
  onSubmit: () => void;
};

function CreateCustomerDialog({
  open,
  name,
  contact,
  phone,
  loading,
  onOpenChange,
  onNameChange,
  onContactChange,
  onPhoneChange,
  onSubmit
}: CreateCustomerDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sales-create-dialog">
        <DialogTitle>创建客户</DialogTitle>
        <DialogDescription>新客户默认不是月结客户，后续可在客户详情里设置。</DialogDescription>
        <FieldGroup className="sales-create-dialog-grid">
          <Field className="sales-create-field full">
            <FieldLabel>客户名称</FieldLabel>
            <Input value={name} onChange={(event) => onNameChange(event.target.value)} />
          </Field>
          <Field className="sales-create-field">
            <FieldLabel>联系人</FieldLabel>
            <Input value={contact} onChange={(event) => onContactChange(event.target.value)} />
          </Field>
          <Field className="sales-create-field">
            <FieldLabel>电话</FieldLabel>
            <Input value={phone} onChange={(event) => onPhoneChange(event.target.value)} />
          </Field>
        </FieldGroup>
        <DialogFooter>
          <DialogClose asChild>
            <Button variant="outline">取消</Button>
          </DialogClose>
          <Button type="button" disabled={loading} onClick={onSubmit}>
            {loading ? "创建中" : "创建并选中"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export { CreateCustomerDialog };
