import io
import tempfile
import unittest
import zipfile
from contextlib import ExitStack, contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.channels import http_api
from src.engine.native_db import NativeDBClient
from src.services.business.products import ProductService
from src.skills.bag_upload.workflow import BagUploadWorkflow


def archive_bytes(size=3):
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("奇兰品种.png", b"x" * size)
    return out.getvalue()


class BagUploadDialogApiTest(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.stack.enter_context(patch.object(http_api, "UPLOAD_DIR", self.root))
        self.stack.enter_context(patch.object(http_api, "_current_web_user", return_value={"id": 1}))
        self.permission = self.stack.enter_context(patch.object(http_api, "_has_permission", return_value=True))
        self.feature = self.stack.enter_context(patch.object(http_api, "feature_enabled", return_value=True))
        self.session = self.stack.enter_context(patch("src.core.session.SessionManager"))
        self.agent = self.stack.enter_context(patch.object(http_api, "_agent"))
        self.stack.enter_context(patch.object(http_api.logger, "exception"))
        self.processor = self.stack.enter_context(patch.object(BagUploadWorkflow, "_process_batch_upload", return_value={
            "source": "/private/upload.zip", "bag_type": "岩茶", "price": 19.80, "is_listed": True,
            "total": 2,
            "success": [{"index": 1, "title": "【SJ9999】奇兰-长泡袋", "code": "SJ9999", "action": "新增",
                         "category_name": "品种茶泡袋", "price": 19.80, "is_listed": True,
                         "core_result": {"code": 0, "data": {"id": 88, "spu_id": 50}}}],
            "failures": [{"index": 2, "title": "failed", "error": "保存失败"}],
        }))
        self.client = http_api.app.test_client()

    def upload(self, **overrides):
        data = {"bag_type": "岩茶", "price": "19.80", "is_listed": "1", "archive": (io.BytesIO(archive_bytes()), "batch.zip")}
        data.update(overrides)
        return self.client.post("/api/product/bag-upload", data=data)

    def test_upload_is_independent_of_pending_and_returns_partial_results(self):
        response = self.upload()
        self.assertEqual(response.status_code, 200)
        data = response.get_json()["data"]
        self.assertEqual(data["price"], 19.80)
        self.assertTrue(data["is_listed"])
        self.assertEqual(data["total"], 2)
        self.assertEqual(data["success"][0]["product_id"], 88)
        self.assertEqual(data["success"][0]["spu_id"], 50)
        self.assertEqual(len(data["failures"]), 1)
        self.assertIn("成功 1", data["summary"])
        self.assertNotIn("/private", response.get_data(as_text=True))
        self.session.assert_not_called()
        self.agent.run.assert_not_called()
        self.assertEqual(list(self.root.iterdir()), [])
        options = self.processor.call_args.args[1]
        self.assertEqual(options["price"], 19.80)
        self.assertTrue(options["is_listed"])

    def test_invalid_form_values_are_rejected_before_processing(self):
        cases = [{"price": value} for value in ["", "0", "-1", "NaN", "Infinity", "1e2", "1.234", "10000000000"]]
        cases += [{"bag_type": "unknown"}, {"is_listed": "yes please"}, {"archive": (io.BytesIO(b"x"), "image.png")}]
        for invalid in cases:
            with self.subTest(invalid=invalid):
                self.assertEqual(self.upload(**invalid).status_code, 400)
        self.processor.assert_not_called()
        self.assertEqual(list(self.root.iterdir()), [])

    def test_missing_archive_and_invalid_zip_are_rejected(self):
        self.assertEqual(self.client.post("/api/product/bag-upload", data={"price": "18", "bag_type": "岩茶", "is_listed": "1"}).status_code, 400)
        self.assertEqual(self.upload(archive=(io.BytesIO(b"not a zip"), "bad.zip")).status_code, 400)
        self.processor.assert_not_called()
        self.assertEqual(list(self.root.iterdir()), [])

    def test_archive_security_checks_run_before_processing(self):
        for names in [["readme.txt"], [f"{index}.png" for index in range(101)]]:
            out = io.BytesIO()
            with zipfile.ZipFile(out, "w") as archive:
                for name in names:
                    archive.writestr(name, b"x")
            with self.subTest(count=len(names)):
                self.assertEqual(self.upload(archive=(io.BytesIO(out.getvalue()), "batch.zip")).status_code, 400)
        self.processor.assert_not_called()

    def test_login_is_required(self):
        with patch.object(http_api, "_current_web_user", return_value=None):
            response = self.upload()
        self.assertEqual(response.status_code, 401)
        self.processor.assert_not_called()

    def test_unlisted_and_all_templates_are_explicit_options(self):
        for template in ["岩茶", "红茶", "宽版"]:
            with self.subTest(template=template):
                response = self.upload(bag_type=template, is_listed="0", price="12.34")
                self.assertEqual(response.status_code, 200)
                options = self.processor.call_args.args[1]
                self.assertEqual(options["bag_type"], template)
                self.assertFalse(options["is_listed"])
                self.assertEqual(options["price"], 12.34)

    def test_product_and_image_permissions_and_feature_are_required(self):
        for denied in ["设置", "图片上传"]:
            with self.subTest(permission=denied):
                self.permission.side_effect = lambda name, *args, **kwargs: name != denied
                self.assertEqual(self.upload().status_code, 403)
        self.permission.side_effect = None
        self.feature.return_value = False
        self.assertEqual(self.upload().status_code, 403)
        self.processor.assert_not_called()

    def test_new_endpoint_accepts_archive_above_old_image_limit(self):
        self.assertEqual(self.upload(archive=(io.BytesIO(archive_bytes(26 * 1024 * 1024)), "large.zip")).status_code, 200)
        self.processor.assert_called_once()

    def test_new_endpoint_rejects_oversized_request_and_file(self):
        response = self.client.post("/api/product/bag-upload", environ_overrides={
            "CONTENT_LENGTH": str(102 * 1024 * 1024), "CONTENT_TYPE": "multipart/form-data; boundary=test", "wsgi.input": io.BytesIO(b""),
        })
        self.assertEqual(response.status_code, 413)
        self.assertIn("100", response.get_json()["msg"])
        with patch.object(http_api, "MAX_BAG_ARCHIVE_UPLOAD_BYTES", 4096):
            self.assertEqual(self.upload(archive=(io.BytesIO(archive_bytes(4097)), "large.zip")).status_code, 413)
        self.processor.assert_not_called()

    def test_processor_exception_cleans_upload_and_does_not_touch_pending(self):
        self.processor.side_effect = RuntimeError("renderer failed")
        response = self.upload()
        self.assertEqual(response.status_code, 500)
        self.assertEqual(list(self.root.iterdir()), [])
        self.session.assert_not_called()


class ProductListingTransactionTest(unittest.TestCase):
    def setUp(self):
        self.db = object.__new__(NativeDBClient)
        self.events = []
        self.cursor = MagicMock()
        self.cursor.lastrowid = 88
        self.cursor.fetchone.return_value = {"spu_id": 50, "sku_no": "SJ9999"}
        self.cursor.execute.side_effect = lambda sql, args=None: self.events.append((sql, args))

        @contextmanager
        def transaction():
            self.events.append(("BEGIN", None))
            try:
                yield self.cursor
                self.events.append(("COMMIT", None))
            except Exception:
                self.events.append(("ROLLBACK", None))
                raise

        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(self.db, "transaction", transaction))
        self.stack.enter_context(patch.object(self.db, "_ensure_number_sequence_tables"))
        self.stack.enter_context(patch.object(self.db, "_sku_no_available", return_value=True))
        self.stack.enter_context(patch.object(self.db, "resolve_sku_id", return_value=88))
        self.stack.enter_context(patch.object(self.db, "_default_is_stock_item_for_product", return_value=0))
        self.stack.enter_context(patch.object(self.db, "_replace_product_media"))

    def payload(self, existing=False, **extra):
        result = {"title": "奇兰", "status": 1, "product_type": "bubble_bag", "product_category_id": [19],
                  "base": {"88" if existing else "new_0": {"coding": "SJ9999", "unit": {"new_0": {"unit_id": 2, "price": 19.80}}}}, **extra}
        if existing:
            result["id"] = 88
        return result

    def test_listing_and_price_are_saved_in_same_transaction(self):
        for existing in [False, True]:
            for listed in [False, True]:
                with self.subTest(existing=existing, listed=listed):
                    self.events.clear()
                    result = self.db.save_product(self.payload(existing, is_listed=listed))
                    self.assertEqual(result["code"], 0)
                    listing_writes = [(sql, args) for sql, args in self.events if "UPDATE product_sku" in sql and "is_listed" in sql]
                    self.assertEqual(len(listing_writes), 1)
                    sql, args = listing_writes[0]
                    self.assertEqual(args[0], int(listed))
                    self.assertIn("active", sql)
                    self.assertTrue(any(19.80 in args for sql, args in self.events if args and "retail_price" in sql))
                    self.assertEqual(self.events[0][0], "BEGIN")
                    self.assertEqual(self.events[-1][0], "COMMIT")

    def test_old_callers_without_listing_option_do_not_change_it(self):
        self.assertEqual(self.db.save_product(self.payload(existing=True))["code"], 0)
        self.assertFalse(any("is_listed" in sql for sql, _ in self.events))

    def test_invalid_listing_option_is_rejected_before_transaction(self):
        for value in [None, "false", "true", 2, -1, "anything"]:
            with self.subTest(value=value):
                self.assertEqual(self.db.save_product(self.payload(is_listed=value))["code"], 400)
        self.assertEqual(self.events, [])

    def test_listing_failure_rolls_back_entire_product_save(self):
        def execute(sql, args=None):
            self.events.append((sql, args))
            if "UPDATE product_sku" in sql and "is_listed" in sql:
                raise RuntimeError("listing write failed")
        self.cursor.execute.side_effect = execute
        with self.assertRaisesRegex(RuntimeError, "listing write failed"):
            self.db.save_product(self.payload(is_listed=True))
        self.assertEqual(self.events[-1][0], "ROLLBACK")
        self.assertNotIn(("COMMIT", None), self.events)

    def test_upload_lookup_can_include_inactive_without_changing_default_or_public_search(self):
        db = object.__new__(NativeDBClient)
        with patch.object(db, "query", return_value=[]) as query:
            ProductService(db).search("SJ1737", active_only=False)
            sql = query.call_args.args[0]
            self.assertNotIn("s.status = 'active'", sql)
            self.assertIn("s.deleted_at IS NULL", sql)
            ProductService(db).search("SJ1737")
            self.assertIn("s.status = 'active'", query.call_args.args[0])
            ProductService(db).search("SJ1737", active_only=False, listed_only=True)
            self.assertIn("s.status = 'active'", query.call_args.args[0])
            self.assertIn("s.is_listed = 1", query.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
