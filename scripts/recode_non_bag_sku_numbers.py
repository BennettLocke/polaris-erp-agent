"""Recode non-bag SKU numbers into a compact SJ1001+ range.

The script leaves bag products untouched and records every changed SKU in
product_sku_recode_log. Historical sales/inventory snapshots are not changed.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

from src.engine.native_db import get_native_db_client  # noqa: E402


BAG_NAME_PATTERNS = ["%\u6ce1\u888b%", "%\u8336\u888b%"]


def fetch_candidates(cursor) -> list[dict[str, Any]]:
    cursor.execute(
        """
        SELECT
            s.id AS sku_id,
            s.spu_id,
            s.sku_no AS old_sku_no,
            s.color,
            sp.title,
            sp.product_type,
            pc.id AS category_id,
            pc.name AS category_name,
            pc.product_type AS category_product_type
        FROM product_sku s
        JOIN product_spu sp ON sp.id = s.spu_id
        LEFT JOIN product_category pc ON pc.id = COALESCE(sp.default_category_id, s.primary_category_id)
        WHERE s.deleted_at IS NULL
          AND sp.deleted_at IS NULL
          AND NOT (
            sp.product_type IN ('bag', 'bubble_bag')
            OR COALESCE(pc.product_type, '') = 'bag'
            OR COALESCE(pc.name, '') LIKE %s
            OR COALESCE(pc.name, '') LIKE %s
          )
        ORDER BY
            COALESCE(pc.id, 999999) ASC,
            sp.title ASC,
            COALESCE(s.color, '') ASC,
            s.id ASC
        """,
        BAG_NAME_PATTERNS,
    )
    return list(cursor.fetchall())


def fetch_used_codes(cursor) -> dict[str, int]:
    cursor.execute(
        """
        SELECT id, sku_no
        FROM product_sku
        WHERE sku_no REGEXP '^SJ[0-9]+$'
        """
    )
    return {str(row.get("sku_no") or ""): int(row.get("id") or 0) for row in cursor.fetchall()}


def build_plan(cursor, start: int) -> tuple[list[dict[str, Any]], list[str]]:
    candidates = fetch_candidates(cursor)
    candidate_ids = {int(row["sku_id"]) for row in candidates}
    used = fetch_used_codes(cursor)
    reserved = {code: sku_id for code, sku_id in used.items() if sku_id not in candidate_ids}
    assigned: set[str] = set()
    skipped: list[str] = []
    number = max(1, int(start))
    plan: list[dict[str, Any]] = []
    for row in candidates:
        while True:
            code = f"SJ{number:04d}"
            number += 1
            if code in assigned:
                continue
            if code in reserved:
                skipped.append(code)
                continue
            break
        item = dict(row)
        item["new_sku_no"] = code
        plan.append(item)
        assigned.add(code)
    return plan, skipped


def ensure_log_table(cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS product_sku_recode_log (
            id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
            batch_no VARCHAR(80) NOT NULL,
            sku_id BIGINT UNSIGNED NOT NULL,
            spu_id BIGINT UNSIGNED NULL,
            old_sku_no VARCHAR(80) NOT NULL,
            new_sku_no VARCHAR(80) NOT NULL,
            product_title VARCHAR(160) NULL,
            sku_color VARCHAR(60) NULL,
            category_name VARCHAR(80) NULL,
            changed_at DATETIME NOT NULL,
            note VARCHAR(255) NULL,
            PRIMARY KEY (id),
            UNIQUE KEY uk_recode_batch_sku (batch_no, sku_id),
            KEY idx_recode_sku_id (sku_id),
            KEY idx_recode_old_code (old_sku_no),
            KEY idx_recode_new_code (new_sku_no)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
    )


def apply_plan(cursor, plan: list[dict[str, Any]], batch_no: str) -> None:
    ensure_log_table(cursor)
    for item in plan:
        temp_code = f"TMP_RECODE_{batch_no}_{int(item['sku_id'])}"
        cursor.execute(
            "UPDATE product_sku SET sku_no=%s, updated_at=NOW() WHERE id=%s",
            (temp_code, int(item["sku_id"])),
        )
    for item in plan:
        cursor.execute(
            """
            INSERT INTO product_sku_recode_log
                (batch_no, sku_id, spu_id, old_sku_no, new_sku_no, product_title,
                 sku_color, category_name, changed_at, note)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s)
            """,
            (
                batch_no,
                int(item["sku_id"]),
                int(item["spu_id"]) if item.get("spu_id") else None,
                str(item.get("old_sku_no") or ""),
                str(item.get("new_sku_no") or ""),
                str(item.get("title") or ""),
                str(item.get("color") or ""),
                str(item.get("category_name") or ""),
                "non-bag recode from SJ1001",
            ),
        )
        cursor.execute(
            """
            UPDATE product_sku s
            JOIN product_spu sp ON sp.id = s.spu_id
            SET s.sku_no=%s,
                s.search_text=TRIM(CONCAT_WS(' ', sp.title, NULLIF(s.color, ''), %s)),
                s.updated_at=NOW()
            WHERE s.id=%s
            """,
            (str(item["new_sku_no"]), str(item["new_sku_no"]), int(item["sku_id"])),
        )


def print_preview(plan: list[dict[str, Any]], skipped: list[str], show: int) -> None:
    print(f"planned_count={len(plan)}")
    if plan:
        print(f"first_new_code={plan[0]['new_sku_no']}")
        print(f"last_new_code={plan[-1]['new_sku_no']}")
    print(f"reserved_bag_codes_skipped={len(skipped)}")
    if skipped:
        print("skipped_sample=" + ", ".join(skipped[:30]))
    for item in plan[: max(0, show)]:
        print(
            f"{item['sku_id']}: {item.get('old_sku_no')} -> {item.get('new_sku_no')} | "
            f"{item.get('category_name') or '-'} | {item.get('title') or '-'} | {item.get('color') or ''}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Recode non-bag product SKU numbers from SJ1001.")
    parser.add_argument("--start", type=int, default=1001)
    parser.add_argument("--apply", action="store_true", help="Apply changes. Without this flag the script only previews.")
    parser.add_argument("--show", type=int, default=25)
    args = parser.parse_args()

    client = get_native_db_client()
    if args.apply:
        batch_no = time.strftime("sku_recode_%Y%m%d_%H%M%S")
        with client.transaction() as cursor:
            plan, skipped = build_plan(cursor, args.start)
            apply_plan(cursor, plan, batch_no)
        print_preview(plan, skipped, args.show)
        print(f"applied_batch={batch_no}")
    else:
        with client.cursor() as cursor:
            plan, skipped = build_plan(cursor, args.start)
        print_preview(plan, skipped, args.show)
        print("dry_run=1")


if __name__ == "__main__":
    main()
