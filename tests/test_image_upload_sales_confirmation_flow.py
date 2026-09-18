import unittest
from unittest.mock import patch

from src.channels import http_api
from src.core.product_matcher import ProductMatcher
from src.skills.order_flow.workflow import OrderFlowWorkflow


class FakeSession:
    def __init__(self):
        self.saved = []

    def save_pending(self, intent, state):
        self.saved.append((intent, state))

    def has_pending(self):
        return bool(self.saved)


def _image_item(customer="测试客户", goods="喜悦半斤", color="红色", qty=2):
    return {
        "parsed": {
            "customer_name": customer,
            "goods_name": goods,
            "color": color,
            "quantity": qty,
            "unit": "套",
        },
        "workflow_order_payload": {
            "customer": customer,
            "goods_name": goods,
            "color": color,
            "quantity": qty,
            "order_images": ["https://example.test/design.jpg"],
        },
    }


class FakeProductIdCaller:
    def __init__(self):
        self.calls = []

    def call(self, tool_name, **kwargs):
        self.calls.append((tool_name, kwargs))
        if tool_name == "product_info":
            return {
                "id": kwargs["product_id"],
                "product_id": kwargs["product_id"],
                "title": "【艺】三两",
                "name": "【艺】三两",
                "spec": "绿色",
                "simple_desc": "1件24套",
                "price": "25.00",
                "is_stock_item": 1,
                "product_type": "gift_box",
                "purchase_policy": "order_qty",
                "base": [{"unit_id": 1, "unit_name": "套", "price": "25.00"}],
            }
        if tool_name == "get_unit_list":
            return [{"id": 1, "name": "套"}]
        if tool_name == "product_search":
            return []
        raise AssertionError(f"unexpected tool call: {tool_name}")


class FakeOneJinRelatedCandidateCaller:
    def __init__(self):
        self.calls = []
        self.product = {
            "id": 2201,
            "product_id": 2201,
            "title": "【顶峰见】一斤盒",
            "name": "【顶峰见】一斤盒",
            "spec": "红色",
            "simple_desc": "1件20套",
            "price": "38.00",
            "is_stock_item": 1,
            "product_type": "gift_box",
            "purchase_policy": "order_qty",
            "base": [{"unit_id": 1, "unit_name": "套", "price": "38.00"}],
        }

    def call(self, tool_name, **kwargs):
        self.calls.append((tool_name, kwargs))
        if tool_name == "product_search":
            keyword = str(kwargs.get("keyword") or "").replace(" ", "")
            return [self.product] if keyword == "顶峰" else []
        if tool_name == "inventory_search":
            keyword = str(kwargs.get("keyword") or "").replace(" ", "")
            if keyword == "顶峰" and kwargs.get("color") == "红色":
                return [
                    {
                        "product_id": 2201,
                        "产品名称": "【顶峰见】一斤盒",
                        "【颜色】": "红色",
                        "【仓库】": "百鑫仓库",
                        "库存数量": 12,
                        "simple_desc": "1件20套",
                    }
                ]
            return []
        if tool_name == "product_info":
            return dict(self.product) if int(kwargs["product_id"]) == 2201 else None
        if tool_name == "get_unit_list":
            return [{"id": 1, "name": "套"}]
        raise AssertionError(f"unexpected tool call: {tool_name}")


