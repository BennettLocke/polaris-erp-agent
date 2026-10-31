"""Model persistence tests using NativeDBClient's real transaction boundary."""

import copy
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock

from src.engine.exceptions import DBError
from src.engine.native_db import NativeDBClient


ROOT = Path(__file__).resolve().parents[1]


class ModelConnection:
    def __init__(self):
        self.state = {"assets": {}, "bindings": {}, "spus": {10: "Original"}, "skus": {20: 10}, "deleted_spus": set()}
        self.statements = []
        self.commits = 0
        self.rollbacks = 0
        self.autocommit_value = True
        self.fail_sku_write = False

    def get_autocommit(self):
        return self.autocommit_value

    def autocommit(self, value):
        if not value:
            self.snapshot = copy.deepcopy(self.state)
        self.autocommit_value = value

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1
        self.state = self.snapshot

    def cursor(self):
        return ModelCursor(self)


class ModelCursor:
    def __init__(self, connection):
        self.connection = connection
        self.rows = []
        self.lastrowid = 0
        self.rowcount = 0

    def execute(self, sql, params=()):
        sql = " ".join(sql.split())
        params = tuple(params)
        self.connection.statements.append((sql, params))
        state = self.connection.state
        self.rows = []
        self.rowcount = 1
        if sql.startswith("INSERT INTO product_model_asset"):
            columns = sql.split("(", 1)[1].split(")", 1)[0].replace(" ", "").split(",")
            asset_id = max(state["assets"], default=0) + 1
            row = dict(zip(columns, params))
            row.update(id=asset_id, origin_spu_id=None, deleted_at=None)
            state["assets"][asset_id] = row
            self.lastrowid = asset_id
        elif "FROM product_model_asset" in sql:
            if "JOIN product_model_binding" in sql:
                asset_id = state["bindings"].get(params[0])
            else:
                asset_id = params[0]
            row = state["assets"].get(asset_id)
            if "JOIN product_spu" in sql and params[0] in state["deleted_spus"]:
                row = None
            if row and ("deleted_at IS NULL" not in sql or row["deleted_at"] is None):
                self.rows = [copy.deepcopy(row)]
        elif sql.startswith("SELECT") and "FROM product_model_binding" in sql:
            if "model_asset_id=%s" in sql:
                self.rows = [{"spu_id": spu, "model_asset_id": asset} for spu, asset in state["bindings"].items() if asset == params[0]]
            else:
                asset = state["bindings"].get(params[0])
                self.rows = [{"spu_id": params[0], "model_asset_id": asset}] if asset else []
        elif sql.startswith("UPDATE product_model_asset"):
            row = state["assets"][params[-1]]
            if "SET origin_spu_id=" in sql:
                row["origin_spu_id"], row["updated_at"] = params[:2]
            else:
                row["deleted_at"], row["updated_at"] = params[:2]
        elif sql.startswith("INSERT INTO product_model_binding"):
            spu, asset = params[:2]
            if asset in state["bindings"].values() and state["bindings"].get(spu) != asset:
                raise AssertionError("unique asset binding violated")
            state["bindings"][spu] = asset
        elif sql.startswith("DELETE FROM product_model_binding"):
            for spu_id in params:
                state["bindings"].pop(spu_id, None)
        elif sql.startswith("SELECT id FROM product_spu"):
            self.rows = [{"id": spu_id} for spu_id in sorted(params)
                         if spu_id in state["spus"] and spu_id not in state["deleted_spus"]]
        elif sql.startswith("SELECT id FROM product_sku WHERE spu_id IN"):
            self.rows = [{"id": sku} for sku, spu in state["skus"].items() if spu in params]
        elif sql.startswith("SELECT spu_id FROM product_sku"):
            self.rows = [{"spu_id": state["skus"][params[0]]}]
        elif sql.startswith("SELECT sku_no FROM product_sku"):
            self.rows = [{"sku_no": "SJ0020"}]
        elif sql.startswith("INSERT INTO product_spu"):
            self.lastrowid = max(state["spus"], default=0) + 1
            state["spus"][self.lastrowid] = params[0]
        elif sql.startswith("UPDATE product_spu SET title="):
            state["spus"][params[-1]] = params[0]
        elif sql.startswith("UPDATE product_spu SET available_colors="):
            pass
        elif sql.startswith("UPDATE product_spu SET deleted_at="):
            state["deleted_spus"].update(params[2:])
        elif sql.startswith(("INSERT INTO product_sku", "UPDATE product_sku")):
            if self.connection.fail_sku_write:
                raise RuntimeError("simulated SKU write failure")
            if sql.startswith("INSERT"):
                self.lastrowid = max(state["skus"], default=0) + 1
                state["skus"][self.lastrowid] = params[0]
        else:
            raise AssertionError(f"unexpected SQL: {sql}")
        return self.rowcount

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows

    def close(self):
        pass


