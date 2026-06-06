import unittest

from src.core.skill_engine import SkillEngine
from src.skills.inventory.workflow import InventoryWorkflow


class FakeInventoryCaller:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def call(self, name, **kwargs):
        self.calls.append((name, kwargs))
        if name == "inventory_search":
            return self.rows
        return []


class InventoryNaturalQueryContractTest(unittest.TestCase):
    def test_fast_inventory_extracts_spec_color_without_series(self):
        engine = object.__new__(SkillEngine)

        result = engine._extract_inventory_params("三两红色还有吗")

        self.assertEqual(result, {"intent": "inventory", "color": "红色", "product_name": "二三两"})

    def test_fast_inventory_without_warehouse_keeps_lookup_unscoped(self):
        engine = object.__new__(SkillEngine)

        result = engine._extract_inventory_params("喜悦半斤库存")

        self.assertEqual(result["intent"], "inventory")
        self.assertEqual(result["product_name"].replace(" ", ""), "喜悦半斤")
        self.assertNotIn("warehouse_id", result)

    def test_fast_inventory_extracts_warehouse_spec_and_color(self):
        engine = object.__new__(SkillEngine)

        result = engine._extract_inventory_params("查百鑫三两红色库存")

        self.assertEqual(
            result,
            {
                "intent": "inventory",
                "warehouse": "百鑫仓库",
                "warehouse_id": 2,
                "color": "红色",
                "product_name": "二三两",
            },
        )

    def test_inventory_query_passes_warehouse_filter_to_search(self):
        workflow = InventoryWorkflow.__new__(InventoryWorkflow)
        caller = FakeInventoryCaller(
            [
                {
                    "产品名称": "【云岭】二三两",
                    "【颜色】": "红色",
                    "【仓库】": "百鑫仓库",
                    "库存数量": 12,
                }
            ]
        )
        workflow.caller = caller

        result = workflow.execute(
            "查百鑫三两红色库存",
            {"product_name": "二三两", "color": "红色", "warehouse": "百鑫仓库", "warehouse_id": 2},
        )

        self.assertEqual(
            caller.calls[0],
            (
                "inventory_search",
                {"keyword": "二三两", "color": "红色", "warehouse_id": 2, "only_in_stock": True, "limit": 100},
            ),
        )
        self.assertIn("百鑫仓库", result["reply"])
        self.assertIn("【云岭】二三两", result["reply"])


if __name__ == "__main__":
    unittest.main()
