"""Workflow-order business service."""

from __future__ import annotations

from .base import BusinessService


class WorkflowService(BusinessService):
    def save_order(
        self,
        *,
        customer_name: str,
        goods_name: str,
        order_quantity: int,
        order_id: int | None = None,
        customer_phone: str = "",
        color: str = "",
        order_images: list[str] | None = None,
        is_screen_print: int = 0,
        is_made: int | None = None,
        is_delivered: int | None = None,
        order_type: int = 0,
        remark: str = "",
    ) -> dict:
        return self.db.save_workflow_order(
            order_id=order_id,
            customer_name=customer_name,
            customer_phone=customer_phone,
            goods_name=goods_name,
            order_quantity=order_quantity,
            color=color,
            order_images=order_images or [],
            is_screen_print=is_screen_print,
            is_made=is_made,
            is_delivered=is_delivered,
            order_type=order_type,
            remark=remark,
        )

    def list_orders(
        self,
        *,
        keyword: str = "",
        page: int = 1,
        page_size: int = 20,
        status_filter: str = "all",
        customer_id: int | None = None,
    ) -> tuple[list[dict], int]:
        return self.db.workflow_orders(keyword=keyword, page=page, page_size=page_size, status_filter=status_filter, customer_id=customer_id)

    def detail(self, order_id: int) -> dict:
        rows = self.db.query(
            "SELECT * FROM workflow_order WHERE id=%s AND deleted_at IS NULL LIMIT 1",
            (order_id,),
        )
        if not rows:
            return {"code": 404, "msg": "工作流订单不存在"}
        return {"code": 0, "data": rows[0]}

    def delete_orders(self, ids: str) -> dict:
        return self.db.delete_workflow_orders(ids)

    def update_status(self, *, order_id: int, field: str, value: int) -> dict:
        return self.db.update_workflow_status(order_id=order_id, field=field, value=value)

    def link_sales_order(self, workflow_order_id: int, sales_order_id: int, *, operator_user_id=None) -> dict:
        return self.db.link_workflow_sales_order(
            workflow_order_id=workflow_order_id,
            sales_order_id=sales_order_id,
            operator_user_id=operator_user_id,
        )


def get_workflow_service() -> WorkflowService:
    return WorkflowService()
