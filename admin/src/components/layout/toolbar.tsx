import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

type ToolbarProps = {
  actions?: ReactNode;
  children?: ReactNode;
  className?: string;
  title?: ReactNode;
};

function Toolbar({ actions, children, className, title }: ToolbarProps) {
  return (
    <div data-slot="toolbar" className={cn("sj-toolbar", className)}>
      <div className="sj-toolbar-main">
        {title ? <div className="sj-toolbar-title">{title}</div> : null}
        {children}
      </div>
      {actions ? <div className="sj-toolbar-actions">{actions}</div> : null}
    </div>
  );
}

export { Toolbar };
export type { ToolbarProps };
