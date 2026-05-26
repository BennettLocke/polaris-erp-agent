import {
  createContext,
  useContext,
  useMemo,
  useState,
  type ButtonHTMLAttributes,
  type HTMLAttributes,
  type ReactNode
} from "react";

import { cn } from "@/lib/utils";

type SidebarContextValue = {
  collapsed: boolean;
  setCollapsed: (collapsed: boolean) => void;
  toggleSidebar: () => void;
};

const SidebarContext = createContext<SidebarContextValue | null>(null);

function useSidebar() {
  const context = useContext(SidebarContext);
  if (!context) {
    throw new Error("useSidebar must be used inside SidebarProvider");
  }
  return context;
}

type SidebarProviderProps = HTMLAttributes<HTMLDivElement> & {
  defaultCollapsed?: boolean;
};

function SidebarProvider({
  defaultCollapsed = false,
  className,
  children,
  ...props
}: SidebarProviderProps) {
  const [collapsed, setCollapsed] = useState(defaultCollapsed);
  const value = useMemo<SidebarContextValue>(
    () => ({
      collapsed,
      setCollapsed,
      toggleSidebar: () => setCollapsed((next) => !next)
    }),
    [collapsed]
  );

  return (
    <SidebarContext.Provider value={value}>
      <div
        data-slot="sidebar-wrapper"
        className={cn("sj-sidebar-provider", className)}
        data-state={collapsed ? "collapsed" : "expanded"}
        data-sidebar-collapsed={collapsed ? "true" : "false"}
        {...props}
      >
        {children}
      </div>
    </SidebarContext.Provider>
  );
}

function Sidebar({ className, ...props }: HTMLAttributes<HTMLElement>) {
  return (
    <aside
      data-slot="sidebar"
      data-sidebar="sidebar"
      className={cn("sj-sidebar", className)}
      {...props}
    />
  );
}

function SidebarHeader({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      data-slot="sidebar-header"
      data-sidebar="header"
      className={cn("sj-sidebar-header", className)}
      {...props}
    />
  );
}

function SidebarContent({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      data-slot="sidebar-content"
      data-sidebar="content"
      className={cn("sj-sidebar-content", className)}
      {...props}
    />
  );
}

function SidebarGroup({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <section
      data-slot="sidebar-group"
      data-sidebar="group"
      className={cn("sj-sidebar-group", className)}
      {...props}
    />
  );
}

function SidebarGroupLabel({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      data-slot="sidebar-group-label"
      data-sidebar="group-label"
      className={cn("sj-sidebar-group-label", className)}
      {...props}
    />
  );
}

function SidebarMenu({ className, ...props }: HTMLAttributes<HTMLUListElement>) {
  return (
    <ul
      data-slot="sidebar-menu"
      data-sidebar="menu"
      className={cn("sj-sidebar-menu", className)}
      {...props}
    />
  );
}

function SidebarMenuItem({ className, ...props }: HTMLAttributes<HTMLLIElement>) {
  return (
    <li
      data-slot="sidebar-menu-item"
      data-sidebar="menu-item"
      className={cn("sj-sidebar-menu-item", className)}
      {...props}
    />
  );
}

type SidebarMenuButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  isActive?: boolean;
};

function SidebarMenuButton({
  isActive = false,
  className,
  children,
  type,
  ...props
}: SidebarMenuButtonProps) {
  return (
    <button
      type={type ?? "button"}
      data-slot="sidebar-menu-button"
      data-sidebar="menu-button"
      className={cn("sj-sidebar-menu-button", className)}
      data-active={isActive ? "true" : "false"}
      aria-current={isActive ? "page" : undefined}
      {...props}
    >
      {children}
    </button>
  );
}

function SidebarMenuBadge({ className, ...props }: HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      data-slot="sidebar-menu-badge"
      data-sidebar="menu-badge"
      className={cn("sj-sidebar-menu-badge", className)}
      {...props}
    />
  );
}

function SidebarFooter({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      data-slot="sidebar-footer"
      data-sidebar="footer"
      className={cn("sj-sidebar-footer", className)}
      {...props}
    />
  );
}

function SidebarRail({ className, type, ...props }: ButtonHTMLAttributes<HTMLButtonElement>) {
  const { toggleSidebar } = useSidebar();
  return (
    <button
      type={type ?? "button"}
      data-slot="sidebar-rail"
      data-sidebar="rail"
      className={cn("sj-sidebar-rail", className)}
      aria-label="Toggle sidebar"
      onClick={toggleSidebar}
      {...props}
    />
  );
}

function SidebarInset({ className, ...props }: HTMLAttributes<HTMLElement>) {
  return <main data-slot="sidebar-inset" className={cn("sj-sidebar-inset", className)} {...props} />;
}

type SidebarTriggerProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  children?: ReactNode;
};

function SidebarTrigger({ className, children, type, ...props }: SidebarTriggerProps) {
  const { collapsed, toggleSidebar } = useSidebar();
  return (
    <button
      type={type ?? "button"}
      data-slot="sidebar-trigger"
      data-sidebar="trigger"
      className={cn("sj-sidebar-trigger", className)}
      aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
      aria-pressed={collapsed}
      onClick={toggleSidebar}
      {...props}
    >
      {children}
    </button>
  );
}

export {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarRail,
  SidebarTrigger,
  useSidebar
};
