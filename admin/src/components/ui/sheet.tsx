import * as SheetPrimitive from "@radix-ui/react-dialog";
import { cva, type VariantProps } from "class-variance-authority";
import { X } from "lucide-react";
import type { ComponentPropsWithoutRef } from "react";

import { cn } from "@/lib/utils";

const Sheet = SheetPrimitive.Root;
const SheetTrigger = SheetPrimitive.Trigger;
const SheetClose = SheetPrimitive.Close;
const SheetPortal = SheetPrimitive.Portal;

const sheetVariants = cva("sj-sheet-content", {
  variants: {
    side: {
      top: "sj-sheet-content--top",
      right: "sj-sheet-content--right",
      bottom: "sj-sheet-content--bottom",
      left: "sj-sheet-content--left"
    }
  },
  defaultVariants: {
    side: "right"
  }
});

function SheetOverlay({
  className,
  ...props
}: ComponentPropsWithoutRef<typeof SheetPrimitive.Overlay>) {
  return <SheetPrimitive.Overlay data-slot="sheet-overlay" className={cn("sj-dialog-overlay", className)} {...props} />;
}

function SheetContent({
  side = "right",
  className,
  children,
  ...props
}: ComponentPropsWithoutRef<typeof SheetPrimitive.Content> & VariantProps<typeof sheetVariants>) {
  return (
    <SheetPortal>
      <SheetOverlay />
      <SheetPrimitive.Content data-slot="sheet-content" className={cn(sheetVariants({ side }), className)} {...props}>
        {children}
        <SheetPrimitive.Close data-slot="sheet-close" className="sj-dialog-close">
          <X />
          <span className="sj-sr-only">Close</span>
        </SheetPrimitive.Close>
      </SheetPrimitive.Content>
    </SheetPortal>
  );
}

function SheetHeader({ className, ...props }: ComponentPropsWithoutRef<"div">) {
  return <div data-slot="sheet-header" className={cn("sj-dialog-header", className)} {...props} />;
}

function SheetFooter({ className, ...props }: ComponentPropsWithoutRef<"div">) {
  return <div data-slot="sheet-footer" className={cn("sj-dialog-footer", className)} {...props} />;
}

function SheetTitle({
  className,
  ...props
}: ComponentPropsWithoutRef<typeof SheetPrimitive.Title>) {
  return <SheetPrimitive.Title data-slot="sheet-title" className={cn("sj-dialog-title", className)} {...props} />;
}

function SheetDescription({
  className,
  ...props
}: ComponentPropsWithoutRef<typeof SheetPrimitive.Description>) {
  return <SheetPrimitive.Description data-slot="sheet-description" className={cn("sj-dialog-description", className)} {...props} />;
}

export {
  Sheet,
  SheetClose,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetOverlay,
  SheetPortal,
  SheetTitle,
  SheetTrigger
};
