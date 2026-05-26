from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class AdminProductsRedesignContractTest(unittest.TestCase):
    def test_product_page_uses_compact_filters_and_safe_actions(self):
        api_source = (ROOT / "admin" / "src" / "api.ts").read_text(encoding="utf-8")
        product_source = (
            ROOT / "admin" / "src" / "components" / "business" / "products" / "products-page.tsx"
        ).read_text(encoding="utf-8")
        style_source = (ROOT / "admin" / "src" / "styles.css").read_text(encoding="utf-8")
        toolbar_source = product_source.split("function ProductToolbar", 1)[1].split(
            "function ProductCategoryTabs", 1
        )[0]
        card_source = product_source.split("function ProductCard", 1)[1].split(
            "function ProductListSkeleton", 1
        )[0]

        self.assertIn("listedState", api_source)
        self.assertIn("listed_state", api_source)
        self.assertIn("stockMode", api_source)
        self.assertIn("stock_mode", api_source)
        self.assertIn("quality", api_source)

        self.assertNotIn("<CardTitle>商品</CardTitle>", toolbar_source)
        self.assertIn("ProductQuickFilters", product_source)
        self.assertIn("已上架", product_source)
        self.assertIn("未上架", product_source)
        self.assertIn("扣库存", product_source)
        self.assertIn("不扣库存", product_source)
        self.assertIn("无主图", product_source)
        self.assertIn("缺件规", product_source)

        self.assertIn("DropdownMenu", card_source)
        self.assertIn("DropdownMenuTrigger", card_source)
        self.assertIn("DropdownMenuItem", card_source)
        footer_source = card_source.split('<CardFooter className="product-spu-actions">', 1)[1].split(
            "</CardFooter>", 1
        )[0]
        self.assertNotIn('variant="destructive"', footer_source)
        shelf_action_source = footer_source.split("<DropdownMenu>", 1)[0]
        self.assertIn('setConfirmAction("shelf")', shelf_action_source)
        self.assertIn('{isListed ? "下架" : "上架"}', shelf_action_source)
        self.assertIn("aspect-ratio: 1 / 1;", style_source)
        self.assertIn("object-fit: contain;", style_source)
        self.assertIn("repeat(auto-fill, minmax(208px, 1fr))", style_source)
        self.assertIn("product-spu-actions--primary", product_source)
        self.assertIn("product-spu-summary-row", card_source)
        self.assertIn("product-spu-detail-row", card_source)
        self.assertIn("product-spu-price", card_source)
        self.assertIn("product-spu-stock", card_source)
        self.assertNotIn("product-spu-metrics", card_source)
        self.assertNotIn("productColorCount(product)} 色", card_source)
        self.assertIn("product-spu-status--listed", card_source)
        self.assertIn("product-spu-status--unlisted", card_source)
        self.assertIn("product-spu-color-text", card_source)
        self.assertIn("product-spu-meta-label", card_source)
        self.assertIn("product-spu-meta-value", card_source)
        self.assertIn("productColorsInline", product_source)
        colors_source = card_source.split('<div className="product-spu-color-text"', 1)[1].split("</div>", 1)[0]
        self.assertNotIn("<Badge", colors_source)
        self.assertIn("--sj-success-soft", style_source)
        self.assertIn("--sj-danger-soft", style_source)
        self.assertIn("height: 18px;", style_source)
        self.assertIn("font-size: 11px;", style_source)

    def test_product_list_api_accepts_admin_filter_contract(self):
        api_source = (ROOT / "src" / "channels" / "http_api" / "__init__.py").read_text(encoding="utf-8")
        service_source = (ROOT / "src" / "services" / "business" / "products.py").read_text(encoding="utf-8")
        db_source = (ROOT / "src" / "engine" / "native_db.py").read_text(encoding="utf-8")

        self.assertIn("listed_state", api_source)
        self.assertIn("stock_mode", api_source)
        self.assertIn("quality", api_source)
        self.assertIn("listed_state", service_source)
        self.assertIn("stock_mode", service_source)
        self.assertIn("quality", service_source)
        self.assertIn("s.is_listed = 1", db_source)
        self.assertIn("s.is_stock_item = 0", db_source)
        self.assertIn("missing_case_pack", db_source)
        self.assertIn("missing_image", db_source)

    def test_product_page_size_tracks_visible_grid_capacity(self):
        product_source = (
            ROOT / "admin" / "src" / "components" / "business" / "products" / "products-page.tsx"
        ).read_text(encoding="utf-8")

        self.assertIn("calculateProductPageSize", product_source)
        self.assertIn("PRODUCT_PAGE_SIZE_MIN", product_source)
        self.assertIn("PRODUCT_PAGE_SIZE_MAX", product_source)
        self.assertIn("PRODUCT_PAGE_SIZE_BUFFER_ROWS", product_source)
        self.assertIn("ResizeObserver", product_source)
        self.assertIn("gridRef", product_source)
        self.assertIn("setPageSize", product_source)
        self.assertIn("productPageRangeText", product_source)
        self.assertIn("pageSize={pageSize}", product_source)
        self.assertNotIn("const pageSize = 14;", product_source)


if __name__ == "__main__":
    unittest.main()
