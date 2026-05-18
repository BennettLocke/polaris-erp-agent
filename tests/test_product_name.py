from src.core.product_name import normalize_product_name, product_terms


def test_long_half_jin_aliases_collapse_to_half_jin():
    assert normalize_product_name("见喜长款半斤黄色") == "见喜 半斤黄色"
    assert normalize_product_name("见喜长半斤") == "见喜 半斤"
    assert normalize_product_name("见喜 长 半斤") == "见喜 半斤"
    assert product_terms("见喜长款半斤") == ["见喜", "半斤"]


def test_short_half_jin_is_preserved():
    assert normalize_product_name("见喜短半斤") == "见喜 短半斤"
    assert normalize_product_name("见喜五格短半斤") == "见喜 五格短半斤"
    assert product_terms("见喜短半斤") == ["见喜", "短半斤"]


def test_liang_aliases_collapse_to_er_san_liang():
    for raw in ["见喜2两", "见喜3两", "见喜二两", "见喜三两", "见喜二三两", "见喜二 三 两"]:
        assert normalize_product_name(raw) == "见喜 二三两"
        assert product_terms(raw) == ["见喜", "二三两"]


def test_small_box_aliases_accept_digits_spaces_and_chinese():
    cases = {
        "见喜3小盒": "见喜 三小盒",
        "见喜3 小盒": "见喜 三小盒",
        "见喜三 小 盒": "见喜 三小盒",
        "见喜6小盒": "见喜 六小盒",
        "见喜六 小盒": "见喜 六小盒",
        "见喜10小盒": "见喜 十小盒",
        "见喜十 小盒": "见喜 十小盒",
    }
    for raw, expected in cases.items():
        assert normalize_product_name(raw) == expected
