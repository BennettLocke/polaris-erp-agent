import io
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from src.channels import http_api


def _recognized_item(name: str, customer: str = "齐唯茶业") -> dict:
    return {
        "parsed": {
            "customer_name": customer,
            "goods_name": name,
            "color": "红色",
            "quantity": 2,
            "unit": "套",
        },
        "workflow_order_payload": {
            "customer": customer,
            "goods_name": name,
            "color": "红色",
            "quantity": 2,
        },
    }


class ImageUploadBatchTest(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.tmp = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.session_dir = self.tmp / "sessions"
        self.stack.enter_context(patch.object(http_api, "UPLOAD_DIR", self.tmp / "uploads"))
        self.stack.enter_context(patch("src.core.session.HISTORY_DIR", self.session_dir))
        self.stack.enter_context(patch.object(http_api, "_validate_saved_image"))
        self.stack.enter_context(patch.object(http_api, "_current_web_user", return_value={"id": 1}))
        self.stack.enter_context(patch.object(http_api, "_has_permission", return_value=True))
        self.client = http_api.app.test_client()

    @staticmethod
    def _files(count=2):
        return [(io.BytesIO(f"image-{index}".encode()), f"design-{index}.png") for index in range(count)]

    def _post(self, *, batch_id="batch-001", count=2):
        return self.client.post(
            "/api/images/upload-batch",
            data={
                "session_id": "batch-session",
                "batch_id": batch_id,
                "images": self._files(count),
            },
            content_type="multipart/form-data",
        )

    def test_upload_limits_expose_batch_size_and_file_count(self):
        response = self.client.get("/api/images/upload-limits")

        self.assertEqual(response.status_code, 200)
        limits = response.get_json()["data"]
        self.assertEqual(limits["image_batch_files"], 6)
        self.assertEqual(limits["image_batch_bytes"], 100 * 1024 * 1024)

    @patch("src.core.nodes.image_workflow.process_image_batch")
    @patch.object(http_api, "_handle_image_auto_workflow_sales_flow", return_value="批次处理完成")
    def test_multiple_images_are_processed_once_and_create_one_sales_flow(self, handle_flow, process_batch):
        items = [_recognized_item("喜悦半斤"), _recognized_item("岩味三两")]
        process_batch.return_value = {
            "items": items,
            "files": [
                {"image_path": "one", "status": "success", "error": "", "result": items[0]},
                {"image_path": "two", "status": "success", "error": "", "result": items[1]},
            ],
            "total_files": 2,
            "success_files": 2,
            "failed_files": 0,
            "incomplete": False,
        }

        response = self._post()

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()["data"]
        self.assertEqual(payload["batch"]["total_files"], 2)
        self.assertEqual(len(payload["batch"]["files"]), 2)
        process_batch.assert_called_once()
        self.assertEqual(handle_flow.call_count, 1)
        self.assertTrue(handle_flow.call_args.kwargs["allow_sales"])

    @patch("src.core.nodes.image_workflow.process_image_batch")
    @patch.object(http_api, "_handle_image_auto_workflow_sales_flow", return_value="部分识别失败")
    def test_incomplete_batch_keeps_workflows_but_disables_sales_confirmation(self, handle_flow, process_batch):
        item = _recognized_item("喜悦半斤")
        process_batch.return_value = {
            "items": [item, {"parsed": {}, "error": "未识别到礼盒名称"}],
            "files": [
                {"image_path": "one", "status": "success", "error": "", "result": item},
                {"image_path": "two", "status": "failed", "error": "未识别到礼盒名称", "result": {"error": "未识别到礼盒名称"}},
            ],
            "total_files": 2,
            "success_files": 1,
            "failed_files": 1,
            "incomplete": True,
        }

        response = self._post(batch_id="batch-incomplete")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(handle_flow.call_args.kwargs["allow_sales"])
        self.assertEqual(response.get_json()["data"]["batch"]["failed_files"], 1)

    @patch("src.core.nodes.image_workflow.process_image_batch")
    @patch.object(http_api, "_handle_image_auto_workflow_sales_flow", return_value="批次处理完成")
    def test_repeated_batch_id_does_not_process_or_create_orders_twice(self, _handle_flow, process_batch):
        item = _recognized_item("喜悦半斤")
        process_batch.return_value = {
            "items": [item],
            "files": [{"image_path": "one", "status": "success", "error": "", "result": item}],
            "total_files": 1,
            "success_files": 1,
            "failed_files": 0,
            "incomplete": False,
        }

        first = self._post(batch_id="same-batch", count=1)
        second = self._post(batch_id="same-batch", count=1)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.get_json()["data"]["batch"]["replayed"])
        process_batch.assert_called_once()

    def test_batch_rejects_more_than_six_images(self):
        response = self._post(batch_id="too-many", count=7)

        self.assertEqual(response.status_code, 400)
        self.assertIn("6", response.get_json()["msg"])


if __name__ == "__main__":
    unittest.main()
