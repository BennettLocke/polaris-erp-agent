import unittest

from src.channels.http_api import _inventory_lookup_rows


class InventoryLookupContractTest(unittest.TestCase):
    def test_lookup_groups_sku_by_warehouse_and_keeps_zero_stock(self):
        rows = [
            {
                "product_id": 101,
                "spu_id": 10,
                "sku_no": "SJ1001",
                "title": "【云岭】二三两",
                "color": "红色",
                "warehouse_id": 1,
                "warehouse_name": "自己店里",
                "unit_name": "套",
                "quantity": "0",
                "simple_desc": "1件60套",
                "is_stock_item": 1,
            },
            {
                "product_id": 101,
                "spu_id": 10,
                "sku_no": "SJ1001",
                "title": "【云岭】二三两",
                "color": "红色",
                "warehouse_id": 2,
                "warehouse_name": "百鑫仓库",
                "unit_name": "套",
                "quantity": "12",
                "simple_desc": "1件60套",
                "is_stock_item": 1,
            },
        ]

        result = _inventory_lookup_rows(rows)

        self.assertEqual(
            result["warehouses"],
            [
                {"id": 1, "name": "自己店里"},
                {"id": 2, "name": "百鑫仓库"},
            ],
        )
        self.assertEqual(len(result["list"]), 1)
        row = result["list"][0]
        self.assertEqual(row["sku_no"], "SJ1001")
        self.assertEqual(row["color"], "红色")
        self.assertEqual(row["warehouses"], {"自己店里": 0, "百鑫仓库": 12})
        self.assertEqual(row["total_stock"], 12)


if __name__ == "__main__":
    unittest.main()
