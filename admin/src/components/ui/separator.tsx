import * as SeparatorPrimitive from "@radix-ui/react-separator";
import type { ComponentPropsWithoutRef } from "react";

import { cn } from "@/lib/utils";

function Separator({
  className,
  orientation = "horizontal",
  decorative = true,
  ...props
}: ComponentPropsWithoutRef<typeof SeparatorPrimitive.Root>) {
  return (
    <SeparatorPrimitive.Root
      data-slot="separator"
      className={cn("sj-separator", orientation === "vertical" && "sj-separator--vertical", className)}
      decorative={decorative}
      orientation={orientation}
      {...props}
    />
  );
}

export { Separator };
