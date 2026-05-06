"""常量定义 - 延迟加载 config，便于单元测试"""
from __future__ import annotations

_config = None


def _get_config():
    """延迟加载配置（首次访问时才加载）"""
    global _config
    if _config is None:
        from src.core.config import get_config
        _config = get_config()
    return _config


# ---- 静态常量（无需配置） ----
UNIT_TAO = 1            # 套
UNIT_GE = 3             # 个
UNIT_ZHANG = 5          # 张

# ---- 销售单状态 ----
SALES_STATUS_PENDING = 0
SALES_STATUS_AUDITING = 1
SALES_STATUS_AUDITED = 2
SALES_STATUS_DELIVERED = 3
SALES_STATUS_RECEIVED = 4
SALES_STATUS_COMPLETED = 5
SALES_STATUS_CANCELLED = 6
SALES_STATUS_CLOSED = 7

# ---- 入库/出库状态 ----
STOCK_STATUS_DRAFT = 0
STOCK_STATUS_PENDING = 1
STOCK_STATUS_APPROVED = 2
STOCK_STATUS_DONE = 3
STOCK_STATUS_FINISHED = 5

# ---- 意图类型 ----
INTENT_IMAGE_ORDER = "image_order"
INTENT_TEXT_ORDER = "text_order"
INTENT_INVENTORY_QUERY = "inventory_query"
INTENT_KNOWLEDGE_QA = "knowledge_qa"
INTENT_UNKNOWN = "unknown"


def __getattr__(name: str):
    """延迟加载配置相关的常量"""
    cfg = _get_config()

    _LAZY_MAP = {
        "WAREHOUSE_SELF": ("erp.warehouse.self", 1, int),
        "WAREHOUSE_BAIXIN": ("erp.warehouse.baixin", 2, int),
        "CUSTOMER_QIWU_TEA": ("erp.customer.qiwu_tea_id", 1, int),
        "CUSTOMER_DEFAULT": ("erp.customer.default_id", 1, int),
        "NON_INVENTORY_CATEGORIES": ("business_rules.inventory_decision.non_check_categories", [
            "泡袋", "包茶", "内衬", "PVC", "标签", "纸箱",
            "烫金泡袋", "提袋UV", "提袋丝印", "烫膜",
        ], None),
        "ONE_PIECE_SERIES": ("business_rules.unit_conversion.one_piece_series", [
            "见喜", "岩味", "出彩", "岩彩", "喜悦", "茶派",
            "圆满", "喜物", "开物",
        ], None),
        "NON_ONE_PIECE_SERIES": ("business_rules.unit_conversion.non_one_piece_series", [
            "星禾", "生财", "墨香", "大吉", "山川", "远航",
            "顶呱呱", "云岭", "视界", "锦程", "旷野", "小盒子", "余味",
        ], None),
        "GIFT_BOX_KEYWORDS": ("business_rules.inventory_decision.gift_box_keywords", [
            "礼盒", "盒子", "盒",
        ], None),
        "COLOR_ALIASES": ("business_rules.color_filter.aliases", {}, None),
        "STANDARD_COLORS": ("business_rules.color_filter.standard_colors", [
            "橙色", "红色", "绿色", "蓝色", "黄色", "黑色", "白色", "灰色",
            "咖色", "金色", "银色", "香槟金", "深咖色", "古铜色", "古铜红",
            "橄榄绿", "卡其色", "深绿",
        ], None),
        "HOT_STAMP_KEYWORDS": ("business_rules.hot_stamp.keywords", [
            "烫金泡袋", "烫金", "泡袋烫金",
        ], None),
        "AUTO_PRINT_CUSTOMERS": ("business_rules.print_rules.auto_print_customers", "1", None),
        "DEFAULT_NO_PRINT": ("business_rules.print_rules.default_no_print", True, None),
        "PRICE_PRIORITY": ("business_rules.price_rules.priority", [
            "customer_history", "retail_price",
        ], None),
        "ALLOW_EMPTY_PRICE": ("business_rules.price_rules.allow_empty_price", False, None),
        "DEFAULT_WAREHOUSE": ("business_rules.warehouse_defaults.default_warehouse", 2, int),
        "TRANSFER_FROM": ("business_rules.warehouse_defaults.transfer_from", 1, int),
        "TRANSFER_TO": ("business_rules.warehouse_defaults.transfer_to", 2, int),
        "ALLOW_SPLIT_ORDER": ("business_rules.order_rules.allow_split_order", False, None),
        "DEFAULT_PAY_TYPE": ("business_rules.order_rules.default_pay_type", 1, int),
        "PURCHASE_DEFAULT_WAREHOUSE": ("business_rules.purchase_rules.default_warehouse", 2, int),
        "PURCHASE_NOTE": ("business_rules.purchase_rules.note", "送至百鑫", None),
        "SCREEN_PRINT_KEYWORDS": ("business_rules.workflow.screen_print_keywords", [
            "丝印", "印刷",
        ], None),
        "IMAGE_SUPPORTED_EXTENSIONS": ("business_rules.image.supported_extensions", [
            "jpg", "jpeg", "png", "gif", "webp",
        ], None),
        "KNOWLEDGE_QA_TOP_K": ("business_rules.knowledge_qa.top_k", 5, int),
        "KNOWLEDGE_QA_MAX_CHUNK_CHARS": ("business_rules.knowledge_qa.max_chunk_chars", 500, int),
    }

    if name in _LAZY_MAP:
        key, default, cast = _LAZY_MAP[name]
        value = cfg.get(key, default)
        if cast and value is not None:
            value = cast(value)
        globals()[name] = value
        return value

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
