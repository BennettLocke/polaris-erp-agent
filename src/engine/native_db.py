"""Native sjagent_core database access.

This module is the first runtime layer that reads and writes the self-owned
sjagent_core schema.  It keeps the response shape close to the old ERP helpers
so the existing agent tools and React admin can switch over without a large
frontend rewrite.
"""
from __future__ import annotations

import json
import hashlib
import html as html_lib
import os
import re
import threading
import time
import contextvars
from contextlib import contextmanager
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Iterable, Optional

import pymysql
from pymysql.cursors import DictCursor

from src.engine.exceptions import DBError
from src.utils import get_logger

logger = get_logger("sjagent.native_db")

PUBLIC_IMAGE_HOST = "https://img.513sjbz.com"
LEGACY_OSS_IMAGE_HOSTS = (
    "https://513sjbz.oss-cn-beijing.aliyuncs.com",
    "http://513sjbz.oss-cn-beijing.aliyuncs.com",
)

_NATIVE_OPERATOR_USER_ID: contextvars.ContextVar[int | None] = contextvars.ContextVar(
    "sjagent_native_operator_user_id",
    default=None,
)


def _coerce_user_id(value: Any) -> int | None:
    if value in (None, ""):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        parsed = int(text)
        return parsed if parsed > 0 else None
    match = re.fullmatch(r"(?:web|user|auth)_(\d+)", text)
    if match:
        parsed = int(match.group(1))
        return parsed if parsed > 0 else None
    return None


def set_native_operator_user_id(user_id: Any) -> contextvars.Token:
    return _NATIVE_OPERATOR_USER_ID.set(_coerce_user_id(user_id))


def reset_native_operator_user_id(token: contextvars.Token) -> None:
    _NATIVE_OPERATOR_USER_ID.reset(token)


def current_native_operator_user_id() -> int | None:
    return _NATIVE_OPERATOR_USER_ID.get()


