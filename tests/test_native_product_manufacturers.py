import unittest
from pathlib import Path

from src.engine.native_db import NativeDBClient


ROOT = Path(__file__).resolve().parents[1]


class ManufacturerQueryClient(NativeDBClient):
    def __new__(cls):
        return object.__new__(cls)

    def __init__(self):
        self.queries: list[tuple[str, list]] = []

    def query(self, sql: str, params=None):
        self.queries.append((" ".join(sql.split()), list(params or [])))
        return [
            {
                "id": 7,
                "name": "鑫创艺",
                "kind": "supplier",
                "contact_name": "张三",
                "phone": "13800138000",
                "address": "",
                "note": "礼盒厂家",
                "status": "active",
                "product_count": 3,
            }
        ]


class NativeProductManufacturersTest(unittest.TestCase):
    def test_product_manufacturers_use_party_suppliers_and_count_bound_spus(self):
        client = ManufacturerQueryClient()

        rows = client.product_manufacturers()

        sql = client.queries[0][0]
        self.assertIn("FROM party p", sql)
        self.assertIn("p.kind IN ('supplier', 'both')", sql)
        self.assertIn("FROM product_spu", sql)
        self.assertIn("default_supplier_id", sql)
        self.assertEqual(rows[0]["id"], 7)
        self.assertEqual(rows[0]["manufacturer_id"], 7)
        self.assertEqual(rows[0]["name"], "鑫创艺")
        self.assertEqual(rows[0]["product_count"], 3)

    def test_product_options_exposes_active_manufacturer_list(self):
        client = object.__new__(NativeDBClient)
        client.product_categories = lambda: []
        client.product_media_assets = lambda **_kwargs: []
        client.product_manufacturers = lambda **kwargs: [
            {"id": 7, "name": "鑫创艺", "status": "active", "product_count": 3, "active_only": kwargs.get("active_only")}
        ]
        client.query = lambda *_args, **_kwargs: []

        options = client.product_options()

        self.assertIn("manufacturer_list", options)
        self.assertEqual(options["manufacturer_list"][0]["id"], 7)
        self.assertTrue(options["manufacturer_list"][0]["active_only"])

    def test_save_product_accepts_default_supplier_id_for_spu(self):
        source = (ROOT / "src" / "engine" / "native_db.py").read_text(encoding="utf-8")
        save_source = source.split("def save_product", 1)[1].split("def update_purchase_policy_by_series", 1)[0]

        self.assertIn("default_supplier_id", save_source)
        self.assertIn('payload.get("default_supplier_id"', save_source)
        self.assertIn("product_spu", save_source)
        self.assertIn("supplier_requested", save_source)
        self.assertIn("CASE WHEN %s THEN %s ELSE default_supplier_id END", save_source)


if __name__ == "__main__":
    unittest.main()
