"""Native database client smoke tests."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.engine.native_db import _clean_number_sequence_note, get_native_db_client


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


if __name__ == "__main__":
    unittest.main()
