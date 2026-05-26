import type { ReactNode } from "react";

import type { AuthUser } from "@/types";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";
import { AppSidebar, type AppNavGroup } from "@/components/layout/app-sidebar";

type AppShellProps<Route extends string = string> = {
  activeRoute: Route;
  children: ReactNode;
  navGroups: Array<AppNavGroup<Route>>;
  onNavigate: (route: Route) => void;
  user: AuthUser;
};

function AppShell<Route extends string>({
  activeRoute,
  children,
  navGroups,
  onNavigate,
  user
}: AppShellProps<Route>) {
  return (
    <SidebarProvider>
      <AppSidebar
        activeRoute={activeRoute}
        groups={navGroups}
        onNavigate={onNavigate}
        user={user}
      />
      <SidebarInset className="content">{children}</SidebarInset>
    </SidebarProvider>
  );
}

export { AppShell };
export type { AppShellProps };
