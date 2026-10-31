"""Versioned binding config, atomic saves, and public mini projections."""
import copy
import json
import unittest
from unittest.mock import Mock, patch

from src.channels import http_api
from src.services.business.products import ProductService
from tests import test_native_product_models as native_tests


def config(bound_asset, **overrides):
    return {"version": 1, "asset_id": bound_asset, "material_index": 4,
            "sku_colors": {"20": "#ab12ef"}, "default_sku_key": "20",
            "camera_direction": [0, 3, 4], "default_pose": "open", **overrides}


class ProductModelConfigSaveTest(unittest.TestCase):
    record = native_tests.NativeProductModelsTest.record
    save = native_tests.NativeProductModelsTest.save

    def setUp(self):
        native_tests.NativeProductModelsTest.setUp(self)
        self.metadata["materials"] = [{"index": 4, "name": "Paper"}, {"index": 9, "name": "Foil"}]

    def stored(self):
        value = self.connection.state["configs"].get(10)
        return json.loads(value) if isinstance(value, str) else value

    def test_config_normalizes_hex_camera_and_maps_new_keys_to_real_ids(self):
        asset = self.record()
        result = self.save(asset["id"], base={"20": {"spec": "Red"}, "new_0": {"spec": "Blue"}},
                           model_config=config(asset["id"], sku_colors={"new_0": "#aabbcc"}, default_sku_key="new_0"))
        new_id = str(result["data"]["sku_ids"][1])
        self.assertEqual(self.stored(), config(asset["id"], sku_colors={new_id: "#AABBCC"},
            default_sku_key=new_id, camera_direction=[0.0, 0.6, 0.8]))

    def test_omission_preserves_null_resets_and_replacement_retains_only_colors(self):
        first = self.record()
        self.save(first["id"], model_config=config(first["id"]))
        expected = copy.deepcopy(self.stored())
        self.client.save_product({"id": 20, "title": "Renamed", "base": {"20": {"spec": "New name"}}})
        self.assertEqual(self.stored(), expected)
        self.metadata["oss_key"] = "product-models/second.glb"
        second = self.record()
        self.save(second["id"])
        self.assertEqual(self.stored(), config(second["id"], material_index=None,
            camera_direction=None, sku_colors={"20": "#AB12EF"}))
        self.client.save_product({"id": 20, "title": "Reset", "model_config": None})
        self.assertIsNone(self.stored())
        self.assertEqual(self.connection.state["bindings"][10], second["id"])
        self.save(None)
        self.assertNotIn(10, self.connection.state["configs"])

    def test_invalid_config_rolls_back_title_skus_binding_and_origin(self):
        asset = self.record()
        invalid = [{"version": True}, {"version": 2}, {"asset_id": True}, {"asset_id": 999},
                   {"material_index": 0}, {"material_index": True}, {"material_index": 4.0},
                   {"sku_colors": {"999": "#AABBCC"}}, {"sku_colors": {"20": "red"}},
                   {"sku_colors": {20: "#AABBCC"}}, {"sku_colors": []},
                   {"camera_direction": [0, 0, 0]}, {"camera_direction": [True, 0, 1]},
                   {"camera_direction": [float("inf"), 1, 0]}, {"camera_direction": [float("nan"), 1, 0]},
                   {"camera_direction": [1, 0]}, {"default_pose": "closed"},
                   {"default_sku_key": "foreign"}, {"cached_names": {} }]
        for override in invalid:
            with self.subTest(override=override):
                before = copy.deepcopy(self.connection.state)
                with self.assertRaises(ValueError):
                    self.save(asset["id"], model_config=config(asset["id"], **override))
                self.assertEqual(self.connection.state, before)

    def test_config_without_binding_is_rejected(self):
        with self.assertRaises(ValueError):
            self.client.save_product({"id": 20, "title": "Updated", "model_config": config(1)})

    def test_null_material_can_retain_partial_colors_and_default_falls_back(self):
        asset = self.record()
        self.save(asset["id"], model_config=config(asset["id"], material_index=None,
            default_sku_key=None, camera_direction=None))
        self.assertEqual(self.stored()["default_sku_key"], "20")
        self.assertIsNone(self.stored()["material_index"])

    def test_nonobjects_and_missing_fields_raise_value_error(self):
        asset = self.record()
        for value in ([], "config", 1, True, {}, {"version": 1}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.save(asset["id"], model_config=value)

    def test_inferred_legacy_spec_key_is_not_a_submitted_base_key(self):
        asset = self.record()
        with self.assertRaises(ValueError):
            self.save(asset["id"], base={}, model_config=config(asset["id"],
                sku_colors={"new_0": "#112233"}, default_sku_key="new_0"))

    def test_detail_does_not_pair_config_with_a_different_asset_during_replacement(self):
        self.client._row_to_product = lambda row: dict(row)
        self.client.query = Mock(return_value=[{"id": 20, "spu_id": 10}])
        self.client.product_model_for_spu = Mock(return_value={"id": 1})
        self.client.product_model_config_for_spu = Mock(return_value=config(2))
        self.assertIsNone(self.client.product_info(20)["model_config"])

    def test_foreign_base_sku_cannot_be_recolored_or_modified(self):
        self.connection.state["skus"][99] = 88
        asset = self.record()
        before = copy.deepcopy(self.connection.state)
        with self.assertRaises(ValueError):
            self.save(asset["id"], base={"99": {"spec": "Intruder"}},
                      model_config=config(asset["id"], sku_colors={"99": "#AABBCC"}, default_sku_key="99"))
        self.assertEqual(self.connection.state, before)

    def test_explicit_available_sku_number_cannot_bypass_spu_ownership(self):
        self.connection.state["skus"][99] = 88
        self.client._sku_no_available = lambda *_args: True
        asset = self.record()
        with self.assertRaises(ValueError):
            self.save(asset["id"], base={"99": {"spec": "Intruder", "coding": "SJ0099"}},
                      model_config=config(asset["id"], sku_colors={"99": "#112233"}, default_sku_key="99"))

    def test_huge_and_tiny_finite_camera_vectors_normalize_without_overflow(self):
        asset = self.record()
        for vector in ([1e308, 1e308, 1e308], [5e-324, 0, 0]):
            self.save(asset["id"], model_config=config(asset["id"], camera_direction=vector))
            import math
            self.assertAlmostEqual(math.hypot(*self.stored()["camera_direction"]), 1)

    def test_unchanged_bound_config_does_not_require_upload_ownership(self):
        asset = self.record()
        self.save(asset["id"])
        self.client.save_product({"id": 20, "title": "Updated", "base": {"20": {}},
            "model_config": config(asset["id"])}, operator_user_id=99)
        self.assertEqual(self.stored()["sku_colors"], {"20": "#AB12EF"})

    def test_omitted_config_normalizes_old_hexes_and_prunes_invalid_colors(self):
        asset = self.record()
        self.save(asset["id"])
        self.connection.state["configs"][10] = json.dumps(config(asset["id"],
            sku_colors={"20": "#aabbcc", "999": "#112233"}))
        self.client.save_product({"id": 20, "title": "Updated", "base": {"20": {}}})
        self.assertEqual(self.stored()["sku_colors"], {"20": "#AABBCC"})

    def test_config_only_update_prunes_deleted_and_falls_back_in_product_order(self):
        asset = self.record()
        self.connection.state["skus"][21] = 10
        self.save(asset["id"], base={"20": {}, "21": {}}, model_config=config(asset["id"],
            sku_colors={"20": "#112233", "21": "#445566"}, default_sku_key="21"))
        del self.connection.state["skus"][21]
        self.client.save_product({"id": 20, "title": "Updated", "base": {"20": {}}})
        self.assertEqual(self.stored()["sku_colors"], {"20": "#112233"})
        self.assertEqual(self.stored()["default_sku_key"], "20")

    def test_config_saves_lock_spu_then_binding_before_sku_writes_and_current_pruning(self):
        asset = self.record()
        self.save(asset["id"], model_config=config(asset["id"]))
        for extra in ({}, {"model_config": config(asset["id"])}):
            with self.subTest(extra=extra):
                self.connection.statements.clear()
                self.client.save_product({"id": 20, "title": "Updated", "base": {"20": {}}, **extra})
                statements = [sql for sql, _ in self.connection.statements]
                spu_lock = next(i for i, sql in enumerate(statements) if sql.startswith("UPDATE product_spu SET title="))
                binding_lock = next(i for i, sql in enumerate(statements)
                                    if "FROM product_model_binding" in sql and "FOR UPDATE" in sql)
                sku_write = next(i for i, sql in enumerate(statements) if sql.startswith("UPDATE product_sku"))
                pruning_lock = next(i for i, sql in enumerate(statements)
                                    if sql.startswith("SELECT id FROM product_sku WHERE spu_id=") and "FOR UPDATE" in sql)
                self.assertLess(spu_lock, binding_lock)
                self.assertLess(binding_lock, sku_write)
                self.assertLess(sku_write, pruning_lock)


class ProductModelConfigApiTest(unittest.TestCase):
    def test_config_only_save_forwards_operator_through_api_and_service(self):
        db = Mock()
        db.save_product.return_value = {"code": 0}
        service = ProductService(db)
        payload = {"id": 20, "title": "Updated", "model_config": None}
        with patch.object(http_api, "get_product_service", return_value=service), patch.object(
            http_api, "_current_web_user", return_value={"id": 7}), patch.object(http_api, "_has_permission", return_value=True):
            response = http_api.app.test_client().post("/api/product/save", json=payload)
        self.assertEqual(response.status_code, 200)
        db.save_product.assert_called_once_with(payload, operator_user_id=7)

    def test_config_only_requires_existing_product_maintenance_permission(self):
        with patch.object(http_api, "_current_web_user", return_value={"id": 7}), patch.object(
            http_api, "_has_permission", return_value=False), patch.object(http_api, "get_product_service") as service:
            response = http_api.app.test_client().post("/api/product/save", json={"title": "Updated", "model_config": None})
        self.assertEqual(response.status_code, 403)
        service.assert_not_called()

    def test_mini_detail_whitelists_asset_and_filters_hidden_colors(self):
        product = {"id": 20, "spu_id": 10, "is_listed": 1,
            "model": {"id": 5, "url": "https://example/model.glb", "animation_count": 2,
                      "materials": [{"index": 4, "name": "Paper", "private": "secret"}],
                      "oss_key": "secret", "uploaded_by": 7, "sha256": "secret"},
            "model_config": config(5, sku_colors={"20": "#112233", "21": "#445566", "99": "#778899"},
                                   default_sku_key="99", camera_direction=None),
            "product_group_data": [{"id": 21, "is_listed": 1, "color": "Visible"},
                                   {"id": 20, "is_listed": 0, "color": "Hidden"}]}
        with patch.object(http_api, "get_product_service") as service:
            service.return_value.info.return_value = product
            response = http_api.app.test_client().get("/api/mini/goods/detail?id=21")
        goods = response.get_json()["data"]["goods"]
        self.assertEqual(goods["model"], {"id": 5, "url": "https://example/model.glb", "animation_count": 2,
                                         "materials": [{"index": 4, "name": "Paper"}]})
        self.assertEqual(goods["model_config"]["sku_colors"], {"21": "#445566"})
        self.assertEqual(goods["model_config"]["default_sku_key"], "21")
        self.assertEqual(goods["model_url"], "https://example/model.glb")
        self.assertTrue(goods["has_model"])
        self.assertNotIn("secret", json.dumps(goods))

    def test_mini_list_never_carries_full_asset_or_config(self):
        item = http_api._mini_product_payload({"id": 20, "model": {"id": 1, "oss_key": "secret"},
                                              "model_config": config(1)}, list_item=True)
        self.assertNotIn("model", item)
        self.assertNotIn("model_config", item)


if __name__ == "__main__":
    unittest.main()