def _env(name: str, fallback: str = "") -> str:
    value = os.environ.get(name)
    return value if value not in (None, "") else fallback


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _clean_number_sequence_note(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text.count("?") >= 4 and not re.search(r"[\u4e00-\u9fff]", text):
        code_match = re.search(r"([A-Za-z]{1,20}\d{1,10})", text)
        if code_match:
            code = code_match.group(1).upper()
            return f"礼盒和泡袋统一从 {code} 往后自动编号"
        return ""
    return text


def _json_loads(value: Any, default: Any = None) -> Any:
    if value in (None, ""):
        return default
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default


def _json_dumps(value: Any) -> str:
    return json.dumps(value if value is not None else [], ensure_ascii=False)


def _num(value: Any, default: float = 0.0) -> float:
    if value in (None, ""):
        return default
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _qty_text(value: Any) -> str:
    number = _num(value)
    return str(int(number)) if number.is_integer() else f"{number:.3f}".rstrip("0").rstrip(".")


def _normalize_purchase_policy(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"1", "true", "yes", "on", "one_case", "one_piece", "case", "piece"}:
        return "one_case"
    if text in {"none", "no_purchase", "disabled"}:
        return "none"
    if text in {"min_qty", "minimum"}:
        return "min_qty"
    return "order_qty"


def _money(value: Any) -> str:
    number = _num(value)
    if abs(number) < 0.000001:
        number = 0
    return f"{number:.2f}"


def _date_text(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    text = str(value)
    return text[:10] if len(text) >= 10 else text


def _first_image(value: Any) -> str:
    if not value:
        return ""
    parsed = _json_loads(value, None)
    if isinstance(parsed, list):
        return str(parsed[0]) if parsed else ""
    if isinstance(parsed, str):
        return parsed
    text = str(value).strip()
    return text.split(",")[0].strip() if text else ""


def _normalize_public_image_url(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    for host in LEGACY_OSS_IMAGE_HOSTS:
        if text.startswith(host):
            return f"{PUBLIC_IMAGE_HOST}{text[len(host):]}"
    return text


def _normalize_public_image_urls(value: Any) -> list[str]:
    items = _json_loads(value, [])
    if isinstance(items, str):
        items = [items]
    if not isinstance(items, list):
        return []
    result: list[str] = []
    for item in items:
        url = _normalize_public_image_url(item)
        if url and url not in result:
            result.append(url)
    return result


def _normalize_public_image_text(value: Any) -> str:
    text = str(value or "")
    if not text:
        return ""
    for host in LEGACY_OSS_IMAGE_HOSTS:
        text = text.replace(host, PUBLIC_IMAGE_HOST)
    return text


def _merge_category_names(category_ids: Iterable[Any], category_lookup: dict[int, str], primary_name: str = "") -> list[str]:
    names: list[str] = []

    def add(name: Any) -> None:
        text = str(name or "").strip()
        if text and text not in names:
            names.append(text)

    for value in category_ids or []:
        try:
            category_id = int(value)
        except (TypeError, ValueError):
            continue
        add(category_lookup.get(category_id))

    if not names:
        add(primary_name)
    return names


def _html_image_urls(value: Any) -> list[str]:
    text = str(value or "")
    urls: list[str] = []
    for match in re.finditer(r"<img[^>]+src=[\"']([^\"']+)[\"']", text, re.I):
        url = match.group(1).strip()
        if url and url not in urls:
            urls.append(url)
    return urls


def _phone_digits(value: Any) -> str:
    return re.sub(r"\D+", "", str(value or ""))


def _pay_status_text(value: Any) -> str:
    return {
        "paid": "已付款",
        "unpaid": "未付款",
        "monthly": "月结",
        "partial": "部分付款",
        "refunded": "已退款",
    }.get(str(value or ""), str(value or "未记录"))


def _pay_type_text(value: Any) -> str:
    return {
        "wechat": "微信",
        "cash": "现金",
        "balance": "余额",
        "monthly": "月结",
        "account": "账户",
        "bank": "转账",
        "alipay": "支付宝",
        "receipt": "收款",
        "recharge": "充值",
        "settlement": "结款",
        "adjustment": "余额调整",
    }.get(str(value or ""), str(value or ""))


def _balance_entry_type_text(value: Any) -> str:
    return {
        "receipt": "收款",
        "recharge": "充值",
        "settlement": "结款",
        "adjustment": "余额调整",
        "balance_pay": "余额付款",
        "balance_refund": "余额退回",
        "settlement_refund": "月结取消转余额",
    }.get(str(value or ""), str(value or ""))


def _media_type(value: Any) -> str:
    return {
        "main": "main_image",
        "detail": "detail_image",
        "image": "color_image",
    }.get(str(value or ""), str(value or ""))


def _source_text(value: Any) -> str:
    source = str(value or "").strip()
    return {
        "migration": "迁移导入",
        "upload": "上传",
        "native_api": "系统保存",
        "webui": "后台上传",
        "manual": "手工维护",
        "shopxo": "商城迁移",
        "erp": "ERP迁移",
        "sku_image": "SKU颜色图",
    }.get(source, source or "-")


FIXED_NON_STOCK_CATEGORY_NAMES = ("快递纸箱", "PVC礼盒")
FIXED_NON_STOCK_CATEGORY_KEYWORDS = (
    "泡袋",
    "茶袋",
    "标签",
    "服务",
    "设计",
    "制版",
    "辅料",
    "包茶",
    "烫金",
    "快递纸箱",
    "纸箱",
    "PVC礼盒",
    "PVC",
)


def _gift_box_label(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return text if text.endswith("礼盒") else f"{text}礼盒"


_ASSET_CATEGORY_ORDER = {
    "半斤礼盒": 10,
    "一两礼盒": 20,
    "二两礼盒": 30,
    "三两礼盒": 40,
    "五格礼盒": 50,
    "2泡礼盒": 60,
    "2泡小盒": 65,
    "3小盒礼盒": 70,
    "6小盒礼盒": 80,
    "PVC礼盒": 90,
    "大红袍泡袋": 110,
    "水仙泡袋": 120,
    "肉桂泡袋": 130,
    "红茶泡袋": 140,
    "品种茶泡袋": 150,
    "纯色泡袋": 160,
    "公版泡袋": 170,
    "空白泡袋": 180,
    "宽版泡袋": 190,
    "快递纸箱": 800,
    "其他产品": 900,
}


def _normalize_asset_category_name(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    replacements = {
        "pvc礼盒": "PVC礼盒",
        "PVC礼盒": "PVC礼盒",
        "品种茶袋": "品种茶泡袋",
        "红茶袋": "红茶泡袋",
        "空白": "空白泡袋",
        "宽版": "宽版泡袋",
        "公版": "公版泡袋",
    }
    return replacements.get(text, text)


def _asset_group_from_label(label: str, product_type: str = "", category_id: Any = None) -> tuple[str, str, int]:
    clean_label = _normalize_asset_category_name(label)
    if not clean_label:
        return "", "", 0
    type_prefix = str(product_type or "").strip() or "category"
    key_source = category_id or clean_label
    group_key = f"{type_prefix}:{key_source}"
    order = _ASSET_CATEGORY_ORDER.get(clean_label)
    if order is None:
        order = 10 if type_prefix == "gift_box" else 110 if type_prefix == "bag" else 900
    return group_key, clean_label, order


def _infer_gift_box_asset_group(full_text: str) -> str:
    text = str(full_text or "")
    if re.search(r"PVC|pvc|透明PVC|牛皮纸PVC", text):
        return "PVC礼盒"
    if "2泡小盒" in text or "两泡装小盒" in text:
        return "2泡小盒"
    if "2泡" in text or "两泡装" in text or "小盒子" in text:
        return "2泡礼盒"
    if "五格" in text or "十小盒" in text or "短半斤" in text:
        return "五格礼盒"
    if "3小盒" in text or "三小盒" in text:
        return "3小盒礼盒"
    if "6小盒" in text or "六小盒" in text:
        return "6小盒礼盒"
    if "半斤" in text:
        return "半斤礼盒"
    if "一两" in text or "1两" in text or "一两装" in text:
        return "一两礼盒"
    if "二两" in text:
        return "二两礼盒"
    if "二三两" in text or "三两" in text or "两大盒" in text:
        return "三两礼盒"
    return ""


def _infer_bag_asset_group(full_text: str) -> str:
    text = str(full_text or "")
    if "宽版" in text:
        return "宽版泡袋"
    if "公版" in text:
        return "公版泡袋"
    if "空白" in text:
        return "空白泡袋"
    if "纯色" in text:
        return "纯色泡袋"
    if any(word in text for word in ["红茶", "正山小种", "小种", "金骏眉", "赤甘", "妃子笑"]):
        return "红茶泡袋"
    if "肉桂" in text or "牛肉" in text or "马肉" in text:
        return "肉桂泡袋"
    if any(word in text for word in ["水仙", "老枞", "老丛", "高枞", "高丛", "枞王"]):
        return "水仙泡袋"
    if "大红袍" in text:
        return "大红袍泡袋"
    if any(word in text for word in [
        "品种茶", "奇兰", "奇蘭", "奇丹", "百瑞香", "石乳", "梅占", "金牡丹",
        "雀舌", "水金龟", "黄观音", "野茶", "私房茶", "岩茶", "雪梨", "素心兰",
        "黄玫瑰", "金观音", "佛手", "矮脚乌龙", "岩骨花香", "天然果香",
    ]):
        return "品种茶泡袋"
    return ""


def _asset_group_info(row: dict) -> tuple[str, str, str, str, int]:
    product_type = str(row.get("product_type") or "").strip()
    title = str(row.get("spu_title") or "").strip()
    series = str(row.get("series") or "").strip()
    size_label = str(row.get("size_label") or "").strip()
    category_name = _normalize_asset_category_name(row.get("category_name"))
    category_type = str(row.get("category_product_type") or product_type).strip()
    category_id = row.get("category_id")
    full_text = " ".join([
        title,
        series,
        size_label,
        category_name,
        str(row.get("bag_type") or ""),
        str(row.get("tea_type") or ""),
    ])
    if title and (not series or not size_label):
        match = re.match(r"^【([^】]+)】\s*(.+)$", title)
        if match:
            series = series or match.group(1).strip()
            size_label = size_label or match.group(2).strip()
            full_text = " ".join([
                title,
                series,
                size_label,
                category_name,
                str(row.get("bag_type") or ""),
                str(row.get("tea_type") or ""),
            ])

    if category_name:
        group_key, group_text, order = _asset_group_from_label(category_name, category_type or product_type, category_id)
    elif product_type == "gift_box":
        label = _infer_gift_box_asset_group(full_text)
        group_key, group_text, order = _asset_group_from_label(label or "其他产品", "gift_box")
    elif product_type == "bag":
        label = _infer_bag_asset_group(full_text)
        group_key, group_text, order = _asset_group_from_label(label or "其他产品", "bag")
    elif product_type == "shipping":
        group_key, group_text, order = _asset_group_from_label("快递纸箱", "shipping")
    elif title:
        group_key, group_text, order = _asset_group_from_label("其他产品", product_type or "other")
    else:
        group_key, group_text, order = "pending", "待绑定图片", 990

    return group_key, group_text, series, size_label, order


class NativeDBClient:
    """Thread-local pymysql client for the sjagent-owned schema."""

    _instance: Optional["NativeDBClient"] = None
    _local = threading.local()
    _operator_columns_ready = False
    _operator_columns_lock = threading.Lock()
    _print_tables_ready = False
    _print_tables_lock = threading.Lock()
    _number_sequence_tables_ready = False
    _number_sequence_tables_lock = threading.Lock()
    _system_settings_ready = False
    _system_settings_lock = threading.Lock()
    _sales_delete_columns_ready = False
    _sales_delete_columns_lock = threading.Lock()
    _party_columns_ready = False
    _party_columns_lock = threading.Lock()
    _default_operator_ready = False
    _default_operator_user_id: int | None = None
    _default_operator_lock = threading.Lock()
    _inventory_policy_sync_lock = threading.Lock()
    _inventory_policy_last_sync_at = 0.0
    _inventory_policy_sync_ttl_seconds = 15.0

    def __new__(cls) -> "NativeDBClient":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self.db_config = {
            "host": _env("SJAGENT_CORE_DB_HOST", _env("DB_HOST", "127.0.0.1")),
            "port": int(_env("SJAGENT_CORE_DB_PORT", _env("DB_PORT", "3306"))),
            "name": _env("SJAGENT_CORE_DB_NAME", "sjagent_core"),
            "user": _env("SJAGENT_CORE_DB_USER", _env("DB_USER", "")),
            "password": _env("SJAGENT_CORE_DB_PASSWORD", _env("DB_PASSWORD", "")),
            "charset": "utf8mb4",
        }

    def _get_connection(self) -> pymysql.Connection:
        connection = getattr(self._local, "connection", None)
        if connection is None or not connection.open:
            try:
                connection = pymysql.connect(
                    host=self.db_config["host"],
                    port=self.db_config["port"],
                    user=self.db_config["user"],
                    password=self.db_config["password"],
                    database=self.db_config["name"],
                    charset=self.db_config["charset"],
                    cursorclass=DictCursor,
                    autocommit=True,
                )
                self._local.connection = connection
                logger.info("native database connection established")
            except pymysql.Error as e:
                self._local.connection = None
                raise DBError(f"native database connection failed: {e}") from e
        else:
            try:
                connection.ping(reconnect=True)
            except pymysql.Error:
                self._local.connection = None
                return self._get_connection()
        return connection

    @contextmanager
    def cursor(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
        finally:
            cursor.close()

    @contextmanager
    def transaction(self):
        conn = self._get_connection()
        old_autocommit = conn.get_autocommit()
        conn.autocommit(False)
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.autocommit(old_autocommit)

    def query(self, sql: str, params: tuple | list | None = None) -> list[dict]:
        try:
            with self.cursor() as cursor:
                cursor.execute(sql, tuple(params or ()))
                return list(cursor.fetchall())
        except pymysql.Error as e:
            logger.error(f"native query failed: {e}")
            raise DBError(f"native query failed: {e}") from e

    def execute(self, sql: str, params: tuple | list | None = None) -> int:
        try:
            with self.cursor() as cursor:
                return cursor.execute(sql, tuple(params or ()))
        except pymysql.Error as e:
            logger.error(f"native execute failed: {e}")
            raise DBError(f"native execute failed: {e}") from e

    def _default_operator(self) -> int | None:
        configured = _coerce_user_id(_env("SJAGENT_DEFAULT_OPERATOR_USER_ID", _env("SJAGENT_AGENT_OPERATOR_USER_ID", "")))
        if configured:
            return configured
        configured_name = _env("SJAGENT_DEFAULT_OPERATOR_USERNAME", _env("SJAGENT_DEFAULT_OPERATOR_NAME", "")).strip()
        with self.__class__._default_operator_lock:
            if self.__class__._default_operator_ready and not configured_name:
                return self.__class__._default_operator_user_id
            try:
                if configured_name:
                    rows = self.query(
                        """
                        SELECT id
                        FROM auth_user
                        WHERE approval_status='approved'
                          AND is_active=1
                          AND (username=%s OR display_name=%s)
                        ORDER BY is_admin DESC, id ASC
                        LIMIT 1
                        """,
                        (configured_name, configured_name),
                    )
                else:
                    rows = self.query(
                        """
                        SELECT id
                        FROM auth_user
                        WHERE approval_status='approved'
                          AND is_active=1
                          AND (is_admin=1 OR role IN ('admin','staff'))
                        ORDER BY is_admin DESC, id ASC
                        LIMIT 1
                        """
                    )
                user_id = _coerce_user_id(rows[0].get("id")) if rows else None
                if not configured_name:
                    self.__class__._default_operator_user_id = user_id
                    self.__class__._default_operator_ready = True
                return user_id
            except Exception as e:
                logger.warning(f"default operator lookup failed: {e}")
                if not configured_name:
                    self.__class__._default_operator_ready = True
                return None

    def _operator_user_id(self, explicit: Any = None) -> int | None:
        return _coerce_user_id(explicit) or current_native_operator_user_id() or self._default_operator()

    def _table_exists(self, cursor, table_name: str) -> bool:
        if not re.fullmatch(r"[0-9A-Za-z_]+", str(table_name or "")):
            return False
        cursor.execute("SHOW TABLES LIKE %s", (table_name,))
        return cursor.fetchone() is not None

    def _ensure_operator_columns(self) -> None:
        if self.__class__._operator_columns_ready:
            return
        with self.__class__._operator_columns_lock:
            if self.__class__._operator_columns_ready:
                return
            try:
                with self.cursor() as cursor:
                    cursor.execute("SHOW COLUMNS FROM sales_order LIKE 'canceled_by_user_id'")
                    if not cursor.fetchone():
                        cursor.execute(
                            "ALTER TABLE sales_order ADD COLUMN canceled_by_user_id BIGINT UNSIGNED NULL AFTER canceled_at"
                        )
                    cursor.execute("SHOW COLUMNS FROM sales_order LIKE 'settlement_ledger_id'")
                    if not cursor.fetchone():
                        cursor.execute(
                            "ALTER TABLE sales_order ADD COLUMN settlement_ledger_id BIGINT UNSIGNED NULL AFTER source_workflow_id"
                        )
                    cursor.execute("SHOW COLUMNS FROM sales_order LIKE 'settled_at'")
                    if not cursor.fetchone():
                        cursor.execute(
                            "ALTER TABLE sales_order ADD COLUMN settled_at DATETIME NULL AFTER settlement_ledger_id"
                        )
                    cursor.execute("SHOW INDEX FROM sales_order WHERE Key_name='idx_sales_order_canceled_by'")
                    if not cursor.fetchone():
                        cursor.execute("ALTER TABLE sales_order ADD KEY idx_sales_order_canceled_by (canceled_by_user_id)")
                    cursor.execute("SHOW INDEX FROM sales_order WHERE Key_name='idx_sales_order_settlement'")
                    if not cursor.fetchone():
                        cursor.execute("ALTER TABLE sales_order ADD KEY idx_sales_order_settlement (settlement_ledger_id)")
                self.__class__._operator_columns_ready = True
            except pymysql.Error as e:
                logger.warning(f"native operator column check failed: {e}")
                raise DBError(f"native operator column check failed: {e}") from e

    def _ensure_sales_delete_columns(self) -> None:
        if self.__class__._sales_delete_columns_ready:
            return
        with self.__class__._sales_delete_columns_lock:
            if self.__class__._sales_delete_columns_ready:
                return
            try:
                with self.cursor() as cursor:
                    cursor.execute("SHOW COLUMNS FROM sales_order LIKE 'deleted_at'")
                    if not cursor.fetchone():
                        cursor.execute("ALTER TABLE sales_order ADD COLUMN deleted_at DATETIME NULL AFTER cancel_reason")
                    cursor.execute("SHOW COLUMNS FROM sales_order LIKE 'deleted_by_user_id'")
                    if not cursor.fetchone():
                        cursor.execute(
                            "ALTER TABLE sales_order ADD COLUMN deleted_by_user_id BIGINT UNSIGNED NULL AFTER deleted_at"
                        )
                    cursor.execute("SHOW COLUMNS FROM sales_order LIKE 'delete_reason'")
                    if not cursor.fetchone():
                        cursor.execute("ALTER TABLE sales_order ADD COLUMN delete_reason VARCHAR(500) NULL AFTER deleted_by_user_id")
                    cursor.execute("SHOW INDEX FROM sales_order WHERE Key_name='idx_sales_order_deleted_at'")
                    if not cursor.fetchone():
                        cursor.execute("ALTER TABLE sales_order ADD KEY idx_sales_order_deleted_at (deleted_at)")
                    cursor.execute("SHOW INDEX FROM sales_order WHERE Key_name='idx_sales_order_deleted_by'")
                    if not cursor.fetchone():
                        cursor.execute("ALTER TABLE sales_order ADD KEY idx_sales_order_deleted_by (deleted_by_user_id)")
                self.__class__._sales_delete_columns_ready = True
            except pymysql.Error as e:
                logger.warning(f"native sales delete column check failed: {e}")
                raise DBError(f"native sales delete column check failed: {e}") from e

    def _ensure_party_columns(self) -> None:
        if self.__class__._party_columns_ready:
            return
        with self.__class__._party_columns_lock:
            if self.__class__._party_columns_ready:
                return
            try:
                with self.cursor() as cursor:
                    cursor.execute("SHOW COLUMNS FROM party LIKE 'is_monthly_customer'")
                    if not cursor.fetchone():
                        cursor.execute(
                            "ALTER TABLE party ADD COLUMN is_monthly_customer TINYINT NOT NULL DEFAULT 0 AFTER settlement_type"
                        )
                self.__class__._party_columns_ready = True
            except pymysql.Error as e:
                logger.warning(f"native party column check failed: {e}")
                raise DBError(f"native party column check failed: {e}") from e

    def _ensure_print_tables(self) -> None:
        if self.__class__._print_tables_ready:
            return
        with self.__class__._print_tables_lock:
            if self.__class__._print_tables_ready:
                return
            try:
                with self.cursor() as cursor:
                    cursor.execute(
                        """
                        CREATE TABLE IF NOT EXISTS print_template (
                            id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                            template_key VARCHAR(80) NOT NULL,
                            document_type VARCHAR(40) NOT NULL DEFAULT 'sales_order',
                            name VARCHAR(120) NOT NULL,
                            paper_size VARCHAR(20) NOT NULL DEFAULT 'A4',
                            orientation VARCHAR(20) NOT NULL DEFAULT 'landscape',
                            font_size INT NOT NULL DEFAULT 12,
                            copies INT NOT NULL DEFAULT 1,
                            show_logo TINYINT NOT NULL DEFAULT 0,
                            show_operator TINYINT NOT NULL DEFAULT 1,
                            show_customer_phone TINYINT NOT NULL DEFAULT 1,
                            show_payment TINYINT NOT NULL DEFAULT 1,
                            show_note TINYINT NOT NULL DEFAULT 1,
                            header_text VARCHAR(200) NOT NULL DEFAULT '肆计包装销售单',
                            footer_text VARCHAR(500) NULL,
                            custom_css TEXT NULL,
                            is_default TINYINT NOT NULL DEFAULT 1,
                            is_enabled TINYINT NOT NULL DEFAULT 1,
                            created_by_user_id BIGINT UNSIGNED NULL,
                            updated_by_user_id BIGINT UNSIGNED NULL,
                            created_at DATETIME NOT NULL,
                            updated_at DATETIME NOT NULL,
                            PRIMARY KEY (id),
                            UNIQUE KEY uk_print_template_key (template_key),
                            KEY idx_print_template_type (document_type, is_default, is_enabled)
                        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                        """
                    )
                    cursor.execute(
                        """
                        CREATE TABLE IF NOT EXISTS print_job (
                            id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                            job_no VARCHAR(80) NOT NULL,
                            document_type VARCHAR(40) NOT NULL DEFAULT 'sales_order',
                            document_id BIGINT UNSIGNED NOT NULL,
                            template_id BIGINT UNSIGNED NULL,
                            status VARCHAR(30) NOT NULL DEFAULT 'pending',
                            print_url VARCHAR(300) NULL,
                            copies INT NOT NULL DEFAULT 1,
                            created_by_user_id BIGINT UNSIGNED NULL,
                            printed_by_user_id BIGINT UNSIGNED NULL,
                            created_at DATETIME NOT NULL,
                            printed_at DATETIME NULL,
                            updated_at DATETIME NOT NULL,
                            PRIMARY KEY (id),
                            UNIQUE KEY uk_print_job_no (job_no),
                            KEY idx_print_job_document (document_type, document_id),
                            KEY idx_print_job_status (status, created_at)
                        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                        """
                    )
                    cursor.execute(
                        """
                        INSERT INTO print_template
                            (template_key, document_type, name, paper_size, orientation, font_size, copies,
                             show_logo, show_operator, show_customer_phone, show_payment, show_note,
                             header_text, footer_text, custom_css, is_default, is_enabled, created_at, updated_at)
                        VALUES
                            ('sales_order_default', 'sales_order', '默认销售单模板', 'A5', 'landscape', 12, 1,
                             0, 1, 1, 1, 1,
                             '肆计包装销售单', '谢谢惠顾，请核对商品数量与金额。', '', 1, 1, NOW(), NOW())
                        ON DUPLICATE KEY UPDATE template_key=VALUES(template_key)
                        """
                    )
                self.__class__._print_tables_ready = True
            except pymysql.Error as e:
                logger.warning(f"native print table check failed: {e}")
                raise DBError(f"native print table check failed: {e}") from e

    def _ensure_number_sequence_tables(self) -> None:
        if self.__class__._number_sequence_tables_ready:
            return
        with self.__class__._number_sequence_tables_lock:
            if self.__class__._number_sequence_tables_ready:
                return
            try:
                with self.cursor() as cursor:
                    cursor.execute(
                        """
                        CREATE TABLE IF NOT EXISTS number_sequence_setting (
                            sequence_key VARCHAR(80) NOT NULL,
                            prefix VARCHAR(20) NOT NULL DEFAULT 'SJ',
                            start_number INT NOT NULL DEFAULT 1001,
                            next_number INT NOT NULL DEFAULT 1001,
                            pad_width INT NOT NULL DEFAULT 4,
                            skipped_numbers TEXT NULL,
                            note VARCHAR(255) NULL,
                            updated_by_user_id BIGINT UNSIGNED NULL,
                            created_at DATETIME NOT NULL,
                            updated_at DATETIME NOT NULL,
                            PRIMARY KEY (sequence_key)
                        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                        """
                    )
                    cursor.execute(
                        """
                        CREATE TABLE IF NOT EXISTS number_sequence_log (
                            id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                            sequence_key VARCHAR(80) NOT NULL,
                            old_prefix VARCHAR(20) NULL,
                            old_start_number INT NULL,
                            old_next_number INT NULL,
                            old_pad_width INT NULL,
                            old_skipped_numbers TEXT NULL,
                            new_prefix VARCHAR(20) NOT NULL,
                            new_start_number INT NOT NULL,
                            new_next_number INT NOT NULL,
                            new_pad_width INT NOT NULL,
                            new_skipped_numbers TEXT NULL,
                            note VARCHAR(255) NULL,
                            changed_by_user_id BIGINT UNSIGNED NULL,
                            created_at DATETIME NOT NULL,
                            PRIMARY KEY (id),
                            KEY idx_number_sequence_log_key (sequence_key, created_at)
                        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                        """
                    )
                    cursor.execute("SHOW COLUMNS FROM number_sequence_setting LIKE 'start_number'")
                    if not cursor.fetchone():
                        cursor.execute("ALTER TABLE number_sequence_setting ADD COLUMN start_number INT NOT NULL DEFAULT 1001 AFTER prefix")
                    cursor.execute("SHOW COLUMNS FROM number_sequence_setting LIKE 'skipped_numbers'")
                    if not cursor.fetchone():
                        cursor.execute("ALTER TABLE number_sequence_setting ADD COLUMN skipped_numbers TEXT NULL AFTER pad_width")
                    for column, sql in {
                        "old_start_number": "ALTER TABLE number_sequence_log ADD COLUMN old_start_number INT NULL AFTER old_prefix",
                        "old_skipped_numbers": "ALTER TABLE number_sequence_log ADD COLUMN old_skipped_numbers TEXT NULL AFTER old_pad_width",
                        "new_start_number": "ALTER TABLE number_sequence_log ADD COLUMN new_start_number INT NOT NULL DEFAULT 1001 AFTER new_prefix",
                        "new_skipped_numbers": "ALTER TABLE number_sequence_log ADD COLUMN new_skipped_numbers TEXT NULL AFTER new_pad_width",
                    }.items():
                        cursor.execute(f"SHOW COLUMNS FROM number_sequence_log LIKE '{column}'")
                        if not cursor.fetchone():
                            cursor.execute(sql)
                    cursor.execute(
                        """
                        INSERT INTO number_sequence_setting
                            (sequence_key, prefix, start_number, next_number, pad_width, skipped_numbers, note, created_at, updated_at)
                        VALUES ('product_sku', 'SJ', 1001, 1001, 4, '[]', '商品 SKU 编号', NOW(), NOW())
                        ON DUPLICATE KEY UPDATE sequence_key=VALUES(sequence_key)
                        """
                    )
                self.__class__._number_sequence_tables_ready = True
            except pymysql.Error as e:
                logger.warning(f"native number sequence table check failed: {e}")
                raise DBError(f"native number sequence table check failed: {e}") from e

    def _ensure_system_settings_tables(self) -> None:
        if self.__class__._system_settings_ready:
            return
        with self.__class__._system_settings_lock:
            if self.__class__._system_settings_ready:
                return
            try:
                with self.cursor() as cursor:
                    cursor.execute(
                        """
                        CREATE TABLE IF NOT EXISTS system_setting (
                            setting_key VARCHAR(80) NOT NULL,
                            setting_value LONGTEXT NOT NULL,
                            note VARCHAR(255) NULL,
                            updated_by_user_id BIGINT UNSIGNED NULL,
                            created_at DATETIME NOT NULL,
                            updated_at DATETIME NOT NULL,
                            PRIMARY KEY (setting_key)
                        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                        """
                    )
                    cursor.execute(
                        """
                        CREATE TABLE IF NOT EXISTS system_setting_log (
                            id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                            setting_key VARCHAR(80) NOT NULL,
                            old_value LONGTEXT NULL,
                            new_value LONGTEXT NOT NULL,
                            changed_by_user_id BIGINT UNSIGNED NULL,
                            created_at DATETIME NOT NULL,
                            PRIMARY KEY (id),
                            KEY idx_system_setting_log_key (setting_key, created_at)
                        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                        """
                    )
                self.__class__._system_settings_ready = True
            except pymysql.Error as e:
                logger.warning(f"native system settings table check failed: {e}")
                raise DBError(f"native system settings table check failed: {e}") from e

    def close(self):
        connection = getattr(self._local, "connection", None)
        if connection and connection.open:
            connection.close()
            self._local.connection = None

    # ---- product search helpers ----

    def _compact_keyword(self, keyword: str) -> str:
        return str(keyword or "").replace("【", "").replace("】", "").replace(" ", "").replace("　", "")

    def _keyword_terms(self, keyword: str) -> list[str]:
        text = str(keyword or "").strip()
        terms = [term for term in text.split() if term]
        return terms or ([text] if text else [])

    def _keyword_variants(self, keyword: str) -> list[str]:
        compact = self._compact_keyword(keyword)
        variants: list[str] = []

        def add(value: str):
            value = self._compact_keyword(value)
            if value and value not in variants:
                variants.append(value)

        add(keyword)
        add(compact)
        replacements = [
            ("半斤", "0.5斤"),
            ("0.5斤", "半斤"),
            ("二三两", "2两3两"),
            ("2两3两", "二三两"),
            ("三小盒", "3小盒"),
            ("3小盒", "三小盒"),
            ("六小盒", "6小盒"),
            ("6小盒", "六小盒"),
            ("十小盒", "10小盒"),
            ("10小盒", "十小盒"),
            ("一两", "1两"),
            ("1两", "一两"),
        ]
        queue = [compact]
        for value in queue:
            for src, dst in replacements:
                if src in value:
                    changed = value.replace(src, dst)
                    if changed not in queue:
                        queue.append(changed)
        for value in queue:
            add(value)
        return variants or [compact]

    def _sku_where(
        self,
        keyword: str = "",
        status: Any = None,
        category_id: int | None = None,
        category_ids: Iterable[Any] | None = None,
        product_type: str = "",
        active_only: bool = False,
        listed_only: bool = False,
        listed_state: str = "",
        stock_mode: str = "",
        quality: str = "",
    ) -> tuple[str, list[Any]]:
        where = ["s.deleted_at IS NULL", "sp.deleted_at IS NULL"]
        params: list[Any] = []
        if active_only:
            where.append("s.status = 'active'")
        elif status not in (None, ""):
            status_map = {0: "active", 1: "inactive", 2: "stopped", 3: "deleted"}
            try:
                status_value = status_map.get(int(status), str(status))
            except (TypeError, ValueError):
                status_value = str(status)
            where.append("s.status = %s")
            params.append(status_value)
        elif listed_only:
            where.append("s.status = 'active'")
        if listed_only:
            where.append("s.is_listed = 1")
        listed_value = str(listed_state or "").strip().lower()
        if listed_value in {"listed", "1", "true", "yes"}:
            where.append("s.is_listed = 1")
        elif listed_value in {"unlisted", "0", "false", "no"}:
            where.append("s.is_listed = 0")
        stock_value = str(stock_mode or "").strip().lower()
        if stock_value in {"stock", "stock_item", "1", "true", "yes"}:
            where.append("s.is_stock_item = 1")
            where.append("COALESCE(s.inventory_policy, '') <> 'none'")
        elif stock_value in {"non_stock", "no_stock", "0", "false", "no"}:
            where.append("(s.is_stock_item = 0 OR COALESCE(s.inventory_policy, '') = 'none')")
        quality_value = str(quality or "").strip().lower()
        if quality_value == "missing_image":
            where.append(
                "("
                "NULLIF(TRIM(COALESCE(s.main_image_url, '')), '') IS NULL "
                "AND NOT EXISTS ("
                "  SELECT 1 FROM product_media pm "
                "  WHERE pm.spu_id = sp.id "
                "    AND pm.media_type = 'main_image' "
                "    AND pm.is_active = 1"
                ")"
                ")"
            )
        elif quality_value == "missing_case_pack":
            where.append("(sp.case_pack_qty IS NULL OR sp.case_pack_qty = 0)")
        elif quality_value == "missing_price":
            where.append("(COALESCE(s.retail_price, s.min_price, s.max_price, 0) <= 0)")
        product_type_values = [
            item.strip()
            for item in str(product_type or "").split(",")
            if item.strip()
        ]
        if product_type_values:
            placeholders = ",".join(["%s"] * len(product_type_values))
            where.append(f"sp.product_type IN ({placeholders})")
            params.extend(product_type_values)
        category_values: list[int] = []
        if category_id:
            category_values.append(int(category_id))
        for value in category_ids or []:
            try:
                item = int(value)
            except (TypeError, ValueError):
                continue
            if item and item not in category_values:
                category_values.append(item)
        if category_values:
            placeholders = ",".join(["%s"] * len(category_values))
            json_parts = " OR ".join(["JSON_CONTAINS(s.category_ids, %s)"] * len(category_values))
            where.append(f"(s.primary_category_id IN ({placeholders}) OR {json_parts})")
            params.extend(category_values)
            params.extend(json.dumps(item, ensure_ascii=False) for item in category_values)
        for term in self._keyword_terms(keyword):
            term_parts = []
            for variant in self._keyword_variants(term):
                like = f"%{variant}%"
                term_parts.append(
                    "("
                    "s.sku_no LIKE %s OR sp.title LIKE %s OR sp.series LIKE %s "
                    "OR s.color LIKE %s OR s.search_text LIKE %s "
                    "OR s.id IN ("
                    "  SELECT pa.target_id FROM product_alias pa "
                    "  WHERE pa.is_enabled = 1 "
                    "    AND pa.target_type='sku' "
                    "    AND (pa.alias LIKE %s OR pa.normalized_alias LIKE %s)"
                    ") "
                    "OR sp.id IN ("
                    "  SELECT pa.target_id FROM product_alias pa "
                    "  WHERE pa.is_enabled = 1 "
                    "    AND pa.target_type='spu' "
                    "    AND (pa.alias LIKE %s OR pa.normalized_alias LIKE %s)"
                    ")"
                    ")"
                )
                params.extend([like, like, like, like, like, like, like, like, like])
            where.append("(" + " OR ".join(term_parts) + ")")
        return " AND ".join(where), params

    def _product_select_sql(self) -> str:
        return """
            SELECT
                s.id, s.spu_id, s.sku_no, s.primary_category_id, s.category_ids,
                s.color, s.bag_type, s.tea_type, s.material_type, s.service_type,
                s.unit_id, s.min_purchase_qty, s.min_purchase_unit_id,
                s.inventory_policy, s.purchase_policy, s.default_warehouse_id,
                s.retail_price, s.min_price, s.max_price, s.cost_price, s.price_note,
                s.is_stock_item, s.is_sellable, s.is_listed, s.status,
                s.main_image_url, s.detail_image_urls, s.content_html, s.created_at, s.updated_at,
                sp.title, sp.product_type, sp.series, sp.size_label, sp.available_colors,
                sp.case_pack_qty, sp.default_category_id, sp.inventory_policy AS spu_inventory_policy,
                sp.purchase_policy AS spu_purchase_policy,
                (
                    SELECT pm.url
                    FROM product_media pm
                    WHERE pm.spu_id = sp.id
                      AND pm.sku_id IS NULL
                      AND pm.media_type = 'main_image'
                      AND pm.is_active = 1
                    ORDER BY pm.sort_order ASC, pm.id DESC
                    LIMIT 1
                ) AS spu_main_image_url,
                u.name AS unit_name, c.name AS primary_category_name,
                COALESCE(inv.total_qty, 0) AS inventory
            FROM product_sku s
            JOIN product_spu sp ON sp.id = s.spu_id
            LEFT JOIN product_unit u ON u.id = s.unit_id
            LEFT JOIN product_category c ON c.id = s.primary_category_id
            LEFT JOIN (
                SELECT sku_id, SUM(quantity) AS total_qty
                FROM inventory_balance
                GROUP BY sku_id
            ) inv ON inv.sku_id = s.id
        """

    def _product_category_name_lookup(self) -> dict[int, str]:
        cached = getattr(self, "_product_category_name_lookup_cache", None)
        if cached is not None:
            return cached
        rows = self.query("SELECT id, name FROM product_category WHERE is_enabled = 1")
        lookup = {
            int(row.get("id")): str(row.get("name") or f"分类#{row.get('id')}")
            for row in rows
            if row.get("id") not in (None, "")
        }
        self._product_category_name_lookup_cache = lookup
        return lookup

    def _piece_text(self, row: dict) -> str:
        qty = row.get("case_pack_qty")
        if qty in (None, ""):
            return ""
        return f"1件{_qty_text(qty)}套"

    def _status_text(self, status: str) -> str:
        return {
            "active": "正常",
            "inactive": "停用",
            "stopped": "停售",
            "deleted": "已删除",
        }.get(str(status or "active"), str(status or "正常"))

    def _sales_status_text(self, status: str) -> str:
        return {
            "draft": "草稿",
            "confirmed": "已确认",
            "completed": "已完成",
            "canceled": "已取消",
            "deleted": "已删除",
        }.get(str(status or ""), str(status or "状态"))

    def _row_to_product(self, row: dict) -> dict:
        category_ids = _json_loads(row.get("category_ids"), [])
        if not isinstance(category_ids, list):
            category_ids = []
        primary_category_id = row.get("primary_category_id") or row.get("default_category_id")
        if primary_category_id and int(primary_category_id) not in category_ids:
            category_ids = [int(primary_category_id)] + [int(item) for item in category_ids if str(item).isdigit()]
        category_names = _merge_category_names(
            category_ids,
            self._product_category_name_lookup(),
            row.get("primary_category_name") or "",
        )
        category_text = " / ".join(category_names)
        price = row.get("retail_price") or row.get("min_price") or row.get("max_price") or 0
        spec_image = _normalize_public_image_url(row.get("main_image_url") or _first_image(row.get("detail_image_urls")))
        spu_image = _normalize_public_image_url(row.get("spu_main_image_url") or "")
        image = _normalize_public_image_url(spu_image or spec_image)
        detail_images = _normalize_public_image_urls(row.get("detail_image_urls"))
        available_colors = _json_loads(row.get("available_colors"), [])
        if not isinstance(available_colors, list):
            available_colors = []
        title = row.get("title") or "商品"
        color = row.get("color") or ""
        purchase_policy = _normalize_purchase_policy(row.get("purchase_policy") or row.get("spu_purchase_policy"))
        return {
            "id": row.get("id"),
            "product_id": row.get("id"),
            "spu_id": row.get("spu_id"),
            "sku_no": row.get("sku_no") or "",
            "coding": row.get("sku_no") or "",
            "product_code": row.get("sku_no") or "",
            "title": title,
            "name": title,
            "series": row.get("series") or "",
            "size_label": row.get("size_label") or "",
            "product_type": row.get("product_type") or "",
            "inventory_policy": row.get("inventory_policy") or row.get("spu_inventory_policy") or "",
            "purchase_policy": purchase_policy,
            "is_one_case_purchase": 1 if purchase_policy == "one_case" else 0,
            "spec": color,
            "color": color,
            "available_colors": [str(item).strip() for item in available_colors if str(item or "").strip()],
            "bag_type": row.get("bag_type") or "",
            "tea_type": row.get("tea_type") or "",
            "simple_desc": self._piece_text(row),
            "piece_text": self._piece_text(row),
            "case_pack_qty": _qty_text(row.get("case_pack_qty")) if row.get("case_pack_qty") not in (None, "") else "",
            "unit_id": int(row.get("unit_id") or 1),
            "unit_name": row.get("unit_name") or "",
            "price": _money(price),
            "retail_price": _money(row.get("retail_price") or price),
            "min_price": _money(row.get("min_price") or price),
            "max_price": _money(row.get("max_price") or price),
            "cost_price": _money(row.get("cost_price")),
            "inventory": _qty_text(row.get("inventory")),
            "status": 0 if str(row.get("status") or "active") == "active" else 1,
            "native_status": row.get("status") or "active",
            "status_text": self._status_text(row.get("status") or "active"),
            "is_stock_item": int(row.get("is_stock_item") if row.get("is_stock_item") not in (None, "") else 1),
            "is_listed": int(row.get("is_listed") or 0),
            "system_goods_is_shelves": int(row.get("is_listed") or 0),
            "spu_main_image_url": spu_image,
            "spec_image_url": spec_image,
            "sku_image_url": spec_image,
            "images": image,
            "main_images": image,
            "main_images_list": [image] if image else [],
            "detail_image_urls": detail_images,
            "content": _normalize_public_image_text(row.get("content_html") or ""),
            "product_category_ids": category_ids,
            "product_category_names": category_names,
            "product_category_text": category_text,
            "base": [{
                "id": row.get("id"),
                "unit_id": int(row.get("unit_id") or 1),
                "coding": row.get("sku_no") or "",
                "price": _money(price),
                "cost_price": _money(row.get("cost_price")),
                "images": spec_image,
                "is_stock_item": int(row.get("is_stock_item") if row.get("is_stock_item") not in (None, "") else 1),
                "purchase_policy": purchase_policy,
            }],
        }

    def product_search(self, keyword: str, limit: int = 80, *, listed_only: bool = False) -> list[dict]:
        where_sql, params = self._sku_where(keyword, active_only=True, listed_only=listed_only)
        rows = self.query(
            f"""
            {self._product_select_sql()}
            WHERE {where_sql}
            ORDER BY
              CASE WHEN s.sku_no = %s THEN 0 WHEN sp.title LIKE %s THEN 1 ELSE 2 END,
              sp.title ASC, s.color ASC, s.id ASC
            LIMIT %s
            """,
            params + [keyword, f"%{keyword}%", max(1, min(limit, 300))],
        )
        return [self._row_to_product(row) for row in rows]

    def product_info(self, product_id: int, *, listed_only: bool = False) -> dict | None:
        sku_id = self.resolve_sku_id(product_id)
        if not sku_id:
            return None
        listed_clause = " AND s.status = 'active' AND s.is_listed = 1" if listed_only else ""
        rows = self.query(
            f"{self._product_select_sql()} WHERE s.id = %s{listed_clause} LIMIT 1",
            (sku_id,),
        )
        if not rows:
            return None
        product = self._row_to_product(rows[0])
        if listed_only:
            product = self._hydrate_product_group_summary(product, listed_only=True)
        return product

    def _hydrate_product_group_summary(self, product: dict, *, listed_only: bool = False) -> dict:
        spu_id = product.get("spu_id")
        if not spu_id:
            return product
        listed_clause = " AND s.status = 'active' AND s.is_listed = 1" if listed_only else ""
        rows = self.query(
            f"""
            {self._product_select_sql()}
            WHERE s.spu_id = %s AND s.deleted_at IS NULL AND sp.deleted_at IS NULL{listed_clause}
            ORDER BY s.color ASC, s.id ASC
            """,
            (spu_id,),
        )
        variants = [self._row_to_product(row) for row in rows]
        if not variants:
            return product
        color_names, color_text, color_count = self._product_color_summary(variants)
        product["product_group_data"] = variants
        product["spec_count"] = len(variants)
        product["color_count"] = color_count
        product["color_names"] = color_names
        product["color_text"] = color_text
        product["available_colors"] = color_names
        return product

    def _product_color_summary(self, variants: list[dict]) -> tuple[list[str], str, int]:
        colors: list[str] = []
        for item in variants:
            clean = str(item.get("color") or item.get("spec") or "").strip()
            if clean and clean not in colors:
                colors.append(clean)
        if not colors and variants:
            colors.append("默认颜色")
        return colors, " / ".join(colors), len(colors)

    def _product_sort_mode(self, sort: Any = "") -> str:
        value = str(sort or "").strip().lower().replace("-", "_")
        if value in {"latest", "new", "newest", "updated"}:
            return "latest"
        if value in {"price", "price_asc", "price_low", "price_low_to_high"}:
            return "price_asc"
        if value in {"sales", "popular", "hot", "comprehensive", "best"}:
            return "sales"
        return "default"

    def _product_sales_rank_join_sql(self) -> str:
        return """
            LEFT JOIN (
                SELECT
                    i.sku_id,
                    SUM(i.quantity) AS sold_qty,
                    SUM(i.amount) AS sales_amount,
                    COUNT(DISTINCT so.id) AS order_count,
                    MAX(so.sales_at) AS latest_sales_at
                FROM sales_order_item i
                JOIN sales_order so ON so.id = i.sales_order_id
                WHERE so.deleted_at IS NULL
                  AND so.status NOT IN ('canceled', 'deleted')
                  AND so.sales_at >= DATE_SUB(CURDATE(), INTERVAL 90 DAY)
                  AND so.sales_at < DATE_ADD(CURDATE(), INTERVAL 1 DAY)
                GROUP BY i.sku_id
            ) sales_rank ON sales_rank.sku_id = s.id
        """

    def product_list(
        self,
        keyword: str = "",
        page: int = 1,
        page_size: int = 20,
        status: Any = None,
        category_id: int | None = None,
        group: bool = False,
        category_ids: Iterable[Any] | None = None,
        product_type: str = "",
        listed_only: bool = False,
        sort: Any = "",
        listed_state: str = "",
        stock_mode: str = "",
        quality: str = "",
    ) -> tuple[list[dict], int]:
        page = max(1, int(page or 1))
        page_size = max(1, min(int(page_size or 20), 200))
        offset = (page - 1) * page_size
        sort_mode = self._product_sort_mode(sort)
        price_sql = "COALESCE(NULLIF(s.retail_price, 0), NULLIF(s.min_price, 0), NULLIF(s.max_price, 0))"
        listed_value = str(listed_state or "").strip().lower()
        group_listed_filter = group and listed_value in {"listed", "1", "true", "yes", "unlisted", "0", "false", "no"}
        where_sql, params = self._sku_where(
            keyword,
            status=status,
            category_id=category_id,
            category_ids=category_ids,
            product_type=product_type,
            listed_only=listed_only,
            listed_state="" if group_listed_filter else listed_state,
            stock_mode=stock_mode,
            quality=quality,
        )
        if not group:
            order_sql = "s.updated_at DESC, s.id DESC"
            if sort_mode == "price_asc":
                order_sql = f"({price_sql} IS NULL) ASC, {price_sql} ASC, s.updated_at DESC, s.id DESC"
            elif sort_mode == "sales":
                order_sql = (
                    "COALESCE(sales_rank.sold_qty, 0) DESC, "
                    "COALESCE(sales_rank.sales_amount, 0) DESC, "
                    "COALESCE(sales_rank.latest_sales_at, '1970-01-01') DESC, "
                    "s.updated_at DESC, s.id DESC"
                )
            sales_rank_join_sql = self._product_sales_rank_join_sql() if sort_mode == "sales" else ""
            total_rows = self.query(
                f"{self._product_select_sql()} WHERE {where_sql}",
                params,
            )
            total = len(total_rows)
            rows = self.query(
                f"""
                {self._product_select_sql()}
                {sales_rank_join_sql}
                WHERE {where_sql}
                ORDER BY {order_sql}
                LIMIT %s OFFSET %s
                """,
                params + [page_size, offset],
            )
            return [self._row_to_product(row) for row in rows], total

        listed_having_sql = ""
        if group_listed_filter:
            if listed_value in {"listed", "1", "true", "yes"}:
                listed_having_sql = "HAVING listed_sku_count > 0"
            else:
                listed_having_sql = "HAVING listed_sku_count = 0"

        total_rows = self.query(
            f"""
            SELECT COUNT(*) AS total
            FROM (
                SELECT sp.id AS spu_id,
                       SUM(CASE WHEN s.status = 'active' AND s.is_listed = 1 THEN 1 ELSE 0 END) AS listed_sku_count
                FROM product_sku s
                JOIN product_spu sp ON sp.id = s.spu_id
                WHERE {where_sql}
                GROUP BY sp.id
                {listed_having_sql}
            ) grouped_product
            """,
            params,
        )
        total = int(total_rows[0].get("total") or 0) if total_rows else 0
        group_order_sql = "latest_time DESC, latest_id DESC"
        if sort_mode == "price_asc":
            group_order_sql = "min_price IS NULL ASC, min_price ASC, latest_time DESC, latest_id DESC"
        elif sort_mode == "sales":
            group_order_sql = "sold_qty DESC, sales_amount DESC, latest_sales_at DESC, latest_time DESC, latest_id DESC"
        sales_rank_join_sql = self._product_sales_rank_join_sql() if sort_mode == "sales" else ""
        sales_rank_select_sql = (
            """
                   COALESCE(SUM(sales_rank.sold_qty), 0) AS sold_qty,
                   COALESCE(SUM(sales_rank.sales_amount), 0) AS sales_amount,
                   COALESCE(MAX(sales_rank.latest_sales_at), '1970-01-01') AS latest_sales_at
            """
            if sort_mode == "sales"
            else """
                   0 AS sold_qty,
                   0 AS sales_amount,
                   '1970-01-01' AS latest_sales_at
            """
        )
        group_rows = self.query(
            f"""
            SELECT sp.id AS spu_id,
                   MAX(s.updated_at) AS latest_time,
                   MAX(s.id) AS latest_id,
                   MIN({price_sql}) AS min_price,
                   SUM(CASE WHEN s.status = 'active' AND s.is_listed = 1 THEN 1 ELSE 0 END) AS listed_sku_count,
                   {sales_rank_select_sql}
            FROM product_sku s
            JOIN product_spu sp ON sp.id = s.spu_id
            {sales_rank_join_sql}
            WHERE {where_sql}
            GROUP BY sp.id
            {listed_having_sql}
            ORDER BY {group_order_sql}
            LIMIT %s OFFSET %s
            """,
            params + [page_size, offset],
        )
        spu_ids = [int(row["spu_id"]) for row in group_rows if row.get("spu_id")]
        if not spu_ids:
            return [], total
        placeholders = ",".join(["%s"] * len(spu_ids))
        rows = self.query(
            f"""
            {self._product_select_sql()}
            WHERE s.spu_id IN ({placeholders}) AND s.deleted_at IS NULL AND sp.deleted_at IS NULL
              {"AND s.status = 'active' AND s.is_listed = 1" if listed_only else ""}
            ORDER BY sp.title ASC, s.color ASC, s.id ASC
            """,
            spu_ids,
        )
        by_spu: dict[int, list[dict]] = {spu_id: [] for spu_id in spu_ids}
        for row in rows:
            by_spu.setdefault(int(row.get("spu_id") or 0), []).append(self._row_to_product(row))

        items: list[dict] = []
        for spu_id in spu_ids:
            variants = by_spu.get(spu_id) or []
            if not variants:
                continue
            primary = next((item for item in variants if item.get("images")), variants[0]).copy()
            inventories = [_num(item.get("inventory")) for item in variants]
            prices = [_num(item.get("price")) for item in variants if _num(item.get("price")) > 0]
            categories = []
            category_texts = []
            for item in variants:
                for cid in item.get("product_category_ids") or []:
                    if cid not in categories:
                        categories.append(cid)
                text = item.get("product_category_text") or ""
                if text and text not in category_texts:
                    category_texts.append(text)
            color_names, color_text, color_count = self._product_color_summary(variants)
            primary["product_group_data"] = variants
            primary["spec_count"] = len(variants)
            primary["color_count"] = color_count
            primary["color_names"] = color_names
            primary["color_text"] = color_text
            primary["available_colors"] = color_names
            primary["inventory"] = _qty_text(sum(inventories))
            if prices:
                primary["price"] = _money(min(prices))
                primary["min_price"] = _money(min(prices))
                primary["max_price"] = _money(max(prices))
            primary["product_category_ids"] = categories
            primary["product_category_text"] = " / ".join(category_texts[:3])
            primary["is_stock_item"] = 1 if any(int(v.get("is_stock_item") or 0) for v in variants) else 0
            listed_variants = [
                v for v in variants
                if int(v.get("system_goods_is_shelves") or 0) == 1 and str(v.get("native_status") or "active") == "active"
            ]
            primary["listed_sku_count"] = len(listed_variants)
            primary["unlisted_sku_count"] = max(0, len(variants) - len(listed_variants))
            primary["is_listed"] = 1 if listed_variants else 0
            primary["system_goods_is_shelves"] = primary["is_listed"]
            items.append(primary)
        return items, total

    def product_categories(
        self,
        *,
        listed_only: bool = False,
        exclude_names: Iterable[str] | None = None,
    ) -> list[dict]:
        join_filters = ["s.deleted_at IS NULL"]
        if listed_only:
            join_filters.extend(["s.status = 'active'", "s.is_listed = 1"])
        where = ["c.is_enabled = 1"]
        params: list[Any] = []
        excluded = [str(item).strip() for item in (exclude_names or []) if str(item or "").strip()]
        if excluded:
            placeholders = ",".join(["%s"] * len(excluded))
            where.append(f"c.name NOT IN ({placeholders})")
            params.extend(excluded)
        having_sql = "HAVING total > 0" if listed_only else ""
        rows = self.query(
            f"""
            SELECT c.id, c.parent_id, c.name, c.product_type, c.inventory_policy, c.sort_order, c.is_enabled,
                   c.icon, c.icon_active, c.realistic_images, c.big_images,
                   COUNT(DISTINCT CASE WHEN sp.id IS NOT NULL THEN s.spu_id END) AS total
            FROM product_category c
            LEFT JOIN product_sku s
              ON (s.primary_category_id = c.id OR JSON_CONTAINS(s.category_ids, CAST(c.id AS CHAR)))
             AND {" AND ".join(join_filters)}
            LEFT JOIN product_spu sp
              ON sp.id = s.spu_id AND sp.deleted_at IS NULL
            WHERE {" AND ".join(where)}
            GROUP BY c.id
            {having_sql}
            ORDER BY COALESCE(c.sort_order, 0) DESC, c.id ASC
            """,
            params,
        )
        return [
            {
                "id": row.get("id"),
                "pid": row.get("parent_id") or 0,
                "name": row.get("name") or f"分类#{row.get('id')}",
                "product_type": row.get("product_type") or "",
                "inventory_policy": row.get("inventory_policy") or "",
                "icon": row.get("icon") or "",
                "icon_active": row.get("icon_active") or "",
                "realistic_images": row.get("realistic_images") or "",
                "big_images": row.get("big_images") or "",
                "total": int(row.get("total") or 0),
            }
            for row in rows
        ]

    def miniapp_assets(self, scene: str | None = None, include_disabled: bool = False) -> list[dict]:
        where = [] if include_disabled else ["enabled=1"]
        params: list[Any] = []
        if scene:
            where.append("scene=%s")
            params.append(str(scene))
        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        return self.query(
            f"""
            SELECT id, scene, name, asset_url, active_asset_url,
                   link_type, link_value, badge_text, subtitle,
                   sort_order, enabled, extra_json
            FROM miniapp_asset
            {where_sql}
            ORDER BY sort_order DESC, id ASC
            """,
            params,
        )

    def update_miniapp_asset_image(self, asset_id: int, field: str, url: str) -> dict:
        allowed = {"asset_url", "active_asset_url"}
        if field not in allowed:
            return {"code": 400, "msg": "不支持的小程序图片字段"}
        clean_url = str(url or "").strip()
        rows = self.query("SELECT id FROM miniapp_asset WHERE id=%s", (int(asset_id),))
        if not rows:
            return {"code": 404, "msg": "小程序图片配置不存在"}
        affected = self.execute(
            f"UPDATE miniapp_asset SET {field}=%s, updated_at=%s WHERE id=%s",
            (clean_url, _now(), int(asset_id)),
        )
        return {"code": 0, "data": {"id": int(asset_id), field: clean_url, "affected": affected}}

    def create_miniapp_asset(
        self,
        *,
        scene: str,
        name: str,
        asset_url: str = "",
        active_asset_url: str = "",
        link_type: str = "page",
        link_value: str = "",
        badge_text: str = "",
        subtitle: str = "",
        sort_order: int = 0,
        enabled: int = 1,
        extra_json: Any = None,
    ) -> dict:
        clean_scene = str(scene or "").strip()
        if clean_scene != "home_banner":
            return {"code": 400, "msg": "当前只支持新增首页轮播图"}
        clean_name = str(name or "").strip() or "首页轮播"
        now = _now()
        extra_text = json.dumps(extra_json, ensure_ascii=False) if isinstance(extra_json, (dict, list)) else extra_json
        with self.transaction() as cursor:
            cursor.execute(
                """
                INSERT INTO miniapp_asset
                    (scene, name, asset_url, active_asset_url, link_type, link_value,
                     badge_text, subtitle, sort_order, enabled, extra_json, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    clean_scene,
                    clean_name,
                    str(asset_url or "").strip(),
                    str(active_asset_url or "").strip(),
                    str(link_type or "page").strip(),
                    str(link_value or "").strip(),
                    str(badge_text or "").strip(),
                    str(subtitle or "").strip(),
                    int(sort_order or 0),
                    1 if int(enabled or 0) else 0,
                    extra_text,
                    now,
                    now,
                ),
            )
            asset_id = int(cursor.lastrowid or 0)
        return {
            "code": 0,
            "data": {
                "id": asset_id,
                "scene": clean_scene,
                "name": clean_name,
                "asset_url": str(asset_url or "").strip(),
                "active_asset_url": str(active_asset_url or "").strip(),
                "link_type": str(link_type or "page").strip(),
                "link_value": str(link_value or "").strip(),
                "badge_text": str(badge_text or "").strip(),
                "subtitle": str(subtitle or "").strip(),
                "sort_order": int(sort_order or 0),
                "enabled": 1 if int(enabled or 0) else 0,
            },
        }

    def delete_miniapp_asset(self, asset_id: int) -> dict:
        clean_id = int(asset_id or 0)
        rows = self.query("SELECT id, scene FROM miniapp_asset WHERE id=%s", (clean_id,))
        if not rows:
            return {"code": 404, "msg": "小程序图片配置不存在"}
        if str(rows[0].get("scene") or "") != "home_banner":
            return {"code": 400, "msg": "只能删除首页轮播图"}
        affected = self.execute("DELETE FROM miniapp_asset WHERE id=%s AND scene=%s", (clean_id, "home_banner"))
        return {"code": 0, "data": {"id": clean_id, "affected": affected}}

    def update_product_category_image(self, category_id: int, field: str, url: str) -> dict:
        allowed = {"icon", "icon_active"}
        if field not in allowed:
            return {"code": 400, "msg": "不支持的分类图片字段"}
        clean_url = str(url or "").strip()
        rows = self.query("SELECT id FROM product_category WHERE id=%s", (int(category_id),))
        if not rows:
            return {"code": 404, "msg": "商品分类不存在"}
        affected = self.execute(
            f"UPDATE product_category SET {field}=%s, updated_at=%s WHERE id=%s",
            (clean_url, _now(), int(category_id)),
        )
        return {"code": 0, "data": {"id": int(category_id), field: clean_url, "affected": affected}}

    def product_options(self, product_id: int | None = None) -> dict:
        categories = self.product_categories()
        units = self.query(
            "SELECT id, name, code FROM product_unit WHERE is_enabled=1 ORDER BY id ASC"
        )
        data: dict[str, Any] = {
            "product_category": categories,
            "unit_list": units,
            "media_assets": self.product_media_assets(include_pending=True, limit=60),
            "product_status_list": [
                {"value": 0, "name": "正常"},
                {"value": 1, "name": "停用"},
                {"value": 2, "name": "停售"},
                {"value": 3, "name": "停产"},
            ],
        }
        if product_id:
            product = self.product_info(product_id)
            if product:
                items, _ = self.product_list(keyword="", page=1, page_size=1, group=True)
                spu_id = product.get("spu_id")
                grouped = None
                if spu_id:
                    rows = self.query(
                        f"{self._product_select_sql()} WHERE s.spu_id=%s AND s.deleted_at IS NULL ORDER BY s.color ASC, s.id ASC",
                        (spu_id,),
                    )
                    variants = [self._row_to_product(row) for row in rows]
                    grouped = product.copy()
                    grouped["product_group_data"] = variants
                    grouped["spec_count"] = len(variants)
                    color_names, color_text, color_count = self._product_color_summary(variants)
                    grouped["color_count"] = color_count
                    grouped["color_names"] = color_names
                    grouped["color_text"] = color_text
                    grouped["available_colors"] = color_names
                    grouped["media_assets"] = self.product_media_assets(
                        spu_id=int(spu_id),
                        sku_ids=[int(item.get("id")) for item in variants if item.get("id")],
                        include_pending=True,
                    )
                    if variants:
                        grouped["product_category_ids"] = variants[0].get("product_category_ids", [])
                data["data"] = grouped or product
        return data

    def _parse_case_pack_qty(self, simple_desc: str) -> Decimal | None:
        text = str(simple_desc or "")
        match = re.search(r"(\d+(?:\.\d+)?)\s*(?:套|个|张)?\s*/\s*件", text)
        if not match:
            match = re.search(r"1\s*件\s*(\d+(?:\.\d+)?)", text)
        if not match:
            match = re.search(r"(\d+(?:\.\d+)?)\s*(?:套|个|张)", text)
        return Decimal(match.group(1)) if match else None

    def _payload_is_bag_product(
        self,
        cursor,
        *,
        product_type: str = "",
        category_ids: list[int] | None = None,
        bag_type: str = "",
    ) -> bool:
        product_type_text = str(product_type or "").strip().lower()
        if product_type_text in {"bag", "bubble_bag"}:
            return True
        if str(bag_type or "").strip() and product_type_text in {"bag", "bubble_bag"}:
            return True
        clean_ids = [int(item) for item in (category_ids or []) if str(item).isdigit()]
        if not clean_ids:
            return False
        placeholders = ",".join(["%s"] * len(clean_ids))
        cursor.execute(
            f"""
            SELECT id
            FROM product_category
            WHERE id IN ({placeholders})
              AND (
                product_type='bag'
                OR name LIKE %s
                OR name LIKE %s
              )
            LIMIT 1
            """,
            clean_ids + ["%泡袋%", "%茶袋%"],
        )
        return cursor.fetchone() is not None

    def _sequence_code(self, prefix: str, number: int, pad_width: int = 4) -> str:
        clean_prefix = re.sub(r"[^0-9A-Za-z]", "", str(prefix or "SJ")).upper()[:20] or "SJ"
        clean_width = max(1, min(int(pad_width or 4), 10))
        return f"{clean_prefix}{max(int(number or 1), 1):0{clean_width}d}"

    def _sku_sequence_row(self, cursor, *, lock: bool = False) -> dict:
        self._ensure_number_sequence_tables()
        self._ensure_system_settings_tables()
        sql = """
            SELECT sequence_key, prefix, start_number, next_number, pad_width, skipped_numbers, note, updated_by_user_id, updated_at
            FROM number_sequence_setting
            WHERE sequence_key='product_sku'
            LIMIT 1
        """
        if lock:
            sql += " FOR UPDATE"
        cursor.execute(sql)
        row = cursor.fetchone()
        if row:
            return row
        now = _now()
        cursor.execute(
            """
            INSERT INTO number_sequence_setting
                (sequence_key, prefix, start_number, next_number, pad_width, skipped_numbers, note, created_at, updated_at)
            VALUES ('product_sku', 'SJ', 1001, 1001, 4, '[]', '商品 SKU 编号', %s, %s)
            """,
            (now, now),
        )
        cursor.execute(sql)
        return cursor.fetchone() or {
            "sequence_key": "product_sku",
            "prefix": "SJ",
            "start_number": 1001,
            "next_number": 1001,
            "pad_width": 4,
            "skipped_numbers": "[]",
        }

    def _sequence_skip_numbers(self, value: Any) -> set[int]:
        raw = _json_loads(value, [])
        if isinstance(raw, str):
            raw = re.split(r"[\s,，、]+", raw)
        if not isinstance(raw, list):
            raw = []
        result: set[int] = set()
        for item in raw:
            text = str(item or "").strip().upper()
            match = re.search(r"(\d+)$", text)
            if match:
                number = int(match.group(1))
                if number > 0:
                    result.add(number)
        return result

    def _next_sequence_code(self, cursor, *, prefix: str, start_number: int, pad_width: int, skipped_numbers: set[int] | None = None) -> str:
        clean_prefix = re.sub(r"[^0-9A-Za-z]", "", str(prefix or "SJ")).upper()[:20] or "SJ"
        cursor.execute(
            """
            SELECT sku_no
            FROM product_sku
            WHERE sku_no LIKE %s
            """,
            (f"{clean_prefix}%",),
        )
        used = {str(row.get("sku_no") or "").upper() for row in cursor.fetchall()}
        skipped = skipped_numbers or set()
        number = max(int(start_number or 1), 1)
        while True:
            code = self._sequence_code(clean_prefix, number, pad_width)
            if number not in skipped and code.upper() not in used:
                return code
            number += 1

    def _next_sku_no(self, cursor, *, start_number: int = 1, compact_from_start: bool = False) -> str:
        if compact_from_start:
            row = self._sku_sequence_row(cursor)
            prefix = row.get("prefix") or "SJ"
            pad_width = int(row.get("pad_width") or 4)
            configured_start = max(int(row.get("start_number") or 1), int(row.get("next_number") or 1))
            return self._next_sequence_code(
                cursor,
                prefix=prefix,
                start_number=max(int(start_number or 1), configured_start, 1),
                pad_width=pad_width,
                skipped_numbers=self._sequence_skip_numbers(row.get("skipped_numbers")),
            )
        cursor.execute(
            """
            SELECT sku_no
            FROM product_sku
            WHERE sku_no REGEXP '^SJ[0-9]+$'
            ORDER BY CAST(SUBSTRING(sku_no, 3) AS UNSIGNED) DESC
            LIMIT 1
            """
        )
        row = cursor.fetchone() or {}
        match = re.search(r"SJ(\d+)", str(row.get("sku_no") or ""))
        next_no = int(match.group(1)) + 1 if match else 1
        return f"SJ{next_no:04d}"

    def _sku_no_available(self, cursor, sku_no: str, current_id: int | None = None) -> bool:
        if not sku_no:
            return False
        cursor.execute("SELECT id FROM product_sku WHERE sku_no=%s LIMIT 1", (sku_no,))
        row = cursor.fetchone()
        return not row or (current_id is not None and int(row.get("id") or 0) == int(current_id))

    def _put_product_media(
        self,
        cursor,
        *,
        sku_id: int | None,
        spu_id: int | None,
        media_type: str,
        url: str,
        storage: str = "oss",
        sort_order: int = 0,
        source: str = "native_api",
    ) -> None:
        url = str(url or "").strip()
        if not url:
            return
        now = _now()
        cursor.execute(
            """
            UPDATE product_media
            SET sku_id=%s, spu_id=%s, media_type=%s, storage=%s, sort_order=%s,
                is_active=1, source=%s, updated_at=%s
            WHERE url=%s
              AND (
                (media_type='pending' AND sku_id IS NULL AND spu_id IS NULL)
                OR (media_type=%s AND sku_id <=> %s AND spu_id <=> %s)
              )
            LIMIT 1
            """,
            (sku_id, spu_id, media_type, storage, sort_order, source, now, url, media_type, sku_id, spu_id),
        )
        if cursor.rowcount:
            return
        cursor.execute(
            """
            INSERT INTO product_media
                (sku_id, spu_id, media_type, url, storage, sort_order, is_active, source, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, 1, %s, %s, %s)
            """,
            (sku_id, spu_id, media_type, url, storage, sort_order, source, now, now),
        )

    def _replace_product_media(
        self,
        cursor,
        *,
        sku_id: int | None,
        spu_id: int | None,
        media_type: str,
        urls: list[str],
        storage: str = "oss",
    ) -> None:
        now = _now()
        cursor.execute(
            """
            UPDATE product_media
            SET is_active=0, updated_at=%s
            WHERE media_type=%s AND sku_id <=> %s AND spu_id <=> %s
            """,
            (now, media_type, sku_id, spu_id),
        )
        seen: set[str] = set()
        for index, url in enumerate(urls):
            clean_url = str(url or "").strip()
            if not clean_url or clean_url in seen:
                continue
            seen.add(clean_url)
            self._put_product_media(
                cursor,
                sku_id=sku_id,
                spu_id=spu_id,
                media_type=media_type,
                url=clean_url,
                storage=storage,
                sort_order=index,
            )

    def record_product_upload(self, url: str, storage: str = "oss") -> None:
        clean_url = str(url or "").strip()
        if not clean_url:
            return
        with self.transaction() as cursor:
            self._put_product_media(
                cursor,
                sku_id=None,
                spu_id=None,
                media_type="pending",
                url=clean_url,
                storage=storage,
                sort_order=0,
                source="upload",
            )

    def product_media_assets(
        self,
        *,
        spu_id: int | None = None,
        sku_ids: list[int] | None = None,
        media_type: str = "",
        include_pending: bool = True,
        limit: int = 120,
    ) -> list[dict]:
        scope_parts: list[str] = []
        params: list[Any] = []
        type_clause = ""
        type_params: list[Any] = []
        normalized_media_type = _media_type(media_type)
        if normalized_media_type:
            raw_types = {
                "main_image": ["main_image", "main"],
                "detail_image": ["detail_image", "detail"],
                "color_image": ["color_image", "image"],
                "pending": ["pending"],
            }.get(normalized_media_type, [normalized_media_type])
            placeholders = ",".join(["%s"] * len(raw_types))
            type_clause = f" AND pm.media_type IN ({placeholders})"
            type_params.extend(raw_types)
        if spu_id:
            scope_parts.append("(pm.spu_id=%s OR s.spu_id=%s)")
            params.extend([int(spu_id), int(spu_id)])
        clean_sku_ids = [int(item) for item in (sku_ids or []) if item]
        if clean_sku_ids:
            placeholders = ",".join(["%s"] * len(clean_sku_ids))
            scope_parts.append(f"pm.sku_id IN ({placeholders})")
            params.extend(clean_sku_ids)
        if include_pending and (spu_id or clean_sku_ids):
            scope_parts.append("(pm.sku_id IS NULL AND pm.spu_id IS NULL AND pm.media_type='pending')")
        if not scope_parts:
            scope_parts.append("1=1")
        requested_limit = max(1, min(int(limit or 120), 6000))
        raw_limit = max(requested_limit * 10, 8000)
        raw_limit = min(raw_limit, 12000)
        rows = self.query(
            f"""
            SELECT pm.id, pm.sku_id, COALESCE(pm.spu_id, s.spu_id) AS spu_id,
                   pm.spu_id AS media_spu_id, pm.media_type, pm.url, pm.storage, pm.file_name,
                   pm.sort_order, pm.is_active, pm.source, pm.created_at, pm.updated_at,
                   sp.title AS spu_title, sp.product_type, sp.series, sp.size_label,
                   COALESCE(sp.default_category_id, s.primary_category_id) AS category_id,
                   pc.name AS category_name, pc.product_type AS category_product_type,
                   s.sku_no, s.color AS sku_color, s.bag_type, COALESCE(s.tea_type, sp.tea_type) AS tea_type
            FROM product_media pm
            LEFT JOIN product_sku s ON s.id = pm.sku_id AND s.deleted_at IS NULL
            LEFT JOIN product_spu sp ON sp.id = COALESCE(pm.spu_id, s.spu_id) AND sp.deleted_at IS NULL
            LEFT JOIN product_category pc ON pc.id = COALESCE(sp.default_category_id, s.primary_category_id)
            WHERE pm.is_active=1 AND ({' OR '.join(scope_parts)}){type_clause}
            ORDER BY
              CASE pm.media_type
                WHEN 'main_image' THEN 0
                WHEN 'main' THEN 0
                WHEN 'color_image' THEN 1
                WHEN 'image' THEN 1
                WHEN 'detail_image' THEN 2
                WHEN 'detail' THEN 2
                WHEN 'pending' THEN 3
                ELSE 9
              END,
              sort_order ASC, id DESC
            LIMIT %s
            """,
            params + type_params + [raw_limit],
        )
        if not normalized_media_type or normalized_media_type == "color_image":
            color_scope_parts: list[str] = ["s.deleted_at IS NULL", "NULLIF(s.main_image_url, '') IS NOT NULL"]
            color_params: list[Any] = []
            if spu_id:
                color_scope_parts.append("s.spu_id=%s")
                color_params.append(int(spu_id))
            if clean_sku_ids:
                placeholders = ",".join(["%s"] * len(clean_sku_ids))
                color_scope_parts.append(f"s.id IN ({placeholders})")
                color_params.extend(clean_sku_ids)
            color_rows = self.query(
                f"""
                SELECT NULL AS id, s.id AS sku_id, s.spu_id,
                       NULL AS media_spu_id, 'color_image' AS media_type,
                       s.main_image_url AS url, 'oss' AS storage, '' AS file_name,
                       0 AS sort_order, 1 AS is_active, 'sku_image' AS source,
                       s.created_at, s.updated_at,
                       sp.title AS spu_title, sp.product_type, sp.series, sp.size_label,
                       COALESCE(sp.default_category_id, s.primary_category_id) AS category_id,
                       pc.name AS category_name, pc.product_type AS category_product_type,
                       s.sku_no, s.color AS sku_color, s.bag_type, COALESCE(s.tea_type, sp.tea_type) AS tea_type
                FROM product_sku s
                JOIN product_spu sp ON sp.id = s.spu_id AND sp.deleted_at IS NULL
                LEFT JOIN product_category pc ON pc.id = COALESCE(sp.default_category_id, s.primary_category_id)
                WHERE {' AND '.join(color_scope_parts)}
                ORDER BY sp.default_category_id ASC, sp.title ASC, s.color ASC, s.id ASC
                LIMIT %s
                """,
                color_params + [raw_limit],
            )
            rows.extend(color_rows)
        type_text = {
            "main": "主图",
            "main_image": "主图",
            "detail": "详情页",
            "detail_image": "详情页",
            "color_image": "颜色图",
            "pending": "待绑定",
            "image": "颜色图",
        }
        result = []
        seen_assets: set[tuple[str, str, str, str]] = set()
        for row in rows:
            normalized_type = _media_type(row.get("media_type"))
            url = str(row.get("url") or "")
            row_spu_id = str(row.get("spu_id") or "")
            if normalized_type == "main_image":
                dedupe_key = (normalized_type, row_spu_id or f"url:{url}", "", "")
            elif normalized_type == "detail_image":
                dedupe_key = (normalized_type, row_spu_id, url, "")
            elif normalized_type == "color_image":
                dedupe_key = (normalized_type, row_spu_id, str(row.get("sku_color") or row.get("sku_id") or ""), url)
            else:
                dedupe_key = (normalized_type, row_spu_id, url, str(row.get("id") or ""))
            if dedupe_key in seen_assets:
                continue
            seen_assets.add(dedupe_key)
            product_name = row.get("spu_title") or ""
            color = row.get("sku_color") or ""
            if not product_name and row.get("spu_id"):
                product_name = f"产品#{row.get('spu_id')}"
            binding_text = "待绑定"
            if product_name:
                binding_text = product_name
                if normalized_type == "color_image" and color:
                    binding_text = f"{product_name} / {color}"
            group_key, group_text, series, size_label, group_order = _asset_group_info(row)
            result.append({
                "id": row.get("id"),
                "sku_id": row.get("sku_id"),
                "spu_id": row.get("spu_id"),
                "media_spu_id": row.get("media_spu_id"),
                "spu_title": row.get("spu_title") or "",
                "product_type": row.get("product_type") or "",
                "category_product_type": row.get("category_product_type") or "",
                "bag_type": row.get("bag_type") or "",
                "tea_type": row.get("tea_type") or "",
                "series": series,
                "size_label": size_label,
                "product_name": product_name,
                "binding_text": binding_text,
                "category_id": row.get("category_id"),
                "category_name": _normalize_asset_category_name(row.get("category_name")),
                "asset_group_key": group_key,
                "asset_group_text": group_text,
                "asset_group_order": group_order,
                "sku_no": row.get("sku_no") or "",
                "sku_color": color,
                "media_type": normalized_type,
                "raw_media_type": row.get("media_type") or "",
                "media_type_text": type_text.get(normalized_type, type_text.get(str(row.get("media_type") or ""), str(row.get("media_type") or ""))),
                "url": url,
                "storage": row.get("storage") or "",
                "source": row.get("source") or "",
                "source_text": _source_text(row.get("source")),
                "sort_order": int(row.get("sort_order") or 0),
                "created_at": str(row.get("created_at") or ""),
                "updated_at": str(row.get("updated_at") or ""),
            })
        return result[:requested_limit]

    def product_media_assets_page(
        self,
        *,
        spu_id: int | None = None,
        sku_ids: list[int] | None = None,
        media_type: str = "",
        include_pending: bool = True,
        page: int = 1,
        page_size: int = 80,
    ) -> tuple[list[dict], int]:
        scope_parts: list[str] = []
        params: list[Any] = []
        type_clause = ""
        type_params: list[Any] = []
        normalized_media_type = _media_type(media_type)
        if normalized_media_type:
            raw_types = {
                "main_image": ["main_image", "main"],
                "detail_image": ["detail_image", "detail"],
                "color_image": ["color_image", "image"],
                "pending": ["pending"],
            }.get(normalized_media_type, [normalized_media_type])
            placeholders = ",".join(["%s"] * len(raw_types))
            type_clause = f" AND pm.media_type IN ({placeholders})"
            type_params.extend(raw_types)
        if spu_id:
            scope_parts.append("(pm.spu_id=%s OR s.spu_id=%s)")
            params.extend([int(spu_id), int(spu_id)])
        clean_sku_ids = [int(item) for item in (sku_ids or []) if item]
        if clean_sku_ids:
            placeholders = ",".join(["%s"] * len(clean_sku_ids))
            scope_parts.append(f"pm.sku_id IN ({placeholders})")
            params.extend(clean_sku_ids)
        if include_pending and (spu_id or clean_sku_ids):
            scope_parts.append("(pm.sku_id IS NULL AND pm.spu_id IS NULL AND pm.media_type='pending')")
        if not scope_parts:
            scope_parts.append("1=1")
        select_parts = [
            f"""
            SELECT pm.id, pm.sku_id, COALESCE(pm.spu_id, s.spu_id) AS spu_id,
                   pm.spu_id AS media_spu_id, pm.media_type, pm.url, pm.storage, pm.file_name,
                   pm.sort_order, pm.is_active, pm.source, pm.created_at, pm.updated_at,
                   sp.title AS spu_title, sp.product_type, sp.series, sp.size_label,
                   COALESCE(sp.default_category_id, s.primary_category_id) AS category_id,
                   pc.name AS category_name, pc.product_type AS category_product_type,
                   s.sku_no, s.color AS sku_color, s.bag_type, COALESCE(s.tea_type, sp.tea_type) AS tea_type,
                   CASE pm.media_type
                     WHEN 'main_image' THEN 0
                     WHEN 'main' THEN 0
                     WHEN 'color_image' THEN 1
                     WHEN 'image' THEN 1
                     WHEN 'detail_image' THEN 2
                     WHEN 'detail' THEN 2
                     WHEN 'pending' THEN 3
                     ELSE 9
                   END AS asset_sort_rank
            FROM product_media pm
            LEFT JOIN product_sku s ON s.id = pm.sku_id AND s.deleted_at IS NULL
            LEFT JOIN product_spu sp ON sp.id = COALESCE(pm.spu_id, s.spu_id) AND sp.deleted_at IS NULL
            LEFT JOIN product_category pc ON pc.id = COALESCE(sp.default_category_id, s.primary_category_id)
            WHERE pm.is_active=1 AND ({' OR '.join(scope_parts)}){type_clause}
            """
        ]
        select_params: list[Any] = params + type_params
        if not normalized_media_type or normalized_media_type == "color_image":
            color_scope_parts: list[str] = ["s.deleted_at IS NULL", "NULLIF(s.main_image_url, '') IS NOT NULL"]
            color_params: list[Any] = []
            if spu_id:
                color_scope_parts.append("s.spu_id=%s")
                color_params.append(int(spu_id))
            if clean_sku_ids:
                placeholders = ",".join(["%s"] * len(clean_sku_ids))
                color_scope_parts.append(f"s.id IN ({placeholders})")
                color_params.extend(clean_sku_ids)
            select_parts.append(
                f"""
                SELECT NULL AS id, s.id AS sku_id, s.spu_id,
                       NULL AS media_spu_id, 'color_image' AS media_type,
                       s.main_image_url AS url, 'oss' AS storage, '' AS file_name,
                       0 AS sort_order, 1 AS is_active, 'sku_image' AS source,
                       s.created_at, s.updated_at,
                       sp.title AS spu_title, sp.product_type, sp.series, sp.size_label,
                       COALESCE(sp.default_category_id, s.primary_category_id) AS category_id,
                       pc.name AS category_name, pc.product_type AS category_product_type,
                       s.sku_no, s.color AS sku_color, s.bag_type, COALESCE(s.tea_type, sp.tea_type) AS tea_type,
                       1 AS asset_sort_rank
                FROM product_sku s
                JOIN product_spu sp ON sp.id = s.spu_id AND sp.deleted_at IS NULL
                LEFT JOIN product_category pc ON pc.id = COALESCE(sp.default_category_id, s.primary_category_id)
                WHERE {' AND '.join(color_scope_parts)}
                  AND NOT EXISTS (
                    SELECT 1
                    FROM product_media pm2
                    WHERE pm2.is_active=1
                      AND pm2.sku_id=s.id
                      AND pm2.url=s.main_image_url
                      AND pm2.media_type IN ('color_image', 'image')
                    LIMIT 1
                  )
                """
            )
            select_params.extend(color_params)
        union_sql = " UNION ALL ".join(select_parts)
        safe_page = max(1, int(page or 1))
        safe_page_size = max(1, min(int(page_size or 80), 200))
        count_rows = self.query(
            f"SELECT COUNT(*) AS total FROM ({union_sql}) media_page_count",
            select_params,
        )
        rows = self.query(
            f"""
            SELECT *
            FROM ({union_sql}) media_page_rows
            ORDER BY asset_sort_rank ASC, sort_order ASC, id DESC
            LIMIT %s OFFSET %s
            """,
            select_params + [safe_page_size, (safe_page - 1) * safe_page_size],
        )
        total = int(count_rows[0].get("total") or 0) if count_rows else 0
        return self._format_product_media_asset_rows(rows), total

    def _format_product_media_asset_rows(self, rows: list[dict]) -> list[dict]:
        type_text = {
            "main": "主图",
            "main_image": "主图",
            "detail": "详情页",
            "detail_image": "详情页",
            "color_image": "颜色图",
            "pending": "待绑定",
            "image": "颜色图",
        }
        result = []
        seen_assets: set[tuple[str, str, str, str]] = set()
        for row in rows:
            normalized_type = _media_type(row.get("media_type"))
            url = str(row.get("url") or "")
            row_spu_id = str(row.get("spu_id") or "")
            if normalized_type == "main_image":
                dedupe_key = (normalized_type, row_spu_id or f"url:{url}", "", "")
            elif normalized_type == "detail_image":
                dedupe_key = (normalized_type, row_spu_id, url, "")
            elif normalized_type == "color_image":
                dedupe_key = (normalized_type, row_spu_id, str(row.get("sku_color") or row.get("sku_id") or ""), url)
            else:
                dedupe_key = (normalized_type, row_spu_id, url, str(row.get("id") or ""))
            if dedupe_key in seen_assets:
                continue
            seen_assets.add(dedupe_key)
            product_name = row.get("spu_title") or ""
            color = row.get("sku_color") or ""
            if not product_name and row.get("spu_id"):
                product_name = f"产品#{row.get('spu_id')}"
            binding_text = "待绑定"
            if product_name:
                binding_text = product_name
                if normalized_type == "color_image" and color:
                    binding_text = f"{product_name} / {color}"
            group_key, group_text, series, size_label, group_order = _asset_group_info(row)
            result.append({
                "id": row.get("id"),
                "sku_id": row.get("sku_id"),
                "spu_id": row.get("spu_id"),
                "media_spu_id": row.get("media_spu_id"),
                "spu_title": row.get("spu_title") or "",
                "product_type": row.get("product_type") or "",
                "category_product_type": row.get("category_product_type") or "",
                "bag_type": row.get("bag_type") or "",
                "tea_type": row.get("tea_type") or "",
                "series": series,
                "size_label": size_label,
                "product_name": product_name,
                "binding_text": binding_text,
                "category_id": row.get("category_id"),
                "category_name": _normalize_asset_category_name(row.get("category_name")),
                "asset_group_key": group_key,
                "asset_group_text": group_text,
                "asset_group_order": group_order,
                "sku_no": row.get("sku_no") or "",
                "sku_color": color,
                "media_type": normalized_type,
                "raw_media_type": row.get("media_type") or "",
                "media_type_text": type_text.get(normalized_type, type_text.get(str(row.get("media_type") or ""), str(row.get("media_type") or ""))),
                "url": url,
                "storage": row.get("storage") or "",
                "source": row.get("source") or "",
                "source_text": _source_text(row.get("source")),
                "sort_order": int(row.get("sort_order") or 0),
                "created_at": str(row.get("created_at") or ""),
                "updated_at": str(row.get("updated_at") or ""),
            })
        return result

    def delete_product_media(self, media_id: int) -> dict:
        rows = self.query(
            """
            SELECT pm.id, pm.media_type, pm.url, COALESCE(pm.spu_id, s.spu_id) AS spu_id
            FROM product_media pm
            LEFT JOIN product_sku s ON s.id = pm.sku_id AND s.deleted_at IS NULL
            WHERE pm.id=%s
            LIMIT 1
            """,
            (int(media_id),),
        )
        if not rows:
            return {"code": 0, "data": {"id": int(media_id), "affected": 0}}
        row = rows[0]
        normalized_type = _media_type(row.get("media_type"))
        raw_types = {
            "main_image": ["main_image", "main"],
            "detail_image": ["detail_image", "detail"],
        }.get(normalized_type)
        if raw_types and row.get("spu_id") and row.get("url"):
            placeholders = ",".join(["%s"] * len(raw_types))
            affected = self.execute(
                f"""
                UPDATE product_media pm
                LEFT JOIN product_sku s ON s.id = pm.sku_id AND s.deleted_at IS NULL
                SET pm.is_active=0, pm.updated_at=%s
                WHERE pm.is_active=1
                  AND pm.url=%s
                  AND pm.media_type IN ({placeholders})
                  AND COALESCE(pm.spu_id, s.spu_id)=%s
                """,
                [_now(), row.get("url")] + raw_types + [int(row.get("spu_id"))],
            )
        else:
            affected = self.execute(
                "UPDATE product_media SET is_active=0, updated_at=%s WHERE id=%s",
                (_now(), int(media_id)),
            )
        return {"code": 0, "data": {"id": int(media_id), "affected": affected}}

    def delete_pending_product_media(self, media_ids: Iterable[Any]) -> dict:
        ids: list[int] = []
        for raw in media_ids or []:
            text = str(raw or "").strip()
            if not text.isdigit():
                continue
            media_id = int(text)
            if media_id > 0 and media_id not in ids:
                ids.append(media_id)
        if not ids:
            return {"code": 400, "msg": "缺少未绑定图片ID"}
        placeholders = ",".join(["%s"] * len(ids))
        affected = self.execute(
            f"""
            UPDATE product_media
            SET is_active=0, updated_at=%s
            WHERE is_active=1
              AND media_type='pending'
              AND sku_id IS NULL
              AND spu_id IS NULL
              AND id IN ({placeholders})
            """,
            [_now()] + ids,
        )
        return {"code": 0, "data": {"ids": ids, "affected": affected}}

    def save_product(self, payload: dict) -> dict:
        title = str(payload.get("title") or payload.get("name") or "").strip()
        if not title:
            return {"code": 400, "msg": "商品名称不能为空"}
        product_type = str(payload.get("product_type") or "gift_box").strip() or "gift_box"
        default_bag_type = str(payload.get("bag_type") or "").strip()
        category_ids = payload.get("product_category_id") or payload.get("categoryIds") or []
        if isinstance(category_ids, str):
            category_ids = [item for item in category_ids.split(",") if item.strip()]
        category_ids = [int(item) for item in category_ids if str(item).strip().isdigit()]
        primary_category_id = category_ids[0] if category_ids else None
        status_map = {0: "active", 1: "inactive", 2: "stopped", 3: "stopped"}
        status = status_map.get(int(payload.get("status", 0) or 0), "active")
        main_images = payload.get("main_images") or []
        if isinstance(main_images, str):
            main_images = _json_loads(main_images, [main_images]) if main_images.startswith("[") else [main_images]
        main_image = str(main_images[0]).strip() if main_images else ""
        content_html = payload.get("content") or payload.get("content_html") or ""
        detail_images = _html_image_urls(content_html)
        case_pack_qty = self._parse_case_pack_qty(payload.get("simple_desc") or "")
        purchase_policy = _normalize_purchase_policy(payload.get("purchase_policy") or payload.get("is_one_case_purchase"))
        base = payload.get("base") or {}
        if not isinstance(base, dict):
            return {"code": 400, "msg": "规格数据格式不正确"}

        self._ensure_number_sequence_tables()
        product_id = payload.get("id") or payload.get("product_id")
        with self.transaction() as cursor:
            now = _now()
            spu_id = None
            if product_id:
                sku_id = self.resolve_sku_id(int(product_id), cursor=cursor)
                if sku_id:
                    cursor.execute("SELECT spu_id FROM product_sku WHERE id=%s LIMIT 1", (sku_id,))
                    row = cursor.fetchone() or {}
                    spu_id = row.get("spu_id")
            if not spu_id:
                cursor.execute(
                    """
                    INSERT INTO product_spu
                        (title, product_type, default_category_id, case_pack_qty, purchase_policy, source, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, 'native_api', %s, %s)
                    """,
                    (title, product_type, primary_category_id, case_pack_qty, purchase_policy, now, now),
                )
                spu_id = cursor.lastrowid
            else:
                cursor.execute(
                    """
                    UPDATE product_spu
                    SET title=%s, product_type=%s, default_category_id=%s, case_pack_qty=COALESCE(%s, case_pack_qty),
                        purchase_policy=%s, updated_at=%s
                    WHERE id=%s
                    """,
                    (title, product_type, primary_category_id, case_pack_qty, purchase_policy, now, spu_id),
                )

            saved_ids: list[int] = []
            colors: list[str] = []
            specs = list(base.items()) or [("new_0", {"spec": payload.get("spec") or payload.get("color") or ""})]
            for product_key, spec_payload in specs:
                if not isinstance(spec_payload, dict):
                    continue
                existing_id = int(product_key) if str(product_key).isdigit() else None
                if existing_id:
                    existing_id = self.resolve_sku_id(existing_id, cursor=cursor)
                unit_payload = next(iter((spec_payload.get("unit") or {}).values()), {}) if isinstance(spec_payload.get("unit"), dict) else {}
                color = str(spec_payload.get("spec") or spec_payload.get("color") or "").strip()
                if color and color not in colors:
                    colors.append(color)
                bag_type = str(spec_payload.get("bag_type") or default_bag_type or "").strip()
                unit_id = int(unit_payload.get("unit_id") or spec_payload.get("unit_id") or 1)
                requested_sku_no = str(spec_payload.get("coding") or unit_payload.get("coding") or "").strip()
                if requested_sku_no and requested_sku_no.startswith("SJ") and self._sku_no_available(cursor, requested_sku_no, existing_id):
                    sku_no = requested_sku_no
                elif existing_id:
                    cursor.execute("SELECT sku_no FROM product_sku WHERE id=%s", (existing_id,))
                    sku_no = (cursor.fetchone() or {}).get("sku_no") or self._next_sku_no(
                        cursor,
                        start_number=1001,
                        compact_from_start=True,
                    )
                else:
                    sku_no = self._next_sku_no(
                        cursor,
                        start_number=1001,
                        compact_from_start=True,
                    )
                price = unit_payload.get("price") or spec_payload.get("price") or 0
                cost_price = unit_payload.get("cost_price") or spec_payload.get("cost_price") or 0
                image = str(spec_payload.get("images") or "").strip()
                spec_purchase_policy = _normalize_purchase_policy(spec_payload.get("purchase_policy") or purchase_policy)
                default_is_stock_item = self._default_is_stock_item_for_product(cursor, category_ids, product_type)
                if default_is_stock_item == 0:
                    is_stock_item = 0
                elif "is_stock_item" in spec_payload:
                    is_stock_item = 0 if str(spec_payload.get("is_stock_item", 1)).lower() in ("0", "false", "no", "off") else 1
                else:
                    is_stock_item = default_is_stock_item
                if existing_id:
                    cursor.execute(
                        """
                        UPDATE product_sku
                        SET sku_no=%s, primary_category_id=%s, category_ids=%s, color=%s,
                            bag_type=%s, unit_id=%s, retail_price=%s, min_price=%s, max_price=%s, cost_price=%s,
                            status=%s, is_stock_item=%s, purchase_policy=%s, main_image_url=%s, detail_image_urls=%s, content_html=%s, search_text=%s,
                            source='native_api', updated_at=%s
                        WHERE id=%s
                        """,
                        (
                            sku_no,
                            primary_category_id,
                            _json_dumps(category_ids),
                            color,
                            bag_type,
                            unit_id,
                            price,
                            price,
                            price,
                            cost_price,
                            status,
                            is_stock_item,
                            spec_purchase_policy,
                            image,
                            _json_dumps(detail_images),
                            content_html,
                            f"{title} {color} {sku_no}",
                            now,
                            existing_id,
                        ),
                    )
                    sku_id = existing_id
                else:
                    cursor.execute(
                        """
                        INSERT INTO product_sku
                            (spu_id, sku_no, primary_category_id, category_ids, color, bag_type, unit_id,
                             retail_price, min_price, max_price, cost_price, status, is_stock_item, purchase_policy, main_image_url,
                             detail_image_urls, content_html, search_text, source, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'native_api', %s, %s)
                        """,
                        (
                            spu_id,
                            sku_no,
                            primary_category_id,
                            _json_dumps(category_ids),
                            color,
                            bag_type,
                            unit_id,
                            price,
                            price,
                            price,
                            cost_price,
                            status,
                            is_stock_item,
                            spec_purchase_policy,
                            image,
                            _json_dumps(detail_images),
                            content_html,
                            f"{title} {color} {sku_no}",
                            now,
                            now,
                        ),
                    )
                    sku_id = cursor.lastrowid
                saved_ids.append(int(sku_id))
                self._replace_product_media(
                    cursor,
                    sku_id=int(sku_id),
                    spu_id=int(spu_id),
                    media_type="color_image",
                    urls=[image] if image else [],
                )
            self._replace_product_media(
                cursor,
                sku_id=None,
                spu_id=int(spu_id),
                media_type="main_image",
                urls=[main_image] if main_image else [],
            )
            self._replace_product_media(
                cursor,
                sku_id=None,
                spu_id=int(spu_id),
                media_type="detail_image",
                urls=detail_images,
            )
            cursor.execute(
                "UPDATE product_spu SET available_colors=%s, updated_at=%s WHERE id=%s",
                (_json_dumps(colors), now, spu_id),
            )
        return {"code": 0, "data": {"id": saved_ids[0] if saved_ids else product_id, "sku_ids": saved_ids, "spu_id": spu_id}}

    def update_purchase_policy_by_series(self, series: list[str] | str, purchase_policy: str) -> dict:
        names = [str(item or "").strip() for item in (series if isinstance(series, list) else [series])]
        names = [item for item in names if item]
        if not names:
            return {"spu": 0, "sku": 0}
        policy = _normalize_purchase_policy(purchase_policy)
        now = _now()
        spu_total = 0
        sku_total = 0
        with self.transaction() as cursor:
            for name in names:
                like = f"%{name}%"
                params = [policy, now, like, name, like]
                cursor.execute(
                    """
                    UPDATE product_spu
                    SET purchase_policy=%s, updated_at=%s
                    WHERE deleted_at IS NULL
                      AND (title LIKE %s OR series=%s OR REPLACE(REPLACE(title, '【', ''), '】', '') LIKE %s)
                    """,
                    params,
                )
                spu_total += int(cursor.rowcount or 0)
                cursor.execute(
                    """
                    UPDATE product_sku s
                    JOIN product_spu sp ON sp.id=s.spu_id
                    SET s.purchase_policy=%s, s.updated_at=%s
                    WHERE s.deleted_at IS NULL
                      AND sp.deleted_at IS NULL
                      AND (sp.title LIKE %s OR sp.series=%s OR REPLACE(REPLACE(sp.title, '【', ''), '】', '') LIKE %s)
                    """,
                    params,
                )
                sku_total += int(cursor.rowcount or 0)
        return {"spu": spu_total, "sku": sku_total}

    def _delete_product_sku_legacy(self, ids: str | list[int]) -> dict:
        if isinstance(ids, str):
            raw_ids = [item.strip() for item in ids.split(",") if item.strip()]
        else:
            raw_ids = [str(item) for item in ids]
        sku_ids = [self.resolve_sku_id(int(item)) for item in raw_ids if str(item).isdigit()]
        sku_ids = [int(item) for item in sku_ids if item]
        if not sku_ids:
            return {"code": 400, "msg": "没有可删除的商品"}
        placeholders = ",".join(["%s"] * len(sku_ids))
        self.execute(
            f"UPDATE product_sku SET status='deleted', deleted_at=%s, updated_at=%s WHERE id IN ({placeholders})",
            [_now(), _now()] + sku_ids,
        )
        return {"code": 0, "data": {"ids": sku_ids}}

    def _update_product_shelves_sku_legacy(self, product_id: int, state: int) -> dict:
        sku_id = self.resolve_sku_id(product_id)
        if not sku_id:
            return {"code": 404, "msg": "商品不存在"}
        self.execute("UPDATE product_sku SET is_listed=%s, updated_at=%s WHERE id=%s", (1 if state else 0, _now(), sku_id))
        return {"code": 0, "data": {"id": sku_id, "is_listed": 1 if state else 0}}

    def _product_spu_ids_from_inputs(self, ids: str | list[int] | list[str], cursor) -> tuple[list[int], list[int]]:
        if isinstance(ids, str):
            raw_ids = [item.strip() for item in ids.split(",") if item.strip()]
        else:
            raw_ids = [str(item) for item in ids]
        spu_ids: list[int] = []
        sku_ids: list[int] = []
        for item in raw_ids:
            if not item.isdigit():
                continue
            product_id = int(item)
            cursor.execute(
                "SELECT id, spu_id FROM product_sku WHERE id=%s AND deleted_at IS NULL LIMIT 1",
                (product_id,),
            )
            sku = cursor.fetchone()
            if not sku:
                sku_id = self.resolve_sku_id(product_id, cursor=cursor)
                if sku_id:
                    cursor.execute(
                        "SELECT id, spu_id FROM product_sku WHERE id=%s AND deleted_at IS NULL LIMIT 1",
                        (sku_id,),
                    )
                    sku = cursor.fetchone()
            if sku:
                sku_id = int(sku["id"])
                spu_id = int(sku.get("spu_id") or 0)
                if sku_id not in sku_ids:
                    sku_ids.append(sku_id)
                if spu_id and spu_id not in spu_ids:
                    spu_ids.append(spu_id)
                continue
            cursor.execute("SELECT id FROM product_spu WHERE id=%s AND deleted_at IS NULL LIMIT 1", (product_id,))
            spu = cursor.fetchone()
            if spu and int(spu["id"]) not in spu_ids:
                spu_ids.append(int(spu["id"]))
        return spu_ids, sku_ids

    def delete_product(self, ids: str | list[int]) -> dict:
        now = _now()
        with self.transaction() as cursor:
            spu_ids, seed_sku_ids = self._product_spu_ids_from_inputs(ids, cursor)
            if not spu_ids:
                return {"code": 400, "msg": "没有可删除的商品"}
            placeholders = ",".join(["%s"] * len(spu_ids))
            cursor.execute(
                f"SELECT id FROM product_sku WHERE spu_id IN ({placeholders}) AND deleted_at IS NULL",
                spu_ids,
            )
            all_sku_ids = [int(row["id"]) for row in cursor.fetchall()]
            cursor.execute(
                f"""
                UPDATE product_sku
                SET status='deleted', deleted_at=%s, updated_at=%s
                WHERE spu_id IN ({placeholders}) AND deleted_at IS NULL
                """,
                [now, now] + spu_ids,
            )
            sku_affected = int(cursor.rowcount or 0)
            cursor.execute(
                f"""
                UPDATE product_spu
                SET deleted_at=%s, updated_at=%s
                WHERE id IN ({placeholders}) AND deleted_at IS NULL
                """,
                [now, now] + spu_ids,
            )
            spu_affected = int(cursor.rowcount or 0)
        if not all_sku_ids:
            all_sku_ids = seed_sku_ids
        return {
            "code": 0,
            "data": {
                "ids": all_sku_ids,
                "sku_ids": all_sku_ids,
                "spu_ids": spu_ids,
                "affected": sku_affected,
                "spu_affected": spu_affected,
            },
        }

    def update_product_shelves(
        self,
        product_id: int,
        state: int,
        *,
        spu_id: Any | None = None,
        sku_ids: Iterable[Any] | None = None,
    ) -> dict:
        now = _now()
        target_state = 1 if state else 0
        with self.transaction() as cursor:
            spu_ids: list[int] = []
            seed_sku_ids: list[int] = []

            def add_spu_id(value: Any) -> None:
                try:
                    clean_id = int(value or 0)
                except (TypeError, ValueError):
                    return
                if clean_id <= 0:
                    return
                cursor.execute("SELECT id FROM product_spu WHERE id=%s AND deleted_at IS NULL LIMIT 1", (clean_id,))
                row = cursor.fetchone()
                if row and int(row["id"]) not in spu_ids:
                    spu_ids.append(int(row["id"]))

            add_spu_id(spu_id)
            explicit_sku_ids = [item for item in (sku_ids or []) if str(item or "").strip()]
            if explicit_sku_ids:
                explicit_spu_ids, explicit_seed_sku_ids = self._product_spu_ids_from_inputs(explicit_sku_ids, cursor)
                for explicit_spu_id in explicit_spu_ids:
                    if explicit_spu_id not in spu_ids:
                        spu_ids.append(explicit_spu_id)
                seed_sku_ids.extend([item for item in explicit_seed_sku_ids if item not in seed_sku_ids])
            if not spu_ids:
                spu_ids, seed_sku_ids = self._product_spu_ids_from_inputs([product_id], cursor)
            if not spu_ids:
                return {"code": 404, "msg": "商品不存在"}
            placeholders = ",".join(["%s"] * len(spu_ids))
            cursor.execute(
                f"SELECT id FROM product_sku WHERE spu_id IN ({placeholders}) AND deleted_at IS NULL ORDER BY spu_id ASC, id ASC",
                spu_ids,
            )
            sku_ids = [int(row["id"]) for row in cursor.fetchall()] or seed_sku_ids
            if target_state:
                cursor.execute(
                    f"UPDATE product_sku SET is_listed=%s, status='active', updated_at=%s WHERE spu_id IN ({placeholders}) AND deleted_at IS NULL",
                    [target_state, now] + spu_ids,
                )
            else:
                cursor.execute(
                    f"UPDATE product_sku SET is_listed=%s, updated_at=%s WHERE spu_id IN ({placeholders}) AND deleted_at IS NULL",
                    [target_state, now] + spu_ids,
                )
            affected = int(cursor.rowcount or 0)
            cursor.execute(
                f"UPDATE product_spu SET updated_at=%s WHERE id IN ({placeholders}) AND deleted_at IS NULL",
                [now] + spu_ids,
            )
            matching_sql = "is_listed=%s AND status='active'" if target_state else "is_listed=%s"
            cursor.execute(
                f"""
                SELECT COUNT(*) AS total,
                       SUM(CASE WHEN {matching_sql} THEN 1 ELSE 0 END) AS matching
                FROM product_sku
                WHERE spu_id IN ({placeholders}) AND deleted_at IS NULL
                """,
                [target_state] + spu_ids,
            )
            verify_row = cursor.fetchone() or {}
            total_sku_count = int(verify_row.get("total") or 0)
            matching_sku_count = int(verify_row.get("matching") or 0)
        return {
            "code": 0,
            "data": {
                "id": sku_ids[0] if sku_ids else product_id,
                "spu_id": spu_ids[0],
                "spu_ids": spu_ids,
                "sku_ids": sku_ids,
                "is_listed": target_state,
                "affected": affected,
                "total_sku_count": total_sku_count,
                "matching_sku_count": matching_sku_count,
                "all_sku_matched": matching_sku_count == total_sku_count,
            },
        }

    # ---- customers, users, warehouses ----

    def _customer_list_where(self, keyword: str = "", filter_value: str = "all") -> tuple[list[str], list[Any]]:
        self._ensure_party_columns()
        self._ensure_sales_delete_columns()
        where = ["p.kind='customer'", "p.deleted_at IS NULL"]
        params: list[Any] = []
        if keyword:
            like = f"%{keyword}%"
            digits = f"%{_phone_digits(keyword)}%" if _phone_digits(keyword) else like
            where.append("(name LIKE %s OR contact_name LIKE %s OR phone LIKE %s OR phone_normalized LIKE %s)")
            params.extend([like, like, like, digits])
        clean_filter = str(filter_value or "all").strip()
        balance_sql = "(COALESCE(wallet.wallet_amount, 0) - COALESCE(debt.debt_amount, 0))"
        if clean_filter == "monthly":
            where.append("COALESCE(p.is_monthly_customer, 0)=1")
        elif clean_filter == "normal":
            where.append("COALESCE(p.is_monthly_customer, 0)=0")
        elif clean_filter == "debt":
            where.append(f"{balance_sql} < 0")
        elif clean_filter == "credit":
            where.append(f"{balance_sql} > 0")
        elif clean_filter == "no_phone":
            where.append("(p.phone IS NULL OR p.phone='' OR p.phone_normalized IS NULL OR p.phone_normalized='')")
        elif clean_filter == "normal_debt":
            where.append("COALESCE(p.is_monthly_customer, 0)=0")
            where.append(f"{balance_sql} < 0")
        return where, params

    def _customer_balance_join_sql(self) -> str:
        return """
            LEFT JOIN (
                SELECT customer_id, SUM(balance_delta) AS wallet_amount
                FROM customer_balance_ledger
                GROUP BY customer_id
            ) wallet ON wallet.customer_id = p.id
            LEFT JOIN (
                SELECT customer_id, SUM(receivable_amount) AS debt_amount
                FROM sales_order
                WHERE status NOT IN ('canceled', 'deleted')
                  AND pay_status IN ('unpaid', 'monthly', 'partial')
                GROUP BY customer_id
            ) debt ON debt.customer_id = p.id
        """

    def _customer_row_payload(self, row: dict) -> dict:
        return {
            "id": row.get("id"),
            "customer_id": row.get("id"),
            "name": row.get("name") or f"客户#{row.get('id')}",
            "customer_name": row.get("name") or f"客户#{row.get('id')}",
            "company_name": row.get("name") or "",
            "contacts_name": row.get("contact_name") or "",
            "contacts_mobile": row.get("phone") or "",
            "contacts_tel": row.get("phone") or "",
            "phone": row.get("phone") or "",
            "mobile": row.get("phone") or "",
            "address": row.get("address") or "",
            "status": row.get("status") or "active",
            "is_monthly_customer": int(row.get("is_monthly_customer") or 0),
            "latest_order_at": str(row.get("latest_order_at") or ""),
            "latest_order_amount": _money(row.get("latest_order_amount")),
            "year_amount": _money(row.get("year_amount")),
            "year_order_count": int(row.get("year_order_count") or 0),
            "month1_amount": _money(row.get("month1_amount")),
            "month3_amount": _money(row.get("month3_amount")),
            "wallet_amount": _money(row.get("wallet_amount")),
            "debt_amount": _money(row.get("debt_amount")),
            "balance_amount": _money(row.get("balance_amount")),
            "sales_count": int(row.get("sales_count") or 0),
            "source": "native",
        }

    def customer_list_page(
        self,
        keyword: str = "",
        page: int = 1,
        page_size: int = 20,
        filter_value: str = "all",
    ) -> tuple[list[dict], int, dict]:
        page = max(1, int(page or 1))
        page_size = max(1, min(int(page_size or 20), 300))
        where, params = self._customer_list_where(keyword, filter_value)
        where_sql = " AND ".join(where)
        balance_sql = "(COALESCE(wallet.wallet_amount, 0) - COALESCE(debt.debt_amount, 0))"
        balance_joins = self._customer_balance_join_sql()

        total_rows = self.query(
            f"""
            SELECT
                COUNT(*) AS total,
                COALESCE(SUM(CASE WHEN COALESCE(p.is_monthly_customer, 0)=1 THEN 1 ELSE 0 END), 0) AS monthly,
                COALESCE(SUM(CASE WHEN {balance_sql} < 0 THEN 1 ELSE 0 END), 0) AS debt,
                COALESCE(SUM(CASE WHEN COALESCE(p.is_monthly_customer, 0)=0 AND {balance_sql} < 0 THEN 1 ELSE 0 END), 0) AS normal_debt,
                COALESCE(SUM(CASE WHEN COALESCE(p.is_monthly_customer, 0)=1 AND {balance_sql} < 0 THEN 1 ELSE 0 END), 0) AS monthly_debt,
                COALESCE(SUM(CASE WHEN p.phone IS NULL OR p.phone='' OR p.phone_normalized IS NULL OR p.phone_normalized='' THEN 1 ELSE 0 END), 0) AS no_phone,
                COALESCE(SUM(CASE WHEN {balance_sql} > 0 THEN 1 ELSE 0 END), 0) AS credit,
                COALESCE(SUM(GREATEST({balance_sql}, 0)), 0) AS credit_amount,
                COALESCE(SUM(GREATEST(-{balance_sql}, 0)), 0) AS debt_amount
            FROM party p
            {balance_joins}
            WHERE {where_sql}
            """,
            params,
        )
        rows = self.query(
            f"""
            SELECT
                p.id, p.name, p.contact_name, p.phone, p.phone_normalized, p.address,
                p.wechat_name, p.status, p.is_monthly_customer, p.created_at, p.updated_at,
                latest.sales_at AS latest_order_at,
                latest.receivable_amount AS latest_order_amount,
                COALESCE(yearly.year_amount, 0) AS year_amount,
                COALESCE(yearly.year_order_count, 0) AS year_order_count,
                COALESCE(month1.month_amount, 0) AS month1_amount,
                COALESCE(month3.month3_amount, 0) AS month3_amount,
                COALESCE(wallet.wallet_amount, 0) AS wallet_amount,
                COALESCE(debt.debt_amount, 0) AS debt_amount,
                COALESCE(wallet.wallet_amount, 0) - COALESCE(debt.debt_amount, 0) AS balance_amount,
                COALESCE(total.sales_count, 0) AS sales_count
            FROM party p
            LEFT JOIN sales_order latest
              ON latest.id = (
                SELECT so.id
                FROM sales_order so
                WHERE so.customer_id = p.id AND so.status NOT IN ('canceled', 'deleted')
                ORDER BY so.sales_at DESC, so.id DESC
                LIMIT 1
              )
            LEFT JOIN (
                SELECT customer_id, SUM(receivable_amount) AS year_amount, COUNT(*) AS year_order_count
                FROM sales_order
                WHERE status NOT IN ('canceled', 'deleted') AND sales_at >= DATE_SUB(NOW(), INTERVAL 1 YEAR)
                GROUP BY customer_id
            ) yearly ON yearly.customer_id = p.id
            LEFT JOIN (
                SELECT customer_id, SUM(receivable_amount) AS month_amount
                FROM sales_order
                WHERE status NOT IN ('canceled', 'deleted') AND sales_at >= DATE_SUB(NOW(), INTERVAL 1 MONTH)
                GROUP BY customer_id
            ) month1 ON month1.customer_id = p.id
            LEFT JOIN (
                SELECT customer_id, SUM(receivable_amount) AS month3_amount
                FROM sales_order
                WHERE status NOT IN ('canceled', 'deleted') AND sales_at >= DATE_SUB(NOW(), INTERVAL 3 MONTH)
                GROUP BY customer_id
            ) month3 ON month3.customer_id = p.id
            {balance_joins}
            LEFT JOIN (
                SELECT customer_id, COUNT(*) AS sales_count
                FROM sales_order
                WHERE status NOT IN ('canceled', 'deleted')
                GROUP BY customer_id
            ) total ON total.customer_id = p.id
            WHERE {where_sql}
            ORDER BY latest.sales_at DESC, p.updated_at DESC, p.id DESC
            LIMIT %s OFFSET %s
            """,
            params + [page_size, (page - 1) * page_size],
        )
        total_row = total_rows[0] if total_rows else {}
        summary = {
            "total": int(total_row.get("total") or 0),
            "monthly": int(total_row.get("monthly") or 0),
            "debt": int(total_row.get("debt") or 0),
            "normal_debt": int(total_row.get("normal_debt") or 0),
            "monthly_debt": int(total_row.get("monthly_debt") or 0),
            "no_phone": int(total_row.get("no_phone") or 0),
            "credit": int(total_row.get("credit") or 0),
            "credit_amount": _money(total_row.get("credit_amount")),
            "debt_amount": _money(total_row.get("debt_amount")),
        }
        return [self._customer_row_payload(row) for row in rows], int(total_row.get("total") or 0), summary

    def customer_list(self, keyword: str = "", limit: int = 100) -> list[dict]:
        rows, _, _ = self.customer_list_page(
            keyword,
            page=1,
            page_size=max(1, min(int(limit or 100), 300)),
            filter_value="all",
        )
        return rows

    def _sales_period_where(self, period: str = "", month: str = "") -> tuple[list[str], list[Any], dict]:
        where: list[str] = []
        params: list[Any] = []
        summary: dict[str, str] = {}
        clean_month = str(month or "").strip()
        if re.match(r"^\d{4}-\d{2}$", clean_month):
            start = datetime.strptime(f"{clean_month}-01", "%Y-%m-%d")
            if start.month == 12:
                end = start.replace(year=start.year + 1, month=1)
            else:
                end = start.replace(month=start.month + 1)
            where.append("sales_at >= %s AND sales_at < %s")
            params.extend([start.strftime("%Y-%m-%d 00:00:00"), end.strftime("%Y-%m-%d 00:00:00")])
            summary = {"period": "month", "label": f"{clean_month} 月"}
            return where, params, summary
        clean_period = str(period or "").strip()
        months = 3 if clean_period in ("3m", "3month", "three_months") else 1 if clean_period in ("1m", "month", "recent_month") else 0
        if months:
            start = datetime.now() - timedelta(days=30 * months)
            where.append("sales_at >= %s")
            params.append(start.strftime("%Y-%m-%d 00:00:00"))
            summary = {"period": f"{months}m", "label": f"最近{months}个月"}
        return where, params, summary

    def _statement_range(
        self,
        *,
        month: str = "",
        date_from: str = "",
        date_to: str = "",
    ) -> tuple[datetime, datetime, str, str]:
        clean_month = str(month or "").strip()
        if clean_month:
            start, end = self._month_range(clean_month)
            return start, end, start.strftime("%Y-%m-%d"), (end - timedelta(days=1)).strftime("%Y-%m-%d")
        clean_from = str(date_from or "").strip()
        clean_to = str(date_to or "").strip()
        if not clean_from or not clean_to:
            now = datetime.now()
            clean_month = now.strftime("%Y-%m")
            start, end = self._month_range(clean_month)
            return start, end, start.strftime("%Y-%m-%d"), (end - timedelta(days=1)).strftime("%Y-%m-%d")
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", clean_from) or not re.match(r"^\d{4}-\d{2}-\d{2}$", clean_to):
            raise DBError("日期格式不正确")
        start = datetime.strptime(clean_from, "%Y-%m-%d")
        end_day = datetime.strptime(clean_to, "%Y-%m-%d")
        if start > end_day:
            raise DBError("开始日期不能晚于结束日期")
        if (end_day - start).days > 366:
            raise DBError("对账单时间范围不能超过366天")
        end = end_day + timedelta(days=1)
        return start, end, clean_from, clean_to

    def customer_statement(
        self,
        customer_id: int,
        *,
        month: str = "",
        date_from: str = "",
        date_to: str = "",
    ) -> dict:
        start, end, start_text, end_text = self._statement_range(
            month=month,
            date_from=date_from,
            date_to=date_to,
        )
        start_sql = start.strftime("%Y-%m-%d 00:00:00")
        end_sql = end.strftime("%Y-%m-%d 00:00:00")
        customer_rows = self.query(
            """
            SELECT id, name, contact_name, phone, address, is_monthly_customer
            FROM party
            WHERE id=%s AND kind='customer' AND deleted_at IS NULL
            LIMIT 1
            """,
            (int(customer_id),),
        )
        if not customer_rows:
            raise DBError("客户不存在")
        customer = customer_rows[0]
        opening_rows = self.query(
            """
            SELECT
              COALESCE((SELECT SUM(balance_delta) FROM customer_balance_ledger WHERE customer_id=%s AND created_at < %s), 0) AS wallet_amount,
              COALESCE((
                SELECT SUM(receivable_amount)
                FROM sales_order
                WHERE customer_id=%s
                  AND status NOT IN ('canceled', 'deleted')
                  AND pay_status IN ('unpaid', 'monthly', 'partial')
                  AND sales_at < %s
              ), 0) AS debt_amount
            """,
            (int(customer_id), start_sql, int(customer_id), start_sql),
        )
        sales_rows = self.query(
            """
            SELECT s.id, s.sales_no, s.status, s.pay_type, s.pay_status, s.total_quantity,
                   s.goods_amount, s.receivable_amount, s.sales_at, s.note,
                   wu.display_name AS created_by_name, wu.username AS created_by_username
            FROM sales_order s
            LEFT JOIN auth_user wu ON wu.id=s.created_by_user_id
            WHERE s.customer_id=%s
              AND s.status NOT IN ('canceled', 'deleted')
              AND s.sales_at >= %s AND s.sales_at < %s
            ORDER BY s.sales_at ASC, s.id ASC
            """,
            (int(customer_id), start_sql, end_sql),
        )
        sales_ids = [int(row.get("id") or 0) for row in sales_rows if row.get("id")]
        items_by_sales: dict[int, list[dict]] = {sid: [] for sid in sales_ids}
        if sales_ids:
            placeholders = ",".join(["%s"] * len(sales_ids))
            item_rows = self.query(
                f"""
                SELECT i.sales_order_id, i.line_no, i.sku_no_snapshot, i.title_snapshot,
                       i.color_snapshot, i.quantity, i.unit_price, i.amount,
                       w.name AS warehouse_name
                FROM sales_order_item i
                LEFT JOIN warehouse w ON w.id=i.warehouse_id
                WHERE i.sales_order_id IN ({placeholders})
                ORDER BY i.sales_order_id ASC, i.line_no ASC
                """,
                sales_ids,
            )
            for item in item_rows:
                sid = int(item.get("sales_order_id") or 0)
                items_by_sales.setdefault(sid, []).append({
                    "line_no": int(item.get("line_no") or 0),
                    "sku_no": item.get("sku_no_snapshot") or "",
                    "title": item.get("title_snapshot") or "商品",
                    "color": item.get("color_snapshot") or "默认颜色",
                    "quantity": _qty_text(item.get("quantity")),
                    "unit_price": _money(item.get("unit_price")),
                    "amount": _money(item.get("amount")),
                    "warehouse_name": item.get("warehouse_name") or "",
                })
        ledger_rows = self.query(
            """
            SELECT l.id, l.ledger_no, l.entry_type, l.pay_type, l.amount, l.applied_amount,
                   l.balance_delta, l.related_month, l.note, l.created_at,
                   wu.display_name AS created_by_name, wu.username AS created_by_username
            FROM customer_balance_ledger l
            LEFT JOIN auth_user wu ON wu.id=l.created_by_user_id
            WHERE l.customer_id=%s AND l.created_at >= %s AND l.created_at < %s
            ORDER BY l.created_at ASC, l.id ASC
            """,
            (int(customer_id), start_sql, end_sql),
        )
        sales_amount = sum(_num(row.get("receivable_amount")) for row in sales_rows)
        sales_quantity = sum(_num(row.get("total_quantity")) for row in sales_rows)
        unpaid_amount = sum(
            _num(row.get("receivable_amount"))
            for row in sales_rows
            if str(row.get("pay_status") or "") in {"unpaid", "monthly", "partial"}
        )
        receipt_amount = sum(
            _num(row.get("amount"))
            for row in ledger_rows
            if str(row.get("entry_type") or "") in {"receipt", "recharge"}
        )
        settlement_amount = sum(
            _num(row.get("amount"))
            for row in ledger_rows
            if str(row.get("entry_type") or "") == "settlement"
        )
        adjust_amount = sum(
            _num(row.get("balance_delta"))
            for row in ledger_rows
            if str(row.get("entry_type") or "") == "adjustment"
        )
        ledger_delta = sum(_num(row.get("balance_delta")) for row in ledger_rows)
        opening_row = opening_rows[0] if opening_rows else {}
        opening_balance = _num(opening_row.get("wallet_amount")) - _num(opening_row.get("debt_amount"))
        ending_balance = opening_balance + ledger_delta - unpaid_amount
        sales_result = []
        for row in sales_rows:
            sid = int(row.get("id") or 0)
            sales_result.append({
                "id": sid,
                "sales_no": row.get("sales_no") or str(sid),
                "sales_at": str(row.get("sales_at") or ""),
                "status": row.get("status") or "",
                "status_text": self._sales_status_text(row.get("status") or ""),
                "pay_status": row.get("pay_status") or "",
                "pay_status_text": _pay_status_text(row.get("pay_status")),
                "pay_type": row.get("pay_type") or "",
                "pay_type_text": _pay_type_text(row.get("pay_type")),
                "total_quantity": _qty_text(row.get("total_quantity")),
                "goods_amount": _money(row.get("goods_amount")),
                "receivable_amount": _money(row.get("receivable_amount")),
                "created_by_name": row.get("created_by_name") or row.get("created_by_username") or "",
                "note": row.get("note") or "",
                "items": items_by_sales.get(sid, []),
            })
        ledger_result = [
            {
                "id": int(row.get("id") or 0),
                "ledger_no": row.get("ledger_no") or "",
                "entry_type": row.get("entry_type") or "",
                "entry_type_text": _balance_entry_type_text(row.get("entry_type")),
                "pay_type": row.get("pay_type") or "",
                "pay_type_text": _pay_type_text(row.get("pay_type")),
                "amount": _money(row.get("amount")),
                "applied_amount": _money(row.get("applied_amount")),
                "balance_delta": _money(row.get("balance_delta")),
                "related_month": row.get("related_month") or "",
                "note": row.get("note") or "",
                "created_by_name": row.get("created_by_name") or row.get("created_by_username") or "",
                "created_at": str(row.get("created_at") or ""),
            }
            for row in ledger_rows
        ]
        period_label = str(month or "").strip() or f"{start_text} 至 {end_text}"
        return {
            "customer": {
                "id": int(customer.get("id") or customer_id),
                "name": customer.get("name") or "",
                "contact_name": customer.get("contact_name") or "",
                "phone": customer.get("phone") or "",
                "address": customer.get("address") or "",
                "is_monthly_customer": int(customer.get("is_monthly_customer") or 0),
            },
            "period_label": period_label,
            "month": str(month or "").strip(),
            "date_from": start_text,
            "date_to": end_text,
            "generated_at": _now(),
            "opening_balance": _money(opening_balance),
            "sales_amount": _money(sales_amount),
            "receipt_amount": _money(receipt_amount),
            "settlement_amount": _money(settlement_amount),
            "adjust_amount": _money(adjust_amount),
            "ledger_delta": _money(ledger_delta),
            "unpaid_amount": _money(unpaid_amount),
            "ending_balance": _money(ending_balance),
            "sales_quantity": _qty_text(sales_quantity),
            "sales_count": len(sales_result),
            "ledger_count": len(ledger_result),
            "sales": sales_result,
            "ledger": ledger_result,
        }

    def customer_sales(
        self,
        customer_id: int,
        page: int = 1,
        page_size: int = 50,
        period: str = "",
        month: str = "",
        pay_status: str = "",
    ) -> tuple[list[dict], int, dict]:
        page = max(1, int(page or 1))
        page_size = max(1, min(int(page_size or 50), 200))
        period_where, period_params, summary = self._sales_period_where(period, month)
        where_sql = "s.customer_id=%s AND s.status NOT IN ('canceled', 'deleted')"
        params: list[Any] = [customer_id]
        if period_where:
            where_sql += " AND " + " AND ".join(clause.replace("sales_at", "s.sales_at") for clause in period_where)
            params.extend(period_params)
        clean_pay_status = str(pay_status or "").strip()
        pay_status_label = ""
        if clean_pay_status and clean_pay_status != "all":
            if clean_pay_status in {"unsettled", "debt"}:
                where_sql += " AND s.pay_status IN ('unpaid', 'monthly', 'partial')"
                pay_status_label = "未结"
            else:
                where_sql += " AND s.pay_status=%s"
                params.append(clean_pay_status)
                pay_status_label = _pay_status_text(clean_pay_status)
        total_rows = self.query(
            f"""
            SELECT COUNT(*) AS total,
                   COALESCE(SUM(receivable_amount), 0) AS total_amount,
                   COALESCE(SUM(CASE
                     WHEN pay_status IN ('unpaid', 'monthly', 'partial') THEN receivable_amount
                   ELSE 0
                   END), 0) AS unpaid_amount
            FROM sales_order s
            WHERE {where_sql}
            """,
            params,
        )
        rows = self.query(
            f"""
            SELECT s.id, s.sales_no, s.status, s.pay_type, s.pay_status, s.total_quantity, s.goods_amount,
                   s.receivable_amount, s.sales_at, s.note,
                   wu.display_name AS created_by_name, wu.username AS created_by_username
            FROM sales_order s
            LEFT JOIN auth_user wu ON wu.id=s.created_by_user_id
            WHERE {where_sql}
            ORDER BY s.sales_at DESC, s.id DESC
            LIMIT %s OFFSET %s
            """,
            params + [page_size, (page - 1) * page_size],
        )
        sales_ids = [int(row["id"]) for row in rows if row.get("id")]
        items_by_sales: dict[int, list[str]] = {sid: [] for sid in sales_ids}
        if sales_ids:
            placeholders = ",".join(["%s"] * len(sales_ids))
            item_rows = self.query(
                f"""
                SELECT sales_order_id, title_snapshot, color_snapshot, quantity, unit_price
                FROM sales_order_item
                WHERE sales_order_id IN ({placeholders})
                ORDER BY sales_order_id ASC, line_no ASC
                """,
                sales_ids,
            )
            for item in item_rows:
                sid = int(item.get("sales_order_id") or 0)
                line = f"{item.get('title_snapshot') or '商品'} {item.get('color_snapshot') or ''} x{_qty_text(item.get('quantity'))}"
                items_by_sales.setdefault(sid, []).append(line.strip())
        result = []
        for row in rows:
            sid = int(row.get("id") or 0)
            result.append({
                "id": sid,
                "sales_no": row.get("sales_no") or str(sid),
                "status": row.get("status") or "",
                "status_text": self._sales_status_text(row.get("status") or ""),
                "pay_type": row.get("pay_type") or "",
                "pay_type_text": _pay_type_text(row.get("pay_type")),
                "pay_status": row.get("pay_status") or "",
                "pay_status_text": _pay_status_text(row.get("pay_status")),
                "total_quantity": _qty_text(row.get("total_quantity")),
                "goods_amount": _money(row.get("goods_amount")),
                "receivable_amount": _money(row.get("receivable_amount")),
                "sales_at": str(row.get("sales_at") or ""),
                "created_by_name": row.get("created_by_name") or row.get("created_by_username") or "",
                "items_preview": "；".join(items_by_sales.get(sid, [])[:3]),
                "note": row.get("note") or "",
            })
        total_row = total_rows[0] if total_rows else {}
        summary.update({
            "label": " · ".join([item for item in [summary.get("label") or "全部销售单", pay_status_label] if item]),
            "total": int(total_row.get("total") or 0),
            "total_amount": _money(total_row.get("total_amount")),
            "unpaid_amount": _money(total_row.get("unpaid_amount")),
            "balance_amount": _money(-_num(total_row.get("unpaid_amount"))),
        })
        return result, int(total_row.get("total") or 0), summary

    def _next_balance_ledger_no(self) -> str:
        return f"CB{datetime.now().strftime('%Y%m%d%H%M%S')}{int(time.time() * 1000) % 1000:03d}"

    def _positive_money(self, value: Any) -> Decimal:
        amount = Decimal(str(value or "0")).quantize(Decimal("0.01"))
        if amount <= 0:
            raise DBError("金额必须大于0")
        return amount

    def _signed_money(self, value: Any) -> Decimal:
        try:
            amount = Decimal(str(value or "0")).quantize(Decimal("0.01"))
        except Exception as exc:
            raise DBError("金额格式不正确") from exc
        if amount == 0:
            raise DBError("调整金额不能为0")
        return amount

    def _sku_tracks_inventory(self, sku: dict | None) -> bool:
        if not sku:
            return True
        explicit_policy = str(sku.get("inventory_policy") or "").strip().lower()
        if explicit_policy == "none":
            return False
        if explicit_policy in {"strict", "weak"}:
            return True
        if str(sku.get("product_type") or "").strip().lower() in {"bag", "bubble_bag"}:
            return False
        stock_text = " ".join(
            str(sku.get(key) or "")
            for key in ("title", "size_label", "primary_category_name", "product_category_text", "category_name")
        )
        if any(keyword in stock_text for keyword in FIXED_NON_STOCK_CATEGORY_KEYWORDS):
            return False
        value = sku.get("is_stock_item")
        if value in (None, ""):
            return True
        return int(value or 0) == 1

    def _inventory_rules(self, cursor=None) -> dict:
        if cursor is not None:
            return self._system_setting_value(cursor, "inventory_rules")
        with self.cursor() as local_cursor:
            return self._system_setting_value(local_cursor, "inventory_rules")

    def _default_out_warehouse_id(self, cursor) -> int:
        rules = self._inventory_rules(cursor)
        try:
            configured = int(rules.get("default_out_warehouse_id") or 0)
        except (TypeError, ValueError):
            configured = 0
        if configured > 0:
            return configured
        cursor.execute("SELECT id FROM warehouse WHERE name LIKE %s ORDER BY id ASC LIMIT 1", ("%店%",))
        row = cursor.fetchone()
        return int(row.get("id") or 2) if row else 2

    def _allow_negative_stock(self, cursor) -> bool:
        rules = self._inventory_rules(cursor)
        return int(rules.get("allow_negative_stock") or 0) == 1

    def _explicit_allow_negative_stock(self, value: Any, default: bool) -> bool:
        if value in (None, ""):
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return int(value) == 1
        text = str(value).strip().lower()
        if text in {"1", "true", "yes", "on", "allow", "allowed"}:
            return True
        if text in {"0", "false", "no", "off", "deny", "denied"}:
            return False
        return default

    def _normalize_category_inventory_policy(self, value: Any, default: str = "strict") -> str:
        clean = str(value or "").strip().lower()
        if clean in {"none", "no_stock", "non_stock", "0", "false", "不扣库存"}:
            return "none"
        if clean in {"weak", "loose", "弱库存"}:
            return "weak"
        if clean in {"strict", "stock", "stock_item", "1", "true", "扣库存"}:
            return "strict"
        return default

    def _sku_category_match_sql(self, alias: str, category_ids: list[int]) -> tuple[str, list[Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        for category_id in category_ids:
            clauses.append(
                f"({alias}.primary_category_id=%s OR JSON_CONTAINS(COALESCE({alias}.category_ids, '[]'), CAST(%s AS CHAR)))"
            )
            params.extend([category_id, category_id])
        return " OR ".join(clauses), params

    def _inventory_policy_category_ids(self, cursor, policy: str) -> list[int]:
        cursor.execute(
            "SELECT id FROM product_category WHERE is_enabled=1 AND inventory_policy=%s",
            (policy,),
        )
        return [int(row.get("id") or 0) for row in cursor.fetchall() if row.get("id")]

    def _sync_category_inventory_policy(self, cursor, category_ids: list[int], policy: str) -> dict:
        clean_id_set: set[int] = set()
        for item in category_ids:
            try:
                category_id = int(item or 0)
            except (TypeError, ValueError):
                continue
            if category_id > 0:
                clean_id_set.add(category_id)
        clean_ids = sorted(clean_id_set)
        if not clean_ids:
            return {"sku": 0, "spu": 0}
        clean_policy = self._normalize_category_inventory_policy(policy)
        now = _now()
        sku_affected = 0
        spu_affected = 0
        if self._table_exists(cursor, "product_sku"):
            match_sql, match_params = self._sku_category_match_sql("s", clean_ids)
            if clean_policy == "none":
                sku_affected = cursor.execute(
                    f"""
                    UPDATE product_sku s
                    SET s.is_stock_item=0, s.inventory_policy='none', s.updated_at=%s
                    WHERE s.deleted_at IS NULL
                      AND ({match_sql})
                      AND (s.is_stock_item <> 0 OR COALESCE(s.inventory_policy, '') <> 'none')
                    """,
                    [now, *match_params],
                )
            else:
                non_stock_ids = self._inventory_policy_category_ids(cursor, "none")
                non_stock_filter = ""
                non_stock_params: list[Any] = []
                if non_stock_ids:
                    non_stock_sql, non_stock_params = self._sku_category_match_sql("s", non_stock_ids)
                    non_stock_filter = f" AND NOT ({non_stock_sql})"
                sku_affected = cursor.execute(
                    f"""
                    UPDATE product_sku s
                    SET s.is_stock_item=1, s.inventory_policy=%s, s.updated_at=%s
                    WHERE s.deleted_at IS NULL
                      AND ({match_sql})
                      {non_stock_filter}
                      AND (s.is_stock_item <> 1 OR COALESCE(s.inventory_policy, '') <> %s)
                    """,
                    [clean_policy, now, *match_params, *non_stock_params, clean_policy],
                )
        if self._table_exists(cursor, "product_spu"):
            placeholders = ",".join(["%s"] * len(clean_ids))
            if clean_policy == "none":
                spu_affected = cursor.execute(
                    f"""
                    UPDATE product_spu
                    SET inventory_policy='none', updated_at=%s
                    WHERE default_category_id IN ({placeholders})
                      AND COALESCE(inventory_policy, '') <> 'none'
                    """,
                    [now, *clean_ids],
                )
            else:
                non_stock_ids = self._inventory_policy_category_ids(cursor, "none")
                non_stock_filter = ""
                non_stock_params = []
                if non_stock_ids:
                    non_stock_placeholders = ",".join(["%s"] * len(non_stock_ids))
                    non_stock_filter = f" AND default_category_id NOT IN ({non_stock_placeholders})"
                    non_stock_params = non_stock_ids
                spu_affected = cursor.execute(
                    f"""
                    UPDATE product_spu
                    SET inventory_policy=%s, updated_at=%s
                    WHERE default_category_id IN ({placeholders})
                      {non_stock_filter}
                      AND COALESCE(inventory_policy, '') <> %s
                    """,
                    [clean_policy, now, *clean_ids, *non_stock_params, clean_policy],
                )
        return {"sku": int(sku_affected or 0), "spu": int(spu_affected or 0)}

    def _sync_inventory_policy_categories(self, cursor=None) -> dict:
        if cursor is None:
            now_monotonic = time.monotonic()
            with self._inventory_policy_sync_lock:
                if now_monotonic - self._inventory_policy_last_sync_at < self._inventory_policy_sync_ttl_seconds:
                    return {"sku": 0, "spu": 0}
                self._inventory_policy_last_sync_at = now_monotonic
            with self.transaction() as local_cursor:
                return self._sync_inventory_policy_categories(local_cursor)
        if not self._table_exists(cursor, "product_category"):
            return {"sku": 0, "spu": 0}
        placeholders = ",".join(["%s"] * len(FIXED_NON_STOCK_CATEGORY_NAMES))
        cursor.execute(
            f"""
            UPDATE product_category
            SET inventory_policy='none', updated_at=%s
            WHERE name IN ({placeholders})
              AND COALESCE(inventory_policy, '') = ''
            """,
            [_now(), *FIXED_NON_STOCK_CATEGORY_NAMES],
        )
        cursor.execute(
            """
            SELECT id, inventory_policy
            FROM product_category
            WHERE is_enabled=1 AND inventory_policy IN ('none', 'strict', 'weak')
            ORDER BY FIELD(inventory_policy, 'none', 'strict', 'weak'), id ASC
            """,
        )
        synced = {"sku": 0, "spu": 0}
        for row in cursor.fetchall():
            result = self._sync_category_inventory_policy(
                cursor,
                [int(row.get("id") or 0)],
                str(row.get("inventory_policy") or "strict"),
            )
            synced["sku"] += result.get("sku", 0)
            synced["spu"] += result.get("spu", 0)
        with self._inventory_policy_sync_lock:
            self._inventory_policy_last_sync_at = time.monotonic()
        return synced

    def _apply_inventory_rule_keywords_to_categories(self, cursor, rules: dict) -> None:
        if not self._table_exists(cursor, "product_category"):
            return
        now = _now()
        stock_keywords = [str(item).strip() for item in rules.get("stock_category_keywords") or [] if str(item or "").strip()]
        non_stock_keywords = [str(item).strip() for item in rules.get("non_stock_category_keywords") or [] if str(item or "").strip()]
        for policy, keywords in (("strict", stock_keywords), ("none", non_stock_keywords)):
            for keyword in keywords:
                cursor.execute(
                    f"""
                    UPDATE product_category
                    SET inventory_policy='{policy}', updated_at=%s
                    WHERE is_enabled=1 AND name LIKE %s
                    """,
                    (now, f"%{keyword}%"),
                )

    def save_product_category(self, payload: dict, *, operator_user_id: Any = None) -> dict:
        payload = payload or {}
        category_id = int(payload.get("id") or 0)
        name = str(payload.get("name") or "").strip()
        if not name:
            raise DBError("分类名称不能为空")
        product_type = re.sub(r"[^0-9A-Za-z_]", "", str(payload.get("product_type") or "other").strip().lower())[:30] or "other"
        inventory_policy = self._normalize_category_inventory_policy(payload.get("inventory_policy"))
        try:
            parent_id = int(payload.get("parent_id") or payload.get("pid") or 0)
        except (TypeError, ValueError):
            parent_id = 0
        try:
            sort_order = int(payload.get("sort_order") or 0)
        except (TypeError, ValueError):
            sort_order = 0
        is_enabled = 1 if int(payload.get("is_enabled", 1) or 0) else 0
        code = re.sub(r"[^0-9A-Za-z_-]", "", str(payload.get("code") or "").strip())[:80]
        now = _now()
        operator_user_id = self._operator_user_id(operator_user_id)
        synced = {"sku": 0, "spu": 0}
        with self.transaction() as cursor:
            if category_id:
                cursor.execute("SELECT id, code FROM product_category WHERE id=%s LIMIT 1 FOR UPDATE", (category_id,))
                row = cursor.fetchone()
                if not row:
                    raise DBError("商品分类不存在")
                cursor.execute("SELECT id FROM product_category WHERE name=%s AND id<>%s LIMIT 1", (name, category_id))
                if cursor.fetchone():
                    raise DBError("商品分类名称已存在")
                cursor.execute(
                    """
                    UPDATE product_category
                    SET parent_id=%s, name=%s, product_type=%s, inventory_policy=%s,
                        sort_order=%s, is_enabled=%s, updated_at=%s
                    WHERE id=%s
                    """,
                    (parent_id or None, name, product_type, inventory_policy, sort_order, is_enabled, now, category_id),
                )
            else:
                cursor.execute("SELECT id FROM product_category WHERE name=%s LIMIT 1", (name,))
                if cursor.fetchone():
                    raise DBError("商品分类名称已存在")
                cursor.execute("SELECT COALESCE(MAX(id), 0) + 1 AS next_id FROM product_category")
                row = cursor.fetchone() or {}
                category_id = max(int(row.get("next_id") or 1), 1)
                code = code or f"cat_{category_id}"
                cursor.execute(
                    """
                    INSERT INTO product_category
                        (id, parent_id, code, name, product_type, inventory_policy, sort_order, is_enabled, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (category_id, parent_id or None, code, name, product_type, inventory_policy, sort_order, is_enabled, now, now),
                )
            synced = self._sync_category_inventory_policy(cursor, [category_id], inventory_policy)
        return {
            "code": 0,
            "data": {
                "category": {
                    "id": category_id,
                    "pid": parent_id,
                    "parent_id": parent_id,
                    "name": name,
                    "product_type": product_type,
                    "inventory_policy": inventory_policy,
                    "sort_order": sort_order,
                    "is_enabled": is_enabled,
                    "total": int(payload.get("total") or 0),
                },
                "synced": synced,
                "operator_user_id": operator_user_id,
            },
        }

    def _default_is_stock_item_for_product(self, cursor, category_ids: list[int], product_type: str = "") -> int:
        rules = self._inventory_rules(cursor)
        if str(product_type or "").strip().lower() in {"bag", "bubble_bag"}:
            return 0
        clean_category_ids: set[int] = set()
        for category_id in category_ids or []:
            try:
                clean_category_ids.add(int(category_id))
            except (TypeError, ValueError):
                continue
        non_stock_ids: set[int] = set()
        stock_ids: set[int] = set()
        for item in rules.get("non_stock_category_ids") or []:
            try:
                non_stock_ids.add(int(item))
            except (TypeError, ValueError):
                continue
        for item in rules.get("stock_category_ids") or []:
            try:
                stock_ids.add(int(item))
            except (TypeError, ValueError):
                continue
        keywords = [str(item).strip() for item in rules.get("non_stock_category_keywords") or [] if str(item).strip()]
        if product_type in {"service", "virtual"}:
            return 0
        if clean_category_ids & non_stock_ids:
            return 0
        if clean_category_ids & stock_ids:
            return 1
        if clean_category_ids:
            sorted_ids = sorted(clean_category_ids)
            placeholders = ",".join(["%s"] * len(sorted_ids))
            cursor.execute(f"SELECT name, inventory_policy FROM product_category WHERE id IN ({placeholders})", sorted_ids)
            category_rows = cursor.fetchall()
            category_policy = [
                self._normalize_category_inventory_policy(row.get("inventory_policy"), default="")
                for row in category_rows
                if str(row.get("inventory_policy") or "").strip()
            ]
            if "none" in category_policy:
                return 0
            if any(policy in {"strict", "weak"} for policy in category_policy):
                return 1
            names = " ".join(str(row.get("name") or "") for row in category_rows)
            if keywords and any(keyword and keyword in names for keyword in keywords):
                return 0
        return 1

    def _month_range(self, month: str) -> tuple[datetime, datetime]:
        clean_month = str(month or "").strip()
        if not re.match(r"^\d{4}-\d{2}$", clean_month):
            raise DBError("月份格式不正确")
        start = datetime.strptime(f"{clean_month}-01", "%Y-%m-%d")
        end = start.replace(year=start.year + 1, month=1) if start.month == 12 else start.replace(month=start.month + 1)
        return start, end

    def customer_balance_entry(
        self,
        customer_id: int,
        *,
        entry_type: str,
        amount: Any,
        pay_type: str = "",
        note: str = "",
        operator_user_id: Any = None,
    ) -> dict:
        self._ensure_operator_columns()
        self._ensure_system_settings_tables()
        operator_user_id = self._operator_user_id(operator_user_id)
        clean_type = str(entry_type or "").strip()
        if clean_type not in ("receipt", "recharge"):
            raise DBError("余额操作类型不正确")
        amount_dec = self._positive_money(amount)
        now = _now()
        ledger_no = self._next_balance_ledger_no()
        pay = str(pay_type or clean_type).strip() or clean_type
        with self.transaction() as cursor:
            cursor.execute("SELECT id, name FROM party WHERE id=%s AND kind='customer' AND deleted_at IS NULL LIMIT 1 FOR UPDATE", (int(customer_id),))
            customer = cursor.fetchone()
            if not customer:
                raise DBError("客户不存在")
            cursor.execute(
                """
                INSERT INTO customer_balance_ledger
                    (ledger_no, customer_id, entry_type, pay_type, amount, applied_amount,
                     balance_delta, note, created_by_user_id, created_at)
                VALUES (%s, %s, %s, %s, %s, 0, %s, %s, %s, %s)
                """,
                (ledger_no, int(customer_id), clean_type, pay, amount_dec, amount_dec, note, operator_user_id, now),
            )
            ledger_id = cursor.lastrowid
        return {
            "code": 0,
            "data": {
                "id": int(ledger_id),
                "ledger_no": ledger_no,
                "customer_id": int(customer_id),
                "entry_type": clean_type,
                "entry_type_text": _balance_entry_type_text(clean_type),
                "amount": _money(amount_dec),
                "balance_delta": _money(amount_dec),
            },
        }

    def customer_balance_adjust(
        self,
        customer_id: int,
        *,
        amount: Any,
        note: str = "",
        operator_user_id: Any = None,
    ) -> dict:
        operator_user_id = self._operator_user_id(operator_user_id)
        amount_dec = self._signed_money(amount)
        amount_abs = abs(amount_dec)
        now = _now()
        ledger_no = self._next_balance_ledger_no()
        with self.transaction() as cursor:
            cursor.execute("SELECT id, name FROM party WHERE id=%s AND kind='customer' AND deleted_at IS NULL LIMIT 1 FOR UPDATE", (int(customer_id),))
            customer = cursor.fetchone()
            if not customer:
                raise DBError("客户不存在")
            cursor.execute(
                """
                INSERT INTO customer_balance_ledger
                    (ledger_no, customer_id, entry_type, pay_type, amount, applied_amount,
                     balance_delta, note, created_by_user_id, created_at)
                VALUES (%s, %s, 'adjustment', 'adjustment', %s, 0, %s, %s, %s, %s)
                """,
                (ledger_no, int(customer_id), amount_abs, amount_dec, note, operator_user_id, now),
            )
            ledger_id = cursor.lastrowid
        return {
            "code": 0,
            "data": {
                "id": int(ledger_id),
                "ledger_no": ledger_no,
                "customer_id": int(customer_id),
                "entry_type": "adjustment",
                "entry_type_text": _balance_entry_type_text("adjustment"),
                "amount": _money(amount_abs),
                "balance_delta": _money(amount_dec),
            },
        }

    def customer_month_settlement(
        self,
        customer_id: int,
        *,
        month: str,
        amount: Any,
        pay_type: str = "wechat",
        note: str = "",
        operator_user_id: Any = None,
    ) -> dict:
        operator_user_id = self._operator_user_id(operator_user_id)
        amount_dec = self._positive_money(amount)
        start, end = self._month_range(month)
        month_text = start.strftime("%Y-%m")
        now = _now()
        ledger_no = self._next_balance_ledger_no()
        pay = str(pay_type or "wechat").strip() or "wechat"
        with self.transaction() as cursor:
            cursor.execute("SELECT id, name FROM party WHERE id=%s AND kind='customer' AND deleted_at IS NULL LIMIT 1 FOR UPDATE", (int(customer_id),))
            customer = cursor.fetchone()
            if not customer:
                raise DBError("客户不存在")
            cursor.execute(
                """
                SELECT id, receivable_amount, pay_status, pay_type
                FROM sales_order
                WHERE customer_id=%s AND status NOT IN ('canceled', 'deleted')
                  AND sales_at >= %s AND sales_at < %s
                  AND pay_status IN ('unpaid', 'monthly', 'partial')
                FOR UPDATE
                """,
                (int(customer_id), start.strftime("%Y-%m-%d 00:00:00"), end.strftime("%Y-%m-%d 00:00:00")),
            )
            orders = list(cursor.fetchall())
            if not orders:
                raise DBError("该月份没有未结金额")
            applied = Decimal("0.00")
            for order in orders:
                applied += Decimal(str(order.get("receivable_amount") or "0")).quantize(Decimal("0.01"))
            if applied <= 0:
                raise DBError("该月份没有未结金额")
            balance_delta = amount_dec - applied
            cursor.execute(
                """
                INSERT INTO customer_balance_ledger
                    (ledger_no, customer_id, entry_type, pay_type, amount, applied_amount,
                     balance_delta, related_month, note, created_by_user_id, created_at)
                VALUES (%s, %s, 'settlement', %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (ledger_no, int(customer_id), pay, amount_dec, applied, balance_delta, month_text, note, operator_user_id, now),
            )
            ledger_id = cursor.lastrowid
            order_ids = [int(order["id"]) for order in orders if order.get("id")]
            placeholders = ",".join(["%s"] * len(order_ids))
            cursor.execute(
                f"""
                UPDATE sales_order
                SET pay_status='paid', pay_type=%s, settlement_ledger_id=%s, settled_at=%s,
                    status=CASE WHEN status='draft' THEN 'completed' ELSE status END,
                    updated_at=%s
                WHERE id IN ({placeholders})
                """,
                [pay, int(ledger_id), now, now] + order_ids,
            )
            affected = cursor.rowcount
        return {
            "code": 0,
            "data": {
                "id": int(ledger_id),
                "ledger_no": ledger_no,
                "customer_id": int(customer_id),
                "month": month_text,
                "order_count": int(affected),
                "amount": _money(amount_dec),
                "applied_amount": _money(applied),
                "balance_delta": _money(balance_delta),
            },
        }

    def customer_balance_ledger(
        self,
        customer_id: int,
        page: int = 1,
        page_size: int = 100,
    ) -> tuple[list[dict], int, dict]:
        page = max(1, int(page or 1))
        page_size = max(1, min(int(page_size or 100), 200))
        summary_rows = self.query(
            """
            SELECT p.id, p.name,
                   COALESCE(wallet.wallet_amount, 0) AS wallet_amount,
                   COALESCE(debt.debt_amount, 0) AS debt_amount,
                   COALESCE(wallet.wallet_amount, 0) - COALESCE(debt.debt_amount, 0) AS balance_amount
            FROM party p
            LEFT JOIN (
                SELECT customer_id, SUM(balance_delta) AS wallet_amount
                FROM customer_balance_ledger
                GROUP BY customer_id
            ) wallet ON wallet.customer_id = p.id
            LEFT JOIN (
                SELECT customer_id, SUM(receivable_amount) AS debt_amount
                FROM sales_order
                WHERE status NOT IN ('canceled', 'deleted')
                  AND pay_status IN ('unpaid', 'monthly', 'partial')
                GROUP BY customer_id
            ) debt ON debt.customer_id = p.id
            WHERE p.id=%s AND p.kind='customer' AND p.deleted_at IS NULL
            LIMIT 1
            """,
            (int(customer_id),),
        )
        if not summary_rows:
            raise DBError("客户不存在")
        total_rows = self.query(
            "SELECT COUNT(*) AS total FROM customer_balance_ledger WHERE customer_id=%s",
            (int(customer_id),),
        )
        rows = self.query(
            """
            SELECT l.id, l.ledger_no, l.entry_type, l.pay_type, l.amount, l.applied_amount,
                   l.balance_delta, l.related_month, l.note, l.created_at,
                   wu.display_name AS created_by_name, wu.username AS created_by_username
            FROM customer_balance_ledger l
            LEFT JOIN auth_user wu ON wu.id=l.created_by_user_id
            WHERE l.customer_id=%s
            ORDER BY l.created_at DESC, l.id DESC
            LIMIT %s OFFSET %s
            """,
            (int(customer_id), page_size, (page - 1) * page_size),
        )
        result = [
            {
                "id": int(row.get("id") or 0),
                "ledger_no": row.get("ledger_no") or "",
                "customer_id": int(customer_id),
                "entry_type": row.get("entry_type") or "",
                "entry_type_text": _balance_entry_type_text(row.get("entry_type")),
                "pay_type": row.get("pay_type") or "",
                "pay_type_text": _pay_type_text(row.get("pay_type")),
                "amount": _money(row.get("amount")),
                "applied_amount": _money(row.get("applied_amount")),
                "balance_delta": _money(row.get("balance_delta")),
                "related_month": row.get("related_month") or "",
                "note": row.get("note") or "",
                "created_by_name": row.get("created_by_name") or row.get("created_by_username") or "",
                "created_at": str(row.get("created_at") or ""),
            }
            for row in rows
        ]
        summary_row = summary_rows[0]
        summary = {
            "customer_id": int(customer_id),
            "customer_name": summary_row.get("name") or "",
            "wallet_amount": _money(summary_row.get("wallet_amount")),
            "debt_amount": _money(summary_row.get("debt_amount")),
            "balance_amount": _money(summary_row.get("balance_amount")),
        }
        return result, int((total_rows[0] if total_rows else {}).get("total") or 0), summary

    def users(self, keyword: str = "", page: int = 1, page_size: int = 50) -> tuple[list[dict], int]:
        page = max(1, int(page or 1))
        page_size = max(1, min(int(page_size or 50), 200))
        where = ["1=1"]
        params: list[Any] = []
        if keyword:
            like = f"%{keyword}%"
            where.append("(u.username LIKE %s OR u.display_name LIKE %s OR u.phone LIKE %s OR p.name LIKE %s)")
            params.extend([like, like, like, like])
        where_sql = " AND ".join(where)
        total_rows = self.query(
            f"SELECT COUNT(*) AS total FROM auth_user u LEFT JOIN party p ON p.id=u.linked_party_id WHERE {where_sql}",
            params,
        )
        total = int(total_rows[0].get("total") or 0) if total_rows else 0
        rows = self.query(
            f"""
            SELECT u.id, u.username, u.display_name, u.phone, u.role, u.linked_party_id,
                   u.approval_status, u.is_active, u.is_admin, u.last_login_at, u.created_at,
                   p.name AS party_name,
                   GROUP_CONCAT(CONCAT(ai.provider, ':', ai.external_user_id) ORDER BY ai.id SEPARATOR ',') AS identities
            FROM auth_user u
            LEFT JOIN party p ON p.id = u.linked_party_id
            LEFT JOIN auth_identity ai ON ai.user_id = u.id AND ai.is_enabled = 1
            WHERE {where_sql}
            GROUP BY u.id
            ORDER BY u.updated_at DESC, u.id DESC
            LIMIT %s OFFSET %s
            """,
            params + [page_size, (page - 1) * page_size],
        )
        for row in rows:
            username = str(row.get("username") or "")
            if username.lower().startswith("shopxo:"):
                row["account_display"] = f"ID {username.split(':', 1)[1]}"
            else:
                row["account_display"] = username
            row["role_text"] = {
                "admin": "管理员",
                "staff": "员工",
                "warehouse": "员工",
                "designer": "员工",
                "readonly": "访客",
                "customer": "客户",
                "guest": "访客",
            }.get(str(row.get("role") or ""), str(row.get("role") or ""))
        return rows, total

    def update_user(
        self,
        user_id: int,
        role: str | None = None,
        is_active: int | None = None,
        display_name: str | None = None,
    ) -> dict:
        updates = []
        params: list[Any] = []
        if role is not None:
            role_map = {
                "管理员": "admin",
                "老板": "admin",
                "员工": "staff",
                "客户": "customer",
                "访客": "guest",
            }
            role = role_map.get(str(role or "").strip(), str(role or "").strip())
            allowed_roles = {"admin", "staff", "customer", "guest"}
            if role not in allowed_roles:
                return {"code": 400, "msg": "角色不正确"}
            updates.append("role=%s")
            params.append(role)
            updates.append("is_admin=%s")
            params.append(1 if role == "admin" else 0)
        if is_active is not None:
            updates.append("is_active=%s")
            params.append(1 if int(is_active or 0) else 0)
            if int(is_active or 0):
                updates.append("approval_status='approved'")
        if display_name is not None:
            clean_name = str(display_name or "").strip()
            if not clean_name:
                return {"code": 400, "msg": "显示名称不能为空"}
            updates.append("display_name=%s")
            params.append(clean_name[:80])
        if not updates:
            return {"code": 400, "msg": "没有要更新的字段"}
        updates.append("updated_at=%s")
        params.append(_now())
        params.append(int(user_id))
        affected = self.execute(f"UPDATE auth_user SET {', '.join(updates)} WHERE id=%s", params)
        return {"code": 0, "data": {"affected": affected, "id": int(user_id)}}

    def _identity_user_by_id(self, cursor, user_id: int) -> dict | None:
        cursor.execute(
            """
            SELECT u.*, p.name AS linked_party_name
            FROM auth_user u
            LEFT JOIN party p ON p.id=u.linked_party_id
            WHERE u.id=%s
            LIMIT 1
            """,
            (int(user_id),),
        )
        return cursor.fetchone()

    def _identity_users_by_phone(self, cursor, phone: str) -> list[dict]:
        digits = _phone_digits(phone)
        if not digits:
            return []
        cursor.execute(
            """
            SELECT u.*, p.name AS linked_party_name
            FROM auth_user u
            LEFT JOIN party p ON p.id=u.linked_party_id
            WHERE u.phone=%s
            ORDER BY u.is_admin DESC, u.id ASC
            LIMIT 5
            """,
            (digits,),
        )
        return list(cursor.fetchall())

    def _identity_customers_by_phone(self, cursor, phone: str) -> list[dict]:
        digits = _phone_digits(phone)
        if not digits:
            return []
        cursor.execute(
            """
            SELECT id, name, phone, phone_normalized
            FROM party
            WHERE kind='customer'
              AND deleted_at IS NULL
              AND (phone_normalized=%s OR phone=%s)
            ORDER BY id ASC
            LIMIT 5
            """,
            (digits, digits),
        )
        return list(cursor.fetchall())

    def _identity_user_is_internal(self, user: dict | None) -> bool:
        if not user:
            return False
        role = str(user.get("role") or "").strip()
        return int(user.get("is_admin") or 0) == 1 or role in {"admin", "staff", "warehouse", "designer"}

    def _identity_display_name(self, profile: dict | None, fallback: str = "微信用户") -> str:
        profile = profile if isinstance(profile, dict) else {}
        return str(
            profile.get("nickName")
            or profile.get("nickname")
            or profile.get("display_name")
            or profile.get("name")
            or fallback
        ).strip()[:80] or fallback

    def _identity_upsert(self, cursor, *, user_id: int, provider: str, external_id: str, openid: str = "", unionid: str = "", profile: dict | None = None) -> None:
        now = _now()
        cursor.execute(
            """
            INSERT INTO auth_identity
                (user_id, provider, external_user_id, openid, unionid, raw_profile, is_enabled, created_at, updated_at)
            VALUES (%s,%s,%s,%s,%s,%s,1,%s,%s)
            ON DUPLICATE KEY UPDATE
                user_id=VALUES(user_id),
                openid=VALUES(openid),
                unionid=VALUES(unionid),
                raw_profile=VALUES(raw_profile),
                is_enabled=1,
                updated_at=VALUES(updated_at)
            """,
            (
                int(user_id),
                str(provider or "").strip(),
                str(external_id or "").strip(),
                openid or None,
                unionid or None,
                json.dumps(profile or {}, ensure_ascii=False),
                now,
                now,
            ),
        )

    def _identity_link_customer_if_allowed(self, cursor, *, user: dict, phone: str) -> tuple[int | None, str, bool]:
        customers = self._identity_customers_by_phone(cursor, phone)
        if len(customers) > 1:
            return None, "customer_phone_conflict", True
        if len(customers) != 1:
            return None, "no_customer_match", False
        customer_id = int(customers[0].get("id") or 0)
        if self._identity_user_is_internal(user):
            return customer_id, "internal_user_not_changed", False
        cursor.execute(
            """
            UPDATE auth_user
            SET linked_party_id=%s,
                role=CASE WHEN role IN ('guest','customer','') THEN 'customer' ELSE role END,
                approval_status=CASE WHEN approval_status='pending' THEN 'approved' ELSE approval_status END,
                is_active=1,
                updated_at=%s
            WHERE id=%s
            """,
            (customer_id, _now(), int(user["id"])),
        )
        return customer_id, "linked_customer", False

    def identity_sync_user_phone(self, user_id: int, *, phone: str, operator_user_id: Any = None) -> dict:
        digits = _phone_digits(phone)
        if not digits:
            return {"code": 400, "msg": "手机号不能为空"}
        with self.transaction() as cursor:
            user = self._identity_user_by_id(cursor, int(user_id))
            if not user:
                return {"code": 404, "msg": "用户不存在"}
            cursor.execute(
                "UPDATE auth_user SET phone=%s, updated_at=%s WHERE id=%s",
                (digits, _now(), int(user_id)),
            )
            self._identity_upsert(cursor, user_id=int(user_id), provider="phone", external_id=digits)
            user["phone"] = digits
            customer_id, status, needs_review = self._identity_link_customer_if_allowed(cursor, user=user, phone=digits)
        return {
            "code": 0,
            "data": {
                "user_id": int(user_id),
                "phone": digits,
                "customer_id": customer_id,
                "bind_status": status,
                "needs_review": needs_review,
            },
        }

    def identity_sync_customer_phone(self, customer_id: int, *, phone: str, operator_user_id: Any = None) -> dict:
        self._ensure_party_columns()
        digits = _phone_digits(phone)
        if not digits:
            return {"code": 400, "msg": "手机号不能为空"}
        with self.transaction() as cursor:
            cursor.execute(
                """
                SELECT id, name
                FROM party
                WHERE id=%s AND kind='customer' AND deleted_at IS NULL
                LIMIT 1
                """,
                (int(customer_id),),
            )
            customer = cursor.fetchone()
            if not customer:
                return {"code": 404, "msg": "客户不存在"}
            cursor.execute(
                """
                UPDATE party
                SET phone=%s, phone_normalized=%s, updated_at=%s
                WHERE id=%s
                """,
                (digits, digits, _now(), int(customer_id)),
            )
            users = self._identity_users_by_phone(cursor, digits)
            if len(users) > 1:
                return {
                    "code": 409,
                    "msg": "手机号匹配多个用户，请人工处理",
                    "data": {"customer_id": int(customer_id), "phone": digits, "needs_review": True},
                    "_http_status": 409,
                }
            linked_user_id = None
            bind_status = "no_user_match"
            if len(users) == 1:
                user = users[0]
                linked_user_id = int(user.get("id") or 0)
                self._identity_upsert(cursor, user_id=linked_user_id, provider="phone", external_id=digits)
                if self._identity_user_is_internal(user):
                    bind_status = "internal_user_not_changed"
                else:
                    cursor.execute(
                        """
                        UPDATE auth_user
                        SET linked_party_id=%s,
                            role=CASE WHEN role IN ('guest','customer','') THEN 'customer' ELSE role END,
                            approval_status=CASE WHEN approval_status='pending' THEN 'approved' ELSE approval_status END,
                            is_active=1,
                            updated_at=%s
                        WHERE id=%s
                        """,
                        (int(customer_id), _now(), linked_user_id),
                    )
                    bind_status = "linked_user"
        return {
            "code": 0,
            "data": {
                "customer_id": int(customer_id),
                "user_id": linked_user_id,
                "phone": digits,
                "bind_status": bind_status,
                "needs_review": False,
            },
        }

    def identity_link_wechat(self, *, openid: str, unionid: str = "", phone: str = "", profile: dict | None = None) -> dict:
        openid = str(openid or "").strip()
        unionid = str(unionid or "").strip()
        digits = _phone_digits(phone)
        profile = profile if isinstance(profile, dict) else {}
        if not openid:
            return {"code": 400, "msg": "缺少微信 openid"}
        now = _now()
        with self.transaction() as cursor:
            cursor.execute(
                """
                SELECT u.*, p.name AS linked_party_name
                FROM auth_identity ai
                JOIN auth_user u ON u.id=ai.user_id
                LEFT JOIN party p ON p.id=u.linked_party_id
                WHERE ai.provider='wechat'
                  AND ai.external_user_id=%s
                  AND ai.is_enabled=1
                LIMIT 1
                """,
                (openid,),
            )
            existing_user = cursor.fetchone()
            if existing_user:
                user_id = int(existing_user["id"])
                saved_phone = _phone_digits(existing_user.get("phone"))
                link_phone = digits or saved_phone
                if digits and not existing_user.get("phone"):
                    cursor.execute("UPDATE auth_user SET phone=%s, updated_at=%s WHERE id=%s", (digits, now, user_id))
                    existing_user["phone"] = digits
                if link_phone:
                    self._identity_upsert(cursor, user_id=user_id, provider="phone", external_id=link_phone)
                    customer_id, status, needs_review = self._identity_link_customer_if_allowed(cursor, user=existing_user, phone=link_phone)
                else:
                    customer_id = existing_user.get("linked_party_id")
                    status = "existing_identity"
                    needs_review = False
                self._identity_upsert(
                    cursor,
                    user_id=user_id,
                    provider="wechat",
                    external_id=openid,
                    openid=openid,
                    unionid=unionid,
                    profile=profile,
                )
                return {
                    "code": 0,
                    "data": {
                        "user_id": user_id,
                        "customer_id": customer_id,
                        "phone": link_phone or "",
                        "bind_status": status,
                        "needs_review": needs_review,
                    },
                }

            users = self._identity_users_by_phone(cursor, digits) if digits else []
            if len(users) > 1:
                return {
                    "code": 409,
                    "msg": "手机号匹配多个用户，请人工处理",
                    "data": {"phone": digits, "needs_review": True},
                    "_http_status": 409,
                }
            if len(users) == 1:
                user = users[0]
                user_id = int(user["id"])
                if digits:
                    self._identity_upsert(cursor, user_id=user_id, provider="phone", external_id=digits)
                    customer_id, status, needs_review = self._identity_link_customer_if_allowed(cursor, user=user, phone=digits)
                else:
                    customer_id = user.get("linked_party_id")
                    status = "linked_existing_user"
                    needs_review = False
                self._identity_upsert(
                    cursor,
                    user_id=user_id,
                    provider="wechat",
                    external_id=openid,
                    openid=openid,
                    unionid=unionid,
                    profile=profile,
                )
                return {
                    "code": 0,
                    "data": {
                        "user_id": user_id,
                        "customer_id": customer_id,
                        "phone": digits or user.get("phone") or "",
                        "bind_status": "linked_existing_user" if status == "no_customer_match" else status,
                        "needs_review": needs_review,
                    },
                }

            customers = self._identity_customers_by_phone(cursor, digits) if digits else []
            if len(customers) > 1:
                return {
                    "code": 409,
                    "msg": "手机号匹配多个客户，请人工处理",
                    "data": {"phone": digits, "needs_review": True},
                    "_http_status": 409,
                }
            customer_id = int(customers[0]["id"]) if len(customers) == 1 else None
            display_name = self._identity_display_name(profile, fallback=f"微信用户{digits[-4:]}" if digits else "微信用户")
            username = f"wechat:{hashlib.sha1(openid.encode('utf-8')).hexdigest()[:24]}"
            approval_status = "approved" if digits else "pending"
            cursor.execute(
                """
                INSERT INTO auth_user
                    (username, password_hash, display_name, phone, role, linked_party_id,
                     approval_status, is_active, is_admin, created_at, updated_at)
                VALUES (%s,NULL,%s,%s,'customer',%s,%s,1,0,%s,%s)
                ON DUPLICATE KEY UPDATE
                    display_name=VALUES(display_name),
                    phone=COALESCE(VALUES(phone), phone),
                    linked_party_id=COALESCE(VALUES(linked_party_id), linked_party_id),
                    updated_at=VALUES(updated_at)
                """,
                (username, display_name, digits or None, customer_id, approval_status, now, now),
            )
            cursor.execute("SELECT id FROM auth_user WHERE username=%s LIMIT 1", (username,))
            user_id = int(cursor.fetchone()["id"])
            self._identity_upsert(
                cursor,
                user_id=user_id,
                provider="wechat",
                external_id=openid,
                openid=openid,
                unionid=unionid,
                profile=profile,
            )
            if digits:
                self._identity_upsert(cursor, user_id=user_id, provider="phone", external_id=digits)
        return {
            "code": 0,
            "data": {
                "user_id": user_id,
                "customer_id": customer_id,
                "phone": digits,
                "bind_status": "created_customer_user" if customer_id else "created_phone_user" if digits else "created_pending_wechat_user",
                "needs_review": False,
            },
        }

    def warehouse_list(self) -> list[dict]:
        rows = self.query(
            """
            SELECT id, code, name, warehouse_type, address, contact_name, phone,
                   is_default_sales, is_default_inbound, is_enabled
            FROM warehouse
            WHERE is_enabled=1
            ORDER BY COALESCE(sort_order, id), id
            """
        )
        return [
            {
                "id": row.get("id"),
                "warehouse_id": row.get("id"),
                "code": row.get("code") or "",
                "name": row.get("name") or f"仓库#{row.get('id')}",
                "warehouse_name": row.get("name") or f"仓库#{row.get('id')}",
                "type": row.get("warehouse_type") or "",
                "is_default_sales": int(row.get("is_default_sales") or 0),
                "is_default_inbound": int(row.get("is_default_inbound") or 0),
            }
            for row in rows
        ]

    # ---- inventory reads ----

    def resolve_sku_id(self, product_id: int, cursor=None) -> int | None:
        if not product_id:
            return None
        close_cursor = False
        if cursor is None:
            cursor = self._get_connection().cursor()
            close_cursor = True
        try:
            cursor.execute("SELECT id FROM product_sku WHERE id=%s AND deleted_at IS NULL LIMIT 1", (int(product_id),))
            row = cursor.fetchone()
            if row:
                return int(row["id"])
            cursor.execute(
                """
                SELECT native_id
                FROM migration_product_ref
                WHERE entity_type='sku' AND external_id=%s
                LIMIT 1
                """,
                (str(product_id),),
            )
            row = cursor.fetchone()
            return int(row["native_id"]) if row and row.get("native_id") else None
        finally:
            if close_cursor:
                cursor.close()

    def _inventory_rows(self, where_sql: str, params: list[Any], limit: int = 1000) -> list[dict]:
        rows = self.query(
            f"""
            SELECT
                b.sku_id AS product_id,
                sp.id AS spu_id,
                s.sku_no,
                s.is_stock_item,
                sp.title,
                s.color,
                sp.case_pack_qty,
                b.warehouse_id,
                w.name AS warehouse_name,
                b.unit_id,
                u.name AS unit_name,
                b.quantity,
                b.available_qty,
                b.reserved_qty
            FROM inventory_balance b
            JOIN product_sku s ON s.id = b.sku_id
            JOIN product_spu sp ON sp.id = s.spu_id
            JOIN warehouse w ON w.id = b.warehouse_id
            LEFT JOIN product_unit u ON u.id = b.unit_id
            WHERE {where_sql}
            ORDER BY sp.title ASC, s.color ASC, w.id ASC
            LIMIT %s
            """,
            params + [max(1, min(limit, 5000))],
        )
        result = []
        for row in rows:
            piece = f"1件{_qty_text(row.get('case_pack_qty'))}套" if row.get("case_pack_qty") not in (None, "") else ""
            result.append({
                "product_id": row.get("product_id"),
                "id": row.get("product_id"),
                "spu_id": row.get("spu_id"),
                "sku_no": row.get("sku_no") or "",
                "is_stock_item": int(row.get("is_stock_item") if row.get("is_stock_item") not in (None, "") else 1),
                "产品名称": row.get("title") or "商品",
                "title": row.get("title") or "商品",
                "name": row.get("title") or "商品",
                "【颜色】": row.get("color") or "",
                "spec": row.get("color") or "",
                "color": row.get("color") or "",
                "simple_desc": piece,
                "warehouse_id": row.get("warehouse_id"),
                "【仓库】": row.get("warehouse_name") or "",
                "warehouse_name": row.get("warehouse_name") or "",
                "unit_id": row.get("unit_id"),
                "unit_name": row.get("unit_name") or "",
                "库存数量": _qty_text(row.get("quantity")),
                "inventory": _qty_text(row.get("quantity")),
                "stock": _qty_text(row.get("quantity")),
                "available_qty": _qty_text(row.get("available_qty")),
                "reserved_qty": _qty_text(row.get("reserved_qty")),
            })
        return result

    def get_product_inventory(self, product_id: int) -> list[dict]:
        sku_id = self.resolve_sku_id(product_id)
        if not sku_id:
            return []
        return self._inventory_rows("b.sku_id=%s", [sku_id], limit=100)

    def get_warehouse_inventory(self, warehouse_id: int) -> list[dict]:
        return self._inventory_rows("b.warehouse_id=%s AND b.quantity <> 0", [int(warehouse_id)], limit=3000)

    def search_inventory(
        self,
        keyword: str = "",
        color: str = "",
        warehouse_id: int | None = None,
        only_in_stock: bool = False,
        limit: int = 100,
    ) -> list[dict]:
        where_sql, params = self._sku_where(keyword, active_only=True)
        where = [where_sql]
        if color:
            where.append("s.color LIKE %s")
            params.append(f"%{color}%")
        if warehouse_id:
            where.append("b.warehouse_id = %s")
            params.append(int(warehouse_id))
        if only_in_stock:
            where.append("b.quantity > 0")
        return self._inventory_rows(" AND ".join(where), params, limit=max(limit, 100))

    def inventory_balances(
        self,
        keyword: str = "",
        sku_id: int | None = None,
        color: str = "",
        warehouse_id: int | None = None,
        stock_status: str = "",
        group_by_product: bool = False,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[dict], int]:
        self._sync_inventory_policy_categories()
        where_sql, params = self._sku_where(keyword, active_only=False, stock_mode="stock")
        if sku_id:
            resolved_sku_id = self.resolve_sku_id(int(sku_id))
            if not resolved_sku_id:
                return [], 0
            where_sql = f"{where_sql} AND s.id=%s"
            params.append(int(resolved_sku_id))
        color = str(color or "").strip()
        if color:
            where_sql = f"{where_sql} AND s.color LIKE %s"
            params.append(f"%{color}%")
        warehouse_where = ["w.is_enabled=1"]
        warehouse_params: list[Any] = []
        if warehouse_id:
            warehouse_where.append("w.id=%s")
            warehouse_params.append(int(warehouse_id))
        warehouse_where_sql = " AND ".join(warehouse_where)
        quantity_expr = "COALESCE(b.quantity, 0)"
        stock_status = (stock_status or "").strip()
        status_where = ""
        if stock_status == "in_stock":
            status_where = f"{quantity_expr} > 0"
        elif stock_status == "zero":
            status_where = f"{quantity_expr} = 0"
        elif stock_status == "negative":
            status_where = f"{quantity_expr} < 0"
        if group_by_product:
            scoped_where_sql = f"{where_sql} AND {warehouse_where_sql}"
            if status_where:
                scoped_where_sql = f"{scoped_where_sql} AND {status_where}"
            scoped_params = params + warehouse_params
            count_rows = self.query(
                f"""
                SELECT COUNT(*) AS total
                FROM (
                    SELECT sp.id
                    FROM product_sku s
                    JOIN product_spu sp ON sp.id=s.spu_id
                    CROSS JOIN warehouse w
                    LEFT JOIN inventory_balance b ON b.sku_id=s.id AND b.warehouse_id=w.id
                    WHERE {scoped_where_sql}
                    GROUP BY sp.id
                ) page_spu_count
                """,
                scoped_params,
            )
            total = int(count_rows[0].get("total") or 0) if count_rows else 0
            page_spu = self.query(
                f"""
                SELECT sp.id
                FROM product_sku s
                JOIN product_spu sp ON sp.id=s.spu_id
                CROSS JOIN warehouse w
                LEFT JOIN inventory_balance b ON b.sku_id=s.id AND b.warehouse_id=w.id
                WHERE {scoped_where_sql}
                GROUP BY sp.id, sp.title
                ORDER BY sp.title ASC, sp.id ASC
                LIMIT %s OFFSET %s
                """,
                scoped_params + [page_size, (max(1, page) - 1) * page_size],
            )
            spu_ids = [int(row.get("id") or 0) for row in page_spu if row.get("id")]
            if not spu_ids:
                return [], total
            placeholders = ",".join(["%s"] * len(spu_ids))
            fetch_where_sql = f"{where_sql} AND {warehouse_where_sql} AND sp.id IN ({placeholders})"
            if status_where:
                fetch_where_sql = f"{fetch_where_sql} AND {status_where}"
            rows = self.query(
                f"""
                SELECT
                    s.id AS product_id,
                    sp.id AS spu_id,
                    s.sku_no,
                    s.is_stock_item,
                    sp.title,
                    s.color,
                    sp.case_pack_qty,
                    w.id AS warehouse_id,
                    w.name AS warehouse_name,
                    COALESCE(b.unit_id, s.unit_id) AS unit_id,
                    u.name AS unit_name,
                    COALESCE(b.quantity, 0) AS quantity,
                    COALESCE(b.available_qty, b.quantity, 0) AS available_qty,
                    COALESCE(b.reserved_qty, 0) AS reserved_qty
                FROM product_sku s
                JOIN product_spu sp ON sp.id=s.spu_id
                CROSS JOIN warehouse w
                LEFT JOIN inventory_balance b ON b.sku_id=s.id AND b.warehouse_id=w.id
                LEFT JOIN product_unit u ON u.id=COALESCE(b.unit_id, s.unit_id)
                WHERE {fetch_where_sql}
                ORDER BY sp.title ASC, s.color ASC, w.id ASC
                """,
                params + warehouse_params + spu_ids,
            )
        elif status_where:
            scoped_where_sql = f"{where_sql} AND {warehouse_where_sql} AND {status_where}"
            scoped_params = params + warehouse_params
            count_rows = self.query(
                f"""
                SELECT COUNT(*) AS total
                FROM product_sku s
                JOIN product_spu sp ON sp.id=s.spu_id
                CROSS JOIN warehouse w
                LEFT JOIN inventory_balance b ON b.sku_id=s.id AND b.warehouse_id=w.id
                WHERE {scoped_where_sql}
                """,
                scoped_params,
            )
            total = int(count_rows[0].get("total") or 0) if count_rows else 0
            rows = self.query(
                f"""
                SELECT
                    s.id AS product_id,
                    sp.id AS spu_id,
                    s.sku_no,
                    s.is_stock_item,
                    sp.title,
                    s.color,
                    sp.case_pack_qty,
                    w.id AS warehouse_id,
                    w.name AS warehouse_name,
                    COALESCE(b.unit_id, s.unit_id) AS unit_id,
                    u.name AS unit_name,
                    COALESCE(b.quantity, 0) AS quantity,
                    COALESCE(b.available_qty, b.quantity, 0) AS available_qty,
                    COALESCE(b.reserved_qty, 0) AS reserved_qty
                FROM product_sku s
                JOIN product_spu sp ON sp.id=s.spu_id
                CROSS JOIN warehouse w
                LEFT JOIN inventory_balance b ON b.sku_id=s.id AND b.warehouse_id=w.id
                LEFT JOIN product_unit u ON u.id=COALESCE(b.unit_id, s.unit_id)
                WHERE {scoped_where_sql}
                ORDER BY sp.title ASC, s.color ASC, w.id ASC
                LIMIT %s OFFSET %s
                """,
                scoped_params + [page_size, (max(1, page) - 1) * page_size],
            )
        else:
            count_rows = self.query(
                f"""
                SELECT COUNT(*) AS total
                FROM product_sku s
                JOIN product_spu sp ON sp.id=s.spu_id
                WHERE {where_sql}
                """,
                params,
            )
            total = int(count_rows[0].get("total") or 0) if count_rows else 0
            rows = self.query(
                f"""
                SELECT
                    s.id AS product_id,
                    sp.id AS spu_id,
                    s.sku_no,
                    s.is_stock_item,
                    sp.title,
                    s.color,
                    sp.case_pack_qty,
                    w.id AS warehouse_id,
                    w.name AS warehouse_name,
                    COALESCE(b.unit_id, s.unit_id) AS unit_id,
                    u.name AS unit_name,
                    COALESCE(b.quantity, 0) AS quantity,
                    COALESCE(b.available_qty, b.quantity, 0) AS available_qty,
                    COALESCE(b.reserved_qty, 0) AS reserved_qty
                FROM (
                    SELECT s.id
                    FROM product_sku s
                    JOIN product_spu sp ON sp.id=s.spu_id
                    WHERE {where_sql}
                    ORDER BY sp.title ASC, s.color ASC, s.id ASC
                    LIMIT %s OFFSET %s
                ) page_sku
                JOIN product_sku s ON s.id=page_sku.id
                JOIN product_spu sp ON sp.id=s.spu_id
                CROSS JOIN warehouse w
                LEFT JOIN inventory_balance b ON b.sku_id=s.id AND b.warehouse_id=w.id
                LEFT JOIN product_unit u ON u.id=COALESCE(b.unit_id, s.unit_id)
                WHERE {warehouse_where_sql}
                ORDER BY sp.title ASC, s.color ASC, w.id ASC
                """,
                params + [page_size, (max(1, page) - 1) * page_size] + warehouse_params,
            )
        result = []
        for row in rows:
            piece = f"1件{_qty_text(row.get('case_pack_qty'))}套" if row.get("case_pack_qty") not in (None, "") else ""
            result.append({
                "product_id": row.get("product_id"),
                "id": row.get("product_id"),
                "spu_id": row.get("spu_id"),
                "sku_no": row.get("sku_no") or "",
                "is_stock_item": int(row.get("is_stock_item") if row.get("is_stock_item") not in (None, "") else 1),
                "产品名称": row.get("title") or "商品",
                "title": row.get("title") or "商品",
                "name": row.get("title") or "商品",
                "【颜色】": row.get("color") or "",
                "spec": row.get("color") or "",
                "color": row.get("color") or "",
                "simple_desc": piece,
                "warehouse_id": row.get("warehouse_id"),
                "【仓库】": row.get("warehouse_name") or "",
                "warehouse_name": row.get("warehouse_name") or "",
                "unit_id": row.get("unit_id"),
                "unit_name": row.get("unit_name") or "",
                "库存数量": _qty_text(row.get("quantity")),
                "inventory": _qty_text(row.get("quantity")),
                "stock": _qty_text(row.get("quantity")),
                "quantity": _qty_text(row.get("quantity")),
                "available_qty": _qty_text(row.get("available_qty")),
                "reserved_qty": _qty_text(row.get("reserved_qty")),
            })
        return result, total

    def inventory_ledger(
        self,
        keyword: str = "",
        sku_id: int | None = None,
        warehouse_id: int | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[dict], int]:
        where = ["1=1"]
        params: list[Any] = []
        if sku_id:
            where.append("l.sku_id=%s")
            params.append(int(sku_id))
        if warehouse_id:
            where.append("l.warehouse_id=%s")
            params.append(int(warehouse_id))
        if keyword:
            like = f"%{keyword}%"
            where.append("(l.ledger_no LIKE %s OR l.sku_no_snapshot LIKE %s OR sp.title LIKE %s OR s.color LIKE %s OR w.name LIKE %s OR l.biz_type LIKE %s)")
            params.extend([like, like, like, like, like, like])
        where_sql = " AND ".join(where)
        total_rows = self.query(
            f"""
            SELECT COUNT(*) AS total
            FROM inventory_ledger l
            JOIN product_sku s ON s.id=l.sku_id
            JOIN product_spu sp ON sp.id=s.spu_id
            JOIN warehouse w ON w.id=l.warehouse_id
            WHERE {where_sql}
            """,
            params,
        )
        rows = self.query(
            f"""
            SELECT l.*, sp.title, s.color, w.name AS warehouse_name, u.name AS unit_name,
                   wu.display_name AS operator_name, wu.username AS operator_username
            FROM inventory_ledger l
            JOIN product_sku s ON s.id=l.sku_id
            JOIN product_spu sp ON sp.id=s.spu_id
            JOIN warehouse w ON w.id=l.warehouse_id
            LEFT JOIN product_unit u ON u.id=l.unit_id
            LEFT JOIN auth_user wu ON wu.id=l.operator_user_id
            WHERE {where_sql}
            ORDER BY l.occurred_at DESC, l.id DESC
            LIMIT %s OFFSET %s
            """,
            params + [page_size, (max(1, page) - 1) * page_size],
        )
        return rows, int(total_rows[0].get("total") or 0) if total_rows else 0

    # ---- sales/workflow reads ----

    def sales_cards(
        self,
        keyword: str = "",
        page: int = 1,
        page_size: int = 20,
        status: Any = None,
        status_filter: str = "active",
        pay_status: str = "",
        date_from: str = "",
        date_to: str = "",
        customer_id: int | None = None,
    ) -> tuple[list[dict], int]:
        self._ensure_operator_columns()
        self._ensure_sales_delete_columns()
        page = max(1, int(page or 1))
        page_size = max(1, min(int(page_size or 20), 100))
        where = ["1=1"]
        params: list[Any] = []
        if status not in (None, ""):
            where.append("s.status=%s")
            params.append(str(status))
        elif status_filter == "deleted":
            where.append("s.status='deleted'")
        else:
            where.append("s.status NOT IN ('canceled', 'deleted')")
        if pay_status:
            where.append("s.pay_status=%s")
            params.append(str(pay_status))
        if date_from:
            where.append("DATE(s.sales_at)>=%s")
            params.append(str(date_from)[:10])
        if date_to:
            where.append("DATE(s.sales_at)<=%s")
            params.append(str(date_to)[:10])
        if customer_id:
            where.append("s.customer_id=%s")
            params.append(int(customer_id))
        join_items = ""
        if keyword:
            join_items = " LEFT JOIN sales_order_item si_filter ON si_filter.sales_order_id=s.id"
            like = f"%{keyword}%"
            where.append("(s.sales_no LIKE %s OR s.customer_name_snapshot LIKE %s OR si_filter.title_snapshot LIKE %s OR si_filter.sku_no_snapshot LIKE %s OR si_filter.color_snapshot LIKE %s)")
            params.extend([like, like, like, like, like])
        where_sql = " AND ".join(where)
        total_rows = self.query(
            f"SELECT COUNT(DISTINCT s.id) AS total FROM sales_order s {join_items} WHERE {where_sql}",
            params,
        )
        total = int(total_rows[0].get("total") or 0) if total_rows else 0
        sales_rows = self.query(
            f"""
            SELECT DISTINCT s.*,
                   wu.display_name AS created_by_name,
                   wu.username AS created_by_username,
                   cu.display_name AS canceled_by_name,
                   cu.username AS canceled_by_username,
                   du.display_name AS deleted_by_name,
                   du.username AS deleted_by_username
            FROM sales_order s
            LEFT JOIN auth_user wu ON wu.id=s.created_by_user_id
            LEFT JOIN auth_user cu ON cu.id=s.canceled_by_user_id
            LEFT JOIN auth_user du ON du.id=s.deleted_by_user_id
            {join_items}
            WHERE {where_sql}
            ORDER BY s.sales_at DESC, s.id DESC
            LIMIT %s OFFSET %s
            """,
            params + [page_size, (page - 1) * page_size],
        )
        ids = [int(row["id"]) for row in sales_rows if row.get("id")]
        items_by_sales: dict[int, list[dict]] = {sid: [] for sid in ids}
        if ids:
            placeholders = ",".join(["%s"] * len(ids))
            item_rows = self.query(
                f"""
                SELECT i.*, w.name AS warehouse_name, s.main_image_url
                FROM sales_order_item i
                LEFT JOIN warehouse w ON w.id=i.warehouse_id
                LEFT JOIN product_sku s ON s.id=i.sku_id
                WHERE i.sales_order_id IN ({placeholders})
                ORDER BY i.sales_order_id ASC, i.line_no ASC
                """,
                ids,
            )
            for item in item_rows:
                sid = int(item.get("sales_order_id") or 0)
                items_by_sales.setdefault(sid, []).append({
                    "product_id": item.get("sku_id"),
                    "title": item.get("title_snapshot") or "商品",
                    "spec": item.get("color_snapshot") or "",
                    "quantity": _qty_text(item.get("quantity")),
                    "price": _money(item.get("unit_price")),
                    "total_price": _money(item.get("amount")),
                    "warehouse_id": item.get("warehouse_id"),
                    "warehouse_name": item.get("warehouse_name") or "",
                    "image": item.get("main_image_url") or "",
                })
        cards = []
        for row in sales_rows:
            sid = int(row.get("id") or 0)
            products = items_by_sales.get(sid, [])
            cards.append({
                "id": sid,
                "sales_no": row.get("sales_no") or str(sid),
                "customer_id": row.get("customer_id"),
                "customer_name": row.get("customer_name_snapshot") or "客户未识别",
                "status": row.get("status"),
                "status_text": self._sales_status_text(row.get("status") or ""),
                "pay_type": row.get("pay_type") or "",
                "pay_type_text": _pay_type_text(row.get("pay_type")),
                "pay_status": row.get("pay_status") or "",
                "pay_status_text": _pay_status_text(row.get("pay_status")),
                "total_price": _money(row.get("receivable_amount") or row.get("goods_amount")),
                "goods_amount": _money(row.get("goods_amount")),
                "receivable_amount": _money(row.get("receivable_amount")),
                "buy_number_count": _qty_text(row.get("total_quantity")),
                "total_quantity": _qty_text(row.get("total_quantity")),
                "date_text": _date_text(row.get("sales_at")),
                "sales_at": str(row.get("sales_at") or ""),
                "created_at": str(row.get("created_at") or ""),
                "updated_at": str(row.get("updated_at") or ""),
                "canceled_at": str(row.get("canceled_at") or ""),
                "cancel_reason": row.get("cancel_reason") or "",
                "created_by_user_id": row.get("created_by_user_id"),
                "created_by_name": row.get("created_by_name") or row.get("created_by_username") or "",
                "canceled_by_user_id": row.get("canceled_by_user_id"),
                "canceled_by_name": row.get("canceled_by_name") or row.get("canceled_by_username") or "",
                "deleted_at": str(row.get("deleted_at") or ""),
                "delete_reason": row.get("delete_reason") or "",
                "deleted_by_user_id": row.get("deleted_by_user_id"),
                "deleted_by_name": row.get("deleted_by_name") or row.get("deleted_by_username") or "",
                "source": row.get("source") or "",
                "product_summary": self._first_product_line(products),
                "products": products,
                "note": row.get("note") or "",
            })
        return cards, total

    def sales_detail(self, sales_id: int) -> dict:
        self._ensure_operator_columns()
        self._ensure_sales_delete_columns()
        rows = self.query(
            """
            SELECT s.*,
                   wu.display_name AS created_by_name,
                   wu.username AS created_by_username,
                   cu.display_name AS canceled_by_name,
                   cu.username AS canceled_by_username,
                   du.display_name AS deleted_by_name,
                   du.username AS deleted_by_username
            FROM sales_order s
            LEFT JOIN auth_user wu ON wu.id=s.created_by_user_id
            LEFT JOIN auth_user cu ON cu.id=s.canceled_by_user_id
            LEFT JOIN auth_user du ON du.id=s.deleted_by_user_id
            WHERE s.id=%s
            LIMIT 1
            """,
            (sales_id,),
        )
        if not rows:
            return {"code": 404, "msg": "销售单不存在"}
        sale = rows[0]
        item_rows = self.query(
            """
            SELECT i.*, w.name AS warehouse_name, s.main_image_url
            FROM sales_order_item i
            LEFT JOIN warehouse w ON w.id=i.warehouse_id
            LEFT JOIN product_sku s ON s.id=i.sku_id
            WHERE i.sales_order_id=%s
            ORDER BY i.line_no ASC
            """,
            (sales_id,),
        )
        detail = [
            {
                "product_id": item.get("sku_id"),
                "title": item.get("title_snapshot") or "商品",
                "spec": item.get("color_snapshot") or "",
                "buy_number": _qty_text(item.get("quantity")),
                "quantity": _qty_text(item.get("quantity")),
                "price": _money(item.get("unit_price")),
                "total_price": _money(item.get("amount")),
                "warehouse_id": item.get("warehouse_id"),
                "warehouse_name": item.get("warehouse_name") or "",
                "images": item.get("main_image_url") or "",
            }
            for item in item_rows
        ]
        ledger_rows = self.query(
            """
            SELECT l.id, l.ledger_no, l.biz_type, l.change_qty, l.before_qty, l.after_qty,
                   l.note, l.occurred_at, w.name AS warehouse_name,
                   wu.display_name AS operator_name, wu.username AS operator_username
            FROM inventory_ledger l
            LEFT JOIN warehouse w ON w.id=l.warehouse_id
            LEFT JOIN auth_user wu ON wu.id=l.operator_user_id
            WHERE l.biz_id=%s AND l.biz_type IN ('sales_out', 'sales_cancel', 'sales_delete')
            ORDER BY l.occurred_at ASC, l.id ASC
            """,
            (sales_id,),
        )
        ledgers = [
            {
                "id": row.get("id"),
                "ledger_no": row.get("ledger_no") or "",
                "biz_type": row.get("biz_type") or "",
                "biz_type_text": "销售出库" if row.get("biz_type") == "sales_out" else "删除回滚",
                "change_qty": _qty_text(row.get("change_qty")),
                "before_qty": _qty_text(row.get("before_qty")),
                "after_qty": _qty_text(row.get("after_qty")),
                "warehouse_name": row.get("warehouse_name") or "",
                "operator_name": row.get("operator_name") or row.get("operator_username") or "",
                "note": row.get("note") or "",
                "occurred_at": str(row.get("occurred_at") or ""),
            }
            for row in ledger_rows
        ]
        return {
            "code": 0,
            "data": {
                "id": sale.get("id"),
                "sales_id": sale.get("id"),
                "sales_no": sale.get("sales_no"),
                "customer_id": sale.get("customer_id"),
                "customer_name": sale.get("customer_name_snapshot"),
                "status": sale.get("status"),
                "status_text": self._sales_status_text(sale.get("status") or ""),
                "pay_type": sale.get("pay_type"),
                "pay_type_text": _pay_type_text(sale.get("pay_type")),
                "pay_status": sale.get("pay_status"),
                "pay_status_text": _pay_status_text(sale.get("pay_status")),
                "total_price": _money(sale.get("receivable_amount") or sale.get("goods_amount")),
                "goods_amount": _money(sale.get("goods_amount")),
                "receivable_amount": _money(sale.get("receivable_amount")),
                "buy_number_count": _qty_text(sale.get("total_quantity")),
                "total_quantity": _qty_text(sale.get("total_quantity")),
                "sales_at": str(sale.get("sales_at") or ""),
                "date_text": _date_text(sale.get("sales_at")),
                "created_at": str(sale.get("created_at") or ""),
                "updated_at": str(sale.get("updated_at") or ""),
                "canceled_at": str(sale.get("canceled_at") or ""),
                "cancel_reason": sale.get("cancel_reason") or "",
                "created_by_user_id": sale.get("created_by_user_id"),
                "created_by_name": sale.get("created_by_name") or sale.get("created_by_username") or "",
                "canceled_by_user_id": sale.get("canceled_by_user_id"),
                "canceled_by_name": sale.get("canceled_by_name") or sale.get("canceled_by_username") or "",
                "deleted_at": str(sale.get("deleted_at") or ""),
                "delete_reason": sale.get("delete_reason") or "",
                "deleted_by_user_id": sale.get("deleted_by_user_id"),
                "deleted_by_name": sale.get("deleted_by_name") or sale.get("deleted_by_username") or "",
                "source": sale.get("source") or "",
                "detail": detail,
                "products": detail,
                "items": detail,
                "inventory_ledgers": ledgers,
                "note": sale.get("note") or "",
            },
        }

    def _print_template_row_to_dict(self, row: dict) -> dict:
        if not row:
            return {}
        return {
            "id": row.get("id"),
            "template_key": row.get("template_key") or "sales_order_default",
            "document_type": row.get("document_type") or "sales_order",
            "name": row.get("name") or "默认销售单模板",
            "paper_size": row.get("paper_size") or "A5",
            "orientation": row.get("orientation") or "landscape",
            "font_size": int(row.get("font_size") or 12),
            "copies": int(row.get("copies") or 1),
            "show_logo": int(row.get("show_logo") or 0),
            "show_operator": int(row.get("show_operator") or 0),
            "show_customer_phone": int(row.get("show_customer_phone") or 0),
            "show_payment": int(row.get("show_payment") or 0),
            "show_note": int(row.get("show_note") or 0),
            "header_text": row.get("header_text") or "肆计包装销售单",
            "footer_text": row.get("footer_text") or "",
            "custom_css": row.get("custom_css") or "",
            "is_default": int(row.get("is_default") or 0),
            "is_enabled": int(row.get("is_enabled") or 0),
            "updated_at": str(row.get("updated_at") or ""),
        }

    def _default_sales_print_template(self) -> dict:
        self._ensure_print_tables()
        rows = self.query(
            """
            SELECT *
            FROM print_template
            WHERE document_type='sales_order' AND is_enabled=1
            ORDER BY is_default DESC, id ASC
            LIMIT 1
            """
        )
        if not rows:
            self.__class__._print_tables_ready = False
            self._ensure_print_tables()
            rows = self.query(
                "SELECT * FROM print_template WHERE template_key='sales_order_default' LIMIT 1"
            )
        return self._print_template_row_to_dict(rows[0] if rows else {})

    def sales_print_settings(self) -> dict:
        template = self._default_sales_print_template()
        latest_rows = self.query(
            """
            SELECT id, sales_no
            FROM sales_order
            WHERE status NOT IN ('canceled', 'deleted')
            ORDER BY sales_at DESC, id DESC
            LIMIT 1
            """
        )
        latest = latest_rows[0] if latest_rows else {}
        template["latest_sales_id"] = latest.get("id") or 0
        template["latest_sales_no"] = latest.get("sales_no") or ""
        template["latest_print_url"] = (
            f"/api/sales/{int(latest.get('id'))}/print-html?auto=0"
            if latest.get("id")
            else ""
        )
        return {"code": 0, "data": template}

    def _default_system_setting(self, key: str) -> dict:
        defaults = {
            "product_basic": {
                "categories": [
                    {"key": "gift_box", "name": "礼盒", "is_stock_item": 1},
                    {"key": "bag", "name": "泡袋", "is_stock_item": 0},
                    {"key": "accessory", "name": "辅料", "is_stock_item": 0},
                    {"key": "carton", "name": "快递纸箱", "is_stock_item": 0},
                    {"key": "pvc_gift_box", "name": "PVC礼盒", "is_stock_item": 0},
                    {"key": "other", "name": "其他", "is_stock_item": 1},
                ],
                "units": ["套", "捆", "个", "张", "斤"],
                "bag_types": ["长泡袋", "短泡袋", "红茶袋", "宽版", "空白"],
                "default_case_pack_qty": "",
                "default_unit": "套",
                "default_is_stock_item": 1,
            },
            "inventory_rules": {
                "stock_category_keywords": ["礼盒"],
                "non_stock_category_keywords": list(FIXED_NON_STOCK_CATEGORY_KEYWORDS),
                "default_out_warehouse_id": 1,
                "allow_negative_stock": 0,
            },
            "payment_rules": {
                "payment_statuses": ["已付", "月结", "未付"],
                "paid_methods": ["微信", "现金", "余额", "转账", "支付宝"],
                "default_payment_status": "已付",
                "default_paid_method": "微信",
                "balance_adjust_reasons": ["手动调整", "客户充值", "售后退回", "对账修正"],
                "monthly_customer_rule": "客户选择月结时销售单计入欠款，结款后改为已付。",
            },
            "image_rules": {
                "oss_path": "products/{yyyy}/{mm}/",
                "thumbnail_rule": "image/resize,w_240/quality,q_80",
                "asset_category_rule": "按商品 SPU + 大分类归档，未绑定图片单独展示。",
                "pending_cleanup_days": 30,
                "auto_compress": 1,
            },
            "permission_rules": {
                "roles": ["管理员", "员工", "客户", "访客"],
                "permissions": {
                    "管理员": ["开单", "删单", "打印", "查看库存", "调库存", "盘点", "调拨", "调余额", "图片上传", "图片绑定", "设置", "查看"],
                    "员工": ["开单", "打印", "查看库存", "图片上传", "图片绑定", "查看"],
                    "客户": ["查看"],
                    "访客": [],
                },
                "miniapp_can_create_sales": ["管理员", "员工"],
            },
            "miniapp_design": {
                "version": 1,
                "home": {
                    "title": "肆计包装",
                    "subtitle": "茶包装产品展示",
                    "modules": [
                        {
                            "id": "banner_default",
                            "type": "banner",
                            "enabled": 1,
                            "title": "首页轮播",
                            "items": [
                                {
                                    "title": "肆计包装",
                                    "image": "",
                                    "url": "/pages/goods-category/goods-category",
                                }
                            ],
                        },
                        {
                            "id": "nav_default",
                            "type": "nav",
                            "enabled": 1,
                            "title": "快捷导航",
                            "items": [
                                {"title": "半斤礼盒", "url": "/pages/goods-search/goods-search?keywords=半斤礼盒"},
                                {"title": "三两礼盒", "url": "/pages/goods-search/goods-search?keywords=三两礼盒"},
                                {"title": "泡袋", "url": "/pages/goods-search/goods-search?keywords=泡袋"},
                                {"title": "订单", "url": "/pages/order/order"},
                            ],
                        },
                        {
                            "id": "products_default",
                            "type": "product_shelf",
                            "enabled": 1,
                            "title": "推荐产品",
                            "keywords": "",
                            "category_id": "",
                            "limit": 8,
                        },
                    ],
                },
                "tabbar": {
                    "style": {
                        "color": "#606266",
                        "selected_color": "#2a94ff",
                        "background_color": "#ffffff",
                        "border_style": "black",
                    },
                    "items": [
                        {
                            "text": "首页",
                            "page_path": "/pages/index/index",
                            "icon": "static/images/common/tabbar/home.png",
                            "selected_icon": "static/images/black/tabbar/home.png",
                            "enabled": 1,
                        },
                        {
                            "text": "分类",
                            "page_path": "/pages/goods-category/goods-category",
                            "icon": "static/images/common/tabbar/category.png",
                            "selected_icon": "static/images/black/tabbar/category.png",
                            "enabled": 1,
                        },
                        {
                            "text": "订单",
                            "page_path": "/pages/order/order",
                            "icon": "static/images/common/tabbar/cart.png",
                            "selected_icon": "static/images/black/tabbar/cart.png",
                            "enabled": 1,
                        },
                        {
                            "text": "我的",
                            "page_path": "/pages/user/user",
                            "icon": "static/images/common/tabbar/user.png",
                            "selected_icon": "static/images/black/tabbar/user.png",
                            "enabled": 1,
                        },
                    ],
                },
            },
        }
        return json.loads(json.dumps(defaults.get(key, {}), ensure_ascii=False))

    def _miniapp_design_text(self, value: Any, limit: int = 80) -> str:
        text = str(value or "").strip()
        if len(text) > limit:
            text = text[:limit]
        return text

    def _miniapp_design_link(self, value: Any) -> str:
        url = str(value or "").strip()
        if not url or url == "#":
            return ""
        allowed_prefixes = (
            "/pages/index/index",
            "/pages/goods-category/goods-category",
            "/pages/order/order",
            "/pages/user/user",
            "/pages/goods-search/goods-search",
        )
        return url if any(url.startswith(prefix) for prefix in allowed_prefixes) else ""

    def _miniapp_design_style(self, value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            return {}
        clean: dict[str, Any] = {}
        for field in ("background", "primary"):
            if field in value:
                clean[field] = self._miniapp_design_text(value.get(field), 40)
        for field, max_value in {"margin_top": 80, "margin_bottom": 80, "radius": 40}.items():
            if field not in value:
                continue
            try:
                clean[field] = min(max(int(value.get(field) or 0), 0), max_value)
            except Exception:
                clean[field] = 0
        return clean

    def _miniapp_tabbar_setting(self, value: Any, default: dict[str, Any]) -> dict[str, Any]:
        clean = json.loads(json.dumps(default or {}, ensure_ascii=False))
        if not isinstance(value, dict):
            return clean
        style = value.get("style")
        if isinstance(style, dict):
            clean_style = dict(clean.get("style") or {})
            for field in ("color", "selected_color", "background_color"):
                if field in style:
                    clean_style[field] = self._miniapp_design_text(style.get(field), 40)
            border_style = str(style.get("border_style") or clean_style.get("border_style") or "black").strip().lower()
            clean_style["border_style"] = border_style if border_style in {"black", "white"} else "black"
            clean["style"] = clean_style
        allowed_pages = {
            "/pages/index/index",
            "/pages/goods-category/goods-category",
            "/pages/order/order",
            "/pages/user/user",
        }
        items = value.get("items")
        if not isinstance(items, list):
            return clean
        clean_items: list[dict[str, Any]] = []
        for item in items[:4]:
            if not isinstance(item, dict):
                continue
            page_path = self._miniapp_design_link(item.get("page_path") or item.get("url"))
            if page_path not in allowed_pages:
                continue
            clean_items.append({
                "text": self._miniapp_design_text(item.get("text") or item.get("title"), 8),
                "page_path": page_path,
                "icon": self._miniapp_design_text(item.get("icon"), 500),
                "selected_icon": self._miniapp_design_text(item.get("selected_icon"), 500),
                "enabled": 1 if int(item.get("enabled") or 0) else 0,
            })
        if clean_items:
            clean["items"] = clean_items
        return clean

    def _sanitize_miniapp_design_setting(self, value: dict) -> dict:
        default = self._default_system_setting("miniapp_design")
        clean = json.loads(json.dumps(default, ensure_ascii=False))
        home = value.get("home") if isinstance(value, dict) else {}
        if not isinstance(home, dict):
            home = {}
        clean["version"] = 1
        clean["home"]["title"] = self._miniapp_design_text(home.get("title") or clean["home"].get("title"), 40)
        clean["home"]["subtitle"] = self._miniapp_design_text(home.get("subtitle") or clean["home"].get("subtitle"), 80)
        home_style = self._miniapp_design_style(home.get("style"))
        if home_style:
            clean["home"]["style"] = home_style
        clean["tabbar"] = self._miniapp_tabbar_setting(
            value.get("tabbar") if isinstance(value, dict) else None,
            clean.get("tabbar") or {},
        )
        modules = home.get("modules")
        if not isinstance(modules, list):
            modules = clean["home"].get("modules") or []
        allowed_types = {
            "banner",
            "nav",
            "image",
            "hot_zone",
            "product_shelf",
            "search",
            "notice",
            "title",
            "rich_text",
            "video",
            "row_line",
            "blank",
            "goods_magic",
            "goods_tabs",
            "coupon",
            "seckill",
            "activity",
            "tabs",
            "tabs_carousel",
            "data_magic",
            "data_tabs",
            "float_window",
        }
        clean_modules: list[dict[str, Any]] = []
        for index, module in enumerate(modules[:30]):
            if not isinstance(module, dict):
                continue
            module_type = str(module.get("type") or "").strip()
            if module_type not in allowed_types:
                continue
            clean_module: dict[str, Any] = {
                "id": self._miniapp_design_text(module.get("id") or f"{module_type}_{index + 1}", 50),
                "type": module_type,
                "enabled": 1 if int(module.get("enabled") or 0) else 0,
                "title": self._miniapp_design_text(module.get("title"), 60),
            }
            module_style = self._miniapp_design_style(module.get("style"))
            if module_style:
                clean_module["style"] = module_style
            if module_type in {"banner", "nav", "image", "hot_zone", "video"}:
                items = module.get("items")
                if not isinstance(items, list):
                    items = []
                clean_items: list[dict[str, str]] = []
                for item in items[:20]:
                    if not isinstance(item, dict):
                        continue
                    clean_items.append({
                        "title": self._miniapp_design_text(item.get("title"), 60),
                        "image": self._miniapp_design_text(item.get("image"), 500),
                        "url": self._miniapp_design_link(item.get("url")),
                    })
                clean_module["items"] = clean_items
            if module_type == "product_shelf":
                try:
                    limit = int(module.get("limit") or 8)
                except Exception:
                    limit = 8
                clean_module["keywords"] = self._miniapp_design_text(module.get("keywords"), 80)
                clean_module["category_id"] = self._miniapp_design_text(module.get("category_id"), 20)
                clean_module["limit"] = min(max(limit, 1), 30)
            for field, limit in {"placeholder": 80, "content": 500, "subtitle": 80}.items():
                if field in module:
                    clean_module[field] = self._miniapp_design_text(module.get(field), limit)
            if "height" in module:
                try:
                    clean_module["height"] = min(max(int(module.get("height") or 0), 0), 200)
                except Exception:
                    clean_module["height"] = 0
            clean_modules.append(clean_module)
        if clean_modules:
            clean["home"]["modules"] = clean_modules
        return clean

    def _system_setting_value(self, cursor, key: str) -> dict:
        self._ensure_system_settings_tables()
        cursor.execute(
            "SELECT setting_value FROM system_setting WHERE setting_key=%s LIMIT 1",
            (key,),
        )
        row = cursor.fetchone()
        default = self._default_system_setting(key)
        if not row:
            return default
        value = _json_loads(row.get("setting_value"), {})
        if not isinstance(value, dict):
            value = {}
        merged = default.copy()
        merged.update(value)
        return merged

    def system_setting(self, key: str) -> dict:
        allowed = {"product_basic", "inventory_rules", "payment_rules", "image_rules", "permission_rules", "miniapp_design"}
        if key not in allowed:
            return {"code": 400, "msg": "设置项不存在"}
        with self.cursor() as cursor:
            if key == "inventory_rules":
                self._sync_inventory_policy_categories(cursor)
            data = self._system_setting_value(cursor, key)
            extras: dict[str, Any] = {}
            if key in {"product_basic", "inventory_rules"}:
                extras["categories"] = self.product_categories()
                extras["units"] = self.query("SELECT id, name, code FROM product_unit WHERE is_enabled=1 ORDER BY id ASC")
            if key == "inventory_rules":
                extras["warehouses"] = self.warehouse_list()
            if key == "image_rules":
                rows = self.product_media_assets(include_pending=True, limit=6000)
                extras["media_summary"] = {
                    "total": len(rows),
                    "pending": sum(1 for row in rows if row.get("media_type") == "pending"),
                    "main": sum(1 for row in rows if row.get("media_type") == "main_image"),
                    "detail": sum(1 for row in rows if row.get("media_type") == "detail_image"),
                    "color": sum(1 for row in rows if row.get("media_type") == "color_image"),
                }
        return {"code": 0, "data": {"key": key, "value": data, **extras}}

    def save_system_setting(self, key: str, payload: dict, operator_user_id: Any = None) -> dict:
        allowed = {"product_basic", "inventory_rules", "payment_rules", "image_rules", "permission_rules", "miniapp_design"}
        if key not in allowed:
            return {"code": 400, "msg": "设置项不存在"}
        self._ensure_system_settings_tables()
        operator_user_id = self._operator_user_id(operator_user_id)
        payload = payload or {}
        value = payload.get("value") if isinstance(payload.get("value"), dict) else payload
        default = self._default_system_setting(key)
        clean_value = default.copy()
        clean_value.update(value if isinstance(value, dict) else {})
        if key == "permission_rules":
            clean_value = default
        if key == "miniapp_design":
            clean_value = self._sanitize_miniapp_design_setting(clean_value)
        if key == "product_basic":
            categories = clean_value.get("categories")
            if isinstance(categories, list):
                for category in categories:
                    if not isinstance(category, dict):
                        continue
                    name = str(category.get("name") or category.get("key") or "")
                    category_type = str(category.get("product_type") or category.get("key") or "").lower()
                    if category_type == "bag" or "泡袋" in name or "茶袋" in name:
                        category["is_stock_item"] = 0
        if key == "inventory_rules":
            keywords = clean_value.get("non_stock_category_keywords")
            if not isinstance(keywords, list):
                keywords = []
            clean_value["non_stock_category_keywords"] = [
                str(item).strip() for item in keywords if str(item or "").strip()
            ]
            stock_keywords = clean_value.get("stock_category_keywords")
            if isinstance(stock_keywords, list):
                clean_value["stock_category_keywords"] = [
                    str(item).strip() for item in stock_keywords if str(item or "").strip()
                ]
        now = _now()
        with self.transaction() as cursor:
            cursor.execute("SELECT setting_value FROM system_setting WHERE setting_key=%s LIMIT 1 FOR UPDATE", (key,))
            row = cursor.fetchone()
            old_value = row.get("setting_value") if row else None
            encoded = _json_dumps(clean_value)
            if row:
                cursor.execute(
                    """
                    UPDATE system_setting
                    SET setting_value=%s, updated_by_user_id=%s, updated_at=%s
                    WHERE setting_key=%s
                    """,
                    (encoded, operator_user_id, now, key),
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO system_setting
                        (setting_key, setting_value, note, updated_by_user_id, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (key, encoded, key, operator_user_id, now, now),
                )
            cursor.execute(
                """
                INSERT INTO system_setting_log
                    (setting_key, old_value, new_value, changed_by_user_id, created_at)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (key, old_value, encoded, operator_user_id, now),
            )
            if key == "inventory_rules":
                self._apply_inventory_rule_keywords_to_categories(cursor, clean_value)
                self._sync_inventory_policy_categories(cursor)
        return self.system_setting(key)

    def _sku_sequence_usage(self, cursor, row: dict) -> dict:
        prefix = re.sub(r"[^0-9A-Za-z]", "", str(row.get("prefix") or "SJ")).upper()[:20] or "SJ"
        pad_width = int(row.get("pad_width") or 4)
        start_number = max(int(row.get("start_number") or 1001), 1)
        next_number = max(int(row.get("next_number") or start_number), 1)
        configured_start = max(start_number, next_number)
        skipped_numbers = self._sequence_skip_numbers(row.get("skipped_numbers"))
        cursor.execute(
            "SELECT sku_no FROM product_sku WHERE sku_no LIKE %s",
            (f"{prefix}%",),
        )
        used_codes = [str(item.get("sku_no") or "").strip().upper() for item in cursor.fetchall()]
        pattern = re.compile(rf"^{re.escape(prefix)}(\d+)$", re.I)
        used_numbers: list[int] = []
        for code in used_codes:
            match = pattern.fullmatch(code)
            if match:
                used_numbers.append(int(match.group(1)))
        next_code = self._next_sequence_code(
            cursor,
            prefix=prefix,
            start_number=configured_start,
            pad_width=pad_width,
            skipped_numbers=skipped_numbers,
        )
        min_number = min(used_numbers) if used_numbers else None
        max_number = max(used_numbers) if used_numbers else None
        return {
            "prefix": prefix,
            "start_number": start_number,
            "next_number": next_number,
            "pad_width": pad_width,
            "next_code": next_code,
            "skipped_numbers": sorted(skipped_numbers),
            "used_count": len(used_codes),
            "numeric_used_count": len(used_numbers),
            "used_min_code": self._sequence_code(prefix, min_number, pad_width) if min_number else "",
            "used_max_code": self._sequence_code(prefix, max_number, pad_width) if max_number else "",
        }

    def sku_number_settings(self) -> dict:
        self._ensure_number_sequence_tables()
        with self.cursor() as cursor:
            row = self._sku_sequence_row(cursor)
            usage = self._sku_sequence_usage(cursor, row)
            cursor.execute("SELECT COUNT(*) AS total FROM product_sku")
            total_row = cursor.fetchone() or {}
            change_logs: list[dict] = []
            cursor.execute(
                """
                SELECT id, old_prefix, old_next_number, old_pad_width,
                       new_prefix, new_next_number, new_pad_width,
                       note, changed_by_user_id, created_at
                FROM number_sequence_log
                WHERE sequence_key='product_sku'
                ORDER BY created_at DESC, id DESC
                LIMIT 8
                """
            )
            for log in cursor.fetchall():
                change_logs.append({
                    "id": int(log.get("id") or 0),
                    "old_code": self._sequence_code(log.get("old_prefix") or "SJ", log.get("old_next_number") or 1, log.get("old_pad_width") or 4),
                    "new_code": self._sequence_code(log.get("new_prefix") or "SJ", log.get("new_next_number") or 1, log.get("new_pad_width") or 4),
                    "note": _clean_number_sequence_note(log.get("note")),
                    "operator_user_id": log.get("changed_by_user_id"),
                    "created_at": str(log.get("created_at") or ""),
                })

            recode_batches: list[dict] = []
            if self._table_exists(cursor, "product_sku_recode_log"):
                cursor.execute(
                    """
                    SELECT batch_no, COUNT(*) AS changed_count,
                           MIN(new_sku_no) AS first_new_code,
                           MAX(new_sku_no) AS last_new_code,
                           MIN(changed_at) AS started_at,
                           MAX(changed_at) AS finished_at
                    FROM product_sku_recode_log
                    GROUP BY batch_no
                    ORDER BY MAX(changed_at) DESC
                    LIMIT 8
                    """
                )
                for item in cursor.fetchall():
                    recode_batches.append({
                        "batch_no": item.get("batch_no") or "",
                        "changed_count": int(item.get("changed_count") or 0),
                        "first_new_code": item.get("first_new_code") or "",
                        "last_new_code": item.get("last_new_code") or "",
                        "started_at": str(item.get("started_at") or ""),
                        "finished_at": str(item.get("finished_at") or ""),
                    })

        data = {
            "sequence_key": "product_sku",
            "prefix": usage["prefix"],
            "start_number": usage["start_number"],
            "next_number": usage["next_number"],
            "pad_width": usage["pad_width"],
            "next_code": usage["next_code"],
            "start_code": self._sequence_code(usage["prefix"], usage["start_number"], usage["pad_width"]),
            "configured_code": self._sequence_code(usage["prefix"], usage["next_number"], usage["pad_width"]),
            "skipped_numbers": usage["skipped_numbers"],
            "skipped_numbers_text": "、".join(self._sequence_code(usage["prefix"], item, usage["pad_width"]) for item in usage["skipped_numbers"]),
            "used_count": usage["used_count"],
            "numeric_used_count": usage["numeric_used_count"],
            "used_min_code": usage["used_min_code"],
            "used_max_code": usage["used_max_code"],
            "total_sku_count": int(total_row.get("total") or 0),
            "note": _clean_number_sequence_note(row.get("note")),
            "updated_at": str(row.get("updated_at") or ""),
            "change_logs": change_logs,
            "recode_batches": recode_batches,
        }
        return {"code": 0, "data": data}

    def save_sku_number_settings(self, payload: dict, operator_user_id: Any = None) -> dict:
        self._ensure_number_sequence_tables()
        payload = payload or {}
        raw_prefix = str(payload.get("prefix") or "").strip()
        raw_next_code = str(payload.get("next_code") or payload.get("configured_code") or "").strip()
        raw_start_number = payload.get("start_number")
        raw_next_number = payload.get("next_number")
        raw_pad_width = payload.get("pad_width")

        code_match = re.fullmatch(r"\s*([A-Za-z]{1,20})(\d{1,10})\s*", raw_next_code) if raw_next_code else None
        if code_match:
            prefix = (raw_prefix or code_match.group(1)).upper()
            next_number = int(code_match.group(2))
            pad_width = max(len(code_match.group(2)), 1)
        elif raw_next_code and raw_next_code.isdigit():
            prefix = (raw_prefix or "SJ").upper()
            next_number = int(raw_next_code)
            pad_width = max(len(raw_next_code), 1)
        else:
            prefix = (raw_prefix or "SJ").upper()
            try:
                next_number = int(raw_next_number or 1001)
            except (TypeError, ValueError):
                raise DBError("下一个编号必须是数字，或填写类似 SJ1570")
            try:
                pad_width = int(raw_pad_width or 4)
            except (TypeError, ValueError):
                pad_width = 4

        prefix = re.sub(r"[^0-9A-Za-z]", "", prefix).upper()[:20] or "SJ"
        try:
            start_number = int(raw_start_number or 1001)
        except (TypeError, ValueError):
            start_number = 1001
        start_number = max(start_number, 1)
        next_number = max(next_number, 1)
        pad_width = max(1, min(pad_width, 10))
        if raw_pad_width not in (None, ""):
            try:
                pad_width = max(1, min(int(raw_pad_width), 10))
            except (TypeError, ValueError):
                pass
        note = _clean_number_sequence_note(payload.get("note"))[:255]
        skipped_numbers = sorted(self._sequence_skip_numbers(payload.get("skipped_numbers") or payload.get("skip_numbers") or ""))
        skipped_json = _json_dumps(skipped_numbers)
        operator_user_id = self._operator_user_id(operator_user_id)
        now = _now()
        with self.transaction() as cursor:
            old = self._sku_sequence_row(cursor, lock=True)
            changed = (
                str(old.get("prefix") or "SJ").upper() != prefix
                or int(old.get("start_number") or 1001) != start_number
                or int(old.get("next_number") or 1) != next_number
                or int(old.get("pad_width") or 4) != pad_width
                or sorted(self._sequence_skip_numbers(old.get("skipped_numbers"))) != skipped_numbers
                or str(old.get("note") or "") != note
            )
            cursor.execute(
                """
                UPDATE number_sequence_setting
                SET prefix=%s, start_number=%s, next_number=%s, pad_width=%s, skipped_numbers=%s, note=%s,
                    updated_by_user_id=%s, updated_at=%s
                WHERE sequence_key='product_sku'
                """,
                (prefix, start_number, next_number, pad_width, skipped_json, note, operator_user_id, now),
            )
            if changed:
                cursor.execute(
                    """
                    INSERT INTO number_sequence_log
                        (sequence_key, old_prefix, old_start_number, old_next_number, old_pad_width, old_skipped_numbers,
                         new_prefix, new_start_number, new_next_number, new_pad_width, new_skipped_numbers,
                         note, changed_by_user_id, created_at)
                    VALUES ('product_sku', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        old.get("prefix") or "SJ",
                        int(old.get("start_number") or 1001),
                        int(old.get("next_number") or 1),
                        int(old.get("pad_width") or 4),
                        old.get("skipped_numbers") or "[]",
                        prefix,
                        start_number,
                        next_number,
                        pad_width,
                        skipped_json,
                        note,
                        operator_user_id,
                        now,
                    ),
                )
        return self.sku_number_settings()

    def save_sales_print_settings(self, payload: dict, operator_user_id: Any = None) -> dict:
        self._ensure_print_tables()
        payload = payload or {}
        operator_user_id = self._operator_user_id(operator_user_id)

        def clean_text(name: str, default: str, limit: int) -> str:
            text = str(payload.get(name, default) or "").strip()
            return text[:limit]

        paper_size = str(payload.get("paper_size") or "A4").strip().upper()
        if paper_size not in {"A4", "A5", "80MM"}:
            paper_size = "A4"
        if paper_size == "80MM":
            paper_size = "80mm"
        orientation = str(payload.get("orientation") or "landscape").strip()
        if orientation not in {"portrait", "landscape"}:
            orientation = "landscape"
        try:
            font_size = int(payload.get("font_size") or 12)
        except (TypeError, ValueError):
            font_size = 12
        font_size = max(10, min(font_size, 18))
        try:
            copies = int(payload.get("copies") or 1)
        except (TypeError, ValueError):
            copies = 1
        copies = max(1, min(copies, 5))
        bool_fields = {
            "show_logo": 1 if payload.get("show_logo") in (1, "1", True, "true", "on") else 0,
            "show_operator": 1 if payload.get("show_operator") in (1, "1", True, "true", "on") else 0,
            "show_customer_phone": 1 if payload.get("show_customer_phone") in (1, "1", True, "true", "on") else 0,
            "show_payment": 1 if payload.get("show_payment") in (1, "1", True, "true", "on") else 0,
            "show_note": 1 if payload.get("show_note") in (1, "1", True, "true", "on") else 0,
        }
        name = clean_text("name", "默认销售单模板", 120) or "默认销售单模板"
        header_text = clean_text("header_text", "肆计包装销售单", 200) or "肆计包装销售单"
        footer_text = clean_text("footer_text", "", 500)
        custom_css = str(payload.get("custom_css") or "")[:5000]
        now = _now()
        with self.transaction() as cursor:
            cursor.execute(
                "SELECT id FROM print_template WHERE template_key='sales_order_default' LIMIT 1 FOR UPDATE"
            )
            row = cursor.fetchone()
            if row:
                cursor.execute(
                    """
                    UPDATE print_template
                    SET name=%s, paper_size=%s, orientation=%s, font_size=%s, copies=%s,
                        show_logo=%s, show_operator=%s, show_customer_phone=%s, show_payment=%s,
                        show_note=%s, header_text=%s, footer_text=%s, custom_css=%s,
                        is_default=1, is_enabled=1, updated_by_user_id=%s, updated_at=%s
                    WHERE id=%s
                    """,
                    (
                        name,
                        paper_size,
                        orientation,
                        font_size,
                        copies,
                        bool_fields["show_logo"],
                        bool_fields["show_operator"],
                        bool_fields["show_customer_phone"],
                        bool_fields["show_payment"],
                        bool_fields["show_note"],
                        header_text,
                        footer_text,
                        custom_css,
                        operator_user_id,
                        now,
                        row.get("id"),
                    ),
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO print_template
                        (template_key, document_type, name, paper_size, orientation, font_size, copies,
                         show_logo, show_operator, show_customer_phone, show_payment, show_note,
                         header_text, footer_text, custom_css, is_default, is_enabled,
                         created_by_user_id, updated_by_user_id, created_at, updated_at)
                    VALUES
                        ('sales_order_default', 'sales_order', %s, %s, %s, %s, %s,
                         %s, %s, %s, %s, %s, %s, %s, %s, 1, 1, %s, %s, %s, %s)
                    """,
                    (
                        name,
                        paper_size,
                        orientation,
                        font_size,
                        copies,
                        bool_fields["show_logo"],
                        bool_fields["show_operator"],
                        bool_fields["show_customer_phone"],
                        bool_fields["show_payment"],
                        bool_fields["show_note"],
                        header_text,
                        footer_text,
                        custom_css,
                        operator_user_id,
                        operator_user_id,
                        now,
                        now,
                    ),
                )
        return self.sales_print_settings()

    def _sales_print_order_payload(self, sales_id: int) -> dict:
        detail = self.sales_detail(int(sales_id))
        if detail.get("code") not in (None, 0):
            return detail
        order = dict(detail.get("data") or {})
        if str(order.get("status") or "") in {"canceled", "deleted"}:
            return {"code": 400, "msg": "已删除的销售单不能打印"}
        party_rows = self.query(
            "SELECT phone, address, contact_name FROM party WHERE id=%s LIMIT 1",
            (order.get("customer_id"),),
        )
        if party_rows:
            party = party_rows[0]
            order["customer_phone"] = party.get("phone") or ""
            order["customer_address"] = party.get("address") or ""
            order["contact_name"] = party.get("contact_name") or ""
        return {"code": 0, "data": order}

    def sales_print_data(self, sales_id: int) -> dict:
        order_result = self._sales_print_order_payload(sales_id)
        if order_result.get("code") not in (None, 0):
            return order_result
        return {
            "code": 0,
            "data": {
                "order": order_result.get("data") or {},
                "template": self._default_sales_print_template(),
            },
        }

    def sales_print_html(
        self,
        sales_id: int,
        template_id: int | None = None,
        auto_print: bool = True,
        show_actions: bool = True,
    ) -> str:
        self._ensure_print_tables()
        payload = self.sales_print_data(sales_id)
        if payload.get("code") not in (None, 0):
            raise DBError(payload.get("msg") or "销售单不存在")
        data = payload.get("data") or {}
        order = data.get("order") or {}
        template = data.get("template") or self._default_sales_print_template()

        def esc(value: Any) -> str:
            return html_lib.escape(str(value or ""), quote=True)

        def clean_print_note(value: Any) -> str:
            lines = []
            for line in str(value or "").splitlines():
                clean = line.strip()
                if not clean:
                    continue
                if clean.startswith(("打印失败：", "打印失败:", "自动打印失败：", "自动打印失败:")):
                    continue
                if clean in {"PDF 渲染失败", "print failed"}:
                    continue
                lines.append(clean)
            return "\n".join(lines)

        paper_size = template.get("paper_size") or "A5"
        orientation = template.get("orientation") or "landscape"
        font_size = int(template.get("font_size") or 12)
        page_rule = "80mm auto" if paper_size == "80mm" else f"{paper_size} {orientation}"
        page_margin = "4mm" if paper_size == "80mm" else "6mm"
        thermal_class = " thermal" if paper_size == "80mm" else ""
        sheet_width_map = {
            ("A4", "portrait"): "210mm",
            ("A4", "landscape"): "297mm",
            ("A5", "portrait"): "148mm",
            ("A5", "landscape"): "210mm",
        }
        sheet_width = "80mm" if paper_size == "80mm" else sheet_width_map.get((paper_size, orientation), "210mm")
        rows = []
        for index, item in enumerate(order.get("products") or order.get("detail") or [], start=1):
            qty = item.get("quantity") or item.get("buy_number") or "0"
            rows.append(
                "<tr>"
                f"<td class=\"center\">{index}</td>"
                f"<td><strong>{esc(item.get('title') or '商品')}</strong><small>{esc(item.get('spec') or '')}</small></td>"
                f"<td class=\"num\">{esc(qty)}</td>"
                f"<td class=\"num\">¥{esc(_money(item.get('price')))}</td>"
                f"<td class=\"num\">¥{esc(_money(item.get('total_price')))}</td>"
                "</tr>"
            )
        payment_line = ""
        if int(template.get("show_payment") or 0):
            payment_text = " / ".join(
                item
                for item in [
                    order.get("pay_status_text") or _pay_status_text(order.get("pay_status")),
                    order.get("pay_type_text") or _pay_type_text(order.get("pay_type")),
                ]
                if item
            )
            payment_line = f"<span>付款：{esc(payment_text or '-')}</span>"
        operator_line = ""
        if int(template.get("show_operator") or 0):
            operator_line = f"<span>开单人：{esc(order.get('created_by_name') or '-')}</span>"
        phone_line = ""
        if int(template.get("show_customer_phone") or 0) and order.get("customer_phone"):
            phone_line = f"<span>电话：{esc(order.get('customer_phone'))}</span>"
        print_note = clean_print_note(order.get("note"))
        note_line = ""
        if int(template.get("show_note") or 0) and print_note:
            note_line = f"<div class=\"print-note\"><b>备注</b><span>{esc(print_note)}</span></div>"
        custom_css = str(template.get("custom_css") or "")
        auto_script = (
            "<script>window.addEventListener('load',function(){setTimeout(function(){window.print();},500);});</script>"
            if auto_print
            else ""
        )
        action_bar = (
            """
  <div class="print-actions">
    <button type="button" onclick="window.close()">关闭</button>
    <button class="primary" type="button" onclick="window.print()">打印</button>
  </div>"""
            if show_actions
            else ""
        )
        html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(order.get('sales_no') or sales_id)} 打印</title>
  <style>
    @page {{ size: {page_rule}; margin: {page_margin}; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: #f5f6f8; color: #111827; font-family: "Microsoft YaHei", "PingFang SC", Arial, sans-serif; font-size: {font_size}px; }}
    .print-actions {{ position: sticky; top: 0; z-index: 3; display: flex; justify-content: flex-end; gap: 8px; padding: 10px 14px; background: rgba(255,255,255,.92); border-bottom: 1px solid #e5e7eb; }}
    .print-actions button {{ height: 36px; padding: 0 14px; border: 1px solid #d9dee6; border-radius: 6px; background: #fff; cursor: pointer; }}
    .print-actions .primary {{ background: #1f8a70; border-color: #1f8a70; color: #fff; font-weight: 700; }}
    .sheet {{ width: min(100%, {sheet_width}); margin: 16px auto; padding: 18mm; background: #fff; box-shadow: 0 12px 32px rgba(20,28,38,.12); }}
    .sheet.thermal {{ width: 80mm; padding: 5mm; margin: 0 auto; box-shadow: none; }}
    .print-head {{ display: grid; grid-template-columns: 1fr auto; gap: 12px; align-items: start; padding-bottom: 10px; }}
    h1 {{ margin: 0; font-size: 24px; line-height: 1.2; letter-spacing: 0; }}
    .doc-no {{ text-align: right; color: #111827; line-height: 1.6; }}
    .meta {{ display: flex; flex-wrap: wrap; gap: 8px 18px; padding: 12px 0; color: #111827; border-bottom: 1px solid #e6e9ee; }}
    .meta span {{ white-space: nowrap; }}
    .print-table {{ width: 100%; border-collapse: collapse; table-layout: fixed; margin-top: 14px; border: 1px solid #111827; }}
    .print-table th, .print-table td {{ padding: 8px 9px; border: 1px solid #111827; text-align: left; vertical-align: top; color: #111827; background: #fff; }}
    .print-table th {{ font-weight: 700; }}
    .print-table th:first-child, .print-table td:first-child {{ width: 42px; }}
    .print-table th:nth-child(3), .print-table td:nth-child(3),
    .print-table th:nth-child(4), .print-table td:nth-child(4),
    .print-table th:nth-child(5), .print-table td:nth-child(5) {{ width: 112px; }}
    .print-table strong {{ font-weight: 700; }}
    .print-table td small {{ display: block; margin-top: 3px; color: #111827; }}
    .summary {{ display: grid; justify-content: end; gap: 6px; margin-top: 14px; }}
    .summary div {{ display: grid; grid-template-columns: 96px 130px; gap: 12px; }}
    .summary span {{ color: #111827; text-align: right; }}
    .summary strong {{ color: #111827; text-align: right; font-size: 16px; }}
    .print-note, .footer {{ margin-top: 16px; padding: 10px 0 0; border-top: 1px solid #e6e9ee; color: #111827; line-height: 1.7; }}
    .print-note b {{ margin-right: 8px; }}
    .print-note span {{ white-space: pre-wrap; }}
    .center {{ text-align: center; }}
    .num {{ text-align: right; white-space: nowrap; }}
    .thermal h1 {{ font-size: 18px; }}
    .thermal .print-head {{ grid-template-columns: 1fr; }}
    .thermal .doc-no {{ text-align: left; }}
    .thermal .print-table th, .thermal .print-table td {{ padding: 5px 3px; }}
    .thermal .print-table th:nth-child(4), .thermal .print-table td:nth-child(4),
    .thermal .print-table th:nth-child(5), .thermal .print-table td:nth-child(5) {{ width: auto; }}
    {custom_css}
    @media print {{
      body {{ background: #fff; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
      .print-actions {{ display: none; }}
      .sheet:not(.thermal) {{ width: auto; margin: 0; padding: 6mm 8mm; box-shadow: none; }}
      .print-table, .print-table th, .print-table td {{ border-color: #111827 !important; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
    }}
  </style>
</head>
<body>
{action_bar}
  <main class="sheet{thermal_class}">
    <header class="print-head">
      <div>
        <h1>{esc(template.get('header_text') or '肆计包装销售单')}</h1>
        <div class="meta">
          <span>客户：{esc(order.get('customer_name') or '-')}</span>
          {phone_line}
          {payment_line}
          {operator_line}
        </div>
      </div>
      <div class="doc-no">
        <div>单号：{esc(order.get('sales_no') or sales_id)}</div>
        <div>日期：{esc(_date_text(order.get('sales_at') or order.get('created_at')))}</div>
      </div>
    </header>
    <table class="print-table">
      <thead>
        <tr><th>#</th><th>商品</th><th class="num">数量</th><th class="num">单价</th><th class="num">金额</th></tr>
      </thead>
      <tbody>{''.join(rows) or '<tr><td colspan="5">暂无商品明细</td></tr>'}</tbody>
    </table>
    <section class="summary">
      <div><span>总数量</span><strong>{esc(_qty_text(order.get('total_quantity') or order.get('buy_number_count') or 0))}</strong></div>
      <div><span>应收金额</span><strong>¥{esc(_money(order.get('receivable_amount') or order.get('total_price') or 0))}</strong></div>
    </section>
    {note_line}
    <footer class="footer">{esc(template.get('footer_text') or '')}</footer>
  </main>
  {auto_script}
</body>
</html>"""
        return html

    def create_sales_print_task(self, sales_id: int, template_id: int | None = None, operator_user_id: Any = None) -> dict:
        self._ensure_print_tables()
        operator_user_id = self._operator_user_id(operator_user_id)
        template = self._default_sales_print_template()
        template_id = int(template_id or template.get("id") or 0) or None
        rows = self.query("SELECT id, sales_no, status FROM sales_order WHERE id=%s LIMIT 1", (int(sales_id),))
        if not rows:
            return {"code": 404, "msg": "销售单不存在"}
        if str(rows[0].get("status") or "") in {"canceled", "deleted"}:
            return {"code": 400, "msg": "已删除的销售单不能打印"}
        now = _now()
        job_no = self._ledger_no("PJ")
        print_url = f"/api/sales/{int(sales_id)}/print-html?auto=1"
        with self.transaction() as cursor:
            cursor.execute(
                """
                INSERT INTO print_job
                    (job_no, document_type, document_id, template_id, status, print_url, copies,
                     created_by_user_id, created_at, updated_at)
                VALUES (%s, 'sales_order', %s, %s, 'pending', %s, %s, %s, %s, %s)
                """,
                (
                    job_no,
                    int(sales_id),
                    template_id,
                    print_url,
                    int(template.get("copies") or 1),
                    operator_user_id,
                    now,
                    now,
                ),
            )
            job_id = cursor.lastrowid
            cursor.execute("UPDATE sales_order SET print_status='pending', updated_at=%s WHERE id=%s", (now, int(sales_id)))
        return {
            "code": 0,
            "data": {
                "id": job_id,
                "task_id": job_id,
                "job_no": job_no,
                "sales_id": int(sales_id),
                "print_url": print_url,
                "copies": int(template.get("copies") or 1),
                "status": "pending",
            },
        }

    def sales_print_task_list(self, page: int = 1, page_size: int = 50) -> dict:
        self._ensure_print_tables()
        page = max(1, int(page or 1))
        page_size = max(1, min(int(page_size or 50), 200))
        rows = self.query(
            """
            SELECT j.*, s.sales_no, s.customer_name_snapshot
            FROM print_job j
            LEFT JOIN sales_order s ON s.id=j.document_id
            WHERE j.document_type='sales_order' AND j.status='pending'
            ORDER BY j.created_at ASC, j.id ASC
            LIMIT %s OFFSET %s
            """,
            (page_size, (page - 1) * page_size),
        )
        return {
            "code": 0,
            "data": {
                "list": [
                    {
                        "id": row.get("id"),
                        "task_id": row.get("id"),
                        "job_no": row.get("job_no") or "",
                        "sales_id": row.get("document_id"),
                        "sales_no": row.get("sales_no") or "",
                        "customer_name": row.get("customer_name_snapshot") or "",
                        "status": row.get("status") or "",
                        "print_url": row.get("print_url") or "",
                        "copies": int(row.get("copies") or 1),
                        "created_at": str(row.get("created_at") or ""),
                    }
                    for row in rows
                ]
            },
        }

    def sales_print_task_done(self, task_id: int, operator_user_id: Any = None) -> dict:
        self._ensure_print_tables()
        operator_user_id = self._operator_user_id(operator_user_id)
        now = _now()
        with self.transaction() as cursor:
            cursor.execute("SELECT * FROM print_job WHERE id=%s FOR UPDATE", (int(task_id),))
            job = cursor.fetchone()
            if not job:
                return {"code": 404, "msg": "打印任务不存在"}
            cursor.execute(
                """
                UPDATE print_job
                SET status='printed', printed_by_user_id=%s, printed_at=%s, updated_at=%s
                WHERE id=%s
                """,
                (operator_user_id, now, now, int(task_id)),
            )
            if str(job.get("document_type") or "") == "sales_order":
                cursor.execute(
                    "UPDATE sales_order SET print_status='printed', updated_at=%s WHERE id=%s",
                    (now, int(job.get("document_id") or 0)),
                )
        return {"code": 0, "data": {"id": int(task_id), "status": "printed"}}

    def _first_product_line(self, products: list[dict]) -> str:
        if not products:
            return "暂无商品明细"
        item = products[0]
        return f"{item.get('title') or '商品'} {item.get('spec') or ''} x{item.get('quantity') or 0}  ¥{item.get('price') or '0.00'}".strip()

    def workflow_orders(
        self,
        keyword: str = "",
        page: int = 1,
        page_size: int = 20,
        status_filter: str = "active",
        customer_id: int | None = None,
    ) -> tuple[list[dict], int]:
        where = ["wo.deleted_at IS NULL"]
        params: list[Any] = []
        if status_filter == "unmade":
            where.append("wo.is_made <> 1")
        elif status_filter == "pending":
            where.append("(wo.is_made <> 1 OR wo.is_delivered <> 1 OR wo.status <> 'completed')")
        elif status_filter != "all":
            where.append("(wo.is_made <> 1 OR wo.is_delivered <> 1 OR wo.status <> 'completed' OR wo.created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY))")
        if customer_id:
            where.append("wo.customer_id=%s")
            params.append(int(customer_id))
        if keyword:
            like = f"%{keyword}%"
            where.append("(CAST(wo.id AS CHAR) LIKE %s OR wo.workflow_no LIKE %s OR wo.customer_name_snapshot LIKE %s OR wo.customer_phone_snapshot LIKE %s OR wo.goods_name_snapshot LIKE %s OR wo.color_snapshot LIKE %s)")
            params.extend([like, like, like, like, like, like])
        where_sql = " AND ".join(where)
        total_rows = self.query(f"SELECT COUNT(*) AS total FROM workflow_order wo WHERE {where_sql}", params)
        rows = self.query(
            f"""
            SELECT wo.*, wu.display_name AS created_by_name, wu.username AS created_by_username
            FROM workflow_order wo
            LEFT JOIN auth_user wu ON wu.id=wo.created_by_user_id
            WHERE {where_sql}
            ORDER BY wo.created_at DESC, wo.id DESC
            LIMIT %s OFFSET %s
            """,
            params + [page_size, (max(1, page) - 1) * page_size],
        )
        cards = []
        for row in rows:
            images = _json_loads(row.get("order_image_urls"), [])
            cards.append({
                "id": row.get("id"),
                "order_no": str(row.get("id") or "").strip(),
                "workflow_order_id": row.get("id"),
                "workflow_no": row.get("workflow_no") or "",
                "customer_name": row.get("customer_name_snapshot") or "客户未填写",
                "customer_phone": row.get("customer_phone_snapshot") or "",
                "goods_name": row.get("goods_name_snapshot") or "商品未填写",
                "goods_color": row.get("color_snapshot") or "",
                "order_quantity": _qty_text(row.get("quantity")),
                "is_screen_print": int(row.get("is_screen_print") or 0),
                "is_screen_print_text": "是" if int(row.get("is_screen_print") or 0) else "否",
                "is_made": int(row.get("is_made") or 0),
                "is_delivered": int(row.get("is_delivered") or 0),
                "order_type": 1 if row.get("status") == "completed" else 0,
                "status_text": "完成" if row.get("status") == "completed" else "待完成",
                "order_time_text": _date_text(row.get("created_at")),
                "complete_time_text": _date_text(row.get("updated_at")) if row.get("status") == "completed" else "",
                "order_images": images if isinstance(images, list) else [],
                "created_by_user_id": row.get("created_by_user_id"),
                "created_by_name": row.get("created_by_name") or row.get("created_by_username") or "",
            })
        return cards, int(total_rows[0].get("total") or 0) if total_rows else 0

    def save_workflow_order(
        self,
        customer_name: str,
        goods_name: str,
        order_quantity: int,
        order_id: int | None = None,
        customer_phone: str = "",
        color: str = "",
        order_images: list[str] | None = None,
        is_screen_print: int = 0,
        is_made: int | None = None,
        is_delivered: int | None = None,
        order_type: int = 0,
        remark: str = "",
    ) -> dict:
        now = _now()
        operator_user_id = self._operator_user_id()
        status = "completed" if int(order_type or 0) == 1 else "pending"
        made_value = int(is_made or 0) if is_made is not None else None
        delivered_value = int(is_delivered or 0) if is_delivered is not None else None
        customer_id = self._find_party_id(customer_name, customer_phone)
        if order_id:
            with self.transaction() as cursor:
                cursor.execute(
                    """
                    UPDATE workflow_order
                    SET customer_id=%s, customer_name_snapshot=%s, customer_phone_snapshot=%s,
                        goods_name_snapshot=%s, color_snapshot=%s, quantity=%s, order_image_urls=%s,
                        is_screen_print=%s, is_made=COALESCE(%s, is_made),
                        is_delivered=COALESCE(%s, is_delivered), status=%s, remark=%s, updated_at=%s
                    WHERE id=%s
                    """,
                    (
                        customer_id,
                        customer_name,
                        customer_phone,
                        goods_name,
                        color,
                        Decimal(str(order_quantity or 0)),
                        _json_dumps(order_images or []),
                        int(is_screen_print or 0),
                        made_value,
                        delivered_value,
                        status,
                        remark,
                        now,
                        int(order_id),
                    ),
                )
                cursor.execute(
                    """
                    INSERT INTO workflow_order_log
                        (workflow_order_id, action, operator_user_id, note, created_at)
                    VALUES (%s, 'update', %s, %s, %s)
                    """,
                    (int(order_id), operator_user_id, "native workflow order update", now),
                )
            return {"code": 0, "data": {"id": int(order_id)}}
        workflow_no = f"WF{datetime.now().strftime('%Y%m%d%H%M%S')}{int(time.time() * 1000) % 1000:03d}"
        with self.transaction() as cursor:
            cursor.execute(
                """
                INSERT INTO workflow_order
                    (workflow_no, customer_id, customer_name_snapshot, customer_phone_snapshot,
                     goods_name_snapshot, color_snapshot, quantity, order_image_urls,
                     is_screen_print, is_made, is_delivered, status, remark, source,
                     created_by_user_id, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'native_api', %s, %s, %s)
                """,
                (
                    workflow_no,
                    customer_id,
                    customer_name,
                    customer_phone,
                    goods_name,
                    color,
                    Decimal(str(order_quantity or 0)),
                    _json_dumps(order_images or []),
                    int(is_screen_print or 0),
                    int(is_made or 0),
                    int(is_delivered or 0),
                    status,
                    remark,
                    operator_user_id,
                    now,
                    now,
                ),
            )
            new_id = cursor.lastrowid
            cursor.execute(
                "INSERT INTO workflow_order_log (workflow_order_id, action, operator_user_id, note, created_at) VALUES (%s, 'create', %s, %s, %s)",
                (new_id, operator_user_id, "native workflow order", now),
            )
        return {"code": 0, "data": {"id": new_id, "workflow_no": workflow_no}}

    def update_workflow_status(self, order_id: int, field: str, value: int) -> dict:
        if field not in ("is_made", "is_delivered", "order_type"):
            return {"code": 400, "msg": "字段不允许更新"}
        now = _now()
        operator_user_id = self._operator_user_id()
        if field == "order_type":
            status = "completed" if int(value or 0) == 1 else "pending"
            with self.transaction() as cursor:
                cursor.execute("UPDATE workflow_order SET status=%s, updated_at=%s WHERE id=%s", (status, now, order_id))
                cursor.execute(
                    """
                    INSERT INTO workflow_order_log
                        (workflow_order_id, action, field_name, new_value, operator_user_id, created_at)
                    VALUES (%s, 'status_update', %s, %s, %s, %s)
                    """,
                    (order_id, field, status, operator_user_id, now),
                )
        else:
            with self.transaction() as cursor:
                cursor.execute(f"UPDATE workflow_order SET {field}=%s, updated_at=%s WHERE id=%s", (int(value or 0), now, order_id))
                cursor.execute(
                    """
                    INSERT INTO workflow_order_log
                        (workflow_order_id, action, field_name, new_value, operator_user_id, created_at)
                    VALUES (%s, 'status_update', %s, %s, %s, %s)
                    """,
                    (order_id, field, str(int(value or 0)), operator_user_id, now),
                )
        return {"code": 0, "data": {"id": order_id, field: value}}

    def delete_workflow_orders(self, ids: str) -> dict:
        raw_ids = [int(item) for item in str(ids or "").split(",") if item.strip().isdigit()]
        if not raw_ids:
            return {"code": 400, "msg": "缺少工作流订单ID"}
        placeholders = ",".join(["%s"] * len(raw_ids))
        now = _now()
        operator_user_id = self._operator_user_id()
        with self.transaction() as cursor:
            cursor.execute(f"UPDATE workflow_order SET deleted_at=%s, updated_at=%s WHERE id IN ({placeholders})", [now, now] + raw_ids)
            for order_id in raw_ids:
                cursor.execute(
                    """
                    INSERT INTO workflow_order_log
                        (workflow_order_id, action, operator_user_id, note, created_at)
                    VALUES (%s, 'delete', %s, %s, %s)
                    """,
                    (order_id, operator_user_id, "native workflow order delete", now),
                )
        return {"code": 0, "data": {"ids": raw_ids}}

    def link_workflow_sales_order(
        self,
        workflow_order_id: int,
        sales_order_id: int,
        operator_user_id: Any = None,
    ) -> dict:
        workflow_order_id = int(workflow_order_id or 0)
        sales_order_id = int(sales_order_id or 0)
        if workflow_order_id <= 0 or sales_order_id <= 0:
            return {"code": 400, "msg": "workflow_order_id and sales_order_id are required"}
        now = _now()
        operator_user_id = self._operator_user_id(operator_user_id)
        with self.transaction() as cursor:
            cursor.execute(
                """
                SELECT id, sales_order_id
                FROM workflow_order
                WHERE id=%s AND deleted_at IS NULL
                LIMIT 1
                FOR UPDATE
                """,
                (workflow_order_id,),
            )
            workflow_order = cursor.fetchone()
            if not workflow_order:
                return {"code": 404, "msg": "工作流订单不存在"}

            cursor.execute(
                """
                SELECT id, source_workflow_id
                FROM sales_order
                WHERE id=%s AND status NOT IN ('canceled', 'deleted')
                LIMIT 1
                FOR UPDATE
                """,
                (sales_order_id,),
            )
            sales_order = cursor.fetchone()
            if not sales_order:
                return {"code": 404, "msg": "销售单不存在"}

            old_sales_order_id = int(workflow_order.get("sales_order_id") or 0)
            old_workflow_order_id = int(sales_order.get("source_workflow_id") or 0)
            if old_sales_order_id and old_sales_order_id != sales_order_id:
                return {"code": 409, "msg": "工作流订单已关联其他销售单"}
            if old_workflow_order_id and old_workflow_order_id != workflow_order_id:
                return {"code": 409, "msg": "销售单已关联其他工作流订单"}

            cursor.execute(
                "UPDATE workflow_order SET sales_order_id=%s, updated_at=%s WHERE id=%s",
                (sales_order_id, now, workflow_order_id),
            )
            cursor.execute(
                "UPDATE sales_order SET source_workflow_id=%s, updated_at=%s WHERE id=%s",
                (workflow_order_id, now, sales_order_id),
            )
            cursor.execute(
                """
                INSERT INTO workflow_order_log
                    (workflow_order_id, action, field_name, old_value, new_value,
                     operator_user_id, note, created_at)
                VALUES (%s, 'link_sales', 'sales_order_id', %s, %s, %s, %s, %s)
                """,
                (
                    workflow_order_id,
                    str(old_sales_order_id or ""),
                    str(sales_order_id),
                    operator_user_id,
                    f"link sales order {sales_order_id}",
                    now,
                ),
            )
        return {"code": 0, "data": {"workflow_order_id": workflow_order_id, "sales_order_id": sales_order_id}}

    def _find_party_id(self, name: str = "", phone: str = "") -> int | None:
        phone_norm = _phone_digits(phone)
        params: list[Any] = []
        where = []
        if phone_norm:
            where.append("phone_normalized=%s")
            params.append(phone_norm)
        if name:
            where.append("name=%s")
            params.append(name)
        if not where:
            return None
        rows = self.query(f"SELECT id FROM party WHERE kind='customer' AND ({' OR '.join(where)}) LIMIT 1", params)
        return int(rows[0]["id"]) if rows else None

    def customer_create(self, name: str, contacts_name: str = "", contacts_tel: str = "") -> dict:
        self._ensure_party_columns()
        name = str(name or "").strip()
        if not name:
            return {"code": 400, "msg": "客户名称不能为空"}
        phone_norm = _phone_digits(contacts_tel)
        now = _now()
        existing = self._find_party_id(name, contacts_tel)
        if existing:
            return {"code": 0, "data": {"id": existing, "existed": True}}
        with self.transaction() as cursor:
            cursor.execute(
                """
                INSERT INTO party
                    (name, kind, contact_name, phone, phone_normalized, is_monthly_customer, source, status, created_at, updated_at)
                VALUES (%s, 'customer', %s, %s, %s, 0, 'native_api', 'active', %s, %s)
                """,
                (name, contacts_name, contacts_tel, phone_norm or None, now, now),
            )
            party_id = cursor.lastrowid
        return {"code": 0, "data": {"id": party_id}}

    def update_customer_monthly(self, customer_id: int, is_monthly_customer: Any) -> dict:
        self._ensure_party_columns()
        customer_id = int(customer_id or 0)
        value = 1 if str(is_monthly_customer).strip().lower() in {"1", "true", "yes", "on"} else 0
        affected = self.execute(
            """
            UPDATE party
            SET is_monthly_customer=%s, settlement_type=%s, updated_at=%s
            WHERE id=%s AND kind='customer' AND deleted_at IS NULL
            """,
            (value, "monthly" if value else None, _now(), customer_id),
        )
        if not affected:
            return {"code": 404, "msg": "客户不存在"}
        return {"code": 0, "data": {"id": customer_id, "is_monthly_customer": value}}

    def update_customer_profile(
        self,
        customer_id: int,
        *,
        name: Any = None,
        contacts_name: Any = None,
        address: Any = None,
    ) -> dict:
        self._ensure_party_columns()
        customer_id = int(customer_id or 0)
        fields: list[str] = []
        params: list[Any] = []
        if name is not None:
            clean_name = str(name or "").strip()
            if not clean_name:
                return {"code": 400, "msg": "客户名称不能为空"}
            fields.append("name=%s")
            params.append(clean_name)
        if contacts_name is not None:
            fields.append("contact_name=%s")
            params.append(str(contacts_name or "").strip())
        if address is not None:
            fields.append("address=%s")
            params.append(str(address or "").strip())
        if not fields:
            return {"code": 0, "data": {"id": customer_id}}
        fields.append("updated_at=%s")
        params.append(_now())
        affected = self.execute(
            f"""
            UPDATE party
            SET {', '.join(fields)}
            WHERE id=%s AND kind='customer' AND deleted_at IS NULL
            """,
            params + [customer_id],
        )
        if not affected:
            return {"code": 404, "msg": "客户不存在"}
        return {"code": 0, "data": {"id": customer_id}}

    # ---- inventory writes ----

    def _ledger_no(self, prefix: str) -> str:
        return f"{prefix}{datetime.now().strftime('%Y%m%d%H%M%S')}{int(time.time() * 1000) % 1000:03d}"

    def _db_enabled_flag(self, value: Any, *, default: bool = True) -> bool:
        if value in (None, ""):
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return int(value) == 1
        text = str(value).strip().lower()
        if text in {"1", "true", "yes", "y", "on", "active", "enabled"}:
            return True
        if text in {"0", "false", "no", "n", "off", "inactive", "disabled", "deleted", "none"}:
            return False
        return default

    def _sku_sales_unavailable_reason(self, sku: dict) -> str:
        status = str(sku.get("status") if sku.get("status") not in (None, "") else "active").strip().lower()
        if status not in {"active", "normal", "enabled", "0"}:
            return "状态不是正常"
        if not self._db_enabled_flag(sku.get("is_sellable"), default=True):
            return "不可售"
        return ""

    def _get_sku_for_update(self, cursor, sku_id: int, *, require_sellable: bool = False) -> dict:
        cursor.execute(
            """
            SELECT s.*, sp.title, sp.product_type, sp.case_pack_qty
            FROM product_sku s
            JOIN product_spu sp ON sp.id=s.spu_id
            WHERE s.id=%s AND s.deleted_at IS NULL
            FOR UPDATE
            """,
            (sku_id,),
        )
        row = cursor.fetchone()
        if not row:
            raise DBError(f"商品不存在: {sku_id}")
        if require_sellable:
            reason = self._sku_sales_unavailable_reason(row)
            if reason:
                title = row.get("title") or row.get("sku_no") or sku_id
                raise DBError(f"商品{reason}，不能开单：{title}")
        return row

    def _change_inventory(
        self,
        cursor,
        sku: dict,
        warehouse_id: int,
        unit_id: int,
        delta: Decimal,
        biz_type: str,
        biz_id: int,
        biz_item_id: int | None,
        note: str = "",
        counterparty_warehouse_id: int | None = None,
        allow_negative: bool = False,
        operator_user_id: Any = None,
    ) -> int:
        sku_id = int(sku["id"])
        clean_operator_user_id = self._operator_user_id(operator_user_id)
        cursor.execute(
            """
            SELECT *
            FROM inventory_balance
            WHERE sku_id=%s AND warehouse_id=%s AND unit_id=%s
            FOR UPDATE
            """,
            (sku_id, warehouse_id, unit_id),
        )
        balance = cursor.fetchone()
        before = Decimal(str(balance.get("quantity") if balance else 0))
        after = before + delta
        if after < 0 and not allow_negative:
            raise DBError(f"{sku.get('title')} {sku.get('color') or ''} 库存不足")
        now = _now()
        if balance:
            cursor.execute(
                """
                UPDATE inventory_balance
                SET quantity=%s, available_qty=%s, version=version+1, updated_at=%s
                WHERE id=%s
                """,
                (after, after, now, balance["id"]),
            )
            balance_id = int(balance["id"])
        else:
            cursor.execute(
                """
                INSERT INTO inventory_balance
                    (sku_id, warehouse_id, unit_id, quantity, reserved_qty, available_qty, version, updated_at)
                VALUES (%s, %s, %s, %s, 0, %s, 1, %s)
                """,
                (sku_id, warehouse_id, unit_id, after, after, now),
            )
            balance_id = cursor.lastrowid
        cursor.execute(
            """
            INSERT INTO inventory_ledger
                (ledger_no, sku_id, sku_no_snapshot, warehouse_id, unit_id, change_qty,
                 before_qty, after_qty, biz_type, biz_id, biz_item_id, counterparty_warehouse_id,
                 operator_user_id, note, occurred_at, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                self._ledger_no("LG"),
                sku_id,
                sku.get("sku_no") or "",
                warehouse_id,
                unit_id,
                delta,
                before,
                after,
                biz_type,
                biz_id,
                biz_item_id,
                counterparty_warehouse_id,
                clean_operator_user_id,
                note,
                now,
                now,
            ),
        )
        ledger_id = cursor.lastrowid
        cursor.execute("UPDATE inventory_balance SET last_ledger_id=%s WHERE id=%s", (ledger_id, balance_id))
        return int(ledger_id)

    def create_stock_in(self, warehouse_id: int, products: list[dict], note: str = "智能体进货", operator_user_id: Any = None) -> dict:
        now = _now()
        operator_user_id = self._operator_user_id(operator_user_id)
        doc_no = self._ledger_no("IN")
        with self.transaction() as cursor:
            total_qty = Decimal("0")
            cursor.execute(
                """
                INSERT INTO stock_document
                    (doc_no, doc_type, direction, warehouse_id, status, total_quantity, note, created_by_user_id, created_at, confirmed_at)
                VALUES (%s, 'other_enter', 'in', %s, 'confirmed', 0, %s, %s, %s, %s)
                """,
                (doc_no, warehouse_id, note, operator_user_id, now, now),
            )
            doc_id = cursor.lastrowid
            for index, item in enumerate(products or [], start=1):
                sku_id = self.resolve_sku_id(int(item.get("product_id") or item.get("id") or 0), cursor=cursor)
                if not sku_id:
                    raise DBError("入库商品不存在")
                sku = self._get_sku_for_update(cursor, sku_id)
                unit_id = int(item.get("unit_id") or sku.get("unit_id") or 1)
                qty = Decimal(str(item.get("buy_number") or item.get("quantity") or item.get("number") or 0))
                if qty <= 0:
                    raise DBError("入库数量必须大于0")
                total_qty += qty
                cursor.execute(
                    """
                    INSERT INTO stock_document_item
                        (stock_document_id, line_no, sku_id, sku_no_snapshot, title_snapshot, unit_id, quantity, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (doc_id, index, sku_id, sku.get("sku_no"), sku.get("title"), unit_id, qty, now),
                )
                item_id = cursor.lastrowid
                if self._sku_tracks_inventory(sku):
                    ledger_id = self._change_inventory(cursor, sku, warehouse_id, unit_id, qty, "stock_in", doc_id, item_id, note, allow_negative=True, operator_user_id=operator_user_id)
                    cursor.execute("UPDATE stock_document_item SET ledger_id=%s WHERE id=%s", (ledger_id, item_id))
            cursor.execute("UPDATE stock_document SET total_quantity=%s WHERE id=%s", (total_qty, doc_id))
        return {"code": 0, "data": {"id": doc_id, "doc_no": doc_no}}

    def create_transfer(self, out_warehouse_id: int, enter_warehouse_id: int, products: list[dict], note: str = "智能体调拨", operator_user_id: Any = None) -> dict:
        if int(out_warehouse_id) == int(enter_warehouse_id):
            return {"code": 400, "msg": "调出仓库和调入仓库不能相同"}
        now = _now()
        operator_user_id = self._operator_user_id(operator_user_id)
        transfer_no = self._ledger_no("TR")
        with self.transaction() as cursor:
            total_qty = Decimal("0")
            cursor.execute(
                """
                INSERT INTO transfer_order
                    (transfer_no, from_warehouse_id, to_warehouse_id, status, total_quantity, note, created_by_user_id, created_at, confirmed_at)
                VALUES (%s, %s, %s, 'confirmed', 0, %s, %s, %s, %s)
                """,
                (transfer_no, out_warehouse_id, enter_warehouse_id, note, operator_user_id, now, now),
            )
            transfer_id = cursor.lastrowid
            for index, item in enumerate(products or [], start=1):
                sku_id = self.resolve_sku_id(int(item.get("product_id") or item.get("id") or 0), cursor=cursor)
                if not sku_id:
                    raise DBError("调拨商品不存在")
                sku = self._get_sku_for_update(cursor, sku_id)
                unit_id = int(item.get("unit_id") or sku.get("unit_id") or 1)
                qty = Decimal(str(item.get("transfer_number") or item.get("quantity") or item.get("number") or 0))
                if qty <= 0:
                    raise DBError("调拨数量必须大于0")
                total_qty += qty
                cursor.execute(
                    """
                    INSERT INTO transfer_order_item
                        (transfer_order_id, line_no, sku_id, sku_no_snapshot, title_snapshot, unit_id, quantity, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (transfer_id, index, sku_id, sku.get("sku_no"), sku.get("title"), unit_id, qty, now),
                )
                item_id = cursor.lastrowid
                if self._sku_tracks_inventory(sku):
                    out_ledger_id = self._change_inventory(cursor, sku, out_warehouse_id, unit_id, -qty, "transfer_out", transfer_id, item_id, note, enter_warehouse_id, operator_user_id=operator_user_id)
                    in_ledger_id = self._change_inventory(cursor, sku, enter_warehouse_id, unit_id, qty, "transfer_in", transfer_id, item_id, note, out_warehouse_id, allow_negative=True, operator_user_id=operator_user_id)
                    cursor.execute(
                        "UPDATE transfer_order_item SET out_ledger_id=%s, in_ledger_id=%s WHERE id=%s",
                        (out_ledger_id, in_ledger_id, item_id),
                    )
            cursor.execute("UPDATE transfer_order SET total_quantity=%s WHERE id=%s", (total_qty, transfer_id))
        return {"code": 0, "data": {"id": transfer_id, "transfer_no": transfer_no}}

    def create_stocktake(self, warehouse_id: int, products: list[dict], note: str = "智能体盘点同步", operator_user_id: Any = None) -> dict:
        now = _now()
        operator_user_id = self._operator_user_id(operator_user_id)
        stocktake_no = self._ledger_no("ST")
        with self.transaction() as cursor:
            cursor.execute(
                """
                INSERT INTO stocktake_order
                    (stocktake_no, warehouse_id, scope_type, status, total_diff_qty, note, created_by_user_id, created_at, confirmed_at)
                VALUES (%s, %s, 'partial', 'confirmed', 0, %s, %s, %s, %s)
                """,
                (stocktake_no, warehouse_id, note, operator_user_id, now, now),
            )
            order_id = cursor.lastrowid
            total_diff = Decimal("0")
            for item in products or []:
                sku_id = self.resolve_sku_id(int(item.get("product_id") or item.get("id") or 0), cursor=cursor)
                if not sku_id:
                    raise DBError("盘点商品不存在")
                sku = self._get_sku_for_update(cursor, sku_id)
                unit_id = int(item.get("unit_id") or sku.get("unit_id") or 1)
                counted = Decimal(str(item.get("number") or item.get("quantity") or 0))
                cursor.execute(
                    """
                    SELECT quantity FROM inventory_balance
                    WHERE sku_id=%s AND warehouse_id=%s AND unit_id=%s
                    FOR UPDATE
                    """,
                    (sku_id, warehouse_id, unit_id),
                )
                row = cursor.fetchone() or {}
                book = Decimal(str(row.get("quantity") or 0))
                diff = counted - book
                total_diff += diff
                tracks_inventory = self._sku_tracks_inventory(sku)
                if not tracks_inventory:
                    book = counted
                    diff = Decimal("0")
                cursor.execute(
                    """
                    INSERT INTO stocktake_item
                        (stocktake_order_id, sku_id, unit_id, book_qty, counted_qty, diff_qty, reason, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (order_id, sku_id, unit_id, book, counted, diff, note, now),
                )
                item_id = cursor.lastrowid
                if tracks_inventory:
                    ledger_id = self._change_inventory(cursor, sku, warehouse_id, unit_id, diff, "stocktake", order_id, item_id, note, allow_negative=True, operator_user_id=operator_user_id)
                    cursor.execute("UPDATE stocktake_item SET ledger_id=%s WHERE id=%s", (ledger_id, item_id))
            cursor.execute("UPDATE stocktake_order SET total_diff_qty=%s WHERE id=%s", (total_diff, order_id))
        return {"code": 0, "data": {"id": order_id, "stocktake_no": stocktake_no}}

    def create_sales_order(
        self,
        customer_id: int,
        warehouse_id: int,
        products: list[dict],
        create_time: str = "",
        pay_status: str | None = None,
        pay_type: str | None = None,
        operator_user_id: Any = None,
        allow_negative_stock: Any | None = None,
    ) -> dict:
        self._ensure_operator_columns()
        self._ensure_party_columns()
        self._ensure_system_settings_tables()
        operator_user_id = self._operator_user_id(operator_user_id)
        if not products:
            return {"code": 400, "msg": "销售明细不能为空"}
        now = _now()
        sales_at = create_time or now
        sales_no = self._ledger_no("SO")
        with self.transaction() as cursor:
            default_out_warehouse_id = self._default_out_warehouse_id(cursor)
            allow_negative_sales_out = self._explicit_allow_negative_stock(
                allow_negative_stock,
                self._allow_negative_stock(cursor),
            )
            cursor.execute(
                "SELECT id, name, is_monthly_customer FROM party WHERE id=%s AND deleted_at IS NULL LIMIT 1 FOR UPDATE",
                (customer_id,),
            )
            customer = cursor.fetchone()
            if not customer:
                raise DBError("客户不存在")
            customer_is_monthly = int(customer.get("is_monthly_customer") or 0) == 1
            explicit_pay_status = pay_status not in (None, "")
            explicit_pay_type = pay_type not in (None, "")
            clean_pay_status = str(pay_status).strip() if explicit_pay_status else ("monthly" if customer_is_monthly else "paid")
            clean_pay_type = str(pay_type).strip() if explicit_pay_type else ("monthly" if clean_pay_status == "monthly" else "wechat")
            allowed_status = {"paid", "unpaid", "monthly", "partial"}
            allowed_type = {"wechat", "cash", "balance", "monthly", "account", "bank", "alipay", ""}
            if clean_pay_status not in allowed_status:
                clean_pay_status = "monthly" if customer_is_monthly and not explicit_pay_status else "paid"
            if clean_pay_type not in allowed_type:
                clean_pay_type = "monthly" if clean_pay_status == "monthly" else "wechat"
            if clean_pay_status == "monthly":
                clean_pay_type = "monthly"
            elif clean_pay_status == "unpaid" and clean_pay_type == "wechat":
                clean_pay_type = ""
            cursor.execute(
                """
                INSERT INTO sales_order
                    (sales_no, customer_id, customer_name_snapshot, status, pay_type, pay_status,
                     total_quantity, goods_amount, receivable_amount, source, created_by_user_id,
                     sales_at, created_at, updated_at)
                VALUES (%s, %s, %s, 'confirmed', %s, %s, 0, 0, 0, 'native_api', %s, %s, %s, %s)
                """,
                (sales_no, customer_id, customer.get("name"), clean_pay_type, clean_pay_status, operator_user_id, sales_at, now, now),
            )
            sales_id = cursor.lastrowid
            total_qty = Decimal("0")
            total_amount = Decimal("0")
            for index, item in enumerate(products, start=1):
                sku_id = self.resolve_sku_id(int(item.get("product_id") or item.get("id") or 0), cursor=cursor)
                if not sku_id:
                    raise DBError("销售商品不存在")
                sku = self._get_sku_for_update(cursor, sku_id, require_sellable=True)
                line_warehouse_id = int(item.get("warehouse_id") or warehouse_id or sku.get("default_warehouse_id") or default_out_warehouse_id)
                unit_id = int(item.get("unit_id") or sku.get("unit_id") or 1)
                qty = Decimal(str(item.get("buy_number") or item.get("quantity") or item.get("number") or 0))
                price = Decimal(str(item.get("price") or sku.get("retail_price") or 0))
                if qty <= 0:
                    raise DBError("销售数量必须大于0")
                amount = qty * price
                total_qty += qty
                total_amount += amount
                cursor.execute(
                    """
                    INSERT INTO sales_order_item
                        (sales_order_id, line_no, sku_id, sku_no_snapshot, title_snapshot, color_snapshot,
                         warehouse_id, unit_id, quantity, unit_price, amount, cost_price_snapshot,
                         price_source, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'manual', %s)
                    """,
                    (
                        sales_id,
                        index,
                        sku_id,
                        sku.get("sku_no"),
                        sku.get("title"),
                        sku.get("color"),
                        line_warehouse_id,
                        unit_id,
                        qty,
                        price,
                        amount,
                        sku.get("cost_price"),
                        now,
                    ),
                )
                item_id = cursor.lastrowid
                if self._sku_tracks_inventory(sku):
                    self._change_inventory(
                        cursor,
                        sku,
                        line_warehouse_id,
                        unit_id,
                        -qty,
                        "sales_out",
                        sales_id,
                        item_id,
                        f"销售单 {sales_no}",
                        allow_negative=allow_negative_sales_out,
                        operator_user_id=operator_user_id,
                    )
            cursor.execute(
                """
                UPDATE sales_order
                SET total_quantity=%s, goods_amount=%s, receivable_amount=%s, updated_at=%s
                WHERE id=%s
                """,
                (total_qty, total_amount, total_amount, now, sales_id),
            )
            if clean_pay_status == "paid" and clean_pay_type == "balance" and total_amount > 0:
                cursor.execute(
                    """
                    SELECT
                      COALESCE((
                        SELECT SUM(balance_delta)
                        FROM customer_balance_ledger
                        WHERE customer_id=%s
                      ), 0) AS wallet_amount,
                      COALESCE((
                        SELECT SUM(receivable_amount)
                        FROM sales_order
                        WHERE customer_id=%s
                          AND status NOT IN ('canceled', 'deleted')
                          AND pay_status IN ('unpaid', 'monthly', 'partial')
                      ), 0) AS debt_amount
                    """,
                    (customer_id, customer_id),
                )
                wallet_row = cursor.fetchone() or {}
                wallet_amount = Decimal(str(wallet_row.get("wallet_amount") or "0")).quantize(Decimal("0.01"))
                debt_amount = Decimal(str(wallet_row.get("debt_amount") or "0")).quantize(Decimal("0.01"))
                available_amount = wallet_amount - debt_amount
                total_amount = total_amount.quantize(Decimal("0.01"))
                if available_amount < total_amount:
                    raise DBError(f"客户余额不足，当前可用余额{_money(available_amount)}")
                cursor.execute(
                    """
                    INSERT INTO customer_balance_ledger
                        (ledger_no, customer_id, entry_type, pay_type, amount, applied_amount,
                         balance_delta, related_month, note, created_by_user_id, created_at)
                    VALUES (%s, %s, 'balance_pay', 'balance', %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        self._ledger_no("CB"),
                        customer_id,
                        total_amount,
                        total_amount,
                        -total_amount,
                        str(sales_at)[:7],
                        f"销售单 {sales_no} 余额付款",
                        operator_user_id,
                        now,
                    ),
                )
        return {"code": 0, "data": {"id": sales_id, "sales_id": sales_id, "sales_no": sales_no}}

    def update_sales_order_payment(
        self,
        sales_id: int,
        *,
        pay_status: str,
        pay_type: str = "",
        note: str = "",
        operator_user_id: Any = None,
    ) -> dict:
        self._ensure_operator_columns()
        self._ensure_sales_delete_columns()
        operator_user_id = self._operator_user_id(operator_user_id)
        now = _now()
        allowed_status = {"paid", "unpaid", "monthly", "partial"}
        allowed_type = {"wechat", "cash", "balance", "monthly", "account", "bank", "alipay", ""}
        clean_pay_status = str(pay_status or "").strip()
        clean_pay_type = str(pay_type or "").strip()
        clean_note = str(note or "").strip()[:200]
        if clean_pay_status not in allowed_status:
            return {"code": 400, "msg": "结款状态不正确"}
        if clean_pay_type not in allowed_type:
            return {"code": 400, "msg": "收款方式不正确"}
        if clean_pay_status == "monthly":
            clean_pay_type = "monthly"
        elif clean_pay_status == "unpaid":
            clean_pay_type = ""
        elif clean_pay_status == "paid" and not clean_pay_type:
            clean_pay_type = "wechat"
        elif clean_pay_status == "paid" and clean_pay_type == "monthly":
            clean_pay_type = "wechat"

        with self.transaction() as cursor:
            cursor.execute("SELECT * FROM sales_order WHERE id=%s FOR UPDATE", (int(sales_id),))
            sale = cursor.fetchone()
            if not sale:
                return {"code": 404, "msg": "销售单不存在"}
            if sale.get("status") in ("canceled", "deleted"):
                return {"code": 400, "msg": "已取消或已删除的销售单不能修改收款方式"}
            if sale.get("settlement_ledger_id") and not (
                sale.get("pay_status") == "paid" and sale.get("pay_type") == "balance"
            ):
                return {"code": 400, "msg": "已参与月结结款的销售单不能单独修改收款方式"}

            customer_id = int(sale.get("customer_id") or 0)
            sales_no = str(sale.get("sales_no") or sales_id)
            sales_at = str(sale.get("sales_at") or now)
            amount = Decimal(str(sale.get("receivable_amount") or "0")).quantize(Decimal("0.01"))
            old_pay_status = str(sale.get("pay_status") or "")
            old_pay_type = str(sale.get("pay_type") or "")
            old_is_balance_paid = old_pay_status == "paid" and old_pay_type == "balance"
            new_is_balance_paid = clean_pay_status == "paid" and clean_pay_type == "balance"

            balance_action = ""
            if new_is_balance_paid and not old_is_balance_paid and amount > 0:
                cursor.execute("SELECT id FROM party WHERE id=%s AND deleted_at IS NULL LIMIT 1 FOR UPDATE", (customer_id,))
                if not cursor.fetchone():
                    raise DBError("客户不存在")
                cursor.execute(
                    """
                    SELECT
                      COALESCE((
                        SELECT SUM(balance_delta)
                        FROM customer_balance_ledger
                        WHERE customer_id=%s
                      ), 0) AS wallet_amount,
                      COALESCE((
                        SELECT SUM(receivable_amount)
                        FROM sales_order
                        WHERE customer_id=%s
                          AND id<>%s
                          AND status NOT IN ('canceled', 'deleted')
                          AND pay_status IN ('unpaid', 'monthly', 'partial')
                      ), 0) AS debt_amount
                    """,
                    (customer_id, customer_id, int(sales_id)),
                )
                wallet_row = cursor.fetchone() or {}
                wallet_amount = Decimal(str(wallet_row.get("wallet_amount") or "0")).quantize(Decimal("0.01"))
                debt_amount = Decimal(str(wallet_row.get("debt_amount") or "0")).quantize(Decimal("0.01"))
                available_amount = wallet_amount - debt_amount
                if available_amount < amount:
                    raise DBError(f"客户余额不足，当前可用余额{_money(available_amount)}")
                ledger_note = f"销售单 {sales_no} 改为余额付款"
                if clean_note:
                    ledger_note = f"{ledger_note}；{clean_note}"
                cursor.execute(
                    """
                    INSERT INTO customer_balance_ledger
                        (ledger_no, customer_id, entry_type, pay_type, amount, applied_amount,
                         balance_delta, related_month, note, created_by_user_id, created_at)
                    VALUES (%s, %s, 'balance_pay', 'balance', %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        self._ledger_no("CB"),
                        customer_id,
                        amount,
                        amount,
                        -amount,
                        sales_at[:7],
                        ledger_note[:500],
                        operator_user_id,
                        now,
                    ),
                )
                balance_action = "balance_pay"
            elif old_is_balance_paid and not new_is_balance_paid and amount > 0:
                cursor.execute("SELECT id FROM party WHERE id=%s AND deleted_at IS NULL LIMIT 1 FOR UPDATE", (customer_id,))
                if not cursor.fetchone():
                    raise DBError("客户不存在")
                ledger_note = f"销售单 {sales_no} 收款方式改出余额，退回余额"
                if clean_note:
                    ledger_note = f"{ledger_note}；{clean_note}"
                cursor.execute(
                    """
                    INSERT INTO customer_balance_ledger
                        (ledger_no, customer_id, entry_type, pay_type, amount, applied_amount,
                         balance_delta, related_month, note, created_by_user_id, created_at)
                    VALUES (%s, %s, 'balance_refund', 'balance', %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        self._ledger_no("CB"),
                        customer_id,
                        amount,
                        amount,
                        amount,
                        sales_at[:7],
                        ledger_note[:500],
                        operator_user_id,
                        now,
                    ),
                )
                balance_action = "balance_refund"

            old_payment_text = " / ".join(
                text for text in [_pay_status_text(old_pay_status), _pay_type_text(old_pay_type)] if text
            )
            new_payment_text = " / ".join(
                text for text in [_pay_status_text(clean_pay_status), _pay_type_text(clean_pay_type)] if text
            )
            payment_note = f"{now} 收款修改：{old_payment_text or '-'} -> {new_payment_text or '-'}"
            if clean_note:
                payment_note = f"{payment_note}；{clean_note}"
            cursor.execute(
                """
                UPDATE sales_order
                SET pay_status=%s,
                    pay_type=%s,
                    settlement_ledger_id=NULL,
                    settled_at=NULL,
                    note=CASE
                        WHEN note IS NULL OR note='' THEN %s
                        ELSE CONCAT(note, '\n', %s)
                    END,
                    updated_at=%s
                WHERE id=%s
                """,
                (clean_pay_status, clean_pay_type, payment_note, payment_note, now, int(sales_id)),
            )
        return {
            "code": 0,
            "data": {
                "id": int(sales_id),
                "sales_id": int(sales_id),
                "pay_status": clean_pay_status,
                "pay_status_text": _pay_status_text(clean_pay_status),
                "pay_type": clean_pay_type,
                "pay_type_text": _pay_type_text(clean_pay_type),
                "balance_action": balance_action,
            },
        }

    def delete_sales_order(self, sales_id: int, operator_user_id: Any = None) -> dict:
        self._ensure_operator_columns()
        self._ensure_sales_delete_columns()
        now = _now()
        operator_user_id = self._operator_user_id(operator_user_id)
        with self.transaction() as cursor:
            cursor.execute("SELECT * FROM sales_order WHERE id=%s FOR UPDATE", (sales_id,))
            sale = cursor.fetchone()
            if not sale:
                return {"code": 404, "msg": "销售单不存在"}
            if sale.get("status") in ("canceled", "deleted"):
                return {"code": 0, "data": {"id": sales_id, "already_deleted": True}}
            is_native_sale = sale.get("source") in ("native_api", "webui", "manual")
            if is_native_sale and sale.get("pay_status") == "paid" and sale.get("pay_type") == "balance":
                cursor.execute("SELECT id FROM party WHERE id=%s AND deleted_at IS NULL LIMIT 1 FOR UPDATE", (sale.get("customer_id"),))
                if not cursor.fetchone():
                    raise DBError("客户不存在")
            cursor.execute(
                """
                SELECT *
                FROM inventory_ledger
                WHERE biz_id=%s AND biz_type='sales_out'
                ORDER BY id ASC
                """,
                (sales_id,),
            )
            sales_out_ledgers = list(cursor.fetchall())
            for ledger in sales_out_ledgers:
                change_qty = Decimal(str(ledger.get("change_qty") or "0"))
                if change_qty >= 0:
                    continue
                sku = self._get_sku_for_update(cursor, int(ledger["sku_id"]))
                self._change_inventory(
                    cursor,
                    sku,
                    int(ledger["warehouse_id"]),
                    int(ledger["unit_id"]),
                    -change_qty,
                    "sales_delete",
                    sales_id,
                    int(ledger.get("biz_item_id") or 0) or None,
                    f"删除销售单 {sale.get('sales_no')}",
                    allow_negative=True,
                    operator_user_id=operator_user_id,
                )
            cursor.execute(
                """
                UPDATE sales_order
                SET status='deleted',
                    deleted_at=%s,
                    deleted_by_user_id=%s,
                    delete_reason='web delete',
                    canceled_at=%s,
                    canceled_by_user_id=%s,
                    cancel_reason='soft delete',
                    updated_at=%s
                WHERE id=%s
                """,
                (now, operator_user_id, now, operator_user_id, now, sales_id),
            )
            refund_amount = Decimal(str(sale.get("receivable_amount") or "0")).quantize(Decimal("0.01"))
            if is_native_sale and sale.get("pay_status") == "paid" and sale.get("pay_type") == "balance" and refund_amount > 0:
                cursor.execute(
                    """
                    INSERT INTO customer_balance_ledger
                        (ledger_no, customer_id, entry_type, pay_type, amount, applied_amount,
                         balance_delta, related_month, note, created_by_user_id, created_at)
                    VALUES (%s, %s, 'balance_refund', 'balance', %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        self._ledger_no("CB"),
                        int(sale.get("customer_id") or 0),
                        refund_amount,
                        refund_amount,
                        refund_amount,
                        str(sale.get("sales_at") or "")[:7],
                        f"删除销售单 {sale.get('sales_no')} 退回余额",
                        operator_user_id,
                        now,
                    ),
                )
            elif is_native_sale and sale.get("pay_status") == "paid" and sale.get("settlement_ledger_id") and refund_amount > 0:
                cursor.execute(
                    """
                    INSERT INTO customer_balance_ledger
                        (ledger_no, customer_id, entry_type, pay_type, amount, applied_amount,
                         balance_delta, related_month, note, created_by_user_id, created_at)
                    VALUES (%s, %s, 'settlement_refund', %s, %s, 0, %s, %s, %s, %s, %s)
                    """,
                    (
                        self._ledger_no("CB"),
                        int(sale.get("customer_id") or 0),
                        sale.get("pay_type") or "settlement",
                        refund_amount,
                        refund_amount,
                        str(sale.get("sales_at") or "")[:7],
                        f"删除已结月结销售单 {sale.get('sales_no')} 转入余额",
                        operator_user_id,
                        now,
                    ),
                )
        return {"code": 0, "data": {"id": sales_id}}

    def cancel_sales_order(self, sales_id: int, operator_user_id: Any = None) -> dict:
        return self.delete_sales_order(sales_id=sales_id, operator_user_id=operator_user_id)

    def sales_history_price(self, customer_id: int, product_id: int) -> float | None:
        sku_id = self.resolve_sku_id(product_id)
        if not sku_id:
            return None
        rows = self.query(
            """
            SELECT i.unit_price
            FROM sales_order_item i
            JOIN sales_order s ON s.id=i.sales_order_id
            WHERE s.customer_id=%s AND i.sku_id=%s AND s.status NOT IN ('canceled', 'deleted')
            ORDER BY s.sales_at DESC, i.id DESC
            LIMIT 1
            """,
            (customer_id, sku_id),
        )
        return float(rows[0]["unit_price"]) if rows else None

    def get_product_price(self, product_id: int) -> float | None:
        sku_id = self.resolve_sku_id(product_id)
        if not sku_id:
            return None
        rows = self.query("SELECT retail_price, min_price FROM product_sku WHERE id=%s LIMIT 1", (sku_id,))
        if not rows:
            return None
        value = rows[0].get("retail_price") or rows[0].get("min_price")
        return float(value) if value not in (None, "") else None

    # ---- management table reads ----

    def dashboard_summary(self) -> dict:
        rows = self.query(
            """
            SELECT COUNT(*) AS count, COALESCE(SUM(receivable_amount), 0) AS amount
            FROM sales_order
            WHERE sales_at >= CURDATE() AND sales_at < DATE_ADD(CURDATE(), INTERVAL 1 DAY)
              AND status NOT IN ('canceled', 'deleted')
            """
        )
        workflow_rows = self.query(
            """
            SELECT COUNT(*) AS count
            FROM workflow_order
            WHERE deleted_at IS NULL
              AND status <> 'completed'
              AND (COALESCE(is_made, 0) <> 1 OR COALESCE(is_delivered, 0) <> 1)
            """
        )
        sales = rows[0] if rows else {}
        workflow = workflow_rows[0] if workflow_rows else {}
        return {
            "today_sales_count": int(sales.get("count") or 0),
            "today_sales_amount": _money(sales.get("amount") or 0),
            "pending_workflow_count": int(workflow.get("count") or 0),
            "updated_at": int(time.time()),
        }

    def stock_documents(self, keyword: str = "", page: int = 1, page_size: int = 50) -> tuple[list[dict], int]:
        where = ["1=1"]
        params: list[Any] = []
        if keyword:
            like = f"%{keyword}%"
            where.append("(d.doc_no LIKE %s OR d.doc_type LIKE %s OR w.name LIKE %s OR d.note LIKE %s)")
            params.extend([like, like, like, like])
        where_sql = " AND ".join(where)
        total_rows = self.query(
            f"SELECT COUNT(*) AS total FROM stock_document d JOIN warehouse w ON w.id=d.warehouse_id WHERE {where_sql}",
            params,
        )
        rows = self.query(
            f"""
            SELECT d.*, w.name AS warehouse_name, p.name AS party_name,
                   wu.display_name AS created_by_name, wu.username AS created_by_username
            FROM stock_document d
            JOIN warehouse w ON w.id=d.warehouse_id
            LEFT JOIN party p ON p.id=d.related_party_id
            LEFT JOIN auth_user wu ON wu.id=d.created_by_user_id
            WHERE {where_sql}
            ORDER BY d.created_at DESC, d.id DESC
            LIMIT %s OFFSET %s
            """,
            params + [page_size, (max(1, page) - 1) * page_size],
        )
        return rows, int(total_rows[0].get("total") or 0) if total_rows else 0

    def stocktakes(self, keyword: str = "", page: int = 1, page_size: int = 50) -> tuple[list[dict], int]:
        where = ["1=1"]
        params: list[Any] = []
        if keyword:
            like = f"%{keyword}%"
            where.append("(o.stocktake_no LIKE %s OR w.name LIKE %s OR o.note LIKE %s)")
            params.extend([like, like, like])
        where_sql = " AND ".join(where)
        total_rows = self.query(f"SELECT COUNT(*) AS total FROM stocktake_order o JOIN warehouse w ON w.id=o.warehouse_id WHERE {where_sql}", params)
        rows = self.query(
            f"""
            SELECT o.*, w.name AS warehouse_name,
                   wu.display_name AS created_by_name, wu.username AS created_by_username
            FROM stocktake_order o
            JOIN warehouse w ON w.id=o.warehouse_id
            LEFT JOIN auth_user wu ON wu.id=o.created_by_user_id
            WHERE {where_sql}
            ORDER BY o.created_at DESC, o.id DESC
            LIMIT %s OFFSET %s
            """,
            params + [page_size, (max(1, page) - 1) * page_size],
        )
        return rows, int(total_rows[0].get("total") or 0) if total_rows else 0

    def transfers(self, keyword: str = "", page: int = 1, page_size: int = 50) -> tuple[list[dict], int]:
        where = ["1=1"]
        params: list[Any] = []
        if keyword:
            like = f"%{keyword}%"
            where.append("(t.transfer_no LIKE %s OR fw.name LIKE %s OR tw.name LIKE %s OR t.note LIKE %s)")
            params.extend([like, like, like, like])
        where_sql = " AND ".join(where)
        total_rows = self.query(
            f"SELECT COUNT(*) AS total FROM transfer_order t JOIN warehouse fw ON fw.id=t.from_warehouse_id JOIN warehouse tw ON tw.id=t.to_warehouse_id WHERE {where_sql}",
            params,
        )
        rows = self.query(
            f"""
            SELECT t.*, fw.name AS from_warehouse_name, tw.name AS to_warehouse_name,
                   wu.display_name AS created_by_name, wu.username AS created_by_username
            FROM transfer_order t
            JOIN warehouse fw ON fw.id=t.from_warehouse_id
            JOIN warehouse tw ON tw.id=t.to_warehouse_id
            LEFT JOIN auth_user wu ON wu.id=t.created_by_user_id
            WHERE {where_sql}
            ORDER BY t.created_at DESC, t.id DESC
            LIMIT %s OFFSET %s
            """,
            params + [page_size, (max(1, page) - 1) * page_size],
        )
        return rows, int(total_rows[0].get("total") or 0) if total_rows else 0


def get_native_db_client() -> NativeDBClient:
    return NativeDBClient()
