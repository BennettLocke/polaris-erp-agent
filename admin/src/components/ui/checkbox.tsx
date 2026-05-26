import * as CheckboxPrimitive from "@radix-ui/react-checkbox";
import { Check } from "lucide-react";
import type { ComponentPropsWithoutRef } from "react";

import { cn } from "@/lib/utils";

function Checkbox({
  className,
  ...props
}: ComponentPropsWithoutRef<typeof CheckboxPrimitive.Root>) {
  return (
    <CheckboxPrimitive.Root data-slot="checkbox" className={cn("sj-checkbox", className)} {...props}>
      <CheckboxPrimitive.Indicator data-slot="checkbox-indicator" className="sj-checkbox-indicator">
        <Check />
      </CheckboxPrimitive.Indicator>
    </CheckboxPrimitive.Root>
  );
}

export { Checkbox };
