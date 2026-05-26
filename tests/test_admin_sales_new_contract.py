from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


def extract_function_section(source: str, name: str) -> str:
    signature_index = source.index(f"function {name}(")
    body_start = source.index("{", signature_index)
    depth = 0
    for index in range(body_start, len(source)):
        char = source[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[signature_index:index + 1]
    raise AssertionError(f"Could not extract function {name}")


class AdminSalesNewContractTest(unittest.TestCase):
    def test_react_sales_new_page_uses_service_layer_contract(self):
        api_source = (ROOT / "admin" / "src" / "api.ts").read_text(encoding="utf-8")
        app_source = (ROOT / "admin" / "src" / "App.tsx").read_text(encoding="utf-8")

        self.assertIn("createCustomer", api_source)
        self.assertIn("/api/customer/create", api_source)
        self.assertIn("searchProductsForSales", api_source)
        self.assertIn("/api/product/list", api_source)
        self.assertIn("group=1", api_source)
        self.assertIn("customerPrice", api_source)
        self.assertIn("/api/customer/price", api_source)
        self.assertIn("createSalesOrder", api_source)
        self.assertIn("/api/sales/add", api_source)

        self.assertIn("function SalesNewPage", app_source)
        self.assertIn("selectCustomer", app_source)
        self.assertIn('setPayStatus("monthly")', app_source)
        self.assertIn('setPayStatus("paid")', app_source)
        self.assertIn("addSalesLine", app_source)
        self.assertIn("submitSalesOrder", app_source)
        self.assertIn("products: lines.map", app_source)

    def test_sales_new_page_uses_shadcn_component_layer(self):
        app_source = (ROOT / "admin" / "src" / "App.tsx").read_text(encoding="utf-8")
        section = extract_function_section(app_source, "SalesNewPage")

        for import_path in [
            './components/business/sales-create',
            './components/ui/button',
            './components/ui/card',
            './components/layout/toolbar',
        ]:
            self.assertIn(import_path, app_source)

        self.assertIn("<Button", section)
        self.assertIn("<Card", section)
        self.assertIn("<Toolbar", section)
        for component in [
            "SalesCustomerField",
            "SalesPaymentFields",
            "SalesProductSearch",
            "SalesLineTable",
            "SalesSummaryCard",
            "SalesResultCard",
            "CreateCustomerDialog",
            "SalesOrderDetailSheet",
        ]:
            self.assertIn(f"<{component}", section)

        for raw_element in ["<button", "<input", "<select"]:
            self.assertNotIn(raw_element, section)
        self.assertNotIn("datetime-local", section)

        forbidden_class_tokens = {"primary-action", "ghost-action", "status-badge", "panel"}
        class_values = []
        for chunk in section.split('className="')[1:]:
            class_values.append(chunk.split('"', 1)[0])
        used_tokens = {token for value in class_values for token in value.split()}
        self.assertTrue(
            forbidden_class_tokens.isdisjoint(used_tokens),
            f"SalesNewPage still uses legacy classes: {sorted(forbidden_class_tokens & used_tokens)}",
        )


if __name__ == "__main__":
    unittest.main()
