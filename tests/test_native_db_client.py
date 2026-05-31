"""Native database client smoke tests."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.engine.exceptions import DBError
from src.engine.native_db import NativeDBClient, _clean_number_sequence_note, get_native_db_client


class NativeDBClientSmokeTest(unittest.TestCase):
    def test_native_db_client_init(self):
        client = get_native_db_client()
        self.assertEqual(client.db_config.get("name"), "sjagent_core")

    def test_number_sequence_note_repairs_unrecoverable_question_marks(self):
        self.assertEqual(
            _clean_number_sequence_note("??????? SJ1570 ??????"),
            "礼盒和泡袋统一从 SJ1570 往后自动编号",
        )
        self.assertEqual(
            _clean_number_sequence_note("礼盒和泡袋统一从 SJ1570 往后自动编号"),
            "礼盒和泡袋统一从 SJ1570 往后自动编号",
        )

    def test_sales_sku_lookup_allows_unlisted_sku_when_required(self):
        class FakeCursor:
            def __init__(self):
                self.sql = ""
                self.params = ()

            def execute(self, sql, params=()):
                self.sql = sql
                self.params = params

            def fetchone(self):
                return {
                    "id": 88,
                    "sku_no": "SJ0088",
                    "title": "下架礼盒",
                    "status": "active",
                    "is_sellable": 1,
                    "is_listed": 0,
                }

        client = object.__new__(NativeDBClient)

        sku = client._get_sku_for_update(FakeCursor(), 88, require_sellable=True)

        self.assertEqual(sku["id"], 88)
        self.assertEqual(sku["is_listed"], 0)

    def test_sales_sku_lookup_rejects_unsellable_sku_when_required(self):
        class FakeCursor:
            def execute(self, sql, params=()):
                pass

            def fetchone(self):
                return {
                    "id": 89,
                    "sku_no": "SJ0089",
                    "title": "不可售礼盒",
                    "status": "active",
                    "is_sellable": 0,
                    "is_listed": 1,
                }

        client = object.__new__(NativeDBClient)

        with self.assertRaisesRegex(DBError, "不可售"):
            client._get_sku_for_update(FakeCursor(), 89, require_sellable=True)

    def test_sales_sellable_guard_is_only_applied_to_sales_order_creation(self):
        source = (Path(__file__).parent.parent / "src" / "engine" / "native_db.py").read_text(encoding="utf-8")
        stock_in_source = source.split("def create_stock_in", 1)[1].split("def create_transfer", 1)[0]
        sales_source = source.split("def create_sales_order", 1)[1].split("def delete_sales_order", 1)[0]

        self.assertNotIn("require_sellable=True", stock_in_source)
        self.assertIn("_get_sku_for_update(cursor, sku_id, require_sellable=True)", sales_source)

    def test_workflow_sales_link_updates_both_tables_and_writes_log(self):
        source = (Path(__file__).parent.parent / "src" / "engine" / "native_db.py").read_text(encoding="utf-8")
        link_source = source.split("def link_workflow_sales_order", 1)[1].split("def create_sales_order", 1)[0]

        self.assertIn("UPDATE workflow_order", link_source)
        self.assertIn("sales_order_id=%s", link_source)
        self.assertIn("UPDATE sales_order", link_source)
        self.assertIn("source_workflow_id=%s", link_source)
        self.assertIn("INSERT INTO workflow_order_log", link_source)
        self.assertIn("'link_sales'", link_source)

    def test_delete_pending_product_media_only_scopes_unbound_pending_assets(self):
        client = object.__new__(NativeDBClient)
        calls = []

        def fake_execute(sql, params=()):
            calls.append((sql, params))
            return 2

        client.execute = fake_execute

        result = client.delete_pending_product_media([1, "2", "x", 2, 0])

        self.assertEqual(result["code"], 0)
        self.assertEqual(result["data"]["ids"], [1, 2])
        self.assertEqual(result["data"]["affected"], 2)
        sql = " ".join(calls[0][0].split())
        self.assertIn("media_type='pending'", sql)
        self.assertIn("sku_id IS NULL", sql)
        self.assertIn("spu_id IS NULL", sql)
        self.assertIn("is_active=1", sql)

    def test_wechat_login_existing_identity_uses_saved_phone_to_link_customer(self):
        class FakeCursor:
            def __init__(self):
                self.calls = []

            def execute(self, sql, params=()):
                self.calls.append((sql, params))

            def fetchone(self):
                return {
                    "id": 9,
                    "phone": "13800138000",
                    "linked_party_id": None,
                    "role": "customer",
                    "is_admin": 0,
                }

        class FakeTransaction:
            def __init__(self, cursor):
                self.cursor = cursor

            def __enter__(self):
                return self.cursor

            def __exit__(self, exc_type, exc, tb):
                return False

        client = object.__new__(NativeDBClient)
        cursor = FakeCursor()
        linked_calls = []
        upserts = []
        client.transaction = lambda: FakeTransaction(cursor)
        client._identity_link_customer_if_allowed = lambda cursor, user, phone: (
            linked_calls.append({"user_id": user["id"], "phone": phone}) or (55, "linked_customer", False)
        )
        client._identity_upsert = lambda cursor, **kwargs: upserts.append(kwargs)

        result = client.identity_link_wechat(openid="wx-openid", profile={})

        self.assertEqual(result["code"], 0)
        self.assertEqual(result["data"]["customer_id"], 55)
        self.assertEqual(result["data"]["bind_status"], "linked_customer")
        self.assertEqual(linked_calls, [{"user_id": 9, "phone": "13800138000"}])
        self.assertIn({"user_id": 9, "provider": "phone", "external_id": "13800138000"}, upserts)

    def test_wechat_login_saved_phone_conflict_still_requires_review(self):
        class FakeCursor:
            def execute(self, sql, params=()):
                pass

            def fetchone(self):
                return {
                    "id": 9,
                    "phone": "13800138000",
                    "linked_party_id": None,
                    "role": "customer",
                    "is_admin": 0,
                }

        class FakeTransaction:
            def __enter__(self):
                return FakeCursor()

            def __exit__(self, exc_type, exc, tb):
                return False

        client = object.__new__(NativeDBClient)
        client.transaction = lambda: FakeTransaction()
        client._identity_link_customer_if_allowed = lambda cursor, user, phone: (
            None,
            "customer_phone_conflict",
            True,
        )
        client._identity_upsert = lambda cursor, **kwargs: None

        result = client.identity_link_wechat(openid="wx-openid", profile={})

        self.assertEqual(result["code"], 0)
        self.assertIsNone(result["data"]["customer_id"])
        self.assertEqual(result["data"]["bind_status"], "customer_phone_conflict")
        self.assertTrue(result["data"]["needs_review"])

    def test_sales_print_html_keeps_original_layout_with_bordered_product_table(self):
        source = (Path(__file__).parent.parent / "src" / "engine" / "native_db.py").read_text(encoding="utf-8")
        print_source = source.split("def sales_print_html", 1)[1].split("def create_sales_print_task", 1)[0]

        self.assertIn('class="print-table"', print_source)
        self.assertIn('class="meta"', print_source)
        self.assertIn('class="doc-no"', print_source)
        self.assertIn('class="summary"', print_source)
        self.assertIn("print-note", print_source)
        self.assertIn('class="footer"', print_source)
        self.assertNotIn('class="info-table"', print_source)
        self.assertNotIn('class="summary-table"', print_source)
        self.assertNotIn('class="note-table"', print_source)
        self.assertIn("border-collapse: collapse", print_source)
        self.assertIn("border: 1px solid #111827", print_source)
        self.assertIn("td small", print_source)
        self.assertIn("print-color-adjust: exact", print_source)

    def test_sales_print_html_keeps_headers_white_and_hides_internal_print_failures(self):
        client = get_native_db_client()
        original_ensure = client._ensure_print_tables
        original_sales_print_data = client.sales_print_data
        client._ensure_print_tables = lambda: None
        client.sales_print_data = lambda sales_id: {
            "code": 0,
            "data": {
                "order": {
                    "sales_no": "SO-DEMO",
                    "customer_name": "测试客户",
                    "created_at": "2026-05-27 15:30:00",
                    "total_quantity": 20,
                    "receivable_amount": 360,
                    "note": "客户自提\n打印失败：PDF 渲染失败",
                    "products": [
                        {"title": "【岩彩】二三两", "spec": "蓝色", "quantity": "20", "price": "18.00", "total_price": "360.00"},
                    ],
                },
                "template": {
                    "paper_size": "A5",
                    "orientation": "landscape",
                    "font_size": 12,
                    "show_payment": 0,
                    "show_operator": 0,
                    "show_customer_phone": 0,
                    "show_note": 1,
                    "header_text": "肆计包装·设计销售单",
                    "footer_text": "",
                },
            },
        }
        try:
            html = client.sales_print_html(1, auto_print=False)
        finally:
            client._ensure_print_tables = original_ensure
            client.sales_print_data = original_sales_print_data

        self.assertIn("客户自提", html)
        self.assertNotIn("PDF 渲染失败", html)
        self.assertNotIn("打印失败", html)
        self.assertNotIn("background: #f3f4f6", html)
        self.assertNotIn('class="info-table"', html)
        self.assertNotIn('class="summary-table"', html)
        self.assertNotIn('class="note-table"', html)
        self.assertIn('class="meta"', html)
        self.assertIn('class="summary"', html)
        self.assertIn('class="print-note"', html)

    def test_sales_print_html_can_hide_preview_action_bar(self):
        client = get_native_db_client()
        original_ensure = client._ensure_print_tables
        original_sales_print_data = client.sales_print_data
        client._ensure_print_tables = lambda: None
        client.sales_print_data = lambda sales_id: {
            "code": 0,
            "data": {
                "order": {
                    "sales_no": "SO-DEMO",
                    "customer_name": "测试客户",
                    "created_at": "2026-05-27 15:30:00",
                    "total_quantity": 1,
                    "receivable_amount": 1,
                    "products": [
                        {"title": "测试商品", "spec": "蓝色", "quantity": "1", "price": "1.00", "total_price": "1.00"},
                    ],
                },
                "template": {
                    "paper_size": "A5",
                    "orientation": "landscape",
                    "font_size": 12,
                    "show_note": 0,
                    "header_text": "肆计包装·设计销售单",
                },
            },
        }
        try:
            html = client.sales_print_html(1, auto_print=False, show_actions=False)
        finally:
            client._ensure_print_tables = original_ensure
            client.sales_print_data = original_sales_print_data

        self.assertNotIn('class="print-actions"', html)
        self.assertNotIn('onclick="window.print()"', html)

    def test_sales_print_html_keeps_inner_print_padding_to_avoid_edge_clipping(self):
        client = get_native_db_client()
        original_ensure = client._ensure_print_tables
        original_sales_print_data = client.sales_print_data
        client._ensure_print_tables = lambda: None
        client.sales_print_data = lambda sales_id: {
            "code": 0,
            "data": {
                "order": {
                    "sales_no": "SO-DEMO",
                    "customer_name": "测试客户",
                    "created_at": "2026-05-27 15:30:00",
                    "total_quantity": 1,
                    "receivable_amount": 1,
                    "products": [
                        {"title": "测试商品", "spec": "蓝色", "quantity": "1", "price": "1.00", "total_price": "1.00"},
                    ],
                },
                "template": {
                    "paper_size": "A5",
                    "orientation": "landscape",
                    "font_size": 12,
                    "show_note": 0,
                    "header_text": "肆计包装·设计销售单",
                },
            },
        }
        try:
            html = client.sales_print_html(1, auto_print=False, show_actions=False)
        finally:
            client._ensure_print_tables = original_ensure
            client.sales_print_data = original_sales_print_data

        self.assertIn("@page { size: A5 landscape; margin: 6mm; }", html)
        self.assertIn(".sheet:not(.thermal) { width: auto; margin: 0; padding: 6mm 8mm;", html)
        self.assertNotIn(".sheet { width: auto; margin: 0; padding: 0;", html)


if __name__ == "__main__":
    unittest.main()
