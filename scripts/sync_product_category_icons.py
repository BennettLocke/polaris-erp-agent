"""Sync ShopXO goods category image fields into the native product category table."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

import pymysql
from dotenv import load_dotenv
from pymysql.cursors import DictCursor

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.config import get_config  # noqa: E402


DEFAULT_TARGET_DB = "sjagent_core"
MEDIA_COLUMNS = (
    ("icon", "VARCHAR(500) NULL AFTER default_unit_id"),
    ("icon_active", "VARCHAR(500) NULL AFTER icon"),
    ("realistic_images", "VARCHAR(500) NULL AFTER icon_active"),
    ("big_images", "VARCHAR(500) NULL AFTER realistic_images"),
)


def quote_ident(name: str) -> str:
    if not re.fullmatch(r"[0-9A-Za-z_]+", name or ""):
        raise ValueError(f"Unsafe database/table identifier: {name!r}")
    return f"`{name}`"


def target_db_config(base_config: dict, target_db: str) -> dict:
    cfg = dict(base_config)
    cfg["host"] = os.getenv("SJAGENT_CORE_DB_HOST") or os.getenv("SJAGENT_CORE_HOST") or cfg["host"]
    cfg["port"] = int(os.getenv("SJAGENT_CORE_DB_PORT") or os.getenv("SJAGENT_CORE_PORT") or cfg["port"])
    cfg["name"] = os.getenv("SJAGENT_CORE_DB_NAME") or os.getenv("SJAGENT_CORE_DB") or target_db
    cfg["user"] = os.getenv("SJAGENT_CORE_DB_USER") or os.getenv("SJAGENT_CORE_USER") or cfg["user"]
    cfg["password"] = os.getenv("SJAGENT_CORE_DB_PASSWORD") or os.getenv("SJAGENT_CORE_PASSWORD") or cfg["password"]
    cfg["charset"] = os.getenv("SJAGENT_CORE_DB_CHARSET") or cfg.get("charset") or "utf8mb4"
    return cfg


def connect(cfg: dict, database: str):
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


def ensure_target_columns(cursor):
    for column, definition in MEDIA_COLUMNS:
        cursor.execute("SHOW COLUMNS FROM product_category LIKE %s", (column,))
        if cursor.fetchone() is None:
            cursor.execute(f"ALTER TABLE product_category ADD COLUMN {quote_ident(column)} {definition}")


def non_empty(value) -> str:
    return str(value or "").strip()


def source_category_icons(cursor, source_db: str) -> dict[str, dict]:
    cursor.execute(
        f"""
        SELECT name, icon, icon_active, realistic_images, big_images
        FROM {quote_ident(source_db)}.sxo_goods_category
        WHERE is_enable = 1
          AND (
            icon <> '' OR icon_active <> '' OR realistic_images <> '' OR big_images <> ''
          )
        ORDER BY sort ASC, id ASC
        """
    )
    rows = cursor.fetchall()
    result: dict[str, dict] = {}
    for row in rows:
        name = non_empty(row.get("name"))
        if not name or name in result:
            continue
        result[name] = {
            "icon": non_empty(row.get("icon")),
            "icon_active": non_empty(row.get("icon_active")),
            "realistic_images": non_empty(row.get("realistic_images")),
            "big_images": non_empty(row.get("big_images")),
        }
    return result


def sync_category_icons(source_db: str, target_db: str) -> dict:
    config = get_config()
    source_cfg = config.db_config
    target_cfg = target_db_config(config.db_config, target_db)
    effective_target_db = target_cfg["name"]

    with connect(source_cfg, source_db) as source_conn, connect(target_cfg, effective_target_db) as target_conn:
        with source_conn.cursor() as source_cursor, target_conn.cursor() as target_cursor:
            ensure_target_columns(target_cursor)
            source_icons = source_category_icons(source_cursor, source_db)
            target_cursor.execute("SELECT id, name FROM product_category WHERE is_enabled = 1 ORDER BY id ASC")
            targets = target_cursor.fetchall()
            matched = 0
            updated = 0
            missing: list[str] = []
            for row in targets:
                name = non_empty(row.get("name"))
                media = source_icons.get(name)
                if not media:
                    missing.append(name)
                    continue
                matched += 1
                target_cursor.execute(
                    """
                    UPDATE product_category
                    SET icon=%s, icon_active=%s, realistic_images=%s, big_images=%s
                    WHERE id=%s
                    """,
                    (
                        media["icon"],
                        media["icon_active"],
                        media["realistic_images"],
                        media["big_images"],
                        row["id"],
                    ),
                )
                updated += target_cursor.rowcount
        target_conn.commit()

    return {
        "code": 0,
        "source_db": source_db,
        "target_db": effective_target_db,
        "source_icon_categories": len(source_icons),
        "target_categories": len(targets),
        "matched": matched,
        "updated": updated,
        "missing": missing,
    }


def parse_args() -> argparse.Namespace:
    load_dotenv(ROOT / ".env")
    config = get_config()
    target_db = os.getenv("SJAGENT_CORE_DB_NAME") or os.getenv("SJAGENT_CORE_DB") or DEFAULT_TARGET_DB
    parser = argparse.ArgumentParser(description="Sync ShopXO category image fields into product_category.")
    parser.add_argument("--source-db", default=config.db_config["name"], help="Source ShopXO database/schema name.")
    parser.add_argument("--target-db", default=target_db, help="Target sjagent_core database/schema name.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    print(json.dumps(sync_category_icons(args.source_db, args.target_db), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
