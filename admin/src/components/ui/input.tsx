import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

function Input({ className, type = "text", ...props }: ComponentProps<"input">) {
  return (
    <input
      data-slot="input"
      className={cn("sj-input", className)}
      type={type}
      {...props}
    />
  );
}

export { Input };
