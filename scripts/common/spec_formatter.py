"""
规格格式化公共函数
处理商品规格、特殊字段过滤、多规格合并等
"""

import re


def format_spec(spec: str) -> str:
    """
    格式化规格字段
    去除多余空格、标准化格式
    """
    if not spec:
        return ""

    # 去除多余空格
    spec = " ".join(spec.split())

    # 去除常见前缀
    prefixes = ["颜色:", "规格:", "款式:"]
    for prefix in prefixes:
        if spec.startswith(prefix):
            spec = spec[len(prefix) :].strip()

    return spec


def extract_spec_key(spec: str) -> str:
    """
    从规格中提取关键信息
    如 "香槟金UV" → "香槟金"
          "橙色-深色" → "橙色"
    """
    # UV 过滤
    spec = spec.split("UV")[0].strip()

    # 颜色-规格 模式
    if "-" in spec:
        spec = spec.split("-")[0].strip()

    return spec


def filter_special_fields(product_data: dict) -> dict:
    """
    过滤商品特殊字段
    去除 null 值、空字符串、临时字段
    """
    filtered = {}
    for key, value in product_data.items():
        # 跳过空值
        if value is None or value == "":
            continue
        # 跳过临时字段
        if key.startswith("_") or key.endswith("_temp"):
            continue
        filtered[key] = value
    return filtered


def merge_color_quantity(items: list[dict]) -> list[dict]:
    """
    合并同商品+颜色的多数量
    用于多订单合并开单

    Args:
        items: [{"product_id": X, "color": "红色", "quantity": Y}, ...]

    Returns:
        合并后的商品列表
    """
    merged = {}

    for item in items:
        key = (item.get("product_id"), item.get("color"))
        if key in merged:
            merged[key]["quantity"] += item.get("quantity", 1)
        else:
            merged[key] = dict(item)

    return list(merged.values())


def parse_product_name(name: str) -> dict:
    """
    解析商品名称
    提取品牌前缀和商品主体
    如 "【喜悦】三小盒" → {"brand": "喜悦", "name": "三小盒", "full": "【喜悦】三小盒"}
    """
    match = re.search(r"【(.+?)】(.+)", name)
    if match:
        return {
            "brand": match.group(1),
            "name": match.group(2),
            "full": name,
        }
    return {
        "brand": "",
        "name": name,
        "full": name,
    }
