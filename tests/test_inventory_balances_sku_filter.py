import unittest
from types import MethodType


class InventoryBalancesSkuFilterTest(unittest.TestCase):
    def test_sku_id_filter_is_applied_before_pagination(self):
        from src.engine.native_db import NativeDBClient

        client = NativeDBClient()
        original_sync = client._sync_inventory_policy_categories
        original_resolve = client.resolve_sku_id
        original_query = client.query
        calls = []
        resolved_inputs = []

        def fake_sync(self):
            return None

        def fake_resolve(self, product_id):
            resolved_inputs.append(product_id)
            return 1234

        def fake_query(self, sql, params=None):
            calls.append((sql, list(params or [])))
            if "COUNT(*) AS total" in sql:
                return [{"total": 1}]
            return [
                {
                    "product_id": 1234,
                    "spu_id": 44,
                    "sku_no": "SJ1234",
                    "is_stock_item": 1,
                    "title": "岩彩 三两",
                    "color": "卡其色",
                    "case_pack_qty": 20,
                    "warehouse_id": 1,
                    "warehouse_name": "自己店里",
                    "unit_id": 1,
                    "unit_name": "套",
                    "quantity": 8,
                    "available_qty": 8,
                    "reserved_qty": 0,
                }
            ]

        try:
            client._sync_inventory_policy_categories = MethodType(fake_sync, client)
            client.resolve_sku_id = MethodType(fake_resolve, client)
            client.query = MethodType(fake_query, client)

            rows, total = client.inventory_balances(sku_id=9800, warehouse_id=1, page=1, page_size=20)
        finally:
            client._sync_inventory_policy_categories = original_sync
            client.resolve_sku_id = original_resolve
            client.query = original_query

        self.assertEqual(total, 1)
        self.assertEqual(rows[0]["product_id"], 1234)
        self.assertEqual(resolved_inputs, [9800])
        self.assertTrue(calls)
        for sql, params in calls:
            self.assertIn("s.id=%s", sql)
            self.assertIn(1234, params)
        self.assertEqual(calls[0][1].count(1234), 1)


if __name__ == "__main__":
    unittest.main()
