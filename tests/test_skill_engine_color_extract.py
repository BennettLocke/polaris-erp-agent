from src.core.skill_engine import SkillEngine


def test_fast_stocktaking_extracts_khaki_color():
    engine = object.__new__(SkillEngine)
    result = engine._extract_stocktaking_params("盘点 岩彩3小盒卡其色 39套 自己店里")
    assert result["warehouse"] == "自己店里"
    assert result["products"] == [
        {"name": "岩彩 三小盒", "quantity": 39, "unit": "套", "color": "卡其色"}
    ]


def test_fast_inventory_extracts_khaki_color():
    engine = object.__new__(SkillEngine)
    result = engine._extract_inventory_params("查 岩彩3小盒卡其色库存")
    assert result == {"intent": "inventory", "color": "卡其色", "product_name": "岩彩 三小盒"}


def test_fast_inventory_extracts_spec_color_without_series():
    engine = object.__new__(SkillEngine)

    result = engine._extract_inventory_params("三两红色还有吗")

    assert result == {"intent": "inventory", "color": "红色", "product_name": "二三两"}


def test_fast_inventory_extracts_warehouse_spec_and_color():
    engine = object.__new__(SkillEngine)

    result = engine._extract_inventory_params("查百鑫三两红色库存")

    assert result == {
        "intent": "inventory",
        "warehouse": "百鑫仓库",
        "warehouse_id": 2,
        "color": "红色",
        "product_name": "二三两",
    }
