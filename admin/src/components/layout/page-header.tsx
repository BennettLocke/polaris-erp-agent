import { LogOut, PanelLeft } from "lucide-react";

import { Button } from "@/components/ui/button";
import { SidebarTrigger } from "@/components/ui/sidebar";

type PageHeaderProps = {
  onLogout: () => void;
  title: string;
};

function PageHeader({ onLogout, title }: PageHeaderProps) {
  return (
    <header className="topbar">
      <div className="topbar-title">
        <SidebarTrigger className="topbar-sidebar-trigger">
          <PanelLeft />
        </SidebarTrigger>
        <div>
          <h1>{title}</h1>
        </div>
      </div>
      <div className="top-actions">
        <Button variant="outline" onClick={onLogout}>
          <LogOut data-icon="inline-start" />
          退出
        </Button>
      </div>
    </header>
  );
}

export { PageHeader };
export type { PageHeaderProps };
