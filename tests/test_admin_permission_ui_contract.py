from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class AdminPermissionUiContractTest(unittest.TestCase):
    def test_web_auth_returns_permissions_for_frontend(self):
        auth_source = (ROOT / "src" / "services" / "business" / "auth.py").read_text(encoding="utf-8")
        types_source = (ROOT / "admin" / "src" / "types.ts").read_text(encoding="utf-8")

        self.assertIn('"permissions": sorted', auth_source)
        self.assertIn("FIXED_ROLE_PERMISSIONS", auth_source)
        self.assertIn("permissions: string[]", types_source)

    def test_react_admin_uses_permission_aware_navigation_and_actions(self):
        helper_source = (ROOT / "admin" / "src" / "lib" / "permissions.ts").read_text(encoding="utf-8")
        app_source = (ROOT / "admin" / "src" / "App.tsx").read_text(encoding="utf-8")
        inventory_source = (
            ROOT / "admin" / "src" / "components" / "business" / "inventory" / "inventory-page.tsx"
        ).read_text(encoding="utf-8")
        customers_source = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (ROOT / "admin" / "src" / "components" / "business" / "customers").glob("*.tsx")
        )

        self.assertIn("function hasPermission", helper_source)
        self.assertIn('permission === "设置"', helper_source)
        self.assertIn("allowedNavGroups", app_source)
        self.assertIn('hasPermission(user, "设置")', app_source)
        self.assertIn("currentUser={user}", app_source)
        self.assertIn("currentUser?: AuthUser", inventory_source)
        self.assertIn("canAdjustInventory", inventory_source)
        self.assertIn("canTransferInventory", inventory_source)
        self.assertIn("canStocktakeInventory", inventory_source)
        self.assertIn("disabled={!canAdjustInventory", inventory_source)
        self.assertIn("canAdjustBalance", customers_source)
        self.assertIn("currentUser?: AuthUser", customers_source)
        self.assertIn('hasPermission(currentUser, "调余额")', customers_source)


if __name__ == "__main__":
    unittest.main()
