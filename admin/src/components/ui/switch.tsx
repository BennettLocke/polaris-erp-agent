import * as SwitchPrimitive from "@radix-ui/react-switch";
import type { ComponentPropsWithoutRef } from "react";

import { cn } from "@/lib/utils";

function Switch({
  className,
  ...props
}: ComponentPropsWithoutRef<typeof SwitchPrimitive.Root>) {
  return (
    <SwitchPrimitive.Root data-slot="switch" className={cn("sj-switch", className)} {...props}>
      <SwitchPrimitive.Thumb data-slot="switch-thumb" className="sj-switch-thumb" />
    </SwitchPrimitive.Root>
  );
}

export { Switch };
