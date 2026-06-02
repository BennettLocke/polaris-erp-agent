import unittest

from src.core.nodes.image_workflow import parse_ocr_text_list, propagate_batch_customer_context
from src.channels.http_api.__init__ import _sanitize_pending_state
from src.skills.workflow_order.workflow import WorkflowOrderWorkflow


class FakeWorkflowCaller:
    def __init__(self):
        self.calls = []

    def call(self, name, **kwargs):
        self.calls.append((name, kwargs))
        return {"code": 0, "data": {"id": len(self.calls)}}


class ImageWorkflowParsingTest(unittest.TestCase):
    def test_short_product_line_without_spec_keeps_product_name(self):
        parsed = parse_ocr_text_list(["七彩黑色20个"])

        self.assertEqual(parsed["goods_name"], "七彩")
        self.assertEqual(parsed["color"], "黑色")
        self.assertEqual(parsed["quantity"], 20)
        self.assertEqual(parsed["unit"], "个")

    def test_craft_words_do_not_pollute_goods_name(self):
        parsed = parse_ocr_text_list(["岩味3小盒红色1件 提袋丝印"])

        self.assertEqual(parsed["goods_name"], "岩味3小盒")
        self.assertEqual(parsed["color"], "红色")
        self.assertEqual(parsed["quantity"], 1)
        self.assertEqual(parsed["unit"], "件")
        self.assertIn("提袋", parsed["craft"])
        self.assertIn("丝印", parsed["craft"])

    def test_gu_tong_jin_is_treated_as_color(self):
        parsed = parse_ocr_text_list(["岩味3小盒古铜金1件 提袋丝印"])

        self.assertEqual(parsed["goods_name"], "岩味3小盒")
        self.assertEqual(parsed["color"], "古铜色")
        self.assertEqual(parsed["quantity"], 1)
        self.assertEqual(parsed["unit"], "件")

    def test_chinese_piece_quantity_is_removed_from_goods_name(self):
        parsed = parse_ocr_text_list(["茶礼半斤一件 黄色"])

        self.assertEqual(parsed["goods_name"], "茶礼半斤")
        self.assertEqual(parsed["color"], "黄色")
        self.assertEqual(parsed["quantity"], 1)
        self.assertEqual(parsed["unit"], "件")

    def test_batch_customer_context_only_repairs_missing_items(self):
        items = [
            {
                "parsed": {"customer_name": "霸枞", "goods_name": "岩味3小盒", "customer_missing": False},
                "workflow_order_payload": {"customer": "霸枞", "goods_name": "岩味3小盒"},
            },
            {
                "parsed": {"customer_name": "散客", "goods_name": "岩味3小盒古铜金", "customer_missing": True},
                "workflow_order_payload": {"customer": "散客", "goods_name": "岩味3小盒古铜金"},
            },
        ]

        propagate_batch_customer_context(items)

        self.assertEqual(items[1]["parsed"]["customer_name"], "霸枞")
        self.assertEqual(items[1]["workflow_order_payload"]["customer"], "霸枞")

    def test_image_workflow_pending_state_drops_empty_rows(self):
        cleaned = _sanitize_pending_state(
            "workflow",
            {
                "pending_action": "confirm_image_workflow_orders",
                "parsed_list": [
                    {"customer": "", "goods_name": "", "quantity": 1},
                    {"customer": "齐唯茶业", "goods_name": "岩味3小盒", "quantity": 2},
                ],
            },
            None,
        )

        self.assertEqual(len(cleaned["parsed_list"]), 1)
        self.assertEqual(cleaned["parsed_list"][0]["customer"], "齐唯茶业")
        self.assertEqual(cleaned["parsed_list"][0]["goods_name"], "岩味3小盒")

    def test_workflow_create_many_skips_rows_without_goods_name(self):
        workflow = WorkflowOrderWorkflow()
        fake_caller = FakeWorkflowCaller()
        workflow.caller = fake_caller

        workflow._create_many([
            {"customer": "散客", "goods_name": "", "quantity": 1},
            {"customer": "齐唯茶业", "goods_name": "岩味3小盒", "quantity": 2},
        ])

        self.assertEqual(len(fake_caller.calls), 1)
        self.assertEqual(fake_caller.calls[0][1]["goods_name"], "岩味3小盒")


if __name__ == "__main__":
    unittest.main()
