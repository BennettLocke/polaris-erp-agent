import unittest
from copy import deepcopy

from src.core.image_correction import prepare_correction_state
from src.channels import http_api


class ImageProductCorrectionTests(unittest.TestCase):
    def setUp(self):
        self.state = {
            "pending_action": "confirm_image_workflow_correction", "correction_batch_id": "batch-1",
            "customer_name": "齐唯", "parsed_list": [
                {"correction_id": "row-1", "goods_name": "墨相3两", "original_goods_name": "墨相3两", "color": "红色", "quantity": 1, "unit": "件", "raw_quantity": 1, "raw_unit": "件", "source_filename": "一.png", "preview_url": "/api/images/file/one.png", "remark": "墨相3两黄色 烫金"},
                {"correction_id": "row-2", "goods_name": "", "quantity": 3, "unit": "套", "source_filename": "二.png"},
            ],
        }
        self.products = {
            44: {"id": 44, "title": "【墨香】二三两", "color": "黄色", "case_pack_qty": 24, "unit_id": 1, "unit_name": "套", "native_status": "active", "is_listed": 0},
            55: {"id": 55, "title": "【喜悦】半斤", "color": "蓝色", "case_pack_qty": 48, "unit_id": 1, "unit_name": "套", "native_status": "active"},
        }

    def selected(self):
        state = deepcopy(self.state)
        state["parsed_list"][0]["selected_sku_id"] = 44
        state["parsed_list"][1]["selected_sku_id"] = 55
        return state

    def test_each_selection_is_canonical_and_keeps_source_and_other_fields(self):
        submitted = self.selected()
        submitted["customer_name"] = "新客户"
        submitted["parsed_list"][0].update(goods_name="伪造名称", color="绿色", preview_url="evil", original_goods_name="伪造OCR")
        clean = prepare_correction_state(submitted, self.state, self.products.get)
        one, two = clean["parsed_list"]
        self.assertEqual((one["goods_name"], one["color"], one["quantity"]), ("【墨香】二三两", "黄色", 24))
        self.assertEqual(one["original_goods_name"], "墨相3两")
        self.assertEqual(one["preview_url"], "/api/images/file/one.png")
        self.assertEqual(one["customer"], "新客户")
        self.assertEqual(two["quantity"], 3)
        self.assertIn("烫金", one["remark"])
        self.assertIn("【墨香】二三两", one["remark"])
        self.assertEqual([p["product_id"] for p in clean["order_params"]["products"]], [44, 55])

    def test_piece_quantity_is_recomputed_from_raw_only_once_and_uses_replacement_pack(self):
        clean = prepare_correction_state(self.selected(), self.state, self.products.get)
        again = prepare_correction_state(clean, clean, self.products.get)
        self.assertEqual(again["parsed_list"][0]["quantity"], 24)
        again["parsed_list"][0]["selected_sku_id"] = 55
        replaced = prepare_correction_state(again, clean, self.products.get)
        self.assertEqual(replaced["parsed_list"][0]["quantity"], 48)

    def test_retrying_an_unacknowledged_old_editor_still_corrects_remark_names(self):
        submitted = self.selected()
        clean = prepare_correction_state(submitted, self.state, self.products.get)
        retried = prepare_correction_state(submitted, clean, self.products.get)
        self.assertNotIn("墨相3两", retried["parsed_list"][0]["remark"])
        self.assertIn("【墨香】二三两", retried["parsed_list"][0]["remark"])

    def test_no_selected_sku_cannot_be_bypassed_by_filling_product_text(self):
        submitted = deepcopy(self.state)
        submitted["parsed_list"][1]["goods_name"] = "喜悦半斤"
        with self.assertRaisesRegex(ValueError, "第 1 张.*选择商品"):
            prepare_correction_state(submitted, self.state, self.products.get)

    def test_unlisted_is_allowed_but_disabled_deleted_and_nonsellable_are_rejected(self):
        self.assertEqual(prepare_correction_state(self.selected(), self.state, self.products.get)["parsed_list"][0]["product_id"], 44)
        for patch in ({"native_status": "inactive"}, {"deleted_at": "2026-10-28"}, {"is_sellable": 0}):
            with self.subTest(patch=patch):
                products = deepcopy(self.products)
                products[44].update(patch)
                with self.assertRaisesRegex(ValueError, "第 1 张.*不可用"):
                    prepare_correction_state(self.selected(), self.state, products.get)

    def test_row_identity_and_batch_token_cannot_be_changed(self):
        for edit in ("batch", "row"):
            submitted = self.selected()
            if edit == "batch":
                submitted["correction_batch_id"] = "other"
            else:
                submitted["parsed_list"].reverse()
            with self.assertRaises(ValueError):
                prepare_correction_state(submitted, self.state, self.products.get)

    def test_incomplete_quantity_or_missing_pack_never_defaults_to_one(self):
        for qty in (0, -1, "", "nan", "inf"):
            submitted = self.selected()
            submitted["parsed_list"][1]["raw_quantity"] = qty
            with self.assertRaisesRegex(ValueError, "第 2 张.*数量"):
                prepare_correction_state(submitted, self.state, self.products.get)
        products = deepcopy(self.products)
        products[44].pop("case_pack_qty")
        with self.assertRaisesRegex(ValueError, "件规"):
            prepare_correction_state(self.selected(), self.state, products.get)

    def test_empty_ocr_color_does_not_preselect_an_arbitrary_matched_sku(self):
        state = http_api._build_image_workflow_correction_state({"parsed": {"goods_name": "墨香3两", "product_id": 44, "color": "", "quantity": 2}, "workflow_order_payload": {"goods_name": "墨香3两"}})
        row = state["parsed_list"][0]
        self.assertEqual(row["recognition_status"], "failed")
        self.assertNotIn("selected_sku_id", row)
        self.assertNotIn("product_id", row)


if __name__ == "__main__":
    unittest.main()
