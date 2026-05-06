"""
通用工具公共函数
order-flow 业务规则的核心公共函数库
"""
from .unit_converter import (
    pieces_to_sets,
    parse_unit_from_simple_desc,
    calculate_order_quantity,
    is_one_piece_order,
    calculate_purchase_quantity,
)

from .color_filter import (
    filter_uv,
    normalize_color,
    extract_color_from_text,
    validate_color,
    STANDARD_COLORS,
)

from .spec_formatter import (
    format_spec,
    extract_spec_key,
    filter_special_fields,
    merge_color_quantity,
    parse_product_name,
)

__all__ = [
    # 件套换算
    "pieces_to_sets",
    "parse_unit_from_simple_desc",
    "calculate_order_quantity",
    "is_one_piece_order",
    "calculate_purchase_quantity",
    # 颜色处理
    "filter_uv",
    "normalize_color",
    "extract_color_from_text",
    "validate_color",
    "STANDARD_COLORS",
    # 规格处理
    "format_spec",
    "extract_spec_key",
    "filter_special_fields",
    "merge_color_quantity",
    "parse_product_name",
]
