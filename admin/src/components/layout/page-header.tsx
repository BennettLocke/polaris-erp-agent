import { LogOut, PanelLeft, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger
} from "@/components/ui/dialog";
import { SidebarTrigger } from "@/components/ui/sidebar";

type PageHeaderProps = {
  eyebrow?: string;
  onLogout: () => void;
  title: string;
};

function PageHeader({ eyebrow = "React + Radix", onLogout, title }: PageHeaderProps) {
  return (
    <header className="topbar">
      <div className="topbar-title">
        <SidebarTrigger className="topbar-sidebar-trigger">
          <PanelLeft />
        </SidebarTrigger>
        <div>
          <span className="eyebrow">{eyebrow}</span>
          <h1>{title}</h1>
        </div>
      </div>
      <div className="top-actions">
        <Dialog>
          <DialogTrigger asChild>
            <Button variant="outline">
              <Sparkles data-icon="inline-start" />
              说明
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogTitle>新后台底座</DialogTitle>
            <DialogDescription>
              当前接入登录态、工作台、设置页和统一 API client；旧 `/web` 仍然保留为生产入口。
            </DialogDescription>
            <div className="dialog-actions">
              <DialogClose asChild>
                <Button>知道了</Button>
              </DialogClose>
            </div>
          </DialogContent>
        </Dialog>
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
