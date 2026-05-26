import * as AlertDialogPrimitive from "@radix-ui/react-alert-dialog";
import type { ComponentPropsWithoutRef } from "react";

import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const AlertDialog = AlertDialogPrimitive.Root;
const AlertDialogTrigger = AlertDialogPrimitive.Trigger;
const AlertDialogPortal = AlertDialogPrimitive.Portal;

function AlertDialogOverlay({
  className,
  ...props
}: ComponentPropsWithoutRef<typeof AlertDialogPrimitive.Overlay>) {
  return <AlertDialogPrimitive.Overlay data-slot="alert-dialog-overlay" className={cn("sj-dialog-overlay", className)} {...props} />;
}

function AlertDialogContent({
  className,
  ...props
}: ComponentPropsWithoutRef<typeof AlertDialogPrimitive.Content>) {
  return (
    <AlertDialogPortal>
      <AlertDialogOverlay />
      <AlertDialogPrimitive.Content data-slot="alert-dialog-content" className={cn("sj-alert-dialog-content", className)} {...props} />
    </AlertDialogPortal>
  );
}

function AlertDialogHeader({ className, ...props }: ComponentPropsWithoutRef<"div">) {
  return <div data-slot="alert-dialog-header" className={cn("sj-dialog-header", className)} {...props} />;
}

function AlertDialogFooter({ className, ...props }: ComponentPropsWithoutRef<"div">) {
  return <div data-slot="alert-dialog-footer" className={cn("sj-dialog-footer", className)} {...props} />;
}

function AlertDialogTitle({
  className,
  ...props
}: ComponentPropsWithoutRef<typeof AlertDialogPrimitive.Title>) {
  return <AlertDialogPrimitive.Title data-slot="alert-dialog-title" className={cn("sj-dialog-title", className)} {...props} />;
}

function AlertDialogDescription({
  className,
  ...props
}: ComponentPropsWithoutRef<typeof AlertDialogPrimitive.Description>) {
  return <AlertDialogPrimitive.Description data-slot="alert-dialog-description" className={cn("sj-dialog-description", className)} {...props} />;
}

function AlertDialogAction({
  className,
  ...props
}: ComponentPropsWithoutRef<typeof AlertDialogPrimitive.Action>) {
  return <AlertDialogPrimitive.Action className={cn(buttonVariants(), className)} {...props} />;
}

function AlertDialogCancel({
  className,
  ...props
}: ComponentPropsWithoutRef<typeof AlertDialogPrimitive.Cancel>) {
  return <AlertDialogPrimitive.Cancel className={cn(buttonVariants({ variant: "outline" }), className)} {...props} />;
}

export {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogOverlay,
  AlertDialogPortal,
  AlertDialogTitle,
  AlertDialogTrigger
};
