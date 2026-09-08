from pathlib import Path
import unittest
from unittest.mock import Mock

from src.engine.exceptions import DBError
from src.engine.native_db import NativeDBClient
from src.services.business.sales import SalesService


ROOT = Path(__file__).resolve().parents[1]


class SalesMergePreviewContractTest(unittest.TestCase):
    @staticmethod
    def merge_client(*, status="confirmed", total=2):
        client = object.__new__(NativeDBClient)

        base_order = {
            "id": 10,
            "customer_id": 3,
            "customer_name_snapshot": "齐唯茶业",
            "status": status,
            "sales_at": "2026-09-07 10:00:00",
            "phone": "13800138000",
            "address": "测试地址",
        }
        orders = [
            {
                "id": 9,
                "sales_no": "SO0009",
                "customer_id": 3,
                "customer_name_snapshot": "齐唯茶业",
                "status": "confirmed",
                "pay_status": "monthly",
                "pay_type": "monthly",
                "total_quantity": 2,
                "goods_amount": 40,
                "discount_amount": 0,
                "receivable_amount": 40,
                "sales_at": "2026-09-05 09:00:00",
                "note": "先送一部分",
            },
            {
                "id": 10,
                "sales_no": "SO0010",
                "customer_id": 3,
                "customer_name_snapshot": "齐唯茶业",
                "status": "confirmed",
                "pay_status": "monthly",
                "pay_type": "monthly",
                "total_quantity": 4,
                "goods_amount": 80,
                "discount_amount": 0,
                "receivable_amount": 80,
                "sales_at": "2026-09-07 10:00:00",
                "note": "",
            },
        ]
        items = [
            {
                "id": 101,
                "sales_order_id": 10,
                "line_no": 1,
                "title_snapshot": "【喜悦】半斤",
                "color_snapshot": "红色",
                "quantity": 2,
                "unit_price": 20,
                "amount": 40,
            },
            {
                "id": 102,
                "sales_order_id": 10,
                "line_no": 2,
                "title_snapshot": "【喜悦】半斤",
                "color_snapshot": "红色",
                "quantity": 2,
                "unit_price": 20,
                "amount": 40,
            },
            {
                "id": 91,
                "sales_order_id": 9,
                "line_no": 1,
                "title_snapshot": "【喜悦】三小盒",
                "color_snapshot": "蓝色",
                "quantity": 2,
                "unit_price": 20,
                "amount": 40,
            },
        ]

        def fake_query(sql, params=()):
            normalized = " ".join(sql.split())
            if "FROM sales_order s" in normalized and "WHERE s.id=%s" in normalized:
                return [base_order]
            if "COUNT(*) AS total" in normalized and "FROM sales_order s" in normalized:
                return [{"total": total}]
            if "FROM sales_order s" in normalized and "ORDER BY s.sales_at ASC" in normalized:
                return orders
            if "FROM sales_order_item i" in normalized:
                return items
            raise AssertionError(f"unexpected query: {normalized}")

        client.query = fake_query
        return client

    def test_sales_service_delegates_merge_candidates(self):
        db = Mock()
        db.sales_merge_candidates.return_value = {"code": 0, "data": {"orders": []}}

        result = SalesService(db).merge_candidates(12)

        self.assertEqual(result, {"code": 0, "data": {"orders": []}})
        db.sales_merge_candidates.assert_called_once_with(12)

    def test_merge_candidate_route_is_read_only(self):
        source = (ROOT / "src" / "channels" / "http_api" / "__init__.py").read_text(encoding="utf-8")

        self.assertIn(
            '@app.route("/api/sales/<int:sales_id>/merge-candidates", methods=["GET"])',
            source,
        )
        self.assertNotIn(
            '@app.route("/api/sales/<int:sales_id>/merge-candidates", methods=["POST"])',
            source,
        )

    def test_merge_candidate_route_requires_print_permission(self):
        source = (ROOT / "src" / "channels" / "http_api" / "__init__.py").read_text(encoding="utf-8")

        self.assertIn(
            '({"GET"}, re.compile(r"^/api/sales/\\d+/merge-candidates$"), "打印")',
            source,
        )

    def test_merge_candidates_uses_base_customer_and_seven_day_window(self):
        data = self.merge_client().sales_merge_candidates(10)["data"]

        self.assertEqual(data["base_sales_id"], 10)
        self.assertEqual(data["customer"]["id"], 3)
        self.assertEqual(data["date_from"], "2026-09-01")
        self.assertEqual(data["date_to"], "2026-09-07")
        self.assertEqual([row["id"] for row in data["orders"]], [9, 10])

    def test_merge_candidates_preserves_duplicate_product_lines(self):
        orders = self.merge_client().sales_merge_candidates(10)["data"]["orders"]
        base_items = next(row["items"] for row in orders if row["id"] == 10)

        self.assertEqual(len(base_items), 2)
        self.assertEqual(base_items[0]["title"], base_items[1]["title"])
        self.assertEqual(base_items[0]["color"], base_items[1]["color"])

    def test_merge_candidates_rejects_deleted_base_order(self):
        with self.assertRaisesRegex(DBError, "已删除或已取消"):
            self.merge_client(status="deleted").sales_merge_candidates(10)

    def test_merge_candidates_rejects_more_than_two_hundred_orders(self):
        with self.assertRaisesRegex(DBError, "超过200张"):
            self.merge_client(total=201).sales_merge_candidates(10)


if __name__ == "__main__":
    unittest.main()
