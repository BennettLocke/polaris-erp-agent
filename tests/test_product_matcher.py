from src.core.product_matcher import ProductMatcher


class FakeCaller:
    def __init__(self):
        self.products = [
            {"id": 153, "title": "【茶派】3小盒", "spec": "红色", "simple_desc": "规格28套/件", "price": 0},
            {"id": 154, "title": "【茶派】3小盒", "spec": "黄色", "simple_desc": "规格28套/件", "price": 0},
            {"id": 23, "title": "【茶派】半斤", "spec": "红色", "simple_desc": "规格20套/件", "price": 0},
            {"id": 301, "title": "【岩彩】3小盒", "spec": "卡其色", "simple_desc": "规格28套/件", "price": 0},
        ]
        self.inventory = [
            {"product_id": 153, "产品名称": "【茶派】3小盒", "【颜色】": "红色", "【仓库】": "自己店里", "库存数量": 0},
            {"product_id": 154, "产品名称": "【茶派】3小盒", "【颜色】": "黄色", "【仓库】": "自己店里", "库存数量": 5},
            {"product_id": 23, "产品名称": "【茶派】半斤", "【颜色】": "红色", "【仓库】": "百鑫仓库", "库存数量": 10},
            {"product_id": 301, "产品名称": "【岩彩】3小盒", "【颜色】": "卡其色", "【仓库】": "自己店里", "库存数量": 39},
        ]

    def call(self, tool_name, **kwargs):
        keyword = kwargs.get("keyword", "")
        color = kwargs.get("color", "")
        if tool_name == "product_search":
            return [row for row in self.products if _matches(row["title"], keyword) and (not color or color in row["spec"])]
        if tool_name == "inventory_search":
            rows = [row for row in self.inventory if _matches(row["产品名称"], keyword) and (not color or color in row["【颜色】"])]
            if kwargs.get("only_in_stock"):
                rows = [row for row in rows if int(row["库存数量"]) > 0]
            return rows
        raise AssertionError(tool_name)


def _matches(title, keyword):
    compact_title = title.replace("【", "").replace("】", "").replace(" ", "")
    terms = [term for term in keyword.split() if term]
    return all(term.replace("三小盒", "3小盒") in compact_title or term in compact_title for term in terms)


def test_matcher_unifies_numeric_and_chinese_specs():
    matcher = ProductMatcher(FakeCaller())
    result = matcher.match("茶派 三小盒", color="红色", allow_llm=False)
    assert result.product["id"] == 153
    assert result.product["title"] == "【茶派】3小盒"


def test_matcher_keeps_ambiguous_brand_from_auto_selecting():
    matcher = ProductMatcher(FakeCaller())
    result = matcher.match("茶派", color="红色", use_inventory=False, allow_llm=False)
    assert result.product is None
    assert len(result.candidates) == 2


def test_matcher_honors_warehouse_and_min_stock():
    matcher = ProductMatcher(FakeCaller())
    result = matcher.match(
        "茶派三小盒",
        color="黄色",
        warehouse_name="自己店里",
        min_stock=3,
        allow_product_fallback=False,
        allow_llm=False,
    )
    assert result.product["id"] == 154

    missing = matcher.match(
        "茶派三小盒",
        color="红色",
        warehouse_name="自己店里",
        min_stock=1,
        allow_product_fallback=False,
        allow_llm=False,
    )
    assert missing.product is None


def test_matcher_extracts_color_from_name_when_llm_misses_it():
    matcher = ProductMatcher(FakeCaller())
    result = matcher.match(
        "岩彩3小盒卡其色",
        warehouse_name="自己店里",
        allow_llm=False,
    )
    assert result.product["id"] == 301
    assert result.product["spec"] == "卡其色"
