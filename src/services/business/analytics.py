"""Sales analytics read service."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

from .base import BusinessService


_PERIOD_DAYS = {
    "today": 0,
    "7d": 7,
    "30d": 30,
    "90d": 90,
}
_PERIODS = {*_PERIOD_DAYS, "week", "month"}
_DIMENSIONS = {"product", "sku"}


def _clean_limit(value: Any, default: int = 20) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(1, min(number, 100))


def _money_text(value: Any) -> str:
    try:
        return f"{Decimal(str(value or 0)):.2f}"
    except (InvalidOperation, ValueError):
        return "0.00"


def _qty_number(value: Any) -> int | float:
    try:
        number = Decimal(str(value or 0))
    except (InvalidOperation, ValueError):
        return 0
    if number == number.to_integral_value():
        return int(number)
    return float(number)


def _clean_text_list(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        raw_values = re.split(r"[,，、/\s]+", value)
    elif isinstance(value, (list, tuple, set)):
        raw_values = value
    else:
        raw_values = [value]

    items: list[str] = []
    for raw in raw_values:
        text = str(raw or "").strip()
        if text and text not in items:
            items.append(text)
    return items


class AnalyticsService(BusinessService):
    """Read-only analytics backed by current sales order data."""

    def hot_products(
        self,
        *,
        period: str = "30d",
        limit: int = 20,
        dimension: str = "product",
        category_names: Any = None,
    ) -> dict:
        clean_period = str(period or "30d").strip().lower()
        if clean_period not in _PERIODS:
            clean_period = "30d"

        clean_dimension = str(dimension or "product").strip().lower()
        if clean_dimension not in _DIMENSIONS:
            clean_dimension = "product"

        clean_limit = _clean_limit(limit)
        period_sql, params = self._period_clause(clean_period)
        clean_category_names = _clean_text_list(category_names)
        category_filter_sql, category_params = self._category_filter_clause(clean_category_names)
        params.extend(category_params)
        params.append(clean_limit)

        sql = self._hot_products_sql(clean_dimension, period_sql, category_filter_sql)
        rows = self.db.query(sql, tuple(params))
        items = [self._hot_product_item(index + 1, row) for index, row in enumerate(rows or [])]
        return {
            "period": clean_period,
            "dimension": clean_dimension,
            "limit": clean_limit,
            "category_names": clean_category_names,
            "items": items,
            "source": "sales_order",
        }

    def _period_clause(self, period: str) -> tuple[str, list[Any]]:
        if period == "month":
            return "s.sales_at >= DATE_FORMAT(CURDATE(), '%Y-%m-01')", []
        if period == "week":
            return "s.sales_at >= DATE_SUB(CURDATE(), INTERVAL WEEKDAY(CURDATE()) DAY)", []
        if period == "today":
            return "s.sales_at >= CURDATE()", []
        return "s.sales_at >= DATE_SUB(CURDATE(), INTERVAL %s DAY)", [_PERIOD_DAYS[period]]

    def _category_filter_clause(self, category_names: list[str]) -> tuple[str, list[Any]]:
        if not category_names:
            return "", []
        placeholders = ", ".join(["%s"] * len(category_names))
        return f"""
              AND EXISTS (
                  SELECT 1
                  FROM product_category pc
                  WHERE pc.is_enabled = 1
                    AND pc.name IN ({placeholders})
                    AND (
                        sku.primary_category_id = pc.id
                        OR sp.default_category_id = pc.id
                        OR JSON_CONTAINS(sku.category_ids, CAST(pc.id AS CHAR))
                    )
              )
        """, list(category_names)

    def _hot_products_sql(self, dimension: str, period_sql: str, category_filter_sql: str = "") -> str:
        if dimension == "sku":
            select_sql = """
                COALESCE(sku.spu_id, i.sku_id) AS product_id,
                i.sku_id AS sku_id,
                COALESCE(NULLIF(i.sku_no_snapshot, ''), sku.sku_no, '') AS sku_no,
                COALESCE(NULLIF(i.title_snapshot, ''), sp.title, '商品') AS title,
                COALESCE(NULLIF(i.color_snapshot, ''), sku.color, '默认颜色') AS color,
                MAX(NULLIF(sku.main_image_url, '')) AS image
            """
            group_sql = """
                COALESCE(sku.spu_id, i.sku_id),
                i.sku_id,
                COALESCE(NULLIF(i.sku_no_snapshot, ''), sku.sku_no, ''),
                COALESCE(NULLIF(i.title_snapshot, ''), sp.title, '商品'),
                COALESCE(NULLIF(i.color_snapshot, ''), sku.color, '默认颜色')
            """
        else:
            select_sql = """
                COALESCE(sku.spu_id, i.sku_id) AS product_id,
                MIN(i.sku_id) AS sku_id,
                MIN(COALESCE(NULLIF(i.sku_no_snapshot, ''), sku.sku_no, '')) AS sku_no,
                COALESCE(NULLIF(i.title_snapshot, ''), sp.title, '商品') AS title,
                GROUP_CONCAT(DISTINCT COALESCE(NULLIF(i.color_snapshot, ''), sku.color) ORDER BY COALESCE(NULLIF(i.color_snapshot, ''), sku.color) SEPARATOR ' / ') AS color,
                MAX(NULLIF(sku.main_image_url, '')) AS image
            """
            group_sql = """
                COALESCE(sku.spu_id, i.sku_id),
                COALESCE(NULLIF(i.title_snapshot, ''), sp.title, '商品')
            """

        return f"""
            SELECT
                {select_sql},
                SUM(i.quantity) AS sold_qty,
                SUM(i.amount) AS amount,
                COUNT(DISTINCT s.id) AS order_count,
                COUNT(DISTINCT s.customer_id) AS customer_count,
                MAX(s.sales_at) AS last_sold_at
            FROM sales_order_item i
            JOIN sales_order s ON s.id = i.sales_order_id
            LEFT JOIN product_sku sku ON sku.id = i.sku_id
            LEFT JOIN product_spu sp ON sp.id = sku.spu_id
            WHERE s.deleted_at IS NULL
              AND s.status NOT IN ('canceled', 'deleted')
              AND sku.deleted_at IS NULL
              AND sp.deleted_at IS NULL
              AND sku.status = 'active'
              AND sku.is_listed = 1
              AND {period_sql}
              AND s.sales_at < DATE_ADD(CURDATE(), INTERVAL 1 DAY)
              {category_filter_sql}
            GROUP BY {group_sql}
            ORDER BY sold_qty DESC, amount DESC, last_sold_at DESC
            LIMIT %s
        """

    def _hot_product_item(self, rank: int, row: dict) -> dict:
        image = str(row.get("image") or "").strip()
        return {
            "rank": rank,
            "product_id": int(row.get("product_id") or 0),
            "sku_id": int(row.get("sku_id") or 0),
            "sku_no": str(row.get("sku_no") or ""),
            "title": str(row.get("title") or "商品"),
            "color": str(row.get("color") or ""),
            "image": image,
            "image_url": image,
            "sold_qty": _qty_number(row.get("sold_qty")),
            "amount": _money_text(row.get("amount")),
            "amount_value": float(_money_text(row.get("amount"))),
            "order_count": int(row.get("order_count") or 0),
            "customer_count": int(row.get("customer_count") or 0),
            "last_sold_at": str(row.get("last_sold_at") or ""),
        }


def get_analytics_service() -> AnalyticsService:
    return AnalyticsService()
