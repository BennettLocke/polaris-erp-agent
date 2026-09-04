import sys
import unittest
from contextlib import contextmanager
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent))

from src.engine.native_db import NativeDBClient


class PriceContextDB(NativeDBClient):
    def __init__(self):
        self.ensured = True
        self.queries = []
        self.__class__._sales_price_columns_ready = True

    def _ensure_sales_price_columns(self):
        self.ensured = True

    @contextmanager
    def cursor(self):
        yield self

    def execute(self, sql, params=()):
        self.last_cursor_sql = sql

    def fetchone(self):
        return {"exists": 1}

    def resolve_sku_id(self, product_id, cursor=None):
        return int(product_id)

    def query(self, sql, params=()):
        self.queries.append((sql, params))
        if "FROM product_sku s" in sql:
            return [{
                "id": 10,
                "spu_id": 91,
                "sku_no": "SJ1047",
                "title": "【喜悦】半斤",
                "color": "红色",
                "unit_id": 1,
                "unit_name": "套",
                "category_id": 7,
                "category_name": "半斤礼盒",
                "product_type": "gift_box",
                "retail_price": "22.00",
                "min_price": "22.00",
                "max_price": "22.00",
            }]
        if "FROM customer_price_memory m" in sql:
            return [{
                "memory_id": 701,
                "item_id": 501,
                "sales_no": "SO202609010001",
                "unit_price": "21.00",
                "quantity": "20.000",
                "unit_id": 1,
                "unit_name": "套",
                "sales_at": "2026-09-01 10:00:00",
                "age_days": 3,
                "remember_price": 1,
                "price_source": "manual_override",
                "source_sales_status": "deleted",
                "source_sales_deleted_at": "2026-09-02 10:00:00",
            }]
        return []


class NativeCustomerPriceContextTest(unittest.TestCase):
    def test_returns_sku_and_auditable_history_rows(self):
        PriceContextDB._instance = None
        db = PriceContextDB()

        result = db.sales_price_context(8, 10, limit=5)

        self.assertTrue(db.ensured)
        self.assertEqual(result["sku"]["category_name"], "半斤礼盒")
        self.assertEqual(result["history"][0]["sales_no"], "SO202609010001")
        self.assertEqual(result["history"][0]["memory_id"], 701)
        self.assertEqual(result["history"][0]["source_sales_status"], "deleted")
        history_sql = next(sql for sql, _ in db.queries if "FROM customer_price_memory m" in sql)
        self.assertIn("m.spu_id=%s", history_sql)
        self.assertIn("m.unit_id=%s", history_sql)
        self.assertIn("m.deleted_at IS NULL", history_sql)
        history_params = next(params for sql, params in db.queries if "FROM customer_price_memory m" in sql)
        self.assertEqual(history_params[:3], (8, 91, 1))

    def test_memory_is_upserted_on_sale_and_not_removed_with_deleted_order(self):
        source = (Path(__file__).parent.parent / "src" / "engine" / "native_db.py").read_text(encoding="utf-8")
        create_section = source.split("def create_sales_order", 1)[1].split("def update_sales_payment", 1)[0]
        delete_section = source.split("def delete_sales_order", 1)[1].split("def cancel_sales_order", 1)[0]

        self.assertIn("INSERT INTO customer_price_memory", create_section)
        self.assertIn("ON DUPLICATE KEY UPDATE", create_section)
        self.assertNotIn("customer_price_memory", delete_section)

        ensure_section = source.split("def _ensure_sales_price_columns", 1)[1].split("def _ensure_party_columns", 1)[0]
        self.assertIn("s.status IN ('confirmed', 'completed', 'deleted')", ensure_section)
        self.assertNotIn("i.remember_price=1", ensure_section)
        self.assertIn("s.status IN ('confirmed', 'completed', 'deleted')", source)


if __name__ == "__main__":
    unittest.main()
