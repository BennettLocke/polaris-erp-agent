import unittest
from unittest.mock import patch
from pathlib import Path

from src.skills.order_flow.workflow import OrderFlowWorkflow
from src.skills.workflow_order.workflow import WorkflowOrderWorkflow

ROOT = Path(__file__).resolve().parents[1]


class FakeOrderCaller:
    def __init__(self):
        self.calls = []

    def call(self, tool_name, **kwargs):
        self.calls.append((tool_name, kwargs))
        if tool_name == "product_info":
            return {"base": [{"unit_id": 1, "unit_name": "套", "price": 10}]}
        if tool_name == "sales_add":
            return {"code": 0, "data": {"id": 123, "sales_no": "SO123"}}
        raise AssertionError(f"unexpected tool call: {tool_name}")

    def last_call(self, tool_name):
        for name, kwargs in reversed(self.calls):
            if name == tool_name:
                return kwargs
        raise AssertionError(f"{tool_name} was not called")


class FakeWorkflowCaller:
    def __init__(self):
        self.next_id = 456

    def call(self, tool_name, **kwargs):
        if tool_name != "workflow_order_save":
            raise AssertionError(f"unexpected tool call: {tool_name}")
        result = {"code": 0, "data": {"id": self.next_id}}
        self.next_id += 1
        return result


class FakePurchaseOrderCaller(FakeOrderCaller):
    def call(self, tool_name, **kwargs):
        if tool_name == "other_enter_add":
            self.calls.append((tool_name, kwargs))
            return {"code": 0, "data": {"id": 321, "doc_no": "IN321"}}
        return super().call(tool_name, **kwargs)


class WorkflowSalesLinkingTest(unittest.TestCase):
    def test_auto_purchase_order_reply_contains_compact_purchase_result(self):
        workflow = object.__new__(OrderFlowWorkflow)
        workflow.caller = FakePurchaseOrderCaller()
        state = {
            "pending_action": "confirm_create_order",
            "customer_id": 7,
            "customer_name": "测试客户",
            "warehouse_id": 2,
            "auto_purchase": True,
            "products": [
                {
                    "product_id": 88,
                    "unit_id": 1,
                    "unit": "套",
                    "name": "【墨香】半斤",
                    "color": "黄色",
                    "qty": 10,
                    "price": 27,
                    "warehouse_id": 2,
                    "purchase_warehouse_id": 2,
                    "purchase_qty": 10,
                    "purchase_unit": "套",
                    "need_purchase": True,
                }
            ],
        }

        result = workflow.resume("确认", state)

        notice = "商品：墨香半斤\n颜色：黄色\n进货：10套\n备注：送至百鑫"
        self.assertIn(notice, result["reply"])
        self.assertNotIn("【进货结果】", result["reply"])
        self.assertLess(result["reply"].index("商品：墨香半斤"), result["reply"].index("开单成功"))
        self.assertEqual(workflow.caller.last_call("other_enter_add")["note"], "送至百鑫")

    def test_piece_purchase_result_omits_per_piece_description(self):
        workflow = object.__new__(OrderFlowWorkflow)

        quantity = workflow._purchase_result_quantity({
            "purchase_qty": 1,
            "purchase_unit": "件",
            "per_piece": 24,
        })

        self.assertEqual(quantity, "1件")

    def test_multiple_purchase_results_merge_products_and_keep_one_final_note(self):
        workflow = object.__new__(OrderFlowWorkflow)

        result = workflow._format_purchase_results([
            {"product": "墨香半斤", "color": "黄色", "quantity": "10套", "note": "送至百鑫"},
            {"product": "喜悦半斤", "color": "红色", "quantity": "5套", "note": "送至百鑫"},
        ])

        self.assertEqual(
            result,
            "商品：墨香半斤（黄色，10套）、喜悦半斤（红色，5套）\n备注：送至百鑫",
        )
        self.assertEqual(result.count("商品："), 1)
        self.assertEqual(result.count("备注："), 1)

    def test_order_flow_passes_workflow_order_id_to_sales_add_after_confirm(self):
        workflow = object.__new__(OrderFlowWorkflow)
        workflow.caller = FakeOrderCaller()
        state = {
            "pending_action": "confirm_create_order",
            "customer_id": 7,
            "customer_name": "测试客户",
            "warehouse_id": 2,
            "skip_inventory": True,
            "workflow_order_id": 456,
            "products": [
                {
                    "product_id": 88,
                    "unit_id": 1,
                    "unit": "套",
                    "name": "测试礼盒",
                    "qty": 2,
                    "price": 10,
                    "warehouse_id": 2,
                }
            ],
        }

        result = workflow.resume("ok", state)

        self.assertIn("reply", result)
        sales_call = workflow.caller.last_call("sales_add")
        self.assertEqual(sales_call["workflow_order_id"], 456)

    def test_image_workflow_passes_created_workflow_id_to_order_flow(self):
        captured_params = []

        class FakeOrderFlow:
            def execute(self, user_input, params=None):
                captured_params.append(dict(params or {}))
                return {"status": "ask", "question": "confirm", "state": {}}

        workflow = WorkflowOrderWorkflow()
        workflow.caller = FakeWorkflowCaller()
        state = {
            "pending_action": "confirm_image_workflow_orders",
            "parsed_list": [
                {"customer": "测试客户", "goods_name": "测试礼盒", "quantity": 2, "color": "红色"}
            ],
            "order_params": {
                "products": [{"product_id": 88, "name": "测试礼盒", "qty": 2}],
            },
        }

        with patch("src.skills.order_flow.workflow.OrderFlowWorkflow", FakeOrderFlow):
            result = workflow.resume("ok", state)

        self.assertEqual(result["status"], "ask")
        self.assertEqual(captured_params[0]["workflow_order_id"], 456)
        self.assertEqual(captured_params[0]["customer"], "测试客户")

    def test_order_flow_confirm_state_includes_warehouse_name_for_ui(self):
        source = (ROOT / "src" / "skills" / "order_flow" / "workflow.py").read_text(encoding="utf-8")
        confirm_source = source.split("def _confirm_create_order", 1)[1].split("def _create_order", 1)[0]

        self.assertIn('"warehouse_name": self._warehouse_name(warehouse_id)', confirm_source)


if __name__ == "__main__":
    unittest.main()
