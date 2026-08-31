import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

from src.skills.bag_upload.workflow import BagUploadWorkflow


class BagUploadCategoryTest(unittest.TestCase):
    def setUp(self):
        self.workflow = BagUploadWorkflow()

    def test_rock_tea_category_priority(self):
        cases = [
            ("奇兰", 9, "公版泡袋"),
            ("百瑞香", 9, "公版泡袋"),
            ("奇兰品种", 19, "品种茶泡袋"),
            ("品种水仙", 19, "品种茶泡袋"),
            ("肉桂品种", 19, "品种茶泡袋"),
            ("大红袍品种", 19, "品种茶泡袋"),
            ("老枞水仙", 6, "水仙泡袋"),
            ("牛栏坑肉桂", 7, "肉桂泡袋"),
            ("大红袍", 5, "大红袍泡袋"),
            ("正山小种", 12, "红茶泡袋"),
        ]
        for name, category_id, category_name in cases:
            with self.subTest(name=name):
                category = self.workflow._classify_category(name, "岩茶") or self.workflow._default_category("岩茶")
                self.assertEqual(category, {"category_id": category_id, "category_name": category_name})

    def test_explicit_templates_keep_categories_and_prices(self):
        for bag_type, category_id, price in [("红茶", 12, 10), ("宽版", 21, 18)]:
            with self.subTest(bag_type=bag_type):
                self.assertEqual(self.workflow._classify_category("水仙品种", bag_type)["category_id"], category_id)
                self.assertEqual(self.workflow._default_category(bag_type)["category_id"], category_id)
                self.assertEqual(self.workflow._bag_price(bag_type), price)

    def test_display_name_removes_marker_and_redundant_separators(self):
        for raw, expected in [
            ("奇兰品种", "奇兰"),
            ("品种-奇兰", "奇兰"),
            ("奇兰_品种_", "奇兰"),
            ("奇兰-品种-茶香", "奇兰-茶香"),
            ("【品种】奇兰", "奇兰"),
            ("奇兰（品种-）", "奇兰"),
            ("奇兰-品种-品种-茶香", "奇兰-茶香"),
            ("奇兰【品种-品种-】", "奇兰"),
            ("【SJ1737】奇兰品种-长泡袋", "奇兰"),
            ("奇兰-品种-sj1737", "奇兰"),
            ("SJ1737-品种", "泡袋新品"),
            ("老枞水仙", "老枞水仙"),
        ]:
            with self.subTest(raw=raw):
                self.assertEqual(self.workflow._display_title_from_filename(raw), expected)

    def _run_batch(self, directory, names, existing=None, details=None, bag_type="岩茶", workers=1, single_image=False, settings=None, save_results=None):
        if single_image:
            archive = directory / names[0]
            archive.write_bytes(b"test PNG; rendering is stubbed")
        else:
            archive = directory / "bags.zip"
            with zipfile.ZipFile(archive, "w") as bundle:
                for name in names:
                    bundle.writestr(name, b"test PNG; rendering is stubbed")
        service = Mock()
        service.next_sku_no.side_effect = ["SJ9001", "SJ9002", "SJ9003", "SJ9004"]
        service.options.return_value = {"data": {"unit_list": [{"id": 2, "name": "捆"}]}}
        service.save.return_value = {"code": 0, "data": {"id": 101}}
        if save_results is not None:
            service.save.side_effect = save_results
        assets = {"main_path": str(directory / "main.png"), "detail_path": str(directory / "detail.png")}
        with (
            patch("src.skills.bag_upload.workflow.BAG_GENERATED_DIR", directory / "generated"),
            patch("src.skills.bag_upload.workflow.BAG_UPLOAD_WORKERS", workers),
            patch("src.skills.bag_upload.workflow.get_product_service", return_value=service),
            patch.object(self.workflow, "_generate_preview_assets", return_value=assets) as render,
            patch.object(self.workflow, "_upload_to_oss", return_value={"url": "https://example.com/image.png"}),
            patch.object(self.workflow, "_cleanup_generated_assets"),
            patch.object(self.workflow, "_find_existing_product_by_code", return_value=existing) as lookup,
            patch.object(self.workflow, "_load_product_for_edit", return_value=details or existing or {}),
            patch.object(self.workflow, "_product_base_payload", return_value={"existing": {"id": 901}}),
        ):
            result = self.workflow._process_batch_upload(str(archive), {"bag_type": bag_type, **(settings or {})})
        return result, service, render, lookup

    def test_zip_mixed_categories_use_raw_names_before_cleaning(self):
        with tempfile.TemporaryDirectory() as temporary:
            result, service, render, _ = self._run_batch(Path(temporary), [
                "01-奇兰.png", "02-奇兰品种.png", "03-老枞水仙.png", "04-水仙品种.png",
            ])
        self.assertEqual(result["failures"], [])
        self.assertEqual([row["category_name"] for row in result["success"]], [
            "公版泡袋", "品种茶泡袋", "水仙泡袋", "品种茶泡袋",
        ])
        self.assertEqual([call.kwargs["title"] for call in render.call_args_list], ["奇兰", "奇兰", "老枞水仙", "水仙"])
        payloads = [call.args[0] for call in service.save.call_args_list]
        self.assertEqual([row["product_category_id"] for row in payloads], [[9], [19], [6], [19]])
        for index, (payload, item) in enumerate(zip(payloads, result["success"]), start=1):
            self.assertEqual(item["title"], payload["title"])
            self.assertNotIn("品种", item["title"])
            self.assertTrue(item["title"].startswith(f"【SJ900{index}】"))
            self.assertTrue(item["title"].endswith("-长泡袋"))
            self.assertEqual(payload["base"]["new_0"]["unit"]["new_0"]["price"], 18)
        receipt = self.workflow._batch_done_text(result)
        self.assertIn("【SJ9002】奇兰-长泡袋", receipt)
        self.assertNotIn("奇兰品种", receipt)

    def test_existing_code_preserves_product_identity_and_cleans_only_marker(self):
        existing = {"id": 88, "title": "【SJ1737】原版奇兰品种-长泡袋", "status": 1, "product_category_id": [7]}
        with tempfile.TemporaryDirectory() as temporary:
            result, service, render, lookup = self._run_batch(Path(temporary), ["SJ1737-不同文件名品种.png"], existing)
        self.assertEqual(result["failures"], [])
        lookup.assert_called_once_with("SJ1737")
        service.next_sku_no.assert_not_called()
        payload = service.save.call_args.args[0]
        self.assertEqual(payload["id"], 88)
        self.assertEqual(payload["status"], 1)
        self.assertEqual(payload["title"], "【SJ1737】原版奇兰-长泡袋")
        self.assertEqual(payload["product_category_id"], [19])
        self.assertEqual(render.call_args.kwargs["title"], "原版奇兰")
        self.assertEqual(result["success"][0]["title"], payload["title"])
        self.assertEqual(result["success"][0]["source_title"], "原版奇兰")
        self.assertEqual(result["success"][0]["action"], "更新")

    def test_existing_title_without_marker_is_not_renamed(self):
        existing = {"id": 88, "title": "【SJ1737】原版  奇兰-长泡袋", "status": 0}
        with tempfile.TemporaryDirectory() as temporary:
            result, service, render, _ = self._run_batch(Path(temporary), ["SJ1737-奇兰品种.png"], existing)
        self.assertEqual(result["failures"], [])
        self.assertEqual(service.save.call_args.args[0]["title"], existing["title"])
        self.assertEqual(render.call_args.kwargs["title"], "原版  奇兰")

    def test_existing_code_only_uses_original_product_name_for_category(self):
        existing = {"id": 88, "title": "【SJ1737】水仙品种-长泡袋", "status": 0}
        with tempfile.TemporaryDirectory() as temporary:
            result, service, render, _ = self._run_batch(Path(temporary), ["SJ1737.png"], existing)
        self.assertEqual(result["failures"], [])
        self.assertEqual(service.save.call_args.args[0]["product_category_id"], [19])
        self.assertEqual(render.call_args.kwargs["title"], "水仙")

    def test_existing_detail_name_is_used_for_both_images_and_receipt(self):
        existing = {"id": 88, "title": "【SJ1737】旧名品种-长泡袋", "status": 0}
        details = {**existing, "title": "【SJ1737】现名品种-长泡袋"}
        with tempfile.TemporaryDirectory() as temporary:
            result, service, render, _ = self._run_batch(Path(temporary), ["SJ1737-奇兰品种.png"], existing, details)
        self.assertEqual(result["failures"], [])
        self.assertEqual(service.save.call_args.args[0]["title"], "【SJ1737】现名-长泡袋")
        self.assertEqual(result["success"][0]["title"], service.save.call_args.args[0]["title"])
        self.assertEqual(render.call_args.kwargs["title"], "现名")

    def test_existing_category_becomes_primary_without_stale_categories(self):
        existing = {"id": 88, "title": "【SJ1737】奇兰-长泡袋", "product_category_id": [7, 19]}
        with tempfile.TemporaryDirectory() as temporary:
            result, service, _, _ = self._run_batch(Path(temporary), ["SJ1737-奇兰品种.png"], existing)
        self.assertEqual(result["failures"], [])
        self.assertEqual(service.save.call_args.args[0]["product_category_id"], [19])

    def test_parallel_zip_items_keep_independent_categories(self):
        with tempfile.TemporaryDirectory() as temporary:
            result, service, render, _ = self._run_batch(Path(temporary), [
                "01-奇兰.png", "02-奇兰品种.png", "03-老枞水仙.png", "04-水仙品种.png",
            ], workers=3)
        self.assertEqual(result["failures"], [])
        payloads = {call.args[0]["title"]: call.args[0] for call in service.save.call_args_list}
        rendered = {call.kwargs["code"]: call.kwargs["title"] for call in render.call_args_list}
        for item, category in zip(result["success"], [9, 19, 6, 19]):
            self.assertEqual(payloads[item["title"]]["product_category_id"], [category])
            self.assertNotIn("品种", rendered[item["code"]])
        self.assertEqual(len(payloads), 4)

    def test_single_png_uses_same_category_and_title_rules(self):
        with tempfile.TemporaryDirectory() as temporary:
            result, service, render, _ = self._run_batch(Path(temporary), ["奇兰品种.png"], single_image=True)
        self.assertEqual(result["failures"], [])
        self.assertEqual(service.save.call_args.args[0]["product_category_id"], [19])
        self.assertEqual(render.call_args.kwargs["title"], "奇兰")

    def test_missing_existing_code_is_not_created(self):
        with tempfile.TemporaryDirectory() as temporary:
            result, service, render, _ = self._run_batch(Path(temporary), ["SJ1737-奇兰品种.png"])
        self.assertEqual(len(result["failures"]), 1)
        service.save.assert_not_called()
        service.next_sku_no.assert_not_called()
        render.assert_not_called()

    def test_black_and_wide_uploads_keep_suffix_price_and_category(self):
        for bag_type, category, suffix, price in [("红茶", 12, "短泡袋", 10), ("宽版", 21, "宽版泡袋", 18)]:
            with self.subTest(bag_type=bag_type), tempfile.TemporaryDirectory() as temporary:
                result, service, render, _ = self._run_batch(Path(temporary), ["水仙品种.png"], bag_type=bag_type)
                self.assertEqual(result["failures"], [])
                payload = service.save.call_args.args[0]
                self.assertEqual(payload["title"], f"【SJ9001】水仙-{suffix}")
                self.assertEqual(payload["product_category_id"], [category])
                self.assertEqual(payload["base"]["new_0"]["unit"]["new_0"]["price"], price)
                self.assertEqual(render.call_args.kwargs["title"], "水仙")

    def test_dialog_price_and_listing_apply_to_new_and_existing_products(self):
        for existing in [None, {"id": 88, "title": "【SJ1737】奇兰-长泡袋", "status": 1}]:
            for listed in [True, False]:
                with self.subTest(existing=bool(existing), listed=listed), tempfile.TemporaryDirectory() as temporary:
                    name = "SJ1737-奇兰品种.png" if existing else "奇兰品种.png"
                    result, service, _, _ = self._run_batch(Path(temporary), [name], existing, settings={"price": 12.34, "is_listed": listed})
                    self.assertEqual(result["failures"], [])
                    payload = service.save.call_args.args[0]
                    self.assertEqual(payload.get("is_listed"), listed)
                    if not existing:
                        self.assertEqual(payload["base"]["new_0"]["unit"]["new_0"]["price"], 12.34)
                    self.assertEqual(result["success"][0].get("price"), 12.34)
                    self.assertEqual(result["success"][0].get("is_listed"), listed)

    def test_failed_product_save_is_not_reported_as_success(self):
        with tempfile.TemporaryDirectory() as temporary:
            result, service, _, _ = self._run_batch(Path(temporary), ["01-奇兰.png", "02-水仙.png"],
                settings={"price": 12.34, "is_listed": True},
                save_results=[{"code": 400, "msg": "商品保存失败"}, {"code": 0, "data": {"id": 101}}])
        self.assertEqual(len(result["success"]), 1)
        self.assertEqual(len(result["failures"]), 1)
        self.assertIn("商品保存失败", result["failures"][0]["error"])
        self.assertEqual(result["failures"][0]["filename"], "01-奇兰.png")
        self.assertEqual(service.save.call_count, 2)

    def test_existing_product_real_payload_updates_price_and_preserves_sku_units(self):
        detail = {"id": 88, "title": "【SJ1737】奇兰-长泡袋", "status": 1,
                  "product_group_data": [{"id": 88, "coding": "SJ1737", "base": [{"id": 80, "unit_id": 2, "unit_number": 1, "price": 18, "cost_price": 7}]}]}
        with patch("src.skills.bag_upload.workflow.get_product_service") as service:
            service.return_value.save.return_value = {"code": 0}
            self.workflow._update_existing_product_images(detail, "SJ1737", 19,
                "https://example.com/main.png", "https://example.com/detail.png", price=12.34,
                product_detail=detail, is_listed=True)
            payload = service.return_value.save.call_args.args[0]
        self.assertTrue(payload["is_listed"])
        self.assertEqual(payload["base"]["88"]["unit"]["80"]["price"], 12.34)
        self.assertEqual(payload["base"]["88"]["unit"]["80"]["cost_price"], 7)
        self.assertEqual(payload["base"]["88"]["unit"]["80"]["unit_id"], 2)

    def test_legacy_upload_omits_listing_option(self):
        with tempfile.TemporaryDirectory() as temporary:
            result, service, _, _ = self._run_batch(Path(temporary), ["奇兰.png"])
        self.assertEqual(result["failures"], [])
        self.assertNotIn("is_listed", service.save.call_args.args[0])

    def test_existing_lookup_includes_inactive_products(self):
        inactive = {"id": 88, "sku_no": "SJ1737", "status": 1}
        with patch("src.skills.bag_upload.workflow.get_product_service") as service:
            service.return_value.search.side_effect = lambda code, **kwargs: [inactive] if kwargs.get("active_only") is False else []
            self.assertEqual(self.workflow._find_existing_product_by_code("SJ1737"), inactive)

    def test_failed_render_and_partial_web_copy_clean_temporary_assets(self):
        for failure in ["prepare", "render", "copy"]:
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                source = root / "source.png"
                source.write_bytes(b"source")
                generated, web = root / "generated", root / "web"
                def command(args, **kwargs):
                    if "--debug-dir" in args:
                        prepared = Path(args[3])
                        prepared.parent.mkdir(parents=True, exist_ok=True)
                        prepared.write_bytes(b"prepared")
                        if failure == "prepare":
                            raise RuntimeError("prepare failed")
                    else:
                        output = Path(args[args.index("--output") + 1])
                        (output / "主图.png").write_bytes(b"main")
                        (output / "详情页.png").write_bytes(b"detail")
                        if failure == "render":
                            raise RuntimeError("render failed")
                def copy(src, dest):
                    Path(dest).write_bytes(b"partial")
                    raise RuntimeError("copy failed")
                with patch("src.skills.bag_upload.workflow.BAG_GENERATED_DIR", generated), patch("src.skills.bag_upload.workflow.WEB_IMAGE_DIR", web), patch.object(self.workflow, "_run_command", side_effect=command), patch("src.skills.bag_upload.workflow.shutil.copy2", side_effect=copy):
                    with self.assertRaisesRegex(RuntimeError, "failed"):
                        self.workflow._generate_preview_assets(str(source), "SJ1737", "奇兰")
                self.assertEqual(list(generated.iterdir()), [])
                self.assertEqual(list(web.iterdir()), [])
                self.assertTrue(source.exists())


if __name__ == "__main__":
    unittest.main()
