import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from src.channels import http_api
from src.core.session import SessionManager


class ImageCorrectionPendingTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        directory = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.stack.enter_context(patch("src.core.session.HISTORY_DIR", directory))
        self.stack.enter_context(patch.object(http_api, "_current_web_user", return_value={"id": 1}))
        self.stack.enter_context(patch.object(http_api, "_has_permission", return_value=True))
        self.products = {44: {"id": 44, "title": "【墨香】二三两", "color": "黄色", "case_pack_qty": 24, "native_status": "active"}}
        service = self.stack.enter_context(patch.object(http_api, "get_product_service"))
        service.return_value.info.side_effect = self.products.get
        workflow_service = self.stack.enter_context(patch.object(http_api, "get_workflow_service"))
        workflow_service.return_value.find_saved_batch.return_value = []
        self.state = {
            "pending_action": "confirm_image_workflow_correction", "correction_batch_id": "batch-1", "customer_name": "齐唯",
            "parsed_list": [{"correction_id": "row-1", "goods_name": "墨相3两", "quantity": 1, "unit": "件", "selected_sku_id": 44}],
        }
        self.session = SessionManager("correction-test")
        self.session.save_pending("workflow", self.state)

    def post(self, state=None, execute="confirm"):
        with http_api.app.test_client() as client:
            return client.post("/api/session/pending", json={"session_id": "correction-test", "state": state or self.state, "execute": execute})

    def test_cancel_incomplete_rows_does_not_call_workflow_and_old_form_cannot_confirm(self):
        incomplete = deepcopy(self.state)
        incomplete["parsed_list"][0].pop("selected_sku_id")
        with patch("src.skills.workflow_order.workflow.WorkflowOrderWorkflow.resume") as resume:
            response = self.post(incomplete, "cancel")
            self.assertEqual(response.status_code, 200)
            self.assertFalse(response.get_json()["data"]["session"]["has_pending"])
            self.assertIn("没有写入系统", response.get_json()["data"]["response"])
            self.assertEqual(self.post().status_code, 400)
            resume.assert_not_called()

    def test_stale_batch_and_changed_action_cannot_write(self):
        with patch("src.skills.workflow_order.workflow.WorkflowOrderWorkflow.resume") as resume:
            stale = deepcopy(self.state)
            stale["correction_batch_id"] = "old-batch"
            self.assertEqual(self.post(stale).status_code, 409)
            changed = deepcopy(self.state)
            changed["pending_action"] = "confirm_image_workflow_orders"
            self.assertEqual(self.post(changed).status_code, 400)
            resume.assert_not_called()

    def test_two_failed_rows_must_each_select_a_real_sku(self):
        incomplete = deepcopy(self.state)
        incomplete["parsed_list"].append({"correction_id": "row-2", "goods_name": "喜悦半斤", "quantity": 2, "unit": "套", "source_filename": "two.png"})
        self.session.save_pending("workflow", incomplete)
        with patch("src.skills.workflow_order.workflow.WorkflowOrderWorkflow.resume") as resume:
            response = self.post(incomplete)
            self.assertEqual(response.status_code, 400)
            self.assertIn("第 2 张", response.get_json()["msg"])
            self.assertIn("选择商品", response.get_json()["msg"])
            resume.assert_not_called()

    def test_confirm_rechecks_disabled_product(self):
        self.products[44]["native_status"] = "inactive"
        with patch("src.skills.workflow_order.workflow.WorkflowOrderWorkflow.resume") as resume:
            response = self.post()
            self.assertEqual(response.status_code, 400)
            self.assertIn("不可用", response.get_json()["msg"])
            resume.assert_not_called()

    def test_confirm_changes_pending_once_and_never_confirms_the_next_sales_step(self):
        result = {"status": "ask", "intent": "order", "question": "销售单确认", "state": {"pending_action": "confirm_create_order"}}
        with patch("src.skills.workflow_order.workflow.WorkflowOrderWorkflow.resume", return_value=result) as resume:
            first = self.post()
            second = self.post()
            self.assertEqual(first.status_code, 200)
            self.assertEqual(first.get_json()["data"]["session"]["pending_action"], "confirm_create_order")
            self.assertEqual(second.status_code, 409)
            resume.assert_called_once()
            canonical = resume.call_args.args[1]
            self.assertEqual(canonical["parsed_list"][0]["goods_name"], "【墨香】二三两")
            self.assertEqual(canonical["parsed_list"][0]["quantity"], 24)

    def test_parallel_duplicate_confirm_is_serialized(self):
        entered = threading.Event()
        release = threading.Event()

        def resume(*_args):
            entered.set()
            self.assertTrue(release.wait(3))
            return {"status": "ask", "intent": "order", "question": "销售单确认", "state": {"pending_action": "confirm_create_order"}}

        with patch("src.skills.workflow_order.workflow.WorkflowOrderWorkflow.resume", side_effect=resume) as call:
            with ThreadPoolExecutor(max_workers=2) as executor:
                first = executor.submit(self.post)
                self.assertTrue(entered.wait(3))
                second = executor.submit(self.post)
                release.set()
                statuses = sorted([first.result().status_code, second.result().status_code])
        self.assertEqual(statuses, [200, 409])
        call.assert_called_once()

    def test_real_correction_flow_uses_one_atomic_batch_and_links_every_result(self):
        from unittest.mock import Mock
        from src.engine.native_db import NativeDBClient
        from src.services.business.workflow import WorkflowService
        from tests.test_native_workflow_batch import FakeConnection

        connection = FakeConnection()
        connection.skus[44] = {"id": 44, "spu_id": 18, "sku_no": "SJ0044", "title": "【墨香】二三两", "color": "黄色", "status": "active", "is_sellable": 1, "case_pack_qty": 24}
        connection.spus[18] = {"id": 18, "status": "active", "deleted_at": None}
        db = object.__new__(NativeDBClient)
        db._get_connection = lambda: connection
        db._operator_user_id = lambda: 7
        db.query = lambda _sql, numbers: [row for row in connection.saved["orders"] if row["workflow_no"] in numbers]
        caller = Mock()
        caller.call.side_effect = lambda name, **kwargs: self.products.get(kwargs["product_id"]) if name == "product_info" else None
        state = deepcopy(self.state)
        state["parsed_list"].append({**state["parsed_list"][0], "correction_id": "row-2", "quantity": 2, "unit": "套"})
        self.session.save_pending("workflow", state)
        with patch("src.skills.workflow_order.workflow.get_tool_caller", return_value=caller), \
                patch("src.services.business.workflow.get_workflow_service", return_value=WorkflowService(db)), \
                patch("src.skills.order_flow.workflow.OrderFlowWorkflow") as order:
            order.return_value.execute.return_value = {"status": "ask", "question": "销售单确认", "state": {"pending_action": "confirm_create_order"}}
            response = self.post(state)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(connection.transactions, 1)
        self.assertEqual(connection.commits, 1)
        self.assertEqual(len(connection.saved["orders"]), 2)
        self.assertEqual([row["quantity"] for row in connection.saved["orders"]], [24, 2])
        params = order.return_value.execute.call_args.kwargs["params"]
        self.assertEqual(params["workflow_order_ids"], [1, 2])
        self.assertEqual([p["product_id"] for p in params["products"]], [44, 44])
        self.assertEqual(self.post(state).status_code, 409)

    def test_stale_nonexecuting_update_cannot_restore_correction_after_success(self):
        self.session.save_pending("order", {"pending_action": "confirm_create_order"})
        with http_api.app.test_client() as client:
            response = client.post("/api/session/pending", json={"session_id": "correction-test", "state": self.state})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(SessionManager("correction-test").get_state()["pending_action"], "confirm_create_order")

    def test_sales_handoff_failure_after_commit_never_leaves_cancellable_correction(self):
        from unittest.mock import Mock
        caller = Mock()
        caller.call.side_effect = lambda name, **kwargs: self.products.get(kwargs["product_id"]) if name == "product_info" else None
        with patch("src.skills.workflow_order.workflow.get_tool_caller", return_value=caller), \
                patch("src.services.business.workflow.get_workflow_service") as service, \
                patch("src.skills.order_flow.workflow.OrderFlowWorkflow") as order:
            service.return_value.save_orders_batch.return_value = {"code": 0, "data": [{"id": 99}]}
            service.return_value.find_saved_batch.return_value = []
            order.return_value.execute.side_effect = RuntimeError("handoff failed")
            response = self.post()
            self.assertEqual(response.status_code, 200)
            self.assertIn("工作流订单已创建", response.get_json()["data"]["response"])
            self.assertFalse(response.get_json()["data"]["session"]["has_pending"])
            self.assertEqual(self.post(execute="cancel").status_code, 400)
            service.return_value.save_orders_batch.assert_called_once()

    def test_cancel_and_confirm_reconcile_committed_rows_after_checkpoint_write_failure(self):
        for execute in ("cancel", "confirm"):
            with self.subTest(execute=execute):
                self.session.save_pending("workflow", self.state)
                with patch.object(http_api, "get_workflow_service") as service, \
                        patch("src.skills.workflow_order.workflow.WorkflowOrderWorkflow.resume") as resume:
                    service.return_value.find_saved_batch.return_value = [{"id": 99}]
                    response = self.post(execute=execute)
                    self.assertEqual(response.status_code, 200)
                    self.assertIn("已经创建", response.get_json()["data"]["response"])
                    self.assertNotIn("没有写入系统", response.get_json()["data"]["response"])
                    self.assertFalse(response.get_json()["data"]["session"]["has_pending"])
                    resume.assert_not_called()

    def test_checkpoint_disk_failure_after_commit_is_reconciled_before_cancellation(self):
        import os
        from unittest.mock import Mock
        caller = Mock()
        caller.call.side_effect = lambda name, **kwargs: self.products.get(kwargs["product_id"]) if name == "product_info" else None
        real_replace = os.replace
        replacements = 0

        def replace(source, destination):
            nonlocal replacements
            replacements += 1
            if replacements == 2:
                raise OSError("one-shot checkpoint failure")
            return real_replace(source, destination)

        with patch("src.skills.workflow_order.workflow.get_tool_caller", return_value=caller), \
                patch("src.services.business.workflow.get_workflow_service") as service, \
                patch("src.core.session.os.replace", side_effect=replace), \
                patch.object(http_api, "get_workflow_service") as lookup:
            service.return_value.find_saved_batch.return_value = []
            service.return_value.save_orders_batch.return_value = {"code": 0, "data": [{"id": 99}]}
            lookup.return_value.find_saved_batch.return_value = []
            self.assertEqual(self.post().status_code, 500)
            service.return_value.save_orders_batch.assert_called_once()
            lookup.return_value.find_saved_batch.return_value = [{"id": 99}]
            cancelled = self.post(execute="cancel")
            self.assertEqual(cancelled.status_code, 200)
            self.assertIn("已经创建", cancelled.get_json()["data"]["response"])
            self.assertNotIn("没有写入系统", cancelled.get_json()["data"]["response"])
            self.assertFalse(cancelled.get_json()["data"]["session"]["has_pending"])


if __name__ == "__main__":
    unittest.main()
