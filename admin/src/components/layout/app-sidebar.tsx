import { ChevronsUpDown, type LucideIcon } from "lucide-react";

import type { AuthUser } from "@/types";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail
} from "@/components/ui/sidebar";

type AppNavItem<Route extends string = string> = {
  key: Route;
  label: string;
  icon: LucideIcon;
  badge?: string;
};

type AppNavGroup<Route extends string = string> = {
  label: string;
  items: Array<AppNavItem<Route>>;
};

type AppSidebarProps<Route extends string = string> = {
  activeRoute: Route;
  groups: Array<AppNavGroup<Route>>;
  onNavigate: (route: Route) => void;
  user: AuthUser;
};

function AppSidebar<Route extends string>({
  activeRoute,
  groups,
  onNavigate,
  user
}: AppSidebarProps<Route>) {
  return (
    <Sidebar>
      <SidebarHeader>
        <SidebarMenu className="sidebar-workspace-menu">
          <SidebarMenuItem>
            <SidebarMenuButton className="sidebar-workspace-button" title="肆计包装">
              <div className="brand-mark">北</div>
              <div className="brand-copy">
                <strong>肆计包装</strong>
                <span>北极星后台</span>
              </div>
              <ChevronsUpDown />
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        {groups.map((group) => (
          <SidebarGroup key={group.label}>
            <SidebarGroupLabel>{group.label}</SidebarGroupLabel>
            <SidebarMenu>
              {group.items.map((item) => {
                const Icon = item.icon;
                return (
                  <SidebarMenuItem key={item.key}>
                    <SidebarMenuButton
                      isActive={activeRoute === item.key}
                      onClick={() => onNavigate(item.key)}
                      title={item.label}
                    >
                      <Icon />
                      <span>{item.label}</span>
                      {item.badge ? <SidebarMenuBadge>{item.badge}</SidebarMenuBadge> : null}
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                );
              })}
            </SidebarMenu>
          </SidebarGroup>
        ))}
      </SidebarContent>
      <SidebarFooter>
        <SidebarMenu className="sidebar-user-menu">
          <SidebarMenuItem>
            <SidebarMenuButton className="sidebar-user-button" title={user.display_name || user.username}>
              <div className="user-avatar">{(user.display_name || user.username || "账").slice(0, 1)}</div>
              <div className="user-copy">
                <strong>{user.display_name || user.username}</strong>
                <span>{user.role_text || "账号"}</span>
              </div>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}

export { AppSidebar };
export type { AppNavGroup, AppNavItem, AppSidebarProps };
