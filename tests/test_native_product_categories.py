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


class CategorySaveCursor:
    def __init__(self):
        self.statements: list[tuple[str, list]] = []
        self.rows: list[dict] = []

    def execute(self, sql: str, params=None):
        clean_sql = " ".join(sql.split())
        clean_params = list(params or [])
        self.statements.append((clean_sql, clean_params))
        if "SELECT id FROM product_category WHERE name=%s" in clean_sql:
            self.rows = []
        elif "SELECT COALESCE(MAX(id), 0) + 1 AS next_id FROM product_category" in clean_sql:
            self.rows = [{"next_id": 31}]
        else:
            self.rows = []
        return 1

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return list(self.rows)


class CategorySaveTransaction:
    def __init__(self, cursor: CategorySaveCursor):
        self.cursor = cursor

    def __enter__(self):
        return self.cursor

    def __exit__(self, exc_type, exc, tb):
        return False


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

    def test_fixed_packaging_categories_are_non_stock(self):
        client = object.__new__(NativeDBClient)

        self.assertFalse(client._sku_tracks_inventory({
            "is_stock_item": 1,
            "inventory_policy": "",
            "product_category_text": "PVC礼盒",
        }))
        self.assertFalse(client._sku_tracks_inventory({
            "is_stock_item": 1,
            "inventory_policy": "",
            "product_category_text": "快递纸箱",
        }))
        self.assertTrue(client._sku_tracks_inventory({
            "is_stock_item": 1,
            "inventory_policy": "strict",
            "product_category_text": "PVC礼盒",
        }))

    def test_inventory_rule_defaults_include_fixed_packaging_categories(self):
        client = object.__new__(NativeDBClient)

        rules = client._default_system_setting("inventory_rules")

        self.assertIn("PVC礼盒", rules["non_stock_category_keywords"])
        self.assertIn("快递纸箱", rules["non_stock_category_keywords"])
        self.assertNotIn("纸箱", rules["stock_category_keywords"])

    def test_save_product_category_creates_category_and_syncs_inventory_policy(self):
        client = object.__new__(NativeDBClient)
        cursor = CategorySaveCursor()
        client.transaction = lambda: CategorySaveTransaction(cursor)
        client._table_exists = lambda _cursor, table_name: table_name in {"product_category", "product_sku", "product_spu"}

        result = client.save_product_category(
            {"name": "PVC礼盒", "product_type": "other", "inventory_policy": "none"},
            operator_user_id=7,
        )

        self.assertEqual(result["code"], 0)
        self.assertEqual(result["data"]["category"]["name"], "PVC礼盒")
        self.assertEqual(result["data"]["category"]["inventory_policy"], "none")
        sql_text = "\n".join(statement for statement, _params in cursor.statements)
        self.assertIn("INSERT INTO product_category", sql_text)
        self.assertIn("UPDATE product_sku", sql_text)
        self.assertIn("inventory_policy='none'", sql_text)

    def test_inventory_keyword_rules_update_matching_category_policies(self):
        client = object.__new__(NativeDBClient)
        cursor = CategorySaveCursor()
        client._table_exists = lambda _cursor, table_name: table_name == "product_category"

        client._apply_inventory_rule_keywords_to_categories(
            cursor,
            {"stock_category_keywords": ["礼盒"], "non_stock_category_keywords": ["PVC"]},
        )

        sql_text = "\n".join(statement for statement, _params in cursor.statements)
        self.assertIn("UPDATE product_category", sql_text)
        self.assertIn("inventory_policy='strict'", sql_text)
        self.assertIn("inventory_policy='none'", sql_text)

    def test_product_delete_and_shelves_are_spu_level(self):
        source = (ROOT / "src" / "engine" / "native_db.py").read_text(encoding="utf-8")

        self.assertIn("self._product_spu_ids_from_inputs", source)
        self.assertIn("UPDATE product_sku SET status='deleted'", source)
        self.assertIn("WHERE spu_id IN", source)
        self.assertIn("UPDATE product_spu", source)
        self.assertIn("SET deleted_at=%s", source)
        self.assertIn("UPDATE product_sku SET is_listed=%s", source)
        self.assertIn("WHERE spu_id=%s", source)
