import unittest
from copy import deepcopy
from unittest.mock import patch
from pathlib import Path

from src.skills.order_flow.workflow import OrderFlowWorkflow
from src.skills.workflow_order.workflow import WorkflowOrderWorkflow

ROOT = Path(__file__).resolve().parents[1]


class FakeOrderCaller:
    def __init__(self):
        self.calls = []

    def call(self, tool_name, **kwargs):
        self.calls.append((tool_name, kwargs))
        if tool_name == "product_info":
            return {"base": [{"unit_id": 1, "unit_name": "套", "price": 10}]}
        if tool_name == "sales_add":
            return {"code": 0, "data": {"id": 123, "sales_no": "SO123"}}
        raise AssertionError(f"unexpected tool call: {tool_name}")

    def last_call(self, tool_name):
        for name, kwargs in reversed(self.calls):
            if name == tool_name:
                return kwargs
        raise AssertionError(f"{tool_name} was not called")


class FakeWorkflowCaller:
    def __init__(self):
        self.next_id = 456
        self.calls = []

    def call(self, tool_name, **kwargs):
        self.calls.append((tool_name, kwargs))
        if tool_name != "workflow_order_save":
            raise AssertionError(f"unexpected tool call: {tool_name}")
        result = {"code": 0, "data": {"id": self.next_id}}
        self.next_id += 1
        return result


class FakePurchaseOrderCaller(FakeOrderCaller):
    def call(self, tool_name, **kwargs):
        if tool_name == "other_enter_add":
            self.calls.append((tool_name, kwargs))
            return {"code": 0, "data": {"id": 321, "doc_no": "IN321"}}
        return super().call(tool_name, **kwargs)


class FakeCorrectionCaller:
    def __init__(self, upload_result=None):
        self.calls = []
        self.upload_result = upload_result if upload_result is not None else {
            "url": "https://example.test/corrected.png",
        }
        self.products = {
            88: {"id": 88, "title": "礼盒A", "color": "红色", "status": "active"},
            89: {"id": 89, "title": "礼盒B", "color": "蓝色", "status": "active"},
        }

    def call(self, tool_name, **kwargs):
        self.calls.append((tool_name, kwargs))
        if tool_name == "product_info":
            return dict(self.products[kwargs["product_id"]])
        if tool_name == "script_call":
            return self.upload_result
        raise AssertionError(f"unexpected tool call: {tool_name}")


