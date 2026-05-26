from pathlib import Path
import json
import unittest


ROOT = Path(__file__).resolve().parents[1]
ADMIN = ROOT / "admin"


class AdminShadcnFoundationContractTest(unittest.TestCase):
    def test_admin_has_shadcn_project_foundation(self):
        components_path = ADMIN / "components.json"
        utils_path = ADMIN / "src" / "lib" / "utils.ts"
        tsconfig_path = ADMIN / "tsconfig.json"
        vite_config_path = ADMIN / "vite.config.ts"
        package_path = ADMIN / "package.json"

        self.assertTrue(components_path.exists(), "admin/components.json is required")
        self.assertTrue(utils_path.exists(), "admin/src/lib/utils.ts is required")

        components = json.loads(components_path.read_text(encoding="utf-8"))
        aliases = components.get("aliases", {})
        self.assertEqual(aliases.get("components"), "@/components")
        self.assertEqual(aliases.get("ui"), "@/components/ui")
        self.assertEqual(aliases.get("utils"), "@/lib/utils")

        utils_source = utils_path.read_text(encoding="utf-8")
        self.assertIn("clsx", utils_source)
        self.assertIn("twMerge", utils_source)
        self.assertIn("export function cn", utils_source)

        tsconfig = json.loads(tsconfig_path.read_text(encoding="utf-8"))
        compiler_options = tsconfig.get("compilerOptions", {})
        self.assertEqual(compiler_options.get("baseUrl"), ".")
        self.assertIn("@/*", compiler_options.get("paths", {}))

        vite_source = vite_config_path.read_text(encoding="utf-8")
        self.assertIn("fileURLToPath", vite_source)
        self.assertIn('"@":', vite_source)

        package = json.loads(package_path.read_text(encoding="utf-8"))
        deps = package.get("dependencies", {})
        for dep in ["clsx", "tailwind-merge", "class-variance-authority", "@radix-ui/react-slot"]:
            self.assertIn(dep, deps)

        for dep in [
            "@radix-ui/react-alert-dialog",
            "@radix-ui/react-checkbox",
            "@radix-ui/react-dropdown-menu",
            "@radix-ui/react-popover",
            "@radix-ui/react-scroll-area",
            "@radix-ui/react-select",
            "@radix-ui/react-separator",
            "@radix-ui/react-switch",
        ]:
            self.assertIn(dep, deps)

    def test_core_ui_components_live_under_ui_directory(self):
        for filename in [
            "button.tsx",
            "badge.tsx",
            "card.tsx",
            "input.tsx",
            "field.tsx",
            "calendar.tsx",
            "date-picker.tsx",
            "date-time-picker.tsx",
            "textarea.tsx",
            "sidebar.tsx",
            "select.tsx",
            "combobox.tsx",
            "checkbox.tsx",
            "switch.tsx",
            "table.tsx",
            "pagination.tsx",
            "dialog.tsx",
            "alert-dialog.tsx",
            "sheet.tsx",
            "tabs.tsx",
            "dropdown-menu.tsx",
            "tooltip.tsx",
            "popover.tsx",
            "separator.tsx",
            "skeleton.tsx",
            "empty.tsx",
            "scroll-area.tsx",
        ]:
            self.assertTrue((ADMIN / "src" / "components" / "ui" / filename).exists(), filename)

    def test_core_ui_components_expose_expected_shadcn_api(self):
        ui_dir = ADMIN / "src" / "components" / "ui"
        button_source = (ui_dir / "button.tsx").read_text(encoding="utf-8")
        card_source = (ui_dir / "card.tsx").read_text(encoding="utf-8")
        field_source = (ui_dir / "field.tsx").read_text(encoding="utf-8")

        self.assertIn("buttonVariants", button_source)
        self.assertIn("variant", button_source)
        self.assertIn("size", button_source)
        self.assertIn("asChild", button_source)

        for export_name in ["CardHeader", "CardContent", "CardFooter", "CardTitle"]:
            self.assertIn(export_name, card_source)

        for export_name in ["FieldGroup", "Field", "FieldLabel", "FieldDescription"]:
            self.assertIn(export_name, field_source)

    def test_extended_ui_components_expose_expected_shadcn_api(self):
        ui_dir = ADMIN / "src" / "components" / "ui"
        expected_exports = {
            "select.tsx": ["Select", "SelectTrigger", "SelectContent", "SelectItem"],
            "combobox.tsx": ["Combobox", "ComboboxInput", "ComboboxContent", "ComboboxItem"],
            "calendar.tsx": ["Calendar"],
            "date-picker.tsx": ["DatePicker", "Calendar", "Popover"],
            "date-time-picker.tsx": ["DateTimePicker", "Calendar", "Popover", "Select"],
            "checkbox.tsx": ["Checkbox"],
            "switch.tsx": ["Switch"],
            "table.tsx": ["Table", "TableHeader", "TableBody", "TableRow", "TableCell"],
            "pagination.tsx": ["Pagination", "PaginationContent", "PaginationItem", "PaginationLink"],
            "dialog.tsx": ["Dialog", "DialogTrigger", "DialogContent", "DialogTitle"],
            "alert-dialog.tsx": ["AlertDialog", "AlertDialogTrigger", "AlertDialogContent", "AlertDialogAction"],
            "sheet.tsx": ["Sheet", "SheetTrigger", "SheetContent", "SheetTitle"],
            "tabs.tsx": ["Tabs", "TabsList", "TabsTrigger", "TabsContent"],
            "dropdown-menu.tsx": ["DropdownMenu", "DropdownMenuTrigger", "DropdownMenuContent", "DropdownMenuItem"],
            "tooltip.tsx": ["Tooltip", "TooltipTrigger", "TooltipContent", "TooltipProvider"],
            "popover.tsx": ["Popover", "PopoverTrigger", "PopoverContent"],
            "separator.tsx": ["Separator"],
            "skeleton.tsx": ["Skeleton"],
            "empty.tsx": ["Empty", "EmptyHeader", "EmptyTitle", "EmptyDescription"],
            "scroll-area.tsx": ["ScrollArea", "ScrollBar"],
        }
        for filename, exports in expected_exports.items():
            source = (ui_dir / filename).read_text(encoding="utf-8")
            for export_name in exports:
                self.assertIn(export_name, source, f"{filename} should expose {export_name}")

    def test_ui_foundation_must_not_use_legacy_ui_classes(self):
        legacy_classes = [
            "primary-action",
            "ghost-action",
            "status-badge",
            "metric-card",
            "panel",
        ]
        ui_dir = ADMIN / "src" / "components" / "ui"
        paths = list(ui_dir.glob("*.tsx")) if ui_dir.exists() else []
        self.assertTrue(paths, "ui component files are required before checking legacy class usage")
        for path in paths:
            source = path.read_text(encoding="utf-8")
            for legacy in legacy_classes:
                self.assertNotIn(legacy, source, f"{path.name} still uses legacy class {legacy}")


if __name__ == "__main__":
    unittest.main()
