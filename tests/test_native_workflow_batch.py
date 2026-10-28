"""Workflow batch persistence tests using an in-memory transactional cursor."""

import copy
import json
import re
import unittest
from decimal import Decimal
from unittest.mock import Mock

from src.engine.exceptions import DBError
from src.engine.native_db import NativeDBClient
from src.services.business.workflow import WorkflowService


class FakeCursor:
    def __init__(self, connection):
        self.connection = connection
        self.lastrowid = 0
        self.results = []

    def execute(self, sql, params=()):
        conn = self.connection
        if conn.get_autocommit():
            raise AssertionError("All SQL must run inside the batch transaction")
        sql = " ".join(sql.split())
        conn.calls.append((sql, tuple(params)))
        self.results = []
        if sql.startswith("SELECT"):
            if "FROM workflow_order" in sql:
                if "FOR UPDATE" not in sql:
                    raise AssertionError("Deduplication must lock existing orders")
                self.results = [row for row in conn.pending["orders"] if row["workflow_no"] in params]
            elif "FROM product_sku" in sql:
                if "FOR UPDATE" not in sql:
                    raise AssertionError("SKU lookup must lock the selected SKU")
                sku = conn.skus.get(int(params[0]))
                self.results = [sku] if sku else []
            elif "FROM product_spu" in sql:
                if "FOR UPDATE" not in sql:
                    raise AssertionError("SPU lookup must lock the selected SPU")
                spu = conn.spus.get(int(params[0]))
                self.results = [spu] if spu else []
            elif "FROM party" in sql:
                allowed_kinds = ("customer", "both") if "kind IN ('customer', 'both')" in sql else ("customer",)
                self.results = [
                    party for party in conn.parties
                    if party["kind"] in allowed_kinds
                    and ("deleted_at IS NULL" not in sql or party.get("deleted_at") is None)
                    and (party["name"] in params or party.get("phone_normalized") in params)
                ][:1]
            else:
                raise AssertionError(f"Unexpected query: {sql}")
            return len(self.results)
        match = re.match(r"INSERT INTO (workflow_order_log|workflow_order)\s*\((.*?)\) VALUES \((.*?)\)", sql)
        if not match:
            raise AssertionError(f"Unexpected write: {sql}")
        table, columns, values = match.groups()
        conn.insert_attempts[table] += 1
        if conn.fail_at == (table, conn.insert_attempts[table]):
            raise RuntimeError("injected insert failure")
        bound = iter(params)
        row = {
            column.strip(): next(bound) if value.strip() == "%s" else value.strip().strip("'")
            for column, value in zip(columns.split(","), values.split(","))
        }
        target = "orders" if table == "workflow_order" else "logs"
        self.lastrowid = len(conn.pending[target]) + 1
        row["id"] = self.lastrowid
        conn.pending[target].append(row)
        return 1

    def fetchone(self):
        return self.results[0] if self.results else None

    def fetchall(self):
        return self.results

    def close(self):
        pass


class FakeConnection:
    def __init__(self):
        self.saved = {"orders": [], "logs": []}
        self.pending = None
        self.skus = {}
        self.spus = {}
        self.parties = [
            {"id": 55, "name": "Alice", "kind": "customer"},
            {"id": 56, "name": "Bob", "kind": "customer"},
        ]
        self.calls = []
        self.insert_attempts = {"workflow_order": 0, "workflow_order_log": 0}
        self.fail_at = None
        self.commits = 0
        self.rollbacks = 0
        self.transactions = 0
        self._autocommit = True

    def get_autocommit(self):
        return self._autocommit

    def autocommit(self, enabled):
        if not enabled:
            if not self._autocommit:
                raise AssertionError("Nested transaction")
            self.transactions += 1
            self.pending = copy.deepcopy(self.saved)
        self._autocommit = enabled

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.commits += 1
        self.saved = copy.deepcopy(self.pending)

    def rollback(self):
        self.rollbacks += 1
        self.pending = None


