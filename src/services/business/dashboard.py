"""Dashboard and recent-activity read service."""

from __future__ import annotations

from .base import BusinessService


class DashboardService(BusinessService):
    def summary(self) -> dict:
        return self.db.dashboard_summary()

    def pending_delivery_count(self) -> int:
        rows = self.db.query(
            """
            SELECT COUNT(*) AS count
            FROM workflow_order
            WHERE deleted_at IS NULL AND COALESCE(is_delivered, 0) <> 1
            """
        )
        row = rows[0] if rows else {}
        return int(row.get("count") or 0)

    def recent_orders(self, *, limit: int = 6) -> dict:
        clean_limit = max(1, min(int(limit or 6), 20))
        sales, _sales_total = self.db.sales_cards(keyword="", page=1, page_size=clean_limit, status=None)
        workflows, _workflow_total = self.db.workflow_orders(
            keyword="",
            page=1,
            page_size=clean_limit,
            status_filter="active",
        )
        return {
            "sales": sales[:clean_limit] if isinstance(sales, list) else [],
            "workflows": workflows[:clean_limit] if isinstance(workflows, list) else [],
        }


def get_dashboard_service() -> DashboardService:
    return DashboardService()
