"""Create and import the native product catalog.

This script reads the current ShopXO/ERP product tables and writes the new
North-Star-owned product tables into a separate schema. It is idempotent:
legacy ids are kept only in migration_product_ref, not in product business
tables.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pymysql
from dotenv import load_dotenv
from pymysql.cursors import DictCursor

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.config import get_config  # noqa: E402


DEFAULT_TARGET_DB = "sjagent_core"
CASE_UNIT_ID = 6


CATEGORY_CODES = {
    "半斤礼盒": "gift_box_half_jin",
    "三两礼盒": "gift_box_3liang",
    "二两礼盒": "gift_box_2liang",
    "一两礼盒": "gift_box_1liang",
    "大红袍泡袋": "bag_dahongpao",
    "水仙泡袋": "bag_shuixian",
    "肉桂泡袋": "bag_rougui",
    "纯色泡袋": "bag_plain_color",
    "公版泡袋": "bag_public",
    "pvc礼盒": "gift_box_pvc",
    "品种茶泡袋": "bag_variety_tea",
    "红茶泡袋": "bag_black_tea",
    "五格礼盒": "gift_box_5_grid",
    "2泡礼盒": "gift_box_2_bubble",
    "其他产品": "other_product",
    "6小盒礼盒": "gift_box_6_small",
    "3小盒礼盒": "gift_box_3_small",
    "快递纸箱": "shipping_carton",
    "品种茶袋": "bag_variety_tea_pack",
    "空白泡袋": "bag_blank",
    "宽版泡袋": "bag_wide",
    "2泡小盒": "gift_box_2_bubble_small",
}

UNIT_CODES = {
    "套": ("set", "sale", 0),
    "捆": ("bundle", "sale", 0),
    "个": ("piece", "sale", 0),
    "斤": ("jin", "weight", 2),
    "张": ("sheet", "sale", 0),
    "件": ("case", "package", 0),
}


def quote_ident(name: str) -> str:
    if not re.fullmatch(r"[0-9A-Za-z_]+", name or ""):
        raise ValueError(f"Unsafe database/table identifier: {name!r}")
    return f"`{name}`"


def compact_text(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "").replace("【", "").replace("】", "")).lower()


def normalize_alias(value: Any) -> str:
    return compact_text(value).replace("-", "").replace("_", "")


def as_dt(value: Any) -> datetime:
    try:
        ts = int(value or 0)
    except (TypeError, ValueError):
        ts = 0
    if ts > 0:
        return datetime.fromtimestamp(ts)
    return datetime.now()


def as_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def first_non_empty(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def extract_urls(value: Any) -> list[str]:
    text = str(value or "").strip()
    if not text:
        return []
    urls: list[str] = []

    def add(url: str):
        url = (url or "").strip().strip("\"'")
        if url and url not in urls:
            urls.append(url)

    try:
        decoded = json.loads(text)
        queue = decoded if isinstance(decoded, list) else [decoded]
        while queue:
            item = queue.pop(0)
            if isinstance(item, str):
                add(item)
            elif isinstance(item, dict):
                for key in ("url", "src", "images", "image"):
                    if key in item:
                        queue.append(item[key])
    except Exception:
        pass

    for match in re.findall(r'https?://[^"\'<>\s]+', text):
        add(match)
    return urls


def url_path(url: str) -> str:
    try:
        return urlparse(url).path.lstrip("/")
    except Exception:
        return ""


def file_name_from_url(url: str) -> str:
    path = url_path(url)
    return path.rsplit("/", 1)[-1] if path else ""


def mime_from_url(url: str) -> str:
    lower = url.lower().split("?", 1)[0]
    if lower.endswith(".png"):
        return "image/png"
    if lower.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    if lower.endswith(".webp"):
        return "image/webp"
    if lower.endswith(".gif"):
        return "image/gif"
    return ""


def storage_from_url(url: str) -> str:
    lower = url.lower()
    if "oss-" in lower or "img.513sjbz.com" in lower:
        return "oss"
    return "legacy"


def extract_series_size(title: str) -> tuple[str, str]:
    text = str(title or "").strip()
    match = re.match(r"^【([^】]+)】\s*(.*)$", text)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    match = re.match(r"^\[([^\]]+)\]\s*(.*)$", text)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return "", text


def parse_case_pack_qty(simple_desc: str) -> Decimal | None:
    text = str(simple_desc or "")
    patterns = [
        r"([0-9]+(?:\.[0-9]+)?)\s*(?:套|个|捆|张)?\s*/\s*件",
        r"1\s*件\s*[=＝]\s*([0-9]+(?:\.[0-9]+)?)\s*(?:套|个|捆|张)?",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return as_decimal(match.group(1))
    return None


def category_product_type(name: str) -> str:
    text = str(name or "").lower()
    if "泡袋" in text or text.endswith("袋") or "茶袋" in text:
        return "bag"
    if "礼盒" in text or "小盒" in text or "pvc" in text:
        return "gift_box"
    if "快递" in text or "纸箱" in text:
        return "shipping"
    if "服务" in text or "烫金" in text or "丝印" in text or "uv" in text:
        return "service"
    return "other"


def product_type_from_categories(category_names: list[str]) -> str:
    counts = Counter(category_product_type(name) for name in category_names if name)
    if not counts:
        return "other"
    for preferred in ("gift_box", "bag", "shipping", "service", "other"):
        if counts.get(preferred):
            return preferred
    return counts.most_common(1)[0][0]


def default_unit_for_product_type(product_type: str) -> int:
    return {
        "gift_box": 1,
        "bag": 2,
        "shipping": 3,
        "material": 3,
        "service": 3,
        "other": 3,
    }.get(product_type, 3)


def inventory_policy(product_type: str) -> str:
    if product_type == "gift_box":
        return "strict"
    if product_type == "bag":
        return "none"
    if product_type == "service":
        return "none"
    return "weak"


def purchase_policy(product_type: str, series: str, one_case_series: set[str]) -> str:
    if product_type == "gift_box":
        return "one_case" if series in one_case_series else "order_qty"
    if product_type == "bag":
        return "none"
    return "order_qty"


def infer_bag_type(title: str, category_names: list[str]) -> str:
    text = "".join([title or "", *category_names])
    if "宽版" in text:
        return "宽版"
    if "空白" in text:
        return "空白"
    if "红茶" in text:
        return "红茶袋"
    if "短泡袋" in text or "短袋" in text:
        return "短泡袋"
    if "长泡袋" in text or "长袋" in text:
        return "长泡袋"
    return ""


def infer_tea_type(title: str, category_names: list[str]) -> str:
    text = "".join([title or "", *category_names])
    for tea in ("肉桂", "水仙", "大红袍", "红茶", "品种茶"):
        if tea in text:
            return tea
    return ""


def infer_material_type(title: str, category_names: list[str]) -> str:
    text = "".join([title or "", *category_names])
    for word in ("纸箱", "快递纸箱", "内衬袋", "标签", "提袋", "PVC", "pvc"):
        if word in text:
            return "PVC" if word.lower() == "pvc" else word
    return ""


def infer_service_type(title: str) -> str:
    text = str(title or "")
    for word in ("烫金", "UV", "uv", "丝印", "机器包茶", "入盒", "烫膜"):
        if word in text:
            return "UV" if word.lower() == "uv" else word
    return ""


def category_code(name: str, category_id: int) -> str:
    return CATEGORY_CODES.get(str(name or ""), f"category_{category_id}")


def category_default_unit_id(name: str) -> int:
    product_type = category_product_type(name)
    return default_unit_for_product_type(product_type)


class ProductCatalogMigrator:
    def __init__(self, source_db: str, target_db: str):
        self.source_db = source_db
        self.target_db = target_db
        self.config = get_config()
        self.db_config = self.config.db_config
        self.target_db_config = self.build_target_db_config(target_db)
        self.report: dict[str, Any] = {
            "source_db": source_db,
            "target_db": target_db,
            "started_at": datetime.now().isoformat(timespec="seconds"),
            "counts": {},
            "warnings": [],
        }
        self.standard_colors = set(self.config.get("business_rules.color_filter.standard_colors", []) or [])
        self.color_aliases = self.config.get("business_rules.color_filter.aliases", {}) or {}
        self.one_case_series = set(self.config.get("business_rules.unit_conversion.one_piece_series", []) or [])
        self.category_names: dict[int, str] = {}

    def build_target_db_config(self, target_db: str) -> dict:
        cfg = dict(self.db_config)
        cfg["host"] = os.getenv("SJAGENT_CORE_DB_HOST") or os.getenv("SJAGENT_CORE_HOST") or cfg["host"]
        cfg["port"] = int(os.getenv("SJAGENT_CORE_DB_PORT") or os.getenv("SJAGENT_CORE_PORT") or cfg["port"])
        cfg["name"] = os.getenv("SJAGENT_CORE_DB_NAME") or os.getenv("SJAGENT_CORE_DB") or target_db
        cfg["user"] = os.getenv("SJAGENT_CORE_DB_USER") or os.getenv("SJAGENT_CORE_USER") or cfg["user"]
        cfg["password"] = os.getenv("SJAGENT_CORE_DB_PASSWORD") or os.getenv("SJAGENT_CORE_PASSWORD") or cfg["password"]
        cfg["charset"] = os.getenv("SJAGENT_CORE_DB_CHARSET") or cfg.get("charset") or "utf8mb4"
        return cfg

    def connect_with_config(self, cfg: dict, database: str | None):
        return pymysql.connect(
            host=cfg["host"],
            port=int(cfg["port"]),
            user=cfg["user"],
            password=cfg["password"],
            database=database,
            charset=cfg.get("charset") or "utf8mb4",
            cursorclass=DictCursor,
            autocommit=False,
        )

    def connect_source(self, database: str | None = None):
        cfg = self.db_config
        return self.connect_with_config(cfg, database if database is not None else self.source_db)

    def connect_target(self, database: str | None = None):
        return self.connect_with_config(
            self.target_db_config,
            database if database is not None else self.target_db,
        )

    def connect_target_server(self):
        return self.connect_with_config(self.target_db_config, None)

    def table(self, name: str) -> str:
        return f"{quote_ident(self.target_db)}.{quote_ident(name)}"

    def source_table(self, name: str) -> str:
        return f"{quote_ident(self.source_db)}.{quote_ident(name)}"

    def execute(self, cursor, sql: str, params: tuple | list | None = None) -> int:
        return cursor.execute(sql, params)

    def executemany(self, cursor, sql: str, params: list[tuple]) -> int:
        if not params:
            return 0
        return cursor.executemany(sql, params)

    def query(self, cursor, sql: str, params: tuple | list | None = None) -> list[dict]:
        cursor.execute(sql, params)
        return list(cursor.fetchall())

    def ddl_statements(self) -> list[str]:
        return [
            f"""
            CREATE TABLE IF NOT EXISTS {self.table('product_unit')} (
                id BIGINT UNSIGNED NOT NULL,
                name VARCHAR(30) NOT NULL,
                code VARCHAR(30) NOT NULL,
                unit_type VARCHAR(30) NOT NULL,
                precision_scale TINYINT NOT NULL DEFAULT 0,
                is_enabled TINYINT NOT NULL DEFAULT 1,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                PRIMARY KEY (id),
                UNIQUE KEY uk_product_unit_code (code),
                UNIQUE KEY uk_product_unit_name (name)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            f"""
            CREATE TABLE IF NOT EXISTS {self.table('product_category')} (
                id BIGINT UNSIGNED NOT NULL,
                parent_id BIGINT UNSIGNED NULL,
                code VARCHAR(80) NULL,
                name VARCHAR(80) NOT NULL,
                product_type VARCHAR(30) NOT NULL,
                inventory_policy VARCHAR(20) NULL,
                default_unit_id BIGINT UNSIGNED NULL,
                sort_order INT NULL,
                is_enabled TINYINT NOT NULL DEFAULT 1,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                PRIMARY KEY (id),
                KEY idx_product_category_parent (parent_id),
                KEY idx_product_category_type (product_type),
                UNIQUE KEY uk_product_category_code (code)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            f"""
            CREATE TABLE IF NOT EXISTS {self.table('product_spu')} (
                id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                title VARCHAR(160) NOT NULL,
                product_type VARCHAR(30) NOT NULL,
                series VARCHAR(80) NULL,
                size_label VARCHAR(80) NULL,
                available_colors JSON NULL,
                tea_type VARCHAR(80) NULL,
                case_unit_id BIGINT UNSIGNED NULL,
                case_pack_qty DECIMAL(12,3) NULL,
                default_category_id BIGINT UNSIGNED NULL,
                default_supplier_id BIGINT UNSIGNED NULL,
                inventory_policy VARCHAR(20) NOT NULL DEFAULT 'strict',
                purchase_policy VARCHAR(30) NOT NULL DEFAULT 'order_qty',
                status VARCHAR(20) NOT NULL DEFAULT 'active',
                sort_order INT NULL,
                note TEXT NULL,
                source VARCHAR(30) NOT NULL DEFAULT 'manual',
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                deleted_at DATETIME NULL,
                PRIMARY KEY (id),
                KEY idx_product_spu_type (product_type),
                KEY idx_product_spu_series (series),
                KEY idx_product_spu_category (default_category_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            f"""
            CREATE TABLE IF NOT EXISTS {self.table('product_sku')} (
                id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                spu_id BIGINT UNSIGNED NOT NULL,
                sku_no VARCHAR(80) NOT NULL,
                primary_category_id BIGINT UNSIGNED NULL,
                category_ids JSON NULL,
                color VARCHAR(60) NULL,
                bag_type VARCHAR(40) NULL,
                tea_type VARCHAR(80) NULL,
                material_type VARCHAR(80) NULL,
                service_type VARCHAR(80) NULL,
                unit_id BIGINT UNSIGNED NOT NULL,
                min_purchase_qty DECIMAL(12,3) NULL,
                min_purchase_unit_id BIGINT UNSIGNED NULL,
                inventory_policy VARCHAR(20) NOT NULL DEFAULT 'strict',
                purchase_policy VARCHAR(30) NOT NULL DEFAULT 'order_qty',
                default_warehouse_id BIGINT UNSIGNED NULL,
                default_supplier_id BIGINT UNSIGNED NULL,
                retail_price DECIMAL(12,2) NULL,
                min_price DECIMAL(12,2) NULL,
                max_price DECIMAL(12,2) NULL,
                cost_price DECIMAL(12,2) NULL,
                price_note VARCHAR(255) NULL,
                is_stock_item TINYINT NOT NULL DEFAULT 1,
                is_sellable TINYINT NOT NULL DEFAULT 1,
                is_listed TINYINT NOT NULL DEFAULT 0,
                status VARCHAR(20) NOT NULL DEFAULT 'active',
                main_image_url VARCHAR(500) NULL,
                detail_image_urls JSON NULL,
                content_html MEDIUMTEXT NULL,
                search_text TEXT NULL,
                source VARCHAR(30) NOT NULL DEFAULT 'manual',
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                deleted_at DATETIME NULL,
                PRIMARY KEY (id),
                UNIQUE KEY uk_product_sku_no (sku_no),
                KEY idx_product_sku_spu (spu_id),
                KEY idx_product_sku_category (primary_category_id),
                KEY idx_product_sku_color (color),
                KEY idx_product_sku_status (status)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            f"""
            CREATE TABLE IF NOT EXISTS {self.table('product_alias')} (
                id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                target_type VARCHAR(20) NOT NULL,
                target_id BIGINT UNSIGNED NOT NULL,
                alias VARCHAR(160) NOT NULL,
                normalized_alias VARCHAR(160) NOT NULL,
                alias_type VARCHAR(30) NOT NULL,
                weight INT NOT NULL DEFAULT 10,
                is_enabled TINYINT NOT NULL DEFAULT 1,
                source VARCHAR(30) NOT NULL DEFAULT 'manual',
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                PRIMARY KEY (id),
                UNIQUE KEY uk_product_alias (target_type, target_id, normalized_alias, alias_type),
                KEY idx_product_alias_normalized (normalized_alias)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            f"""
            CREATE TABLE IF NOT EXISTS {self.table('product_media')} (
                id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                sku_id BIGINT UNSIGNED NULL,
                spu_id BIGINT UNSIGNED NULL,
                media_type VARCHAR(30) NOT NULL,
                url VARCHAR(500) NOT NULL,
                storage VARCHAR(30) NOT NULL,
                path VARCHAR(500) NULL,
                file_name VARCHAR(255) NULL,
                mime_type VARCHAR(80) NULL,
                width INT NULL,
                height INT NULL,
                sha256 CHAR(64) NULL,
                sort_order INT NOT NULL DEFAULT 0,
                is_active TINYINT NOT NULL DEFAULT 1,
                source VARCHAR(30) NOT NULL DEFAULT 'manual',
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                PRIMARY KEY (id),
                KEY idx_product_media_sku (sku_id),
                KEY idx_product_media_spu (spu_id),
                KEY idx_product_media_type (media_type)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            f"""
            CREATE TABLE IF NOT EXISTS {self.table('migration_product_ref')} (
                id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                entity_type VARCHAR(20) NOT NULL,
                native_id BIGINT UNSIGNED NOT NULL,
                source_table VARCHAR(120) NOT NULL,
                external_id VARCHAR(120) NOT NULL,
                external_key VARCHAR(160) NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                PRIMARY KEY (id),
                UNIQUE KEY uk_migration_product_ref (entity_type, source_table, external_id),
                KEY idx_migration_product_ref_native (entity_type, native_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
        ]

    def create_schema(self):
        try:
            with self.connect_target_server() as conn:
                with conn.cursor() as cursor:
                    self.execute(
                        cursor,
                        f"CREATE DATABASE IF NOT EXISTS {quote_ident(self.target_db)} "
                        "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci",
                    )
                    for sql in self.ddl_statements():
                        self.execute(cursor, sql)
                conn.commit()
        except pymysql.OperationalError as exc:
            code = int(exc.args[0]) if exc.args else 0
            if code not in (1044, 1045, 1049):
                raise
            self.warn(
                "target_db_create_skipped",
                "目标库账号不能执行 CREATE DATABASE，已改为直接连接已存在的目标库建表",
                {"target_db": self.target_db, "mysql_error": code},
            )
            with self.connect_target() as conn:
                with conn.cursor() as cursor:
                    for sql in self.ddl_statements():
                        self.execute(cursor, sql)
                conn.commit()

    def import_data(self):
        with self.connect_source() as source_conn, self.connect_target() as target_conn:
            with source_conn.cursor() as source_cursor, target_conn.cursor() as target_cursor:
                self.import_units(source_cursor, target_cursor)
                self.import_categories(source_cursor, target_cursor)
                products = self.load_products(source_cursor)
                category_map = self.load_category_map(source_cursor)
                sync_map = self.load_sync_map(source_cursor)
                spu_by_group = self.import_spus(target_cursor, products, category_map)
                self.import_skus(target_cursor, products, category_map, sync_map, spu_by_group)
                self.refresh_report_counts(source_cursor, target_cursor)
            target_conn.commit()
        self.report["finished_at"] = datetime.now().isoformat(timespec="seconds")

    def import_units(self, source_cursor, target_cursor):
        now = datetime.now()
        rows = self.query(source_cursor, f"SELECT id, name, is_enable, add_time, upd_time FROM {self.source_table('sxo_plugins_erp_unit')} ORDER BY id")
        seen = set()
        for row in rows:
            unit_id = int(row["id"])
            name = str(row["name"] or "").strip()
            code, unit_type, precision = UNIT_CODES.get(name, (f"unit_{unit_id}", "sale", 0))
            seen.add(name)
            self.execute(
                target_cursor,
                f"""
                INSERT INTO {self.table('product_unit')}
                    (id, name, code, unit_type, precision_scale, is_enabled, created_at, updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE
                    name=VALUES(name), code=VALUES(code), unit_type=VALUES(unit_type),
                    precision_scale=VALUES(precision_scale), is_enabled=VALUES(is_enabled),
                    updated_at=VALUES(updated_at)
                """,
                (
                    unit_id,
                    name,
                    code,
                    unit_type,
                    precision,
                    int(row.get("is_enable") or 0),
                    as_dt(row.get("add_time")),
                    as_dt(row.get("upd_time")),
                ),
            )
        if "件" not in seen:
            self.execute(
                target_cursor,
                f"""
                INSERT INTO {self.table('product_unit')}
                    (id, name, code, unit_type, precision_scale, is_enabled, created_at, updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE
                    name=VALUES(name), code=VALUES(code), unit_type=VALUES(unit_type),
                    precision_scale=VALUES(precision_scale), is_enabled=VALUES(is_enabled),
                    updated_at=VALUES(updated_at)
                """,
                (CASE_UNIT_ID, "件", "case", "package", 0, 1, now, now),
            )

    def import_categories(self, source_cursor, target_cursor):
        rows = self.query(
            source_cursor,
            f"SELECT id, pid, name, sort, is_enable, add_time, upd_time FROM {self.source_table('sxo_plugins_erp_product_category')} ORDER BY id",
        )
        self.category_names = {int(row["id"]): str(row["name"] or "").strip() for row in rows}
        for row in rows:
            category_id = int(row["id"])
            name = str(row["name"] or "").strip()
            product_type = category_product_type(name)
            self.execute(
                target_cursor,
                f"""
                INSERT INTO {self.table('product_category')}
                    (id, parent_id, code, name, product_type, inventory_policy, default_unit_id,
                     sort_order, is_enabled, created_at, updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE
                    parent_id=VALUES(parent_id), code=VALUES(code), name=VALUES(name),
                    product_type=VALUES(product_type), inventory_policy=VALUES(inventory_policy),
                    default_unit_id=VALUES(default_unit_id), sort_order=VALUES(sort_order),
                    is_enabled=VALUES(is_enabled), updated_at=VALUES(updated_at)
                """,
                (
                    category_id,
                    int(row.get("pid") or 0) or None,
                    category_code(name, category_id),
                    name,
                    product_type,
                    inventory_policy(product_type),
                    category_default_unit_id(name),
                    int(row.get("sort") or 0),
                    int(row.get("is_enable") or 0),
                    as_dt(row.get("add_time")),
                    as_dt(row.get("upd_time")),
                ),
            )

    def load_products(self, cursor) -> list[dict]:
        return self.query(
            cursor,
            f"""
            SELECT
                p.id, p.group_key, p.status, p.title, p.spec, p.coding AS product_coding,
                p.simple_desc, p.images, p.main_images, p.price AS product_price,
                p.min_price, p.max_price, p.cost_price AS product_cost_price,
                p.content, p.note, p.default_supplier_id, p.add_time, p.upd_time,
                pb.unit_id AS base_unit_id, pb.coding AS base_coding,
                pb.price AS base_price, pb.cost_price AS base_cost_price
            FROM {self.source_table('sxo_plugins_erp_product')} p
            LEFT JOIN {self.source_table('sxo_plugins_erp_product_base')} pb ON pb.product_id = p.id
            ORDER BY p.id
            """,
        )

    def load_category_map(self, cursor) -> dict[int, list[int]]:
        rows = self.query(
            cursor,
            f"""
            SELECT product_id, product_category_id
            FROM {self.source_table('sxo_plugins_erp_product_category_join')}
            ORDER BY product_id, product_category_id
            """,
        )
        mapping: dict[int, list[int]] = defaultdict(list)
        for row in rows:
            mapping[int(row["product_id"])].append(int(row["product_category_id"]))
        return {key: sorted(set(value)) for key, value in mapping.items()}

    def load_sync_map(self, cursor) -> dict[int, dict]:
        rows = self.query(
            cursor,
            f"""
            SELECT l.product_id, l.goods_id, g.is_shelves, g.images AS goods_images, g.content_web
            FROM {self.source_table('sxo_plugins_erp_system_goods_sync_product_log')} l
            JOIN (
                SELECT product_id, MAX(add_time) AS max_add_time
                FROM {self.source_table('sxo_plugins_erp_system_goods_sync_product_log')}
                GROUP BY product_id
            ) latest ON latest.product_id = l.product_id AND latest.max_add_time = l.add_time
            LEFT JOIN {self.source_table('sxo_goods')} g ON g.id = l.goods_id
            ORDER BY l.product_id, l.id DESC
            """,
        )
        sync: dict[int, dict] = {}
        for row in rows:
            product_id = int(row["product_id"])
            sync.setdefault(product_id, row)
        return sync

    def ref_map(self, cursor, entity_type: str, source_table: str) -> dict[str, int]:
        rows = self.query(
            cursor,
            f"""
            SELECT external_id, native_id
            FROM {self.table('migration_product_ref')}
            WHERE entity_type=%s AND source_table=%s
            """,
            (entity_type, source_table),
        )
        return {str(row["external_id"]): int(row["native_id"]) for row in rows}

    def upsert_ref(self, cursor, entity_type: str, native_id: int, source_table: str, external_id: str, external_key: str = ""):
        now = datetime.now()
        self.execute(
            cursor,
            f"""
            INSERT INTO {self.table('migration_product_ref')}
                (entity_type, native_id, source_table, external_id, external_key, created_at, updated_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE
                native_id=VALUES(native_id), external_key=VALUES(external_key), updated_at=VALUES(updated_at)
            """,
            (entity_type, native_id, source_table, external_id, external_key or None, now, now),
        )

    def import_spus(self, cursor, products: list[dict], category_map: dict[int, list[int]]) -> dict[str, int]:
        existing_refs = self.ref_map(cursor, "spu", "sxo_plugins_erp_product.group_key")
        by_group: dict[str, list[dict]] = defaultdict(list)
        for product in products:
            by_group[str(product.get("group_key") or product["id"])].append(product)

        spu_by_group: dict[str, int] = {}
        for group_key, rows in by_group.items():
            rows = sorted(rows, key=lambda item: int(item["id"]))
            first = rows[0]
            title = self.common_value(rows, "title") or str(first.get("title") or "")
            series, size_label = extract_series_size(title)
            category_ids = sorted({cid for row in rows for cid in category_map.get(int(row["id"]), [])})
            category_names = [self.category_names.get(cid, "") for cid in category_ids]
            product_type = product_type_from_categories(category_names)
            colors = [
                color
                for color in (self.standardize_color(row.get("spec")) for row in rows)
                if color
            ]
            available_colors = sorted(set(colors), key=colors.index)
            case_values = [parse_case_pack_qty(str(row.get("simple_desc") or "")) for row in rows]
            non_empty_case_values = [value for value in case_values if value is not None]
            case_pack_qty = non_empty_case_values[0] if non_empty_case_values else None
            if len(set(non_empty_case_values)) > 1:
                self.warn("case_pack_conflict", f"SPU {title} 的每件数量不一致，先取 {case_pack_qty}", {"group_key": group_key})
            primary_category_id = self.choose_primary_category(category_ids, title)
            tea_type = infer_tea_type(title, category_names)
            created_at = min(as_dt(row.get("add_time")) for row in rows)
            updated_at = max(as_dt(row.get("upd_time")) for row in rows)
            default_supplier_id = int(first.get("default_supplier_id") or 0) or None
            policy = purchase_policy(product_type, series, self.one_case_series)
            status = "active" if all(int(row.get("status") or 0) == 0 for row in rows) else "inactive"
            spu_id = existing_refs.get(group_key)
            params = (
                title,
                product_type,
                series or None,
                size_label or None,
                json_text(available_colors),
                tea_type or None,
                CASE_UNIT_ID if case_pack_qty is not None else None,
                case_pack_qty,
                primary_category_id,
                default_supplier_id,
                inventory_policy(product_type),
                policy,
                status,
                int(first.get("id") or 0),
                str(first.get("note") or "") or None,
                "migration",
                created_at,
                updated_at,
                None,
            )
            if spu_id:
                self.execute(
                    cursor,
                    f"""
                    UPDATE {self.table('product_spu')}
                    SET title=%s, product_type=%s, series=%s, size_label=%s, available_colors=%s,
                        tea_type=%s, case_unit_id=%s, case_pack_qty=%s, default_category_id=%s,
                        default_supplier_id=%s, inventory_policy=%s, purchase_policy=%s, status=%s,
                        sort_order=%s, note=%s, source=%s, created_at=%s, updated_at=%s, deleted_at=%s
                    WHERE id=%s
                    """,
                    (*params, spu_id),
                )
            else:
                self.execute(
                    cursor,
                    f"""
                    INSERT INTO {self.table('product_spu')}
                        (title, product_type, series, size_label, available_colors, tea_type,
                         case_unit_id, case_pack_qty, default_category_id, default_supplier_id,
                         inventory_policy, purchase_policy, status, sort_order, note, source,
                         created_at, updated_at, deleted_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    params,
                )
                spu_id = cursor.lastrowid
            self.upsert_ref(cursor, "spu", int(spu_id), "sxo_plugins_erp_product.group_key", group_key, title)
            spu_by_group[group_key] = int(spu_id)
        return spu_by_group

    def import_skus(
        self,
        cursor,
        products: list[dict],
        category_map: dict[int, list[int]],
        sync_map: dict[int, dict],
        spu_by_group: dict[str, int],
    ):
        sku_refs = self.ref_map(cursor, "sku", "sxo_plugins_erp_product.id")
        existing_sku_rows = self.query(cursor, f"SELECT id, sku_no FROM {self.table('product_sku')}")
        sku_no_by_id = {int(row["id"]): str(row["sku_no"]) for row in existing_sku_rows}
        allocated_sku_nos = set(sku_no_by_id.values())

        self.execute(cursor, f"DELETE FROM {self.table('product_alias')} WHERE source='migration'")
        self.execute(cursor, f"DELETE FROM {self.table('product_media')} WHERE source='migration'")

        duplicate_sku_sources: list[dict] = []
        nonstandard_specs: Counter[str] = Counter()
        alias_rows: list[tuple] = []
        media_rows: list[tuple] = []
        for product in products:
            product_id = int(product["id"])
            group_key = str(product.get("group_key") or product_id)
            spu_id = spu_by_group[group_key]
            category_ids = category_map.get(product_id, [])
            category_names = [self.category_names.get(cid, "") for cid in category_ids]
            product_type = product_type_from_categories(category_names)
            series, size_label = extract_series_size(str(product.get("title") or ""))
            primary_category_id = self.choose_primary_category(category_ids, str(product.get("title") or ""))
            color = self.standardize_color(product.get("spec"))
            if product.get("spec") and not color:
                nonstandard_specs[str(product.get("spec") or "").strip()] += 1
            existing_sku_id = sku_refs.get(str(product_id))
            existing_sku_no = sku_no_by_id.get(existing_sku_id) if existing_sku_id else None
            if existing_sku_no:
                sku_no = existing_sku_no
            else:
                preferred_sku_no = self.preferred_sku_no(product)
                sku_no = preferred_sku_no
                if sku_no in allocated_sku_nos:
                    generated = f"SJ{product_id:06d}"
                    duplicate_sku_sources.append({"old_product_id": product_id, "preferred": preferred_sku_no, "generated": generated})
                    sku_no = generated
                while sku_no in allocated_sku_nos:
                    sku_no = f"SJ{product_id:06d}{len(allocated_sku_nos) % 10}"
                allocated_sku_nos.add(sku_no)

            sync = sync_map.get(product_id, {})
            main_url, detail_urls = self.product_images(product, sync)
            unit_id = int(product.get("base_unit_id") or 0) or default_unit_for_product_type(product_type)
            retail_price = as_decimal(first_non_empty(product.get("base_price"), product.get("product_price")))
            cost_price = as_decimal(first_non_empty(product.get("base_cost_price"), product.get("product_cost_price")))
            min_price = as_decimal(product.get("min_price")) or retail_price
            max_price = as_decimal(product.get("max_price")) or retail_price
            status = "active" if int(product.get("status") or 0) == 0 else "inactive"
            is_sellable = 1 if status == "active" else 0
            is_listed = int(sync.get("is_shelves") or 0)
            tea_type = infer_tea_type(str(product.get("title") or ""), category_names)
            material_type = infer_material_type(str(product.get("title") or ""), category_names)
            service_type = infer_service_type(str(product.get("title") or ""))
            sku_purchase_policy = purchase_policy(product_type, series, self.one_case_series)
            min_purchase_qty = Decimal("1") if sku_purchase_policy == "one_case" else None
            min_purchase_unit_id = CASE_UNIT_ID if sku_purchase_policy == "one_case" else None
            display_title = str(product.get("title") or "")
            spoken_name = "".join(part for part in [series, size_label, color or ""] if part)
            search_text = " ".join(
                part
                for part in [
                    sku_no,
                    display_title,
                    spoken_name,
                    color,
                    " ".join(category_names),
                    product.get("simple_desc"),
                ]
                if part
            )
            content_html = first_non_empty(product.get("content"), sync.get("content_web")) or None
            params = (
                spu_id,
                sku_no,
                primary_category_id,
                json_text(category_ids),
                color,
                infer_bag_type(str(product.get("title") or ""), category_names) or None,
                tea_type or None,
                material_type or None,
                service_type or None,
                unit_id,
                min_purchase_qty,
                min_purchase_unit_id,
                inventory_policy(product_type),
                sku_purchase_policy,
                int(self.config.get("erp.warehouse.baixin", 2)),
                int(product.get("default_supplier_id") or 0) or None,
                retail_price,
                min_price,
                max_price,
                cost_price,
                None,
                0 if product_type == "service" else 1,
                is_sellable,
                is_listed,
                status,
                main_url or None,
                json_text(detail_urls),
                content_html,
                search_text,
                "migration",
                as_dt(product.get("add_time")),
                as_dt(product.get("upd_time")),
                None,
            )
            if existing_sku_id:
                self.execute(
                    cursor,
                    f"""
                    UPDATE {self.table('product_sku')}
                    SET spu_id=%s, sku_no=%s, primary_category_id=%s, category_ids=%s, color=%s,
                        bag_type=%s, tea_type=%s, material_type=%s, service_type=%s, unit_id=%s,
                        min_purchase_qty=%s, min_purchase_unit_id=%s, inventory_policy=%s,
                        purchase_policy=%s, default_warehouse_id=%s, default_supplier_id=%s,
                        retail_price=%s, min_price=%s, max_price=%s, cost_price=%s, price_note=%s,
                        is_stock_item=%s, is_sellable=%s, is_listed=%s, status=%s,
                        main_image_url=%s, detail_image_urls=%s, content_html=%s, search_text=%s,
                        source=%s, created_at=%s, updated_at=%s, deleted_at=%s
                    WHERE id=%s
                    """,
                    (*params, existing_sku_id),
                )
                sku_id = existing_sku_id
            else:
                self.execute(
                    cursor,
                    f"""
                    INSERT INTO {self.table('product_sku')}
                        (spu_id, sku_no, primary_category_id, category_ids, color, bag_type,
                         tea_type, material_type, service_type, unit_id, min_purchase_qty,
                         min_purchase_unit_id, inventory_policy, purchase_policy,
                         default_warehouse_id, default_supplier_id, retail_price, min_price,
                         max_price, cost_price, price_note, is_stock_item, is_sellable,
                         is_listed, status, main_image_url, detail_image_urls, content_html,
                         search_text, source, created_at, updated_at, deleted_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    params,
                )
                sku_id = cursor.lastrowid
            self.upsert_ref(
                cursor,
                "sku",
                int(sku_id),
                "sxo_plugins_erp_product.id",
                str(product_id),
                first_non_empty(product.get("base_coding"), product.get("product_coding")),
            )
            alias_rows.extend(self.alias_rows(sku_id, spu_id, sku_no, display_title, spoken_name, color, product))
            media_rows.extend(self.media_rows(sku_id, spu_id, main_url, detail_urls, as_dt(product.get("add_time")), as_dt(product.get("upd_time"))))

        if duplicate_sku_sources:
            self.warn("duplicate_sku_no", "发现重复 SJ 编号，已为后续重复项生成临时 SJ 编号", duplicate_sku_sources[:50])
        if nonstandard_specs:
            self.report["nonstandard_specs"] = nonstandard_specs.most_common()
            self.warn("nonstandard_spec", "旧 spec 中有非标准颜色，未写入 product_sku.color", nonstandard_specs.most_common(50))
        self.bulk_insert_aliases(cursor, alias_rows)
        self.bulk_insert_media(cursor, media_rows)

    def common_value(self, rows: list[dict], key: str) -> str:
        values = [str(row.get(key) or "").strip() for row in rows if str(row.get(key) or "").strip()]
        if not values:
            return ""
        return Counter(values).most_common(1)[0][0]

    def choose_primary_category(self, category_ids: list[int], title: str = "") -> int | None:
        if not category_ids:
            return None
        title_text = str(title or "")
        for cid in category_ids:
            name = self.category_names.get(cid, "")
            if name and name.replace("礼盒", "") and name.replace("礼盒", "") in title_text:
                return cid
        return sorted(category_ids)[0]

    def standardize_color(self, spec: Any) -> str:
        text = str(spec or "").strip()
        if not text:
            return ""
        if text in self.standard_colors:
            return text
        if text in self.color_aliases:
            return str(self.color_aliases[text] or "").strip()
        return ""

    def preferred_sku_no(self, product: dict) -> str:
        for value in (product.get("base_coding"), product.get("product_coding"), product.get("title")):
            match = re.search(r"\bSJ\s*0*([0-9]{1,8})\b", str(value or ""), flags=re.IGNORECASE)
            if match:
                digits = match.group(1)
                width = max(4, len(digits))
                return f"SJ{int(digits):0{width}d}"
        return f"SJ{int(product['id']):06d}"

    def product_images(self, product: dict, sync: dict) -> tuple[str, list[str]]:
        main_candidates: list[str] = []
        detail_candidates: list[str] = []
        for field in ("main_images", "images"):
            for url in extract_urls(product.get(field)):
                if url not in main_candidates:
                    main_candidates.append(url)
        for url in extract_urls(sync.get("goods_images")):
            if url not in main_candidates:
                main_candidates.append(url)
        for url in extract_urls(product.get("content")) + extract_urls(sync.get("content_web")):
            if url not in detail_candidates:
                detail_candidates.append(url)
        main_url = main_candidates[0] if main_candidates else (detail_candidates[0] if detail_candidates else "")
        detail_urls = [url for url in detail_candidates if url != main_url]
        for url in main_candidates[1:]:
            if url not in detail_urls:
                detail_urls.insert(0, url)
        return main_url, detail_urls

    def alias_rows(
        self,
        sku_id: int,
        spu_id: int,
        sku_no: str,
        display_title: str,
        spoken_name: str,
        color: str,
        product: dict,
    ):
        now = datetime.now()
        aliases = [
            ("sku", sku_id, sku_no, "code", 100),
            ("sku", sku_id, display_title, "old_title", 50),
            ("sku", sku_id, spoken_name, "spoken_name", 90),
            ("spu", spu_id, display_title, "old_title", 40),
        ]
        old_coding = first_non_empty(product.get("base_coding"), product.get("product_coding"))
        if old_coding and old_coding != sku_no:
            aliases.append(("sku", sku_id, old_coding, "code", 30))
        if color:
            aliases.append(("sku", sku_id, f"{display_title}{color}", "spoken_name", 80))
        rows: list[tuple] = []
        for target_type, target_id, alias, alias_type, weight in aliases:
            alias = str(alias or "").strip()
            if not alias:
                continue
            rows.append(
                (target_type, target_id, alias, normalize_alias(alias), alias_type, weight, 1, "migration", now, now)
            )
        return rows

    def bulk_insert_aliases(self, cursor, rows: list[tuple]):
        self.executemany(
            cursor,
            f"""
            INSERT INTO {self.table('product_alias')}
                (target_type, target_id, alias, normalized_alias, alias_type, weight,
                 is_enabled, source, created_at, updated_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE
                alias=VALUES(alias), weight=VALUES(weight), is_enabled=VALUES(is_enabled),
                source=VALUES(source), updated_at=VALUES(updated_at)
            """,
            rows,
        )

    def media_rows(self, sku_id: int, spu_id: int, main_url: str, detail_urls: list[str], created_at: datetime, updated_at: datetime) -> list[tuple]:
        rows = []
        if main_url:
            rows.append(("main", main_url, 0))
        for index, url in enumerate(detail_urls, start=1):
            rows.append(("detail", url, index))
        seen = set()
        result: list[tuple] = []
        for media_type, url, sort_order in rows:
            if not url or (media_type, url) in seen:
                continue
            seen.add((media_type, url))
            result.append(
                (
                    sku_id,
                    spu_id,
                    media_type,
                    url,
                    storage_from_url(url),
                    url_path(url) or None,
                    file_name_from_url(url) or None,
                    mime_from_url(url) or None,
                    None,
                    None,
                    hashlib.sha256(url.encode("utf-8")).hexdigest(),
                    sort_order,
                    1,
                    "migration",
                    created_at,
                    updated_at,
                ),
            )
        return result

    def bulk_insert_media(self, cursor, rows: list[tuple]):
        self.executemany(
            cursor,
            f"""
            INSERT INTO {self.table('product_media')}
                (sku_id, spu_id, media_type, url, storage, path, file_name, mime_type,
                 width, height, sha256, sort_order, is_active, source, created_at, updated_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            rows,
        )

    def warn(self, code: str, message: str, detail: Any):
        self.report.setdefault("warnings", []).append({"code": code, "message": message, "detail": detail})

    def refresh_report_counts(self, source_cursor, target_cursor):
        source_count_queries = {
            "source_products": f"SELECT COUNT(*) AS cnt FROM {self.source_table('sxo_plugins_erp_product')}",
            "source_groups": f"SELECT COUNT(DISTINCT group_key) AS cnt FROM {self.source_table('sxo_plugins_erp_product')}",
        }
        target_count_queries = {
            "product_unit": f"SELECT COUNT(*) AS cnt FROM {self.table('product_unit')}",
            "product_category": f"SELECT COUNT(*) AS cnt FROM {self.table('product_category')}",
            "product_spu": f"SELECT COUNT(*) AS cnt FROM {self.table('product_spu')}",
            "product_sku": f"SELECT COUNT(*) AS cnt FROM {self.table('product_sku')}",
            "product_alias": f"SELECT COUNT(*) AS cnt FROM {self.table('product_alias')}",
            "product_media": f"SELECT COUNT(*) AS cnt FROM {self.table('product_media')}",
            "migration_product_ref": f"SELECT COUNT(*) AS cnt FROM {self.table('migration_product_ref')}",
        }
        counts = {}
        for key, sql in source_count_queries.items():
            rows = self.query(source_cursor, sql)
            counts[key] = int(rows[0]["cnt"]) if rows else 0
        for key, sql in target_count_queries.items():
            rows = self.query(target_cursor, sql)
            counts[key] = int(rows[0]["cnt"]) if rows else 0
        self.report["counts"] = counts
        missing_categories = self.query(
            target_cursor,
            f"SELECT COUNT(*) AS cnt FROM {self.table('product_sku')} WHERE primary_category_id IS NULL",
        )
        self.report["counts"]["sku_missing_category"] = int(missing_categories[0]["cnt"] or 0)
        missing_color = self.query(
            target_cursor,
            f"SELECT COUNT(*) AS cnt FROM {self.table('product_sku')} WHERE color IS NULL OR color=''",
        )
        self.report["counts"]["sku_without_standard_color"] = int(missing_color[0]["cnt"] or 0)

    def write_report(self):
        report_path = ROOT / "data" / "migration" / "product_import_report.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(self.report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        return report_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create/import native product catalog tables.")
    target_db = os.getenv("SJAGENT_CORE_DB_NAME") or os.getenv("SJAGENT_CORE_DB") or DEFAULT_TARGET_DB
    parser.add_argument("--target-db", default=target_db, help="Target native database/schema name.")
    parser.add_argument("--source-db", default=None, help="Source ShopXO/ERP database/schema name. Defaults to config database.name.")
    parser.add_argument("--schema-only", action="store_true", help="Only create schema, do not import data.")
    parser.add_argument("--import-only", action="store_true", help="Only import data, assuming schema already exists.")
    return parser.parse_args()


def main() -> int:
    load_dotenv(ROOT / ".env")
    args = parse_args()
    config = get_config()
    source_db = args.source_db or config.db_config["name"]
    migrator = ProductCatalogMigrator(source_db=source_db, target_db=args.target_db)
    if not args.import_only:
        migrator.create_schema()
    if not args.schema_only:
        migrator.import_data()
    report_path = migrator.write_report()
    print(json.dumps({"code": 0, "target_db": migrator.target_db, "report_path": str(report_path), "counts": migrator.report.get("counts", {})}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
