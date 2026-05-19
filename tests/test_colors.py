from src.core.colors import extract_color_from_text, known_colors, normalize_color


def test_extracts_configured_colors():
    assert "卡其色" in known_colors()
    assert extract_color_from_text("岩彩3小盒卡其色39套") == "卡其色"


def test_prefers_longest_color_token():
    assert extract_color_from_text("香槟金UV") == "香槟金"


def test_normalizes_common_color_aliases():
    assert normalize_color("咖啡色") == "咖色"
