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
