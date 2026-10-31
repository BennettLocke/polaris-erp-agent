"""Explicit additive migration for existing product model tables (MySQL 5.7+)."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.deploy_database_schema import ROOT, connect, core_db_config
from dotenv import load_dotenv


def migrate(cursor) -> bool:
    cursor.execute("""
        SELECT DATA_TYPE, IS_NULLABLE
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='product_model_binding'
          AND COLUMN_NAME='model_config'
    """)
    column = cursor.fetchone()
    if column:
        # MariaDB represents JSON as LONGTEXT with a JSON_VALID check.
        if column["DATA_TYPE"].lower() not in ("json", "longtext") or column["IS_NULLABLE"] != "YES":
            raise ValueError("Existing model_config column is incompatible; no data was rewritten")
        return False
    cursor.execute("ALTER TABLE product_model_binding ADD COLUMN model_config JSON NULL")
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("host", "port", "database", "user", "password"):
        parser.add_argument("--" + name)
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    cfg = core_db_config(args)
    connection = connect(cfg, cfg["database"])
    try:
        with connection.cursor() as cursor:
            changed = migrate(cursor)
        connection.commit()
        print("model_config column added" if changed else "model_config column already present; unchanged")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
