import threading
import time
import unittest
from unittest.mock import ANY, MagicMock, call, patch

import numpy as np

from src.core.nodes.image_workflow import (
    _process_ocr_order,
    _normalize_goods_keyword,
    parse_ocr_text_list,
    process_image_batch,
    process_single_image,
    propagate_batch_customer_context,
    propagate_batch_goods_context,
)
from scripts.image_processor import Frame
from src.channels.http_api.__init__ import _sanitize_pending_state
from src.skills.workflow_order.workflow import WorkflowOrderWorkflow


class FakeWorkflowCaller:
    def __init__(self):
        self.calls = []

    def call(self, name, **kwargs):
        self.calls.append((name, kwargs))
        return {"code": 0, "data": {"id": len(self.calls)}}


class FakeGoodsContextCaller:
    def __init__(self):
        self.products = [
            {"id": 1086, "title": "【艺】三两", "spec": "橙色", "simple_desc": "1件24套", "price": "25.00"},
            {"id": 1096, "title": "【艺】三两", "spec": "绿色", "simple_desc": "1件24套", "price": "25.00"},
        ]

    def call(self, name, **kwargs):
        if name == "product_search":
            keyword = str(kwargs.get("keyword") or "").replace(" ", "").replace("【", "").replace("】", "")
            return [
                product
                for product in self.products
                if keyword and keyword in product["title"].replace("【", "").replace("】", "")
            ]
        if name == "inventory_search":
            keyword = str(kwargs.get("keyword") or "").replace(" ", "").replace("【", "").replace("】", "")
            color = kwargs.get("color") or ""
            return [
                {
                    "product_id": product["id"],
                    "产品名称": product["title"],
                    "【颜色】": product["spec"],
                    "【仓库】": "百鑫仓库",
                    "库存数量": 10,
                    "simple_desc": product["simple_desc"],
                }
                for product in self.products
                if keyword and keyword in product["title"].replace("【", "").replace("】", "") and (not color or color == product["spec"])
            ]
        if name == "product_info":
            for product in self.products:
                if int(product["id"]) == int(kwargs["product_id"]):
                    return product
            return {}
        raise AssertionError(f"unexpected call: {name}")