class LockingModelConnection(ModelConnection):
    """Two fake sessions share rows and enforce the production row-lock order."""

    def __init__(self, state, locks, before_lock=None, after_lock=None):
        super().__init__()
        self.state = state
        self.locks = locks
        self.held = set()
        self.before_lock = before_lock or (lambda _key: None)
        self.after_lock = after_lock or (lambda _key: None)

    def acquire(self, key):
        if key in self.held:
            return
        self.before_lock(key)
        if not self.locks[key].acquire(timeout=3):
            raise AssertionError(f"fake row-lock timeout: {key}")
        self.held.add(key)
        self.after_lock(key)

    def autocommit(self, value):
        super().autocommit(value)
        if value:
            for key in self.held:
                self.locks[key].release()
            self.held.clear()

    def cursor(self):
        return LockingModelCursor(self)


class LockingModelCursor(ModelCursor):
    def execute(self, sql, params=()):
        normalized = " ".join(sql.split())
        if normalized.startswith("UPDATE product_spu SET title="):
            self.connection.acquire(("spu", params[-1]))
        elif "FROM product_spu" in normalized and "FOR UPDATE" in normalized:
            for spu_id in sorted(params):
                self.connection.acquire(("spu", spu_id))
        elif "FROM product_model_asset" in normalized and "FOR UPDATE" in normalized:
            self.connection.acquire(("asset", params[0]))
        return super().execute(sql, params)


