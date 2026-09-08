from pathlib import Path
import unittest
from unittest.mock import Mock

from src.services.business.sales import SalesService


ROOT = Path(__file__).resolve().parents[1]


class SalesMergePreviewContractTest(unittest.TestCase):
    def test_sales_service_delegates_merge_candidates(self):
        db = Mock()
        db.sales_merge_candidates.return_value = {"code": 0, "data": {"orders": []}}

        result = SalesService(db).merge_candidates(12)

        self.assertEqual(result, {"code": 0, "data": {"orders": []}})
        db.sales_merge_candidates.assert_called_once_with(12)

    def test_merge_candidate_route_is_read_only(self):
        source = (ROOT / "src" / "channels" / "http_api" / "__init__.py").read_text(encoding="utf-8")

        self.assertIn(
            '@app.route("/api/sales/<int:sales_id>/merge-candidates", methods=["GET"])',
            source,
        )
        self.assertNotIn(
            '@app.route("/api/sales/<int:sales_id>/merge-candidates", methods=["POST"])',
            source,
        )

    def test_merge_candidate_route_requires_print_permission(self):
        source = (ROOT / "src" / "channels" / "http_api" / "__init__.py").read_text(encoding="utf-8")

        self.assertIn(
            '({"GET"}, re.compile(r"^/api/sales/\\d+/merge-candidates$"), "打印")',
            source,
        )


if __name__ == "__main__":
    unittest.main()
