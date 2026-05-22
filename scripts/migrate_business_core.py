"""Create and import core business data into sjagent_core.

The import reads warehouses, parties, ShopXO/Web users, external identities,
and current inventory balances from the legacy ShopXO/ERP database. It writes
North-Star-owned business tables in a separate target schema and is safe to run
more than once.

Legacy product ids are resolved through migration_product_ref; they are not
written into business tables.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import pymysql
from dotenv import load_dotenv
from pymysql.cursors import DictCursor


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.config import get_config  # noqa: E402


DEFAULT_TARGET_DB = "sjagent_core"


def quote_ident(name: str) -> str:
    if not re.fullmatch(r"[0-9A-Za-z_]+", name or ""):
        raise ValueError(f"Unsafe database/table identifier: {name!r}")
    return f"`{name}`"


def env_first(*names: str, default: str | None = None) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value not in (None, ""):
            return value
    return default


def as_dt(value: Any) -> datetime:
    try:
        ts = int(value or 0)
    except (TypeError, ValueError):
        ts = 0
    if ts > 0:
        return datetime.fromtimestamp(ts)
    return datetime.now()


def as_decimal(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    text = str(value).strip()
    if not text:
        return Decimal("0")
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return Decimal("0")


def clean_text(value: Any, limit: int | None = None) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if limit is not None:
        return text[:limit]
    return text


def first_non_empty(*values: Any) -> str:
    for value in values:
        text = clean_text(value)
        if text:
            return text
    return ""


def normalize_phone(value: Any) -> str:
    text = str(value or "")
    if not text:
        return ""
    digits = re.sub(r"\D+", "", text)
    if len(digits) >= 11:
        candidate = digits[-11:]
        if re.fullmatch(r"1[0-9]{10}", candidate):
            return candidate
    return ""


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def json_array_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "[]"
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return json_text(parsed)
        if parsed:
            return json_text([parsed])
    except Exception:
        pass
    return json_text([text])


def stable_external_id(prefix: str, value: Any) -> str:
    return f"{prefix}:{str(value or '').strip()}"


class BusinessCoreMigrator:
    def __init__(self, source_db: str, target_db: str, args: argparse.Namespace):
        self.source_db = source_db
        self.target_db = target_db
        self.config = get_config()
        self.base_db_config = self.config.db_config
        self.source_db_config = self.build_source_db_config(args, source_db)
        self.target_db_config = self.build_target_db_config(args, target_db)
        self.report: dict[str, Any] = {
            "source_db": source_db,
            "target_db": target_db,
            "started_at": datetime.now().isoformat(timespec="seconds"),
            "counts": {},
            "warnings": [],
        }

    def build_source_db_config(self, args: argparse.Namespace, source_db: str) -> dict[str, Any]:
        cfg = dict(self.base_db_config)
        cfg["host"] = args.source_host or env_first("SJAGENT_SOURCE_DB_HOST", "SOURCE_DB_HOST", "DB_HOST", default=cfg["host"])
        cfg["port"] = int(args.source_port or env_first("SJAGENT_SOURCE_DB_PORT", "SOURCE_DB_PORT", "DB_PORT", default=str(cfg["port"])))
        cfg["name"] = args.source_db or env_first("SJAGENT_SOURCE_DB_NAME", "SOURCE_DB_NAME", "DB_NAME", default=source_db)
        cfg["user"] = args.source_user or env_first("SJAGENT_SOURCE_DB_USER", "SOURCE_DB_USER", "DB_USER", default=cfg["user"])
        cfg["password"] = args.source_password or env_first("SJAGENT_SOURCE_DB_PASSWORD", "SOURCE_DB_PASSWORD", "DB_PASSWORD", default=cfg["password"])
        cfg["charset"] = env_first("SJAGENT_SOURCE_DB_CHARSET", "SOURCE_DB_CHARSET", default=cfg.get("charset") or "utf8mb4")
        return cfg

    def build_target_db_config(self, args: argparse.Namespace, target_db: str) -> dict[str, Any]:
        cfg = dict(self.base_db_config)
        cfg["host"] = args.target_host or env_first("SJAGENT_CORE_DB_HOST", "SJAGENT_CORE_HOST", default=cfg["host"])
        cfg["port"] = int(args.target_port or env_first("SJAGENT_CORE_DB_PORT", "SJAGENT_CORE_PORT", default=str(cfg["port"])))
        cfg["name"] = args.target_db or env_first("SJAGENT_CORE_DB_NAME", "SJAGENT_CORE_DB", default=target_db)
        cfg["user"] = args.target_user or env_first("SJAGENT_CORE_DB_USER", "SJAGENT_CORE_USER", default=cfg["user"])
        cfg["password"] = args.target_password or env_first("SJAGENT_CORE_DB_PASSWORD", "SJAGENT_CORE_PASSWORD", default=cfg["password"])
        cfg["charset"] = env_first("SJAGENT_CORE_DB_CHARSET", default=cfg.get("charset") or "utf8mb4")
        return cfg

    def connect_with_config(self, cfg: dict[str, Any], database: str | None):
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

    def connect_source(self):
        return self.connect_with_config(self.source_db_config, self.source_db)

    def connect_target(self, database: str | None = None):
        return self.connect_with_config(self.target_db_config, database if database is not None else self.target_db)

    def connect_target_server(self):
        return self.connect_with_config(self.target_db_config, None)

    def table(self, name: str) -> str:
        return f"{quote_ident(self.target_db)}.{quote_ident(name)}"

    def source_table(self, name: str) -> str:
        return f"{quote_ident(self.source_db)}.{quote_ident(name)}"

    def query(self, cursor, sql: str, params: tuple | list | None = None) -> list[dict]:
        cursor.execute(sql, params)
        return list(cursor.fetchall())

    def execute(self, cursor, sql: str, params: tuple | list | None = None) -> int:
        return cursor.execute(sql, params)

    def executemany(self, cursor, sql: str, params: list[tuple]) -> int:
        if not params:
            return 0
        return cursor.executemany(sql, params)

    def warn(self, code: str, message: str, detail: Any):
        self.report.setdefault("warnings", []).append({"code": code, "message": message, "detail": detail})

    def ensure_database(self):
        try:
            conn = self.connect_target_server()
            with conn.cursor() as cursor:
                cursor.execute(
                    f"CREATE DATABASE IF NOT EXISTS {quote_ident(self.target_db)} "
                    "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
            conn.commit()
            conn.close()
        except pymysql.OperationalError as exc:
            code = int(exc.args[0]) if exc.args else 0
            if code not in (1044, 1045):
                raise
            self.warn(
                "create_database_skipped",
                "Could not create target database; will connect to the target database directly.",
                {"mysql_error": code, "database": self.target_db},
            )

    def create_schema(self):
        from scripts.deploy_database_schema import deploy as deploy_schema

        deploy_args = argparse.Namespace(
            database=self.target_db,
            host=self.target_db_config["host"],
            port=str(self.target_db_config["port"]),
            user=self.target_db_config["user"],
            password=self.target_db_config["password"],
            schema_dir=str(ROOT / "database" / "schema"),
            only=None,
            dry_run=False,
        )
        schema_report = deploy_schema(deploy_args)
        self.report["schema_deploy_files"] = schema_report.get("files", [])

    def ddl_statements(self) -> list[str]:
        return [
            f"""
            CREATE TABLE IF NOT EXISTS {self.table('warehouse')} (
                id BIGINT UNSIGNED NOT NULL,
                code VARCHAR(60) NOT NULL,
                name VARCHAR(120) NOT NULL,
                warehouse_type VARCHAR(30) NOT NULL,
                address VARCHAR(300) NULL,
                contact_name VARCHAR(80) NULL,
                phone VARCHAR(40) NULL,
                is_default_sales TINYINT NOT NULL DEFAULT 0,
                is_default_inbound TINYINT NOT NULL DEFAULT 0,
                sort_order INT NULL,
                is_enabled TINYINT NOT NULL DEFAULT 1,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                PRIMARY KEY (id),
                UNIQUE KEY uk_warehouse_code (code),
                KEY idx_warehouse_enabled (is_enabled)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            f"""
            CREATE TABLE IF NOT EXISTS {self.table('party')} (
                id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                name VARCHAR(160) NOT NULL,
                kind VARCHAR(20) NOT NULL,
                contact_name VARCHAR(80) NULL,
                phone VARCHAR(40) NULL,
                phone_normalized VARCHAR(40) NOT NULL DEFAULT '',
                address VARCHAR(300) NULL,
                wechat_name VARCHAR(120) NULL,
                auto_print_sales TINYINT NOT NULL DEFAULT 0,
                settlement_type VARCHAR(30) NULL,
                tags JSON NULL,
                note TEXT NULL,
                source VARCHAR(30) NOT NULL DEFAULT 'manual',
                status VARCHAR(20) NOT NULL DEFAULT 'active',
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                deleted_at DATETIME NULL,
                PRIMARY KEY (id),
                UNIQUE KEY uk_party_migration_match (name, phone_normalized, kind),
                KEY idx_party_phone (phone_normalized),
                KEY idx_party_kind (kind),
                KEY idx_party_status (status)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            f"""
            CREATE TABLE IF NOT EXISTS {self.table('auth_user')} (
                id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                username VARCHAR(80) NOT NULL,
                password_hash VARCHAR(255) NULL,
                display_name VARCHAR(80) NOT NULL,
                phone VARCHAR(40) NULL,
                role VARCHAR(30) NOT NULL DEFAULT 'customer',
                linked_party_id BIGINT UNSIGNED NULL,
                approval_status VARCHAR(20) NOT NULL DEFAULT 'approved',
                is_active TINYINT NOT NULL DEFAULT 1,
                is_admin TINYINT NOT NULL DEFAULT 0,
                last_login_at DATETIME NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                PRIMARY KEY (id),
                UNIQUE KEY uk_auth_user_username (username),
                KEY idx_auth_user_phone (phone),
                KEY idx_auth_user_party (linked_party_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            f"""
            CREATE TABLE IF NOT EXISTS {self.table('auth_identity')} (
                id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                user_id BIGINT UNSIGNED NOT NULL,
                provider VARCHAR(30) NOT NULL,
                external_user_id VARCHAR(160) NOT NULL,
                openid VARCHAR(160) NULL,
                unionid VARCHAR(160) NULL,
                raw_profile JSON NULL,
                is_enabled TINYINT NOT NULL DEFAULT 1,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                PRIMARY KEY (id),
                UNIQUE KEY uk_auth_identity_provider_external (provider, external_user_id),
                KEY idx_auth_identity_user (user_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            f"""
            CREATE TABLE IF NOT EXISTS {self.table('inventory_balance')} (
                id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                sku_id BIGINT UNSIGNED NOT NULL,
                warehouse_id BIGINT UNSIGNED NOT NULL,
                unit_id BIGINT UNSIGNED NOT NULL,
                quantity DECIMAL(12,3) NOT NULL DEFAULT 0,
                reserved_qty DECIMAL(12,3) NOT NULL DEFAULT 0,
                available_qty DECIMAL(12,3) NOT NULL DEFAULT 0,
                low_stock_qty DECIMAL(12,3) NULL,
                last_ledger_id BIGINT UNSIGNED NULL,
                version BIGINT NOT NULL DEFAULT 1,
                updated_at DATETIME NOT NULL,
                PRIMARY KEY (id),
                UNIQUE KEY uk_inventory_balance_sku_warehouse_unit (sku_id, warehouse_id, unit_id),
                KEY idx_inventory_balance_warehouse (warehouse_id),
                KEY idx_inventory_balance_sku (sku_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            f"""
            CREATE TABLE IF NOT EXISTS {self.table('inventory_ledger')} (
                id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                ledger_no VARCHAR(80) NOT NULL,
                sku_id BIGINT UNSIGNED NOT NULL,
                sku_no_snapshot VARCHAR(80) NOT NULL,
                warehouse_id BIGINT UNSIGNED NOT NULL,
                unit_id BIGINT UNSIGNED NOT NULL,
                change_qty DECIMAL(12,3) NOT NULL,
                before_qty DECIMAL(12,3) NOT NULL,
                after_qty DECIMAL(12,3) NOT NULL,
                biz_type VARCHAR(40) NOT NULL,
                biz_id BIGINT UNSIGNED NULL,
                biz_item_id BIGINT UNSIGNED NULL,
                counterparty_warehouse_id BIGINT UNSIGNED NULL,
                operator_user_id BIGINT UNSIGNED NULL,
                note VARCHAR(500) NULL,
                occurred_at DATETIME NOT NULL,
                created_at DATETIME NOT NULL,
                PRIMARY KEY (id),
                UNIQUE KEY uk_inventory_ledger_no (ledger_no),
                KEY idx_inventory_ledger_sku (sku_id),
                KEY idx_inventory_ledger_warehouse (warehouse_id),
                KEY idx_inventory_ledger_biz (biz_type, biz_id, biz_item_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
        ]

    def source_table_exists(self, cursor, table_name: str) -> bool:
        cursor.execute("SHOW TABLES LIKE %s", (table_name,))
        return bool(cursor.fetchone())

    def import_data(self):
        source_conn = self.connect_source()
        target_conn = self.connect_target()
        try:
            with source_conn.cursor() as source_cursor, target_conn.cursor() as target_cursor:
                self.import_warehouses(source_cursor, target_cursor)
                party_by_phone = self.import_parties(source_cursor, target_cursor)
                user_by_source = self.import_auth_users(source_cursor, target_cursor, party_by_phone)
                self.import_auth_identities(source_cursor, target_cursor, user_by_source)
                self.import_inventory(source_cursor, target_cursor)
                self.import_sales(source_cursor, target_cursor)
                self.import_workflow_orders(source_cursor, target_cursor)
                self.import_stock_documents(source_cursor, target_cursor)
                self.import_stocktakes(source_cursor, target_cursor)
                self.import_transfers(source_cursor, target_cursor)
                self.refresh_report_counts(source_cursor, target_cursor)
            target_conn.commit()
        except Exception:
            target_conn.rollback()
            raise
        finally:
            source_conn.close()
            target_conn.close()

    def import_warehouses(self, source_cursor, target_cursor):
        rows = self.query(
            source_cursor,
            f"""
            SELECT id, name, alias, address, contacts_name, contacts_mobile, contacts_tel,
                   is_enable, sort, add_time, upd_time
            FROM {self.source_table('sxo_plugins_erp_warehouse')}
            ORDER BY id
            """,
        )
        params = []
        for row in rows:
            warehouse_id = int(row["id"])
            code = self.warehouse_code(row)
            name = first_non_empty(row.get("name"), row.get("alias"), f"Warehouse {warehouse_id}")[:120]
            phone = first_non_empty(row.get("contacts_mobile"), row.get("contacts_tel"))[:40] or None
            params.append(
                (
                    warehouse_id,
                    code,
                    name,
                    self.warehouse_type(row),
                    clean_text(row.get("address"), 300) or None,
                    clean_text(row.get("contacts_name"), 80) or None,
                    phone,
                    1 if warehouse_id == int(self.config.get("erp.warehouse.baixin", 2)) else 0,
                    1 if warehouse_id == int(self.config.get("erp.warehouse.baixin", 2)) else 0,
                    int(row.get("sort") or 0),
                    1 if int(row.get("is_enable") or 0) == 1 else 0,
                    as_dt(row.get("add_time")),
                    as_dt(row.get("upd_time")),
                )
            )
        self.executemany(
            target_cursor,
            f"""
            INSERT INTO {self.table('warehouse')}
                (id, code, name, warehouse_type, address, contact_name, phone,
                 is_default_sales, is_default_inbound, sort_order, is_enabled,
                 created_at, updated_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE
                code=VALUES(code), name=VALUES(name), warehouse_type=VALUES(warehouse_type),
                address=VALUES(address), contact_name=VALUES(contact_name), phone=VALUES(phone),
                is_default_sales=VALUES(is_default_sales),
                is_default_inbound=VALUES(is_default_inbound),
                sort_order=VALUES(sort_order), is_enabled=VALUES(is_enabled),
                updated_at=VALUES(updated_at)
            """,
            params,
        )

    def warehouse_code(self, row: dict) -> str:
        warehouse_id = int(row.get("id") or 0)
        name = str(row.get("name") or "")
        if warehouse_id == int(self.config.get("erp.warehouse.self", 1)):
            return "self_store"
        if warehouse_id == int(self.config.get("erp.warehouse.baixin", 2)):
            return "baixin"
        if row.get("alias"):
            return re.sub(r"[^0-9A-Za-z_]+", "_", str(row["alias"]).strip().lower()).strip("_")[:60] or f"warehouse_{warehouse_id}"
        return f"warehouse_{warehouse_id}" if not name else f"warehouse_{warehouse_id}"

    def warehouse_type(self, row: dict) -> str:
        warehouse_id = int(row.get("id") or 0)
        if warehouse_id == int(self.config.get("erp.warehouse.self", 1)):
            return "store"
        if warehouse_id == int(self.config.get("erp.warehouse.baixin", 2)):
            return "main"
        return "temporary"

    def import_parties(self, source_cursor, target_cursor) -> dict[str, int]:
        rows = self.query(
            source_cursor,
            f"""
            SELECT id, name, company_name, is_enable, is_customer, is_supplier,
                   address, contacts_name, contacts_mobile, contacts_tel, note,
                   add_time, upd_time
            FROM {self.source_table('sxo_plugins_erp_company')}
            ORDER BY id
            """,
        )
        auto_print_ids = {
            int(value)
            for value in re.findall(r"\d+", str(self.config.get("business_rules.print_rules.auto_print_customers", "") or ""))
        }
        params = []
        for row in rows:
            old_id = int(row["id"])
            name = first_non_empty(row.get("name"), row.get("company_name"), row.get("contacts_name"), f"Party {old_id}")[:160]
            phone = first_non_empty(row.get("contacts_mobile"), row.get("contacts_tel"))[:40] or None
            phone_norm = normalize_phone(phone) or None
            is_customer = int(row.get("is_customer") or 0) == 1
            is_supplier = int(row.get("is_supplier") or 0) == 1
            kind = "both" if is_customer and is_supplier else ("supplier" if is_supplier else "customer")
            tags = []
            if is_customer:
                tags.append("legacy_customer")
            if is_supplier:
                tags.append("legacy_supplier")
            params.append(
                (
                    old_id,
                    name,
                    kind,
                    clean_text(row.get("contacts_name"), 80) or None,
                    phone,
                    phone_norm,
                    clean_text(row.get("address"), 300) or None,
                    None,
                    1 if old_id in auto_print_ids else 0,
                    None,
                    json_text(tags),
                    clean_text(row.get("note")) or None,
                    "migration",
                    "active" if int(row.get("is_enable") or 0) == 1 else "inactive",
                    as_dt(row.get("add_time")),
                    as_dt(row.get("upd_time")),
                    None,
                )
            )
        self.executemany(
            target_cursor,
            f"""
            INSERT INTO {self.table('party')}
                (id, name, kind, contact_name, phone, phone_normalized, address, wechat_name,
                 auto_print_sales, settlement_type, tags, note, source, status,
                 created_at, updated_at, deleted_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE
                name=VALUES(name), kind=VALUES(kind),
                contact_name=VALUES(contact_name), phone=VALUES(phone),
                phone_normalized=VALUES(phone_normalized), address=VALUES(address),
                auto_print_sales=VALUES(auto_print_sales), tags=VALUES(tags), note=VALUES(note),
                status=VALUES(status), source=VALUES(source), updated_at=VALUES(updated_at),
                deleted_at=VALUES(deleted_at)
            """,
            params,
        )
        party_by_phone: dict[str, int] = {}
        rows = self.query(
            target_cursor,
            f"""
            SELECT id, phone_normalized
            FROM {self.table('party')}
            WHERE phone_normalized IS NOT NULL AND phone_normalized <> ''
            ORDER BY id
            """,
        )
        for row in rows:
            party_by_phone.setdefault(str(row["phone_normalized"]), int(row["id"]))
        return party_by_phone

    def import_auth_users(self, source_cursor, target_cursor, party_by_phone: dict[str, int]) -> dict[tuple[str, str], int]:
        user_by_source: dict[tuple[str, str], int] = {}
        params = []
        if self.source_table_exists(source_cursor, "sjagent_web_users"):
            rows = self.query(
                source_cursor,
                f"""
                SELECT id, username, password_hash, display_name, approval_status,
                       is_admin, is_active, created_at, updated_at, last_login_at
                FROM {self.source_table('sjagent_web_users')}
                ORDER BY id
                """,
            )
            for row in rows:
                username = first_non_empty(row.get("username"), stable_external_id("web", row["id"]))[:80]
                phone_norm = normalize_phone(username)
                params.append(
                    (
                        username,
                        row.get("password_hash") or None,
                        first_non_empty(row.get("display_name"), username)[:80],
                        phone_norm or None,
                        "admin" if int(row.get("is_admin") or 0) == 1 else "staff",
                        party_by_phone.get(phone_norm),
                        clean_text(row.get("approval_status"), 20) or "approved",
                        1 if int(row.get("is_active") or 0) == 1 else 0,
                        1 if int(row.get("is_admin") or 0) == 1 else 0,
                        as_dt(row.get("last_login_at")) if int(row.get("last_login_at") or 0) > 0 else None,
                        as_dt(row.get("created_at")),
                        as_dt(row.get("updated_at")),
                    )
                )
        if self.source_table_exists(source_cursor, "sxo_user"):
            rows = self.query(
                source_cursor,
                f"""
                SELECT id, username, nickname, mobile, email, status, user_role,
                       is_delete_time, is_logout_time, add_time, upd_time
                FROM {self.source_table('sxo_user')}
                ORDER BY id
                """,
            )
            for row in rows:
                old_id = int(row["id"])
                username = first_non_empty(row.get("mobile"), row.get("email"), row.get("username"), stable_external_id("shopxo", old_id))[:80]
                phone_norm = normalize_phone(row.get("mobile"))
                is_deleted = int(row.get("is_delete_time") or 0) > 0 or int(row.get("is_logout_time") or 0) > 0
                is_active = 0 if is_deleted or int(row.get("status") or 0) != 0 else 1
                is_admin = 1 if int(row.get("user_role") or 0) == 0 and is_active else 0
                params.append(
                    (
                        username,
                        None,
                        first_non_empty(row.get("nickname"), row.get("username"), row.get("mobile"), f"ShopXO User {old_id}")[:80],
                        phone_norm or None,
                        "admin" if is_admin else "customer",
                        party_by_phone.get(phone_norm),
                        "approved" if is_active else "rejected",
                        is_active,
                        is_admin,
                        None,
                        as_dt(row.get("add_time")),
                        as_dt(row.get("upd_time")),
                    )
                )
        self.executemany(
            target_cursor,
            f"""
            INSERT INTO {self.table('auth_user')}
                (username, password_hash, display_name, phone, role, linked_party_id,
                 approval_status, is_active, is_admin, last_login_at, created_at, updated_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE
                password_hash=COALESCE(VALUES(password_hash), password_hash),
                display_name=VALUES(display_name), phone=VALUES(phone), role=VALUES(role),
                linked_party_id=VALUES(linked_party_id), approval_status=VALUES(approval_status),
                is_active=VALUES(is_active), is_admin=VALUES(is_admin),
                last_login_at=COALESCE(VALUES(last_login_at), last_login_at),
                updated_at=VALUES(updated_at)
            """,
            params,
        )
        rows = self.query(target_cursor, f"SELECT id, username FROM {self.table('auth_user')}")
        user_by_username = {str(row["username"]): int(row["id"]) for row in rows}
        if self.source_table_exists(source_cursor, "sjagent_web_users"):
            for row in self.query(source_cursor, f"SELECT id, username FROM {self.source_table('sjagent_web_users')}"):
                username = first_non_empty(row.get("username"), stable_external_id("web", row["id"]))[:80]
                if username in user_by_username:
                    user_by_source[("web", str(row["id"]))] = user_by_username[username]
        if self.source_table_exists(source_cursor, "sxo_user"):
            for row in self.query(source_cursor, f"SELECT id, username, mobile, email FROM {self.source_table('sxo_user')}"):
                username = first_non_empty(row.get("mobile"), row.get("email"), row.get("username"), stable_external_id("shopxo", row["id"]))[:80]
                if username in user_by_username:
                    user_by_source[("shopxo", str(row["id"]))] = user_by_username[username]
        return user_by_source

    def import_auth_identities(self, source_cursor, target_cursor, user_by_source: dict[tuple[str, str], int]):
        rows_to_insert: list[tuple] = []
        now = datetime.now()
        self.execute(
            target_cursor,
            f"""
            DELETE FROM {self.table('auth_identity')}
            WHERE provider='phone'
              AND (CHAR_LENGTH(external_user_id) <> 11 OR external_user_id NOT REGEXP '^1[0-9]{{10}}$')
            """,
        )
        if self.source_table_exists(source_cursor, "sjagent_web_users"):
            rows = self.query(source_cursor, f"SELECT id, username, created_at, updated_at FROM {self.source_table('sjagent_web_users')}")
            for row in rows:
                user_id = user_by_source.get(("web", str(row["id"])))
                if not user_id:
                    continue
                username = first_non_empty(row.get("username"), stable_external_id("web", row["id"]))
                rows_to_insert.append(
                    (user_id, "web", stable_external_id("web", row["id"]), None, None, json_text({"username": username}), 1, as_dt(row.get("created_at")), as_dt(row.get("updated_at")))
                )
                phone_norm = normalize_phone(username)
                if phone_norm:
                    rows_to_insert.append((user_id, "phone", phone_norm, None, None, json_text({"source": "sjagent_web_users"}), 1, as_dt(row.get("created_at")), as_dt(row.get("updated_at"))))
        if self.source_table_exists(source_cursor, "sxo_user"):
            rows = self.query(
                source_cursor,
                f"SELECT id, username, mobile, email, nickname, avatar, add_time, upd_time FROM {self.source_table('sxo_user')}",
            )
            for row in rows:
                user_id = user_by_source.get(("shopxo", str(row["id"])))
                if not user_id:
                    continue
                raw_profile = {
                    "username": row.get("username") or "",
                    "nickname": row.get("nickname") or "",
                    "email": row.get("email") or "",
                    "avatar": row.get("avatar") or "",
                }
                rows_to_insert.append((user_id, "shopxo", str(row["id"]), None, None, json_text(raw_profile), 1, as_dt(row.get("add_time")), as_dt(row.get("upd_time"))))
                phone_norm = normalize_phone(row.get("mobile"))
                if phone_norm:
                    rows_to_insert.append((user_id, "phone", phone_norm, None, None, json_text({"source": "sxo_user"}), 1, as_dt(row.get("add_time")), as_dt(row.get("upd_time"))))
        if self.source_table_exists(source_cursor, "sxo_user_platform"):
            rows = self.query(
                source_cursor,
                f"""
                SELECT id, user_id, platform, weixin_openid, weixin_unionid, weixin_web_openid,
                       alipay_openid, toutiao_openid, toutiao_unionid, qq_openid, qq_unionid,
                       kuaishou_openid, add_time, upd_time
                FROM {self.source_table('sxo_user_platform')}
                ORDER BY id
                """,
            )
            provider_fields = [
                ("wechat", "weixin_openid", "weixin_unionid"),
                ("wechat_web", "weixin_web_openid", "weixin_unionid"),
                ("alipay", "alipay_openid", None),
                ("toutiao", "toutiao_openid", "toutiao_unionid"),
                ("qq", "qq_openid", "qq_unionid"),
                ("kuaishou", "kuaishou_openid", None),
            ]
            for row in rows:
                user_id = user_by_source.get(("shopxo", str(row["user_id"])))
                if not user_id:
                    continue
                for provider, openid_key, unionid_key in provider_fields:
                    openid = clean_text(row.get(openid_key), 160)
                    if not openid:
                        continue
                    unionid = clean_text(row.get(unionid_key), 160) if unionid_key else ""
                    rows_to_insert.append(
                        (
                            user_id,
                            provider,
                            openid,
                            openid,
                            unionid or None,
                            json_text({"platform": row.get("platform") or "", "source_id": row.get("id")}),
                            1,
                            as_dt(row.get("add_time")),
                            as_dt(row.get("upd_time")),
                        )
                    )
        self.executemany(
            target_cursor,
            f"""
            INSERT INTO {self.table('auth_identity')}
                (user_id, provider, external_user_id, openid, unionid, raw_profile,
                 is_enabled, created_at, updated_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE
                user_id=VALUES(user_id), openid=VALUES(openid), unionid=VALUES(unionid),
                raw_profile=VALUES(raw_profile), is_enabled=VALUES(is_enabled),
                updated_at=VALUES(updated_at)
            """,
            rows_to_insert,
        )

    def import_inventory(self, source_cursor, target_cursor):
        sku_map = self.product_sku_map(target_cursor)
        if not sku_map:
            self.warn(
                "missing_product_mapping",
                "No product SKU mapping found in migration_product_ref; inventory import skipped.",
                {},
            )
            return
        rows = self.query(
            source_cursor,
            f"""
            SELECT wi.id, wi.product_id, wi.warehouse_id, wi.unit_id, wi.inventory,
                   wi.add_time, wi.upd_time
            FROM {self.source_table('sxo_plugins_erp_warehouse_product_inventory')} wi
            ORDER BY wi.warehouse_id, wi.product_id, wi.unit_id
            """,
        )
        sku_rows = self.product_sku_rows(target_cursor)
        balance_rows: list[tuple] = []
        ledger_rows: list[tuple] = []
        skipped_missing_map = []
        for row in rows:
            old_product_id = str(row["product_id"])
            sku_id = sku_map.get(old_product_id)
            if not sku_id:
                skipped_missing_map.append({"old_product_id": int(row["product_id"]), "warehouse_id": int(row["warehouse_id"])})
                continue
            sku = sku_rows.get(sku_id, {})
            unit_id = int(row.get("unit_id") or 0) or int(sku.get("unit_id") or 0)
            if not unit_id:
                skipped_missing_map.append({"old_product_id": int(row["product_id"]), "reason": "missing_unit_id"})
                continue
            quantity = as_decimal(row.get("inventory"))
            reserved = Decimal("0")
            occurred_at = as_dt(row.get("upd_time") or row.get("add_time"))
            warehouse_id = int(row["warehouse_id"])
            sku_no = clean_text(sku.get("sku_no"), 80) or f"SKU{sku_id}"
            ledger_no = self.migration_ledger_no(sku_id, warehouse_id, unit_id)
            balance_rows.append((sku_id, warehouse_id, unit_id, quantity, reserved, quantity - reserved, None, 1, occurred_at))
            ledger_rows.append(
                (
                    ledger_no,
                    sku_id,
                    sku_no,
                    warehouse_id,
                    unit_id,
                    quantity,
                    Decimal("0"),
                    quantity,
                    "migration_init",
                    None,
                    None,
                    None,
                    None,
                    "Initial inventory snapshot from legacy ERP.",
                    occurred_at,
                    occurred_at,
                )
            )
        self.executemany(
            target_cursor,
            f"""
            INSERT INTO {self.table('inventory_ledger')}
                (ledger_no, sku_id, sku_no_snapshot, warehouse_id, unit_id, change_qty,
                 before_qty, after_qty, biz_type, biz_id, biz_item_id,
                 counterparty_warehouse_id, operator_user_id, note, occurred_at, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE
                sku_no_snapshot=VALUES(sku_no_snapshot), change_qty=VALUES(change_qty),
                before_qty=VALUES(before_qty), after_qty=VALUES(after_qty),
                note=VALUES(note), occurred_at=VALUES(occurred_at)
            """,
            ledger_rows,
        )
        ledger_ids = self.ledger_id_map(target_cursor)
        balance_rows_with_ledger = []
        for row in balance_rows:
            sku_id, warehouse_id, unit_id, quantity, reserved, available, low_stock, version, updated_at = row
            ledger_id = ledger_ids.get(self.migration_ledger_no(sku_id, warehouse_id, unit_id))
            balance_rows_with_ledger.append((sku_id, warehouse_id, unit_id, quantity, reserved, available, low_stock, ledger_id, version, updated_at))
        self.executemany(
            target_cursor,
            f"""
            INSERT INTO {self.table('inventory_balance')}
                (sku_id, warehouse_id, unit_id, quantity, reserved_qty, available_qty,
                 low_stock_qty, last_ledger_id, version, updated_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE
                quantity=VALUES(quantity), reserved_qty=VALUES(reserved_qty),
                available_qty=VALUES(available_qty), low_stock_qty=VALUES(low_stock_qty),
                last_ledger_id=VALUES(last_ledger_id), version=version+1,
                updated_at=VALUES(updated_at)
            """,
            balance_rows_with_ledger,
        )
        if skipped_missing_map:
            self.report["inventory_skipped_missing_product_mapping"] = len(skipped_missing_map)
            self.warn(
                "inventory_missing_product_mapping",
                "Some legacy inventory rows could not be mapped through migration_product_ref.",
                skipped_missing_map[:100],
            )

    def product_sku_map(self, target_cursor) -> dict[str, int]:
        try:
            rows = self.query(
                target_cursor,
                f"""
                SELECT external_id, native_id
                FROM {self.table('migration_product_ref')}
                WHERE entity_type='sku'
                  AND source_table='sxo_plugins_erp_product.id'
                """,
            )
        except pymysql.err.ProgrammingError:
            return {}
        return {str(row["external_id"]): int(row["native_id"]) for row in rows}

    def product_sku_rows(self, target_cursor) -> dict[int, dict]:
        try:
            rows = self.query(target_cursor, f"SELECT id, sku_no, unit_id FROM {self.table('product_sku')}")
        except pymysql.err.ProgrammingError:
            return {}
        return {int(row["id"]): dict(row) for row in rows}

    def import_sales(self, source_cursor, target_cursor):
        if not self.source_table_exists(source_cursor, "sxo_plugins_erp_sales"):
            self.warn("missing_sales_source", "Legacy sales table does not exist; sales import skipped.", {})
            return
        customer_names = self.party_name_map(target_cursor)
        sales_rows = self.query(
            source_cursor,
            f"""
            SELECT id, sales_no, customer_id, pay_type, status, pay_status,
                   price, total_price, pay_price, buy_number_count, note, admin_note,
                   fail_reason, add_time, upd_time, cancel_time
            FROM {self.source_table('sxo_plugins_erp_sales')}
            ORDER BY id
            """,
        )
        sales_params = []
        for row in sales_rows:
            sales_id = int(row["id"])
            customer_id = int(row.get("customer_id") or 0) or 2
            total_price = as_decimal(row.get("total_price"))
            pay_price = as_decimal(row.get("pay_price"))
            note = "\n".join(
                part
                for part in [
                    clean_text(row.get("note")),
                    clean_text(row.get("admin_note")),
                    clean_text(row.get("fail_reason")),
                ]
                if part
            ) or None
            sales_at = as_dt(row.get("add_time"))
            updated_at = as_dt(row.get("upd_time") or row.get("add_time"))
            sales_params.append(
                (
                    sales_id,
                    clean_text(row.get("sales_no"), 80) or f"XS-MIG-{sales_id}",
                    customer_id,
                    customer_names.get(customer_id, f"客户{customer_id}"),
                    self.sales_status(row),
                    self.pay_type(row.get("pay_type")),
                    self.pay_status(row.get("pay_status"), pay_price, total_price),
                    as_decimal(row.get("buy_number_count")),
                    total_price,
                    Decimal("0"),
                    total_price,
                    "migration",
                    None,
                    "none",
                    note,
                    None,
                    sales_at,
                    sales_at,
                    updated_at,
                    as_dt(row.get("cancel_time")) if int(row.get("cancel_time") or 0) > 0 else None,
                    clean_text(row.get("fail_reason"), 500) or None,
                )
            )
        self.executemany(
            target_cursor,
            f"""
            INSERT INTO {self.table('sales_order')}
                (id, sales_no, customer_id, customer_name_snapshot, status, pay_type,
                 pay_status, total_quantity, goods_amount, discount_amount,
                 receivable_amount, source, source_workflow_id, print_status, note,
                 created_by_user_id, sales_at, created_at, updated_at, canceled_at,
                 cancel_reason)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE
                sales_no=VALUES(sales_no), customer_id=VALUES(customer_id),
                customer_name_snapshot=VALUES(customer_name_snapshot), status=VALUES(status),
                pay_type=VALUES(pay_type), pay_status=VALUES(pay_status),
                total_quantity=VALUES(total_quantity), goods_amount=VALUES(goods_amount),
                discount_amount=VALUES(discount_amount),
                receivable_amount=VALUES(receivable_amount), note=VALUES(note),
                sales_at=VALUES(sales_at), updated_at=VALUES(updated_at),
                canceled_at=VALUES(canceled_at), cancel_reason=VALUES(cancel_reason)
            """,
            sales_params,
        )
        self.import_sales_items(source_cursor, target_cursor)

    def import_sales_items(self, source_cursor, target_cursor):
        if not self.source_table_exists(source_cursor, "sxo_plugins_erp_sales_detail"):
            return
        sku_map = self.product_sku_map(target_cursor)
        sku_rows = self.product_sku_rows(target_cursor)
        rows = self.query(
            source_cursor,
            f"""
            SELECT d.id, d.sales_id, d.product_id, d.unit_id, d.warehouse_id,
                   d.title, d.spec, d.price, d.buy_number, d.total_price,
                   d.note, d.add_time
            FROM {self.source_table('sxo_plugins_erp_sales_detail')} d
            JOIN {self.source_table('sxo_plugins_erp_sales')} s ON s.id = d.sales_id
            ORDER BY d.sales_id, d.id
            """,
        )
        params = []
        skipped = []
        line_no_by_sales: dict[int, int] = {}
        for row in rows:
            sales_id = int(row["sales_id"])
            sku_id = sku_map.get(str(row.get("product_id")))
            if not sku_id:
                skipped.append({"detail_id": int(row["id"]), "old_product_id": int(row.get("product_id") or 0)})
                continue
            line_no_by_sales[sales_id] = line_no_by_sales.get(sales_id, 0) + 1
            sku = sku_rows.get(sku_id, {})
            unit_id = int(row.get("unit_id") or 0) or int(sku.get("unit_id") or 1)
            warehouse_id = int(row.get("warehouse_id") or 0) or int(self.config.get("erp.warehouse.baixin", 2))
            unit_price = as_decimal(row.get("price"))
            amount = as_decimal(row.get("total_price")) or unit_price * as_decimal(row.get("buy_number"))
            params.append(
                (
                    int(row["id"]),
                    sales_id,
                    line_no_by_sales[sales_id],
                    sku_id,
                    clean_text(sku.get("sku_no"), 80) or f"SKU{sku_id}",
                    clean_text(row.get("title"), 180) or clean_text(sku.get("sku_no"), 80) or f"SKU{sku_id}",
                    clean_text(row.get("spec"), 60) or None,
                    warehouse_id,
                    unit_id,
                    as_decimal(row.get("buy_number")),
                    unit_price,
                    amount,
                    None,
                    "migration",
                    None,
                    clean_text(row.get("note"), 500) or None,
                    as_dt(row.get("add_time")),
                )
            )
        self.executemany(
            target_cursor,
            f"""
            INSERT INTO {self.table('sales_order_item')}
                (id, sales_order_id, line_no, sku_id, sku_no_snapshot, title_snapshot,
                 color_snapshot, warehouse_id, unit_id, quantity, unit_price, amount,
                 cost_price_snapshot, price_source, workflow_order_id, note, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE
                sales_order_id=VALUES(sales_order_id), line_no=VALUES(line_no),
                sku_id=VALUES(sku_id), sku_no_snapshot=VALUES(sku_no_snapshot),
                title_snapshot=VALUES(title_snapshot), color_snapshot=VALUES(color_snapshot),
                warehouse_id=VALUES(warehouse_id), unit_id=VALUES(unit_id),
                quantity=VALUES(quantity), unit_price=VALUES(unit_price),
                amount=VALUES(amount), price_source=VALUES(price_source),
                note=VALUES(note)
            """,
            params,
        )
        if skipped:
            self.report["sales_item_skipped_missing_product_mapping"] = len(skipped)
            self.warn(
                "sales_item_missing_product_mapping",
                "Some sales detail rows could not be mapped through migration_product_ref.",
                skipped[:100],
            )

    def party_name_map(self, target_cursor) -> dict[int, str]:
        rows = self.query(target_cursor, f"SELECT id, name FROM {self.table('party')}")
        return {int(row["id"]): str(row["name"]) for row in rows}

    def sales_status(self, row: dict) -> str:
        status = int(row.get("status") or 0)
        if int(row.get("cancel_time") or 0) > 0:
            return "canceled"
        if status in {3, 4, 5}:
            return "completed"
        return "draft"

    def pay_type(self, value: Any) -> str | None:
        code = int(value or 0)
        return {1: "cash", 2: "wechat", 3: "monthly", 4: "account"}.get(code)

    def pay_status(self, value: Any, pay_price: Decimal, total_price: Decimal) -> str:
        code = int(value or 0)
        if total_price > 0 and pay_price >= total_price:
            return "paid"
        if pay_price > 0:
            return "partial"
        if code == 1:
            return "paid"
        return "unpaid"

    def import_workflow_orders(self, source_cursor, target_cursor):
        rows = []
        if self.source_table_exists(source_cursor, "sxo_workflow_order"):
            rows.extend(
                (
                    "workflow",
                    int(row["id"]),
                    int(row["id"]),
                    row,
                )
                for row in self.query(
                    source_cursor,
                    f"""
                    SELECT id, order_type, customer_name, customer_phone, order_images,
                           order_quantity, is_screen_print, is_made, is_delivered,
                           goods_name, goods_color, order_time, complete_time,
                           add_time, upd_time
                    FROM {self.source_table('sxo_workflow_order')}
                    ORDER BY id
                    """,
                )
            )
        if self.source_table_exists(source_cursor, "sxo_bx_workflow_order"):
            rows.extend(
                (
                    "bx_workflow",
                    int(row["id"]),
                    1000000 + int(row["id"]),
                    row,
                )
                for row in self.query(
                    source_cursor,
                    f"""
                    SELECT id, order_type, packaging_shop_name, shop_id, customer_name,
                           customer_phone, order_images, order_quantity, is_screen_print,
                           is_made, is_delivered, goods_name, goods_color, order_time,
                           complete_time, add_time, upd_time
                    FROM {self.source_table('sxo_bx_workflow_order')}
                    ORDER BY id
                    """,
                )
            )
        order_params = []
        log_params = []
        for source_name, old_id, new_id, row in rows:
            created_at = as_dt(row.get("add_time") or row.get("order_time"))
            updated_at = as_dt(row.get("upd_time") or row.get("complete_time") or row.get("add_time"))
            customer_name = first_non_empty(row.get("customer_name"), row.get("packaging_shop_name"), "未填客户")[:160]
            goods_name = first_non_empty(row.get("goods_name"), row.get("packaging_shop_name"), "未填商品")[:180]
            remark_parts = []
            if source_name == "bx_workflow":
                remark_parts.append(f"包装店：{clean_text(row.get('packaging_shop_name')) or '未填'}")
                if int(row.get("shop_id") or 0):
                    remark_parts.append(f"旧 shop_id：{int(row.get('shop_id') or 0)}")
            order_params.append(
                (
                    new_id,
                    f"WF-MIG-{source_name.upper()}-{old_id}",
                    None,
                    customer_name,
                    clean_text(row.get("customer_phone"), 40) or None,
                    None,
                    None,
                    goods_name,
                    clean_text(row.get("goods_color"), 60) or None,
                    as_decimal(row.get("order_quantity")),
                    None,
                    self.workflow_order_type(row.get("order_type")),
                    json_array_text(row.get("order_images")),
                    None,
                    1 if int(row.get("is_screen_print") or 0) else 0,
                    1 if int(row.get("is_made") or 0) else 0,
                    1 if int(row.get("is_delivered") or 0) else 0,
                    None,
                    self.workflow_status(row),
                    "\n".join(part for part in remark_parts if part) or None,
                    source_name,
                    None,
                    created_at,
                    updated_at,
                    None,
                )
            )
            log_params.append(
                (
                    new_id,
                    new_id,
                    "migration_import",
                    "source",
                    None,
                    f"{source_name}:{old_id}",
                    None,
                    "从旧工作流订单迁移",
                    created_at,
                )
            )
        self.executemany(
            target_cursor,
            f"""
            INSERT INTO {self.table('workflow_order')}
                (id, workflow_no, customer_id, customer_name_snapshot,
                 customer_phone_snapshot, sku_id, sku_no_snapshot,
                 goods_name_snapshot, color_snapshot, quantity, unit_id,
                 order_type, order_image_urls, ocr_text, is_screen_print,
                 is_made, is_delivered, sales_order_id, status, remark, source,
                 created_by_user_id, created_at, updated_at, deleted_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE
                customer_name_snapshot=VALUES(customer_name_snapshot),
                customer_phone_snapshot=VALUES(customer_phone_snapshot),
                goods_name_snapshot=VALUES(goods_name_snapshot),
                color_snapshot=VALUES(color_snapshot), quantity=VALUES(quantity),
                order_type=VALUES(order_type), order_image_urls=VALUES(order_image_urls),
                is_screen_print=VALUES(is_screen_print), is_made=VALUES(is_made),
                is_delivered=VALUES(is_delivered), status=VALUES(status),
                remark=VALUES(remark), source=VALUES(source),
                updated_at=VALUES(updated_at)
            """,
            order_params,
        )
        self.executemany(
            target_cursor,
            f"""
            INSERT INTO {self.table('workflow_order_log')}
                (id, workflow_order_id, action, field_name, old_value,
                 new_value, operator_user_id, note, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE
                workflow_order_id=VALUES(workflow_order_id), action=VALUES(action),
                field_name=VALUES(field_name), new_value=VALUES(new_value),
                note=VALUES(note)
            """,
            log_params,
        )

    def workflow_order_type(self, value: Any) -> str:
        code = int(value or 0)
        return {1: "design", 2: "screen_print", 3: "bag", 4: "full_service"}.get(code, "other")

    def workflow_status(self, row: dict) -> str:
        if int(row.get("is_delivered") or 0):
            return "done"
        if int(row.get("is_made") or 0):
            return "processing"
        return "pending"

    def import_stock_documents(self, source_cursor, target_cursor):
        self.import_other_enter(source_cursor, target_cursor)
        self.import_other_out(source_cursor, target_cursor)

    def import_other_enter(self, source_cursor, target_cursor):
        if not self.source_table_exists(source_cursor, "sxo_plugins_erp_other_enter"):
            return
        rows = self.query(
            source_cursor,
            f"""
            SELECT id, other_enter_no, supplier_id, warehouse_id, status,
                   total_price, enter_number_count, fail_reason, admin_note,
                   note, success_time, cancel_time, add_time, upd_time
            FROM {self.source_table('sxo_plugins_erp_other_enter')}
            ORDER BY id
            """,
        )
        params = []
        for row in rows:
            doc_id = int(row["id"])
            params.append(
                (
                    doc_id,
                    clean_text(row.get("other_enter_no"), 80) or f"RK-MIG-{doc_id}",
                    "purchase_in",
                    "in",
                    int(row.get("warehouse_id") or 0) or int(self.config.get("erp.warehouse.baixin", 2)),
                    int(row.get("supplier_id") or 0) or None,
                    None,
                    self.document_status(row),
                    as_decimal(row.get("enter_number_count")),
                    self.combine_notes(row.get("note"), row.get("admin_note"), row.get("fail_reason")),
                    None,
                    as_dt(row.get("add_time")),
                    as_dt(row.get("success_time")) if int(row.get("success_time") or 0) > 0 else None,
                    as_dt(row.get("cancel_time")) if int(row.get("cancel_time") or 0) > 0 else None,
                )
            )
        self.upsert_stock_documents(target_cursor, params)
        self.import_stock_document_items(
            source_cursor,
            target_cursor,
            source_table="sxo_plugins_erp_other_enter_detail",
            parent_column="other_enter_id",
            quantity_column="enter_number",
            source_offset=0,
        )

    def import_other_out(self, source_cursor, target_cursor):
        if not self.source_table_exists(source_cursor, "sxo_plugins_erp_other_out"):
            return
        rows = self.query(
            source_cursor,
            f"""
            SELECT id, other_out_no, customer_id, warehouse_id, status,
                   total_price, out_number_count, fail_reason, admin_note,
                   note, success_time, cancel_time, add_time, upd_time
            FROM {self.source_table('sxo_plugins_erp_other_out')}
            ORDER BY id
            """,
        )
        params = []
        for row in rows:
            old_id = int(row["id"])
            doc_id = 1000000 + old_id
            params.append(
                (
                    doc_id,
                    clean_text(row.get("other_out_no"), 80) or f"CK-MIG-{old_id}",
                    "other_out",
                    "out",
                    int(row.get("warehouse_id") or 0) or int(self.config.get("erp.warehouse.self", 1)),
                    int(row.get("customer_id") or 0) or None,
                    None,
                    self.document_status(row),
                    as_decimal(row.get("out_number_count")),
                    self.combine_notes(row.get("note"), row.get("admin_note"), row.get("fail_reason")),
                    None,
                    as_dt(row.get("add_time")),
                    as_dt(row.get("success_time")) if int(row.get("success_time") or 0) > 0 else None,
                    as_dt(row.get("cancel_time")) if int(row.get("cancel_time") or 0) > 0 else None,
                )
            )
        self.upsert_stock_documents(target_cursor, params)
        self.import_stock_document_items(
            source_cursor,
            target_cursor,
            source_table="sxo_plugins_erp_other_out_detail",
            parent_column="other_out_id",
            quantity_column="out_number",
            source_offset=1000000,
        )

    def upsert_stock_documents(self, target_cursor, params: list[tuple]):
        self.executemany(
            target_cursor,
            f"""
            INSERT INTO {self.table('stock_document')}
                (id, doc_no, doc_type, direction, warehouse_id, related_party_id,
                 related_sales_order_id, status, total_quantity, note,
                 created_by_user_id, created_at, confirmed_at, canceled_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE
                doc_no=VALUES(doc_no), doc_type=VALUES(doc_type),
                direction=VALUES(direction), warehouse_id=VALUES(warehouse_id),
                related_party_id=VALUES(related_party_id),
                status=VALUES(status), total_quantity=VALUES(total_quantity),
                note=VALUES(note), confirmed_at=VALUES(confirmed_at),
                canceled_at=VALUES(canceled_at)
            """,
            params,
        )

    def import_stock_document_items(
        self,
        source_cursor,
        target_cursor,
        source_table: str,
        parent_column: str,
        quantity_column: str,
        source_offset: int,
    ):
        if not self.source_table_exists(source_cursor, source_table):
            return
        sku_map = self.product_sku_map(target_cursor)
        sku_rows = self.product_sku_rows(target_cursor)
        rows = self.query(
            source_cursor,
            f"""
            SELECT id, {parent_column} AS parent_id, product_id, unit_id, title, spec,
                   price, {quantity_column} AS quantity, total_price, note, add_time
            FROM {self.source_table(source_table)}
            ORDER BY {parent_column}, id
            """,
        )
        params = []
        skipped = []
        line_no_by_parent: dict[int, int] = {}
        for row in rows:
            parent_id = source_offset + int(row["parent_id"])
            sku_id = sku_map.get(str(row.get("product_id")))
            if not sku_id:
                skipped.append({"source_table": source_table, "detail_id": int(row["id"]), "old_product_id": int(row.get("product_id") or 0)})
                continue
            line_no_by_parent[parent_id] = line_no_by_parent.get(parent_id, 0) + 1
            sku = sku_rows.get(sku_id, {})
            params.append(
                (
                    source_offset + int(row["id"]),
                    parent_id,
                    line_no_by_parent[parent_id],
                    sku_id,
                    clean_text(sku.get("sku_no"), 80) or f"SKU{sku_id}",
                    clean_text(row.get("title"), 180) or clean_text(sku.get("sku_no"), 80) or f"SKU{sku_id}",
                    int(row.get("unit_id") or 0) or int(sku.get("unit_id") or 1),
                    as_decimal(row.get("quantity")),
                    as_decimal(row.get("price")),
                    as_decimal(row.get("total_price")),
                    clean_text(row.get("note"), 200) or None,
                    None,
                    as_dt(row.get("add_time")),
                )
            )
        self.executemany(
            target_cursor,
            f"""
            INSERT INTO {self.table('stock_document_item')}
                (id, stock_document_id, line_no, sku_id, sku_no_snapshot,
                 title_snapshot, unit_id, quantity, unit_cost, amount,
                 reason, ledger_id, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE
                stock_document_id=VALUES(stock_document_id), line_no=VALUES(line_no),
                sku_id=VALUES(sku_id), sku_no_snapshot=VALUES(sku_no_snapshot),
                title_snapshot=VALUES(title_snapshot), unit_id=VALUES(unit_id),
                quantity=VALUES(quantity), unit_cost=VALUES(unit_cost),
                amount=VALUES(amount), reason=VALUES(reason)
            """,
            params,
        )
        if skipped:
            self.warn(
                "stock_document_item_missing_product_mapping",
                "Some stock document items could not be mapped through migration_product_ref.",
                skipped[:100],
            )

    def import_stocktakes(self, source_cursor, target_cursor):
        if not self.source_table_exists(source_cursor, "sxo_plugins_erp_inventory_check"):
            return
        rows = self.query(
            source_cursor,
            f"""
            SELECT id, inventory_check_no, warehouse_id, status, check_number_count,
                   check_user, fail_reason, note, check_time, success_time,
                   cancel_time, add_time, upd_time
            FROM {self.source_table('sxo_plugins_erp_inventory_check')}
            ORDER BY id
            """,
        )
        params = []
        for row in rows:
            stocktake_id = int(row["id"])
            params.append(
                (
                    stocktake_id,
                    clean_text(row.get("inventory_check_no"), 80) or f"PD-MIG-{stocktake_id}",
                    int(row.get("warehouse_id") or 0) or int(self.config.get("erp.warehouse.baixin", 2)),
                    "all",
                    None,
                    self.document_status(row),
                    Decimal("0"),
                    self.combine_notes(row.get("note"), row.get("fail_reason"), f"旧盘点人：{clean_text(row.get('check_user'))}" if clean_text(row.get("check_user")) else ""),
                    None,
                    as_dt(row.get("add_time")),
                    as_dt(row.get("success_time") or row.get("check_time")) if int(row.get("success_time") or row.get("check_time") or 0) > 0 else None,
                )
            )
        self.executemany(
            target_cursor,
            f"""
            INSERT INTO {self.table('stocktake_order')}
                (id, stocktake_no, warehouse_id, scope_type, scope_value, status,
                 total_diff_qty, note, created_by_user_id, created_at, confirmed_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE
                stocktake_no=VALUES(stocktake_no), warehouse_id=VALUES(warehouse_id),
                status=VALUES(status), note=VALUES(note),
                confirmed_at=VALUES(confirmed_at)
            """,
            params,
        )
        self.import_stocktake_items(source_cursor, target_cursor)

    def import_stocktake_items(self, source_cursor, target_cursor):
        if not self.source_table_exists(source_cursor, "sxo_plugins_erp_inventory_check_detail"):
            return
        sku_map = self.product_sku_map(target_cursor)
        sku_rows = self.product_sku_rows(target_cursor)
        rows = self.query(
            source_cursor,
            f"""
            SELECT id, inventory_check_id, product_id, unit_id, check_number,
                   note, add_time
            FROM {self.source_table('sxo_plugins_erp_inventory_check_detail')}
            ORDER BY inventory_check_id, id
            """,
        )
        params = []
        skipped = []
        for row in rows:
            sku_id = sku_map.get(str(row.get("product_id")))
            if not sku_id:
                skipped.append({"detail_id": int(row["id"]), "old_product_id": int(row.get("product_id") or 0)})
                continue
            sku = sku_rows.get(sku_id, {})
            counted_qty = as_decimal(row.get("check_number"))
            params.append(
                (
                    int(row["id"]),
                    int(row["inventory_check_id"]),
                    sku_id,
                    int(row.get("unit_id") or 0) or int(sku.get("unit_id") or 1),
                    counted_qty,
                    counted_qty,
                    Decimal("0"),
                    self.combine_notes(row.get("note"), "旧盘点没有账面数，迁移时按实盘数保存，差异先置 0。"),
                    None,
                    as_dt(row.get("add_time")),
                )
            )
        self.executemany(
            target_cursor,
            f"""
            INSERT INTO {self.table('stocktake_item')}
                (id, stocktake_order_id, sku_id, unit_id, book_qty, counted_qty,
                 diff_qty, reason, ledger_id, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE
                stocktake_order_id=VALUES(stocktake_order_id),
                sku_id=VALUES(sku_id), unit_id=VALUES(unit_id),
                book_qty=VALUES(book_qty), counted_qty=VALUES(counted_qty),
                diff_qty=VALUES(diff_qty), reason=VALUES(reason)
            """,
            params,
        )
        if skipped:
            self.warn(
                "stocktake_item_missing_product_mapping",
                "Some stocktake items could not be mapped through migration_product_ref.",
                skipped[:100],
            )

    def import_transfers(self, source_cursor, target_cursor):
        if not self.source_table_exists(source_cursor, "sxo_plugins_erp_inventory_transfer"):
            return
        rows = self.query(
            source_cursor,
            f"""
            SELECT id, inventory_transfer_no, out_warehouse_id, enter_warehouse_id,
                   status, transfer_number_count, transfer_user, fail_reason, note,
                   transfer_time, success_time, cancel_time, add_time, upd_time
            FROM {self.source_table('sxo_plugins_erp_inventory_transfer')}
            ORDER BY id
            """,
        )
        params = []
        for row in rows:
            transfer_id = int(row["id"])
            params.append(
                (
                    transfer_id,
                    clean_text(row.get("inventory_transfer_no"), 80) or f"DB-MIG-{transfer_id}",
                    int(row.get("out_warehouse_id") or 0),
                    int(row.get("enter_warehouse_id") or 0),
                    self.document_status(row),
                    as_decimal(row.get("transfer_number_count")),
                    self.combine_notes(row.get("note"), row.get("fail_reason"), f"旧调拨人：{clean_text(row.get('transfer_user'))}" if clean_text(row.get("transfer_user")) else ""),
                    None,
                    as_dt(row.get("add_time")),
                    as_dt(row.get("success_time") or row.get("transfer_time")) if int(row.get("success_time") or row.get("transfer_time") or 0) > 0 else None,
                    as_dt(row.get("cancel_time")) if int(row.get("cancel_time") or 0) > 0 else None,
                )
            )
        self.executemany(
            target_cursor,
            f"""
            INSERT INTO {self.table('transfer_order')}
                (id, transfer_no, from_warehouse_id, to_warehouse_id, status,
                 total_quantity, note, created_by_user_id, created_at,
                 confirmed_at, canceled_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE
                transfer_no=VALUES(transfer_no),
                from_warehouse_id=VALUES(from_warehouse_id),
                to_warehouse_id=VALUES(to_warehouse_id),
                status=VALUES(status), total_quantity=VALUES(total_quantity),
                note=VALUES(note), confirmed_at=VALUES(confirmed_at),
                canceled_at=VALUES(canceled_at)
            """,
            params,
        )
        self.import_transfer_items(source_cursor, target_cursor)

    def import_transfer_items(self, source_cursor, target_cursor):
        if not self.source_table_exists(source_cursor, "sxo_plugins_erp_inventory_transfer_detail"):
            return
        sku_map = self.product_sku_map(target_cursor)
        sku_rows = self.product_sku_rows(target_cursor)
        rows = self.query(
            source_cursor,
            f"""
            SELECT id, inventory_transfer_id, product_id, unit_id, title,
                   transfer_number, note, add_time
            FROM {self.source_table('sxo_plugins_erp_inventory_transfer_detail')}
            ORDER BY inventory_transfer_id, id
            """,
        )
        params = []
        skipped = []
        line_no_by_parent: dict[int, int] = {}
        for row in rows:
            transfer_id = int(row["inventory_transfer_id"])
            sku_id = sku_map.get(str(row.get("product_id")))
            if not sku_id:
                skipped.append({"detail_id": int(row["id"]), "old_product_id": int(row.get("product_id") or 0)})
                continue
            line_no_by_parent[transfer_id] = line_no_by_parent.get(transfer_id, 0) + 1
            sku = sku_rows.get(sku_id, {})
            params.append(
                (
                    int(row["id"]),
                    transfer_id,
                    line_no_by_parent[transfer_id],
                    sku_id,
                    clean_text(sku.get("sku_no"), 80) or f"SKU{sku_id}",
                    clean_text(row.get("title"), 180) or clean_text(sku.get("sku_no"), 80) or f"SKU{sku_id}",
                    int(row.get("unit_id") or 0) or int(sku.get("unit_id") or 1),
                    as_decimal(row.get("transfer_number")),
                    None,
                    None,
                    clean_text(row.get("note"), 500) or None,
                    as_dt(row.get("add_time")),
                )
            )
        self.executemany(
            target_cursor,
            f"""
            INSERT INTO {self.table('transfer_order_item')}
                (id, transfer_order_id, line_no, sku_id, sku_no_snapshot,
                 title_snapshot, unit_id, quantity, out_ledger_id,
                 in_ledger_id, note, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE
                transfer_order_id=VALUES(transfer_order_id),
                line_no=VALUES(line_no), sku_id=VALUES(sku_id),
                sku_no_snapshot=VALUES(sku_no_snapshot),
                title_snapshot=VALUES(title_snapshot), unit_id=VALUES(unit_id),
                quantity=VALUES(quantity), note=VALUES(note)
            """,
            params,
        )
        if skipped:
            self.warn(
                "transfer_item_missing_product_mapping",
                "Some transfer items could not be mapped through migration_product_ref.",
                skipped[:100],
            )

    def document_status(self, row: dict) -> str:
        status = int(row.get("status") or 0)
        if int(row.get("cancel_time") or 0) > 0 or status in {4, 5}:
            return "canceled"
        if status in {2, 3}:
            return "confirmed"
        return "draft"

    def combine_notes(self, *values: Any) -> str | None:
        text = "\n".join(clean_text(value) for value in values if clean_text(value))
        return text or None

    def ledger_id_map(self, target_cursor) -> dict[str, int]:
        rows = self.query(
            target_cursor,
            f"SELECT id, ledger_no FROM {self.table('inventory_ledger')} WHERE biz_type='migration_init'",
        )
        return {str(row["ledger_no"]): int(row["id"]) for row in rows}

    def migration_ledger_no(self, sku_id: int, warehouse_id: int, unit_id: int) -> str:
        digest = hashlib.sha1(f"{sku_id}:{warehouse_id}:{unit_id}".encode("utf-8")).hexdigest()[:12]
        return f"MIGINIT-{warehouse_id}-{sku_id}-{unit_id}-{digest}"

    def refresh_report_counts(self, source_cursor, target_cursor):
        counts: dict[str, int] = {}
        source_count_queries = {
            "source_warehouses": f"SELECT COUNT(*) AS cnt FROM {self.source_table('sxo_plugins_erp_warehouse')}",
            "source_parties": f"SELECT COUNT(*) AS cnt FROM {self.source_table('sxo_plugins_erp_company')}",
            "source_inventory_rows": f"SELECT COUNT(*) AS cnt FROM {self.source_table('sxo_plugins_erp_warehouse_product_inventory')}",
        }
        if self.source_table_exists(source_cursor, "sjagent_web_users"):
            source_count_queries["source_web_users"] = f"SELECT COUNT(*) AS cnt FROM {self.source_table('sjagent_web_users')}"
        if self.source_table_exists(source_cursor, "sxo_user"):
            source_count_queries["source_shopxo_users"] = f"SELECT COUNT(*) AS cnt FROM {self.source_table('sxo_user')}"
        if self.source_table_exists(source_cursor, "sxo_plugins_erp_sales"):
            source_count_queries["source_sales_orders"] = f"SELECT COUNT(*) AS cnt FROM {self.source_table('sxo_plugins_erp_sales')}"
        if self.source_table_exists(source_cursor, "sxo_plugins_erp_sales_detail"):
            source_count_queries["source_sales_items"] = f"SELECT COUNT(*) AS cnt FROM {self.source_table('sxo_plugins_erp_sales_detail')}"
        optional_source_counts = {
            "source_workflow_orders": "sxo_workflow_order",
            "source_bx_workflow_orders": "sxo_bx_workflow_order",
            "source_other_enter": "sxo_plugins_erp_other_enter",
            "source_other_enter_items": "sxo_plugins_erp_other_enter_detail",
            "source_other_out": "sxo_plugins_erp_other_out",
            "source_other_out_items": "sxo_plugins_erp_other_out_detail",
            "source_stocktake_orders": "sxo_plugins_erp_inventory_check",
            "source_stocktake_items": "sxo_plugins_erp_inventory_check_detail",
            "source_transfer_orders": "sxo_plugins_erp_inventory_transfer",
            "source_transfer_items": "sxo_plugins_erp_inventory_transfer_detail",
        }
        for key, table_name in optional_source_counts.items():
            if self.source_table_exists(source_cursor, table_name):
                source_count_queries[key] = f"SELECT COUNT(*) AS cnt FROM {self.source_table(table_name)}"
        target_count_queries = {
            "warehouse": f"SELECT COUNT(*) AS cnt FROM {self.table('warehouse')}",
            "party": f"SELECT COUNT(*) AS cnt FROM {self.table('party')}",
            "auth_user": f"SELECT COUNT(*) AS cnt FROM {self.table('auth_user')}",
            "auth_identity": f"SELECT COUNT(*) AS cnt FROM {self.table('auth_identity')}",
            "inventory_balance": f"SELECT COUNT(*) AS cnt FROM {self.table('inventory_balance')}",
            "inventory_ledger_migration_init": f"SELECT COUNT(*) AS cnt FROM {self.table('inventory_ledger')} WHERE biz_type='migration_init'",
            "sales_order": f"SELECT COUNT(*) AS cnt FROM {self.table('sales_order')}",
            "sales_order_item": f"SELECT COUNT(*) AS cnt FROM {self.table('sales_order_item')}",
            "workflow_order": f"SELECT COUNT(*) AS cnt FROM {self.table('workflow_order')}",
            "workflow_order_log": f"SELECT COUNT(*) AS cnt FROM {self.table('workflow_order_log')}",
            "stock_document": f"SELECT COUNT(*) AS cnt FROM {self.table('stock_document')}",
            "stock_document_item": f"SELECT COUNT(*) AS cnt FROM {self.table('stock_document_item')}",
            "stocktake_order": f"SELECT COUNT(*) AS cnt FROM {self.table('stocktake_order')}",
            "stocktake_item": f"SELECT COUNT(*) AS cnt FROM {self.table('stocktake_item')}",
            "transfer_order": f"SELECT COUNT(*) AS cnt FROM {self.table('transfer_order')}",
            "transfer_order_item": f"SELECT COUNT(*) AS cnt FROM {self.table('transfer_order_item')}",
        }
        for key, sql in source_count_queries.items():
            rows = self.query(source_cursor, sql)
            counts[key] = int(rows[0]["cnt"] or 0) if rows else 0
        for key, sql in target_count_queries.items():
            rows = self.query(target_cursor, sql)
            counts[key] = int(rows[0]["cnt"] or 0) if rows else 0
        self.report["counts"] = counts

    def write_report(self):
        self.report["finished_at"] = datetime.now().isoformat(timespec="seconds")
        report_path = ROOT / "data" / "migration" / "business_core_import_report.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(self.report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        return report_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create/import core business tables.")
    default_target_db = env_first("SJAGENT_CORE_DB_NAME", "SJAGENT_CORE_DB", default=DEFAULT_TARGET_DB)
    parser.add_argument("--target-db", default=default_target_db, help="Target native database/schema name.")
    parser.add_argument("--source-db", default=None, help="Source ShopXO/ERP database/schema name. Defaults to source env or config database.name.")
    parser.add_argument("--schema-only", action="store_true", help="Only create schema, do not import data.")
    parser.add_argument("--import-only", action="store_true", help="Only import data, assuming schema already exists.")
    parser.add_argument("--source-host", default=None, help="Source DB host override.")
    parser.add_argument("--source-port", default=None, help="Source DB port override.")
    parser.add_argument("--source-user", default=None, help="Source DB user override.")
    parser.add_argument("--source-password", default=None, help="Source DB password override.")
    parser.add_argument("--target-host", default=None, help="Target DB host override.")
    parser.add_argument("--target-port", default=None, help="Target DB port override.")
    parser.add_argument("--target-user", default=None, help="Target DB user override.")
    parser.add_argument("--target-password", default=None, help="Target DB password override.")
    return parser.parse_args()


def main() -> int:
    load_dotenv(ROOT / ".env")
    args = parse_args()
    config = get_config()
    source_db = args.source_db or env_first("SJAGENT_SOURCE_DB_NAME", "SOURCE_DB_NAME", default=config.db_config["name"])
    migrator = BusinessCoreMigrator(source_db=source_db, target_db=args.target_db, args=args)
    if not args.import_only:
        migrator.create_schema()
    if not args.schema_only:
        migrator.import_data()
    report_path = migrator.write_report()
    print(
        json.dumps(
            {
                "code": 0,
                "source_db": migrator.source_db,
                "target_db": migrator.target_db,
                "report_path": str(report_path),
                "counts": migrator.report.get("counts", {}),
                "warnings": len(migrator.report.get("warnings", [])),
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
