"""Explicit MySQL 5.7-compatible additive migration, never runtime DDL."""
import unittest
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock


class ModelConfigMigrationTest(unittest.TestCase):
    def test_direct_script_invocation_supports_help_without_database_access(self):
        result = subprocess.run([sys.executable, "scripts/migrate_product_model_config.py", "--help"],
            cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--database", result.stdout)

    def test_adds_only_missing_nullable_json_column_and_rerun_does_not_write(self):
        from scripts.migrate_product_model_config import migrate
        cursor = Mock()
        cursor.fetchone.side_effect = [None, {"DATA_TYPE": "json", "IS_NULLABLE": "YES"}]
        self.assertTrue(migrate(cursor))
        self.assertFalse(migrate(cursor))
        statements = [call.args[0] for call in cursor.execute.call_args_list]
        self.assertEqual(sum("ALTER TABLE" in sql for sql in statements), 1)
        self.assertIn("INFORMATION_SCHEMA.COLUMNS", statements[0])
        self.assertIn("model_config JSON NULL", statements[1])
        self.assertFalse(any("UPDATE " in sql or "DROP " in sql for sql in statements))

    def test_incompatible_existing_column_stops_without_rewrite(self):
        from scripts.migrate_product_model_config import migrate
        cursor = Mock()
        cursor.fetchone.return_value = {"DATA_TYPE": "varchar", "IS_NULLABLE": "NO"}
        with self.assertRaises(ValueError):
            migrate(cursor)
        self.assertEqual(cursor.execute.call_count, 1)
