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
_SALES_OVERVIEW_DEFAULT_PERIOD = "7d"
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

    def sales_overview(self, *, period: str = _SALES_OVERVIEW_DEFAULT_PERIOD, recent_limit: int = 8) -> dict:
        clean_period = str(period or _SALES_OVERVIEW_DEFAULT_PERIOD).strip().lower()
        if clean_period not in _PERIODS:
            clean_period = _SALES_OVERVIEW_DEFAULT_PERIOD

        period_sql, params = self._period_clause(clean_period)
        kpi_rows = self.db.query(self._sales_overview_kpi_sql(period_sql), tuple(params))
        trend_rows = self.db.query(self._sales_overview_trend_sql(period_sql), tuple(params))
        recent_rows = self.db.query(
            self._sales_overview_recent_sql(period_sql),
            tuple(params + [_clean_limit(recent_limit, default=8)]),
        )

        kpi = self._sales_overview_kpi(kpi_rows[0] if kpi_rows else {})
        return {
            "period": clean_period,
            "kpi": kpi,
            "trend": [self._sales_overview_trend_item(row) for row in (trend_rows or [])],
            "recent_sales": [self._sales_overview_recent_item(row) for row in (recent_rows or [])],
            "source": "sales_order",
        }

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
            return "s.sales_at >= DATE_ADD(LAST_DAY(DATE_SUB(CURDATE(), INTERVAL 1 MONTH)), INTERVAL 1 DAY)", []
        if period == "week":
            return "s.sales_at >= DATE_SUB(CURDATE(), INTERVAL WEEKDAY(CURDATE()) DAY)", []
        if period == "today":
            return "s.sales_at >= CURDATE()", []
        return "s.sales_at >= DATE_SUB(CURDATE(), INTERVAL %s DAY)", [_PERIOD_DAYS[period]]

    def _sales_overview_base_where(self, period_sql: str) -> str:
        return f"""
            s.deleted_at IS NULL
            AND s.status NOT IN ('canceled', 'deleted')
            AND {period_sql}
            AND s.sales_at < DATE_ADD(CURDATE(), INTERVAL 1 DAY)
        """

    def _sales_overview_kpi_sql(self, period_sql: str) -> str:
        return f"""
            /* analytics_sales_overview_kpi */
            SELECT
                SUM(COALESCE(s.receivable_amount, s.goods_amount, 0)) AS sales_amount,
                COUNT(DISTINCT s.id) AS order_count,
                SUM(COALESCE(items.item_quantity, 0)) AS item_quantity,
                COUNT(DISTINCT s.customer_id) AS customer_count,
                CASE
                    WHEN COUNT(DISTINCT s.id) > 0
                    THEN SUM(COALESCE(s.receivable_amount, s.goods_amount, 0)) / COUNT(DISTINCT s.id)
                    ELSE 0
                END AS average_order_amount
            FROM sales_order s
            LEFT JOIN (
                SELECT sales_order_id, SUM(quantity) AS item_quantity
                FROM sales_order_item
                GROUP BY sales_order_id
            ) items ON items.sales_order_id = s.id
            WHERE {self._sales_overview_base_where(period_sql)}
        """

    def _sales_overview_trend_sql(self, period_sql: str) -> str:
        return f"""
            /* analytics_sales_overview_trend */
            SELECT
                DATE(s.sales_at) AS date,
                SUM(COALESCE(s.receivable_amount, s.goods_amount, 0)) AS sales_amount,
                COUNT(DISTINCT s.id) AS order_count
            FROM sales_order s
            WHERE {self._sales_overview_base_where(period_sql)}
            GROUP BY DATE(s.sales_at)
            ORDER BY DATE(s.sales_at) ASC
        """

    def _sales_overview_recent_sql(self, period_sql: str) -> str:
        return f"""
            /* analytics_sales_overview_recent */
            SELECT
                s.id,
                s.sales_no,
                COALESCE(NULLIF(s.customer_name_snapshot, ''), '客户') AS customer_name,
                COALESCE(GROUP_CONCAT(i.title_snapshot ORDER BY i.line_no SEPARATOR ' / '), '销售单') AS product_summary,
                COALESCE(s.receivable_amount, s.goods_amount, 0) AS receivable_amount,
                s.pay_status,
                s.pay_type,
                s.sales_at
            FROM sales_order s
            LEFT JOIN sales_order_item i ON i.sales_order_id = s.id
            WHERE {self._sales_overview_base_where(period_sql)}
            GROUP BY s.id, s.sales_no, s.customer_name_snapshot,
                     s.receivable_amount, s.goods_amount, s.pay_status, s.pay_type, s.sales_at
            ORDER BY s.sales_at DESC, s.id DESC
            LIMIT %s
        """

    def _category_filter_clause(self, category_names: list[str]) -> tuple[str, list[Any]]:
        if not category_names:
            return "", []
        placeholders = ", ".join(["%s"] * len(category_names))
        like_sql = " OR ".join(["pc.name LIKE %s"] * len(category_names))
        return f"""
              AND EXISTS (
                  SELECT 1
                  FROM product_category pc
                  WHERE pc.is_enabled = 1
                    AND (pc.name IN ({placeholders}) OR {like_sql})
                    AND (
                        sku.primary_category_id = pc.id
                        OR sp.default_category_id = pc.id
                        OR JSON_CONTAINS(sku.category_ids, CAST(pc.id AS CHAR))
                    )
              )
        """, list(category_names) + [f"%{name}%" for name in category_names]

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

    def _sales_overview_kpi(self, row: dict) -> dict:
        return {
            "sales_amount": _money_text(row.get("sales_amount")),
            "sales_amount_value": float(_money_text(row.get("sales_amount"))),
            "order_count": int(row.get("order_count") or 0),
            "item_quantity": _qty_number(row.get("item_quantity")),
            "customer_count": int(row.get("customer_count") or 0),
            "average_order_amount": _money_text(row.get("average_order_amount")),
            "average_order_amount_value": float(_money_text(row.get("average_order_amount"))),
        }

    def _sales_overview_trend_item(self, row: dict) -> dict:
        return {
            "date": str(row.get("date") or ""),
            "sales_amount": _money_text(row.get("sales_amount")),
            "sales_amount_value": float(_money_text(row.get("sales_amount"))),
            "order_count": int(row.get("order_count") or 0),
        }

    def _sales_overview_recent_item(self, row: dict) -> dict:
        pay_status = str(row.get("pay_status") or "").strip()
        pay_type = str(row.get("pay_type") or "").strip()
        return {
            "id": int(row.get("id") or 0),
            "sales_no": str(row.get("sales_no") or ""),
            "customer_name": str(row.get("customer_name") or "客户"),
            "product_summary": str(row.get("product_summary") or "销售单"),
            "receivable_amount": _money_text(row.get("receivable_amount")),
            "receivable_amount_value": float(_money_text(row.get("receivable_amount"))),
            "pay_status": pay_status,
            "pay_status_text": str(row.get("pay_status_text") or self._pay_status_text(pay_status)),
            "pay_type": pay_type,
            "pay_type_text": str(row.get("pay_type_text") or self._pay_type_text(pay_type)),
            "sales_at": str(row.get("sales_at") or ""),
        }

    def _pay_status_text(self, status: str) -> str:
        return {
            "paid": "已付款",
            "monthly": "月结",
            "unpaid": "未付款",
        }.get(status, status or "未记录")

    def _pay_type_text(self, pay_type: str) -> str:
        return {
            "wechat": "微信",
            "cash": "现金",
            "balance": "余额",
            "transfer": "转账",
            "monthly": "月结",
        }.get(pay_type, pay_type or "")


def get_analytics_service() -> AnalyticsService:
    return AnalyticsService()
