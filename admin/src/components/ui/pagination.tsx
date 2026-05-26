import { ChevronLeft, ChevronRight, MoreHorizontal } from "lucide-react";
import type { ComponentProps } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

function Pagination({ className, ...props }: ComponentProps<"nav">) {
  return <nav data-slot="pagination" aria-label="pagination" className={cn("sj-pagination", className)} {...props} />;
}

function PaginationContent({ className, ...props }: ComponentProps<"ul">) {
  return <ul data-slot="pagination-content" className={cn("sj-pagination-content", className)} {...props} />;
}

function PaginationItem({ className, ...props }: ComponentProps<"li">) {
  return <li data-slot="pagination-item" className={cn("sj-pagination-item", className)} {...props} />;
}

type PaginationLinkProps = ComponentProps<"button"> & {
  isActive?: boolean;
};

function PaginationLink({ className, isActive, ...props }: PaginationLinkProps) {
  return (
    <Button
      data-slot="pagination-link"
      variant={isActive ? "default" : "outline"}
      size="sm"
      aria-current={isActive ? "page" : undefined}
      className={cn("sj-pagination-link", className)}
      {...props}
    />
  );
}

function PaginationPrevious({ className, children = "上一页", ...props }: ComponentProps<"button">) {
  return (
    <PaginationLink className={cn("sj-pagination-previous", className)} {...props}>
      <ChevronLeft data-icon="inline-start" />
      {children}
    </PaginationLink>
  );
}

function PaginationNext({ className, children = "下一页", ...props }: ComponentProps<"button">) {
  return (
    <PaginationLink className={cn("sj-pagination-next", className)} {...props}>
      {children}
      <ChevronRight data-icon="inline-end" />
    </PaginationLink>
  );
}

function PaginationEllipsis({ className, ...props }: ComponentProps<"span">) {
  return (
    <span data-slot="pagination-ellipsis" className={cn("sj-pagination-ellipsis", className)} {...props}>
      <MoreHorizontal />
      <span className="sj-sr-only">More pages</span>
    </span>
  );
}

export {
  Pagination,
  PaginationContent,
  PaginationEllipsis,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious
};
