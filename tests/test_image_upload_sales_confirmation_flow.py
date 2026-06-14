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
        self.assertEqual(session.saved[0][0], "order")
        self.assertEqual(session.saved[0][1]["pending_action"], "confirm_create_order")
        self.assertIn("工作流已创建，下面确认是否按识别内容开销售单", response)
        self.assertNotIn("是否创建", response)
        self.assertNotIn("是否需要继续开销售单", response)
        self.assertNotIn("confirm_image_sales", str(session.saved[0][1]))

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
