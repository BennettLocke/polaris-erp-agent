import unittest
from types import MethodType


class InventoryLedgerQueryTest(unittest.TestCase):
    def test_ledger_filters_sku_warehouse_and_business_group(self):
        from src.engine.native_db import NativeDBClient

        client = object.__new__(NativeDBClient)
        calls = []

        def fake_resolve(self, value):
            return int(value)

        def fake_query(self, sql, params=None):
            calls.append((" ".join(sql.split()), list(params or [])))
            if "COUNT(*) AS total" in sql:
                return [{"total": 2}]
            return [{"id": 1, "spu_id": 8, "biz_no": "TR-DEMO", "counterparty_warehouse_name": "百鑫仓库"}]

        client.resolve_sku_id = MethodType(fake_resolve, client)
        client.query = MethodType(fake_query, client)

        rows, total = client.inventory_ledger(
            sku_id=10,
            warehouse_id=1,
            biz_group="transfer",
            page=2,
            page_size=20,
        )

        self.assertEqual(total, 2)
        self.assertEqual(rows[0]["biz_no"], "TR-DEMO")
        self.assertEqual(len(calls), 2)
        for sql, params in calls:
            self.assertIn("l.sku_id=%s", sql)
            self.assertIn("l.warehouse_id=%s", sql)
            self.assertIn("l.biz_type IN", sql)
            self.assertIn(10, params)
            self.assertIn(1, params)
            self.assertIn("transfer_out", params)
            self.assertIn("transfer_in", params)
        self.assertEqual(calls[1][1][-2:], [20, 20])

    def test_ledger_can_filter_whole_product_without_warehouse(self):
        from src.engine.native_db import NativeDBClient

        client = object.__new__(NativeDBClient)
        calls = []

        def fake_query(self, sql, params=None):
            calls.append((" ".join(sql.split()), list(params or [])))
            if "COUNT(*) AS total" in sql:
                return [{"total": 24}]
            return []

        client.query = MethodType(fake_query, client)

        rows, total = client.inventory_ledger(spu_id=8, page=2, page_size=20)

        self.assertEqual(rows, [])
        self.assertEqual(total, 24)
        for sql, params in calls:
            self.assertIn("sp.id=%s", sql)
            self.assertNotIn("l.warehouse_id=%s", sql)
            self.assertIn(8, params)
        self.assertEqual(calls[1][1][-2:], [20, 20])

    def test_ledger_context_lists_colors_and_all_warehouse_balances(self):
        from src.engine.native_db import NativeDBClient

        client = object.__new__(NativeDBClient)

        def fake_resolve(self, value):
            return int(value)

        def fake_query(self, sql, params=None):
            normalized = " ".join(sql.split())
            if "SELECT sp.id AS spu_id" in normalized:
                return [{"spu_id": 8, "title": "【喜悦】半斤"}]
            if "FROM product_sku s" in normalized and "ORDER BY s.color" in normalized:
                return [
                    {"id": 10, "sku_no": "SJ0010", "color": "红色"},
                    {"id": 11, "sku_no": "SJ0011", "color": "黄色"},
                ]
            if "FROM warehouse w" in normalized:
                return [
                    {"id": 1, "name": "自己店里", "quantity": 6},
                    {"id": 2, "name": "百鑫仓库", "quantity": 19},
                ]
            raise AssertionError(normalized)

        client.resolve_sku_id = MethodType(fake_resolve, client)
        client.query = MethodType(fake_query, client)

        context = client.inventory_ledger_context(sku_id=10)

        self.assertEqual(context["spu_id"], 8)
        self.assertEqual(context["selected_sku_id"], 10)
        self.assertEqual([item["color"] for item in context["skus"]], ["红色", "黄色"])
        self.assertEqual([item["name"] for item in context["warehouses"]], ["自己店里", "百鑫仓库"])
        self.assertEqual(context["total_quantity"], 25)


if __name__ == "__main__":
    unittest.main()
