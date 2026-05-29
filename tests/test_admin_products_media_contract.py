from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class AdminProductsMediaContractTest(unittest.TestCase):
    def test_react_products_and_media_pages_use_native_contracts(self):
        api_source = (ROOT / "admin" / "src" / "api.ts").read_text(encoding="utf-8")
        app_source = (ROOT / "admin" / "src" / "App.tsx").read_text(encoding="utf-8")
        product_source = (
            ROOT / "admin" / "src" / "components" / "business" / "products" / "products-page.tsx"
        ).read_text(encoding="utf-8")

        self.assertIn("productList", api_source)
        self.assertIn("/api/product/list", api_source)
        self.assertIn("group=1", api_source)
        self.assertIn("productType", api_source)
        self.assertIn("product_type", api_source)
        self.assertIn("productCategories", api_source)
        self.assertIn("/api/product/categories", api_source)
        self.assertIn("deleteProduct", api_source)
        self.assertIn("/api/product/delete", api_source)
        self.assertIn("updateProductShelves", api_source)
        self.assertIn("/api/product/${id}/shelves", api_source)
        self.assertIn("productMedia", api_source)
        self.assertIn("/api/product/media", api_source)
        self.assertIn("deleteProductMedia", api_source)
        self.assertIn("/api/product/media/${id}", api_source)

        self.assertIn("export function ProductsPage", product_source)
        self.assertIn("function ProductToolbar", product_source)
        self.assertIn("function ProductCategoryTabs", product_source)
        self.assertIn("function ProductCategoryFilter", product_source)
        self.assertIn("function ProductCardGrid", product_source)
        self.assertIn("function ProductCard", product_source)
        self.assertIn("function ProductListSkeleton", product_source)
        self.assertIn("function ProductEmptyState", product_source)
        self.assertIn("function ProductSummaryStrip", product_source)
        self.assertIn("Card", product_source)
        self.assertIn("Badge", product_source)
        self.assertIn("Tabs", product_source)
        self.assertIn("Pagination", product_source)
        self.assertIn("Skeleton", product_source)
        self.assertIn("Empty", product_source)
        self.assertIn("AlertDialog", product_source)
        self.assertIn("AlertDialogAction", product_source)
        self.assertIn("onToggleShelves", product_source)
        self.assertIn("onDelete", product_source)
        self.assertIn("颜色", product_source)
        self.assertIn("件规：", product_source)
        self.assertIn("product.color_text", product_source)
        self.assertIn("productType", product_source)
        self.assertNotIn("export function MediaPage", product_source)
        self.assertNotIn("function MediaPage", product_source)
        self.assertNotIn("window.confirm", product_source)
        self.assertIn('loading="lazy"', product_source)
        self.assertIn("media_type", product_source)
        product_index = (
            ROOT / "admin" / "src" / "components" / "business" / "products" / "index.ts"
        ).read_text(encoding="utf-8")
        self.assertEqual(product_index.strip(), 'export { ProductsPage } from "./products-page";')
        self.assertIn("待绑定", product_source)
        self.assertNotIn("function ProductsPage", app_source)
        self.assertNotIn("function MediaPage", app_source)
        self.assertIn("ProductsPage", app_source)
        self.assertIn("SettingsPage", app_source)
        self.assertIn('route === "media"', app_source)
        self.assertIn("section=media", app_source)
        self.assertNotIn("MediaPage", app_source)

    def test_product_media_scope_does_not_leak_pending_assets_into_product_tab(self):
        api_source = (ROOT / "admin" / "src" / "api.ts").read_text(encoding="utf-8")
        http_source = (ROOT / "src" / "channels" / "http_api" / "__init__.py").read_text(encoding="utf-8")

        self.assertIn("includePending", api_source)
        self.assertIn('params.set("include_pending", options.includePending ? "1" : "0")', api_source)
        self.assertIn("include_pending_arg = request.args.get(\"include_pending\")", http_source)
        self.assertIn("else not bool(product_id)", http_source)
        self.assertIn("include_pending=include_pending", http_source)


if __name__ == "__main__":
    unittest.main()
