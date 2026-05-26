import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

const buttonVariants = cva("sj-button", {
  variants: {
    variant: {
      default: "sj-button--default",
      secondary: "sj-button--secondary",
      destructive: "sj-button--destructive",
      outline: "sj-button--outline",
      ghost: "sj-button--ghost",
      link: "sj-button--link"
    },
    size: {
      default: "sj-button--size-default",
      xs: "sj-button--size-xs",
      sm: "sj-button--size-sm",
      lg: "sj-button--size-lg",
      icon: "sj-button--size-icon",
      "icon-xs": "sj-button--size-icon-xs",
      "icon-sm": "sj-button--size-icon-sm",
      "icon-lg": "sj-button--size-icon-lg"
    }
  },
  defaultVariants: {
    variant: "default",
    size: "default"
  }
});

type ButtonProps = ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean;
  };

function Button({
  className,
  variant,
  size,
  asChild = false,
  type,
  ...props
}: ButtonProps) {
  const Comp = asChild ? Slot : "button";

  return (
    <Comp
      data-slot="button"
      className={cn(buttonVariants({ variant, size, className }))}
      type={asChild ? undefined : type ?? "button"}
      {...props}
    />
  );
}

export { Button, buttonVariants };
export type { ButtonProps };
