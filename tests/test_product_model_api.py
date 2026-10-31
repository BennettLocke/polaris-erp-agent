import io
import unittest
import tempfile
from pathlib import Path
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

from src.channels import http_api
from tests.test_product_models import glb


class ProductModelEndpointTest(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.stack.enter_context(patch.object(http_api, "UPLOAD_DIR", self.root))
        self.user = self.stack.enter_context(patch.object(http_api, "_current_web_user", return_value={"id": 7}))
        self.permission = self.stack.enter_context(patch.object(http_api, "_has_permission", return_value=True))
        self.service = MagicMock()
        self.asset = {"id": 9, "url": "https://assets.example/model.glb", "file_name": "盒子.glb", "byte_size": len(glb()), "animation_count": 0, "materials": []}
        self.service.record_model_asset.return_value = self.asset
        self.stack.enter_context(patch("src.channels.http_api.product_models.get_product_service", return_value=self.service))
        self.upload = self.stack.enter_context(patch("src.services.business.product_models.upload_model_file", return_value={"url": self.asset["url"], "path": "product_models/20261030/" + "a" * 32 + ".glb"}))
        self.cleanup = self.stack.enter_context(patch("src.services.business.product_models.cleanup_model_object", return_value=True))
        self.client = http_api.app.test_client()

    def post(self, content=None, filename="盒子.glb"):
        return self.client.post("/api/product/models/upload", data={"model": (io.BytesIO(glb() if content is None else content), filename)})

    def test_model_upload_has_a_dedicated_endpoint(self):
        response = self.post(b"invalid", "bad.glb")
        self.assertEqual(response.status_code, 400)
        self.upload.assert_not_called()

    def test_valid_upload_registers_metadata_and_always_removes_local_file(self):
        response = self.post()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["data"]["id"], 9)
        metadata = self.service.record_model_asset.call_args.args[0]
        self.assertEqual(metadata["file_name"], "盒子.glb")
        self.assertEqual(metadata["byte_size"], len(glb()))
        self.assertEqual(self.service.record_model_asset.call_args.kwargs["operator_user_id"], 7)
        self.assertEqual(len(metadata["sha256"]), 64)
        self.assertEqual(list(self.root.iterdir()), [])
        self.cleanup.assert_not_called()

    def test_database_failures_reclaim_this_upload_without_success(self):
        for error in (RuntimeError("database failed"), ValueError("保存失败")):
            with self.subTest(error=type(error)):
                self.service.record_model_asset.side_effect = error
                response = self.post()
                self.assertNotEqual(response.get_json()["code"], 0)
                self.assertTrue(self.cleanup.called)
                self.assertEqual(list(self.root.iterdir()), [])

    def test_local_cleanup_failure_after_registration_never_deletes_committed_asset(self):
        real_temporary_directory = tempfile.TemporaryDirectory

        class FailingCleanup:
            def __init__(self, *args, **kwargs):
                self.directory = real_temporary_directory(*args, **kwargs)
            def __enter__(self):
                return self.directory.__enter__()
            def __exit__(self, *args):
                self.directory.__exit__(*args)
                raise OSError('injected local cleanup error')

        with patch('src.channels.http_api.product_models.tempfile.TemporaryDirectory', FailingCleanup):
            response = self.post()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['data']['id'], 9)
        self.cleanup.assert_not_called()

    def test_oss_failure_does_not_register_asset(self):
        self.upload.side_effect = ValueError("模型上传失败")
        self.assertEqual(self.post().status_code, 400)
        self.service.record_model_asset.assert_not_called()
        self.assertEqual(list(self.root.iterdir()), [])

    def test_missing_empty_wrong_extension_oversized_and_malformed_are_rejected(self):
        self.assertEqual(self.client.post("/api/product/models/upload").status_code, 400)
        for content, filename in [(b"", "a.glb"), (glb(), "a.blend"), (b"broken", "a.glb")]:
            self.assertEqual(self.post(content, filename).status_code, 400)
        with patch.object(http_api, "MAX_MODEL_UPLOAD_BYTES", 128):
            self.assertEqual(self.post().status_code, 413)
        response = self.client.post("/api/product/models/upload", environ_overrides={
            "CONTENT_LENGTH": str(52 * 1024 * 1024), "CONTENT_TYPE": "multipart/form-data; boundary=test", "wsgi.input": io.BytesIO(b""),
        })
        self.assertEqual(response.status_code, 413)
        self.assertIn("50", response.get_json()["msg"])
        self.assertEqual(list(self.root.iterdir()), [])
        self.upload.assert_not_called()

    def test_anonymous_and_permission_denials_do_not_upload(self):
        self.user.return_value = None
        self.assertEqual(self.post().status_code, 401)
        self.user.return_value = {"id": 7}
        for denied in ("设置", "图片上传"):
            self.permission.side_effect = lambda permission: permission != denied
            self.assertEqual(self.post().status_code, 403)
        self.upload.assert_not_called()

    def test_pending_cleanup_claims_database_before_deleting_storage(self):
        self.service.delete_pending_model_asset.return_value = {"oss_key": self.upload.return_value["path"]}
        events = []
        self.service.delete_pending_model_asset.side_effect = lambda *args, **kwargs: events.append("claim") or {"oss_key": self.upload.return_value["path"]}
        self.cleanup.side_effect = lambda *args: events.append("oss") or True
        response = self.client.delete("/api/product/models/9/pending")
        self.assertEqual(response.get_json()["code"], 0)
        self.assertEqual(events, ["claim", "oss"])
        self.service.delete_pending_model_asset.assert_called_once_with(9, operator_user_id=7)

    def test_bound_or_foreign_asset_cannot_be_cleaned(self):
        self.service.delete_pending_model_asset.side_effect = ValueError("不能删除已绑定模型")
        self.assertEqual(self.client.delete("/api/product/models/9/pending").status_code, 400)
        self.cleanup.assert_not_called()

    def test_product_save_forwards_actor_only_for_model_updates(self):
        with patch.object(http_api, "get_product_service", return_value=self.service):
            self.service.save.return_value = {"code": 0, "data": {"id": 8}}
            self.assertEqual(self.client.post("/api/product/save", json={"title": "盒子", "model_asset_id": 9}).status_code, 200)
            self.service.save.assert_called_with({"title": "盒子", "model_asset_id": 9}, operator_user_id=7)
            self.client.post("/api/product/save", json={"title": "盒子"})
            self.service.save.assert_called_with({"title": "盒子"})
            self.service.save.side_effect = ValueError("该模型属于其他商品")
            self.assertEqual(self.client.post("/api/product/save", json={"title": "盒子", "model_asset_id": 9}).status_code, 400)


if __name__ == "__main__":
    unittest.main()
