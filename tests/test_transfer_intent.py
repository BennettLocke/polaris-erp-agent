import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.core.skill_engine import SkillEngine


def _engine():
    return object.__new__(SkillEngine)


def test_transfer_fast_extract_real_conversation():
    engine = _engine()

    result = engine._fast_extract("调货 【岩彩】一两 橙色 8套  百鑫仓库到自己店里")

    assert result["intent"] == "transfer"
    assert result["from"] == "百鑫"
    assert result["to"] == "自己店里"
    assert result["products"] == [
        {"name": "【岩彩】 一两", "quantity": 8, "unit": "套", "color": "橙色"}
    ]
    assert not engine._is_order_request("调货 【岩彩】一两 橙色 8套  百鑫仓库到自己店里")


def test_transfer_answer_params_merges_pending_question():
    engine = _engine()
    partial = {"from": "百鑫", "to": "自己店里"}

    result = engine._extract_answer_params("transfer", "【岩彩】一两 橙色 8套", partial)

    assert result["products"] == [
        {"name": "【岩彩】 一两", "quantity": 8, "unit": "套", "color": "橙色"}
    ]


def test_transfer_interrupts_stale_order_pending():
    engine = _engine()
    state = {"partial_params": {"customer": "调货", "products": [{"name": "", "qty": 8, "unit": "套", "color": "橙色"}]}}

    action = engine._decide_pending_action(
        "调货 【岩彩】一两 橙色 8套  百鑫仓库到自己店里",
        "order",
        state,
        [],
    )

    assert action == "new_request"
