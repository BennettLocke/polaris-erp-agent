"""Mini-program read aggregation service.

The mini-program is a client of sjagent_core. It can read products,
workflow orders and sales summaries, but it must not own inventory or
payment side effects.
"""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import quote

from .base import BusinessService
from .customers import CustomerBalanceService
from .products import ProductService

DEFAULT_HERO_IMAGE = "https://img.513sjbz.com/static/upload/images/app_nav/2026/04/25/1777104334795209.jpg"
MINIAPP_EXCLUDED_CATEGORY_NAMES = ("纯色泡袋", "品种茶泡袋", "2泡礼盒")
HOME_CATEGORY_COPY = {
    "半斤礼盒": ("30", "泡包装礼盒"),
    "三两礼盒": ("18", "泡包装礼盒"),
    "二两礼盒": ("12", "泡包装礼盒"),
    "一两礼盒": ("06", "泡包装礼盒"),
    "6小盒礼盒": ("12", "泡包装礼盒"),
    "3小盒礼盒": ("06", "泡包装礼盒"),
    "2小盒礼盒": ("02", "泡包装礼盒"),
    "五格礼盒": ("20", "泡包装礼盒"),
    "PVC礼盒": ("", "半斤/三两/二两等"),
    "pvc礼盒": ("", "半斤/三两/二两等"),
    "快递纸箱": ("", "30斤/20斤/15斤等"),
}

DEFAULT_BOTTOM_TABS = [
    {
        "title": "首页",
        "icon_url": "https://img.513sjbz.com/static/upload/images/app_center_nav/2026/03/30/1774869699282797.png",
        "active_icon_url": "https://img.513sjbz.com/static/upload/images/app_center_nav/2026/03/30/1774869699200935.png",
        "link_type": "page",
        "link_value": "/pages/home/index",
    },
    {
        "title": "分类",
        "icon_url": "https://img.513sjbz.com/static/upload/images/app_center_nav/2026/03/30/1774869699309568.png",
        "active_icon_url": "https://img.513sjbz.com/static/upload/images/app_center_nav/2026/03/30/1774869698249700.png",
        "link_type": "page",
        "link_value": "/pages/category/index",
    },
    {
        "title": "订单列表",
        "icon_url": "https://img.513sjbz.com/static/upload/images/app_center_nav/2026/03/30/1774869699858406.png",
        "active_icon_url": "https://img.513sjbz.com/static/upload/images/app_center_nav/2026/03/30/1774869699328333.png",
        "link_type": "page",
        "link_value": "/pages/orderflow/index",
    },
    {
        "title": "我的",
        "icon_url": "https://img.513sjbz.com/static/upload/images/app_center_nav/2026/03/30/1774869699161830.png",
        "active_icon_url": "https://img.513sjbz.com/static/upload/images/app_center_nav/2026/03/30/1774869699255558.png",
        "link_type": "page",
        "link_value": "/pages/my/index",
    },
]

DEFAULT_HOME_CATEGORIES = [
    {"title": "半斤礼盒", "badge_text": "30", "subtitle": "泡包装礼盒", "link_type": "search", "link_value": "半斤礼盒"},
    {"title": "三两礼盒", "badge_text": "18", "subtitle": "泡包装礼盒", "link_type": "search", "link_value": "三两礼盒"},
    {"title": "二两礼盒", "badge_text": "12", "subtitle": "泡包装礼盒", "link_type": "search", "link_value": "二两礼盒"},
    {"title": "一两礼盒", "badge_text": "06", "subtitle": "泡包装礼盒", "link_type": "search", "link_value": "一两礼盒"},
    {"title": "6小盒礼盒", "badge_text": "12", "subtitle": "泡包装礼盒", "link_type": "search", "link_value": "6小盒礼盒"},
    {"title": "3小盒礼盒", "badge_text": "06", "subtitle": "泡包装礼盒", "link_type": "search", "link_value": "3小盒礼盒"},
    {"title": "2小盒礼盒", "badge_text": "02", "subtitle": "泡包装礼盒", "link_type": "search", "link_value": "2小盒礼盒"},
    {"title": "五格礼盒", "badge_text": "20", "subtitle": "泡包装礼盒", "link_type": "search", "link_value": "五格礼盒"},
    {"title": "PVC礼盒", "badge_text": "", "subtitle": "半斤/三两/二两等", "link_type": "search", "link_value": "PVC礼盒"},
    {"title": "快递纸箱", "badge_text": "", "subtitle": "30斤/20斤/15斤等", "link_type": "search", "link_value": "快递纸箱"},
]


