import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.business.sales import SalesService


class PricingDB:
    def __init__(self, *, category_name="半斤礼盒", product_type="gift_box", history=None, setting=None):
        self.category_name = category_name
        self.product_type = product_type
        self.history = history or []
        self.setting = setting or {}
        self.calls = []

    def product_info(self, product_id: int, *, listed_only: bool = False):
        self.calls.append(("product_info", product_id))
        return {"id": product_id, "unit_id": 1}

    def system_setting(self, key: str):
        self.calls.append(("system_setting", key))
        return {"code": 0, "data": {"key": key, "value": self.setting}}

    def sales_price_context(self, customer_id: int, product_id: int, *, limit: int = 10):
        self.calls.append(("sales_price_context", customer_id, product_id, limit))
        return {
            "sku": {
                "id": product_id,
                "spu_id": 91,
                "title": "【喜悦】半斤",
                "color": "红色",
                "unit_id": 1,
                "unit_name": "套",
                "category_id": 7,
                "category_name": self.category_name,
                "product_type": self.product_type,
                "retail_price": "22.00",
            },
            "history": list(self.history),
        }

    def create_sales_order(self, **kwargs):
        self.calls.append(("create_sales_order", kwargs))
        return {"code": 0, "data": {"id": 123, "products": kwargs["products"]}}


def history(price, *, days_ago=10, quantity=20, remember=1, item_id=501, unit_id=1):
    return {
        "item_id": item_id,
        "sales_no": "SO202609010001",
        "unit_price": price,
        "quantity": quantity,
        "unit_id": unit_id,
        "unit_name": "套",
        "sales_at": f"days:{days_ago}",
        "age_days": days_ago,
        "remember_price": remember,
    }


class CustomerHistoryPricingTest(unittest.TestCase):
    def test_stable_gift_box_automatically_uses_valid_history_price(self):
        service = SalesService(db=PricingDB(history=[history("21.00")]))

        result = service.price_preview(customer_id=8, product_id=10, quantity=5, unit_id=1)

        self.assertEqual(result["price"], 21.0)
        self.assertEqual(result["source"], "customer_history")
        self.assertEqual(result["policy"], "auto")
        self.assertEqual(result["history"]["item_id"], 501)
        self.assertTrue(result["remember_default"])

    def test_quantity_sensitive_category_only_suggests_history_price(self):
        service = SalesService(db=PricingDB(category_name="2泡小盒", history=[history("3.50")]))

        result = service.price_preview(customer_id=8, product_id=10, quantity=200, unit_id=1)

        self.assertEqual(result["price"], 22.0)
        self.assertEqual(result["source"], "retail_price")
        self.assertEqual(result["policy"], "suggest")
        self.assertEqual(result["history"]["price"], 3.5)
        self.assertFalse(result["remember_default"])

    def test_bag_category_does_not_read_customer_history(self):
        service = SalesService(db=PricingDB(category_name="水仙泡袋", product_type="bag", history=[history("0.12")]))

        result = service.price_preview(customer_id=8, product_id=10, quantity=100, unit_id=1)

        self.assertEqual(result["price"], 22.0)
        self.assertEqual(result["source"], "retail_price")
        self.assertEqual(result["policy"], "off")
        self.assertIsNone(result["history"])

    def test_other_products_default_to_no_memory(self):
        service = SalesService(db=PricingDB(category_name="其他产品", product_type="other", history=[history("12.00")]))

        result = service.price_preview(customer_id=8, product_id=10, quantity=1, unit_id=1)

        self.assertEqual(result["policy"], "off")
        self.assertIsNone(result["history"])

    def test_zero_and_nonremembered_rows_are_skipped(self):
        rows = [
            history("0.00", days_ago=1, item_id=503),
            history("20.00", days_ago=2, remember=0, item_id=502),
            history("21.00", days_ago=3, item_id=501),
        ]
        service = SalesService(db=PricingDB(history=rows))

        result = service.price_preview(customer_id=8, product_id=10, quantity=5, unit_id=1)

        self.assertEqual(result["price"], 21.0)
        self.assertEqual(result["history"]["item_id"], 501)

    def test_expired_or_extreme_history_is_reference_only(self):
        for row in (history("21.00", days_ago=181), history("5.00", days_ago=5)):
            with self.subTest(row=row):
                service = SalesService(db=PricingDB(history=[row]))
                result = service.price_preview(customer_id=8, product_id=10, quantity=5, unit_id=1)
                self.assertEqual(result["price"], 22.0)
                self.assertEqual(result["source"], "retail_price")
                self.assertEqual(result["effective_policy"], "suggest")
                self.assertTrue(result["warnings"])

    def test_create_order_marks_manual_override_and_respects_remember_choice(self):
        db = PricingDB(history=[history("21.00")])
        service = SalesService(db=db)

        service.create_order(
            customer_id=8,
            warehouse_id=2,
            products=[{
                "product_id": 10,
                "unit_id": 1,
                "buy_number": 5,
                "price": 19,
                "remember_price": False,
            }],
        )

        saved = next(call[1] for call in db.calls if call[0] == "create_sales_order")["products"][0]
        self.assertEqual(saved["price_source"], "manual_override")
        self.assertEqual(saved["remember_price"], 0)
        self.assertIsNone(saved["price_reference_item_id"])

    def test_legacy_caller_price_is_classified_by_the_same_policy(self):
        db = PricingDB(history=[history("21.00")])
        service = SalesService(db=db)

        service.create_order(
            customer_id=8,
            warehouse_id=2,
            products=[{"product_id": 10, "unit_id": 1, "buy_number": 5, "price": 21}],
        )

        saved = next(call[1] for call in db.calls if call[0] == "create_sales_order")["products"][0]
        self.assertEqual(saved["price_source"], "customer_history")
        self.assertEqual(saved["remember_price"], 1)
        self.assertEqual(saved["price_reference_item_id"], 501)


if __name__ == "__main__":
    unittest.main()
