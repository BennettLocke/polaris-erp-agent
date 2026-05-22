"""Migrate legacy WebUI login rows into auth_user.

This is a one-time bridge for local/server environments that still have
sjagent_web_users. Runtime WebUI login now reads auth_user directly.
"""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

from src.engine.native_db import get_native_db_client  # noqa: E402


def phone_digits(value: str) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def table_exists(client, table: str) -> bool:
    rows = client.query("SHOW TABLES LIKE %s", (table,))
    return bool(rows)


def find_party_id(client, phone: str) -> int | None:
    digits = phone_digits(phone)
    if not digits:
        return None
    rows = client.query(
        """
        SELECT id
        FROM party
        WHERE phone_normalized=%s OR phone=%s
        ORDER BY id ASC
        LIMIT 1
        """,
        (digits, phone),
    )
    return int(rows[0]["id"]) if rows else None


def main() -> None:
    client = get_native_db_client()
    if not table_exists(client, "sjagent_web_users"):
        print({"migrated": 0, "reason": "legacy table not found"})
        return
    rows = client.query(
        """
        SELECT id, username, password_hash, display_name, approval_status,
               is_admin, is_active, created_at, updated_at, last_login_at
        FROM sjagent_web_users
        ORDER BY id ASC
        """
    )
    migrated = 0
    for row in rows:
        username = str(row.get("username") or "").strip()
        if not username:
            continue
        is_admin = 1 if int(row.get("is_admin") or 0) == 1 else 0
        role = "admin" if is_admin else "staff"
        phone = phone_digits(username) or None
        linked_party_id = find_party_id(client, phone or "") if phone else None
        client.execute(
            """
            INSERT INTO auth_user
                (username, password_hash, display_name, phone, role, linked_party_id,
                 approval_status, is_active, is_admin, last_login_at, created_at, updated_at)
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s,
                FROM_UNIXTIME(NULLIF(%s,0)),
                COALESCE(FROM_UNIXTIME(NULLIF(%s,0)), NOW()),
                COALESCE(FROM_UNIXTIME(NULLIF(%s,0)), NOW())
            )
            ON DUPLICATE KEY UPDATE
                password_hash=COALESCE(NULLIF(VALUES(password_hash), ''), password_hash),
                display_name=VALUES(display_name),
                phone=COALESCE(VALUES(phone), phone),
                role=VALUES(role),
                linked_party_id=COALESCE(VALUES(linked_party_id), linked_party_id),
                approval_status=VALUES(approval_status),
                is_active=VALUES(is_active),
                is_admin=VALUES(is_admin),
                last_login_at=COALESCE(VALUES(last_login_at), last_login_at),
                updated_at=NOW()
            """,
            (
                username,
                row.get("password_hash") or None,
                (row.get("display_name") or username)[:80],
                phone,
                role,
                linked_party_id,
                row.get("approval_status") or "approved",
                1 if int(row.get("is_active") or 0) == 1 else 0,
                is_admin,
                int(row.get("last_login_at") or 0),
                int(row.get("created_at") or 0),
                int(row.get("updated_at") or 0),
            ),
        )
        migrated += 1
    print({"migrated": migrated})


if __name__ == "__main__":
    main()