class MiniAppService(BusinessService):
    def _extra_json(self, item: dict) -> dict:
        value = item.get("extra_json")
        if isinstance(value, dict):
            return value
        if value in (None, ""):
            return {}
        try:
            parsed = json.loads(str(value))
        except Exception:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _title(self, item: dict) -> str:
        return str(item.get("title") or item.get("name") or item.get("text") or "").strip()

    def _asset_url(self, item: dict) -> str:
        return str(item.get("image_url") or item.get("icon_url") or item.get("asset_url") or item.get("image") or item.get("icon") or "").strip()

    def _active_asset_url(self, item: dict) -> str:
        return str(
            item.get("active_icon_url")
            or item.get("active_asset_url")
            or item.get("selected_icon")
            or item.get("icon_active")
            or ""
        ).strip()

    def _link_url(self, item: dict) -> str:
        link_type = str(item.get("link_type") or "").strip()
        link_value = str(item.get("link_value") or item.get("url") or item.get("page_path") or "").strip()
        if not link_value:
            return ""
        if link_type == "page" or link_value.startswith("/pages/"):
            return link_value
        if link_type == "category":
            return f"/pages/product/list?category_id={quote(link_value)}"
        if link_type == "product":
            return f"/pages/product/detail?id={quote(link_value)}"
        if link_type == "search":
            return f"/pages/product/list?keyword={quote(link_value)}"
        return ""

    def _normalize_banner(self, item: dict, index: int) -> dict:
        row = dict(item or {})
        image_url = self._asset_url(row)
        return {
            "id": row.get("id") or f"banner_{index + 1}",
            "scene": str(row.get("scene") or "home_banner").strip(),
            "title": self._title(row),
            "name": self._title(row),
            "image_url": image_url,
            "image": image_url,
            "asset_url": image_url,
            "link_type": str(row.get("link_type") or "page").strip(),
            "link_value": str(row.get("link_value") or row.get("url") or "").strip(),
            "url": self._link_url(row),
            "sort_order": int(row.get("sort_order") or 0),
        }

    def _normalize_nav_item(self, item: dict, index: int, scene: str = "") -> dict:
        row = dict(item or {})
        title = self._title(row)
        icon_url = self._asset_url(row)
        active_icon_url = self._active_asset_url(row)
        url = self._link_url(row)
        return {
            "id": row.get("id") or f"{scene or 'nav'}_{index + 1}",
            "scene": str(row.get("scene") or scene or "").strip(),
            "title": title,
            "name": title,
            "text": title,
            "icon_url": icon_url,
            "active_icon_url": active_icon_url,
            "icon": icon_url,
            "selected_icon": active_icon_url,
            "asset_url": icon_url,
            "active_asset_url": active_icon_url,
            "link_type": str(row.get("link_type") or "page").strip(),
            "link_value": str(row.get("link_value") or row.get("page_path") or row.get("url") or "").strip(),
            "url": url,
            "page_path": url if url.startswith("/pages/") else "",
            "sort_order": int(row.get("sort_order") or 0),
        }

    def _normalize_category_entry(self, item: dict, index: int) -> dict:
        row = dict(item or {})
        extra = self._extra_json(row)
        title = self._title(row) or str(row.get("category_name") or "").strip()
        category_id = row.get("category_id") or extra.get("category_id") or ""
        if row.get("link_value") in (None, ""):
            row["link_value"] = category_id or title
        row["link_type"] = row.get("link_type") or ("category" if category_id else "search")
        icon_url = self._asset_url(row)
        active_icon_url = self._active_asset_url(row)
        return {
            "id": row.get("id") or f"category_{index + 1}",
            "scene": str(row.get("scene") or "home_category").strip(),
            "category_id": category_id,
            "category_name": str(row.get("category_name") or title).strip(),
            "title": title,
            "name": title,
            "icon_url": icon_url,
            "active_icon_url": active_icon_url,
            "asset_url": icon_url,
            "active_asset_url": active_icon_url,
            "badge_text": str(row.get("badge_text") or "").strip(),
            "subtitle": str(row.get("subtitle") or "").strip(),
            "link_type": str(row.get("link_type") or "search").strip(),
            "link_value": str(row.get("link_value") or "").strip(),
            "url": self._link_url(row),
            "sort_order": int(row.get("sort_order") or 0),
            "extra": extra,
        }

    def _home_category_copy(self, title: str) -> tuple[str, str]:
        clean_title = str(title or "").strip()
        if clean_title in HOME_CATEGORY_COPY:
            return HOME_CATEGORY_COPY[clean_title]
        if "礼盒" in clean_title:
            return "", "包装礼盒"
        if "泡袋" in clean_title:
            return "", "茶叶泡袋"
        return "", ""

    def _normalize_product_category_entry(self, item: dict, index: int) -> dict:
        row = dict(item or {})
        title = self._title(row) or str(row.get("category_name") or "").strip()
        category_id = row.get("id") or row.get("category_id") or ""
        badge_text, subtitle = self._home_category_copy(title)
        row["link_type"] = "category" if category_id else "search"
        row["link_value"] = str(category_id or title)
        icon_url = self._asset_url(row)
        active_icon_url = self._active_asset_url(row)
        return {
            "id": row.get("id") or f"category_{index + 1}",
            "scene": "home_category",
            "category_id": category_id,
            "category_name": title,
            "title": title,
            "name": title,
            "icon_url": icon_url,
            "active_icon_url": active_icon_url,
            "asset_url": icon_url,
            "active_asset_url": active_icon_url,
            "badge_text": badge_text,
            "subtitle": subtitle,
            "link_type": row["link_type"],
            "link_value": row["link_value"],
            "url": self._link_url(row),
            "sort_order": int(row.get("sort_order") or 0),
            "total": int(row.get("total") or 0),
            "extra": {},
        }

    def _safe_rows(self, method_name: str, *args) -> list[dict]:
        try:
            method = getattr(self.db, method_name)
        except AttributeError:
            return []
        try:
            rows = method(*args)
        except Exception:
            return []
        return rows if isinstance(rows, list) else []

    def image_config_payload(self) -> dict:
        assets = []
        for scene in ("home_banner", "bottom_tab"):
            for index, item in enumerate(self._safe_rows("miniapp_assets", scene, True)):
                if not isinstance(item, dict):
                    continue
                row = dict(item)
                row["title"] = self._title(row)
                row["asset_url"] = self._asset_url(row)
                row["active_asset_url"] = self._active_asset_url(row)
                row["sort_order"] = int(row.get("sort_order") or 0)
                row["enabled"] = int(row.get("enabled") or 0)
                row["index"] = index
                assets.append(row)
        categories = [
            dict(item)
            for item in self._safe_rows("product_categories")
            if isinstance(item, dict)
        ]
        return {
            "assets": assets,
            "categories": categories,
        }

    def update_image_config(self, payload: dict) -> dict:
        data = payload if isinstance(payload, dict) else {}
        target_type = str(data.get("target_type") or "").strip()
        field = str(data.get("field") or "").strip()
        url = str(data.get("url") or "").strip()
        try:
            target_id = int(data.get("id") or 0)
        except Exception:
            target_id = 0
        if target_id <= 0:
            return {"code": 400, "msg": "缺少图片配置ID"}
        if target_type == "miniapp_asset":
            if not hasattr(self.db, "update_miniapp_asset_image"):
                return {"code": 500, "msg": "数据库服务未实现小程序图片更新"}
            return self.db.update_miniapp_asset_image(target_id, field, url)
        if target_type == "category":
            if not hasattr(self.db, "update_product_category_image"):
                return {"code": 500, "msg": "数据库服务未实现分类图片更新"}
            return self.db.update_product_category_image(target_id, field, url)
        return {"code": 400, "msg": "不支持的图片配置类型"}

    def create_image_asset(self, payload: dict) -> dict:
        data = payload if isinstance(payload, dict) else {}
        scene = str(data.get("scene") or "home_banner").strip()
        if scene != "home_banner":
            return {"code": 400, "msg": "当前只支持新增首页轮播图"}
        if not hasattr(self.db, "create_miniapp_asset"):
            return {"code": 500, "msg": "数据库服务未实现小程序图片新增"}

        existing = self._safe_rows("miniapp_assets", scene, True)
        next_index = len(existing) + 1
        sort_values = []
        for item in existing:
            try:
                sort_values.append(int(item.get("sort_order") or 0))
            except Exception:
                continue
        default_sort = (max(sort_values) - 10) if sort_values else 100
        name = str(data.get("name") or f"首页轮播{next_index}").strip()
        asset = {
            "scene": scene,
            "name": name,
            "asset_url": str(data.get("asset_url") or "").strip(),
            "active_asset_url": str(data.get("active_asset_url") or "").strip(),
            "link_type": str(data.get("link_type") or "page").strip(),
            "link_value": str(data.get("link_value") or "/pages/category/index").strip(),
            "badge_text": str(data.get("badge_text") or "").strip(),
            "subtitle": str(data.get("subtitle") or "").strip(),
            "sort_order": int(data.get("sort_order") or default_sort),
            "enabled": 1,
            "extra_json": data.get("extra_json") if data.get("extra_json") not in ("", {}) else None,
        }
        return self.db.create_miniapp_asset(**asset)

    def delete_image_asset(self, asset_id: int) -> dict:
        try:
            clean_id = int(asset_id or 0)
        except Exception:
            clean_id = 0
        if clean_id <= 0:
            return {"code": 400, "msg": "缺少小程序图片ID"}
        if not hasattr(self.db, "delete_miniapp_asset"):
            return {"code": 500, "msg": "数据库服务未实现小程序图片删除"}
        return self.db.delete_miniapp_asset(clean_id)

    def config_payload(self) -> dict:
        banners = [
            self._normalize_banner(item, index)
            for index, item in enumerate(self._safe_rows("miniapp_assets", "home_banner"))
            if isinstance(item, dict)
        ]
        if not banners:
            banners = [
                self._normalize_banner(
                    {
                        "title": "首页主图",
                        "image_url": DEFAULT_HERO_IMAGE,
                        "link_type": "page",
                        "link_value": "/pages/category/index",
                    },
                    0,
                )
            ]

        categories = [
            self._normalize_product_category_entry(item, index)
            for index, item in enumerate(
                ProductService(db=self.db).categories(
                    listed_only=True,
                    exclude_names=MINIAPP_EXCLUDED_CATEGORY_NAMES,
                )
            )
            if isinstance(item, dict)
        ]
        if not categories:
            categories = [self._normalize_category_entry(item, index) for index, item in enumerate(DEFAULT_HOME_CATEGORIES)]

        nav_items: list[dict] = []

        bottom_tabs = [
            self._normalize_nav_item(item, index, "bottom_tab")
            for index, item in enumerate(self._safe_rows("miniapp_assets", "bottom_tab"))
            if isinstance(item, dict)
        ]
        if not bottom_tabs:
            bottom_tabs = [self._normalize_nav_item(item, index, "bottom_tab") for index, item in enumerate(DEFAULT_BOTTOM_TABS)]

        return {
            "version": 1,
            "source": "sjagent_core",
            "banners": banners,
            "home_categories": categories,
            "nav_items": nav_items,
            "bottom_tabs": bottom_tabs,
            "tabbar": {
                "items": [
                    {
                        "text": item["title"],
                        "page_path": item.get("page_path") or item.get("url") or "",
                        "icon": item.get("icon_url") or "",
                        "selected_icon": item.get("active_icon_url") or "",
                        "enabled": 1,
                    }
                    for item in bottom_tabs
                ]
            },
        }

    def design_payload(self) -> dict:
        result = self.db.system_setting("miniapp_design")
        data = result.get("data") if isinstance(result, dict) else {}
        value = data.get("value") if isinstance(data, dict) else {}
        return value if isinstance(value, dict) else {}

    def product_shelf_items(self, module: dict) -> list[dict]:
        try:
            limit = min(max(int(module.get("limit") or 8), 1), 30)
        except Exception:
            limit = 8
        category_id = module.get("category_id")
        try:
            clean_category_id = int(category_id) if str(category_id or "").strip() else None
        except Exception:
            clean_category_id = None
        keyword = str(module.get("keywords") or "").strip()
        items, _total = ProductService(db=self.db).list(
            keyword=keyword,
            page=1,
            page_size=limit,
            status=0,
            category_id=clean_category_id,
            group=True,
            listed_only=True,
        )
        return items if isinstance(items, list) else []

    def _decimal(self, value) -> Decimal:
        try:
            return Decimal(str(value or "0").replace(",", "").strip() or "0")
        except (InvalidOperation, ValueError):
            return Decimal("0")

    def _money_text(self, value: Decimal) -> str:
        amount = value.copy_abs().quantize(Decimal("0.01"))
        return f"¥{amount}"

    def _balance_payload(self, summary: dict | None, latest_at: str = "") -> dict:
        data = summary if isinstance(summary, dict) else {}
        amount = self._decimal(data.get("balance_amount"))
        if amount < 0:
            status_key = "debt"
            status_text = "欠款"
        elif amount > 0:
            status_key = "credit"
            status_text = "预存"
        else:
            status_key = "settled"
            status_text = "已结清"
        return {
            "amount": str(amount.quantize(Decimal("0.01"))),
            "display_amount": self._money_text(amount),
            "status_key": status_key,
            "status_text": status_text,
            "wallet_amount": str(self._decimal(data.get("wallet_amount")).quantize(Decimal("0.01"))),
            "debt_amount": str(self._decimal(data.get("debt_amount")).quantize(Decimal("0.01"))),
            "updated_at": latest_at,
        }

    def _workflow_order_images(self, value) -> list[str]:
        if value in (None, ""):
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item or "").strip()]
        text = str(value or "").strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item or "").strip()]
            if isinstance(parsed, str) and parsed.strip():
                return [parsed.strip()]
        except Exception:
            pass
        return [part.strip() for part in text.split(",") if part.strip()]

    def _workflow_status(self, item: dict) -> tuple[str, str]:
        if int(item.get("is_delivered") or 0) == 1 or str(item.get("status") or "").strip() == "completed":
            return "completed", "已完成"
        if int(item.get("is_made") or 0) == 1:
            return "pending_delivery", "待配送"
        return "pending_make", "待制作"

    def _quantity_text(self, value) -> str:
        amount = self._decimal(value)
        if amount == amount.to_integral_value():
            number = str(int(amount))
        else:
            number = f"{amount:.2f}".rstrip("0").rstrip(".")
        return f"{number} 套" if number else ""

    def _date_text(self, value) -> str:
        text = str(value or "").strip()
        if len(text) >= 16:
            return text[:16]
        return text

    def _recent_workflow_orders(self, customer_id: int, limit: int = 3) -> list[dict]:
        rows = self.db.query(
            """
            SELECT id, workflow_no, customer_name_snapshot, goods_name_snapshot,
                   color_snapshot, quantity, order_image_urls, is_screen_print,
                   is_made, is_delivered, status, created_at, updated_at
            FROM workflow_order
            WHERE deleted_at IS NULL AND customer_id=%s
            ORDER BY created_at DESC, id DESC
            LIMIT %s
            """,
            (int(customer_id), int(limit)),
        )
        items: list[dict] = []
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict):
                continue
            images = self._workflow_order_images(row.get("order_image_urls"))
            status_key, status_text = self._workflow_status(row)
            items.append({
                "id": row.get("id"),
                "order_no": str(row.get("workflow_no") or row.get("id") or "").strip(),
                "customer_name": str(row.get("customer_name_snapshot") or "").strip(),
                "product_name": str(row.get("goods_name_snapshot") or "").strip(),
                "color": str(row.get("color_snapshot") or "").strip(),
                "quantity": str(row.get("quantity") or "").strip(),
                "quantity_text": self._quantity_text(row.get("quantity")),
                "is_screen_print": bool(int(row.get("is_screen_print") or 0)),
                "status_key": status_key,
                "status_text": status_text,
                "time": self._date_text(row.get("created_at")),
                "updated_at": self._date_text(row.get("updated_at")),
                "images": images,
                "image": images[0] if images else "",
            })
        return items

    def customer_summary(self, user: dict | None = None) -> dict:
        user_data = user if isinstance(user, dict) else {}
        try:
            customer_id = int(user_data.get("linked_party_id") or 0)
        except Exception:
            customer_id = 0
        if customer_id <= 0:
            return {
                "bound": False,
                "customer": None,
                "balance": None,
                "recent": [],
                "source": "sjagent_core",
            }

        rows, _total, summary = CustomerBalanceService(db=self.db).ledger(
            customer_id,
            page=1,
            page_size=1,
        )
        latest_at = ""
        if rows and isinstance(rows[0], dict):
            latest_at = self._date_text(rows[0].get("created_at"))
        customer_name = str(
            user_data.get("linked_party_name")
            or (summary or {}).get("customer_name")
            or user_data.get("customer_name")
            or ""
        ).strip()
        return {
            "bound": True,
            "customer": {
                "id": customer_id,
                "name": customer_name,
            },
            "balance": self._balance_payload(summary, latest_at=latest_at),
            "recent": self._recent_workflow_orders(customer_id, limit=3),
            "source": "sjagent_core",
        }

    def _user_is_internal(self, user: dict) -> bool:
        try:
            if int(user.get("is_admin") or 0) == 1:
                return True
        except Exception:
            if user.get("is_admin") is True:
                return True
        role = str(user.get("role") or user.get("role_code") or "").strip().lower()
        return role in {"admin", "staff", "employee", "warehouse", "designer"}

    def _linked_customer_id(self, user: dict) -> int | None:
        for key in ("linked_party_id", "linkedPartyId", "customer_id", "customerId"):
            try:
                value = int(user.get(key) or 0)
            except Exception:
                value = 0
            if value > 0:
                return value
        return None

    def user_center_payload(self, user: dict | None = None) -> dict:
        user_data = user if isinstance(user, dict) else {}
        customer_id = None if self._user_is_internal(user_data) else self._linked_customer_id(user_data)
        should_query_orders = self._user_is_internal(user_data) or bool(customer_id)
        workflow_total = 0
        sales_total = 0
        if should_query_orders:
            try:
                _rows, workflow_total = self.db.workflow_orders(
                    keyword="",
                    page=1,
                    page_size=1,
                    status_filter="active",
                    customer_id=customer_id,
                )
            except Exception:
                workflow_total = 0
            try:
                _rows, sales_total = self.db.sales_cards(keyword="", page=1, page_size=1, status=None, customer_id=customer_id)
            except Exception:
                sales_total = 0

        workflow_count = int(workflow_total or 0)
        sales_count = int(sales_total or 0)
        order_total = workflow_count + sales_count
        return {
            "user": user,
            "message_total": 0,
            "cart_total": {"buy_number": 0},
            "user_order_count": order_total,
            "user_goods_favor_count": 0,
            "user_goods_browse_count": 0,
            "integral": 0,
            "user_order_status": [
                {"status": 0, "name": "全部订单", "count": order_total},
                {"status": 1, "name": "订单流", "count": workflow_count},
                {"status": 2, "name": "销售单", "count": sales_count},
            ],
            "navigation": [
                {"name": "订单", "event_value": "/pages/order/order", "event_type": 1, "desc": "查看订单流和销售单"},
                {"name": "商品分类", "event_value": "/pages/goods-category/goods-category", "event_type": 1, "desc": "查看产品资料"},
            ],
            "source": "sjagent_core",
        }


def get_miniapp_service() -> MiniAppService:
    return MiniAppService()
