import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.engine.native_db import NativeDBClient


class CapturingNativeDB(NativeDBClient):
    def __new__(cls):
        return object.__new__(cls)

    def __init__(self):
        super().__init__()
        self.queries: list[tuple[str, list]] = []

    def query(self, sql: str, params=()):
        self.queries.append((sql, list(params)))
        if "COUNT" in sql:
            return [{"total": 0}]
        return []


class NativeWorkflowOrderQueryTests(unittest.TestCase):
    def test_workflow_orders_keyword_searches_card_id_and_workflow_no(self):
        db = CapturingNativeDB()

        db.workflow_orders(keyword="WF20260527173319001", page=1, page_size=20, status_filter="active")

        count_sql = db.queries[0][0]
        params = db.queries[0][1]
        self.assertIn("CAST(wo.id AS CHAR) LIKE %s", count_sql)
        self.assertIn("wo.workflow_no LIKE %s", count_sql)
        self.assertIn("%WF20260527173319001%", params)


if __name__ == "__main__":
    unittest.main()
