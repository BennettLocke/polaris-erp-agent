import unittest

from src.services import volc_realtime_asr


XIAONING = "\u5c0f\u5b81"
XIAONING_ALT = "\u6653\u5b81"
XIYUE_CUSTOMER = "\u559c\u60a6\u5ba2\u6237"
ZHANGSAN = "\u5f20\u4e09"
BAIXIN_PACKING = "\u767e\u946b\u5305\u88c5"
XIYUE_HALF_JIN_TITLE = "\u3010\u559c\u60a6\u3011\u534a\u65a4"
XIYUE_HALF_JIN = "\u559c\u60a6\u534a\u65a4"
XIYUE = "\u559c\u60a6"
DAHONGPAO_BAG = "\u5927\u7ea2\u888d\u957f\u6ce1\u888b"


class FakeDb:
    def query(self, sql, params=()):
        if "is_enabled" in sql:
            raise AssertionError("party hotword query must not use removed is_enabled column")
        if "FROM party" in sql:
            return [
                {"name": XIYUE_CUSTOMER, "contact_name": ZHANGSAN},
                {"name": XIAONING, "contact_name": XIAONING_ALT},
                {"name": BAIXIN_PACKING, "contact_name": ""},
            ]
        if "FROM product_spu" in sql:
            return [
                {"title": XIYUE_HALF_JIN_TITLE, "series": XIYUE},
                {"title": DAHONGPAO_BAG, "series": "\u5927\u7ea2\u888d"},
            ]
        return []


class VolcHotwordsTests(unittest.TestCase):
    def test_default_hotwords_do_not_include_xiaoning(self) -> None:
        self.assertNotIn(XIAONING, volc_realtime_asr.DEFAULT_HOTWORDS)
        self.assertNotIn(XIAONING, volc_realtime_asr._split_hotwords([XIAONING, "\u67e5\u8be2"]))
        self.assertNotIn(XIAONING_ALT, volc_realtime_asr._split_hotwords([XIAONING_ALT, "\u67e5\u8be2"]))

    def test_default_hotwords_include_price_query_words(self) -> None:
        for word in ("多少钱", "价格", "售价", "单价"):
            self.assertIn(word, volc_realtime_asr.DEFAULT_HOTWORDS)

    def test_dynamic_hotwords_use_current_party_schema_and_gift_titles(self) -> None:
        original = volc_realtime_asr.get_native_db_client
        volc_realtime_asr.get_native_db_client = lambda: FakeDb()
        try:
            words = volc_realtime_asr._fetch_dynamic_hotwords(20)
        finally:
            volc_realtime_asr.get_native_db_client = original

        self.assertIn(XIYUE_CUSTOMER, words)
        self.assertIn(ZHANGSAN, words)
        self.assertNotIn(XIAONING, words)
        self.assertNotIn(XIAONING_ALT, words)
        self.assertIn(XIYUE_HALF_JIN, words)
        self.assertIn(XIYUE, words)
        self.assertNotIn(DAHONGPAO_BAG, words)


if __name__ == "__main__":
    unittest.main()