class WorkflowSalesLinkingTest(unittest.TestCase):
    def test_identical_sales_rows_merge_before_order_creation(self):
        workflow = object.__new__(OrderFlowWorkflow)
        workflow.caller = FakeOrderCaller()
        products = [
            {
                "product_id": 88,
                "unit_id": 1,
                "unit": "套",
                "name": "【开物】一两装",
                "color": "咖色",
                "qty": 24,
                "price": 17,
                "warehouse_id": 2,
            },
            {
                "product_id": 88,
                "unit_id": 1,
                "unit": "套",
                "name": "【开物】一两装",
                "color": "咖色",
                "qty": 24,
                "price": 17,
                "warehouse_id": 2,
            },
        ]

        workflow._create_order(
            7,
            "测试客户",
            products,
            2,
            workflow_order_ids=[456, 457],
        )

        sales_call = workflow.caller.last_call("sales_add")
        self.assertEqual(len(sales_call["products"]), 1)
        self.assertEqual(sales_call["products"][0]["buy_number"], 48)
        self.assertEqual(sales_call["workflow_order_ids"], [456, 457])

    def test_identical_sales_rows_are_merged_in_confirmation_state(self):
        workflow = object.__new__(OrderFlowWorkflow)
        products = [
            {
                "product_id": 88,
                "unit_id": 1,
                "unit": "套",
                "name": "【开物】一两装",
                "color": "咖色",
                "qty": 24,
                "price": 17,
                "warehouse_id": 2,
            },
            {
                "product_id": 88,
                "unit_id": 1,
                "unit": "套",
                "name": "【开物】一两装",
                "color": "咖色",
                "qty": 24,
                "price": 17,
                "warehouse_id": 2,
            },
        ]

        result = workflow._confirm_create_order(
            7,
            "测试客户",
            products,
            2,
            workflow_order_ids=[456, 457],
        )

        self.assertEqual(len(result["state"]["products"]), 1)
        self.assertEqual(result["state"]["products"][0]["qty"], 48)
        self.assertEqual(result["state"]["workflow_order_ids"], [456, 457])

    def test_duplicate_case_shortage_is_confirmed_as_one_case(self):
        workflow = object.__new__(OrderFlowWorkflow)
        workflow._product_tracks_inventory = lambda _product: True
        workflow._query_inventory = lambda _product_id: {"百鑫仓库": 0, "自己店里": 0}
        products = [
            {
                "product_id": 88,
                "unit_id": 1,
                "unit": "套",
                "name": "【开物】一两装",
                "color": "咖色",
                "qty": 24,
                "warehouse_id": 2,
                "purchase_policy": "one_case",
                "simple_desc": "1件48套",
            },
            {
                "product_id": 88,
                "unit_id": 1,
                "unit": "套",
                "name": "【开物】一两装",
                "color": "咖色",
                "qty": 24,
                "warehouse_id": 2,
                "purchase_policy": "one_case",
                "simple_desc": "1件48套",
            },
        ]

        result = workflow._purchase_confirmation_for_shortage(7, "测试客户", products, 2)

        self.assertEqual(len(result["state"]["purchase_products"]), 1)
        self.assertIn("订单48套，缺口48套，进货1件（48套/件）", result["question"])
        self.assertEqual(result["question"].count("进货1件"), 1)

    def test_duplicate_case_rows_create_one_purchase_requirement(self):
        workflow = object.__new__(OrderFlowWorkflow)
        workflow.caller = FakePurchaseOrderCaller()
        products = [
            {
                "product_id": 88,
                "unit_id": 1,
                "unit": "套",
                "name": "【开物】一两装",
                "color": "咖色",
                "qty": 24,
                "price": 17,
                "warehouse_id": 2,
                "purchase_warehouse_id": 2,
                "purchase_policy": "one_case",
                "simple_desc": "1件48套",
                "shortage_qty": 24,
                "need_purchase": True,
            },
            {
                "product_id": 88,
                "unit_id": 1,
                "unit": "套",
                "name": "【开物】一两装",
                "color": "咖色",
                "qty": 24,
                "price": 17,
                "warehouse_id": 2,
                "purchase_warehouse_id": 2,
                "purchase_policy": "one_case",
                "simple_desc": "1件48套",
                "shortage_qty": 24,
                "need_purchase": True,
            },
        ]

        result = workflow._execute_purchase(products, 2)

        purchase_call = workflow.caller.last_call("other_enter_add")
        self.assertEqual(len(purchase_call["products"]), 1)
        self.assertEqual(purchase_call["products"][0]["buy_number"], 48)
        self.assertEqual(len(result["purchase_results"]), 1)

    def test_shortage_confirmation_uses_combined_demand_for_duplicate_sku(self):
        workflow = object.__new__(OrderFlowWorkflow)
        workflow._product_tracks_inventory = lambda _product: True
        workflow._query_inventory = lambda _product_id: {"百鑫仓库": 30, "自己店里": 0}
        products = [
            {
                "product_id": 88,
                "unit_id": 1,
                "unit": "套",
                "name": "测试礼盒",
                "color": "红色",
                "qty": 20,
                "warehouse_id": 2,
            },
            {
                "product_id": 88,
                "unit_id": 1,
                "unit": "套",
                "name": "测试礼盒",
                "color": "红色",
                "qty": 20,
                "warehouse_id": 2,
            },
        ]

        result = workflow._purchase_confirmation_for_shortage(7, "测试客户", products, 2)

        self.assertIsNotNone(result)
        purchase_products = result["state"]["purchase_products"]
        self.assertEqual(len(purchase_products), 1)
        self.assertEqual(purchase_products[0]["qty"], 40)
        self.assertEqual(purchase_products[0]["shortage_qty"], 10)

    def test_sales_rows_with_different_price_or_warehouse_remain_separate(self):
        workflow = object.__new__(OrderFlowWorkflow)
        products = [
            {"product_id": 88, "unit_id": 1, "color": "红色", "qty": 2, "price": 17, "warehouse_id": 2},
            {"product_id": 88, "unit_id": 1, "color": "红色", "qty": 3, "price": 18, "warehouse_id": 2},
            {"product_id": 88, "unit_id": 1, "color": "红色", "qty": 4, "price": 17, "warehouse_id": 1},
        ]

        merged = workflow._merge_sales_products(products)

        self.assertEqual([item["qty"] for item in merged], [2, 3, 4])

    def test_auto_purchase_order_reply_contains_compact_purchase_result(self):
        workflow = object.__new__(OrderFlowWorkflow)
        workflow.caller = FakePurchaseOrderCaller()
        state = {
            "pending_action": "confirm_create_order",
            "customer_id": 7,
            "customer_name": "测试客户",
            "warehouse_id": 2,
            "auto_purchase": True,
            "products": [
                {
                    "product_id": 88,
                    "unit_id": 1,
                    "unit": "套",
                    "name": "【墨香】半斤",
                    "color": "黄色",
                    "qty": 10,
                    "price": 27,
                    "warehouse_id": 2,
                    "purchase_warehouse_id": 2,
                    "purchase_qty": 10,
                    "purchase_unit": "套",
                    "need_purchase": True,
                }
            ],
        }

        result = workflow.resume("确认", state)

        notice = "商品：墨香半斤\n颜色：黄色\n进货：10套\n备注：送至百鑫"
        self.assertIn(notice, result["reply"])
        self.assertNotIn("【进货结果】", result["reply"])
        self.assertLess(result["reply"].index("商品：墨香半斤"), result["reply"].index("开单成功"))
        self.assertEqual(workflow.caller.last_call("other_enter_add")["note"], "送至百鑫")

    def test_piece_purchase_result_omits_per_piece_description(self):
        workflow = object.__new__(OrderFlowWorkflow)

        quantity = workflow._purchase_result_quantity({
            "purchase_qty": 1,
            "purchase_unit": "件",
            "per_piece": 24,
        })

        self.assertEqual(quantity, "1件")

    def test_multiple_purchase_results_render_each_product_separately(self):
        workflow = object.__new__(OrderFlowWorkflow)

        result = workflow._format_purchase_results([
            {"product": "墨香半斤", "color": "黄色", "quantity": "10套", "note": "送至百鑫"},
            {"product": "喜悦半斤", "color": "红色", "quantity": "5套", "note": "送至百鑫"},
        ])

        self.assertEqual(
            result,
            "商品：墨香半斤\n颜色：黄色\n进货：10套\n备注：送至百鑫"
            "\n\n"
            "商品：喜悦半斤\n颜色：红色\n进货：5套\n备注：送至百鑫",
        )
        self.assertEqual(result.count("商品："), 2)
        self.assertEqual(result.count("备注："), 2)

    def test_order_flow_passes_workflow_order_id_to_sales_add_after_confirm(self):
        workflow = object.__new__(OrderFlowWorkflow)
        workflow.caller = FakeOrderCaller()
        state = {
            "pending_action": "confirm_create_order",
            "customer_id": 7,
            "customer_name": "测试客户",
            "warehouse_id": 2,
            "skip_inventory": True,
            "workflow_order_id": 456,
            "products": [
                {
                    "product_id": 88,
                    "unit_id": 1,
                    "unit": "套",
                    "name": "测试礼盒",
                    "qty": 2,
                    "price": 10,
                    "warehouse_id": 2,
                }
            ],
        }

        result = workflow.resume("ok", state)

        self.assertIn("reply", result)
        sales_call = workflow.caller.last_call("sales_add")
        self.assertEqual(sales_call["workflow_order_id"], 456)

    def test_order_flow_passes_all_workflow_order_ids_to_sales_add_after_confirm(self):
        workflow = object.__new__(OrderFlowWorkflow)
        workflow.caller = FakeOrderCaller()
        state = {
            "pending_action": "confirm_create_order",
            "customer_id": 7,
            "customer_name": "测试客户",
            "warehouse_id": 2,
            "skip_inventory": True,
            "workflow_order_id": 456,
            "workflow_order_ids": [456, 457],
            "products": [
                {
                    "product_id": 88,
                    "unit_id": 1,
                    "unit": "套",
                    "name": "测试礼盒",
                    "qty": 2,
                    "price": 10,
                    "warehouse_id": 2,
                }
            ],
        }

        workflow.resume("确认", state)

        sales_call = workflow.caller.last_call("sales_add")
        self.assertEqual(sales_call["workflow_order_ids"], [456, 457])

    def test_shortage_confirmation_keeps_all_workflow_order_ids(self):
        workflow = object.__new__(OrderFlowWorkflow)
        workflow._product_tracks_inventory = lambda _product: True
        workflow._query_inventory = lambda _product_id: {"百鑫仓库": 0, "自己店里": 0}
        product = {"product_id": 88, "name": "测试礼盒", "qty": 2, "warehouse_id": 2}

        result = workflow._purchase_confirmation_for_shortage(
            7,
            "测试客户",
            [product],
            2,
            workflow_order_ids=[456, 457],
        )

        self.assertEqual(result["state"]["workflow_order_ids"], [456, 457])

    def test_image_workflow_passes_created_workflow_id_to_order_flow(self):
        captured_params = []

        class FakeOrderFlow:
            def execute(self, user_input, params=None):
                captured_params.append(dict(params or {}))
                return {"status": "ask", "question": "confirm", "state": {}}

        workflow = WorkflowOrderWorkflow()
        workflow.caller = FakeWorkflowCaller()
        state = {
            "pending_action": "confirm_image_workflow_orders",
            "parsed_list": [
                {"customer": "测试客户", "goods_name": "测试礼盒", "quantity": 2, "color": "红色"}
            ],
            "order_params": {
                "products": [{"product_id": 88, "name": "测试礼盒", "qty": 2}],
            },
        }

        with patch("src.skills.order_flow.workflow.OrderFlowWorkflow", FakeOrderFlow):
            result = workflow.resume("ok", state)

        self.assertEqual(result["status"], "ask")
        self.assertEqual(captured_params[0]["workflow_order_id"], 456)
        self.assertEqual(captured_params[0]["customer"], "测试客户")

    @patch("src.services.business.workflow.get_workflow_service")
    @patch("src.skills.order_flow.workflow.OrderFlowWorkflow")
    def test_image_workflow_correction_cancel_creates_nothing(self, sales, service):
        service.return_value.find_saved_batch.return_value = []
        workflow = WorkflowOrderWorkflow()
        workflow.caller = FakeCorrectionCaller()

        result = workflow.resume(
            "取消",
            {
                "pending_action": "confirm_image_workflow_correction",
                "customer_name": "测试客户",
                "parsed_list": [
                    {"product_id": 88, "customer": "测试客户", "goods_name": "礼盒A", "color": "红色", "quantity": 2}
                ],
            },
        )

        self.assertEqual(workflow.caller.calls, [])
        self.assertIn("没有写入系统", result["reply"])
        service.assert_not_called()
        sales.assert_not_called()

    @patch("src.services.business.workflow.get_workflow_service")
    @patch("src.skills.order_flow.workflow.OrderFlowWorkflow")
    def test_image_workflow_correction_cannot_be_confirmed_from_chat_while_a_row_is_incomplete(self, sales, service):
        service.return_value.find_saved_batch.return_value = []
        workflow = WorkflowOrderWorkflow()
        workflow.caller = FakeCorrectionCaller()

        result = workflow.resume(
            "确认",
            {
                "pending_action": "confirm_image_workflow_correction",
                "customer_name": "测试客户",
                "parsed_list": [
                    {"product_id": 88, "customer": "测试客户", "goods_name": "礼盒A", "color": "红色", "quantity": 2},
                    {
                        "customer": "测试客户",
                        "goods_name": "礼盒B",
                        "color": "黄色",
                        "quantity": 1,
                        "source_filename": "design-2.png",
                    },
                ],
            },
        )

        self.assertEqual(result["status"], "ask")
        self.assertIn("第 2 张", result["question"])
        self.assertIn("商品", result["question"])
        self.assertEqual(workflow.caller.calls, [("product_info", {"product_id": 88})])
        service.assert_not_called()
        sales.assert_not_called()

    @patch("src.services.business.workflow.get_workflow_service")
    def test_image_workflow_correction_links_every_created_workflow_to_sales(self, service):
        service.return_value.find_saved_batch.return_value = []
        captured_params = []
        service.return_value.save_orders_batch.return_value = {
            "code": 0, "data": [{"id": 456}, {"id": 457}],
        }

        class FakeOrderFlow:
            def execute(self, user_input, params=None):
                service.return_value.save_orders_batch.assert_called_once()
                captured_params.append(dict(params or {}))
                return {"status": "ask", "question": "confirm", "state": {}}

        workflow = WorkflowOrderWorkflow()
        workflow.caller = FakeCorrectionCaller()
        state = {
            "pending_action": "confirm_image_workflow_correction",
            "correction_batch_id": "correction-linking",
            "customer_name": "测试客户",
            "parsed_list": [
                {"selected_sku_id": 88, "customer": "测试客户", "goods_name": "旧名称A", "quantity": 2, "color": "黄色",
                 "order_images": ["https://example.test/one.png"]},
                {"product_id": 89, "customer": "测试客户", "goods_name": "旧名称B", "quantity": 3, "color": "黄色",
                 "order_images": ["https://example.test/two.png"]},
            ],
            "order_params": {
                "customer": "测试客户",
                "products": [
                    {"name": "礼盒A", "qty": 2, "color": "红色"},
                    {"name": "礼盒B", "qty": 3, "color": "蓝色"},
                ],
            },
        }

        with patch("src.skills.order_flow.workflow.OrderFlowWorkflow", FakeOrderFlow):
            result = workflow.resume("确认", state)

        self.assertEqual(result["status"], "ask")
        self.assertEqual(captured_params[0]["workflow_order_id"], 456)
        self.assertEqual(captured_params[0]["workflow_order_ids"], [456, 457])
        self.assertEqual(result["state"]["workflow_order_ids"], [456, 457])
        self.assertEqual([row["product_id"] for row in captured_params[0]["products"]], [88, 89])
        self.assertEqual([row["name"] for row in captured_params[0]["products"]], ["礼盒A", "礼盒B"])
        self.assertEqual(workflow.caller.calls, [
            ("product_info", {"product_id": 88}), ("product_info", {"product_id": 89}),
        ])
        service.return_value.save_orders_batch.assert_called_once_with(
            service.return_value.save_orders_batch.call_args.args[0], batch_id="correction-linking",
        )
        rows = service.return_value.save_orders_batch.call_args.args[0]
        self.assertEqual([row["product_id"] for row in rows], [88, 89])
        self.assertEqual([row["goods_name"] for row in rows], ["礼盒A", "礼盒B"])
        self.assertEqual([row["color"] for row in rows], ["红色", "蓝色"])
        self.assertEqual([row["quantity"] for row in rows], [2, 3])

    @patch("src.services.business.workflow.get_workflow_service")
    def test_image_workflow_correction_uploads_failed_design_before_creating(self, service):
        service.return_value.find_saved_batch.return_value = []
        captured_params = []

        class FakeOrderFlow:
            def execute(self, user_input, params=None):
                service.return_value.save_orders_batch.assert_called_once()
                captured_params.append(dict(params or {}))
                return {"status": "ask", "question": "confirm", "state": {}}

        workflow = WorkflowOrderWorkflow()
        workflow.caller = FakeCorrectionCaller()
        state = {
            "pending_action": "confirm_image_workflow_correction",
            "correction_batch_id": "correction-upload",
            "customer_name": "测试客户",
            "parsed_list": [{
                "selected_sku_id": 88,
                "customer": "测试客户",
                "goods_name": "礼盒A",
                "color": "红色",
                "quantity": 2,
                "source_filename": "design-1.png",
                "source_image_path": "C:/temp/design-1.png",
                "order_images": [],
            }],
            "order_params": {
                "customer": "测试客户",
                "products": [{"name": "礼盒A", "qty": 2, "color": "红色"}],
            },
        }
        original = deepcopy(state)

        def save_batch(rows, *, batch_id):
            self.assertEqual(workflow.caller.calls, [
                ("product_info", {"product_id": 88}),
                ("script_call", {"script_name": "oss_uploader.py", "args": ["C:/temp/design-1.png"]}),
            ])
            self.assertEqual(rows[0]["order_images"], ["https://example.test/corrected.png"])
            return {"code": 0, "data": [{"id": 456}]}

        service.return_value.save_orders_batch.side_effect = save_batch

        with patch("src.skills.order_flow.workflow.OrderFlowWorkflow", FakeOrderFlow):
            result = workflow.resume("确认", state)

        self.assertEqual(result["status"], "ask")
        rows = service.return_value.save_orders_batch.call_args.args[0]
        service.return_value.save_orders_batch.assert_called_once_with(
            rows, batch_id="correction-upload",
        )
        self.assertEqual(rows[0]["product_id"], 88)
        self.assertEqual(rows[0]["source_image_path"], "C:/temp/design-1.png")
        self.assertEqual(rows[0]["source_filename"], "design-1.png")
        self.assertEqual(state, original)
        self.assertEqual(captured_params[0]["workflow_order_ids"], [456])
        self.assertEqual(captured_params[0]["products"][0]["product_id"], 88)

    @patch("src.services.business.workflow.get_workflow_service")
    @patch("src.skills.order_flow.workflow.OrderFlowWorkflow")
    def test_image_workflow_correction_stops_before_database_when_image_upload_fails(self, sales, service):
        service.return_value.find_saved_batch.return_value = []
        workflow = WorkflowOrderWorkflow()
        workflow.caller = FakeCorrectionCaller(upload_result={"error": "upload failed"})
        state = {
            "pending_action": "confirm_image_workflow_correction",
            "customer_name": "测试客户",
            "parsed_list": [{
                "product_id": 88,
                "customer": "测试客户",
                "goods_name": "礼盒A",
                "color": "红色",
                "quantity": 2,
                "source_filename": "design-1.png",
                "source_image_path": "C:/temp/design-1.png",
                "order_images": [],
            }],
            "order_params": {
                "customer": "测试客户",
                "products": [{"name": "礼盒A", "qty": 2, "color": "红色"}],
            },
        }

        result = workflow.resume("确认", state)

        self.assertEqual(result["status"], "ask")
        self.assertIn("图片上传失败", result["question"])
        self.assertEqual([name for name, _ in workflow.caller.calls], ["product_info", "script_call"])
        service.assert_not_called()
        sales.assert_not_called()

    @patch("src.services.business.workflow.get_workflow_service")
    @patch("src.skills.order_flow.workflow.OrderFlowWorkflow")
    def test_image_workflow_correction_revalidates_selected_sku_before_any_writes(self, sales, service):
        service.return_value.find_saved_batch.return_value = []
        workflow = WorkflowOrderWorkflow()
        workflow.caller = FakeCorrectionCaller()
        workflow.caller.products[88]["status"] = "inactive"
        result = workflow.resume("确认", {
            "pending_action": "confirm_image_workflow_correction",
            "customer_name": "测试客户",
            "parsed_list": [{
                "product_id": 88, "goods_name": "礼盒A", "color": "红色", "quantity": 2,
                "source_image_path": "C:/temp/design-1.png", "order_images": [],
            }],
        })
        self.assertEqual(result["status"], "ask")
        self.assertIn("不可用", result["question"])
        self.assertEqual(workflow.caller.calls, [("product_info", {"product_id": 88})])
        service.assert_not_called()
        sales.assert_not_called()

    @patch("src.services.business.workflow.get_workflow_service")
    @patch("src.skills.order_flow.workflow.OrderFlowWorkflow")
    def test_image_workflow_correction_batch_save_failure_never_enters_sales(self, sales, service):
        service.return_value.find_saved_batch.return_value = []
        state = {
            "pending_action": "confirm_image_workflow_correction",
            "correction_batch_id": "correction-save-failure",
            "customer_name": "测试客户",
            "parsed_list": [
                {"product_id": 88, "quantity": 2, "order_images": ["https://example.test/one.png"]},
                {"product_id": 89, "quantity": 3, "order_images": ["https://example.test/two.png"]},
            ],
        }
        for saved in (
            {"code": 1, "msg": "transaction failed", "data": []},
            {"code": 0, "data": [{"id": 456}]},
        ):
            with self.subTest(saved=saved):
                service.reset_mock()
                service.return_value.save_orders_batch.return_value = saved
                workflow = WorkflowOrderWorkflow()
                workflow.caller = FakeCorrectionCaller()
                result = workflow.resume("确认", deepcopy(state))
                self.assertEqual(result["status"], "ask")
                self.assertIn("未保存成功", result["question"])
                rows = service.return_value.save_orders_batch.call_args.args[0]
                service.return_value.save_orders_batch.assert_called_once_with(
                    rows, batch_id="correction-save-failure",
                )
                self.assertEqual([row["product_id"] for row in rows], [88, 89])
                self.assertEqual(workflow.caller.calls, [
                    ("product_info", {"product_id": 88}), ("product_info", {"product_id": 89}),
                ])
                sales.assert_not_called()

    def test_order_flow_confirm_state_includes_warehouse_name_for_ui(self):
        source = (ROOT / "src" / "skills" / "order_flow" / "workflow.py").read_text(encoding="utf-8")
        confirm_source = source.split("def _confirm_create_order", 1)[1].split("def _create_order", 1)[0]

        self.assertIn('"warehouse_name": self._warehouse_name(warehouse_id)', confirm_source)


if __name__ == "__main__":
    unittest.main()
