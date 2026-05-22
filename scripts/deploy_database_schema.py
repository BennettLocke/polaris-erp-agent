"""Deploy sjagent database schema files.

The script is intentionally small and repeatable: it loads SQL files from
database/schema, runs CREATE TABLE/seed statements, and records a deploy log.
Secrets are read from environment variables or .env; no password belongs in
source code.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pymysql
from dotenv import load_dotenv
from pymysql.cursors import DictCursor


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA_DIR = ROOT / "database" / "schema"
DEFAULT_CORE_DB = "sjagent_core"


def quote_ident(name: str) -> str:
    if not re.fullmatch(r"[0-9A-Za-z_]+", name or ""):
        raise ValueError(f"Unsafe database identifier: {name!r}")
    return f"`{name}`"


def env_first(*names: str, default: str | None = None) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value not in (None, ""):
            return value
    return default


def core_db_config(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "host": args.host or env_first("SJAGENT_CORE_DB_HOST", "SJAGENT_CORE_HOST", "DB_HOST", default="127.0.0.1"),
        "port": int(args.port or env_first("SJAGENT_CORE_DB_PORT", "SJAGENT_CORE_PORT", "DB_PORT", default="3306")),
        "database": args.database or env_first("SJAGENT_CORE_DB_NAME", "SJAGENT_CORE_DB", default=DEFAULT_CORE_DB),
        "user": args.user or env_first("SJAGENT_CORE_DB_USER", "SJAGENT_CORE_USER", "DB_USER"),
        "password": args.password or env_first("SJAGENT_CORE_DB_PASSWORD", "SJAGENT_CORE_PASSWORD", "DB_PASSWORD"),
        "charset": env_first("SJAGENT_CORE_DB_CHARSET", default="utf8mb4"),
    }


def connect(cfg: dict[str, Any], database: str | None):
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


def ensure_database(cfg: dict[str, Any]) -> tuple[Any, list[dict[str, Any]]]:
    warnings: list[dict[str, Any]] = []
    db_name = cfg["database"]
    try:
        server_conn = connect(cfg, None)
        with server_conn.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS {quote_ident(db_name)} "
                "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        server_conn.commit()
        server_conn.close()
    except pymysql.OperationalError as exc:
        code = int(exc.args[0]) if exc.args else 0
        if code not in (1044, 1045, 1049):
            raise
        warnings.append(
            {
                "code": "create_database_skipped",
                "message": "Could not create database; connecting to the target database directly.",
                "mysql_error": code,
                "database": db_name,
            }
        )
    return connect(cfg, db_name), warnings


def strip_sql_comments(sql: str) -> str:
    lines: list[str] = []
    for line in sql.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        lines.append(line)
    return "\n".join(lines)


def split_sql(sql: str) -> list[str]:
    cleaned = strip_sql_comments(sql)
    statements: list[str] = []
    current: list[str] = []
    in_single = False
    in_double = False
    escape = False
    for char in cleaned:
        current.append(char)
        if escape:
            escape = False
            continue
        if char == "\\":
            escape = True
            continue
        if char == "'" and not in_double:
            in_single = not in_single
            continue
        if char == '"' and not in_single:
            in_double = not in_double
            continue
        if char == ";" and not in_single and not in_double:
            statement = "".join(current).strip().rstrip(";").strip()
            if statement:
                statements.append(statement)
            current = []
    tail = "".join(current).strip()
    if tail:
        statements.append(tail)
    return statements


def ensure_deploy_log(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_deploy_log (
            id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
            schema_file VARCHAR(255) NOT NULL,
            checksum CHAR(64) NOT NULL,
            statement_count INT NOT NULL,
            applied_at DATETIME NOT NULL,
            PRIMARY KEY (id),
            KEY idx_schema_deploy_log_file (schema_file),
            KEY idx_schema_deploy_log_applied_at (applied_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
    )


def schema_files(schema_dir: Path, only: list[str]) -> list[Path]:
    files = sorted(path for path in schema_dir.glob("*.sql") if path.is_file())
    if not only:
        return files
    selected = []
    for path in files:
        if any(token in path.name for token in only):
            selected.append(path)
    return selected


def table_names_from_files(files: list[Path]) -> list[str]:
    names: list[str] = []
    pattern = re.compile(r"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+`?([0-9A-Za-z_]+)`?", re.IGNORECASE)
    for path in files:
        for match in pattern.finditer(path.read_text(encoding="utf-8")):
            name = match.group(1)
            if name not in names:
                names.append(name)
    return names


def existing_table_counts(cursor, table_names: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table_name in table_names:
        cursor.execute(f"SELECT COUNT(*) AS cnt FROM {quote_ident(table_name)}")
        row = cursor.fetchone()
        counts[table_name] = int(row["cnt"] or 0)
    return counts


def deploy(args: argparse.Namespace) -> dict[str, Any]:
    load_dotenv(ROOT / ".env")
    cfg = core_db_config(args)
    schema_dir = Path(args.schema_dir or DEFAULT_SCHEMA_DIR)
    files = schema_files(schema_dir, args.only or [])
    if not files:
        raise FileNotFoundError(f"No schema files found in {schema_dir}")

    table_names = table_names_from_files(files)
    report: dict[str, Any] = {
        "database": cfg["database"],
        "schema_dir": str(schema_dir),
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "files": [],
        "warnings": [],
    }
    if args.dry_run:
        report["dry_run"] = True
        report["tables"] = table_names
        return report

    conn, warnings = ensure_database(cfg)
    report["warnings"].extend(warnings)
    try:
        with conn.cursor() as cursor:
            ensure_deploy_log(cursor)
            for path in files:
                sql_text = path.read_text(encoding="utf-8")
                statements = split_sql(sql_text)
                for statement in statements:
                    cursor.execute(statement)
                checksum = hashlib.sha256(sql_text.encode("utf-8")).hexdigest()
                cursor.execute(
                    """
                    INSERT INTO schema_deploy_log
                        (schema_file, checksum, statement_count, applied_at)
                    VALUES (%s,%s,%s,%s)
                    """,
                    (path.name, checksum, len(statements), datetime.now()),
                )
                report["files"].append(
                    {"file": path.name, "checksum": checksum, "statement_count": len(statements)}
                )
            report["table_counts"] = existing_table_counts(cursor, table_names)
        conn.commit()
    finally:
        conn.close()
    report["finished_at"] = datetime.now().isoformat(timespec="seconds")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deploy sjagent MySQL schema files.")
    parser.add_argument("--database", default=None, help="Target database name. Defaults to SJAGENT_CORE_DB_NAME or sjagent_core.")
    parser.add_argument("--host", default=None, help="Target DB host override.")
    parser.add_argument("--port", default=None, help="Target DB port override.")
    parser.add_argument("--user", default=None, help="Target DB user override.")
    parser.add_argument("--password", default=None, help="Target DB password override.")
    parser.add_argument("--schema-dir", default=None, help="Schema SQL directory. Defaults to database/schema.")
    parser.add_argument("--only", action="append", help="Only run schema files whose names contain this token. Repeatable.")
    parser.add_argument("--dry-run", action="store_true", help="List files/tables without connecting to MySQL.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = deploy(args)
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