class ImageUploadSalesConfirmationFlowTest(unittest.TestCase):
    def test_product_correction_parses_compact_name_spec_and_color_in_any_order(self):
        workflow = object.__new__(OrderFlowWorkflow)

        for correction in ("墨香3两黄色", "墨香黄色3两", "墨香二三两黄色"):
            with self.subTest(correction=correction):
                corrected = workflow._apply_product_correction(
                    {
                        "name": "墨香半斤",
                        "color": "咖色",
                        "qty": 6,
                        "unit": "套",
                        "_match_candidates": [{"id": 1}],
                    },
                    correction,
                )

                self.assertEqual(corrected["name"], "墨香 二三两")
                self.assertEqual(corrected["color"], "黄色")
                self.assertEqual(corrected["qty"], 6)
                self.assertEqual(corrected["unit"], "套")
                self.assertNotIn("_match_candidates", corrected)

    def test_product_correction_accepts_color_alias_without_replacing_name(self):
        workflow = object.__new__(OrderFlowWorkflow)

        corrected = workflow._apply_product_correction(
            {"name": "墨香 二三两", "color": "咖色", "qty": 2, "unit": "套"},
            "黄",
        )

        self.assertEqual(corrected["name"], "墨香 二三两")
        self.assertEqual(corrected["color"], "黄色")

    def test_product_correction_without_color_preserves_existing_color(self):
        workflow = object.__new__(OrderFlowWorkflow)

        corrected = workflow._apply_product_correction(
            {"name": "墨香半斤", "color": "红色", "qty": 2, "unit": "套"},
            "墨香3两",
        )

        self.assertEqual(corrected["name"], "墨香 二三两")
        self.assertEqual(corrected["color"], "红色")

    def test_product_clarification_question_shows_compact_reply_example(self):
        workflow = object.__new__(OrderFlowWorkflow)
        workflow.product_matcher = ProductMatcher(FakeProductIdCaller())

        question = workflow._format_product_clarification_question(
            {"name": "墨香 二三两", "color": ""}
        )

        self.assertIn("墨香3两黄色", question)

    def test_product_name_pending_uses_compact_correction_before_continuing(self):
        workflow = object.__new__(OrderFlowWorkflow)
        captured = {}

        class CorrectionCaller:
            def __init__(self):
                self.calls = []

            def call(self, tool_name, **kwargs):
                self.calls.append((tool_name, kwargs))
                if tool_name == "workflow_order_correct_product":
                    return {"code": 0, "data": {"id": kwargs["order_id"], "remark": "丝印"}}
                raise AssertionError(f"unexpected tool call: {tool_name}")

        workflow.caller = CorrectionCaller()

        def capture_continue(**kwargs):
            captured.update(kwargs)
            return {"status": "captured"}

        workflow._continue_after_product_resolution = capture_continue
        result = workflow.resume(
            "墨香黄色3两",
            {
                "customer_id": 7,
                "customer_name": "测试客户",
                "products": [
                    {"name": "墨香半斤", "color": "咖色", "qty": 6, "unit": "套"}
                ],
                "product_index": 0,
                "warehouse_hint": "百鑫仓库",
                "workflow_order_ids": [456],
                "pending_action": "confirm_product_name",
            },
        )

        self.assertEqual(result, {"status": "captured"})
        self.assertEqual(captured["products"][0]["name"], "墨香 二三两")
        self.assertEqual(captured["products"][0]["color"], "黄色")
        self.assertEqual(captured["products"][0]["qty"], 6)
        self.assertEqual(captured["workflow_order_ids"], [456])
        self.assertEqual(workflow.caller.calls, [(
            "workflow_order_correct_product",
            {
                "order_id": 456,
                "goods_name": "墨香 二三两",
                "color": "黄色",
            },
        )])

    def test_order_params_preserve_confirmed_image_product_id(self):
        item = _image_item(goods="【艺】三两", color="绿色", qty=6)
        item["parsed"]["product_id"] = 1096

        params = http_api._order_params_from_image_result({"items": [item]})

        self.assertEqual(params["products"][0]["product_id"], 1096)
        self.assertEqual(params["products"][0]["name"], "【艺】三两")

    def test_order_flow_uses_confirmed_product_id_without_name_rematch(self):
        caller = FakeProductIdCaller()
        workflow = object.__new__(OrderFlowWorkflow)
        workflow.caller = caller
        workflow.product_matcher = ProductMatcher(caller)

        resolved = workflow._search_product({
            "product_id": 1096,
            "name": "三两",
            "color": "绿色",
            "qty": 6,
            "unit": "套",
        })

        self.assertIsNotNone(resolved)
        self.assertEqual(resolved["product_id"], 1096)
        self.assertEqual(resolved["name"], "【艺】三两")
        self.assertNotIn("product_search", [name for name, _ in caller.calls])

    def test_order_flow_auto_uses_unique_related_one_jin_box_candidate(self):
        caller = FakeOneJinRelatedCandidateCaller()
        workflow = object.__new__(OrderFlowWorkflow)
        workflow.caller = caller
        workflow.product_matcher = ProductMatcher(caller)

        resolved = workflow._search_product({
            "name": "顶峰见一斤盒",
            "color": "红色",
            "qty": 20,
            "unit": "套",
        })

        self.assertIsNotNone(resolved)
        self.assertEqual(resolved["product_id"], 2201)
        self.assertEqual(resolved["name"], "【顶峰见】一斤盒")
        self.assertEqual(resolved["color"], "红色")

    def test_auto_creates_workflow_then_saves_sales_confirmation_pending(self):
        session = FakeSession()
        captured_workflow_rows = []
        captured_order_params = []

        class FakeWorkflowOrderFlow:
            def _create_many(self, rows):
                captured_workflow_rows.extend(rows)
                return {
                    "status": "done",
                    "reply": "已创建 1 个工作流订单：\n1. 测试客户 | 喜悦半斤 红色 | 2 | 单号 456",
                    "workflow_order_ids": [456],
                }

        class FakeOrderFlow:
            def execute(self, user_input, params=None):
                captured_order_params.append(dict(params or {}))
                return {
                    "status": "ask",
                    "intent": "order",
                    "question": "请确认是否执行开单：",
                    "state": {
                        "pending_action": "confirm_create_order",
                        "customer_name": "测试客户",
                        "products": list((params or {}).get("products") or []),
                    },
                }

        with patch("src.skills.workflow_order.workflow.WorkflowOrderWorkflow", FakeWorkflowOrderFlow), patch(
            "src.skills.order_flow.workflow.OrderFlowWorkflow", FakeOrderFlow
        ):
            response = http_api._handle_image_auto_workflow_sales_flow(
                {"items": [_image_item()]},
                session,
                "图片识别完成。",
            )

        self.assertEqual(len(captured_workflow_rows), 1)
        self.assertEqual(captured_order_params[0]["workflow_order_id"], 456)
        self.assertEqual(captured_order_params[0]["workflow_order_ids"], [456])
        self.assertEqual(session.saved[0][0], "order")
        self.assertEqual(session.saved[0][1]["pending_action"], "confirm_create_order")
        self.assertEqual(session.saved[0][1]["workflow_order_ids"], [456])
        self.assertIn("工作流已创建，下面确认是否按识别内容开销售单", response)
        self.assertNotIn("是否创建", response)
        self.assertNotIn("是否需要继续开销售单", response)
        self.assertNotIn("confirm_image_sales", str(session.saved[0][1]))

    def test_same_customer_batch_creates_one_sales_pending_with_all_workflow_ids(self):
        session = FakeSession()
        captured_order_params = []

        class FakeWorkflowOrderFlow:
            def _create_many(self, rows):
                self.rows = rows
                return {
                    "status": "done",
                    "reply": "已创建 2 个工作流订单",
                    "workflow_order_ids": [456, 457],
                }

        class FakeOrderFlow:
            def execute(self, user_input, params=None):
                captured_order_params.append(dict(params or {}))
                return {
                    "status": "ask",
                    "intent": "order",
                    "question": "请确认是否执行开单：",
                    "state": {
                        "pending_action": "confirm_create_order",
                        "products": list((params or {}).get("products") or []),
                    },
                }

        result = {
            "items": [
                _image_item(customer="客户A", goods="喜悦半斤", color="红色"),
                _image_item(customer="客户A", goods="岩味三两", color="蓝色"),
            ]
        }
        with patch("src.skills.workflow_order.workflow.WorkflowOrderWorkflow", FakeWorkflowOrderFlow), patch(
            "src.skills.order_flow.workflow.OrderFlowWorkflow", FakeOrderFlow
        ):
            http_api._handle_image_auto_workflow_sales_flow(result, session, "图片识别完成。")

        self.assertEqual(len(captured_order_params), 1)
        self.assertEqual(len(captured_order_params[0]["products"]), 2)
        self.assertEqual(captured_order_params[0]["workflow_order_ids"], [456, 457])
        self.assertEqual(session.saved[0][1]["workflow_order_ids"], [456, 457])

    def test_multi_customer_images_create_workflows_but_do_not_merge_sales_pending(self):
        session = FakeSession()

        class FakeWorkflowOrderFlow:
            def _create_many(self, rows):
                return {
                    "status": "done",
                    "reply": "已创建 2 个工作流订单",
                    "workflow_order_ids": [456, 457],
                }

        class FakeOrderFlow:
            def execute(self, user_input, params=None):
                raise AssertionError("multi-customer images must not enter merged sales order flow")

        result = {"items": [_image_item(customer="客户A"), _image_item(customer="客户B", color="蓝色")]}

        with patch("src.skills.workflow_order.workflow.WorkflowOrderWorkflow", FakeWorkflowOrderFlow), patch(
            "src.skills.order_flow.workflow.OrderFlowWorkflow", FakeOrderFlow
        ):
            response = http_api._handle_image_auto_workflow_sales_flow(result, session, "图片识别完成。")

        self.assertFalse(session.has_pending())
        self.assertIn("识别到多个客户，不能合并成一张销售单", response)
        self.assertNotIn("是否创建", response)
        self.assertNotIn("是否需要继续开销售单", response)

    def test_image_without_workflow_payload_still_enters_sales_confirmation_without_extra_question(self):
        session = FakeSession()

        class FakeOrderFlow:
            def execute(self, user_input, params=None):
                return {
                    "status": "ask",
                    "intent": "order",
                    "question": "请确认是否执行开单：",
                    "state": {
                        "pending_action": "confirm_create_order",
                        "products": list((params or {}).get("products") or []),
                    },
                }

        result = {"items": [{"parsed": _image_item()["parsed"]}]}

        with patch("src.skills.order_flow.workflow.OrderFlowWorkflow", FakeOrderFlow):
            response = http_api._handle_image_auto_workflow_sales_flow(result, session, "图片识别完成。")

        self.assertEqual(session.saved[0][0], "order")
        self.assertEqual(session.saved[0][1]["pending_action"], "confirm_create_order")
        self.assertNotIn("confirm_image_sales", str(session.saved[0][1]))
        self.assertNotIn("是否需要继续开销售单", response)


if __name__ == "__main__":
    unittest.main()
