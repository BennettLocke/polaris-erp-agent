import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.channels.http_api.__init__ import (
    _miniapp_path_is_public,
    _mini_order_user_can_edit,
    _mini_orderflow_empty_payload,
    _mini_orderflow_should_query,
)


class MiniAppOrderPermissionTests(unittest.TestCase):
    def test_product_browsing_paths_are_public_for_miniapp(self):
        self.assertTrue(_miniapp_path_is_public("/api/mini/search/datalist"))
        self.assertTrue(_miniapp_path_is_public("/api/mini/goods/detail"))
        self.assertTrue(_miniapp_path_is_public("/api/mini/goods/category"))
        self.assertFalse(_miniapp_path_is_public("/api/mini/user"))

    def test_only_staff_and_admin_can_edit_orders(self):
        self.assertFalse(_mini_order_user_can_edit(None))
        self.assertFalse(_mini_order_user_can_edit({"role": "customer", "is_admin": 0}))
        self.assertTrue(_mini_order_user_can_edit({"role": "staff", "is_admin": 0}))
        self.assertTrue(_mini_order_user_can_edit({"role": "admin", "is_admin": 0}))
        self.assertTrue(_mini_order_user_can_edit({"role": "customer", "is_admin": 1}))

    def test_guests_and_customers_need_keyword_to_query_orders(self):
        self.assertFalse(_mini_orderflow_should_query("", None))
        self.assertFalse(_mini_orderflow_should_query("   ", {"role": "customer"}))
        self.assertTrue(_mini_orderflow_should_query("岩韵", None))
        self.assertTrue(_mini_orderflow_should_query("", {"role": "staff"}))

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
