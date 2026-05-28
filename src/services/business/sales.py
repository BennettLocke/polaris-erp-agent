"""Sales-order business service.

The first service-layer step keeps the existing NativeDBClient transaction
logic intact, while making API and agent flows call one business boundary.
"""

from __future__ import annotations

from typing import Any

from .base import BusinessService


def _extract_sales_id(result: dict) -> int:
    if not isinstance(result, dict):
        return 0
    data = result.get("data")
    if isinstance(data, dict):
        raw_id = data.get("sales_id") or data.get("id")
    else:
        raw_id = data
    try:
        return int(raw_id or 0)
    except (TypeError, ValueError):
        return 0


class SalesService(BusinessService):
    def normalize_products(self, products: list[dict]) -> list[dict]:
        normalized: list[dict] = []
        detail_cache: dict[int, dict] = {}
        for item in products or []:
            if not isinstance(item, dict):
                continue
            product_id = item.get("product_id") or item.get("id")
            if not product_id:
                normalized.append(item)
                continue
            try:
                pid = int(product_id)
            except (TypeError, ValueError):
                normalized.append(item)
                continue
            detail = detail_cache.get(pid)
            if detail is None:
                raw_detail = self.db.product_info(pid) or {}
                detail = raw_detail if isinstance(raw_detail, dict) else {}
                detail_cache[pid] = detail
            next_item = dict(item)
            if not next_item.get("unit_id"):
                next_item["unit_id"] = int(detail.get("unit_id") or 1)
            normalized.append(next_item)
        return normalized

    def create_order(
        self,
        *,
        customer_id: int,
        warehouse_id: int,
        products: list[dict],
        create_time: str = "",
        pay_status: str | None = None,
        pay_type: str | None = None,
        operator_user_id: Any = None,
        workflow_order_id: int | None = None,
    ) -> dict:
        normalized_products = self.normalize_products(products)
        result = self.db.create_sales_order(
            customer_id=customer_id,
            warehouse_id=warehouse_id,
            products=normalized_products,
            create_time=create_time,
            pay_status=pay_status,
            pay_type=pay_type,
            operator_user_id=operator_user_id,
        )
        if not workflow_order_id or not isinstance(result, dict) or result.get("code") not in (None, 0):
            return result

        sales_id = _extract_sales_id(result)
        if not sales_id:
            return result

        link_result = self.db.link_workflow_sales_order(
            workflow_order_id=int(workflow_order_id),
            sales_order_id=sales_id,
            operator_user_id=operator_user_id,
        )
        data = result.setdefault("data", {})
        if isinstance(data, dict):
            if isinstance(link_result, dict) and link_result.get("code") in (None, 0):
                data["workflow_link"] = link_result.get("data") or {}
            else:
                data["workflow_link_error"] = (link_result or {}).get("msg") if isinstance(link_result, dict) else str(link_result)
        return result

    def delete_order(self, sales_id: int, *, operator_user_id: Any = None) -> dict:
        return self.db.delete_sales_order(sales_id, operator_user_id=operator_user_id)

    def detail(self, sales_id: int) -> dict:
        return self.db.sales_detail(sales_id)

    def cards(
        self,
        *,
        keyword: str = "",
        page: int = 1,
        page_size: int = 20,
        status: int | None = None,
        status_filter: str = "active",
        pay_status: str = "",
        date_from: str = "",
        date_to: str = "",
        customer_id: int | None = None,
    ) -> tuple[list[dict], int]:
        return self.db.sales_cards(
            keyword=keyword,
            page=page,
            page_size=page_size,
            status=status,
            status_filter=status_filter,
            pay_status=pay_status,
            date_from=date_from,
            date_to=date_to,
            customer_id=customer_id,
        )

    def history_price(self, customer_id: int, product_id: int) -> float | None:
        return self.db.sales_history_price(customer_id, product_id)

    def print_data(self, sales_id: int) -> dict:
        return self.db.sales_print_data(sales_id)

    def sales_print_html(
        self,
        sales_id: int,
        *,
        template_id: int | None = None,
        auto_print: bool = True,
        show_actions: bool = True,
    ) -> str:
        return self.db.sales_print_html(
            sales_id,
            template_id=template_id,
            auto_print=auto_print,
            show_actions=show_actions,
        )

    def create_print_task(
        self,
        sales_id: int,
        *,
        template_id: int | None = None,
        operator_user_id: Any = None,
    ) -> dict:
        return self.db.create_sales_print_task(
            sales_id=sales_id,
            template_id=template_id,
            operator_user_id=operator_user_id,
        )

    def print_task_list(self, *, page: int = 1, page_size: int = 50) -> dict:
        return self.db.sales_print_task_list(page=page, page_size=page_size)

    def print_task_row(self, task_id: int) -> dict | None:
        rows = self.db.query(
            """
            SELECT j.*, s.sales_no, s.customer_name_snapshot
            FROM print_job j
            LEFT JOIN sales_order s ON s.id=j.document_id
            WHERE j.id=%s AND j.document_type='sales_order'
            LIMIT 1
            """,
            (int(task_id),),
        )
        return rows[0] if rows else None

    def print_task_done(self, task_id: int) -> dict:
        return self.db.sales_print_task_done(task_id)

    def print_task_failed(self, task_id: int, *, sales_id: int, reason: str = "print failed") -> dict:
        clean_reason = str(reason or "print failed")[:200]
        self.db.execute(
            "UPDATE print_job SET status='failed', updated_at=NOW() WHERE id=%s",
            (int(task_id),),
        )
        self.db.execute(
            "UPDATE sales_order SET print_status='failed', updated_at=NOW() WHERE id=%s",
            (int(sales_id or 0),),
        )
        return {"code": 0, "data": {"id": int(task_id), "status": "failed", "reason": clean_reason}}


def get_sales_service() -> SalesService:
    return SalesService()
