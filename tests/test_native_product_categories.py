from pathlib import Path
import unittest

from src.engine.native_db import NativeDBClient, _merge_category_names


ROOT = Path(__file__).resolve().parents[1]


class ProductCategoryIconClient(NativeDBClient):
    def __new__(cls):
        return object.__new__(cls)

    def __init__(self):
        self.last_sql = ""

    def query(self, sql: str, params=None):
        self.last_sql = sql
        return [
            {
                "id": 1,
                "parent_id": 0,
                "name": "半斤礼盒",
                "product_type": "gift_box",
                "inventory_policy": "strict",
                "sort_order": 10,
                "is_enabled": 1,
                "total": 19,
                "icon": "https://img.513sjbz.com/static/upload/images/goods_category/2026/03/31/1774944779609269.png",
                "icon_active": "https://img.513sjbz.com/static/upload/images/goods_category/2026/03/31/1774944779374264.png",
                "realistic_images": "",
                "big_images": "",
            }
        ]


class NativeProductCategoriesTest(unittest.TestCase):
    def test_product_categories_returns_shopxo_icon_fields(self):
        client = ProductCategoryIconClient()

        categories = client.product_categories()

        self.assertIn("c.icon", client.last_sql)
        self.assertEqual(
            categories[0]["icon"],
            "https://img.513sjbz.com/static/upload/images/goods_category/2026/03/31/1774944779609269.png",
        )
        self.assertEqual(
            categories[0]["icon_active"],
            "https://img.513sjbz.com/static/upload/images/goods_category/2026/03/31/1774944779374264.png",
        )
        self.assertEqual(categories[0]["realistic_images"], "")
        self.assertEqual(categories[0]["big_images"], "")

    def test_merge_category_names_keeps_all_sku_categories_in_order(self):
        names = _merge_category_names([3, 2, 3], {2: "二两礼盒", 3: "三两礼盒"}, "三两礼盒")

        self.assertEqual(names, ["三两礼盒", "二两礼盒"])

    def test_product_list_where_supports_product_type_filter(self):
        client = object.__new__(NativeDBClient)

        where_sql, params = client._sku_where(product_type="bag")

        self.assertIn("sp.product_type IN (%s)", where_sql)
        self.assertIn("bag", params)

    def test_product_list_where_supports_multiple_product_types(self):
        client = object.__new__(NativeDBClient)

        where_sql, params = client._sku_where(product_type="bag,bubble_bag")

        self.assertIn("sp.product_type IN (%s,%s)", where_sql)
        self.assertEqual(params, ["bag", "bubble_bag"])

    def test_product_delete_and_shelves_are_spu_level(self):
        source = (ROOT / "src" / "engine" / "native_db.py").read_text(encoding="utf-8")

        self.assertIn("self._product_spu_ids_from_inputs", source)
        self.assertIn("UPDATE product_sku SET status='deleted'", source)
        self.assertIn("WHERE spu_id IN", source)
        self.assertIn("UPDATE product_spu", source)
        self.assertIn("SET deleted_at=%s", source)
        self.assertIn("UPDATE product_sku SET is_listed=%s", source)
        self.assertIn("WHERE spu_id=%s", source)
