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


class WorkflowSalesLinkingTest(unittest.TestCase):
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
