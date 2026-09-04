"""Sales-order business service.

The first service-layer step keeps the existing NativeDBClient transaction
logic intact, while making API and agent flows call one business boundary.
"""

from __future__ import annotations

from typing import Any

from src.engine.exceptions import DBError

from .base import BusinessService


AUTO_HISTORY_CATEGORIES = {
    "半斤礼盒",
    "三两礼盒",
    "二两礼盒",
    "一两礼盒",
    "五格礼盒",
    "3小盒礼盒",
    "6小盒礼盒",
}
SUGGEST_HISTORY_CATEGORIES = {"2泡小盒", "pvc礼盒", "PVC礼盒", "快递纸箱", "未分类"}
OFF_HISTORY_PRODUCT_TYPES = {"bag", "service", "accessory"}
OFF_HISTORY_CATEGORIES = {"其他产品", "其他", "标签", "烫金", "内衬"}


def _number(value: Any, fallback: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _setting_value(result: Any) -> dict:
    if not isinstance(result, dict):
        return {}
    data = result.get("data")
    if isinstance(data, dict) and isinstance(data.get("value"), dict):
        return data["value"]
    return result.get("value") if isinstance(result.get("value"), dict) else {}


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
    def _price_rules(self) -> dict:
        defaults = {
            "enabled": 1,
            "valid_days": 180,
            "min_retail_ratio": 0.5,
            "max_retail_ratio": 2.0,
            "default_policy": "suggest",
            "category_policies": {},
            "product_overrides": {},
        }
        try:
            configured = _setting_value(self.db.system_setting("price_rules"))
        except Exception:
            configured = {}
        defaults.update(configured)
        return defaults

    def _history_policy(self, sku: dict, rules: dict) -> str:
        if int(rules.get("enabled") or 0) != 1:
            return "off"
        overrides = rules.get("product_overrides") if isinstance(rules.get("product_overrides"), dict) else {}
        override = str(overrides.get(str(sku.get("spu_id") or "")) or "").strip().lower()
        if override in {"auto", "suggest", "off"}:
            return override
        policies = rules.get("category_policies") if isinstance(rules.get("category_policies"), dict) else {}
        configured = str(
            policies.get(str(sku.get("category_id") or ""))
            or policies.get(str(sku.get("category_name") or ""))
            or ""
        ).strip().lower()
        if configured in {"auto", "suggest", "off"}:
            return configured
        category_name = str(sku.get("category_name") or "未分类").strip()
        product_type = str(sku.get("product_type") or "").strip().lower()
        if (
            product_type in OFF_HISTORY_PRODUCT_TYPES
            or category_name in OFF_HISTORY_CATEGORIES
            or "泡袋" in category_name
            or "茶袋" in category_name
        ):
            return "off"
        if category_name in AUTO_HISTORY_CATEGORIES:
            return "auto"
        if category_name in SUGGEST_HISTORY_CATEGORIES:
            return "suggest"
        return str(rules.get("default_policy") or "suggest")

    def price_preview(
        self,
        *,
        customer_id: int,
        product_id: int,
        quantity: Any = 1,
        unit_id: int | None = None,
    ) -> dict:
        context = self.db.sales_price_context(customer_id, product_id, limit=10)
        sku = context.get("sku") if isinstance(context, dict) else {}
        sku = sku if isinstance(sku, dict) else {}
        rules = self._price_rules()
        policy = self._history_policy(sku, rules)
        effective_policy = policy
        retail_price = _number(sku.get("retail_price") or sku.get("min_price") or sku.get("max_price"))
        selected_unit_id = int(unit_id or sku.get("unit_id") or 0)
        warnings: list[str] = []
        candidate = None

        if policy != "off":
            for row in context.get("history") or []:
                if not isinstance(row, dict):
                    continue
                if _number(row.get("unit_price")) <= 0:
                    continue
                if int(row.get("remember_price") if row.get("remember_price") is not None else 1) != 1:
                    continue
                row_unit_id = int(row.get("unit_id") or 0)
                if selected_unit_id and row_unit_id and row_unit_id != selected_unit_id:
                    continue
                candidate = row
                break

        history_data = None
        if candidate:
            history_price = _number(candidate.get("unit_price"))
            history_data = {
                **candidate,
                "price": history_price,
                "quantity": _number(candidate.get("quantity")),
            }
            age_days = int(_number(candidate.get("age_days"), 0))
            valid_days = max(1, int(_number(rules.get("valid_days"), 180)))
            if age_days > valid_days:
                warnings.append(f"历史价已超过{valid_days}天")
            if retail_price > 0:
                ratio = history_price / retail_price
                min_ratio = max(0.01, _number(rules.get("min_retail_ratio"), 0.5))
                max_ratio = max(min_ratio, _number(rules.get("max_retail_ratio"), 2.0))
                if ratio < min_ratio or ratio > max_ratio:
                    warnings.append("历史价与当前零售价差异较大")
            if policy == "auto" and warnings:
                effective_policy = "suggest"

        price = retail_price
        source = "retail_price" if retail_price > 0 else "missing"
        reference_item_id = None
        if candidate and effective_policy == "auto":
            price = _number(candidate.get("unit_price"))
            source = "customer_history"
            reference_item_id = int(candidate.get("item_id") or 0) or None

        return {
            "customer_id": int(customer_id),
            "product_id": int(product_id),
            "quantity": _number(quantity, 1),
            "unit_id": selected_unit_id or None,
            "price": price if price > 0 else None,
            "source": source,
            "policy": policy,
            "effective_policy": effective_policy,
            "retail_price": retail_price if retail_price > 0 else None,
            "history": history_data,
            "warnings": warnings,
            "remember_default": policy != "off",
            "price_reference_item_id": reference_item_id,
            "memory_id": (int(candidate.get("memory_id") or 0) or None) if candidate else None,
            "price_scope": "spu",
            "source_sales_status": candidate.get("source_sales_status") if candidate else None,
            "source_sales_deleted_at": candidate.get("source_sales_deleted_at") if candidate else None,
            "sku": sku,
        }

    def normalize_products(self, products: list[dict], *, customer_id: int = 0) -> list[dict]:
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
            preview = {}
            if customer_id:
                try:
                    preview = self.price_preview(
                        customer_id=int(customer_id),
                        product_id=pid,
                        quantity=next_item.get("buy_number") or next_item.get("quantity") or 1,
                        unit_id=int(next_item.get("unit_id") or 0) or None,
                    )
                except Exception:
                    preview = {}
            sku_context = preview.get("sku") if isinstance(preview.get("sku"), dict) else detail
            policy = str(preview.get("policy") or self._history_policy(sku_context, self._price_rules())).strip().lower()
            if policy not in {"auto", "suggest", "off"}:
                policy = "suggest"
            next_item["price_policy"] = policy
            next_item["remember_price"] = 0 if policy == "off" else 1
            spu_id = int(sku_context.get("spu_id") or detail.get("spu_id") or 0)
            if spu_id:
                next_item["spu_id"] = spu_id

            explicit_price = next_item.get("price") not in (None, "")
            if explicit_price:
                next_item["price"] = _number(next_item.get("price"))
                current_source = str(next_item.get("price_source") or "").strip()
                if current_source != "manual_override" and preview:
                    preview_price = _number(preview.get("price"), -1)
                    if preview_price > 0 and abs(preview_price - next_item["price"]) < 0.005:
                        next_item["price_source"] = preview.get("source") or "retail_price"
                        next_item["price_reference_item_id"] = preview.get("price_reference_item_id")
                    else:
                        next_item["price_source"] = "manual_override"
                elif not current_source:
                    next_item["price_source"] = "manual_override"
                if next_item["price_source"] != "customer_history":
                    next_item["price_reference_item_id"] = None
            else:
                if preview.get("price") not in (None, ""):
                    next_item["price"] = preview["price"]
                    next_item["price_source"] = preview.get("source") or "retail_price"
                    next_item["price_reference_item_id"] = preview.get("price_reference_item_id")
            normalized.append(next_item)

        shared_prices: dict[tuple[int, int], float] = {}
        for item in normalized:
            if str(item.get("price_policy") or "") == "off":
                continue
            spu_id = int(item.get("spu_id") or 0)
            unit_id = int(item.get("unit_id") or 0)
            if not spu_id or not unit_id or item.get("price") in (None, ""):
                continue
            price = _number(item.get("price"))
            key = (spu_id, unit_id)
            if key in shared_prices and abs(shared_prices[key] - price) >= 0.005:
                raise DBError("同一款商品不同颜色的销售价格必须一致")
            shared_prices[key] = price
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
        allow_negative_stock: Any | None = None,
    ) -> dict:
        normalized_products = self.normalize_products(products, customer_id=customer_id)
        result = self.db.create_sales_order(
            customer_id=customer_id,
            warehouse_id=warehouse_id,
            products=normalized_products,
            create_time=create_time,
            pay_status=pay_status,
            pay_type=pay_type,
            operator_user_id=operator_user_id,
            allow_negative_stock=allow_negative_stock,
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

    def update_payment(
        self,
        sales_id: int,
        *,
        pay_status: str,
        pay_type: str = "",
        note: str = "",
        operator_user_id: Any = None,
    ) -> dict:
        return self.db.update_sales_order_payment(
            sales_id,
            pay_status=pay_status,
            pay_type=pay_type,
            note=note,
            operator_user_id=operator_user_id,
        )

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