class ImageWorkflowParsingTest(unittest.TestCase):
    @patch("src.core.nodes.image_workflow._process_ocr_order")
    @patch("src.core.nodes.image_workflow.recognize_remark_texts", return_value=["测试备注"])
    @patch("src.core.nodes.image_workflow.ImageProcessor")
    def test_single_detected_frame_still_processes_the_full_image(
        self,
        processor_class,
        _recognize,
        process_order,
    ):
        processor = processor_class.return_value
        processor.detect_black_frames.return_value = [(1, 2, 30, 40)]
        processor._load_image.return_value = np.zeros((1000, 1000, 3), dtype=np.uint8)
        process_order.return_value = {
            "parsed": {"goods_name": "喜悦半斤"},
            "workflow_order_payload": {"goods_name": "喜悦半斤"},
        }

        result = process_single_image("design.png", MagicMock())

        processor.crop_frame.assert_not_called()
        process_order.assert_called_once_with(["测试备注"], "design.png", ANY)
        self.assertEqual(result["parsed"]["goods_name"], "喜悦半斤")

    @patch("src.core.nodes.image_workflow.save_temp_image", side_effect=["crop-1.jpg", "crop-2.jpg"])
    @patch("src.core.nodes.image_workflow._process_ocr_order")
    @patch("src.core.nodes.image_workflow.recognize_remark_texts", return_value=["测试备注"])
    @patch("src.core.nodes.image_workflow.os.path.exists", return_value=False)
    @patch("src.core.nodes.image_workflow.ImageProcessor")
    def test_two_detected_frames_keep_the_legacy_split_flow(
        self,
        processor_class,
        _exists,
        _recognize,
        process_order,
        _save_temp,
    ):
        processor = processor_class.return_value
        frames = [Frame(0, 0, 400, 400), Frame(500, 0, 400, 400)]
        processor.detect_black_frames.return_value = list(reversed(frames))
        processor._load_image.return_value = np.zeros((1000, 1000, 3), dtype=np.uint8)
        processor.crop_frame.side_effect = [object(), object()]
        process_order.side_effect = [
            {"parsed": {"goods_name": "商品一"}, "workflow_order_payload": {"goods_name": "商品一"}},
            {"parsed": {"goods_name": "商品二"}, "workflow_order_payload": {"goods_name": "商品二"}},
        ]

        result = process_single_image("legacy.png", MagicMock())

        self.assertEqual(processor.crop_frame.call_args_list, [call("legacy.png", frames[0]), call("legacy.png", frames[1])])
        self.assertEqual([item["parsed"]["goods_name"] for item in result["items"]], ["商品一", "商品二"])

    @patch("src.core.nodes.image_workflow.save_temp_image", side_effect=["crop-1.jpg", "crop-2.jpg"])
    @patch("src.core.nodes.image_workflow._process_ocr_order")
    @patch("src.core.nodes.image_workflow.recognize_remark_texts", return_value=["测试备注"])
    @patch("src.core.nodes.image_workflow.os.path.exists", return_value=False)
    @patch("src.core.nodes.image_workflow.ImageProcessor")
    def test_two_detected_frames_fall_back_to_one_full_design_when_only_one_is_valid(
        self,
        processor_class,
        _exists,
        _recognize,
        process_order,
        _save_temp,
    ):
        processor = processor_class.return_value
        processor.detect_black_frames.return_value = [Frame(0, 0, 400, 400), Frame(500, 0, 400, 400)]
        processor._load_image.return_value = np.zeros((1000, 1000, 3), dtype=np.uint8)
        processor.crop_frame.side_effect = [object(), object()]
        process_order.side_effect = [
            {"parsed": {"goods_name": "商品一"}, "workflow_order_payload": {"goods_name": "商品一"}},
            {"parsed": {}, "workflow_order_payload": None, "error": "未识别到礼盒名称"},
            {"parsed": {"goods_name": "整张设计稿"}, "workflow_order_payload": {"goods_name": "整张设计稿"}},
        ]

        result = process_single_image("design.png", MagicMock())

        self.assertNotIn("items", result)
        self.assertEqual(result["parsed"]["goods_name"], "整张设计稿")
        self.assertEqual(process_order.call_count, 3)

    @patch("src.core.nodes.image_workflow._process_ocr_order")
    @patch("src.core.nodes.image_workflow.recognize_remark_texts", return_value=["测试备注"])
    @patch("src.core.nodes.image_workflow.ImageProcessor")
    def test_batch_image_skips_legacy_frame_detection(
        self,
        processor_class,
        _recognize,
        process_order,
    ):
        process_order.return_value = {
            "parsed": {"goods_name": "喜悦半斤"},
            "workflow_order_payload": {"goods_name": "喜悦半斤"},
        }

        result = process_single_image("design.png", MagicMock(), allow_legacy_split=False)

        processor_class.return_value.detect_black_frames.assert_not_called()
        process_order.assert_called_once_with(["测试备注"], "design.png", ANY)
        self.assertEqual(result["parsed"]["goods_name"], "喜悦半斤")

    @patch("src.core.nodes.image_workflow._process_ocr_order")
    @patch("src.core.nodes.image_workflow.recognize_remark_texts", return_value=["整图备注"])
    @patch("src.core.nodes.image_workflow.save_temp_image")
    @patch("src.core.nodes.image_workflow.ImageProcessor")
    def test_small_decorative_frames_do_not_trigger_legacy_split(
        self,
        processor_class,
        save_temp,
        _recognize,
        process_order,
    ):
        processor = processor_class.return_value
        processor._load_image.return_value = np.zeros((1000, 1000, 3), dtype=np.uint8)
        processor.detect_black_frames.return_value = [
            Frame(20, 20, 120, 120),
            Frame(200, 100, 400, 400),
        ]
        process_order.return_value = {
            "parsed": {"goods_name": "整张设计稿"},
            "workflow_order_payload": {"goods_name": "整张设计稿"},
        }

        result = process_single_image("decorated.png", MagicMock())

        processor.crop_frame.assert_not_called()
        save_temp.assert_not_called()
        process_order.assert_called_once_with(["整图备注"], "decorated.png", ANY)
        self.assertEqual(result["parsed"]["goods_name"], "整张设计稿")

    @patch("src.core.nodes.image_workflow.upload_to_oss")
    @patch("src.core.nodes.image_workflow.repair_ocr_parsed_fields", return_value={"goods_name": ""})
    @patch("src.core.nodes.image_workflow.parse_ocr_text_list", return_value={"goods_name": ""})
    def test_invalid_ocr_candidate_is_not_uploaded(
        self,
        _parse,
        _repair,
        upload,
    ):
        result = _process_ocr_order(["装饰文字"], "invalid-crop.jpg", MagicMock())

        upload.assert_not_called()
        self.assertEqual(result["error"], "未识别到礼盒名称，未创建工作流订单")
        self.assertEqual(result["image_source_path"], "invalid-crop.jpg")

    @patch("src.core.nodes.image_workflow.find_product_by_goods_name", return_value=None)
    @patch("src.core.nodes.image_workflow.upload_to_oss", return_value="https://example.com/final.png")
    @patch("src.core.nodes.image_workflow.repair_ocr_parsed_fields", side_effect=lambda parsed, caller: parsed)
    @patch("src.core.nodes.image_workflow.parse_ocr_text_list")
    @patch(
        "src.core.nodes.image_workflow.recognize_remark_texts",
        side_effect=[["装饰一"], ["装饰二"], ["喜悦半斤红色10套"]],
    )
    @patch("src.core.nodes.image_workflow.save_temp_image", side_effect=["crop-1.jpg", "crop-2.jpg"])
    @patch("src.core.nodes.image_workflow.os.path.exists", return_value=False)
    @patch("src.core.nodes.image_workflow.ImageProcessor")
    def test_invalid_legacy_candidates_only_upload_the_full_image_once(
        self,
        processor_class,
        _exists,
        _save_temp,
        _recognize,
        parse,
        _repair,
        upload,
        _find_product,
    ):
        processor = processor_class.return_value
        processor._load_image.return_value = np.zeros((1000, 1000, 3), dtype=np.uint8)
        processor.detect_black_frames.return_value = [
            Frame(0, 0, 400, 400),
            Frame(500, 0, 400, 400),
        ]
        processor.crop_frame.side_effect = [object(), object()]

        def parsed_result(texts):
            if texts == ["喜悦半斤红色10套"]:
                return {
                    "goods_name": "喜悦半斤",
                    "color": "红色",
                    "quantity": 10,
                    "unit": "套",
                }
            return {"goods_name": ""}

        parse.side_effect = parsed_result

        result = process_single_image("design.png", MagicMock())

        upload.assert_called_once_with("design.png", ANY)
        self.assertEqual(result["image_url"], "https://example.com/final.png")
        self.assertEqual(result["workflow_order_payload"]["order_images"], ["https://example.com/final.png"])

    @patch("src.core.nodes.image_workflow.process_single_image")
    def test_image_batch_propagates_only_the_reliable_customer_across_files(self, process_one):
        results_by_path = {
            "first.png": {
                "parsed": {"customer_name": "齐唯茶业", "goods_name": "喜悦半斤", "customer_missing": False, "date": "2026-09-11"},
                "workflow_order_payload": {"customer": "齐唯茶业", "goods_name": "喜悦半斤"},
            },
            "second.png": {
                "parsed": {"customer_name": "散客", "goods_name": "岩味三两", "customer_missing": True},
                "workflow_order_payload": {"customer": "散客", "goods_name": "岩味三两"},
            },
        }
        process_one.side_effect = lambda path, caller, **kwargs: results_by_path[path]

        result = process_image_batch(["first.png", "second.png"], MagicMock())

        self.assertEqual(len(result["items"]), 2)
        self.assertEqual(result["items"][1]["parsed"]["customer_name"], "齐唯茶业")
        self.assertEqual(result["items"][1]["parsed"]["date"], "2026-09-11")
        self.assertEqual(result["items"][1]["workflow_order_payload"]["customer"], "齐唯茶业")
        self.assertEqual(result["items"][0]["source_image_index"], 0)
        self.assertEqual(result["items"][1]["source_image_index"], 1)
        self.assertEqual(
            [item.kwargs.get("allow_legacy_split") for item in process_one.call_args_list],
            [False, False],
        )

    @patch("src.core.nodes.image_workflow.process_single_image")
    def test_image_batch_runs_two_images_concurrently_but_preserves_order(self, process_one):
        lock = threading.Lock()
        both_started = threading.Event()
        active = 0
        maximum_active = 0

        def process(path, caller, **kwargs):
            nonlocal active, maximum_active
            with lock:
                active += 1
                maximum_active = max(maximum_active, active)
                if active >= 2:
                    both_started.set()
            both_started.wait(timeout=0.5)
            if path == "first.png":
                time.sleep(0.05)
            with lock:
                active -= 1
            return {
                "parsed": {"customer_name": "同一客户", "goods_name": path},
                "workflow_order_payload": {"customer": "同一客户", "goods_name": path},
            }

        process_one.side_effect = process

        result = process_image_batch(["first.png", "second.png"], MagicMock())

        self.assertEqual(maximum_active, 2)
        self.assertEqual(
            [item["parsed"]["goods_name"] for item in result["items"]],
            ["first.png", "second.png"],
        )

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

    def test_compact_date_and_ocr_uv_do_not_pollute_goods_name(self):
        parsed = parse_ocr_text_list([
            "客户：和言",
            "20260618云岭三小盒UIV 香槟金 20套",
            "提袋 丝印",
        ])

        self.assertEqual(parsed["customer_name"], "和言")
        self.assertEqual(parsed["date"], "2026-06-18")
        self.assertEqual(parsed["goods_name"], "云岭三小盒")
        self.assertEqual(parsed["color"], "香槟金")
        self.assertEqual(parsed["quantity"], 20)
        self.assertEqual(parsed["unit"], "套")
        self.assertIn("UV", parsed["craft"])
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

    def test_short_style_half_jin_design_order_matches_short_half_jin(self):
        for line in ["见喜短款半斤红色1件", "见喜 短 款 半 斤 红色 1件"]:
            with self.subTest(line=line):
                parsed = parse_ocr_text_list([line])

                self.assertEqual(_normalize_goods_keyword(parsed["goods_name"]).replace(" ", ""), "见喜短半斤")
                self.assertEqual(parsed["color"], "红色")
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

    def test_batch_goods_context_repairs_brandless_same_spec_item(self):
        items = [
            {
                "parsed": {"customer_name": "天佑", "goods_name": "三两", "color": "橙色", "quantity": 6, "unit": "套"},
                "product_warning": ["三两"],
                "workflow_order_payload": {"customer": "天佑", "goods_name": "三两", "color": "橙色", "quantity": 6},
            },
            {
                "parsed": {
                    "customer_name": "天佑",
                    "goods_name": "【艺】三两",
                    "color": "绿色",
                    "quantity": 6,
                    "unit": "套",
                    "product_id": 1096,
                    "product_info": {"id": 1096, "title": "【艺】三两", "spec": "绿色"},
                },
                "product_warning": [],
                "workflow_order_payload": {"customer": "天佑", "goods_name": "【艺】三两", "color": "绿色", "quantity": 6},
            },
        ]

        propagate_batch_goods_context(items, FakeGoodsContextCaller())

        self.assertEqual(items[0]["parsed"]["goods_name"], "【艺】三两")
        self.assertEqual(items[0]["parsed"]["product_id"], 1086)
        self.assertEqual(items[0]["workflow_order_payload"]["goods_name"], "【艺】三两")
        self.assertEqual(items[0]["product_warning"], [])

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
