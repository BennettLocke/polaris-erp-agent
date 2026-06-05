"""Service-layer delegation tests.

These tests use a fake DB object so the business boundary can be checked
without touching the local or server sjagent_core database.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from werkzeug.security import check_password_hash, generate_password_hash

from src.engine.exceptions import DBError
from src.services.business.auth import AuthService
from src.services.business.customers import CustomerBalanceService, CustomerService
from src.services.business.dashboard import DashboardService
from src.services.business.identity import IdentityLinkService
from src.services.business.analytics import AnalyticsService
from src.services.business.inventory import InventoryService
from src.services.business.miniapp import MiniAppService
from src.services.business.products import ProductService
from src.services.business.sales import SalesService
from src.services.business.workflow import WorkflowService
from src.services.business.users import UserService


class FakeCursor:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeDB:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []
        self.auth_users: dict[int, dict] = {
            1: {
                "id": 1,
                "username": "admin",
                "display_name": "彬",
                "phone": "13800138000",
                "password_hash": generate_password_hash("secret123"),
                "role": "admin",
                "approval_status": "approved",
                "is_active": 1,
                "is_admin": 1,
                "linked_party_id": None,
                "linked_party_name": "",
                "last_login_at": "",
            }
        }

    def product_info(self, product_id: int, *, listed_only: bool = False) -> dict:
        self.calls.append(("product_info", {"product_id": product_id, "listed_only": listed_only}))
        return {"id": product_id, "unit_id": 9}

    def system_setting(self, key: str) -> dict:
        self.calls.append(("system_setting", {"key": key}))
        return {
            "code": 0,
            "data": {
                "key": key,
                "value": {
                    "home": {
                        "modules": [
                            {
                                "type": "product_shelf",
                                "enabled": 1,
                                "limit": 2,
                                "keywords": "喜悦",
                            }
                        ]
                    }
                },
            },
        }

    def miniapp_assets(self, scene: str | None = None, include_disabled: bool = False) -> list[dict]:
        self.calls.append(("miniapp_assets", {"scene": scene, "include_disabled": include_disabled}))
        rows = {
            "home_banner": [
                {
                    "id": 1,
                    "scene": "home_banner",
                    "name": "首页主图",
                    "asset_url": "https://img.513sjbz.com/static/upload/images/app_nav/2026/04/25/1777104334795209.jpg",
                    "active_asset_url": "",
                    "link_type": "page",
                    "link_value": "/pages/category/index",
                    "sort_order": 100,
                }
            ],
            "home_category": [
                {
                    "id": 31,
                    "scene": "home_category",
                    "name": "半斤礼盒",
                    "asset_url": "https://img.example.test/half.png",
                    "active_asset_url": "",
                    "badge_text": "30",
                    "subtitle": "泡包装礼盒",
                    "link_type": "category",
                    "link_value": "7",
                    "sort_order": 100,
                    "extra_json": '{"category_id": 7}',
                }
            ],
            "home_quick": [
                {
                    "id": 21,
                    "scene": "home_quick",
                    "name": "分类",
                    "asset_url": "",
                    "active_asset_url": "",
                    "link_type": "page",
                    "link_value": "/pages/category/index",
                    "sort_order": 100,
                }
            ],
            "bottom_tab": [
                {
                    "id": 11,
                    "scene": "bottom_tab",
                    "name": "首页",
                    "asset_url": "https://img.513sjbz.com/static/upload/images/app_center_nav/2026/03/30/1774869699282797.png",
                    "active_asset_url": "https://img.513sjbz.com/static/upload/images/app_center_nav/2026/03/30/1774869699200935.png",
                    "link_type": "page",
                    "link_value": "/pages/home/index",
                    "sort_order": 100,
                }
            ],
        }
        if scene:
            return rows.get(scene, [])
        return [item for scene_rows in rows.values() for item in scene_rows]

    def create_miniapp_asset(self, **kwargs) -> dict:
        self.calls.append(("create_miniapp_asset", kwargs))
        return {"code": 0, "data": {"id": 88, **kwargs}}

    def delete_miniapp_asset(self, asset_id: int) -> dict:
        self.calls.append(("delete_miniapp_asset", {"asset_id": asset_id}))
        return {"code": 0, "data": {"id": asset_id, "affected": 1}}

    def product_search(self, keyword: str, limit: int = 80, listed_only: bool = False) -> list[dict]:
        self.calls.append(("product_search", {"keyword": keyword, "limit": limit, "listed_only": listed_only}))
        return [{"id": 88, "title": keyword}]

    def product_list(self, **kwargs):
        self.calls.append(("product_list", kwargs))
        return ([{"id": 88, "title": kwargs.get("keyword") or "商品"}], 1)

    def customer_list(self, keyword: str = "", limit: int = 100):
        self.calls.append(("customer_list", {"keyword": keyword, "limit": limit}))
        return [{"id": 11, "name": keyword or "齐唯茶业"}]

    def customer_list_page(self, **kwargs):
        self.calls.append(("customer_list_page", kwargs))
        return (
            [{"id": 11, "name": kwargs.get("keyword") or "齐唯茶业"}],
            1,
            {"total": 1, "monthly": 0, "no_phone": 1, "normal_debt": 0},
        )

    def customer_statement(self, customer_id: int, **kwargs):
        self.calls.append(("customer_statement", {"customer_id": customer_id, **kwargs}))
        return {
            "customer": {"id": customer_id, "name": "齐唯茶业"},
            "period_label": "2026-05",
            "date_from": "2026-05-01",
            "date_to": "2026-05-31",
            "opening_balance": "0.00",
            "sales_amount": "455.00",
            "receipt_amount": "0.00",
            "settlement_amount": "0.00",
            "adjust_amount": "0.00",
            "ending_balance": "-455.00",
            "sales": [],
            "ledger": [],
        }

    def update_customer_profile(self, customer_id: int, **kwargs):
        self.calls.append(("update_customer_profile", {"customer_id": customer_id, **kwargs}))
        return {"code": 0, "data": {"id": customer_id}}

    def product_categories(self, **kwargs) -> list[dict]:
        self.calls.append(("product_categories", kwargs))
        if not kwargs.get("listed_only") and not kwargs.get("exclude_names"):
            return [{"id": 1, "name": "礼盒"}]
        return [
            {
                "id": 7,
                "name": "半斤礼盒",
                "icon": "https://img.example.test/category-default.png",
                "icon_active": "https://img.example.test/category-active.png",
                "total": 17,
            }
        ]

    def save_product_category(self, payload: dict, *, operator_user_id=None) -> dict:
        self.calls.append(("save_product_category", {"payload": payload, "operator_user_id": operator_user_id}))
        return {"code": 0, "data": {"id": payload.get("id") or 31, "name": payload.get("name")}}

    def product_options(self, product_id: int | None = None) -> dict:
        self.calls.append(("product_options", {"product_id": product_id}))
        return {"code": 0, "data": {"id": product_id}}

    def save_product(self, payload: dict) -> dict:
        self.calls.append(("save_product", {"payload": payload}))
        return {"code": 0, "data": {"id": payload.get("id") or 99}}

    def delete_product(self, ids) -> dict:
        self.calls.append(("delete_product", {"ids": ids}))
        return {"code": 0, "data": {"ids": ids}}

    def update_product_shelves(self, product_id: int, state: int, **kwargs) -> dict:
        self.calls.append(("update_product_shelves", {"product_id": product_id, "state": state, **kwargs}))
        return {"code": 0, "data": {"id": product_id, "is_listed": state}}

    def get_product_price(self, product_id: int) -> float:
        self.calls.append(("get_product_price", {"product_id": product_id}))
        return 18.0

    def record_product_upload(self, url: str, storage: str = "oss") -> None:
        self.calls.append(("record_product_upload", {"url": url, "storage": storage}))

    def product_media_assets(self, **kwargs) -> list[dict]:
        self.calls.append(("product_media_assets", kwargs))
        return [{"id": 1, "url": "https://example.test/a.jpg"}]

    def delete_product_media(self, media_id: int) -> dict:
        self.calls.append(("delete_product_media", {"media_id": media_id}))
        return {"code": 0, "data": {"id": media_id}}

    def update_purchase_policy_by_series(self, series, purchase_policy: str) -> dict:
        self.calls.append(("update_purchase_policy_by_series", {"series": series, "purchase_policy": purchase_policy}))
        return {"spu": 2, "sku": 4}

    def cursor(self):
        self.calls.append(("cursor", {}))
        return FakeCursor()

    def _next_sku_no(self, cursor, *, start_number: int, compact_from_start: bool) -> str:
        self.calls.append(("_next_sku_no", {"start_number": start_number, "compact_from_start": compact_from_start}))
        return f"SJ{start_number}"

    def create_sales_order(self, **kwargs) -> dict:
        self.calls.append(("create_sales_order", kwargs))
        return {"code": 0, "data": {"id": 123, "products": kwargs["products"]}}

    def link_workflow_sales_order(self, workflow_order_id: int, sales_order_id: int, operator_user_id=None) -> dict:
        self.calls.append((
            "link_workflow_sales_order",
            {
                "workflow_order_id": workflow_order_id,
                "sales_order_id": sales_order_id,
                "operator_user_id": operator_user_id,
            },
        ))
        return {"code": 0, "data": {"workflow_order_id": workflow_order_id, "sales_order_id": sales_order_id}}

    def sales_cards(self, **kwargs):
        self.calls.append(("sales_cards", kwargs))
        return ([{"id": 123, "customer_name": "齐唯茶业"}], 1)

    def sales_print_task_list(self, **kwargs) -> dict:
        self.calls.append(("sales_print_task_list", kwargs))
        return {"code": 0, "data": {"list": []}}

    def workflow_orders(self, **kwargs):
        self.calls.append(("workflow_orders", kwargs))
        return ([{"id": 456, "customer_name": "齐唯茶业"}], 1)

    def dashboard_summary(self) -> dict:
        self.calls.append(("dashboard_summary", {}))
        return {"today_sales_count": 2, "today_sales_amount": "18.00", "pending_workflow_count": 3}

    def query(self, sql: str, params=()):
        self.calls.append(("query", {"sql": sql, "params": params}))
        if "analytics_sales_overview_kpi" in sql:
            return [{
                "sales_amount": "1260.50",
                "order_count": 9,
                "item_quantity": "88.000",
                "customer_count": 4,
                "average_order_amount": "140.0555",
            }]
        if "analytics_sales_overview_trend" in sql:
            return [
                {"date": "2026-06-01", "sales_amount": "320.00", "order_count": 2},
                {"date": "2026-06-02", "sales_amount": "940.50", "order_count": 7},
            ]
        if "analytics_sales_overview_recent" in sql:
            return [{
                "id": 123,
                "sales_no": "SO202606020001",
                "customer_name": "齐唯茶业",
                "product_summary": "【喜悦】半斤 红色 x2",
                "receivable_amount": "320.00",
                "pay_status": "paid",
                "pay_status_text": "已付款",
                "pay_type_text": "微信",
                "sales_at": "2026-06-02 10:30:00",
            }]
        if "FROM sales_order_item i" in sql and "SUM(i.quantity)" in sql:
            return [
                {
                    "product_id": 7,
                    "sku_id": 88,
                    "sku_no": "SJ1088",
                    "title": "【锦程】半斤",
                    "color": "绿色",
                    "image": "https://img.example.test/jincheng-green.jpg",
                    "sold_qty": "12.000",
                    "amount": "348.00",
                    "order_count": 5,
                    "customer_count": 4,
                    "last_sold_at": "2026-05-25 10:30:00",
                }
            ]
        if "FROM auth_session s" in sql:
            return [self.auth_users[1]]
        if "FROM auth_user u" in sql and "WHERE u.id=%s" in sql:
            user = self.auth_users.get(int(params[0]))
            return [user] if user else []
        if "FROM auth_user" in sql and "WHERE id=%s" in sql:
            user = self.auth_users.get(int(params[0]))
            return [user] if user else []
        if "FROM auth_user" in sql and "id<>%s" in sql and "(is_admin=1 OR role='admin')" in sql:
            excluded_id = int(params[0])
            total = sum(
                1
                for user in self.auth_users.values()
                if int(user.get("id") or 0) != excluded_id
                and int(user.get("is_active") or 0) == 1
                and (int(user.get("is_admin") or 0) == 1 or user.get("role") == "admin")
            )
            return [{"total": total}]
        if "FROM auth_user u" in sql and "WHERE u.username=%s" in sql:
            account = str(params[0])
            phone = str(params[1])
            for user in self.auth_users.values():
                if user.get("username") == account or str(user.get("phone") or "") == phone:
                    return [user]
            return []
        if "FROM auth_user" in sql and "WHERE is_admin=1 OR role IN" in sql:
            total = sum(1 for user in self.auth_users.values() if int(user.get("is_admin") or 0) == 1 or user.get("role") in ("admin", "staff"))
            return [{"total": total}]
        if "FROM party" in sql and "phone_normalized" in sql:
            return [{"id": 55}]
        if "FROM auth_user" in sql and "WHERE (is_admin=1 OR role IN" in sql:
            return [
                {
                    "id": user.get("id"),
                    "username": user.get("username"),
                    "display_name": user.get("display_name"),
                    "role": user.get("role"),
                    "approval_status": user.get("approval_status"),
                    "is_admin": user.get("is_admin"),
                    "is_active": user.get("is_active"),
                    "created_at": "",
                    "last_login_at": user.get("last_login_at"),
                }
                for user in self.auth_users.values()
            ]
        if "FROM print_job" in sql:
            return [{"id": int(params[0]), "document_id": 123, "sales_no": "S1"}]
        if "FROM workflow_order" in sql and "COUNT" in sql:
            return [{"count": 5}]
        if "FROM workflow_order" in sql and "customer_id=%s" in sql:
            return [
                {
                    "id": 456,
                    "workflow_no": "WF20260527001",
                    "customer_name_snapshot": "Qiwei Tea",
                    "goods_name_snapshot": "Jincheng half gift box",
                    "color_snapshot": "red",
                    "quantity": "120.000",
                    "order_image_urls": '["https://img.example.test/design.jpg"]',
                    "is_screen_print": 1,
                    "is_made": 1,
                    "is_delivered": 0,
                    "status": "pending",
                    "created_at": "2026-05-27 10:30:00",
                    "updated_at": "2026-05-27 11:00:00",
                }
            ]
        return []

    def execute(self, sql: str, params=()) -> int:
        self.calls.append(("execute", {"sql": sql, "params": params}))
        if "INSERT INTO auth_user" in sql:
            user_id = max(self.auth_users) + 1
            self.auth_users[user_id] = {
                "id": user_id,
                "username": params[0],
                "password_hash": params[1],
                "display_name": params[2],
                "phone": params[3],
                "role": params[4],
                "linked_party_id": params[5],
                "approval_status": params[6],
                "is_active": params[7],
                "is_admin": params[8],
                "linked_party_name": "",
                "last_login_at": params[9],
            }
            return 1
        if "SET approval_status='approved'" in sql:
            self.auth_users[int(params[0])]["approval_status"] = "approved"
            self.auth_users[int(params[0])]["is_active"] = 1
            return 1
        if "SET approval_status='rejected'" in sql:
            self.auth_users[int(params[0])]["approval_status"] = "rejected"
            self.auth_users[int(params[0])]["is_active"] = 0
            return 1
        if "UPDATE auth_user SET password_hash" in sql:
            self.auth_users[int(params[1])]["password_hash"] = params[0]
            return 1
        return 1

    def create_transfer(self, **kwargs) -> dict:
        self.calls.append(("create_transfer", kwargs))
        return {"code": 0, "data": kwargs}

    def customer_month_settlement(self, customer_id: int, **kwargs) -> dict:
        self.calls.append(("customer_month_settlement", {"customer_id": customer_id, **kwargs}))
        return {"code": 0}

    def customer_balance_entry(self, customer_id: int, **kwargs) -> dict:
        self.calls.append(("customer_balance_entry", {"customer_id": customer_id, **kwargs}))
        return {"code": 0}

    def customer_balance_adjust(self, customer_id: int, **kwargs) -> dict:
        self.calls.append(("customer_balance_adjust", {"customer_id": customer_id, **kwargs}))
        return {"code": 0}

    def customer_balance_ledger(self, customer_id: int, page: int = 1, page_size: int = 100):
        self.calls.append(("customer_balance_ledger", {"customer_id": customer_id, "page": page, "page_size": page_size}))
        return (
            [{"id": 901, "created_at": "2026-05-27 10:00:00", "balance_delta": "-455.00"}],
            1,
            {
                "customer_id": customer_id,
                "customer_name": "Qiwei Tea",
                "wallet_amount": "0.00",
                "debt_amount": "455.00",
                "balance_amount": "-455.00",
            },
        )

    def users(self, **kwargs):
        self.calls.append(("users", kwargs))
        return ([{"id": 1, "role": "admin"}], 1)

    def update_user(self, user_id: int, role=None, is_active=None, display_name=None):
        self.calls.append(("update_user", {"user_id": user_id, "role": role, "is_active": is_active, "display_name": display_name}))
        user = self.auth_users.get(int(user_id))
        if user and display_name is not None:
            user["display_name"] = display_name
        if user and role is not None:
            user["role"] = role
        if user and is_active is not None:
            user["is_active"] = is_active
        return {"code": 0, "data": {"id": user_id}}

    def identity_link_wechat(self, **kwargs):
        self.calls.append(("identity_link_wechat", kwargs))
        return {"code": 0, "data": {"user_id": 1, "bind_status": "linked_existing_user"}}

    def identity_sync_user_phone(self, user_id: int, **kwargs):
        self.calls.append(("identity_sync_user_phone", {"user_id": user_id, **kwargs}))
        return {"code": 0, "data": {"user_id": user_id, "phone": kwargs.get("phone")}}

    def identity_sync_customer_phone(self, customer_id: int, **kwargs):
        self.calls.append(("identity_sync_customer_phone", {"customer_id": customer_id, **kwargs}))
        return {"code": 0, "data": {"customer_id": customer_id, "phone": kwargs.get("phone")}}


class BusinessServiceTests(unittest.TestCase):
    def test_auth_service_web_login_and_permissions(self):
        db = FakeDB()
        service = AuthService(db=db)

        result = service.login_web_user(username="admin", password="secret123")

        self.assertEqual(result["code"], 0)
        self.assertEqual(result["data"]["session_user_id"], 1)
        self.assertEqual(result["data"]["user"]["role"], "admin")
        self.assertTrue(service.web_user_can_access_admin(db.auth_users[1]))
        self.assertTrue(service.has_permission("设置", db.auth_users[1]))

    def test_auth_service_register_and_approval(self):
        db = FakeDB()
        service = AuthService(db=db)

        registered = service.register_web_user(username="new_staff", password="secret123", display_name="新员工")
        new_user_id = max(db.auth_users)
        approved = service.approve_user(new_user_id)
        rejected = service.reject_user(new_user_id, admin_user_id=1)
        users = service.web_users(status="all")

        self.assertEqual(registered["code"], 0)
        self.assertTrue(registered["data"]["pending"])
        self.assertEqual(approved["data"]["affected"], 1)
        self.assertEqual(rejected["data"]["affected"], 1)
        self.assertGreaterEqual(len(users["data"]["items"]), 2)

    def test_auth_service_native_register_does_not_bind_unverified_phone_to_customer(self):
        db = FakeDB()
        service = AuthService(db=db)

        result = service.native_register(
            account="18800138000",
            password="secret123",
            display_name="微信昵称",
            client_type="miniapp",
        )

        user = result["data"]["user"]
        self.assertEqual(result["code"], 0)
        self.assertTrue(result["data"]["token"].startswith("sj_"))
        self.assertEqual(user["username"], "18800138000")
        self.assertEqual(user["role"], "customer")
        self.assertEqual(user["linked_party_id"], None)
        self.assertEqual(user["phone"], "")
        self.assertFalse(any(
            call[0] == "query" and "FROM party" in call[1]["sql"]
            for call in db.calls
        ))
        self.assertFalse(any(
            call[0] == "execute" and "INSERT INTO auth_identity" in call[1]["sql"]
            for call in db.calls
        ))

    def test_auth_service_native_register_keeps_plain_account_out_of_phone(self):
        db = FakeDB()
        service = AuthService(db=db)

        result = service.native_register(
            account="b945582097",
            password="secret123",
            display_name="Account User",
            client_type="miniapp",
        )

        new_user = db.auth_users[max(db.auth_users)]
        self.assertEqual(result["code"], 0)
        self.assertEqual(new_user["username"], "b945582097")
        self.assertIsNone(new_user["phone"])
        self.assertIsNone(new_user["linked_party_id"])
        self.assertFalse(any(
            call[0] == "query" and "FROM party" in call[1]["sql"]
            for call in db.calls
        ))
        self.assertFalse(any(
            call[0] == "execute" and "INSERT INTO auth_identity" in call[1]["sql"]
            for call in db.calls
        ))

    def test_auth_service_user_public_hides_invalid_saved_phone(self):
        db = FakeDB()
        db.auth_users[1]["phone"] = "945582097"
        service = AuthService(db=db)

        user = service.user_public(db.auth_users[1])

        self.assertEqual(user["phone"], "")
        self.assertEqual(user["mobile"], "")

    def test_auth_service_token_verification(self):
        db = FakeDB()
        service = AuthService(db=db)

        user = service.verify_token("sj_fake_token", force=True)

        self.assertEqual(user["id"], 1)
        self.assertEqual(user["role"], "admin")

    def test_auth_service_changes_native_password(self):
        db = FakeDB()
        service = AuthService(db=db)

        result = service.change_native_password(
            user_id=1,
            old_password="secret123",
            new_password="new-secret",
        )
        rejected = service.change_native_password(
            user_id=1,
            old_password="secret123",
            new_password="another-secret",
        )

        self.assertEqual(result["code"], 0)
        self.assertTrue(check_password_hash(db.auth_users[1]["password_hash"], "new-secret"))
        self.assertEqual(rejected["code"], 401)

    def test_auth_service_uses_customer_name_when_user_is_bound_to_party(self):
        db = FakeDB()
        db.auth_users[1]["display_name"] = "Wechat Nick"
        db.auth_users[1]["linked_party_id"] = 55
        db.auth_users[1]["linked_party_name"] = "\u9f50\u552f\u8336\u4e1a"
        service = AuthService(db=db)

        user = service.user_public(db.auth_users[1])

        self.assertEqual(user["display_name"], "\u9f50\u552f\u8336\u4e1a")
        self.assertEqual(user["user_display_name"], "Wechat Nick")
        self.assertEqual(user["display_name_source"], "customer")
        self.assertFalse(user["can_edit_display_name"])

    def test_auth_service_allows_profile_name_update_only_without_customer_binding(self):
        db = FakeDB()
        service = AuthService(db=db)

        updated = service.update_native_profile(user_id=1, display_name="New Nick", token="token")
        db.auth_users[1]["linked_party_id"] = 55
        db.auth_users[1]["linked_party_name"] = "\u9f50\u552f\u8336\u4e1a"
        rejected = service.update_native_profile(user_id=1, display_name="Should Not Save", token="token")

        self.assertEqual(updated["code"], 0)
        self.assertEqual(updated["data"]["user"]["display_name"], "New Nick")
        self.assertTrue(updated["data"]["user"]["can_edit_display_name"])
        self.assertEqual(rejected["code"], 403)
        self.assertEqual(db.auth_users[1]["display_name"], "New Nick")

    def test_auth_service_wechat_quick_login_exchanges_phone_code_before_binding(self):
        class PhoneCodeAuthService(AuthService):
            def __init__(self, db):
                super().__init__(db=db)
                self.phone_code_calls = []

            def wechat_session_from_code(self, authcode: str, appid: str) -> dict:
                return {"code": 0, "data": {"openid": "wx-openid", "unionid": "wx-unionid"}}

            def wechat_phone_from_code(self, phone_code: str, appid: str) -> dict:
                self.phone_code_calls.append((phone_code, appid))
                return {
                    "code": 0,
                    "data": {
                        "phone": "138 0013 8000",
                        "phone_info": {
                            "phoneNumber": "+86 138 0013 8000",
                            "purePhoneNumber": "13800138000",
                            "countryCode": "86",
                        },
                    },
                }

        db = FakeDB()
        service = PhoneCodeAuthService(db=db)

        result = service.wechat_quick_login(
            authcode="login-code",
            phone_code="phone-code",
            appid="wx-appid",
            profile={"nickName": "彬"},
        )

        self.assertEqual(result["code"], 0)
        self.assertEqual(service.phone_code_calls, [("phone-code", "wx-appid")])
        self.assertIn(
            (
                "identity_link_wechat",
                {
                    "openid": "wx-openid",
                    "unionid": "wx-unionid",
                    "phone": "13800138000",
                    "profile": {
                        "nickName": "彬",
                        "phoneNumber": "+86 138 0013 8000",
                        "purePhoneNumber": "13800138000",
                        "countryCode": "86",
                    },
                },
            ),
            db.calls,
        )

    def test_auth_service_wechat_quick_login_ignores_unverified_profile_phone(self):
        class WechatAuthService(AuthService):
            def wechat_session_from_code(self, authcode: str, appid: str) -> dict:
                return {"code": 0, "data": {"openid": "wx-openid"}}

        db = FakeDB()
        service = WechatAuthService(db=db)

        result = service.wechat_quick_login(
            authcode="login-code",
            appid="wx-appid",
            profile={"nickName": "彬", "purePhoneNumber": "13800138000", "phoneNumber": "13800138000"},
        )

        self.assertEqual(result["code"], 0)
        self.assertIn(
            (
                "identity_link_wechat",
                {
                    "openid": "wx-openid",
                    "unionid": "",
                    "phone": "",
                    "profile": {"nickName": "彬"},
                },
            ),
            db.calls,
        )

    def test_auth_service_wechat_quick_login_rejects_client_supplied_openid(self):
        db = FakeDB()
        service = AuthService(db=db)

        result = service.wechat_quick_login(
            openid="client-openid",
            profile={"nickName": "彬", "purePhoneNumber": "13800138000"},
        )

        self.assertEqual(result["code"], 400)
        self.assertFalse(any(call[0] == "identity_link_wechat" for call in db.calls))

    def test_auth_service_bind_native_phone_exchanges_phone_code_for_current_user(self):
        class PhoneCodeAuthService(AuthService):
            def __init__(self, db):
                super().__init__(db=db)
                self.phone_code_calls = []

            def wechat_phone_from_code(self, phone_code: str, appid: str) -> dict:
                self.phone_code_calls.append((phone_code, appid))
                return {
                    "code": 0,
                    "data": {
                        "phone": "13800138000",
                        "phone_info": {"purePhoneNumber": "13800138000"},
                    },
                }

        db = FakeDB()
        db.auth_users[1]["phone"] = None
        service = PhoneCodeAuthService(db=db)

        result = service.bind_native_phone(
            user_id=1,
            phone_code="phone-code",
            appid="wx-appid",
        )

        self.assertEqual(result["code"], 0)
        self.assertEqual(result["data"]["phone"], "13800138000")
        self.assertEqual(result["data"]["user"]["phone"], "13800138000")
        self.assertEqual(service.phone_code_calls, [("phone-code", "wx-appid")])
        self.assertIn(
            ("identity_sync_user_phone", {"user_id": 1, "phone": "13800138000", "operator_user_id": 1}),
            db.calls,
        )

    def test_sales_service_normalizes_unit_before_create_order(self):
        db = FakeDB()
        service = SalesService(db=db)

        result = service.create_order(
            customer_id=7,
            warehouse_id=2,
            products=[{"product_id": 88, "buy_number": 3, "price": 28}],
            pay_status="paid",
            pay_type="wechat",
            operator_user_id=5,
        )

        self.assertEqual(result["code"], 0)
        self.assertEqual(result["data"]["products"][0]["unit_id"], 9)
        self.assertEqual(db.calls[0], ("product_info", {"product_id": 88, "listed_only": False}))
        self.assertEqual(db.calls[1][0], "create_sales_order")
        self.assertEqual(db.calls[1][1]["operator_user_id"], 5)

    def test_sales_service_links_workflow_order_after_successful_create(self):
        db = FakeDB()
        service = SalesService(db=db)

        result = service.create_order(
            customer_id=7,
            warehouse_id=2,
            products=[{"product_id": 88, "buy_number": 3, "price": 28}],
            workflow_order_id=456,
            operator_user_id=5,
        )

        self.assertEqual(result["code"], 0)
        self.assertEqual(db.calls[-1], (
            "link_workflow_sales_order",
            {"workflow_order_id": 456, "sales_order_id": 123, "operator_user_id": 5},
        ))

    def test_workflow_service_links_sales_order(self):
        db = FakeDB()
        service = WorkflowService(db=db)

        result = service.link_sales_order(456, 123, operator_user_id=5)

        self.assertEqual(result["code"], 0)
        self.assertEqual(db.calls[-1], (
            "link_workflow_sales_order",
            {"workflow_order_id": 456, "sales_order_id": 123, "operator_user_id": 5},
        ))

    def test_inventory_service_transfer_delegates_operator(self):
        db = FakeDB()
        service = InventoryService(db=db)

        result = service.create_transfer(
            out_warehouse_id=2,
            enter_warehouse_id=1,
            products=[{"product_id": 88, "transfer_number": 4}],
            note="move",
            operator_user_id=5,
        )

        self.assertEqual(result["code"], 0)
        self.assertEqual(
            db.calls,
            [
                (
                    "create_transfer",
                    {
                        "out_warehouse_id": 2,
                        "enter_warehouse_id": 1,
                        "products": [{"product_id": 88, "transfer_number": 4}],
                        "note": "move",
                        "operator_user_id": 5,
                    },
                )
            ],
        )

    def test_customer_balance_service_dispatches_actions(self):
        cases = [
            ("settlement", "customer_month_settlement"),
            ("receipt", "customer_balance_entry"),
            ("recharge", "customer_balance_entry"),
            ("adjust", "customer_balance_adjust"),
        ]
        for action, expected_call in cases:
            with self.subTest(action=action):
                db = FakeDB()
                service = CustomerBalanceService(db=db)
                result = service.apply_action(
                    11,
                    action=action,
                    amount=100,
                    pay_type="wechat",
                    note="ok",
                    month="2026-05",
                    operator_user_id=5,
                )

                self.assertEqual(result["code"], 0)
                self.assertEqual(db.calls[0][0], expected_call)
                self.assertEqual(db.calls[0][1]["operator_user_id"], 5)

    def test_customer_balance_service_rejects_missing_action(self):
        service = CustomerBalanceService(db=FakeDB())

        with self.assertRaises(DBError):
            service.apply_action(11, action="", amount=100)

    def test_customer_balance_service_validates_amounts_and_adjust_note(self):
        service = CustomerBalanceService(db=FakeDB())

        for action in ("receipt", "recharge", "settlement"):
            with self.subTest(action=action, amount=0):
                with self.assertRaises(DBError):
                    service.apply_action(11, action=action, amount=0, note="ok")
            with self.subTest(action=action, amount=-1):
                with self.assertRaises(DBError):
                    service.apply_action(11, action=action, amount=-1, note="ok")

        with self.assertRaises(DBError):
            service.apply_action(11, action="adjust", amount=0, note="manual")
        with self.assertRaises(DBError):
            service.apply_action(11, action="adjust", amount=12, note="")

    def test_customer_service_exposes_paged_customer_list(self):
        db = FakeDB()
        service = CustomerService(db=db)

        rows, total, summary = service.list_page(
            "齐唯",
            page=2,
            page_size=12,
            filter_value="monthly",
        )

        self.assertEqual(rows[0]["name"], "齐唯")
        self.assertEqual(total, 1)
        self.assertEqual(summary["total"], 1)
        self.assertEqual(summary["no_phone"], 1)
        self.assertEqual(summary["normal_debt"], 0)
        self.assertEqual(
            db.calls[0],
            (
                "customer_list_page",
                {
                    "keyword": "齐唯",
                    "page": 2,
                    "page_size": 12,
                    "filter_value": "monthly",
                },
            ),
        )

    def test_customer_service_updates_profile_without_identity_logic(self):
        db = FakeDB()
        service = CustomerService(db=db)

        result = service.update_profile(11, name="古越茗风", contacts_name="林", address="店里")

        self.assertEqual(result["code"], 0)
        self.assertEqual(
            db.calls[0],
            (
                "update_customer_profile",
                {
                    "customer_id": 11,
                    "name": "古越茗风",
                    "contacts_name": "林",
                    "address": "店里",
                },
            ),
        )

    def test_customer_service_reads_statement_from_native_db(self):
        db = FakeDB()
        service = CustomerService(db=db)

        statement = service.statement(11, month="2026-05")

        self.assertEqual(statement["customer"]["name"], "齐唯茶业")
        self.assertEqual(statement["sales_amount"], "455.00")
        self.assertEqual(
            db.calls[-1],
            (
                "customer_statement",
                {
                    "customer_id": 11,
                    "month": "2026-05",
                    "date_from": "",
                    "date_to": "",
                },
            ),
        )

    def test_product_service_owns_product_writes_and_numbering(self):
        db = FakeDB()
        service = ProductService(db=db)

        self.assertEqual(service.search("SJ1570", limit=20)[0]["title"], "SJ1570")
        self.assertEqual(service.list(keyword="喜悦", page=1, page_size=20)[1], 1)
        self.assertEqual(service.categories()[0]["name"], "礼盒")
        self.assertEqual(service.options(88)["data"]["id"], 88)
        self.assertEqual(service.save({"title": "新品"})["data"]["id"], 99)
        self.assertEqual(service.delete("88")["code"], 0)
        self.assertEqual(service.update_shelves(88, 1)["data"]["is_listed"], 1)
        self.assertEqual(service.price(88), 18.0)
        service.record_upload("https://example.test/a.jpg")
        self.assertEqual(service.media_assets(limit=10)[0]["id"], 1)
        self.assertEqual(service.delete_media(1)["data"]["id"], 1)
        self.assertEqual(service.update_purchase_policy_by_series(["喜悦"], "one_case")["sku"], 4)
        self.assertEqual(service.next_sku_no(start_number=1570), "SJ1570")
        self.assertEqual(
            [call[0] for call in db.calls],
            [
                "product_search",
                "product_list",
                "product_categories",
                "product_options",
                "save_product",
                "delete_product",
                "update_product_shelves",
                "get_product_price",
                "record_product_upload",
                "product_media_assets",
                "delete_product_media",
                "update_purchase_policy_by_series",
                "cursor",
                "_next_sku_no",
            ],
        )

    def test_product_service_can_save_product_categories(self):
        db = FakeDB()
        service = ProductService(db=db)

        result = service.save_category({"name": "PVC礼盒", "inventory_policy": "none"}, operator_user_id=7)

        self.assertEqual(result["data"]["name"], "PVC礼盒")
        self.assertEqual(db.calls[0], (
            "save_product_category",
            {"payload": {"name": "PVC礼盒", "inventory_policy": "none"}, "operator_user_id": 7},
        ))

    def test_product_service_can_restrict_frontend_reads_to_listed_products(self):
        db = FakeDB()
        service = ProductService(db=db)

        service.list(keyword="喜悦", page=1, page_size=20, group=True, listed_only=True)
        service.info(88, listed_only=True)

        self.assertEqual(db.calls[0], (
            "product_list",
            {
                "keyword": "喜悦",
                "page": 1,
                "page_size": 20,
                "status": None,
                "category_id": None,
                "group": True,
                "category_ids": None,
                "listed_only": True,
                "sort": "",
                "listed_state": "",
                "stock_mode": "",
                "quality": "",
            },
        ))
        self.assertEqual(db.calls[1], ("product_info", {"product_id": 88, "listed_only": True}))

    def test_product_service_passes_sort_mode_to_product_list(self):
        db = FakeDB()
        service = ProductService(db=db)

        service.list(keyword="gift", page=2, page_size=10, group=True, listed_only=True, sort="price_asc")

        self.assertEqual(db.calls[0], (
            "product_list",
            {
                "keyword": "gift",
                "page": 2,
                "page_size": 10,
                "status": None,
                "category_id": None,
                "group": True,
                "category_ids": None,
                "listed_only": True,
                "sort": "price_asc",
                "listed_state": "",
                "stock_mode": "",
                "quality": "",
            },
        ))

    def test_product_service_passes_product_type_when_requested(self):
        db = FakeDB()
        service = ProductService(db=db)

        service.list(keyword="", page=1, page_size=14, group=True, product_type="bag")

        self.assertEqual(db.calls[0], (
            "product_list",
            {
                "keyword": "",
                "page": 1,
                "page_size": 14,
                "status": None,
                "category_id": None,
                "group": True,
                "category_ids": None,
                "listed_only": False,
                "sort": "",
                "product_type": "bag",
                "listed_state": "",
                "stock_mode": "",
                "quality": "",
            },
        ))

    def test_product_service_can_restrict_miniapp_categories_to_listed_products(self):
        db = FakeDB()
        service = ProductService(db=db)

        service.categories(listed_only=True, exclude_names=["纯色泡袋", "品种茶泡袋", "2泡礼盒"])

        self.assertEqual(db.calls[0], (
            "product_categories",
            {
                "listed_only": True,
                "exclude_names": ["纯色泡袋", "品种茶泡袋", "2泡礼盒"],
            },
        ))

    def test_sales_service_marks_print_task_failed(self):
        db = FakeDB()
        service = SalesService(db=db)

        result = service.print_task_failed(9, sales_id=123, reason="printer offline")

        self.assertEqual(result["data"]["status"], "failed")
        self.assertEqual([call[0] for call in db.calls], ["execute", "execute"])
        self.assertIn("UPDATE print_job", db.calls[0][1]["sql"])
        self.assertIn("UPDATE sales_order", db.calls[1][1]["sql"])
        self.assertIn("print_status='failed'", db.calls[1][1]["sql"])
        self.assertNotIn("note=CONCAT", db.calls[1][1]["sql"])

    def test_sales_service_reads_print_task_row(self):
        db = FakeDB()
        service = SalesService(db=db)

        row = service.print_task_row(9)

        self.assertEqual(row["document_id"], 123)
        self.assertEqual(db.calls[0][0], "query")
        self.assertIn("FROM print_job", db.calls[0][1]["sql"])

    def test_dashboard_service_collects_summary_and_recent_orders(self):
        db = FakeDB()
        service = DashboardService(db=db)

        summary = service.summary()
        pending = service.pending_delivery_count()
        recent = service.recent_orders(limit=6)

        self.assertEqual(summary["today_sales_count"], 2)
        self.assertEqual(pending, 5)
        self.assertEqual(recent["sales"][0]["customer_name"], "齐唯茶业")
        self.assertEqual(recent["workflows"][0]["id"], 456)
        self.assertEqual(
            [call[0] for call in db.calls],
            ["dashboard_summary", "query", "sales_cards", "workflow_orders"],
        )

    def test_analytics_service_returns_hot_products_from_sales_items(self):
        db = FakeDB()
        service = AnalyticsService(db=db)

        result = service.hot_products(period="7d", limit=5, dimension="product")

        self.assertEqual(result["period"], "7d")
        self.assertEqual(result["dimension"], "product")
        self.assertEqual(result["limit"], 5)
        self.assertEqual(result["items"][0]["rank"], 1)
        self.assertEqual(result["items"][0]["product_id"], 7)
        self.assertEqual(result["items"][0]["title"], "【锦程】半斤")
        self.assertEqual(result["items"][0]["sold_qty"], 12)
        self.assertEqual(result["items"][0]["amount"], "348.00")
        self.assertEqual(result["items"][0]["order_count"], 5)
        self.assertEqual(result["items"][0]["customer_count"], 4)
        sql = db.calls[0][1]["sql"]
        params = db.calls[0][1]["params"]
        self.assertIn("FROM sales_order_item i", sql)
        self.assertIn("JOIN sales_order s", sql)
        self.assertIn("status NOT IN ('canceled', 'deleted')", sql)
        self.assertIn("sku.deleted_at IS NULL", sql)
        self.assertIn("sp.deleted_at IS NULL", sql)
        self.assertIn("sku.status = 'active'", sql)
        self.assertIn("sku.is_listed = 1", sql)
        self.assertEqual(params[-1], 5)

    def test_analytics_service_returns_sales_overview(self):
        db = FakeDB()
        service = AnalyticsService(db=db)

        result = service.sales_overview(period="invalid")

        self.assertEqual(result["period"], "7d")
        self.assertEqual(result["kpi"]["sales_amount"], "1260.50")
        self.assertEqual(result["kpi"]["order_count"], 9)
        self.assertEqual(result["kpi"]["item_quantity"], 88)
        self.assertEqual(result["kpi"]["customer_count"], 4)
        self.assertEqual(result["kpi"]["average_order_amount"], "140.06")
        self.assertEqual(result["trend"][0]["date"], "2026-06-01")
        self.assertEqual(result["trend"][0]["sales_amount"], "320.00")
        self.assertEqual(result["trend"][0]["order_count"], 2)
        self.assertEqual(result["recent_sales"][0]["sales_no"], "SO202606020001")
        self.assertEqual(result["recent_sales"][0]["pay_status_text"], "已付款")

        sql_text = "\n".join(call[1]["sql"] for call in db.calls if call[0] == "query")
        self.assertIn("s.deleted_at IS NULL", sql_text)
        self.assertIn("s.status NOT IN ('canceled', 'deleted')", sql_text)
        self.assertIn("GROUP BY DATE(s.sales_at)", sql_text)

    def test_miniapp_service_collects_home_and_user_center(self):
        db = FakeDB()
        service = MiniAppService(db=db)

        design = service.design_payload()
        products = service.product_shelf_items(design["home"]["modules"][0])
        center = service.user_center_payload(user={"id": 1, "display_name": "彬", "role": "staff"})

        self.assertEqual(products[0]["title"], "喜悦")
        self.assertEqual(center["user_order_count"], 2)
        self.assertEqual(center["user_order_status"][1]["name"], "订单流")
        self.assertTrue(db.calls[1][1]["listed_only"])
        self.assertEqual(
            [call[0] for call in db.calls],
            ["system_setting", "product_list", "workflow_orders", "sales_cards"],
        )

    def test_miniapp_service_returns_bound_customer_summary(self):
        db = FakeDB()
        db.auth_users[1]["linked_party_id"] = 55
        db.auth_users[1]["linked_party_name"] = "Qiwei Tea"
        service = MiniAppService(db=db)

        payload = service.customer_summary(db.auth_users[1])

        self.assertTrue(payload["bound"])
        self.assertEqual(payload["customer"]["id"], 55)
        self.assertEqual(payload["customer"]["name"], "Qiwei Tea")
        self.assertEqual(payload["balance"]["status_key"], "debt")
        self.assertEqual(payload["balance"]["display_amount"], "¥455.00")
        self.assertEqual(payload["recent"][0]["id"], 456)
        self.assertEqual(payload["recent"][0]["order_no"], "456")
        self.assertEqual(payload["recent"][0]["workflow_no"], "WF20260527001")
        self.assertEqual(payload["recent"][0]["status_key"], "pending_delivery")
        self.assertEqual(payload["recent"][0]["quantity_text"], "120 套")
        self.assertEqual(payload["recent"][0]["image"], "https://img.example.test/design.jpg")
        self.assertEqual(
            [call[0] for call in db.calls],
            ["customer_balance_ledger", "query"],
        )

    def test_miniapp_service_returns_empty_customer_summary_for_unbound_user(self):
        service = MiniAppService(db=FakeDB())

        payload = service.customer_summary({"id": 1, "linked_party_id": None})

        self.assertFalse(payload["bound"])
        self.assertIsNone(payload["customer"])
        self.assertIsNone(payload["balance"])
        self.assertEqual(payload["recent"], [])

    def test_miniapp_service_exposes_database_backed_config(self):
        db = FakeDB()
        service = MiniAppService(db=db)

        payload = service.config_payload()

        self.assertEqual(payload["source"], "sjagent_core")
        self.assertEqual(payload["banners"][0]["image_url"], "https://img.513sjbz.com/static/upload/images/app_nav/2026/04/25/1777104334795209.jpg")
        self.assertEqual(payload["home_categories"][0]["badge_text"], "30")
        self.assertEqual(payload["home_categories"][0]["subtitle"], "泡包装礼盒")
        self.assertEqual(payload["home_categories"][0]["icon_url"], "https://img.example.test/category-default.png")
        self.assertEqual(payload["home_categories"][0]["active_icon_url"], "https://img.example.test/category-active.png")
        self.assertEqual(payload["bottom_tabs"][0]["title"], "首页")
        self.assertEqual(payload["tabbar"]["items"][0]["page_path"], "/pages/home/index")
        self.assertEqual(
            db.calls,
            [
                ("miniapp_assets", {"scene": "home_banner", "include_disabled": False}),
                ("product_categories", {"listed_only": True, "exclude_names": ("纯色泡袋", "品种茶泡袋", "2泡礼盒")}),
                ("miniapp_assets", {"scene": "bottom_tab", "include_disabled": False}),
            ],
        )

    def test_miniapp_service_creates_and_deletes_home_banner_assets(self):
        db = FakeDB()
        service = MiniAppService(db=db)

        created = service.create_image_asset({"scene": "home_banner"})
        deleted = service.delete_image_asset(88)

        self.assertEqual(created["code"], 0)
        self.assertEqual(created["data"]["scene"], "home_banner")
        self.assertEqual(created["data"]["name"], "首页轮播2")
        self.assertEqual(created["data"]["link_value"], "/pages/category/index")
        self.assertEqual(deleted["data"]["id"], 88)
        self.assertEqual(
            db.calls,
            [
                ("miniapp_assets", {"scene": "home_banner", "include_disabled": True}),
                (
                    "create_miniapp_asset",
                    {
                        "scene": "home_banner",
                        "name": "首页轮播2",
                        "asset_url": "",
                        "active_asset_url": "",
                        "link_type": "page",
                        "link_value": "/pages/category/index",
                        "badge_text": "",
                        "subtitle": "",
                        "sort_order": 90,
                        "enabled": 1,
                        "extra_json": None,
                    },
                ),
                ("delete_miniapp_asset", {"asset_id": 88}),
            ],
        )

    def test_user_service_lists_and_updates(self):
        db = FakeDB()
        service = UserService(db=db)

        rows, total = service.list(keyword="彬", page=1, page_size=20)
        result = service.update(1, role="admin", is_active=1)

        self.assertEqual(total, 1)
        self.assertEqual(rows[0]["role"], "admin")
        self.assertEqual(result["code"], 0)
        self.assertIn("update_user", [call[0] for call in db.calls])

    def test_user_service_rejects_self_disable_and_self_role_change(self):
        db = FakeDB()
        service = UserService(db=db)

        disabled = service.update(1, is_active=0, operator_user_id=1)
        demoted = service.update(1, role="staff", operator_user_id=1)

        self.assertEqual(disabled["code"], 400)
        self.assertIn("当前登录账号", disabled["msg"])
        self.assertEqual(demoted["code"], 400)
        self.assertIn("当前登录账号", demoted["msg"])
        self.assertEqual(db.auth_users[1]["role"], "admin")
        self.assertEqual(db.auth_users[1]["is_active"], 1)
        self.assertFalse(any(call[0] == "update_user" for call in db.calls))

    def test_user_service_rejects_disabling_or_demoting_last_admin(self):
        db = FakeDB()
        service = UserService(db=db)

        disabled = service.update(1, is_active=0, operator_user_id=99)
        demoted = service.update(1, role="staff", operator_user_id=99)

        self.assertEqual(disabled["code"], 400)
        self.assertIn("最后一个管理员", disabled["msg"])
        self.assertEqual(demoted["code"], 400)
        self.assertIn("最后一个管理员", demoted["msg"])
        self.assertEqual(db.auth_users[1]["role"], "admin")
        self.assertEqual(db.auth_users[1]["is_active"], 1)
        self.assertFalse(any(call[0] == "update_user" for call in db.calls))

    def test_user_service_allows_admin_change_when_another_active_admin_exists(self):
        db = FakeDB()
        db.auth_users[2] = {
            **db.auth_users[1],
            "id": 2,
            "username": "admin2",
            "display_name": "Admin 2",
            "phone": "13800138001",
        }
        service = UserService(db=db)

        result = service.update(1, role="staff", operator_user_id=2)

        self.assertEqual(result["code"], 0)
        self.assertEqual(db.auth_users[1]["role"], "staff")
        self.assertEqual(db.auth_users[1]["is_active"], 1)

    def test_identity_link_service_normalizes_wechat_phone_binding(self):
        db = FakeDB()
        service = IdentityLinkService(db=db)

        result = service.link_wechat(
            openid="wx-openid",
            unionid="wx-unionid",
            phone="138 0013 8000",
            profile={"nickName": "彬"},
        )

        self.assertEqual(result["code"], 0)
        self.assertEqual(result["data"]["user_id"], 1)
        self.assertEqual(
            db.calls[-1],
            (
                "identity_link_wechat",
                {
                    "openid": "wx-openid",
                    "unionid": "wx-unionid",
                    "phone": "13800138000",
                    "profile": {"nickName": "彬"},
                },
            ),
        )

    def test_identity_link_service_syncs_user_and_customer_phone(self):
        db = FakeDB()
        service = IdentityLinkService(db=db)

        user_result = service.sync_user_phone(1, "138 0013 8000", operator_user_id=9)
        customer_result = service.sync_customer_phone(55, "138 0013 8000", operator_user_id=9)

        self.assertEqual(user_result["data"]["phone"], "13800138000")
        self.assertEqual(customer_result["data"]["phone"], "13800138000")
        self.assertIn(
            ("identity_sync_user_phone", {"user_id": 1, "phone": "13800138000", "operator_user_id": 9}),
            db.calls,
        )
        self.assertIn(
            ("identity_sync_customer_phone", {"customer_id": 55, "phone": "13800138000", "operator_user_id": 9}),
            db.calls,
        )


if __name__ == "__main__":
    unittest.main()
