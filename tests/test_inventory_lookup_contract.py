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

    def test_lookup_hides_total_zero_skus_for_dialog_broad_query(self):
        rows = [
            {
                "product_id": 101,
                "sku_no": "SJ1001",
                "title": "【云岭】半斤",
                "color": "红色",
                "warehouse_id": 1,
                "warehouse_name": "自己店里",
                "quantity": "0",
            },
            {
                "product_id": 101,
                "sku_no": "SJ1001",
                "title": "【云岭】半斤",
                "color": "红色",
                "warehouse_id": 2,
                "warehouse_name": "百鑫仓库",
                "quantity": "0",
            },
            {
                "product_id": 102,
                "sku_no": "SJ1002",
                "title": "【喜悦】半斤",
                "color": "红色",
                "warehouse_id": 2,
                "warehouse_name": "百鑫仓库",
                "quantity": "25",
            },
        ]

        result = _inventory_lookup_rows(rows)

        self.assertEqual([item["sku_no"] for item in result["list"]], ["SJ1002"])
        self.assertEqual(result["list"][0]["warehouses"], {"自己店里": 0, "百鑫仓库": 25})

    def test_lookup_can_hide_zero_stock_for_selected_warehouse(self):
        rows = [
            {
                "product_id": 201,
                "sku_no": "SJ2001",
                "title": "【云岭】二三两",
                "color": "红色",
                "warehouse_id": 2,
                "warehouse_name": "百鑫仓库",
                "unit_name": "套",
                "quantity": "0",
            },
            {
                "product_id": 202,
                "sku_no": "SJ2002",
                "title": "【喜悦】二三两",
                "color": "红色",
                "warehouse_id": 2,
                "warehouse_name": "百鑫仓库",
                "unit_name": "套",
                "quantity": "25",
            },
        ]

        result = _inventory_lookup_rows(rows, include_zero=False)

        self.assertEqual(result["warehouses"], [{"id": 2, "name": "百鑫仓库"}])
        self.assertEqual(len(result["list"]), 1)
        self.assertEqual(result["list"][0]["sku_no"], "SJ2002")
        self.assertEqual(result["list"][0]["warehouses"], {"百鑫仓库": 25})

    def test_inventory_lookup_route_hides_zero_only_when_warehouse_selected(self):
        http_source = (
            __import__("pathlib").Path(__file__).resolve().parents[1]
            / "src"
            / "channels"
            / "http_api"
            / "__init__.py"
        ).read_text(encoding="utf-8")

        route_source = http_source.split("def inventory_lookup_api", 1)[1].split("\n\n@app.route", 1)[0]

        self.assertIn("include_zero=warehouse_id is None", route_source)
        self.assertIn("_inventory_lookup_rows", route_source)


if __name__ == "__main__":
    unittest.main()
