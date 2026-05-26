from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class AdminComboboxContractTest(unittest.TestCase):
    def test_react_admin_has_shadcn_style_combobox_foundation(self):
        component_path = ROOT / "admin" / "src" / "components" / "ui" / "combobox.tsx"
        compatibility_path = ROOT / "admin" / "src" / "components" / "combobox.tsx"
        customer_field_source = (
            ROOT / "admin" / "src" / "components" / "business" / "sales-create" / "sales-customer-field.tsx"
        ).read_text(encoding="utf-8")
        css_source = (ROOT / "admin" / "src" / "styles.css").read_text(encoding="utf-8")

        self.assertTrue(component_path.exists())
        self.assertTrue(compatibility_path.exists())
        component_source = component_path.read_text(encoding="utf-8")
        for name in [
            "Combobox",
            "ComboboxInput",
            "ComboboxContent",
            "ComboboxEmpty",
            "ComboboxList",
            "ComboboxItem",
        ]:
            self.assertIn(f"function {name}", component_source)

        self.assertIn("itemToStringValue", component_source)
        self.assertIn("selectOnEnter", component_source)
        self.assertIn("aria-expanded", component_source)
        self.assertIn('role="combobox"', component_source)
        self.assertIn('role="listbox"', component_source)
        self.assertIn('role="option"', component_source)

        self.assertIn("ComboboxInput", customer_field_source)
        self.assertIn("itemToStringValue", customer_field_source)
        self.assertIn("ComboboxItem", customer_field_source)
        self.assertIn("selectOnEnter={false}", customer_field_source)
        self.assertIn("sj-combobox", css_source)


if __name__ == "__main__":
    unittest.main()
