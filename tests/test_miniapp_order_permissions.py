import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import src.channels.http_api as api_module
from src.channels.http_api.__init__ import (
    _mini_filter_public_order_rows,
    _miniapp_path_is_public,
    _mini_order_customer_id,
    _mini_order_user_can_edit,
    _mini_orderflow_empty_payload,
    _mini_orderflow_public_keyword,
    _mini_orderflow_should_query,
)


class MiniAppOrderPermissionTests(unittest.TestCase):
    def test_product_browsing_paths_are_public_for_miniapp(self):
        self.assertTrue(_miniapp_path_is_public("/api/mini/search/datalist"))
        self.assertTrue(_miniapp_path_is_public("/api/mini/goods/detail"))
        self.assertTrue(_miniapp_path_is_public("/api/mini/goods/category"))
        self.assertTrue(_miniapp_path_is_public("/api/mini/home"))
        self.assertFalse(_miniapp_path_is_public("/api/mini/user"))
        self.assertFalse(_miniapp_path_is_public("/api/mini/orderflow/list"))
        self.assertFalse(_miniapp_path_is_public("/api/mini/inventory/list"))
        self.assertFalse(_miniapp_path_is_public("/api/mini/workflow-order/search"))
        self.assertFalse(_miniapp_path_is_public("/api/mini/workflow-order/inventory-search"))

    def test_only_staff_and_admin_can_edit_orders(self):
        self.assertFalse(_mini_order_user_can_edit(None))
        self.assertFalse(_mini_order_user_can_edit({"role": "customer", "is_admin": 0}))
        self.assertTrue(_mini_order_user_can_edit({"role": "staff", "is_admin": 0}))
        self.assertTrue(_mini_order_user_can_edit({"role": "admin", "is_admin": 0}))
        self.assertTrue(_mini_order_user_can_edit({"role": "customer", "is_admin": 1}))

    def test_linked_customers_can_query_their_own_orders_without_keyword(self):
        self.assertIsNone(_mini_order_customer_id(None))
        self.assertIsNone(_mini_order_customer_id({"role": "customer"}))
        self.assertEqual(_mini_order_customer_id({"role": "customer", "linked_party_id": 55}), 55)
        self.assertFalse(_mini_orderflow_should_query("", None))
        self.assertFalse(_mini_orderflow_should_query("   ", {"role": "customer"}))
        self.assertTrue(_mini_orderflow_should_query("", {"role": "customer", "linked_party_id": 55}))
        self.assertTrue(_mini_orderflow_should_query("岩韵", {"role": "customer", "linked_party_id": 55}))
        self.assertTrue(_mini_orderflow_should_query("", {"role": "staff"}))

    def test_public_order_search_requires_exact_order_number(self):
        self.assertFalse(_mini_orderflow_should_query("见喜", None))
        self.assertFalse(_mini_orderflow_should_query("SJ", None))
        self.assertFalse(_mini_orderflow_should_query("SJ1123", None))
        self.assertFalse(_mini_orderflow_should_query("客户名称", {"role": "customer"}))
        self.assertTrue(_mini_orderflow_public_keyword("1000025"))
        self.assertTrue(_mini_orderflow_public_keyword("WF202605280001"))
        self.assertFalse(_mini_orderflow_should_query("1000025", None))
        self.assertFalse(_mini_orderflow_should_query("XSD202605280001", {"role": "customer"}))

    def test_public_exact_search_filters_fuzzy_order_results(self):
        rows = [
            {"id": 1000025, "order_no": "WF202605280001", "goods_name": "见喜半斤"},
            {"id": 1000026, "order_no": "WF202605280002", "goods_name": "见喜三两"},
            {"sales_no": "XSD202605280001", "customer_name": "好照"},
        ]
        self.assertEqual(
            _mini_filter_public_order_rows(rows, "WF202605280001"),
            [{"id": 1000025, "order_no": "WF202605280001", "goods_name": "见喜半斤"}],
        )
        self.assertEqual(
            _mini_filter_public_order_rows(rows, "1000025"),
            [{"id": 1000025, "order_no": "WF202605280001", "goods_name": "见喜半斤"}],
        )
        self.assertEqual(
            _mini_filter_public_order_rows(rows, "XSD202605280001"),
            [{"sales_no": "XSD202605280001", "customer_name": "好照"}],
        )

    def test_private_legacy_workflow_search_allows_authenticated_staff(self):
        rows = [
            {"id": 1000025, "order_no": "WF202605280001", "goods_name": "match"},
            {"id": 1000026, "order_no": "WF202605280002", "goods_name": "nearby"},
        ]
        original_db_workflow_orders = api_module._db_workflow_orders
        original_request_user = api_module._mini_request_user
        original_verify_native_token = api_module._verify_native_token
        try:
            def fake_db_workflow_orders(keyword, page, page_size, status_filter, customer_id=None):
                return rows, len(rows)

            api_module._db_workflow_orders = fake_db_workflow_orders
            api_module._mini_request_user = lambda: {
                "role": "staff",
                "id": 7,
                "is_active": 1,
                "approval_status": "approved",
                "miniapp_allowed": True,
            }
            api_module._verify_native_token = lambda token: {
                "role": "staff",
                "id": 7,
                "is_active": 1,
                "approval_status": "approved",
                "miniapp_allowed": True,
            }
            with api_module.app.test_client() as client:
                response = client.get(
                    "/api/mini/workflow-order/search?keyword=WF202605280001",
                    headers={"X-SJ-Token": "valid-token"},
                )
            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertEqual(payload["code"], 0)
            self.assertEqual(payload["data"], rows)
        finally:
            api_module._db_workflow_orders = original_db_workflow_orders
            api_module._mini_request_user = original_request_user
            api_module._verify_native_token = original_verify_native_token

    def test_private_mini_orderflow_requires_token_even_without_client_header(self):
        with api_module.app.test_client() as client:
            response = client.get("/api/mini/orderflow/list?keyword=WF202605280001")
        self.assertEqual(response.status_code, 401)

    def test_private_mini_orderflow_requires_token_with_client_header(self):
        with api_module.app.test_client() as client:
            response = client.get(
                "/api/mini/orderflow/list?keyword=WF202605280001",
                headers={"X-SJ-Client": "miniapp"},
            )
        self.assertEqual(response.status_code, 401)

    def test_mini_orderflow_keyword_searches_all_workflow_statuses(self):
        captured = {}
        original_db_workflow_orders = api_module._db_workflow_orders
        original_db_sales_cards = api_module._db_sales_cards
        original_verify_native_token = api_module._verify_native_token
        try:
            api_module._verify_native_token = lambda token: {
                "role": "staff",
                "id": 7,
                "is_active": 1,
                "approval_status": "approved",
                "miniapp_allowed": True,
            }

            def fake_db_workflow_orders(keyword, page, page_size, status_filter, customer_id=None):
                captured["status_filter"] = status_filter
                return [{"id": 1000024, "order_no": "1000024", "status": "completed"}], 1

            api_module._db_workflow_orders = fake_db_workflow_orders
            api_module._db_sales_cards = lambda *args, **kwargs: ([], 0)
            with api_module.app.test_client() as client:
                response = client.get(
                    "/api/mini/orderflow/list?keyword=1000024",
                    headers={"X-SJ-Token": "valid-token"},
                )

            self.assertEqual(response.status_code, 200)
            self.assertEqual(captured["status_filter"], "all")
        finally:
            api_module._db_workflow_orders = original_db_workflow_orders
            api_module._db_sales_cards = original_db_sales_cards
            api_module._verify_native_token = original_verify_native_token

    def test_unbound_customer_cannot_use_exact_order_number_as_public_lookup(self):
        original_db_workflow_orders = api_module._db_workflow_orders
        original_db_sales_cards = api_module._db_sales_cards
        original_verify_native_token = api_module._verify_native_token
        try:
            api_module._verify_native_token = lambda token: {
                "role": "customer",
                "id": 8,
                "linked_party_id": None,
                "is_active": 1,
                "approval_status": "approved",
                "miniapp_allowed": True,
            }
            api_module._db_workflow_orders = lambda *args, **kwargs: (
                [{"id": 1000025, "order_no": "WF202605280001"}],
                1,
            )
            api_module._db_sales_cards = lambda *args, **kwargs: (
                [{"sales_no": "XSD202605280001"}],
                1,
            )
            with api_module.app.test_client() as client:
                response = client.get(
                    "/api/mini/orderflow/list?keyword=WF202605280001",
                    headers={"X-SJ-Token": "valid-token"},
                )
            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertEqual(payload["code"], 0)
            self.assertEqual(payload["data"]["total"], 0)
            self.assertEqual(payload["data"]["workflows"], [])
            self.assertEqual(payload["data"]["sales"], [])
        finally:
            api_module._db_workflow_orders = original_db_workflow_orders
            api_module._db_sales_cards = original_db_sales_cards
            api_module._verify_native_token = original_verify_native_token

    def test_customer_role_cannot_use_staff_inventory_or_customer_lookup(self):
        original_inventory_payload = api_module._mini_workflow_inventory_payload
        original_workflow_order_list = api_module._mini_workflow_order_list
        original_verify_native_token = api_module._verify_native_token
        try:
            api_module._verify_native_token = lambda token: {
                "role": "customer",
                "id": 8,
                "linked_party_id": 55,
                "is_active": 1,
                "approval_status": "approved",
                "miniapp_allowed": True,
            }
            api_module._mini_workflow_inventory_payload = lambda keyword="": {"items": [{"id": 1}]}
            api_module._mini_workflow_order_list = lambda *args, **kwargs: ([{"id": 2}], 1)

            with api_module.app.test_client() as client:
                inventory_response = client.get(
                    "/api/mini/workflow-order/inventory-search?keyword=岩彩",
                    headers={"X-SJ-Token": "valid-token"},
                )
                inventory_list_response = client.get(
                    "/api/mini/inventory/list?keyword=岩彩",
                    headers={"X-SJ-Token": "valid-token"},
                )
                customer_response = client.get(
                    "/api/mini/workflow-order/customer-list?nickname=齐唯",
                    headers={"X-SJ-Token": "valid-token"},
                )

            self.assertEqual(inventory_response.status_code, 403)
            self.assertEqual(inventory_list_response.status_code, 403)
            self.assertEqual(customer_response.status_code, 403)
        finally:
            api_module._mini_workflow_inventory_payload = original_inventory_payload
            api_module._mini_workflow_order_list = original_workflow_order_list
            api_module._verify_native_token = original_verify_native_token

    def test_staff_can_use_readonly_mini_inventory_list(self):
        captured = {}
        original_inventory_payload = api_module._mini_workflow_inventory_payload
        original_verify_native_token = api_module._verify_native_token
        try:
            api_module._verify_native_token = lambda token: {
                "role": "staff",
                "id": 7,
                "is_active": 1,
                "approval_status": "approved",
                "miniapp_allowed": True,
            }

            def fake_inventory_payload(keyword=""):
                captured["keyword"] = keyword
                return {
                    "items": [
                        {
                            "id": 1,
                            "code": "SJ1576",
                            "name": "六小盒",
                            "color": "红色",
                            "qty_shop": 3,
                            "qty_baixin": 6,
                            "total_qty": 9,
                        }
                    ],
                    "total_items": 1,
                    "total_qty": 9,
                    "source": "sjagent_core",
                }

            api_module._mini_workflow_inventory_payload = fake_inventory_payload

            with api_module.app.test_client() as client:
                response = client.get(
                    "/api/mini/inventory/list?keyword=百鑫半斤库存&page=2&page_size=60",
                    headers={"X-SJ-Token": "valid-token"},
                )

            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertEqual(payload["code"], 0)
            self.assertEqual(captured["keyword"], "半斤")
            self.assertEqual(payload["data"]["page"], 2)
            self.assertEqual(payload["data"]["page_size"], 60)
            self.assertEqual(payload["data"]["items"][0]["code"], "SJ1576")
            self.assertEqual(payload["data"]["total_items"], 1)
            self.assertEqual(payload["data"]["total_qty"], 9)
        finally:
            api_module._mini_workflow_inventory_payload = original_inventory_payload
            api_module._verify_native_token = original_verify_native_token

    def test_empty_payload_never_contains_order_rows(self):
        payload = _mini_orderflow_empty_payload(page=2, page_size=30)
        self.assertEqual(payload["page"], 2)
        self.assertEqual(payload["page_size"], 30)
        self.assertEqual(payload["workflows"], [])
        self.assertEqual(payload["sales"], [])
        self.assertEqual(payload["total"], 0)
        self.assertEqual(payload["source"], "sjagent_core")


if __name__ == "__main__":
    unittest.main()
