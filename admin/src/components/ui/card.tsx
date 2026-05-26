import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

type CardProps = ComponentProps<"div"> & {
  size?: "default" | "sm";
};

function Card({ className, size = "default", ...props }: CardProps) {
  return (
    <div
      data-slot="card"
      data-size={size}
      className={cn("sj-card", size === "sm" && "sj-card--sm", className)}
      {...props}
    />
  );
}

function CardHeader({ className, ...props }: ComponentProps<"div">) {
  return <div data-slot="card-header" className={cn("sj-card-header", className)} {...props} />;
}

function CardTitle({ className, ...props }: ComponentProps<"div">) {
  return <div data-slot="card-title" className={cn("sj-card-title", className)} {...props} />;
}

function CardDescription({ className, ...props }: ComponentProps<"div">) {
  return (
    <div
      data-slot="card-description"
      className={cn("sj-card-description", className)}
      {...props}
    />
  );
}

function CardAction({ className, ...props }: ComponentProps<"div">) {
  return <div data-slot="card-action" className={cn("sj-card-action", className)} {...props} />;
}

function CardContent({ className, ...props }: ComponentProps<"div">) {
  return <div data-slot="card-content" className={cn("sj-card-content", className)} {...props} />;
}

function CardFooter({ className, ...props }: ComponentProps<"div">) {
  return <div data-slot="card-footer" className={cn("sj-card-footer", className)} {...props} />;
}

export {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle
};
export type { CardProps };
