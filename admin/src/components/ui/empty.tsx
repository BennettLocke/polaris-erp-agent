import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

function Empty({ className, ...props }: ComponentProps<"div">) {
  return <div data-slot="empty" className={cn("sj-empty", className)} {...props} />;
}

function EmptyHeader({ className, ...props }: ComponentProps<"div">) {
  return <div data-slot="empty-header" className={cn("sj-empty-header", className)} {...props} />;
}

function EmptyTitle({ className, ...props }: ComponentProps<"div">) {
  return <div data-slot="empty-title" className={cn("sj-empty-title", className)} {...props} />;
}

function EmptyDescription({ className, ...props }: ComponentProps<"div">) {
  return <div data-slot="empty-description" className={cn("sj-empty-description", className)} {...props} />;
}

function EmptyContent({ className, ...props }: ComponentProps<"div">) {
  return <div data-slot="empty-content" className={cn("sj-empty-content", className)} {...props} />;
}

export { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyTitle };
