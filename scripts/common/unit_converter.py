"""
件套换算公共函数
严格按 order-flow 规则：
用户报"X件" → 查 simple_desc 提取换算率 → X × 每件套数 = 订单数量
"""
from __future__ import annotations


def _one_piece_series() -> list[str]:
    """读取最新的1件起订系列，支持聊天里动态改规则后立即生效。"""
    try:
        from src.core.config import get_config
        return list(get_config().get("business_rules.unit_conversion.one_piece_series", []) or [])
    except Exception:
        from src.models.constants import ONE_PIECE_SERIES
        return list(ONE_PIECE_SERIES or [])


def pieces_to_sets(pieces: int, per_piece: int) -> int:
    """
    件转套（件套换算）

    Args:
        pieces: 件数（用户输入）
        per_piece: 每件套数（从数据库 simple_desc 提取）

    Returns:
        换算后的套数
    """
    if per_piece <= 0:
        return pieces
    return pieces * per_piece


def parse_unit_from_simple_desc(simple_desc: str) -> int | None:
    """
    从 simple_desc 字段解析每件套数
    支持格式：
      - "规格:60套/件"  → 60
      - "规格:20套/件"  → 20
      - "规格:30个/件"  → 30
      - "28套/件"      → 28
      - "1件28套"      → 28

    Returns:
        每件套数，未知则返回 None
    """
    import re

    # 匹配 "数字套/件"、"数字个/件" 或 "数字张/件"
    patterns = [
        r"(\d+)\s*套\s*/\s*件",
        r"(\d+)\s*个\s*/\s*件",
        r"(\d+)\s*张\s*/\s*件",
        r"(?:1\s*)?件\s*(\d+)\s*(?:套|个|张|只|盒)",
        r"每\s*件\s*(\d+)\s*(?:套|个|张|只|盒)",
    ]

    for pattern in patterns:
        match = re.search(pattern, simple_desc)
        if match:
            return int(match.group(1))

    return None


def calculate_order_quantity(user_reported: str, quantity: int, simple_desc: str) -> int:
    """
    根据用户报的数量和单位，计算订单数量

    Args:
        user_reported: 用户原始描述，如"3件"、"5个"
        quantity: 用户报的数量（整数）
        simple_desc: 商品的 simple_desc 字段

    Returns:
        实际订单数量（套数）

    Examples:
        用户报"3件"，simple_desc="规格:28套/件" → 3×28 = 84
        用户报"5个"，simple_desc="规格:60套/件" → 5×60 = 300
    """
    per_piece = parse_unit_from_simple_desc(simple_desc)

    # 判断用户是否按"件"报
    if "件" in user_reported and per_piece:
        return pieces_to_sets(quantity, per_piece)

    # 用户按"个/套/张"报，直接用数量
    return quantity


def is_one_piece_order(product_name: str) -> bool:
    """
    判断商品是否为1件起订系列
    """
    return any(kw in product_name for kw in _one_piece_series())


def calculate_purchase_quantity(order_quantity: int, per_piece: int, product_name: str) -> int:
    """
    计算进货数量

    规则（按 order-flow B4.3）：
    - 1件起订系列：件数 = ceil(订单数量 / 每件套数)
    - 非1件起：入库数量 = 订单数量

    Args:
        order_quantity: 订单数量（套）
        per_piece: 每件套数
        product_name: 商品名称（用于判断系列）

    Returns:
        实际进货数量
    """
    import math

    if is_one_piece_order(product_name):
        # 1件起订系列
        pieces = math.ceil(order_quantity / per_piece) if per_piece > 0 else order_quantity
        return pieces
    else:
        # 非1件起
        return order_quantity
