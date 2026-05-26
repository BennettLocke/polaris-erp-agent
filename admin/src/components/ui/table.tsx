import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

function Table({ className, ...props }: ComponentProps<"table">) {
  return (
    <div data-slot="table-container" className="sj-table-container">
      <table data-slot="table" className={cn("sj-table", className)} {...props} />
    </div>
  );
}

function TableHeader({ className, ...props }: ComponentProps<"thead">) {
  return <thead data-slot="table-header" className={cn("sj-table-header", className)} {...props} />;
}

function TableBody({ className, ...props }: ComponentProps<"tbody">) {
  return <tbody data-slot="table-body" className={cn("sj-table-body", className)} {...props} />;
}

function TableFooter({ className, ...props }: ComponentProps<"tfoot">) {
  return <tfoot data-slot="table-footer" className={cn("sj-table-footer", className)} {...props} />;
}

function TableRow({ className, ...props }: ComponentProps<"tr">) {
  return <tr data-slot="table-row" className={cn("sj-table-row", className)} {...props} />;
}

function TableHead({ className, ...props }: ComponentProps<"th">) {
  return <th data-slot="table-head" className={cn("sj-table-head", className)} {...props} />;
}

function TableCell({ className, ...props }: ComponentProps<"td">) {
  return <td data-slot="table-cell" className={cn("sj-table-cell", className)} {...props} />;
}

function TableCaption({ className, ...props }: ComponentProps<"caption">) {
  return <caption data-slot="table-caption" className={cn("sj-table-caption", className)} {...props} />;
}

export {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableFooter,
  TableHead,
  TableHeader,
  TableRow
};