class NativeProductModelsTest(unittest.TestCase):
    def setUp(self):
        self.client = object.__new__(NativeDBClient)
        self.connection = ModelConnection()
        self.client._get_connection = lambda: self.connection
        self.client._ensure_number_sequence_tables = lambda: None
        self.client.resolve_sku_id = lambda sku_id, **_kwargs: sku_id
        self.client._next_sku_no = lambda *_args, **_kwargs: "SJ0021"
        self.client._default_is_stock_item_for_product = lambda *_args: 1
        self.client._replace_product_media = lambda *_args, **_kwargs: None
        self.metadata = {
            "oss_key": "product-models/random.glb", "url": "https://img.example/model.glb",
            "file_name": "model.glb", "byte_size": 1234, "sha256": "a" * 64,
            "animation_count": 2, "materials": [{"name": "Paper"}],
        }

    def record(self, owner=7):
        return self.client.record_product_model_asset(self.metadata, owner)

    def save(self, asset_id, actor=7, **payload):
        return self.client.save_product(
            {"id": 20, "title": "Updated", "base": {"20": {"spec": "Red"}}, "model_asset_id": asset_id, **payload},
            operator_user_id=actor,
        )

    def test_record_and_lookup_return_metadata_and_materials_list(self):
        asset = self.record()
        self.assertEqual(asset["byte_size"], 1234)
        self.assertEqual(asset["materials"], self.metadata["materials"])
        self.assertEqual(asset["uploaded_by"], 7)
        self.assertIsNone(asset["origin_spu_id"])
        self.assertEqual(self.client.product_model_asset(asset["id"]), asset)
        self.assertIsNone(self.client.product_model_asset(999))
        self.assertFalse(any("CREATE TABLE" in sql for sql, _ in self.connection.statements))

    def test_record_does_not_accept_origin_or_upload_owner_from_metadata(self):
        self.metadata.update(origin_spu_id=99, uploaded_by=99)
        asset = self.record()
        self.assertEqual(asset["uploaded_by"], 7)
        self.assertIsNone(asset["origin_spu_id"])

    def test_record_rejects_invalid_metadata_and_missing_actor_before_writes(self):
        for field, value in (("byte_size", True), ("byte_size", 0), ("materials", {}),
                             ("animation_count", -1), ("sha256", "bad"), ("oss_key", "")):
            with self.subTest(field=field, value=value):
                with self.assertRaises(ValueError):
                    self.client.record_product_model_asset({**self.metadata, field: value}, 7)
        for actor in (None, True, 0):
            with self.subTest(actor=actor):
                with self.assertRaises(ValueError):
                    self.record(actor)
        self.assertEqual(self.connection.statements, [])

    def test_save_binds_once_for_all_spu_colors(self):
        asset = self.record()
        result = self.save(asset["id"])
        self.assertEqual(result["code"], 0)
        self.assertEqual(self.connection.state["bindings"], {10: asset["id"]})
        model = self.client.product_model_for_spu(10)
        self.assertEqual(model["id"], asset["id"])
        self.assertEqual(model["origin_spu_id"], 10)
        locks = [sql for sql, _ in self.connection.statements if "FOR UPDATE" in sql]
        self.assertTrue(any("product_model_asset" in sql for sql in locks))

    def test_binding_locks_live_spu_before_asset_without_binding_gap_lock(self):
        asset = self.record()
        self.connection.statements.clear()
        self.save(asset["id"])
        locks = [sql for sql, _ in self.connection.statements if "FOR UPDATE" in sql]
        self.assertIn("FROM product_spu", locks[0])
        self.assertIn("deleted_at IS NULL", locks[0])
        self.assertIn("FROM product_model_asset", locks[1])
        self.assertFalse(any("FROM product_model_binding" in sql for sql in locks))

    def test_deleted_spu_cannot_be_bound_even_if_sku_resolution_is_stale(self):
        asset = self.record()
        self.connection.state["deleted_spus"].add(10)
        before = copy.deepcopy(self.connection.state)
        with self.assertRaisesRegex(ValueError, "商品不存在或已删除"):
            self.save(asset["id"])
        self.assertEqual(self.connection.state, before)

    def test_model_lookup_hides_deleted_spu(self):
        asset = self.record()
        self.save(asset["id"])
        self.connection.state["deleted_spus"].add(10)
        self.assertIsNone(self.client.product_model_for_spu(10))

    def test_product_delete_removes_binding_but_retains_origin(self):
        asset = self.record()
        self.save(asset["id"])
        self.client._product_spu_ids_from_inputs = lambda *_args: ([10], [20])
        self.connection.statements.clear()
        result = self.client.delete_product([20])
        self.assertEqual(result["code"], 0)
        self.assertEqual(self.connection.state["bindings"], {})
        self.assertEqual(self.connection.state["deleted_spus"], {10})
        self.assertEqual(self.client.product_model_asset(asset["id"])["origin_spu_id"], 10)
        first_lock = next(sql for sql, _ in self.connection.statements if "FOR UPDATE" in sql)
        self.assertIn("FROM product_spu", first_lock)

    def test_concurrent_same_spu_replacements_serialize_without_losing_origins(self):
        first = self.record()
        self.metadata["oss_key"] = "product-models/second.glb"
        second = self.record()
        locks = {("spu", 10): threading.Lock(), ("asset", first["id"]): threading.Lock(),
                 ("asset", second["id"]): threading.Lock()}
        first_has_asset = threading.Event()
        release_first = threading.Event()
        second_waiting_for_spu = threading.Event()

        def hold_first(key):
            if key == ("asset", first["id"]):
                first_has_asset.set()
                if not release_first.wait(timeout=3):
                    raise AssertionError("test did not release first replacement")

        def observe_second(key):
            if key == ("spu", 10):
                second_waiting_for_spu.set()

        first_conn = LockingModelConnection(self.connection.state, locks, after_lock=hold_first)
        second_conn = LockingModelConnection(self.connection.state, locks, before_lock=observe_second)

        def replacement(connection, asset_id):
            client = object.__new__(NativeDBClient)
            client.__dict__.update(self.client.__dict__)
            client._get_connection = lambda: connection
            return client.save_product({"id": 20, "title": "Updated", "model_asset_id": asset_id},
                                       operator_user_id=7)

        with ThreadPoolExecutor(max_workers=2) as pool:
            one = pool.submit(replacement, first_conn, first["id"])
            try:
                self.assertTrue(first_has_asset.wait(timeout=3))
                two = pool.submit(replacement, second_conn, second["id"])
                self.assertTrue(second_waiting_for_spu.wait(timeout=3))
                self.assertFalse(two.done())
            finally:
                release_first.set()
            self.assertEqual(one.result(timeout=3)["code"], 0)
            self.assertEqual(two.result(timeout=3)["code"], 0)
        self.assertEqual(self.connection.state["bindings"], {10: second["id"]})
        self.assertEqual(self.connection.state["assets"][first["id"]]["origin_spu_id"], 10)
        self.assertEqual(self.connection.state["assets"][second["id"]]["origin_spu_id"], 10)
        self.assertEqual((first_conn.rollbacks, second_conn.rollbacks), (0, 0))

    def test_same_spu_editor_can_rebind_but_origin_is_never_rewritten(self):
        asset = self.record()
        self.save(asset["id"])
        origin_writes = sum("SET origin_spu_id=" in sql for sql, _ in self.connection.statements)
        self.save(asset["id"], actor=99)
        self.save(None, actor=99)
        self.save(asset["id"], actor=99)
        self.assertEqual(self.connection.state["bindings"], {10: asset["id"]})
        self.assertEqual(sum("SET origin_spu_id=" in sql for sql, _ in self.connection.statements), origin_writes)

    def test_omitted_keeps_binding_and_null_unbind_retains_origin(self):
        asset = self.record()
        self.save(asset["id"])
        self.client.save_product({"id": 20, "title": "Legacy"})
        self.assertEqual(self.connection.state["bindings"], {10: asset["id"]})
        self.save(None)
        self.assertEqual(self.connection.state["bindings"], {})
        self.assertIsNone(self.client.product_model_for_spu(10))
        self.assertEqual(self.client.product_model_asset(asset["id"])["origin_spu_id"], 10)

    def test_cross_spu_is_rejected_even_after_unbinding_and_rolls_back_product(self):
        asset = self.record()
        self.save(asset["id"])
        self.save(None)
        before = copy.deepcopy(self.connection.state)
        commits = self.connection.commits
        with self.assertRaises(ValueError):
            self.save(asset["id"], id=None)
        self.assertEqual(self.connection.state, before)
        self.assertEqual(self.connection.commits, commits)
        self.assertEqual(self.connection.rollbacks, 1)

    def test_currently_bound_asset_cannot_move_to_another_spu(self):
        asset = self.record()
        self.save(asset["id"])
        before = copy.deepcopy(self.connection.state)
        with self.assertRaises(ValueError):
            self.save(asset["id"], id=None)
        self.assertEqual(self.connection.state, before)

    def test_staged_asset_requires_actual_uploader(self):
        asset = self.record()
        for actor in (None, 99, True):
            with self.subTest(actor=actor):
                before = copy.deepcopy(self.connection.state)
                with self.assertRaises(ValueError):
                    self.save(asset["id"], actor=actor)
                self.assertEqual(self.connection.state, before)

    def test_save_requires_strict_positive_integer_asset_id(self):
        for value in (True, False, 0, -1, 1.0, "1", "https://example/model.glb", {}, []):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.save(value)

    def test_missing_asset_rolls_back_new_spu(self):
        before = copy.deepcopy(self.connection.state)
        with self.assertRaises(ValueError):
            self.save(999, id=None)
        self.assertEqual(self.connection.state, before)

    def test_later_write_failure_rolls_back_binding_and_origin(self):
        asset = self.record()
        before = copy.deepcopy(self.connection.state)
        self.connection.fail_sku_write = True
        with self.assertRaisesRegex(RuntimeError, "SKU write"):
            self.save(asset["id"])
        self.assertEqual(self.connection.state, before)
        self.assertEqual(self.connection.rollbacks, 1)

    def test_replacing_model_keeps_old_asset_origin(self):
        first = self.record()
        self.save(first["id"])
        self.metadata["oss_key"] = "product-models/second.glb"
        second = self.record()
        self.save(second["id"])
        self.assertEqual(self.connection.state["bindings"], {10: second["id"]})
        self.assertEqual(self.client.product_model_asset(first["id"])["origin_spu_id"], 10)

    def test_failed_replacement_preserves_old_binding_and_new_asset_staging(self):
        first = self.record()
        self.save(first["id"])
        self.metadata["oss_key"] = "product-models/second.glb"
        second = self.record()
        before = copy.deepcopy(self.connection.state)
        self.connection.fail_sku_write = True
        with self.assertRaisesRegex(RuntimeError, "SKU write"):
            self.save(second["id"])
        self.assertEqual(self.connection.state, before)
        self.assertEqual(self.connection.state["bindings"], {10: first["id"]})
        self.assertIsNone(self.connection.state["assets"][second["id"]]["origin_spu_id"])

    def test_pending_delete_claim_commits_tombstone_before_returning_oss_key(self):
        asset = self.record()
        claimed = self.client.delete_pending_product_model_asset(asset["id"], 7)
        self.assertEqual(claimed["oss_key"], self.metadata["oss_key"])
        self.assertIsNotNone(claimed["deleted_at"])
        self.assertEqual(self.connection.commits, 2)
        self.assertTrue(any("product_model_asset" in sql and "FOR UPDATE" in sql for sql, _ in self.connection.statements))
        self.assertIsNone(self.client.product_model_asset(asset["id"]))
        with self.assertRaises(ValueError):
            self.save(asset["id"])
        self.assertEqual(self.client.delete_pending_product_model_asset(asset["id"], 7), claimed)

    def test_storage_cleanup_failure_can_retry_without_rewriting_tombstone(self):
        asset = self.record()
        cleanup_storage = Mock(side_effect=[False, True])
        first = self.client.delete_pending_product_model_asset(asset["id"], operator_user_id=7)
        self.assertFalse(cleanup_storage(first["oss_key"]))
        before_retry = copy.deepcopy(self.connection.state)
        self.connection.statements.clear()
        retry = self.client.delete_pending_product_model_asset(asset["id"], operator_user_id=7)
        self.assertTrue(cleanup_storage(retry["oss_key"]))
        self.assertEqual(retry, first)
        self.assertEqual(self.connection.state, before_retry)
        self.assertFalse(any(sql.startswith("UPDATE") for sql, _ in self.connection.statements))
        self.assertEqual(cleanup_storage.call_count, 2)
        self.assertEqual(self.connection.commits, 3)
        self.assertIsNone(self.client.product_model_asset(asset["id"]))
        with self.assertRaises(ValueError):
            self.save(asset["id"])

    def test_tombstone_retry_still_requires_owner_never_bound_and_no_binding(self):
        asset = self.record()
        self.client.delete_pending_product_model_asset(asset["id"], operator_user_id=7)
        tombstone = copy.deepcopy(self.connection.state)
        for actor in (None, 99, True):
            with self.subTest(actor=actor):
                with self.assertRaises(ValueError):
                    self.client.delete_pending_product_model_asset(asset["id"], operator_user_id=actor)
                self.assertEqual(self.connection.state, tombstone)
        self.connection.state["assets"][asset["id"]]["origin_spu_id"] = 10
        with self.assertRaises(ValueError):
            self.client.delete_pending_product_model_asset(asset["id"], operator_user_id=7)
        self.connection.state["assets"][asset["id"]]["origin_spu_id"] = None
        self.connection.state["bindings"][10] = asset["id"]
        with self.assertRaises(ValueError):
            self.client.delete_pending_product_model_asset(asset["id"], operator_user_id=7)

    def test_facade_keyword_calls_and_chinese_errors(self):
        asset = self.client.record_product_model_asset(self.metadata, operator_user_id=7)
        claimed = self.client.delete_pending_product_model_asset(asset["id"], operator_user_id=7)
        self.assertEqual(claimed["id"], asset["id"])
        for operation in (lambda: self.save("1"), lambda: self.save(asset["id"]),
                          lambda: self.record(None),
                          lambda: self.client.delete_pending_product_model_asset(999, operator_user_id=7)):
            with self.subTest(operation=operation):
                with self.assertRaises(ValueError) as error:
                    operation()
                self.assertRegex(str(error.exception), r"[\u4e00-\u9fff]")

    def test_delete_still_checks_binding_when_origin_is_inconsistent(self):
        asset = self.record()
        self.connection.state["bindings"][10] = asset["id"]
        with self.assertRaises(ValueError):
            self.client.delete_pending_product_model_asset(asset["id"], 7)
        self.assertIsNone(self.connection.state["assets"][asset["id"]]["deleted_at"])

    def test_delete_rejects_wrong_owner_bound_and_previously_bound_assets(self):
        asset = self.record()
        for actor in (None, 99, True):
            with self.subTest(actor=actor):
                with self.assertRaises(ValueError):
                    self.client.delete_pending_product_model_asset(asset["id"], actor)
        self.save(asset["id"])
        with self.assertRaises(ValueError):
            self.client.delete_pending_product_model_asset(asset["id"], 7)
        self.save(None)
        with self.assertRaises(ValueError):
            self.client.delete_pending_product_model_asset(asset["id"], 7)
        self.assertIsNone(self.client.product_model_asset(asset["id"])["deleted_at"])

    def test_product_info_has_model_but_search_has_no_model_queries(self):
        row = {"id": 20, "spu_id": 10}
        self.client.query = Mock(return_value=[row])
        self.client._row_to_product = lambda item: dict(item)
        self.client.product_model_for_spu = Mock(return_value={"id": 5, "materials": []})
        product = self.client.product_info(20)
        self.assertEqual(product["model"]["id"], 5)
        self.client.product_model_for_spu.assert_called_once_with(10)
        self.client.product_model_for_spu.reset_mock()
        self.client.product_search("box")
        self.client.product_model_for_spu.assert_not_called()
        self.client.query = Mock(return_value=[])
        self.client.product_list(group=False)
        self.client.product_list(group=True)
        self.client.product_model_for_spu.assert_not_called()

    def test_product_options_group_inherits_detail_model(self):
        row = {"id": 20, "spu_id": 10, "color": "Red"}
        self.client.query = Mock(return_value=[row])
        self.client._row_to_product = lambda item: dict(item)
        self.client.product_model_for_spu = Mock(return_value={"id": 5, "materials": []})
        self.client.product_categories = lambda: []
        self.client.product_manufacturers = lambda **_kwargs: []
        self.client.product_media_assets = lambda **_kwargs: []
        self.client.product_list = lambda **_kwargs: ([], 0)
        options = self.client.product_options(20)
        self.assertEqual(options["data"]["model"]["id"], 5)
        self.assertEqual(options["data"]["spec_count"], 1)
        self.client.product_model_for_spu.assert_called_once_with(10)

    def test_missing_schema_is_not_silently_treated_as_no_model(self):
        self.client.query = Mock(side_effect=DBError("table does not exist"))
        with self.assertRaises(DBError):
            self.client.product_model_for_spu(10)

    def test_schema_has_origin_tombstone_and_unique_spu_asset_binding(self):
        schema = (ROOT / "database/schema/005_product_models.sql").read_text(encoding="utf-8")
        self.assertIn("CREATE TABLE IF NOT EXISTS product_model_asset", schema)
        self.assertIn("CREATE TABLE IF NOT EXISTS product_model_binding", schema)
        self.assertIn("origin_spu_id BIGINT UNSIGNED NULL", schema)
        self.assertIn("materials_json JSON", schema)
        self.assertIn("byte_size BIGINT UNSIGNED", schema)
        self.assertIn("deleted_at DATETIME NULL", schema)
        self.assertIn("PRIMARY KEY (spu_id)", schema)
        self.assertRegex(schema, r"UNIQUE KEY \w+ \(model_asset_id\)")

    def test_deployment_tool_discovers_migration_005(self):
        from scripts.deploy_database_schema import schema_files, table_names_from_files

        files = schema_files(ROOT / "database/schema", [])
        self.assertIn(ROOT / "database/schema/005_product_models.sql", files)
        self.assertIn("product_model_asset", table_names_from_files(files))
        self.assertIn("product_model_binding", table_names_from_files(files))


if __name__ == "__main__":
    unittest.main()
