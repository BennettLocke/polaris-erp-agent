"""
颜色过滤与处理公共函数
严格按 order-flow 规则：
- 含"UV"只取前面部分："香槟金UV" → "香槟金"
- 颜色标准化
"""
from src.core.config import get_config

_config = get_config()

_DEFAULT_STANDARD_COLORS = [
    "橙色", "红色", "绿色", "蓝色", "黄色", "黑色", "白色",
    "灰色", "咖色", "金色", "银色", "香槟金", "深咖色",
    "古铜色", "古铜红", "橄榄绿", "卡其色", "深绿", "紫色", "粉色",
]

_DEFAULT_COLOR_ALIASES = {
    "桔色": "橙色",
    "黄": "黄色",
    "红": "红色",
    "兰": "蓝色",
    "绿": "绿色",
    "黑": "黑色",
    "白": "白色",
    "灰": "灰色",
    "啡色": "咖色",
    "棕色": "咖色",
    "深棕": "深咖色",
    "铜色": "古铜色",
    "深咖": "咖色",
    "咖啡色": "咖色",
    "棕咖色": "咖色",
}

# 标准颜色列表（用于验证和标准化）
STANDARD_COLORS = list(dict.fromkeys([
    *_config.get("business_rules.color_filter.standard_colors", []),
    *_DEFAULT_STANDARD_COLORS,
]))

# 颜色别名映射（统一标准化）
COLOR_ALIASES = {
    **_DEFAULT_COLOR_ALIASES,
    **_config.get("business_rules.color_filter.aliases", {}),
}


def filter_uv(color: str) -> str:
    """
    颜色 UV 过滤
    含"UV"只取前面部分
    例："香槟金UV" → "香槟金"
    """
    if not color:
        return ""

    if "UV" in color:
        return color.split("UV")[0].strip()

    return color.strip()


def normalize_color(color: str) -> str:
    """
    颜色标准化
    1. UV 过滤
    2. 去除空格
    3. 别名映射
    """
    if not color:
        return ""

    # UV 过滤
    color = filter_uv(color)

    # 去除空格
    color = color.strip()

    # 别名映射
    return COLOR_ALIASES.get(color, color)


def extract_color_from_text(text: str) -> str | None:
    """
    从文本中提取颜色
    返回标准化后的颜色
    """
    text_normalized = normalize_color(text)

    for color in sorted(STANDARD_COLORS, key=len, reverse=True):
        if color in text_normalized:
            return color

    # 检查别名
    for alias, standard in sorted(COLOR_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        if alias in text_normalized:
            return standard

    return None


def validate_color(color: str) -> bool:
    """
    验证颜色是否为标准颜色
    """
    if not color:
        return False
    normalized = normalize_color(color)
    return normalized in STANDARD_COLORS
