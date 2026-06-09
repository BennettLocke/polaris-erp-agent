from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class AdminSidebarContractTest(unittest.TestCase):
    def test_react_admin_uses_composable_sidebar_foundation(self):
        sidebar_path = ROOT / "admin" / "src" / "components" / "ui" / "sidebar.tsx"
        app_source = (ROOT / "admin" / "src" / "App.tsx").read_text(encoding="utf-8")
        app_shell_source = (ROOT / "admin" / "src" / "components" / "layout" / "app-shell.tsx").read_text(encoding="utf-8")
        app_sidebar_source = (ROOT / "admin" / "src" / "components" / "layout" / "app-sidebar.tsx").read_text(encoding="utf-8")
        css_source = (ROOT / "admin" / "src" / "styles.css").read_text(encoding="utf-8")

        self.assertTrue(sidebar_path.exists())
        sidebar_source = sidebar_path.read_text(encoding="utf-8")
        for name in [
            "SidebarProvider",
            "Sidebar",
            "SidebarHeader",
            "SidebarContent",
            "SidebarGroup",
            "SidebarGroupLabel",
            "SidebarMenu",
            "SidebarMenuItem",
            "SidebarMenuButton",
            "SidebarMenuBadge",
            "SidebarFooter",
            "SidebarRail",
            "SidebarInset",
            "SidebarTrigger",
        ]:
            self.assertIn(f"function {name}", sidebar_source)

        self.assertIn('@/components/ui/sidebar', app_shell_source)
        self.assertIn('@/components/ui/sidebar', app_sidebar_source)
        for usage in [
            "<SidebarProvider",
            "<SidebarInset",
        ]:
            self.assertIn(usage, app_shell_source)

        for usage in [
            "<Sidebar",
            "<SidebarHeader",
            "<SidebarContent",
            "<SidebarGroup",
            "<SidebarGroupLabel",
            "<SidebarMenu",
            "<SidebarMenuItem",
            "<SidebarMenuButton",
            "<SidebarMenuBadge",
            "<SidebarFooter",
            "<SidebarRail",
        ]:
            self.assertIn(usage, app_sidebar_source)

        self.assertNotIn('<aside className="sidebar">', app_source)
        self.assertNotIn("<nav>", app_source)

        for css_class in [
            ".sj-sidebar-provider",
            ".sj-sidebar",
            ".sj-sidebar-header",
            ".sj-sidebar-content",
            ".sj-sidebar-group-label",
            ".sj-sidebar-menu-button",
            ".sj-sidebar-menu-badge",
            ".sj-sidebar-footer",
            ".sj-sidebar-rail",
            ".sj-sidebar-inset",
            ".sj-sidebar-trigger",
            '[data-sidebar-collapsed="true"]',
        ]:
            self.assertIn(css_class, css_source)

    def test_sidebar_visual_contract_follows_shadcn_reference(self):
        app_source = (ROOT / "admin" / "src" / "components" / "layout" / "app-sidebar.tsx").read_text(encoding="utf-8")
        css_source = (ROOT / "admin" / "src" / "styles.css").read_text(encoding="utf-8")

        for token in [
            "--sj-sidebar-width: 256px;",
            "--sj-sidebar-width-collapsed: 48px;",
            "--sj-sidebar-background: #fafafa;",
            "--sj-sidebar-accent: #f4f4f5;",
            "--sj-sidebar-foreground: #3f3f46;",
            "--sj-sidebar-muted: #71717a;",
        ]:
            self.assertIn(token, css_source)

        for rule in [
            "background: var(--sj-sidebar-background);",
            "min-height: 32px;",
            "border-radius: 6px;",
            "width: 16px;",
            "height: 16px;",
        ]:
            self.assertIn(rule, css_source)

        self.assertIn('<SidebarMenu className="sidebar-workspace-menu">', app_source)
        self.assertIn('<SidebarMenuButton className="sidebar-workspace-button"', app_source)
        self.assertIn("ChevronsUpDown", app_source)
        self.assertIn("data-slot", (ROOT / "admin" / "src" / "components" / "ui" / "sidebar.tsx").read_text(encoding="utf-8"))
        self.assertNotIn('className="brand"', app_source)

    def test_react_admin_extracts_layout_components(self):
        layout_dir = ROOT / "admin" / "src" / "components" / "layout"
        app_source = (ROOT / "admin" / "src" / "App.tsx").read_text(encoding="utf-8")

        expected_files = {
            "app-shell.tsx": ["AppShell", "AppShellProps"],
            "app-sidebar.tsx": ["AppSidebar", "AppNavGroup", "AppNavItem"],
            "page-header.tsx": ["PageHeader", "PageHeaderProps"],
            "toolbar.tsx": ["Toolbar", "ToolbarProps"],
        }
        for filename, names in expected_files.items():
            path = layout_dir / filename
            self.assertTrue(path.exists(), filename)
            source = path.read_text(encoding="utf-8")
            for name in names:
                self.assertIn(name, source, f"{filename} should expose {name}")

        for import_path in [
            './components/layout/app-shell',
            './components/layout/app-sidebar',
            './components/layout/page-header',
        ]:
            self.assertIn(import_path, app_source)

        self.assertIn("<AppShell", app_source)
        self.assertIn("<PageHeader", app_source)
        self.assertNotIn("function AdminShell", app_source)
        page_header_source = (layout_dir / "page-header.tsx").read_text(encoding="utf-8")
        self.assertNotIn("React + Radix", page_header_source)
        self.assertNotIn("eyebrow", page_header_source)
        self.assertNotIn("待迁移页面", app_source)
        self.assertNotIn("后续迁移", app_source)
        self.assertNotIn("当前接入登录态、工作台、设置页", page_header_source)
        self.assertNotIn("说明", page_header_source)
        self.assertNotIn("商品、库存、订单、设置和工作台已统一接入", page_header_source)
        self.assertNotIn("Sparkles", page_header_source)
        for sidebar_usage in [
            "<SidebarProvider",
            "<SidebarHeader",
            "<SidebarContent",
            "<SidebarFooter",
            "<SidebarRail",
            "<SidebarInset",
        ]:
            self.assertNotIn(sidebar_usage, app_source)


if __name__ == "__main__":
    unittest.main()