class NativeWorkflowBatchTests(unittest.TestCase):
    def setUp(self):
        self.connection = FakeConnection()
        self.db = object.__new__(NativeDBClient)
        self.db._get_connection = lambda: self.connection
        self.db._operator_user_id = lambda: 9
        self.db.query = Mock(side_effect=AssertionError("Use the transaction cursor"))
        self.db.execute = Mock(side_effect=AssertionError("Use the transaction cursor"))
        self.db.save_workflow_order = Mock(side_effect=AssertionError("No nested single saves"))
        self.rows = [
            {"customer_name": "Alice", "goods_name": "Box A", "order_quantity": 20,
             "color": "red", "order_images": ["a.png"], "is_screen_print": 1, "remark": "first"},
            {"customer": "Bob", "goods_name": "Box B", "quantity": 30,
             "order_type": 1, "is_made": 1, "is_delivered": 1},
        ]

    def sku(self, **overrides):
        row = {"id": 88, "sku_no": "SJ0088", "title": "Canonical box", "color": "blue",
               "status": "active", "is_sellable": 1, "is_listed": 0, "case_pack_qty": 28,
               "unit_id": 1, "spu_id": 18}
        row.update(overrides)
        self.connection.skus[row["id"]] = row
        self.connection.spus[row["spu_id"]] = {"id": row["spu_id"], "status": "active", "deleted_at": None}
        return row

    def test_second_order_insert_failure_rolls_back_orders_and_logs_without_commit(self):
        self.connection.fail_at = ("workflow_order", 2)
        with self.assertRaisesRegex(RuntimeError, "injected insert failure"):
            self.db.save_workflow_orders_batch(self.rows, batch_id="rollback")
        self.assertEqual(self.connection.saved, {"orders": [], "logs": []})
        self.assertEqual(self.connection.insert_attempts["workflow_order"], 2)
        self.assertEqual(self.connection.insert_attempts["workflow_order_log"], 1)
        self.assertEqual((self.connection.transactions, self.connection.commits, self.connection.rollbacks), (1, 0, 1))

    def test_log_failure_also_rolls_back_entire_batch(self):
        self.connection.fail_at = ("workflow_order_log", 2)
        with self.assertRaisesRegex(RuntimeError, "injected insert failure"):
            self.db.save_workflow_orders_batch(self.rows)
        self.assertEqual(self.connection.saved, {"orders": [], "logs": []})
        self.assertEqual((self.connection.commits, self.connection.rollbacks), (0, 1))

    def test_two_rows_and_create_logs_share_one_transaction(self):
        result = self.db.save_workflow_orders_batch(self.rows, batch_id="valid")
        self.assertEqual(result["code"], 0)
        self.assertEqual([item["id"] for item in result["data"]], [1, 2])
        orders = self.connection.saved["orders"]
        self.assertEqual([row["workflow_no"] for row in orders], [item["workflow_no"] for item in result["data"]])
        self.assertEqual([row["customer_name_snapshot"] for row in orders], ["Alice", "Bob"])
        self.assertEqual([row["customer_id"] for row in orders], [55, 56])
        self.assertEqual([row["quantity"] for row in orders], [Decimal(20), Decimal(30)])
        self.assertEqual([row["status"] for row in orders], ["pending", "completed"])
        self.assertEqual(json.loads(orders[0]["order_image_urls"]), ["a.png"])
        self.assertEqual(orders[0]["is_screen_print"], 1)
        self.assertEqual(orders[0]["remark"], "first")
        self.assertEqual([row["workflow_order_id"] for row in self.connection.saved["logs"]], [1, 2])
        self.assertTrue(all(row["action"] == "create" for row in self.connection.saved["logs"]))
        self.assertEqual((self.connection.transactions, self.connection.commits, self.connection.rollbacks), (1, 1, 0))

    def test_duplicate_batch_returns_original_ids_without_new_writes(self):
        first = self.db.save_workflow_orders_batch(self.rows, batch_id="repeat")
        attempts = self.connection.insert_attempts.copy()
        second = self.db.save_workflow_orders_batch(self.rows, batch_id="repeat")
        self.assertEqual(first, second)
        self.assertEqual(self.connection.insert_attempts, attempts)
        self.assertEqual(len(self.connection.saved["orders"]), 2)

    def test_correction_identity_keeps_deduplication_stable_when_rows_are_reordered(self):
        for index, row in enumerate(self.rows):
            row["correction_id"] = f"row-{index}"
        first = self.db.save_workflow_orders_batch(self.rows, batch_id="identity")
        second = self.db.save_workflow_orders_batch(list(reversed(self.rows)), batch_id="identity")
        self.assertEqual(second["data"], list(reversed(first["data"])))
        self.assertEqual(len(self.connection.saved["logs"]), 2)

    def test_partial_preexisting_batch_is_rejected_without_creating_missing_rows(self):
        self.db.save_workflow_orders_batch(self.rows, batch_id="partial")
        self.connection.saved["orders"].pop()
        before = copy.deepcopy(self.connection.saved)
        attempts = self.connection.insert_attempts.copy()
        with self.assertRaises(DBError):
            self.db.save_workflow_orders_batch(self.rows, batch_id="partial")
        self.assertEqual(self.connection.saved, before)
        self.assertEqual(self.connection.insert_attempts, attempts)
        self.assertEqual(self.connection.rollbacks, 1)

    def test_no_batch_id_uses_distinct_workflow_numbers(self):
        first = self.db.save_workflow_orders_batch(self.rows)
        second = self.db.save_workflow_orders_batch(self.rows)
        numbers = [row["workflow_no"] for row in first["data"] + second["data"]]
        self.assertEqual(len(set(numbers)), 4)
        self.assertTrue(all(number.startswith("WF") and len(number) <= 80 for number in numbers))

    def test_inactive_or_unsellable_sku_rejection_rolls_back_prior_row(self):
        for unavailable in ({"status": "inactive"}, {"is_sellable": 0}):
            with self.subTest(unavailable=unavailable):
                self.setUp()
                self.sku(**unavailable)
                self.rows[1]["selected_sku_id"] = 88
                with self.assertRaises(DBError):
                    self.db.save_workflow_orders_batch(self.rows)
                self.assertEqual(self.connection.saved, {"orders": [], "logs": []})
                self.assertEqual((self.connection.commits, self.connection.rollbacks), (0, 1))

    def test_selected_sku_is_canonical_unlisted_allowed_and_raw_quantity_converted_once(self):
        self.sku()
        self.rows[0].update(selected_sku_id=88, product_id=999, goods_name="Stale title", color="stale",
                            order_quantity=56, raw_quantity=2, raw_unit="\u4ef6", perpiece=999)
        self.db.save_workflow_orders_batch(self.rows)
        order = self.connection.saved["orders"][0]
        self.assertEqual(order["sku_id"], 88)
        self.assertEqual(order["sku_no_snapshot"], "SJ0088")
        self.assertEqual(order["goods_name_snapshot"], "Canonical box")
        self.assertEqual(order["color_snapshot"], "blue")
        self.assertEqual(order["quantity"], Decimal(56))

    def test_product_id_is_treated_as_native_sku_id(self):
        self.sku()
        self.rows[0]["product_id"] = 88
        self.db.save_workflow_orders_batch(self.rows)
        self.assertEqual(self.connection.saved["orders"][0]["sku_id"], 88)

    def test_missing_sku_rolls_back(self):
        self.rows[1]["product_id"] = 404
        with self.assertRaises(DBError):
            self.db.save_workflow_orders_batch(self.rows)
        self.assertEqual(self.connection.saved, {"orders": [], "logs": []})
        self.assertEqual(self.connection.commits, 0)

    def test_quantity_metadata_is_optional_and_each_row_is_converted_independently(self):
        self.sku(case_pack_qty=20)
        self.sku(id=89, spu_id=19, case_pack_qty=28)
        self.rows[0].update(product_id=88, raw_quantity=2, raw_unit="\u4ef6", perpiece=999)
        self.rows[1].update(product_id=89, raw_quantity=3, raw_unit="\u5957", perpiece=999)
        self.db.save_workflow_orders_batch(self.rows)
        self.assertEqual([row["quantity"] for row in self.connection.saved["orders"]], [Decimal(40), Decimal(3)])

    def test_incomplete_raw_metadata_does_not_multiply_normalized_quantity(self):
        self.sku()
        self.rows[0].update(product_id=88, perpiece=28)
        self.rows[1].update(raw_quantity=2)
        self.db.save_workflow_orders_batch(self.rows)
        self.assertEqual([row["quantity"] for row in self.connection.saved["orders"]], [Decimal(20), Decimal(30)])

    def test_piece_quantity_requires_positive_finite_locked_pack(self):
        for pack in (None, "", 0, -1, "NaN", "sNaN", "Infinity", "-Infinity", "invalid"):
            with self.subTest(pack=pack):
                self.setUp()
                sku = self.sku(case_pack_qty=pack)
                if pack is None:
                    sku.pop("case_pack_qty")
                self.rows[1].update(product_id=88, quantity=56, perpiece=28,
                                    raw_quantity=2, raw_unit="\u4ef6")
                with self.assertRaises(DBError):
                    self.db.save_workflow_orders_batch(self.rows)
                self.assertEqual(self.connection.saved, {"orders": [], "logs": []})
                self.assertEqual((self.connection.commits, self.connection.rollbacks), (0, 1))

    def test_piece_quantity_cannot_use_snapshot_pack_without_selected_sku(self):
        self.rows[1].update(raw_quantity=2, raw_unit="\u4ef6", perpiece=28)
        with self.assertRaises(DBError):
            self.db.save_workflow_orders_batch(self.rows)
        self.assertEqual(self.connection.commits, 0)

    def test_piece_quantity_requires_raw_quantity(self):
        self.sku()
        self.rows[1].update(product_id=88, raw_unit="\u4ef6", perpiece=28)
        with self.assertRaises(DBError):
            self.db.save_workflow_orders_batch(self.rows)
        self.assertEqual(self.connection.commits, 0)

    def test_final_quantity_must_be_positive_and_finite(self):
        for quantity in (None, "", 0, -1, "NaN", "sNaN", "Infinity", "-Infinity", "invalid"):
            for source in ("quantity", "raw_sets", "raw_pieces"):
                with self.subTest(quantity=quantity, source=source):
                    self.setUp()
                    if source == "quantity":
                        self.rows[1]["quantity"] = quantity
                    else:
                        self.rows[1].update(raw_quantity=quantity, raw_unit="\u5957")
                        if source == "raw_pieces":
                            self.sku()
                            self.rows[1].update(product_id=88, raw_unit="\u4ef6")
                        if quantity in (None, "") and source == "raw_sets":
                            continue
                    with self.assertRaises(DBError):
                        self.db.save_workflow_orders_batch(self.rows)
                    self.assertEqual(self.connection.saved, {"orders": [], "logs": []})
                    self.assertEqual((self.connection.commits, self.connection.rollbacks), (0, 1))

    def test_empty_canonical_color_uses_default_instead_of_snapshot(self):
        self.sku(color="")
        self.rows[0].update(product_id=88, color="stale")
        self.db.save_workflow_orders_batch(self.rows)
        self.assertEqual(self.connection.saved["orders"][0]["color_snapshot"], "\u9ed8\u8ba4\u989c\u8272")

    def test_customer_lookup_excludes_deleted_and_allows_both_kind(self):
        self.connection.parties = [
            {"id": 1, "name": "Alice", "kind": "customer", "deleted_at": "2026-01-01"},
            {"id": 2, "name": "Alice", "kind": "supplier"},
            {"id": 55, "name": "Alice", "kind": "both"},
        ]
        self.db.save_workflow_orders_batch(self.rows)
        self.assertEqual([row["customer_id"] for row in self.connection.saved["orders"]], [55, None])

    def test_missing_deleted_or_inactive_spu_rolls_back_entire_batch(self):
        for spu in (None, {"status": "inactive"}, {"status": "deleted"},
                    {"status": "active", "deleted_at": "2026-01-01"}):
            with self.subTest(spu=spu):
                self.setUp()
                self.sku()
                if spu is None:
                    self.connection.spus.clear()
                else:
                    self.connection.spus[18].update(spu)
                self.rows[1]["product_id"] = 88
                with self.assertRaises(DBError):
                    self.db.save_workflow_orders_batch(self.rows)
                self.assertEqual(self.connection.saved, {"orders": [], "logs": []})
                self.assertEqual((self.connection.commits, self.connection.rollbacks), (0, 1))

    def test_repeated_correction_identity_is_rejected_before_writes(self):
        for row in self.rows:
            row["correction_id"] = "same-row"
        with self.assertRaises(DBError):
            self.db.save_workflow_orders_batch(self.rows, batch_id="duplicate-identity")
        self.assertEqual(self.connection.saved, {"orders": [], "logs": []})
        self.assertEqual(self.connection.commits, 0)

    def test_empty_batch_is_a_noop(self):
        self.assertEqual(self.db.save_workflow_orders_batch([]), {"code": 0, "data": []})
        self.assertEqual(self.connection.transactions, 0)

    def test_service_forwards_rows_and_batch_id(self):
        db = Mock()
        db.save_workflow_orders_batch.return_value = {"code": 0, "data": [{"id": 1, "workflow_no": "WF1"}]}
        result = WorkflowService(db).save_orders_batch(self.rows, batch_id="service")
        self.assertEqual(result, db.save_workflow_orders_batch.return_value)
        db.save_workflow_orders_batch.assert_called_once_with(self.rows, batch_id="service")

    def test_product_output_exposes_normalized_sellable_flag(self):
        self.db._product_category_name_lookup = lambda: {}
        for value, expected in ((0, False), ("false", False), (1, True), (None, True)):
            with self.subTest(value=value):
                product = self.db._row_to_product({"id": 88, "is_sellable": value})
                self.assertEqual(product.get("is_sellable"), expected)


if __name__ == "__main__":
    unittest.main()
