import unittest
from unittest.mock import patch

from scripts.common.unit_converter import calculate_order_quantity, parse_unit_from_simple_desc
from src.core.nodes.image_workflow import _process_ocr_order, find_case_pack_by_goods_name, parse_per_piece


class WorkflowCasePackQuantityTest(unittest.TestCase):
    def test_one_piece_case_pack_text_converts_to_set_quantity(self):
        simple_desc = "\u0031\u4ef6\u0032\u0038\u5957"

        self.assertEqual(parse_unit_from_simple_desc(simple_desc), 28)
        self.assertEqual(parse_per_piece(simple_desc), 28)
        self.assertEqual(calculate_order_quantity("\u0031\u4ef6", 1, simple_desc), 28)

    def test_set_quantity_is_not_converted_as_piece_quantity(self):
        simple_desc = "\u0031\u4ef6\u0032\u0038\u5957"

        self.assertEqual(calculate_order_quantity("\u0032\u0030\u5957", 20, simple_desc), 20)

    @patch("src.core.nodes.image_workflow.upload_to_oss", return_value="")
    @patch("src.core.nodes.image_workflow.repair_ocr_parsed_fields", side_effect=lambda parsed, caller: parsed)
    @patch("src.core.nodes.image_workflow.find_case_pack_by_goods_name", return_value={"id": 139, "simple_desc": "\u0031\u4ef6\u0032\u0038\u5957"})
    @patch("src.core.nodes.image_workflow.find_product_by_goods_name", return_value=None)
    def test_mismatched_color_still_uses_goods_case_pack_for_workflow_quantity(
        self,
        _find_product,
        _case_pack,
        _repair,
        _upload,
    ):
        item = _process_ocr_order(
            ["\u5ba2\u6237\uff1a\u9738\u679e\n\u5ca9\u54733\u5c0f\u76d2\u7ea2\u82721\u4ef6 \u63d0\u888b\u4e1d\u5370"],
            "ignored.png",
            caller=object(),
        )

        self.assertEqual(item["workflow_order_payload"]["quantity"], 28)
        self.assertEqual(item["parsed"]["unit"], "\u5957")
        self.assertEqual(item["parsed"]["per_piece"], 28)

    @patch("src.core.nodes.image_workflow.upload_to_oss", return_value="")
    @patch("src.core.nodes.image_workflow.repair_ocr_parsed_fields", side_effect=lambda parsed, caller: parsed)
    @patch("src.core.nodes.image_workflow.find_product_by_goods_name", return_value={"id": 139, "simple_desc": "\u0031\u4ef6\u0032\u0038\u5957"})
    def test_workflow_keeps_set_quantity_without_case_pack_conversion(
        self,
        _find_product,
        _repair,
        _upload,
    ):
        item = _process_ocr_order(
            ["\u5ba2\u6237\uff1a\u9738\u679e\n\u5ca9\u54733\u5c0f\u76d2\u9ed1\u8272\u0032\u0030\u5957 \u63d0\u888b\u4e1d\u5370"],
            "ignored.png",
            caller=object(),
        )

        self.assertEqual(item["workflow_order_payload"]["quantity"], 20)
        self.assertEqual(item["parsed"]["unit"], "\u5957")
        self.assertNotIn("per_piece", item["parsed"])

    @patch("src.core.nodes.image_workflow.upload_to_oss", return_value="")
    @patch("src.core.nodes.image_workflow.repair_ocr_parsed_fields", side_effect=lambda parsed, caller: parsed)
    @patch("src.core.nodes.image_workflow.find_product_by_goods_name", return_value={"id": 139, "simple_desc": "\u0031\u4ef6\u0036\u0030\u5957"})
    def test_chinese_piece_quantity_converts_to_case_pack_quantity(
        self,
        _find_product,
        _repair,
        _upload,
    ):
        item = _process_ocr_order(
            ["\u8336\u793c\u534a\u65a4\u4e00\u4ef6 \u9ec4\u8272"],
            "ignored.png",
            caller=object(),
        )

        self.assertEqual(item["workflow_order_payload"]["goods_name"], "\u8336\u793c\u534a\u65a4")
        self.assertEqual(item["workflow_order_payload"]["quantity"], 60)
        self.assertEqual(item["parsed"]["unit"], "\u5957")
        self.assertEqual(item["parsed"]["per_piece"], 60)

    def test_case_pack_lookup_accepts_same_goods_with_multiple_colors(self):
        class FakeCaller:
            def call(self, tool_name, **kwargs):
                return [
                    {"title": "\u3010\u5ca9\u5473\u3011\u4e09\u5c0f\u76d2", "color": "\u9ed1\u8272", "simple_desc": "\u0031\u4ef6\u0032\u0038\u5957"},
                    {"title": "\u3010\u5ca9\u5473\u3011\u4e09\u5c0f\u76d2", "color": "\u53e4\u94dc\u8272", "simple_desc": "\u0031\u4ef6\u0032\u0038\u5957"},
                ]

        info = find_case_pack_by_goods_name("\u5ca9\u54733\u5c0f\u76d2", FakeCaller())

        self.assertIsNotNone(info)
        self.assertEqual(parse_per_piece(info["simple_desc"]), 28)


if __name__ == "__main__":
    unittest.main()
