from pathlib import Path
import unittest

from src.engine.native_db import NativeDBClient


ROOT = Path(__file__).resolve().parents[1]


class MiniappProductListingContractTest(unittest.TestCase):
    def test_miniapp_product_reads_require_listed_products(self):
        source = (ROOT / "src" / "channels" / "http_api" / "__init__.py").read_text(encoding="utf-8")

        search_start = source.index("def mini_search_datalist_api")
        detail_start = source.index("def mini_goods_detail_api")
        next_route = source.index("@app.route", detail_start + 1)
        search_source = source[search_start:detail_start]
        detail_source = source[detail_start:next_route]

        self.assertIn("listed_only=True", search_source)
        self.assertIn("listed_only=True", detail_source)
        self.assertIn("info(product_id, listed_only=True)", detail_source)

    def test_generic_product_endpoints_can_opt_into_listed_only_reads(self):
        source = (ROOT / "src" / "channels" / "http_api" / "__init__.py").read_text(encoding="utf-8")
        service_source = (ROOT / "src" / "services" / "business" / "products.py").read_text(encoding="utf-8")
        native_source = (ROOT / "src" / "engine" / "native_db.py").read_text(encoding="utf-8")

        search_start = source.index("def product_search")
        list_start = source.index("def product_list", search_start)
        next_route = source.index("@app.route", list_start + 1)
        search_source = source[search_start:list_start]
        list_source = source[list_start:next_route]

        self.assertIn('listed_only = _request_truthy_arg("listed_only", "only_listed", "is_listed")', search_source)
        self.assertIn("search(keyword, limit=100, listed_only=listed_only)", search_source)
        self.assertIn('listed_only = _request_truthy_arg("listed_only", "only_listed", "is_listed")', list_source)
        self.assertIn("listed_only=listed_only", list_source)
        self.assertIn("def search(self, keyword: str, *, limit: int = 80, listed_only: bool = False)", service_source)
        self.assertIn("product_search(keyword, limit=limit, listed_only=listed_only)", service_source)
        self.assertIn("def product_search(self, keyword: str, limit: int = 80, *, listed_only: bool = False)", native_source)
        self.assertIn("_sku_where(keyword, active_only=True, listed_only=listed_only)", native_source)

    def test_grouped_admin_products_use_spu_level_listing_state(self):
        native_source = (ROOT / "src" / "engine" / "native_db.py").read_text(encoding="utf-8")
        admin_source = (ROOT / "admin" / "src" / "components" / "business" / "products" / "products-page.tsx").read_text(encoding="utf-8")

        product_list_start = native_source.index("def product_list")
        categories_start = native_source.index("def product_categories")
        product_list_source = native_source[product_list_start:categories_start]

        self.assertIn("group_listed_filter", product_list_source)
        self.assertIn("HAVING listed_sku_count > 0", product_list_source)
        self.assertIn("HAVING listed_sku_count = 0", product_list_source)
        self.assertIn('primary["is_listed"] = 1 if listed_variants else 0', product_list_source)
        self.assertIn("product.system_goods_is_shelves ?? product.is_listed", admin_source)
        self.assertIn("skuIds: productSkuIds(product)", admin_source)

    def test_miniapp_product_list_accepts_latest_price_and_sales_sort_modes(self):
        source = (ROOT / "src" / "channels" / "http_api" / "__init__.py").read_text(encoding="utf-8")
        service_source = (ROOT / "src" / "services" / "business" / "products.py").read_text(encoding="utf-8")
        native_source = (ROOT / "src" / "engine" / "native_db.py").read_text(encoding="utf-8")

        search_start = source.index("def mini_search_datalist_api")
        detail_start = source.index("def mini_goods_detail_api")
        search_source = source[search_start:detail_start]
        product_list_start = native_source.index("def product_list")
        categories_start = native_source.index("def product_categories")
        product_list_source = native_source[product_list_start:categories_start]

        self.assertIn('_mini_value(payload, "sort", "order_by"', search_source)
        self.assertIn("sort=sort", search_source)
        self.assertIn("sort: Any = \"\"", product_list_source)
        self.assertIn("sort: str = \"\"", service_source)
        self.assertIn("sort=sort", service_source)
        self.assertIn("_product_sort_mode(sort)", product_list_source)
        self.assertIn('{"sales", "popular", "hot", "comprehensive", "best"}', native_source)
        self.assertIn("price_asc", product_list_source)
        self.assertIn("COALESCE(NULLIF(s.retail_price, 0), NULLIF(s.min_price, 0), NULLIF(s.max_price, 0))", product_list_source)
        self.assertIn("_product_sales_rank_join_sql()", product_list_source)
        self.assertIn("FROM sales_order_item i", native_source)
        self.assertIn("JOIN sales_order so ON so.id = i.sales_order_id", native_source)
        self.assertIn("SUM(i.quantity) AS sold_qty", native_source)
        self.assertIn("group_order_sql = \"sold_qty DESC, sales_amount DESC, latest_sales_at DESC, latest_time DESC, latest_id DESC\"", product_list_source)
        self.assertIn("MIN({price_sql}) AS min_price", product_list_source)
        self.assertIn("group_order_sql = \"min_price IS NULL ASC, min_price ASC, latest_time DESC, latest_id DESC\"", product_list_source)
        self.assertIn("group_order_sql = \"latest_time DESC, latest_id DESC\"", product_list_source)

    def test_miniapp_product_list_accepts_multiple_category_ids(self):
        source = (ROOT / "src" / "channels" / "http_api" / "__init__.py").read_text(encoding="utf-8")

        search_start = source.index("def mini_search_datalist_api")
        detail_start = source.index("def mini_goods_detail_api")
        search_source = source[search_start:detail_start]

        self.assertIn("category_ids = _mini_category_ids(payload)", search_source)
        self.assertIn("category_ids=category_ids", search_source)
        self.assertIn('def _mini_category_ids(payload: dict) -> list[int]', source)
        self.assertIn('_mini_value(payload, "category_ids", "categoryIds"', source)

    def test_mini_home_fallback_requires_listed_products(self):
        source = (ROOT / "src" / "channels" / "http_api" / "__init__.py").read_text(encoding="utf-8")

        home_start = source.index("def mini_home_api")
        next_route = source.index("@app.route", home_start + 1)
        home_source = source[home_start:next_route]

        self.assertIn("listed_only=True", home_source)

    def test_miniapp_config_endpoint_is_public_and_service_backed(self):
        source = (ROOT / "src" / "channels" / "http_api" / "__init__.py").read_text(encoding="utf-8")

        endpoint_start = source.index("def miniapp_config_api")
        next_route = source.index("@app.route", endpoint_start + 1)
        endpoint_source = source[endpoint_start:next_route]

        self.assertIn('"/api/miniapp/config"', source)
        self.assertIn('"/api/miniapp/config"', source[source.index("def _miniapp_path_is_public"):source.index("@app.before_request", source.index("def _miniapp_path_is_public"))])
        self.assertIn("config_payload()", endpoint_source)

    def test_miniapp_config_schema_creates_database_backed_asset_table(self):
        schema = (ROOT / "database" / "schema" / "004_miniapp_config.sql").read_text(encoding="utf-8")

        self.assertIn("CREATE TABLE IF NOT EXISTS miniapp_asset", schema)
        self.assertIn("scene VARCHAR(50)", schema)
        self.assertIn("asset_url VARCHAR(600)", schema)
        self.assertIn("active_asset_url VARCHAR(600)", schema)
        self.assertIn("extra_json LONGTEXT", schema)
        self.assertNotIn("CREATE TABLE IF NOT EXISTS miniapp_banner", schema)
        self.assertNotIn("CREATE TABLE IF NOT EXISTS miniapp_nav_item", schema)
        self.assertNotIn("CREATE TABLE IF NOT EXISTS miniapp_category_entry", schema)
        self.assertIn("1777104334795209.jpg", schema)
        self.assertIn("app_center_nav", schema)

    def test_miniapp_categories_require_listed_products_and_exclude_removed_names(self):
        source = (ROOT / "src" / "channels" / "http_api" / "__init__.py").read_text(encoding="utf-8")
        native_source = (ROOT / "src" / "engine" / "native_db.py").read_text(encoding="utf-8")

        category_start = source.index("def mini_goods_category_api")
        search_start = source.index("def mini_search_index_api")
        category_source = source[category_start:search_start]

        self.assertIn("MINIAPP_EXCLUDED_CATEGORY_NAMES", source)
        self.assertIn("listed_only=True", category_source)
        self.assertIn("exclude_names=MINIAPP_EXCLUDED_CATEGORY_NAMES", category_source)
        self.assertIn("s.status = 'active'", native_source)
        self.assertIn("s.is_listed = 1", native_source)

    def test_color_summary_uses_visible_sku_colors_not_spu_cache(self):
        db = NativeDBClient.__new__(NativeDBClient)

        colors, text, count = db._product_color_summary([
            {"available_colors": ["红色", "蓝色"], "color": "红色"},
            {"available_colors": ["红色", "蓝色"], "color": "黄色"},
        ])

        self.assertEqual(colors, ["红色", "黄色"])
        self.assertEqual(text, "红色 / 黄色")
        self.assertEqual(count, 2)

    def test_product_detail_hydrates_listed_group_summary(self):
        source = (ROOT / "src" / "engine" / "native_db.py").read_text(encoding="utf-8")

        product_info_start = source.index("def product_info")
        color_summary_start = source.index("def _product_color_summary")
        product_info_source = source[product_info_start:color_summary_start]

        self.assertIn("_hydrate_product_group_summary(product, listed_only=True)", product_info_source)
        self.assertIn("s.is_listed = 1", product_info_source)


if __name__ == "__main__":
    unittest.main()
