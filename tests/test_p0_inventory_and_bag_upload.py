import unittest
from unittest.mock import patch

from src.core.nodes.executor import executor_node
from src.skills.bag_upload.workflow import BagUploadWorkflow


class FakeProductService:
    def __init__(self) -> None:
        self.saved_payloads = []

    def options(self, product_id=None):
        return {
            "code": 0,
            "data": {
                "unit_list": [
                    {"id": 1, "name": "套", "code": "tao"},
                    {"id": 2, "name": "捆", "code": "kun"},
                    {"id": 3, "name": "个", "code": "ge"},
                ]
            },
        }

    def save(self, payload):
        self.saved_payloads.append(payload)
        return {"code": 0, "data": {"id": 1001}}


class FakeToolCaller:
    def __init__(self) -> None:
        self.calls = []

    def call(self, tool_name, **kwargs):
        self.calls.append((tool_name, kwargs))
        if tool_name == "inventory_transfer":
            return {"code": 0, "data": 2001}
        if tool_name == "sales_history_price":
            return None
        if tool_name == "get_product_price":
            return 18
        if tool_name == "sales_add":
            return {"code": 0, "data": 3001, "sales_no": "SO3001"}
        raise AssertionError(f"unexpected tool call: {tool_name}")

    def last_call(self, tool_name):
        for name, kwargs in reversed(self.calls):
            if name == tool_name:
                return kwargs
        raise AssertionError(f"{tool_name} was not called")


class P0InventoryAndBagUploadTest(unittest.TestCase):
    def test_bag_upload_new_product_uses_bundle_unit(self):
        service = FakeProductService()
        workflow = BagUploadWorkflow()

        with patch("src.skills.bag_upload.workflow.get_product_service", return_value=service):
            workflow._save_product_to_core(
                title="测试肉桂长泡袋",
                code="SJ9999",
                category_id=7,
                main_url="https://example.com/main.png",
                detail_url="https://example.com/detail.png",
            )

        unit_id = service.saved_payloads[0]["base"]["new_0"]["unit"]["new_0"]["unit_id"]
        self.assertEqual(unit_id, 2)

    def test_transfer_order_sales_deducts_from_destination_warehouse(self):
        caller = FakeToolCaller()
        state = {
            "pending_orders": [
                {
                    "action": "transfer",
                    "product_id": 101,
                    "unit_id": 1,
                    "warehouse_id": 1,
                    "from_warehouse": 1,
                    "to_warehouse": 2,
                    "quantity": 6,
                    "product_name": "【岩彩】一两",
                    "color": "红色",
                }
            ],
            "customer_info": {"customer_id": 999},
        }

        with patch("src.core.nodes.executor.get_tool_caller", return_value=caller):
            executor_node(state)

        transfer_call = caller.last_call("inventory_transfer")
        self.assertEqual(transfer_call["out_warehouse_id"], 1)
        self.assertEqual(transfer_call["enter_warehouse_id"], 2)

        sales_call = caller.last_call("sales_add")
        self.assertEqual(sales_call["products"][0]["warehouse_id"], 2)


if __name__ == "__main__":
    unittest.main()
