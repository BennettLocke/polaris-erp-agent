import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.business.miniapp import MiniAppService


class MiniAppCustomerIsolationTests(unittest.TestCase):
    def test_user_center_counts_are_scoped_to_linked_customer(self):
        class FakeDB:
            def __init__(self):
                self.calls = []

            def workflow_orders(self, **kwargs):
                self.calls.append(("workflow_orders", kwargs))
                return [], 5 if kwargs.get("customer_id") == 55 else 99

            def sales_cards(self, **kwargs):
                self.calls.append(("sales_cards", kwargs))
                return [], 7 if kwargs.get("customer_id") == 55 else 99

        db = FakeDB()
        payload = MiniAppService(db=db).user_center_payload({
            "role": "customer",
            "linked_party_id": 55,
            "is_admin": 0,
        })

        self.assertEqual(payload["user_order_count"], 12)
        self.assertEqual(payload["user_order_status"][1]["count"], 5)
        self.assertEqual(payload["user_order_status"][2]["count"], 7)
        self.assertEqual(db.calls[0][1]["customer_id"], 55)
        self.assertEqual(db.calls[1][1]["customer_id"], 55)

    def test_user_center_keeps_staff_global_counts(self):
        class FakeDB:
            def __init__(self):
                self.calls = []

            def workflow_orders(self, **kwargs):
                self.calls.append(("workflow_orders", kwargs))
                return [], 11

            def sales_cards(self, **kwargs):
                self.calls.append(("sales_cards", kwargs))
                return [], 13

        db = FakeDB()
        payload = MiniAppService(db=db).user_center_payload({
            "role": "staff",
            "is_admin": 0,
        })

        self.assertEqual(payload["user_order_count"], 24)
        self.assertIsNone(db.calls[0][1].get("customer_id"))
        self.assertIsNone(db.calls[1][1].get("customer_id"))

    def test_user_center_unbound_customer_does_not_fall_back_to_global_counts(self):
        class FakeDB:
            def workflow_orders(self, **kwargs):
                raise AssertionError("unbound customer must not query global workflow orders")

            def sales_cards(self, **kwargs):
                raise AssertionError("unbound customer must not query global sales orders")

        payload = MiniAppService(db=FakeDB()).user_center_payload({
            "role": "customer",
            "is_admin": 0,
        })

        self.assertEqual(payload["user_order_count"], 0)
        self.assertEqual(payload["user_order_status"][0]["count"], 0)


if __name__ == "__main__":
    unittest.main()
