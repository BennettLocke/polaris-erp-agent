import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

const badgeVariants = cva("sj-badge", {
  variants: {
    variant: {
      default: "sj-badge--default",
      secondary: "sj-badge--secondary",
      destructive: "sj-badge--destructive",
      outline: "sj-badge--outline",
      ghost: "sj-badge--ghost",
      link: "sj-badge--link"
    }
  },
  defaultVariants: {
    variant: "default"
  }
});

type BadgeVariant = NonNullable<VariantProps<typeof badgeVariants>["variant"]>;

type BadgeProps = ComponentProps<"span"> &
  VariantProps<typeof badgeVariants> & {
    asChild?: boolean;
  };

function Badge({ className, variant, asChild = false, ...props }: BadgeProps) {
  const Comp = asChild ? Slot : "span";

  return (
    <Comp
      data-slot="badge"
      className={cn(badgeVariants({ variant, className }))}
      {...props}
    />
  );
}

export { Badge, badgeVariants };
export type { BadgeProps, BadgeVariant };
