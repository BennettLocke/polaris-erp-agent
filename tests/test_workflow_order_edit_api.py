import unittest
from unittest.mock import patch

from src.channels.http_api import _workflow_card, app


class FakeWorkflowService:
    def __init__(self):
        self.calls = []

    def save_order(self, **kwargs):
        self.calls.append(kwargs)
        return {"code": 0, "data": {"id": kwargs.get("order_id")}}


class WorkflowOrderEditApiTest(unittest.TestCase):
    def test_edit_updates_existing_order_for_current_and_legacy_id_fields(self):
        for id_field in ("id", "order_id"):
            with self.subTest(id_field=id_field):
                service = FakeWorkflowService()
                payload = {
                    id_field: 456,
                    "customer_name": "测试客户",
                    "goods_name": "【墨香】二三两",
                    "goods_color": "黄色",
                    "order_quantity": 6,
                    "remark": "丝印",
                }
                with (
                    patch("src.channels.http_api.get_workflow_service", return_value=service),
                    patch("src.channels.http_api._current_web_user", return_value={"id": 1, "native_user_id": 1}),
                    patch("src.channels.http_api._has_permission", return_value=True),
                ):
                    response = app.test_client().post("/api/workflow/orders", json=payload)

                self.assertEqual(response.status_code, 200)
                self.assertEqual(service.calls[0]["order_id"], 456)
                self.assertEqual(service.calls[0]["remark"], "丝印")

    def test_workflow_card_returns_remark_for_edit_form(self):
        card = _workflow_card({"id": 456, "remark": "丝印", "goods_name": "测试礼盒"})

        self.assertEqual(card["remark"], "丝印")


if __name__ == "__main__":
    unittest.main()
