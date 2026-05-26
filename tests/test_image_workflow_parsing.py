import unittest

from src.core.nodes.image_workflow import parse_ocr_text_list, propagate_batch_customer_context


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


if __name__ == "__main__":
    unittest.main()
