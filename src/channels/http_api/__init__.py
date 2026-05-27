"""
HTTP API 渠道（预留 WebUI 和外部调用）
提供 RESTful API 供前端或外部系统调用 Agent
"""
import json
import hmac
import io
import os
import re
import uuid
import time
from pathlib import Path
from urllib.parse import quote, urlparse, urljoin
from flask import Flask, request, jsonify, Response, send_from_directory, session, redirect
from werkzeug.utils import secure_filename
from src.core.agent import Agent
from src.engine.exceptions import DBError
from src.core.features import feature_enabled
from src.core.product_name import PRODUCT_SPECS, normalize_product_name
from src.services.business.customers import build_customer_statement_pdf
from src.services.business import (
    get_analytics_service,
    get_auth_service,
    get_customer_balance_service,
    get_customer_service,
    get_dashboard_service,
    get_inventory_service,
    get_miniapp_service,
    get_product_service,
    get_sales_service,
    get_settings_service,
    get_user_service,
    get_workflow_service,
)
from src.utils import get_logger

logger = get_logger("sjagent.http_api")

app = Flask(__name__)
app.secret_key = os.environ.get("SJAGENT_SECRET_KEY") or "sjagent-webui-auth-secret"
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)
_agent: Agent | None = None
UPLOAD_DIR = Path(__file__).parent.parent.parent.parent / "data" / "uploads"
ADMIN_DIST_DIR = Path(__file__).resolve().parent / "admin_dist"
ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "bmp"}
ALLOWED_BAG_ARCHIVE_EXTENSIONS = {"zip"}
MINIAPP_EXCLUDED_CATEGORY_NAMES = ("纯色泡袋", "品种茶泡袋", "2泡礼盒")


def _api_exception_response(e: Exception):
    response = getattr(e, "response", None)
    if isinstance(response, dict) and response:
        return jsonify(response)
    if isinstance(e, DBError):
        return jsonify({"code": 400, "msg": str(e)}), 400
    return jsonify({"code": 500, "msg": str(e)}), 500


def _json_service_result(result: dict, default_status: int = 200):
    payload = dict(result or {})
    status = int(payload.pop("_http_status", default_status) or default_status)
    return jsonify(payload), status


def _request_truthy_arg(*names: str) -> bool:
    for name in names:
        if name not in request.args:
            continue
        value = str(request.args.get(name) or "").strip().lower()
        return value in {"1", "true", "yes", "on", "listed"}
    return False


def _payload_id_list(value) -> list[int]:
    if value in (None, ""):
        return []
    raw_values = value
    if isinstance(value, str):
        raw_values = re.split(r"[,，、\s]+", value)
    elif not isinstance(value, (list, tuple, set)):
        raw_values = [value]
    ids: list[int] = []
    for raw in raw_values:
        text = str(raw or "").strip()
        if text.isdigit():
            item = int(text)
            if item > 0 and item not in ids:
                ids.append(item)
    return ids


def _native_phone_digits(value) -> str:
    from src.services.business.auth import phone_digits
    return phone_digits(value)


def _token_hash(token: str) -> str:
    from src.services.business.auth import token_hash
    return token_hash(token)


def _ensure_native_auth_tables():
    get_auth_service().ensure_session_table()


def _native_user_public(row: dict | None, token: str = "") -> dict:
    return get_auth_service().user_public(row, token=token)


def _native_user_by_id(user_id: int) -> dict | None:
    return get_auth_service().user_by_id(user_id)


def _native_user_by_account(account: str) -> dict | None:
    return get_auth_service().user_by_account(account)


def _native_user_by_identity(provider: str, external_id: str) -> dict | None:
    return get_auth_service().user_by_identity(provider, external_id)


def _find_party_id_by_phone(phone: str) -> int | None:
    return get_auth_service().find_party_id_by_phone(phone)


def _issue_native_session(user_id: int, client_type: str = "miniapp") -> str:
    return get_auth_service().issue_session(
        user_id,
        client_type=client_type,
        ip=request.headers.get("X-Forwarded-For") or request.remote_addr or "",
        user_agent=request.headers.get("User-Agent") or "",
    )


def _verify_native_token(token: str, force: bool = False) -> dict | None:
    return get_auth_service().verify_token(token, force=force)


def _native_user_can_access_miniapp(user: dict | None) -> bool:
    return get_auth_service().user_can_access_miniapp(user)


def _optional_native_user_from_request() -> dict | None:
    token = _auth_token_from_request()
    if not token:
        return None
    try:
        return _verify_native_token(token)
    except Exception as e:
        logger.warning(f"自有用户 token 可选校验异常: {e}")
        return None


def _mini_request_user() -> dict | None:
    native_user = getattr(request, "native_user", None)
    if isinstance(native_user, dict) and native_user.get("id"):
        return native_user
    return _optional_native_user_from_request()


def _mini_order_user_can_edit(user: dict | None) -> bool:
    if not isinstance(user, dict):
        return False
    try:
        if int(user.get("is_admin") or 0) == 1:
            return True
    except Exception:
        if user.get("is_admin") is True:
            return True
    role = str(user.get("role") or user.get("role_code") or "").strip().lower()
    return role in {"admin", "staff", "employee", "warehouse", "designer"}


def _mini_order_customer_id(user: dict | None) -> int | None:
    if not isinstance(user, dict) or _mini_order_user_can_edit(user):
        return None
    for key in ("linked_party_id", "linkedPartyId", "customer_id", "customerId"):
        try:
            value = int(user.get(key) or 0)
        except Exception:
            value = 0
        if value > 0:
            return value
    return None


def _mini_orderflow_should_query(keyword: str, user: dict | None) -> bool:
    return bool(str(keyword or "").strip()) or _mini_order_user_can_edit(user) or bool(_mini_order_customer_id(user))


def _mini_orderflow_empty_payload(page: int = 1, page_size: int = 20) -> dict:
    return {
        "page": int(page or 1),
        "page_size": int(page_size or 20),
        "workflows": [],
        "workflow_total": 0,
        "sales": [],
        "sales_total": 0,
        "total": 0,
        "source": "sjagent_core",
    }


def _mini_order_edit_denied_response():
    return jsonify({"code": 403, "msg": "只有员工或管理员可以编辑订单"}), 403


def _wechat_session_from_code(authcode: str, appid: str) -> dict:
    return get_auth_service().wechat_session_from_code(authcode, appid)


def _upsert_wechat_user(openid: str, unionid: str = "", profile: dict | None = None) -> dict:
    return get_auth_service().upsert_wechat_user(openid, unionid=unionid, profile=profile)


def _web_auth_user_by_username(username: str) -> dict | None:
    return _native_user_by_account(username)


def _web_auth_user_by_id(user_id: int) -> dict | None:
    return _native_user_by_id(int(user_id))


def _current_web_user() -> dict | None:
    user_id = session.get("auth_user_id")
    if not user_id:
        session.pop("web_user_id", None)
        session.pop("native_user_id", None)
        return None
    user = get_auth_service().current_web_user(user_id)
    if not user:
        session.pop("auth_user_id", None)
        session.pop("web_user_id", None)
        session.pop("native_user_id", None)
        return None
    session["native_user_id"] = user["native_user_id"]
    return user


def _current_web_user_is_admin() -> bool:
    return get_auth_service().is_admin(_current_web_user())


def _web_auth_user_payload(user: dict | None) -> dict:
    return get_auth_service().web_user_payload(user)


def _web_user_can_access_webui(user: dict | None) -> bool:
    return get_auth_service().web_user_can_access_webui(user)


def _request_user_for_permission() -> dict | None:
    native_user = getattr(request, "native_user", None)
    if isinstance(native_user, dict) and native_user.get("id"):
        return native_user
    return _current_web_user()


def _has_permission(permission: str, user: dict | None = None) -> bool:
    user = user if isinstance(user, dict) else _request_user_for_permission()
    return get_auth_service().has_permission(permission, user)


def _permission_denied(permission: str):
    return jsonify({"code": 403, "msg": f"当前账号没有【{permission}】权限"}), 403


API_PERMISSION_RULES = [
    ({"POST"}, re.compile(r"^/api/settings/number/sku$"), "设置"),
    ({"GET", "POST"}, re.compile(r"^/api/settings/system/"), "设置"),
    ({"POST"}, re.compile(r"^/api/settings/print/sales$"), "设置"),
    ({"GET"}, re.compile(r"^/api/users$"), "设置"),
    ({"POST", "PATCH"}, re.compile(r"^/api/users/\d+$"), "设置"),
    ({"POST"}, re.compile(r"^/api/sales/add$"), "开单"),
    ({"DELETE"}, re.compile(r"^/api/sales/\d+$"), "删单"),
    ({"POST"}, re.compile(r"^/api/sales/\d+/print-task$"), "打印"),
    ({"GET"}, re.compile(r"^/api/sales/\d+/print-html$"), "打印"),
    ({"POST"}, re.compile(r"^/api/inventory/purchase$"), "调库存"),
    ({"POST"}, re.compile(r"^/api/inventory/stocktaking$"), "盘点"),
    ({"POST"}, re.compile(r"^/api/inventory/transfer$"), "调拨"),
    ({"POST", "PATCH"}, re.compile(r"^/api/customers/\d+$"), "设置"),
    ({"POST"}, re.compile(r"^/api/customers/\d+/balance$"), "调余额"),
    ({"POST"}, re.compile(r"^/api/product/upload$"), "图片上传"),
    ({"POST"}, re.compile(r"^/api/product/crop-square$"), "图片上传"),
    ({"POST"}, re.compile(r"^/api/miniapp/image-config/upload$"), "图片上传"),
    ({"GET", "POST", "PATCH"}, re.compile(r"^/api/miniapp/image-config$"), "设置"),
    ({"POST"}, re.compile(r"^/api/workflow/images/upload$"), "图片上传"),
    ({"POST", "DELETE"}, re.compile(r"^/api/product/media/\d+$"), "图片绑定"),
    ({"POST", "PATCH"}, re.compile(r"^/api/product/categories$"), "设置"),
    ({"POST"}, re.compile(r"^/api/product/(save|delete)$"), "设置"),
    ({"POST"}, re.compile(r"^/api/product/\d+/shelves$"), "设置"),
    ({"POST"}, re.compile(r"^/api/customer/create$"), "开单"),
    ({"POST"}, re.compile(r"^/api/workflow/orders$"), "开单"),
    ({"POST"}, re.compile(r"^/api/asr/hotwords/sync$"), "设置"),
]

def _web_auth_required_response():
    if request.path == "/web" or request.accept_mimetypes.accept_html:
        return redirect("/login")
    return jsonify({"code": 401, "msg": "请先登录北极星"}), 401


def _auth_token_from_request() -> str:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    return request.headers.get("X-SJ-Token", "") or request.headers.get("X-SJAgent-Token", "") or request.args.get("token", "")


def _miniapp_path_is_public(path: str) -> bool:
    public_mini_paths = {
        "/api/miniapp/config",
        "/api/mini/home",
        "/api/mini/analytics/hot-products",
        "/api/mini/goods/category",
        "/api/mini/goods/detail",
        "/api/mini/search/index",
        "/api/mini/search/datalist",
        "/api/mini/orderflow/list",
        "/api/mini/workflow-order/search",
        "/api/mini/disabled",
        "/api/mini/cart/empty",
    }
    return path in public_mini_paths


@app.before_request
def _miniapp_auth_guard():
    if request.method == "OPTIONS":
        return None
    path = request.path or ""
    if not path.startswith("/api/"):
        return None
    if path.startswith("/api/auth/"):
        return None
    if _miniapp_path_is_public(path):
        return None
    if request.headers.get("X-SJ-Client") != "miniapp":
        return None
    token = _auth_token_from_request()
    try:
        user = _verify_native_token(token)
    except Exception as e:
        logger.warning(f"自有用户 token 校验异常: {e}")
        user = None
    if not user:
        return jsonify({"code": 401, "msg": "请先登录北极星账号"}), 401
    if not _native_user_can_access_miniapp(user):
        return jsonify({"code": 403, "msg": "当前账号未开通业务操作权限"}), 403
    request.native_user = user
    return None


@app.before_request
def _webui_auth_guard():
    if request.method == "OPTIONS":
        return None
    path = request.path or ""
    if request.headers.get("X-SJ-Client") == "miniapp":
        return None
    public_paths = {
        "/login",
        "/screen",
        "/api/web-auth/login",
        "/api/web-auth/register",
        "/api/web-auth/me",
        "/api/web-auth/logout",
    }
    if (
        path in public_paths
        or path.startswith("/api/auth/")
        or path.startswith("/api/screen/")
        or path.startswith("/api/miniapp-design/assets/")
        or path == "/api/miniapp/config"
        or path.startswith("/api/mini/")
        or path.startswith("/api/print-agent/")
    ):
        return None
    if path == "/web" or path.startswith("/api/"):
        if not _current_web_user():
            return _web_auth_required_response()
    return None


@app.before_request
def _api_permission_guard():
    if request.method == "OPTIONS":
        return None
    path = request.path or ""
    if not path.startswith("/api/"):
        return None
    for methods, pattern, permission in API_PERMISSION_RULES:
        if request.method in methods and pattern.match(path):
            if not _has_permission(permission):
                return _permission_denied(permission)
            return None
    return None


@app.before_request
def _native_operator_context():
    path = request.path or ""
    if path.startswith("/api/miniapp-design/assets/"):
        return None
    user_id = None
    if path == "/web" or path.startswith("/api/"):
        native_user = getattr(request, "native_user", None)
        if isinstance(native_user, dict) and native_user.get("id"):
            user_id = native_user.get("id")
        elif request.headers.get("X-SJ-Client") != "miniapp":
            web_user = _current_web_user()
            if isinstance(web_user, dict):
                user_id = web_user.get("native_user_id") or web_user.get("id")
    from src.engine.native_db import set_native_operator_user_id
    request._native_operator_token = set_native_operator_user_id(user_id)
    return None


@app.teardown_request
def _reset_native_operator_context(exc):
    token = getattr(request, "_native_operator_token", None)
    if token is None:
        return None
    from src.engine.native_db import reset_native_operator_user_id
    request._native_operator_token = None
    try:
        reset_native_operator_user_id(token)
    except RuntimeError:
        pass
    return None


def _request_user_id(default: str = "http_user") -> str:
    native_user = getattr(request, "native_user", None)
    if isinstance(native_user, dict) and native_user.get("id"):
        return f"user_{native_user.get('id')}"
    web_user = _current_web_user()
    if isinstance(web_user, dict) and (web_user.get("native_user_id") or web_user.get("id")):
        return f"user_{web_user.get('native_user_id') or web_user.get('id')}"
    return default


def _session_snapshot(session_id: str) -> dict:
    """Return lightweight session state for the WebUI."""
    from src.core.session import SessionManager
    session = SessionManager(session_id)
    state = session.get_state() if session.has_pending() else None
    pending_intent = session.get_pending_intent() if session.has_pending() else None
    pending_action = ""
    if isinstance(state, dict):
        pending_action = state.get("pending_action", "")
    return {
        "has_pending": session.has_pending(),
        "pending_intent": pending_intent,
        "pending_action": pending_action,
        "state": state or {},
        "last_extraction": session.get_meta("last_extraction", {}),
        "last_order": session.get_meta("last_order", {}),
    }


def _pending_number(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _pending_price(value, default=0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _pending_text(*values) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _sanitize_pending_state(intent: str | None, new_state: dict, old_state: dict | None) -> dict:
    """Keep edited confirmation forms from corrupting resolved ERP ids."""
    pending_action = new_state.get("pending_action") or (old_state or {}).get("pending_action")

    if intent == "workflow" and pending_action == "confirm_image_workflow_orders":
        from src.core.customer_name import normalize_customer_name

        parsed_list = new_state.get("parsed_list") or []
        if isinstance(parsed_list, list):
            cleaned_rows = []
            customers = []
            products = []
            old_rows = (old_state or {}).get("parsed_list") or []
            for index, row in enumerate(parsed_list):
                if not isinstance(row, dict):
                    continue
                old_row = old_rows[index] if index < len(old_rows) and isinstance(old_rows[index], dict) else {}
                cleaned = dict(old_row)
                cleaned.update(row)
                customer = normalize_customer_name(cleaned.get("customer") or cleaned.get("customer_name") or "")
                cleaned["customer"] = customer or "散客"
                cleaned["goods_name"] = str(cleaned.get("goods_name") or "").strip()
                cleaned["color"] = str(cleaned.get("color") or "").strip()
                cleaned["quantity"] = max(1, _pending_number(cleaned.get("quantity"), 1))
                cleaned_rows.append(cleaned)
                if cleaned["customer"] and cleaned["customer"] not in customers:
                    customers.append(cleaned["customer"])
                if cleaned["goods_name"]:
                    products.append({
                        "name": cleaned["goods_name"],
                        "qty": cleaned["quantity"],
                        "quantity": cleaned["quantity"],
                        "unit": cleaned.get("unit") or "套",
                        "color": cleaned["color"],
                    })
            new_state["parsed_list"] = cleaned_rows
            rebuilt_order_params = {
                "customer": customers[0] if customers else "",
                "customers": customers,
                "products": products,
            }
            if new_state.get("order_params") is not None or (old_state or {}).get("order_params") is not None:
                new_state["order_params"] = rebuilt_order_params
            if new_state.get("optional_order_params") is not None or (old_state or {}).get("optional_order_params") is not None:
                new_state["optional_order_params"] = rebuilt_order_params
        return new_state

    if intent == "order" and pending_action == "confirm_image_sales":
        from src.core.customer_name import normalize_customer_name

        params = new_state.get("order_params") or {}
        if isinstance(params, dict):
            customer = normalize_customer_name(params.get("customer") or params.get("customer_name") or "")
            products = []
            for product in params.get("products") or []:
                if not isinstance(product, dict):
                    continue
                cleaned = dict(product)
                name = str(cleaned.get("name") or cleaned.get("goods_name") or cleaned.get("product_name") or "").strip()
                cleaned["name"] = name
                cleaned["qty"] = max(1, _pending_number(cleaned.get("qty", cleaned.get("quantity")), 1))
                cleaned["quantity"] = cleaned["qty"]
                cleaned["color"] = str(cleaned.get("color") or cleaned.get("spec") or "").strip()
                cleaned["unit"] = cleaned.get("unit") or "套"
                if name:
                    products.append(cleaned)
            params["customer"] = customer
            params["customers"] = [customer] if customer else []
            params["products"] = products
            new_state["order_params"] = params
        return new_state

    if intent != "order" or new_state.get("pending_action") != "confirm_create_order":
        return new_state

    old_state = old_state or {}
    products = new_state.get("products") or []
    old_products = old_state.get("products") or []
    if not isinstance(products, list):
        return new_state

    from src.skills.order_flow.workflow import OrderFlowWorkflow
    workflow = OrderFlowWorkflow()
    old_customer_name = str(old_state.get("customer_name") or old_state.get("customer") or "").strip()
    from src.core.customer_name import normalize_customer_name
    customer_name = normalize_customer_name(new_state.get("customer_name") or new_state.get("customer") or old_customer_name or "散客") or "散客"
    customer_id = new_state.get("customer_id") or old_state.get("customer_id")
    customer_changed = bool(customer_name and customer_name != old_customer_name)
    if customer_changed:
        customer_id = workflow._search_customer(customer_name)
        if customer_id is None:
            customer_id = workflow._create_customer(customer_name)
        if customer_id is None:
            raise ValueError(f"客户「{customer_name}」未找到，也无法自动创建。")
        new_state["customer_id"] = customer_id
        new_state["customer_name"] = customer_name
        new_state.pop("customer_defaulted", None)
    warehouse_id = new_state.get("warehouse_id") or old_state.get("warehouse_id") or 2
    cleaned = []
    for index, product in enumerate(products):
        if not isinstance(product, dict):
            continue
        old = old_products[index] if index < len(old_products) and isinstance(old_products[index], dict) else {}
        name = _pending_text(
            product.get("name"),
            product.get("product_name"),
            product.get("goods_name"),
            product.get("title"),
            old.get("name"),
            old.get("product_name"),
            old.get("goods_name"),
            old.get("title"),
        )
        color = _pending_text(product.get("color"), product.get("goods_color"), product.get("spec"), old.get("color"), old.get("goods_color"), old.get("spec"))
        qty = _pending_number(product.get("qty", product.get("quantity", old.get("qty", 1))), old.get("qty", 1) or 1)
        edited_price = product.get("price", None)
        price = _pending_price(edited_price, old.get("price", 0) or 0) if edited_price not in (None, "") else old.get("price", 0) or 0
        old_name = _pending_text(old.get("name"), old.get("product_name"), old.get("goods_name"), old.get("title"))
        old_color = _pending_text(old.get("color"), old.get("goods_color"), old.get("spec"))
        name_changed = bool(name and name != old_name)
        color_changed = color != old_color

        if name_changed or color_changed or not old.get("product_id") or not old.get("unit_id"):
            candidate = dict(product)
            for stale_key in (
                "id",
                "product_id",
                "unit_id",
                "base",
                "title",
                "spec",
                "simple_desc",
                "price_overridden",
            ):
                candidate.pop(stale_key, None)
            candidate["name"] = name
            candidate["color"] = color
            candidate["qty"] = qty
            candidate["quantity"] = qty
            candidate["unit"] = product.get("unit") or old.get("unit") or "套"
            resolved = workflow._search_product(candidate)
            if resolved is None:
                raise ValueError(f"商品「{name or old_name} {color}」未匹配到，不能确认开单。")
            if customer_id:
                workflow._fill_price(int(customer_id), resolved)
            merged = resolved
        else:
            merged = dict(old)
            safe_updates = {}
            for key in ("qty", "quantity", "price", "warehouse_id"):
                if key in product:
                    safe_updates[key] = product[key]
            merged.update(safe_updates)
            if customer_changed and customer_id and edited_price in (None, ""):
                workflow._fill_price(int(customer_id), merged)
                price = merged.get("price", price)

        merged["name"] = name or merged.get("name") or merged.get("title") or old_name
        merged["color"] = color
        merged["qty"] = max(1, qty)
        merged["quantity"] = max(1, qty)
        merged["price"] = price or merged.get("price", 0)
        merged["warehouse_id"] = product.get("warehouse_id") or old.get("warehouse_id") or warehouse_id
        try:
            merged["warehouse_id"] = int(merged["warehouse_id"] or 2)
        except (TypeError, ValueError):
            merged["warehouse_id"] = 2
        cleaned.append(merged)

    new_state["products"] = cleaned
    return new_state


def _extract_list_rows(result: dict) -> list[dict]:
    """Extract list rows from the ERP API's common response shapes."""
    if not isinstance(result, dict) or result.get("error"):
        return []
    data = result.get("data", result)
    if isinstance(data, dict):
        return data.get("list") or data.get("data") or data.get("rows") or []
    return data if isinstance(data, list) else []


def _native_db():
    from src.engine.native_db import get_native_db_client
    return get_native_db_client()


def _print_agent_authorized() -> bool:
    """Allow browser sessions, localhost helpers, or token-authenticated print agents."""
    if _current_web_user():
        return True
    expected = os.environ.get("SJAGENT_PRINT_AGENT_TOKEN", "").strip()
    provided = (
        request.headers.get("X-SJ-Print-Token", "")
        or request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        or request.args.get("token", "")
    ).strip()
    if expected and provided and hmac.compare_digest(expected, provided):
        return True
    remote_addr = (request.remote_addr or "").strip()
    return remote_addr in {"127.0.0.1", "::1", "localhost"}


def _print_agent_required_response():
    return jsonify({"code": 401, "msg": "print agent token required"}), 401


def _print_job_row(task_id: int) -> dict | None:
    return get_sales_service().print_task_row(task_id)


def _like_keyword(keyword: str) -> str:
    return f"%{str(keyword or '').strip()}%"


def _normalize_inventory_keyword(keyword: str) -> str:
    text = str(keyword or "").strip()
    if not text:
        return ""
    for word in ("库存", "有货", "有库存", "查货", "查一下", "查下", "查询", "看看", "帮我", "礼盒", "盒子", "的", "吗", "呢"):
        text = text.replace(word, " ")
    text = re.sub(r"(^|\s)查(?=\s|[\u4e00-\u9fa5A-Za-z0-9])", " ", text)
    return normalize_product_name(text, specs=PRODUCT_SPECS)


def _image_first(value) -> str:
    if not value:
        return ""
    if isinstance(value, list):
        return str(value[0]) if value else ""
    text = str(value).strip()
    if not text:
        return ""
    try:
        decoded = json.loads(text)
        if isinstance(decoded, list):
            return str(decoded[0]) if decoded else ""
        if isinstance(decoded, str):
            return decoded
    except Exception:
        pass
    return text.split(",")[0].strip()


def _product_status_text(status) -> str:
    return {
        0: "正常",
        1: "下架",
        2: "停售",
        3: "停产",
    }.get(int(status or 0), "正常")


def _db_sales_cards(
    keyword: str,
    page: int,
    page_size: int,
    status: int | None = None,
    status_filter: str = "active",
    pay_status: str = "",
    date_from: str = "",
    date_to: str = "",
    customer_id: int | None = None,
) -> tuple[list[dict], int]:
    return get_sales_service().cards(
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

def _db_workflow_orders(keyword: str, page: int, page_size: int, status_filter: str = "active", customer_id: int | None = None) -> tuple[list[dict], int]:
    return get_workflow_service().list_orders(keyword=keyword, page=page, page_size=page_size, status_filter=status_filter, customer_id=customer_id)

def _db_product_list(
    keyword: str,
    page: int,
    page_size: int,
    status=None,
    category_id: int | None = None,
    group: bool = False,
    category_ids: list[int] | None = None,
    product_type: str = "",
    listed_only: bool = False,
    sort: str = "",
    listed_state: str = "",
    stock_mode: str = "",
    quality: str = "",
) -> tuple[list[dict], int]:
    return get_product_service().list(
        keyword=keyword,
        page=page,
        page_size=page_size,
        status=status,
        category_id=category_id,
        group=group,
        category_ids=category_ids,
        product_type=product_type,
        listed_only=listed_only,
        sort=sort,
        listed_state=listed_state,
        stock_mode=stock_mode,
        quality=quality,
    )

def _db_product_categories(
    *,
    listed_only: bool = False,
    exclude_names: list[str] | tuple[str, ...] | None = None,
) -> list[dict]:
    return get_product_service().categories(listed_only=listed_only, exclude_names=exclude_names)

def _db_customer_list(keyword: str, limit: int = 50) -> list[dict]:
    return get_customer_service().list(keyword, limit=limit)

def _sales_detail_data(result: dict) -> dict:
    """Extract the most useful sales detail object from SalesDetail."""
    if not isinstance(result, dict) or result.get("error"):
        return {}
    data = result.get("data", result)
    if not isinstance(data, dict):
        return {}
    info = data.get("info") if isinstance(data.get("info"), dict) else {}
    merged = dict(data)
    merged.update({k: v for k, v in info.items() if k not in merged or not merged.get(k)})
    return merged


def _first_text_value(row: dict, keys: tuple[str, ...]) -> str:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return ""


def _customer_name_from_id(caller, customer_id, cache: dict) -> str:
    """Resolve a customer id to a display name via CompanyList/customer_query."""
    if not customer_id:
        return ""
    key = str(customer_id)
    if key in cache:
        return cache[key]

    def pick(rows: list[dict]) -> str:
        for row in rows:
            if not isinstance(row, dict):
                continue
            row_id = row.get("id") or row.get("customer_id") or row.get("company_id")
            if str(row_id or "") != key:
                continue
            return _first_text_value(
                row,
                ("name", "customer_name", "company_name", "title", "contacts_name"),
            )
        return ""

    name = ""
    try:
        rows = caller.call("customer_query", keyword=key)
    except Exception as e:
        logger.warning(f"客户名称补充失败: customer_id={customer_id}, error={e}")
        rows = []
    if isinstance(rows, list):
        name = pick(rows)

    if not name:
        if "__all_customers_by_id" not in cache:
            try:
                all_rows = caller.call("customer_query", keyword="")
            except Exception as e:
                logger.warning(f"客户列表补充失败: {e}")
                all_rows = []
            customer_map = {}
            for row in all_rows if isinstance(all_rows, list) else []:
                if not isinstance(row, dict):
                    continue
                row_id = row.get("id") or row.get("customer_id") or row.get("company_id")
                row_name = _first_text_value(
                    row,
                    ("name", "customer_name", "company_name", "title", "contacts_name"),
                )
                if row_id and row_name:
                    customer_map[str(row_id)] = row_name
            cache["__all_customers_by_id"] = customer_map
        name = cache["__all_customers_by_id"].get(key, "")

    cache[key] = name
    return name


def _enrich_sales_rows(caller, rows: list[dict]) -> list[dict]:
    """SalesList often returns only customer_id; enrich recent rows with SalesDetail."""
    enriched = []
    customer_cache = {}
    for row in rows:
        item = dict(row)
        sid = item.get("id") or item.get("sales_id") or item.get("sales_no")
        detail = {}
        if sid:
            try:
                detail = _sales_detail_data(caller.call("sales_detail", sales_id=int(sid)))
            except Exception as e:
                logger.warning(f"销售单详情补充失败: sales_id={sid}, error={e}")
                detail = {}
        customer_name = (
            _first_text_value(detail, ("customer_name", "company_name", "customer", "name"))
            or _first_text_value(item, ("customer_name", "company_name", "customer", "name"))
        )
        customer_id = item.get("customer_id") or item.get("company_id") or detail.get("customer_id") or detail.get("company_id")
        if customer_name and customer_name.isdigit() and customer_id:
            customer_name = ""
        if not customer_name:
            customer_name = _customer_name_from_id(caller, customer_id, customer_cache)
        if customer_name:
            item["customer_name"] = customer_name
            item["customer_display"] = customer_name
        else:
            item["customer_display"] = "客户未识别"
        if detail.get("total_price") and not item.get("total_price"):
            item["total_price"] = detail.get("total_price")
        enriched.append(item)
    return enriched


def _safe_json(data):
    """Make nested data safe for Flask JSON responses."""
    return json.loads(json.dumps(data, ensure_ascii=False, default=str))


def _as_money(value) -> str:
    if value in (None, ""):
        return "0.00"
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return str(value)


def _mini_request_payload() -> dict:
    payload = {key: request.values.get(key) for key in request.values.keys()}
    body = request.get_json(silent=True)
    if isinstance(body, dict):
        payload.update(body)
    return payload


def _mini_value(payload: dict, *names: str, default=""):
    for name in names:
        if name in payload and payload.get(name) not in (None, ""):
            return payload.get(name)
    return default


def _mini_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _mini_text_list(value) -> list[str]:
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


def _mini_category_id(payload: dict) -> int | None:
    value = _mini_value(payload, "category_id", "cat_id", "cid", "id", default="")
    category_id = _mini_int(value, 0)
    return category_id or None


def _mini_page_payload(payload: dict) -> tuple[int, int]:
    page = max(1, _mini_int(_mini_value(payload, "page", default=1), 1))
    page_size = max(1, min(_mini_int(_mini_value(payload, "page_size", "limit", default=20), 20), 100))
    return page, page_size


def _mini_unique_images(*values) -> list[str]:
    images: list[str] = []

    def add(value):
        if isinstance(value, list):
            for item in value:
                add(item)
            return
        url = str(value or "").strip()
        if url and url not in images:
            images.append(url)

    for value in values:
        add(value)
    return images


def _mini_param(name: str, value) -> dict | None:
    text = str(value or "").strip()
    if not text:
        return None
    return {"name": name, "value": text}


def _mini_product_params(product: dict) -> list[dict]:
    params = [
        _mini_param("商品编号", product.get("sku_no") or product.get("coding") or product.get("product_code")),
        _mini_param("系列", product.get("series")),
        _mini_param("规格", product.get("size_label")),
        _mini_param("颜色", product.get("color") or product.get("spec")),
        _mini_param("分类", product.get("product_category_text")),
        _mini_param("单位", product.get("unit_name")),
        _mini_param("装箱数", product.get("piece_text") or product.get("case_pack_qty")),
    ]
    return [item for item in params if item]


def _mini_product_url(product_id) -> str:
    return f"/pages/goods-detail/goods-detail?id={product_id}"


def _mini_product_content(product: dict, detail_images: list[str]) -> str:
    content = product.get("content_web") or product.get("content") or ""
    if content:
        return str(content)
    return "".join(
        f'<p><img src="{url}" style="max-width:100%;height:auto;" /></p>'
        for url in detail_images
    )


def _mini_product_payload(product: dict, *, list_item: bool = False) -> dict:
    product = dict(product or {})
    product_id = product.get("id") or product.get("product_id")
    detail_images = _mini_unique_images(product.get("detail_image_urls"))
    images = _mini_unique_images(
        product.get("main_images_list"),
        product.get("images"),
        product.get("main_images"),
        product.get("spu_main_image_url"),
        product.get("sku_image_url"),
        product.get("spec_image_url"),
    )
    if not images:
        images = detail_images[:1]
    main_image = images[0] if images else ""
    price = _as_money(product.get("price") or product.get("retail_price") or product.get("min_price"))
    min_price = _as_money(product.get("min_price") or product.get("price") or product.get("retail_price"))
    max_price = _as_money(product.get("max_price") or product.get("price") or product.get("retail_price"))
    params = _mini_product_params(product)
    photo_images = _mini_unique_images(images, detail_images)
    item = {
        **product,
        "id": product_id,
        "goods_id": product_id,
        "title": product.get("title") or product.get("name") or "商品",
        "images": main_image,
        "share_images": main_image,
        "photo": [{"images": url} for url in photo_images],
        "goods_url": _mini_product_url(product_id),
        "simple_desc": product.get("simple_desc") or product.get("piece_text") or "",
        "price": price,
        "retail_price": _as_money(product.get("retail_price") or price),
        "min_price": min_price,
        "max_price": max_price,
        "original_price": _as_money(product.get("original_price") or product.get("max_price") or 0),
        "show_field_price_status": 1,
        "show_field_original_price_status": 0,
        "show_field_price_text": "",
        "show_price_symbol": "¥",
        "show_original_price_symbol": "¥",
        "show_price_unit": "",
        "show_original_price_unit": "",
        "inventory": product.get("inventory") or 0,
        "show_inventory_status": 1,
        "show_sales_number_status": 0,
        "sales_count": product.get("sales_count") or 0,
        "access_count": product.get("access_count") or 0,
        "is_exist_many_spec": 0,
        "is_error": 1 if list_item else 0,
        "error_msg": "",
        "buy_number": "",
        "user_cart_count": "",
        "base_data": params,
        "parameters": {"base": params[:3], "detail": params},
        "content_web": _mini_product_content(product, detail_images),
        "content_app": [{"images": url} for url in detail_images],
        "seo_title": product.get("title") or product.get("name") or "商品",
        "seo_keywords": product.get("product_category_text") or "",
        "seo_desc": product.get("simple_desc") or product.get("piece_text") or "",
        "user_is_favor": 0,
        "comments_count": 0,
        "comments_score": {"rate": 0},
        "comments_data": [],
    }
    return _safe_json(item)


def _mini_category_tree(categories: list[dict]) -> list[dict]:
    nodes: dict[int, dict] = {}
    roots: list[dict] = []
    for category in categories:
        cid = _mini_int(category.get("id"), 0)
        if not cid:
            continue
        nodes[cid] = {
            "id": cid,
            "pid": _mini_int(category.get("pid") or category.get("parent_id"), 0),
            "name": category.get("name") or f"分类#{cid}",
            "vice_name": "",
            "describe": "",
            "icon": category.get("icon") or "",
            "icon_active": category.get("icon_active") or "",
            "images": category.get("images") or "",
            "big_images": category.get("big_images") or "",
            "realistic_images": category.get("realistic_images") or "",
            "total": _mini_int(category.get("total"), 0),
            "items": [],
        }
    for node in nodes.values():
        parent = nodes.get(node["pid"])
        if parent:
            parent["items"].append(node)
        else:
            roots.append(node)
    return roots


def _mini_empty_cart_total() -> dict:
    return {"buy_number": 0}


def _mini_product_page_data(items: list[dict], total: int, page: int, page_size: int) -> dict:
    page_total = max(1, (int(total or 0) + page_size - 1) // page_size) if total else 0
    goods = [_mini_product_payload(item, list_item=True) for item in items]
    return {
        "current_page": page,
        "per_page": page_size,
        "total": int(total or 0),
        "last_page": page_total,
        "page_total": page_total,
        "data": goods,
    }


def _date_text(timestamp) -> str:
    try:
        ts = int(timestamp or 0)
    except (TypeError, ValueError):
        ts = 0
    if not ts:
        return ""
    return time.strftime("%Y-%m-%d", time.localtime(ts))


def _sales_status_text(status) -> str:
    if isinstance(status, str) and not status.isdigit():
        return {
            "draft": "草稿",
            "confirmed": "已确认",
            "completed": "已完成",
            "canceled": "已取消",
            "deleted": "已删除",
        }.get(status, status or "未知状态")
    labels = {
        0: "待提交",
        1: "待审核",
        2: "审核失败",
        3: "待发货",
        4: "部分发货",
        5: "已完成",
        6: "已取消",
        7: "已关闭",
    }
    try:
        return labels.get(int(status), f"状态{status}")
    except (TypeError, ValueError):
        return "未知状态"


def _first_product_line(detail: list[dict]) -> str:
    if not detail:
        return "暂无商品明细"
    item = detail[0] if isinstance(detail[0], dict) else {}
    title = item.get("title") or item.get("product_title") or item.get("name") or "商品"
    spec = item.get("spec") or ""
    qty = item.get("buy_number") or item.get("quantity") or item.get("number") or ""
    price = _as_money(item.get("price"))
    unit = "套"
    line = f"{title}{(' ' + spec) if spec else ''}"
    if qty != "":
        line += f" x{qty}{unit}"
    if price and price != "0.00":
        line += f"  ¥{price}"
    return line


def _sales_card(caller, row: dict, customer_cache: dict) -> dict:
    sid = row.get("id") or row.get("sales_id") or row.get("sales_no")
    detail_result = {}
    if sid:
        try:
            detail_result = caller.call("sales_detail", sales_id=int(sid))
        except Exception as e:
            logger.warning(f"销售单卡片详情查询失败: sales_id={sid}, error={e}")

    detail_data = _sales_detail_data(detail_result)
    detail_rows = []
    if isinstance(detail_result, dict):
        data = detail_result.get("data") if isinstance(detail_result.get("data"), dict) else {}
        detail_rows = data.get("detail") or detail_data.get("detail") or []
    info = detail_data or row
    customer_id = info.get("customer_id") or row.get("customer_id")
    customer_name = (
        _first_text_value(info, ("customer_name", "company_name", "customer", "name"))
        or _first_text_value(row, ("customer_display", "customer_name", "company_name", "customer", "name"))
        or _customer_name_from_id(caller, customer_id, customer_cache)
        or "客户未识别"
    )
    sales_no = info.get("sales_no") or row.get("sales_no") or str(sid or "")
    products = []
    for item in detail_rows if isinstance(detail_rows, list) else []:
        if not isinstance(item, dict):
            continue
        products.append({
            "title": item.get("title") or item.get("product_title") or item.get("name") or "商品",
            "spec": item.get("spec") or "",
            "quantity": item.get("buy_number") or item.get("number") or 0,
            "price": _as_money(item.get("price")),
            "total_price": _as_money(item.get("total_price")),
            "image": item.get("images") or item.get("image") or "",
            "warehouse_id": item.get("warehouse_id"),
        })
    total_quantity = 0
    for item in products:
        try:
            total_quantity += float(item.get("quantity") or 0)
        except (TypeError, ValueError):
            pass

    return {
        "id": sid,
        "sales_no": sales_no,
        "customer_name": customer_name,
        "status": info.get("status", row.get("status")),
        "status_text": _sales_status_text(info.get("status", row.get("status"))),
        "pay_status": info.get("pay_status", row.get("pay_status")),
        "total_price": _as_money(info.get("total_price", row.get("total_price"))),
        "buy_number_count": info.get("buy_number_count", row.get("buy_number_count", 0)),
        "total_quantity": total_quantity or info.get("buy_number_count", row.get("buy_number_count", 0)),
        "date_text": _date_text(info.get("add_time", row.get("add_time"))),
        "product_summary": _first_product_line(products),
        "products": products,
        "note": info.get("note") or info.get("admin_note") or "",
    }


def _workflow_card(row: dict) -> dict:
    if not isinstance(row, dict):
        row = {}
    order_time = row.get("order_time_text") or _date_text(row.get("order_time") or row.get("add_time"))
    images = row.get("order_images") or []
    if isinstance(images, str):
        try:
            parsed_images = json.loads(images)
            images = parsed_images if isinstance(parsed_images, list) else ([parsed_images] if parsed_images else [])
        except Exception:
            images = [images] if images else []
    status = row.get("order_type_text")
    if not status:
        status = "完成" if int(row.get("order_type") or 0) == 1 else "待完成"
    return {
        "id": row.get("id"),
        "customer_name": row.get("customer_name") or "客户未填写",
        "customer_phone": row.get("customer_phone") or "",
        "goods_name": row.get("goods_name") or "商品未填写",
        "goods_color": row.get("goods_color") or "",
        "order_quantity": row.get("order_quantity") or 0,
        "is_screen_print": int(row.get("is_screen_print") or 0),
        "is_screen_print_text": row.get("is_screen_print_text") or ("是" if int(row.get("is_screen_print") or 0) else "否"),
        "is_made": int(row.get("is_made") or 0),
        "is_delivered": int(row.get("is_delivered") or 0),
        "order_type": int(row.get("order_type") or 0),
        "status_text": status,
        "order_time_text": order_time,
        "complete_time_text": row.get("complete_time_text") or "",
        "order_images": images,
    }


def _clean_product_title(title: str) -> str:
    return str(title or "商品").replace("【", "").replace("】", "")


def _compact_product_title(title: str) -> str:
    return (
        _clean_product_title(title)
        .replace(" ", "")
        .replace("　", "")
        .replace("-", "")
        .replace("_", "")
    )


def _product_series_keyword(title: str) -> str:
    text = _compact_product_title(title)
    markers = (
        "短半斤",
        "长款半斤",
        "五格短半斤",
        "二三两",
        "2大盒",
        "二大盒",
        "两大盒",
        "三小盒",
        "六小盒",
        "十小盒",
        "3小盒",
        "6小盒",
        "10小盒",
        "半斤",
        "三两",
        "二两",
        "一两",
        "3两",
        "2两",
        "1两",
    )
    positions = [text.find(marker) for marker in markers if text.find(marker) > 0]
    if not positions:
        return text
    return text[:min(positions)]


def _normalize_warehouse_name(name: str) -> str:
    text = str(name or "")
    if "百鑫" in text:
        return "百鑫仓库"
    if "自己" in text or "店" in text:
        return "店里仓库"
    return text or "仓库"


def _is_gift_box_title(title: str) -> bool:
    text = _clean_product_title(title)
    keywords = (
        "半斤",
        "3两",
        "三两",
        "2两",
        "二两",
        "1两",
        "一两",
        "2大盒",
        "二大盒",
        "两大盒",
        "3小盒",
        "三小盒",
        "6小盒",
        "六小盒",
        "10小盒",
        "十小盒",
    )
    return any(keyword in text for keyword in keywords)


def _piece_text(simple_desc: str) -> str:
    text = str(simple_desc or "").strip()
    if not text:
        return ""
    import re
    match = re.search(r"(\d+)\s*(?:套|个|张)?\s*/\s*件", text)
    if match:
        return f"1件{match.group(1)}个"
    match = re.search(r"(\d+)\s*(?:套|个|张)", text)
    if match:
        return f"1件{match.group(1)}个"
    return text.replace("规格：", "")


def _inventory_cards(
    rows: list[dict],
    limit: int,
    *,
    only_in_stock: bool = True,
    product_rows: list[dict] | None = None,
) -> list[dict]:
    cards: dict[str, dict] = {}

    def ensure_card(row: dict) -> dict | None:
        product_id = row.get("product_id") or row.get("产品ID") or row.get("id")
        title = row.get("产品名称") or row.get("title") or row.get("name") or "商品"
        if not _is_gift_box_title(title):
            return None
        key = _clean_product_title(title)
        if key not in cards:
            cards[key] = {
                "product_id": product_id,
                "title": key,
                "piece_text": _piece_text(row.get("simple_desc") or row.get("simple_desc_text") or ""),
                "total_stock": 0,
                "status_text": "缺货",
                "colors": [],
                "_color_map": {},
            }
        elif product_id and not cards[key].get("product_id"):
            cards[key]["product_id"] = product_id
        if not cards[key].get("piece_text"):
            cards[key]["piece_text"] = _piece_text(row.get("simple_desc") or "")
        return cards[key]

    def ensure_color(card: dict, row: dict, color: str) -> dict:
        product_id = row.get("product_id") or row.get("产品ID") or row.get("id")
        color_key = str(color or "默认")
        if color_key not in card["_color_map"]:
            card["_color_map"][color_key] = {
                "product_id": product_id or card.get("product_id"),
                "color": color_key,
                "total_stock": 0,
                "warehouses": {
                    "百鑫仓库": 0,
                    "店里仓库": 0,
                },
            }
            card["colors"].append(card["_color_map"][color_key])
        color_row = card["_color_map"][color_key]
        if product_id and not color_row.get("product_id"):
            color_row["product_id"] = product_id
        return color_row

    for row in rows:
        if not isinstance(row, dict):
            continue
        color = row.get("【颜色】") or row.get("spec") or row.get("color") or ""
        stock = row.get("库存数量") or row.get("inventory") or row.get("stock") or 0
        try:
            stock = int(float(stock))
        except (TypeError, ValueError):
            stock = 0
        if only_in_stock and stock <= 0:
            continue
        card = ensure_card(row)
        if not card:
            continue
        warehouse = _normalize_warehouse_name(row.get("【仓库】") or row.get("warehouse_name") or row.get("warehouse") or "仓库")
        card["total_stock"] += stock
        color_row = ensure_color(card, row, str(color or "默认"))
        color_row["total_stock"] += stock
        color_row["warehouses"][warehouse] = color_row["warehouses"].get(warehouse, 0) + stock

    if not only_in_stock:
        for row in product_rows or []:
            if not isinstance(row, dict):
                continue
            card = ensure_card(row)
            if not card:
                continue
            color = row.get("【颜色】") or row.get("spec") or row.get("color") or "默认"
            ensure_color(card, row, str(color or "默认"))

    result = list(cards.values())
    for card in result:
        card.pop("_color_map", None)
        if only_in_stock:
            card["colors"] = [item for item in card.get("colors", []) if item.get("total_stock", 0) > 0]
        total = card["total_stock"]
        if total <= 0:
            card["status_text"] = "缺货"
        elif total <= 10:
            card["status_text"] = "库存紧张"
        else:
            card["status_text"] = "有库存"
    result.sort(key=lambda item: (-int(item.get("total_stock", 0) or 0), str(item.get("title") or "")))
    return result[:limit]


def _merge_product_color_options(card: dict, products: list[dict]) -> None:
    """Add same-product color options that currently have no stock rows."""
    color_map = {item.get("color"): item for item in card.get("colors", [])}
    card_title = _compact_product_title(card.get("title") or "")
    for product in products:
        title = _compact_product_title(product.get("title") or product.get("产品名称") or product.get("name") or "")
        if title != card_title and card_title not in title and title not in card_title:
            continue
        color = str(product.get("spec") or product.get("【颜色】") or product.get("color") or "默认")
        product_id = product.get("id") or product.get("product_id") or product.get("产品ID")
        if color in color_map:
            if product_id and not color_map[color].get("product_id"):
                color_map[color]["product_id"] = product_id
            continue
        color_row = {
            "product_id": product_id,
            "color": color,
            "total_stock": 0,
            "warehouses": {
                "百鑫仓库": 0,
                "店里仓库": 0,
            },
        }
        card.setdefault("colors", []).append(color_row)
        color_map[color] = color_row


def _load_product_color_options(caller, card: dict) -> list[dict]:
    keywords = []
    title = card.get("title") or ""
    series = _product_series_keyword(title)
    for keyword in (title, series):
        keyword = str(keyword or "").strip()
        if keyword and keyword not in keywords:
            keywords.append(keyword)
    rows: list[dict] = []
    seen_ids: set[str] = set()
    for keyword in keywords:
        result = caller.call("product_search", keyword=keyword)
        if not isinstance(result, list):
            continue
        for item in result:
            product_id = str(item.get("id") or item.get("product_id") or item.get("产品ID") or "")
            key = product_id or f"{item.get('title')}|{item.get('spec')}"
            if key in seen_ids:
                continue
            seen_ids.add(key)
            rows.append(item)
    return rows


def _allowed_image(filename: str) -> bool:
    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return suffix in ALLOWED_IMAGE_EXTENSIONS


def _allowed_bag_upload(filename: str) -> bool:
    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return suffix in ALLOWED_IMAGE_EXTENSIONS or suffix in ALLOWED_BAG_ARCHIVE_EXTENSIONS


def _safe_upload_suffix(filename: str, allowed: set[str], default: str = ".jpg") -> str:
    raw_suffix = Path(str(filename or "")).suffix.lower()
    if raw_suffix.startswith(".") and raw_suffix[1:] in allowed:
        return raw_suffix
    safe_name = secure_filename(filename or "")
    safe_suffix = Path(safe_name).suffix.lower()
    if safe_suffix.startswith(".") and safe_suffix[1:] in allowed:
        return safe_suffix
    return default


def _delete_local_upload(path: Path, label: str = "上传图片") -> None:
    try:
        path.unlink(missing_ok=True)
    except Exception as e:
        logger.warning(f"{label} OSS 上传成功，但删除本地临时文件失败: {path}, error={e}")


def _format_image_result(result: dict) -> str:
    items = result.get("items") or []
    if items:
        workflow_ids = []
        for item in items:
            workflow = item.get("workflow_order") or {}
            if isinstance(workflow, dict) and (workflow.get("id") or workflow.get("data")):
                data = workflow.get("data") if isinstance(workflow.get("data"), dict) else workflow
                order_id = data.get("id") or data.get("order_id") or data.get("workflow_order_id")
                if order_id:
                    workflow_ids.append(str(order_id))

        lines = [f"图片识别完成，共 {len(items)} 个设计稿。"]
        if workflow_ids:
            lines.append("已创建工作流订单：" + "、".join(workflow_ids))
        for idx, item in enumerate(items, 1):
            parsed = item.get("parsed") or {}
            workflow = item.get("workflow_order") or {}
            order_id = ""
            if isinstance(workflow, dict) and (workflow.get("id") or workflow.get("data")):
                data = workflow.get("data") if isinstance(workflow.get("data"), dict) else workflow
                order_id = data.get("id") or data.get("order_id") or data.get("workflow_order_id") or ""

            summary = [
                parsed.get("customer_name") or "客户未识别",
                (parsed.get("goods_name") or "礼盒未识别") + (f" {parsed.get('color')}" if parsed.get("color") else ""),
                f"{parsed.get('quantity') or 1}{parsed.get('unit') or '套'}",
            ]
            if parsed.get("craft"):
                summary.append(parsed.get("craft"))
            if order_id:
                summary.append(f"工作流{order_id}")
            lines.append(f"{idx}. " + " | ".join(summary))

            if item.get("error"):
                lines.append(f"   提示：{item['error']}")
        warnings = [
            warning
            for item in items
            for warning in (item.get("product_warning") or [])
        ]
        if warnings:
            lines.append(f"提示：{len(warnings)} 个商品暂未精确匹配商品库，确认开单时会继续自动匹配；仍找不到再问你。")
        if result.get("error"):
            lines.append(f"\n整体处理提示：{result['error']}")
        return "\n".join(lines)

    parsed = result.get("parsed") or {}
    workflow = result.get("workflow_order") or {}
    warnings = result.get("product_warning") or []
    lines = ["图片识别完成。"]

    extracted = []
    if parsed.get("customer_name"):
        extracted.append(f"客户：{parsed.get('customer_name')}")
    if parsed.get("goods_name"):
        extracted.append(f"礼盒：{parsed.get('goods_name')}")
    if parsed.get("color"):
        extracted.append(f"颜色：{parsed.get('color')}")
    if parsed.get("quantity"):
        extracted.append(f"数量：{parsed.get('quantity')}{parsed.get('unit') or ''}")
    if parsed.get("craft"):
        extracted.append(f"工艺：{parsed.get('craft')}")
    if extracted:
        lines.append("\n提取结果：")
        lines.extend(extracted)

    if isinstance(workflow, dict) and (workflow.get("id") or workflow.get("data")):
        data = workflow.get("data") if isinstance(workflow.get("data"), dict) else workflow
        order_id = data.get("id") or data.get("order_id") or data.get("workflow_order_id")
        if order_id:
            lines.append(f"\n已创建工作流订单：{order_id}")
        else:
            lines.append("\n已提交工作流订单。")
    elif workflow:
        lines.append("\n已提交工作流订单。")

    if warnings:
        lines.append("\n提示：商品暂未精确匹配商品库，确认开单时会继续自动匹配；仍找不到再问你。")
    if result.get("error"):
        lines.append(f"\n处理提示：{result['error']}")

    return "\n".join(lines)


def _image_items(result: dict) -> list[dict]:
    items = result.get("items") or []
    if items:
        return [item for item in items if isinstance(item, dict)]
    return [result]


def _order_params_from_image_result(result: dict) -> dict:
    products = []
    customers = []
    for item in _image_items(result):
        parsed = item.get("parsed") or {}
        goods_name = parsed.get("goods_name") or ""
        if not goods_name:
            continue
        customer = parsed.get("customer_name") or ""
        if customer and customer not in customers:
            customers.append(customer)
        products.append({
            "name": goods_name,
            "qty": int(parsed.get("quantity") or 1),
            "quantity": int(parsed.get("quantity") or 1),
            "unit": parsed.get("unit") or "套",
            "color": parsed.get("color") or "",
        })
    return {
        "customer": customers[0] if customers else "",
        "customers": customers,
        "products": products,
    }


def _workflow_params_from_image_result(result: dict) -> list[dict]:
    rows = []
    for item in _image_items(result):
        payload = item.get("workflow_order_payload")
        if isinstance(payload, dict) and payload.get("goods_name"):
            rows.append(payload)
    return rows


def _image_has_open_order_marker(result: dict) -> bool:
    return any((item.get("parsed") or {}).get("has_kaipiao") for item in _image_items(result))


def _handle_image_workflow_flow(result: dict, session, response_text: str) -> str:
    parsed_list = _workflow_params_from_image_result(result)
    if not parsed_list:
        return response_text

    order_params = _order_params_from_image_result(result)
    state = {
        "pending_action": "confirm_image_workflow_orders",
        "parsed_list": parsed_list,
    }
    if _image_has_open_order_marker(result):
        state["order_params"] = order_params
    elif order_params.get("products"):
        state["optional_order_params"] = order_params

    session.save_pending("workflow", state)
    lines = [
        response_text,
        "",
        f"请确认是否创建 {len(parsed_list)} 个工作流订单：",
    ]
    for idx, item in enumerate(parsed_list, 1):
        color = f" {item.get('color')}" if item.get("color") else ""
        lines.append(
            f"{idx}. {item.get('customer') or '散客'} | {item.get('goods_name', '')}{color} | {item.get('quantity') or 1}"
        )
    lines.append("确认后才会真正写入工作流订单。")
    return "\n".join(lines)


def _handle_image_sales_flow(result: dict, session, response_text: str) -> str:
    params = _order_params_from_image_result(result)
    products = params.get("products") or []
    customers = params.get("customers") or []
    if not products:
        return response_text
    if len(customers) > 1:
        return (
            response_text
            + "\n\n开单提示：识别到多个客户，不能合并成一张销售单。请分别确认每个客户的开单内容。"
        )

    if _image_has_open_order_marker(result):
        from src.skills.order_flow.workflow import OrderFlowWorkflow
        order_result = OrderFlowWorkflow().execute("图片识别结果自动开单", params=params)
        if order_result.get("status") == "ask":
            session.save_pending("order", order_result["state"])
            return response_text + "\n\n开单需要确认：\n" + order_result["question"]
        return response_text + "\n\n" + order_result.get("reply", "开单流程已处理。")

    session.save_pending("order", {
        "pending_action": "confirm_image_sales",
        "order_params": params,
    })
    lines = [
        response_text,
        "",
        "备注里没有看到「开单」或「下单」，是否需要继续开销售单？",
        "回复「确认」继续开单，回复「取消」只保留工作流订单。",
    ]
    return "\n".join(lines)


def init_api(agent: Agent):
    """初始化 HTTP API"""
    global _agent
    _agent = agent
    if not feature_enabled("asr_hotword_scheduler"):
        logger.info("Aliyun ASR hotword scheduler disabled by device feature switch")
        return
    try:
        from src.services.aliyun_asr import start_hotword_scheduler
        if start_hotword_scheduler():
            logger.info("阿里云 ASR 热词每日同步任务已启动")
    except Exception as e:
        logger.warning(f"阿里云 ASR 热词同步任务未启动: {e}")



@app.route("/", methods=["GET"])
def index():
    return redirect("/web" if _current_web_user() else "/login")


@app.route("/login", methods=["GET"])
def web_login_page():
    if _current_web_user():
        return redirect("/web")
    from src.channels.http_api.webui import get_login_html
    return Response(get_login_html(), content_type="text/html; charset=utf-8")


@app.route("/api/web-auth/register", methods=["POST"])
def web_auth_register():
    body = request.get_json(silent=True) or request.form.to_dict() or {}
    username = (body.get("username") or body.get("account") or "").strip()
    password = body.get("password") or ""
    display_name = (body.get("display_name") or body.get("displayName") or username).strip()
    try:
        result = get_auth_service().register_web_user(
            username=username,
            password=password,
            display_name=display_name,
        )
        data = result.get("data") if isinstance(result, dict) else {}
        session_user_id = data.get("session_user_id") if isinstance(data, dict) else None
        if session_user_id:
            session["auth_user_id"] = int(session_user_id)
            session["native_user_id"] = int(session_user_id)
            session.permanent = True
        if isinstance(data, dict):
            data.pop("session_user_id", None)
            data.pop("auto_login", None)
        return _json_service_result(result)
    except Exception as e:
        logger.error(f"WebUI 注册异常: {e}")
        return jsonify({"code": 500, "msg": f"注册异常: {e}"}), 500


@app.route("/api/web-auth/login", methods=["POST"])
def web_auth_login():
    body = request.get_json(silent=True) or request.form.to_dict() or {}
    username = (body.get("username") or body.get("account") or "").strip()
    password = body.get("password") or ""
    try:
        result = get_auth_service().login_web_user(username=username, password=password)
        data = result.get("data") if isinstance(result, dict) else {}
        session_user_id = data.get("session_user_id") if isinstance(data, dict) else None
        if session_user_id:
            session["auth_user_id"] = int(session_user_id)
            session["native_user_id"] = int(session_user_id)
            session.permanent = True
            data.pop("session_user_id", None)
        return _json_service_result(result)
    except Exception as e:
        logger.error(f"WebUI 登录异常: {e}")
        return jsonify({"code": 500, "msg": f"登录异常: {e}"}), 500


@app.route("/api/web-auth/logout", methods=["POST", "GET"])
def web_auth_logout():
    session.pop("auth_user_id", None)
    session.pop("web_user_id", None)
    session.pop("native_user_id", None)
    if request.method == "GET":
        return redirect("/login")
    return jsonify({"code": 0, "data": {}})


@app.route("/api/web-auth/me", methods=["GET"])
def web_auth_me():
    user = _current_web_user()
    if not user:
        return jsonify({"code": 401, "msg": "未登录"}), 401
    return jsonify({"code": 0, "data": {"user": _web_auth_user_payload(user)}})


@app.route("/api/web-auth/users", methods=["GET"])
def web_auth_users():
    if not _current_web_user_is_admin():
        return jsonify({"code": 403, "msg": "只有管理员可以审批账号"}), 403
    result = get_auth_service().web_users(status=request.args.get("status") or "pending")
    return jsonify(result)


@app.route("/api/web-auth/users/<int:user_id>/approve", methods=["POST"])
def web_auth_user_approve(user_id: int):
    admin = _current_web_user()
    if not admin or int(admin.get("is_admin") or 0) != 1:
        return jsonify({"code": 403, "msg": "只有管理员可以审批账号"}), 403
    return jsonify(get_auth_service().approve_user(user_id))


@app.route("/api/web-auth/users/<int:user_id>/reject", methods=["POST"])
def web_auth_user_reject(user_id: int):
    admin = _current_web_user()
    if not admin or int(admin.get("is_admin") or 0) != 1:
        return jsonify({"code": 403, "msg": "只有管理员可以审批账号"}), 403
    result = get_auth_service().reject_user(user_id, admin_user_id=int(admin["id"]))
    return _json_service_result(result)


@app.route("/web", methods=["GET"])
def webui():
    """WebUI 聊天界面"""
    from src.channels.http_api.webui import get_webui_html
    response = Response(get_webui_html(), content_type="text/html; charset=utf-8")
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@app.route("/admin", methods=["GET"])
@app.route("/admin/", methods=["GET"])
@app.route("/admin/<path:subpath>", methods=["GET"])
def admin_app(subpath: str = ""):
    """React admin shell. The legacy /web entry remains unchanged."""
    if subpath.startswith("assets/"):
        return send_from_directory(ADMIN_DIST_DIR / "assets", subpath.removeprefix("assets/"))
    index_file = ADMIN_DIST_DIR / "index.html"
    if not index_file.exists():
        return Response("React 后台还没有构建，请先在 admin 目录执行 npm.cmd run build。", status=503, mimetype="text/plain")
    response = send_from_directory(ADMIN_DIST_DIR, "index.html")
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return response


@app.route("/screen", methods=["GET"])
def screen_page():
    """Orange Pi 480x320 kiosk page."""
    from src.channels.http_api.screen import get_screen_html

    response = Response(get_screen_html(), content_type="text/html; charset=utf-8")
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@app.route("/api/screen/assets/<path:filename>", methods=["GET"])
def screen_assets(filename: str):
    """Serve screen-only visual assets."""
    from src.channels.http_api.screen import SCREEN_ASSETS_DIR

    return send_from_directory(SCREEN_ASSETS_DIR, filename)


@app.route("/api/miniapp-design/assets/<path:filename>", methods=["GET"])
def miniapp_design_assets(filename: str):
    """Serve ShopXO-style miniapp designer visual assets."""
    assets_dir = Path(__file__).resolve().parent / "miniapp_design_assets"
    return send_from_directory(assets_dir, filename)


@app.route("/api/screen/state", methods=["GET", "POST"])
def screen_state_api():
    """Shared state for the Orange Pi screen and voice loop."""
    from src.services.screen_state import get_screen_state, update_screen_state

    if request.method == "GET":
        return jsonify({"code": 0, "data": get_screen_state()})
    body = request.get_json(silent=True) or {}
    status = body.get("status") or body.get("expression") or "idle"
    role = body.get("role")
    text = body.get("text") or body.get("message")
    reset = bool(body.get("reset"))
    return jsonify(
        {
            "code": 0,
            "data": update_screen_state(status=status, role=role, text=text, source="screen-api", reset=reset),
        }
    )


def _screen_dashboard_payload() -> dict:
    now = time.time()
    summary = get_dashboard_service().summary()
    sales_cards, _sales_total = _db_sales_cards("", 1, 4, None)
    workflow_cards, _workflow_total = _db_workflow_orders("", 1, 6, "active")
    inventory_rows = get_inventory_service().search(keyword="", only_in_stock=True, limit=900)
    inventory_cards = _inventory_cards(inventory_rows if isinstance(inventory_rows, list) else [], 12)
    low_inventory = [card for card in inventory_cards if int(card.get("total_stock") or 0) <= 30][:4]
    if not low_inventory:
        low_inventory = inventory_cards[-4:]
    pending_delivery_count = get_dashboard_service().pending_delivery_count()

    recent = []
    for card in workflow_cards[:3]:
        recent.append(
            {
                "title": f"{card.get('customer_name') or '??'} {card.get('goods_name') or ''}".strip(),
                "sub": f"{card.get('goods_color') or ''} x{card.get('order_quantity') or 0} ? {card.get('status_text') or ''}",
                "tag": "??",
                "class": "ok" if int(card.get("is_made") or 0) else "warn",
            }
        )
    sales_items = [
        {
            "title": card.get("product_summary") or card.get("sales_no") or "???",
            "sub": f"{card.get('customer_name') or '??'} ? {card.get('date_text') or ''}",
            "value": str(card.get("total_quantity") or card.get("buy_number_count") or ""),
        }
        for card in sales_cards
    ]
    inventory_items = [
        {
            "title": card.get("title") or "??",
            "sub": f"{card.get('piece_text') or ''} ? ?? {card.get('total_stock') or 0}",
            "tag": "LOW" if int(card.get("total_stock") or 0) <= 30 else "OK",
            "class": "warn" if int(card.get("total_stock") or 0) <= 30 else "ok",
        }
        for card in low_inventory[:4]
    ]
    order_items = []
    for card in workflow_cards[:6]:
        order_items.append(
            {
                "customer_name": card.get("customer_name") or "??",
                "goods_name": f"{card.get('goods_name') or ''} {card.get('goods_color') or ''}".strip(),
                "status_text": card.get("status_text") or "",
                "status_tag": "???" if not int(card.get("is_made") or 0) else "??",
            }
        )
    return {
        "summary": summary,
        "recent": recent,
        "sales": sales_items,
        "inventory": inventory_items,
        "inventory_total": len(inventory_cards),
        "orders": order_items,
        "pending_delivery_count": pending_delivery_count,
        "updated_at": int(now),
    }

@app.route("/api/screen/dashboard", methods=["GET"])
def screen_dashboard_api():
    """Compact live data for the 480x320 screen page."""
    try:
        return jsonify({"code": 0, "data": _screen_dashboard_payload()})
    except Exception as e:
        logger.warning(f"小屏业务数据查询失败: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/images/file/<path:filename>", methods=["GET"])
def image_file(filename: str):
    """Serve locally uploaded images for WebUI preview."""
    safe_name = secure_filename(filename)
    if not safe_name:
        return jsonify({"code": 400, "msg": "invalid filename"}), 400
    return send_from_directory(UPLOAD_DIR, safe_name)


@app.route("/api/agent/chat", methods=["POST"])
def chat():
    """
    对话接口
    POST /api/agent/chat
    {
        "message": "客户银茗，要1件喜悦三小盒",
        "user_id": "user_001",
        "session_id": "session_001"  // 可选
    }

    Response:
    {
        "code": 0,
        "data": {
            "response": "处理结果...",
            "session_id": "xxx"
        }
    }
    """
    global _agent

    if _agent is None:
        return jsonify({"code": 500, "msg": "Agent not initialized"}), 500

    body = request.get_json()
    message = body.get("message", "")
    user_id = _request_user_id(body.get("user_id", "http_user"))
    session_id = body.get("session_id", f"http_{int(time.time())}")

    if not message:
        return jsonify({"code": 400, "msg": "message is required"}), 400

    try:
        from src.services.screen_state import update_screen_state

        update_screen_state(status="listen", role="user", text=message, source="web-chat")
        update_screen_state(status="processing", role="assistant", text="正在处理...", source="web-chat")
        response = _agent.run(
            user_input=message,
            user_id=user_id,
            session_id=session_id,
        )
        update_screen_state(status="talk", role="assistant", text=str(response or ""), source="web-chat")
        return jsonify({
            "code": 0,
            "data": {
                "response": response,
                "session_id": session_id,
                "session": _session_snapshot(session_id),
            }
        })
    except Exception as e:
        try:
            from src.services.screen_state import update_screen_state

            update_screen_state(status="error", role="assistant", text=f"处理异常：{e}", source="web-chat")
        except Exception:
            pass
        logger.error(f"Agent 调用异常: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/session/pending", methods=["POST"])
def update_session_pending():
    """Update pending workflow state after the user edits the confirmation form."""
    body = request.get_json() or {}
    session_id = body.get("session_id") or ""
    state = body.get("state")
    if not session_id or not isinstance(state, dict):
        return jsonify({"code": 400, "msg": "session_id and state are required"}), 400
    from src.core.session import SessionManager
    session = SessionManager(session_id)
    if not session.has_pending():
        return jsonify({"code": 400, "msg": "no pending action"}), 400
    intent = session.get_pending_intent()
    old_state = session.get_state() or {}
    try:
        state = _sanitize_pending_state(intent, state, old_state)
    except ValueError as e:
        return jsonify({"code": 400, "msg": str(e)}), 400
    session.save_pending(intent, state)
    return jsonify({"code": 0, "data": {"session": _session_snapshot(session_id)}})


@app.route("/api/agent/chat/stream", methods=["POST"])
def chat_stream():
    """
    流式对话接口（SSE）
    POST /api/agent/chat/stream
    {
        "message": "你好",
        "user_id": "user_001",
        "session_id": "session_001"
    }

    Response: SSE stream
    data: {"type": "token", "text": "你"}
    data: {"type": "token", "text": "好"}
    data: {"type": "done", "session_id": "xxx"}
    """
    global _agent

    if _agent is None:
        return jsonify({"code": 500, "msg": "Agent not initialized"}), 500

    body = request.get_json()
    message = body.get("message", "")
    user_id = _request_user_id(body.get("user_id", "http_user"))
    session_id = body.get("session_id", f"http_{int(time.time())}")

    if not message:
        return jsonify({"code": 400, "msg": "message is required"}), 400

    def generate():
        try:
            from src.services.screen_state import update_screen_state

            update_screen_state(status="listen", role="user", text=message, source="web-chat")
            update_screen_state(status="processing", role="assistant", text="正在处理...", source="web-chat")
            response = _agent.run(
                user_input=message,
                user_id=user_id,
                session_id=session_id,
            )
            update_screen_state(status="talk", role="assistant", text=str(response or ""), source="web-chat")
            # 分 token 发送（按自然段落分割，避免单字碎片）
            for line in response.split("\n"):
                if line.strip():
                    token_text = line + "\n"
                else:
                    token_text = "\n"
                yield f"data: {json.dumps({'type': 'token', 'text': token_text}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'session_id': session_id}, ensure_ascii=False)}\n\n"
        except Exception as e:
            try:
                from src.services.screen_state import update_screen_state

                update_screen_state(status="error", role="assistant", text=f"处理异常：{e}", source="web-chat")
            except Exception:
                pass
            logger.error(f"Agent 流式调用异常: {e}")
            yield f"data: {json.dumps({'type': 'error', 'text': str(e)}, ensure_ascii=False)}\n\n"

    return Response(generate(), mimetype='text/event-stream')


@app.route("/api/images/upload", methods=["POST"])
def image_upload():
    """Upload an order/design image, run OCR, and create a workflow order when possible."""
    file = request.files.get("image")
    session_id = request.form.get("session_id") or f"http_{int(time.time())}"
    if not file or not file.filename:
        return jsonify({"code": 400, "msg": "image is required"}), 400

    from src.core.session import SessionManager
    from src.core.tools.caller import get_tool_caller
    from src.core.nodes.image_workflow import process_single_image

    session = SessionManager(session_id)
    is_bag_upload = session.has_pending() and session.get_pending_intent() == "bag_upload"
    if is_bag_upload:
        if not feature_enabled("bag_upload"):
            session.clear_pending()
            return jsonify({"code": 403, "msg": "bag upload is disabled on this device"}), 403
        if not _allowed_bag_upload(file.filename):
            return jsonify({"code": 400, "msg": "泡袋流程只支持 png/jpg/jpeg/webp/bmp 图片或 zip 压缩包"}), 400
    elif not _allowed_image(file.filename):
        return jsonify({"code": 400, "msg": "只支持 png/jpg/jpeg/webp/bmp 图片"}), 400

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    allowed_suffixes = ALLOWED_IMAGE_EXTENSIONS | (ALLOWED_BAG_ARCHIVE_EXTENSIONS if is_bag_upload else set())
    suffix = _safe_upload_suffix(file.filename, allowed_suffixes, ".jpg")
    save_name = f"{int(time.time())}_{uuid.uuid4().hex[:10]}{suffix}"
    save_path = UPLOAD_DIR / save_name
    file.save(save_path)

    try:
        if is_bag_upload:
            if _agent is None:
                return jsonify({"code": 500, "msg": "Agent not initialized"}), 500
            preview_url = f"/api/images/file/{save_name}" if _allowed_image(save_name) else ""
            response_text = _agent.run(
                user_input=f"图片: {save_path} 预览: {preview_url}",
                user_id=_request_user_id("http_user"),
                session_id=session_id,
            )
            return jsonify({
                "code": 0,
                "data": {
                    "response": response_text,
                    "session_id": session_id,
                    "session": _session_snapshot(session_id),
                    "image_path": str(save_path),
                    "result": {
                        "preview_url": preview_url,
                        "image_path": str(save_path),
                        "mode": "bag_upload",
                    },
                }
            })

        caller = get_tool_caller()
        result = process_single_image(str(save_path), caller)
        result["preview_url"] = f"/api/images/file/{save_name}"
        response_text = _format_image_result(result)

        session = SessionManager(session_id)
        session.clear_pending()
        response_text = _handle_image_workflow_flow(result, session, response_text)
        if not session.has_pending():
            response_text = _handle_image_sales_flow(result, session, response_text)
        session.set_meta("last_extraction", {
            "user_input": f"上传图片：{file.filename}",
            "intent": "workflow",
            "params": {
                "action": "image_upload",
                "image_path": str(save_path),
            },
        })
        session.save_turn(f"上传图片：{file.filename}", response_text)

        return jsonify({
            "code": 0,
            "data": {
                "response": response_text,
                "session_id": session_id,
                "session": _session_snapshot(session_id),
                "image_path": str(save_path),
                "result": _safe_json(result),
            }
        })
    except Exception as e:
        logger.error(f"图片上传识别异常: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/workflow/images/upload", methods=["POST"])
def workflow_image_upload():
    """Upload workflow order images to OSS only, without OCR or order creation."""
    file = request.files.get("image")
    if not file or not file.filename:
        return jsonify({"code": 400, "msg": "image is required"}), 400
    if not _allowed_image(file.filename):
        return jsonify({"code": 400, "msg": "只支持 png/jpg/jpeg/webp/bmp 图片"}), 400

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    original_name = secure_filename(file.filename) or "workflow.jpg"
    suffix = Path(original_name).suffix.lower() or ".jpg"
    save_name = f"workflow_{int(time.time())}_{uuid.uuid4().hex[:10]}{suffix}"
    save_path = UPLOAD_DIR / save_name
    file.save(save_path)

    try:
        from scripts.oss_uploader import OSSUploader
        from src.core.config import get_config

        result = OSSUploader(get_config().oss_config).upload(str(save_path))
        if not isinstance(result, dict):
            return jsonify({"code": 500, "msg": "OSS 上传返回异常", "data": result}), 500
        if result.get("error"):
            return jsonify({"code": 500, "msg": result.get("error"), "data": result}), 500
        _delete_local_upload(save_path, "工作流订单图片")
        return jsonify(result if isinstance(result, dict) and "code" in result else {"code": 0, "data": result})
    except Exception as e:
        logger.error(f"工作流订单图片上传 OSS 失败: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/agent/history", methods=["GET"])
def history():
    """
    获取对话历史
    GET /api/agent/history?session_id=xxx
    """
    session_id = request.args.get("session_id", "")
    if not session_id:
        return jsonify({"code": 400, "msg": "session_id is required"}), 400

    try:
        from src.core.session import SessionManager
        session = SessionManager(session_id)
        hist = session.get_history()
        return jsonify({
            "code": 0,
            "data": {
                "session_id": session_id,
                "history": hist,
                "session": _session_snapshot(session_id),
            }
        })
    except Exception as e:
        logger.error(f"获取历史失败: {e}")
        return jsonify({
            "code": 0,
            "data": {
                "session_id": session_id,
                "history": [],
            }
        })


@app.route("/api/orders/recent", methods=["GET"])
def recent_orders():
    """
    Recent sales and workflow orders for the WebUI side panel.
    GET /api/orders/recent?limit=6
    """
    limit = request.args.get("limit", 6, type=int)
    limit = max(1, min(limit, 20))

    try:
        data = get_dashboard_service().recent_orders(limit=limit)
    except Exception as e:
        logger.warning(f"最近业务记录查询失败: {e}")
        data = {"sales": [], "workflows": []}

    return jsonify({
        "code": 0,
        "data": data,
    })


@app.route("/api/dashboard/summary", methods=["GET"])
def dashboard_summary():
    """Live dashboard numbers for the WebUI workbench."""
    try:
        return jsonify({"code": 0, "data": get_dashboard_service().summary()})
    except Exception as e:
        logger.warning(f"?????????: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


def _analytics_hot_products_payload(payload: dict) -> dict:
    period = str(_mini_value(payload, "period", "range", default="30d") or "30d").strip()
    dimension = str(_mini_value(payload, "dimension", "by", default="product") or "product").strip()
    limit = _mini_int(_mini_value(payload, "limit", "page_size", default=20), 20)
    category_names = _mini_text_list(
        _mini_value(payload, "category_names", "categoryNames", "categories", default=[])
    )
    return get_analytics_service().hot_products(
        period=period,
        limit=limit,
        dimension=dimension,
        category_names=category_names,
    )


@app.route("/api/analytics/hot-products", methods=["GET"])
def analytics_hot_products_api():
    """Hot product ranking for WebUI dashboards."""
    try:
        return jsonify({"code": 0, "data": _analytics_hot_products_payload(request.args.to_dict(flat=True))})
    except Exception as e:
        logger.warning(f"热销商品查询失败: {e}")
        return _api_exception_response(e)


@app.route("/api/mini/analytics/hot-products", methods=["GET", "POST"])
def mini_analytics_hot_products_api():
    """Hot product ranking for the mini-program home page and dashboards."""
    try:
        data = _analytics_hot_products_payload(_mini_request_payload())
        return jsonify({
            "code": 0,
            "data": {
                **data,
                "cart_total": _mini_empty_cart_total(),
            },
        })
    except Exception as e:
        logger.error(f"小程序热销商品查询异常: {e}")
        return _api_exception_response(e)


@app.route("/api/sales/cards", methods=["GET"])
def sales_cards():
    """
    Sales cards for the UniApp mini-program.
    GET /api/sales/cards?page=1&page_size=10&keyword=xxx&status=5
    """
    from src.core.tools.caller import get_tool_caller
    caller = get_tool_caller()
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 10, type=int)
    keyword = _normalize_inventory_keyword((request.args.get("keyword", "") or "").strip())
    status_arg = request.args.get("status", "")
    pay_status = (request.args.get("pay_status", "") or "").strip()
    date_from = (request.args.get("date_from", "") or "").strip()
    date_to = (request.args.get("date_to", "") or "").strip()
    page = max(1, page)
    page_size = max(1, min(page_size, 100))
    status_filter = "active"
    status = None
    if status_arg in ("active", "deleted"):
        status_filter = status_arg
    elif status_arg not in ("", None):
        status = int(status_arg)

    try:
        cards, total = _db_sales_cards(
            keyword,
            page,
            page_size,
            status,
            status_filter=status_filter,
            pay_status=pay_status,
            date_from=date_from,
            date_to=date_to,
        )
        return jsonify({
            "code": 0,
            "data": {
                "page": page,
                "page_size": page_size,
                "list": cards,
                "total": total,
                "source": "db",
            }
        })
    except Exception as e:
        logger.warning(f"销售单数据库查询失败，回退 API: {e}")

    try:
        fetch_size = min(120, max(page_size, 50 if keyword else page_size))
        result = caller.call(
            "sales_list",
            keyword=keyword if keyword and keyword.upper().startswith("S") else None,
            status=status,
            page=page,
            page_size=fetch_size,
        )
        rows = _extract_list_rows(result)
        customer_cache = {}
        cards = [_sales_card(caller, row, customer_cache) for row in rows]
        if keyword:
            lower = keyword.lower()
            cards = [
                card for card in cards
                if lower in str(card.get("sales_no", "")).lower()
                or lower in str(card.get("customer_name", "")).lower()
                or lower in str(card.get("product_summary", "")).lower()
                or any(lower in str(p.get("title", "") + " " + p.get("spec", "")).lower() for p in card.get("products", []))
            ]
        result_data = result.get("data", {}) if isinstance(result, dict) else {}
        if not isinstance(result_data, dict):
            result_data = {}
        return jsonify({
            "code": 0,
            "data": {
                "page": page,
                "page_size": page_size,
                "list": cards[:page_size],
                "total": result_data.get("total", len(cards)),
            }
        })
    except Exception as e:
        logger.error(f"销售单卡片查询失败: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/settings/print/sales", methods=["GET"])
def sales_print_settings_api():
    """Sales-order print settings stored in sjagent_core."""
    try:
        return jsonify(get_settings_service().sales_print_settings())
    except Exception as e:
        logger.error(f"sales print settings failed: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/settings/number/sku", methods=["GET"])
def sku_number_settings_api():
    """Product SKU number settings stored in sjagent_core."""
    try:
        return jsonify(get_settings_service().sku_number_settings())
    except Exception as e:
        logger.error(f"sku number settings failed: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/settings/number/sku", methods=["POST"])
def sku_number_settings_save_api():
    """Update the future product SKU number rule without touching history."""
    try:
        payload = request.get_json(silent=True) or {}
        user = _current_web_user() or {}
        operator_user_id = user.get("native_user_id") or user.get("id")
        result = get_settings_service().save_sku_number_settings(payload, operator_user_id=operator_user_id)
        if isinstance(result, dict) and result.get("code") not in (None, 0):
            return jsonify(result), 400
        return jsonify(result if isinstance(result, dict) else {"code": 0, "data": result})
    except Exception as e:
        logger.error(f"sku number settings save failed: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/settings/system/<setting_key>", methods=["GET", "POST"])
def system_setting_api(setting_key: str):
    """Native system settings: product, inventory, payment, image, permission rules."""
    clean_key = str(setting_key or "").strip()
    try:
        if request.method == "GET":
            return jsonify(get_settings_service().get(clean_key))
        payload = request.get_json(silent=True) or {}
        user = _current_web_user() or {}
        operator_user_id = user.get("native_user_id") or user.get("id")
        result = get_settings_service().save(clean_key, payload, operator_user_id=operator_user_id)
        if isinstance(result, dict) and result.get("code") not in (None, 0):
            return jsonify(result), 400
        return jsonify(result if isinstance(result, dict) else {"code": 0, "data": result})
    except Exception as e:
        logger.error(f"system setting failed: key={clean_key}, error={e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/settings/print/sales", methods=["POST"])
def sales_print_settings_save_api():
    """Update the default sales-order print template."""
    try:
        payload = request.get_json(silent=True) or {}
        result = get_settings_service().save_sales_print_settings(payload)
        if isinstance(result, dict) and result.get("code") not in (None, 0):
            return jsonify(result), 400
        return jsonify(result if isinstance(result, dict) else {"code": 0, "data": result})
    except Exception as e:
        logger.error(f"sales print settings save failed: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/sales/<int:sales_id>/print-task", methods=["POST"])
def sales_print_task_api(sales_id: int):
    """Create a native print task for a sales order without ERP."""
    if sales_id <= 0:
        return jsonify({"code": 400, "msg": "sales_id is required"}), 400
    try:
        payload = request.get_json(silent=True) or {}
        user = _current_web_user() or {}
        operator_user_id = user.get("native_user_id") or user.get("id")
        result = get_sales_service().create_print_task(
            sales_id=sales_id,
            template_id=payload.get("template_id"),
            operator_user_id=operator_user_id,
        )
        if isinstance(result, dict):
            if result.get("error"):
                return jsonify({"code": 500, "msg": result.get("error")}), 500
            result_code = result.get("code")
            if result_code not in (None, 0, "0"):
                msg = result.get("msg") or result.get("message") or "打印任务创建失败"
                return jsonify({"code": result_code, "msg": msg, "data": result}), 500
        return jsonify(result if isinstance(result, dict) and "code" in result else {"code": 0, "data": result})
    except Exception as e:
        logger.error(f"sales print task failed: sales_id={sales_id}, error={e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/print-agent/sales/tasks", methods=["GET"])
@app.route("/api/print-agent/sales/task-list", methods=["GET"])
def print_agent_sales_task_list_api():
    """Pending native sales print tasks for the local print helper."""
    if not _print_agent_authorized():
        return _print_agent_required_response()
    try:
        page = max(1, int(request.args.get("page", 1) or 1))
        page_size = max(1, min(int(request.args.get("page_size", 50) or 50), 200))
        result = get_sales_service().print_task_list(page=page, page_size=page_size)
        data = result.get("data") if isinstance(result, dict) else {}
        rows = data.get("list") if isinstance(data, dict) else []
        for row in rows or []:
            task_id = row.get("task_id") or row.get("id")
            if task_id:
                row["html_url"] = f"/api/print-agent/sales/tasks/{int(task_id)}/html"
                row["done_url"] = f"/api/print-agent/sales/tasks/{int(task_id)}/done"
        return jsonify(result)
    except Exception as e:
        logger.error(f"print agent sales task list failed: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/print-agent/sales/tasks/<int:task_id>", methods=["GET"])
def print_agent_sales_task_detail_api(task_id: int):
    """One native print task for local print helpers."""
    if not _print_agent_authorized():
        return _print_agent_required_response()
    row = _print_job_row(task_id)
    if not row:
        return jsonify({"code": 404, "msg": "打印任务不存在"}), 404
    return jsonify({
        "code": 0,
        "data": {
            "id": row.get("id"),
            "task_id": row.get("id"),
            "job_no": row.get("job_no") or "",
            "sales_id": row.get("document_id"),
            "sales_no": row.get("sales_no") or "",
            "customer_name": row.get("customer_name_snapshot") or "",
            "status": row.get("status") or "",
            "copies": int(row.get("copies") or 1),
            "html_url": f"/api/print-agent/sales/tasks/{int(row.get('id'))}/html",
            "done_url": f"/api/print-agent/sales/tasks/{int(row.get('id'))}/done",
            "created_at": str(row.get("created_at") or ""),
        },
    })


@app.route("/api/print-agent/sales/tasks/<int:task_id>/html", methods=["GET"])
def print_agent_sales_task_html_api(task_id: int):
    """Printable sales HTML for local print helpers without a WebUI session."""
    if not _print_agent_authorized():
        return Response("print agent token required", status=401, mimetype="text/plain")
    row = _print_job_row(task_id)
    if not row:
        return Response("打印任务不存在", status=404, mimetype="text/plain")
    try:
        auto_print = request.args.get("auto", "0") in ("1", "true", "True")
        html = get_sales_service().sales_print_html(int(row.get("document_id")), auto_print=auto_print)
        return Response(html, mimetype="text/html")
    except Exception as e:
        logger.error(f"print agent sales task html failed: task_id={task_id}, error={e}")
        return Response(f"打印页面打开失败：{e}", status=500, mimetype="text/plain")


@app.route("/api/print-agent/sales/tasks/<int:task_id>/done", methods=["POST"])
@app.route("/api/print-agent/sales/task-done", methods=["POST"])
def print_agent_sales_task_done_api(task_id: int | None = None):
    """Mark a native sales print task as printed."""
    if not _print_agent_authorized():
        return _print_agent_required_response()
    payload = request.get_json(silent=True) or {}
    resolved_id = task_id or payload.get("task_id") or request.values.get("task_id")
    if not resolved_id:
        return jsonify({"code": 400, "msg": "task_id is required"}), 400
    try:
        result = get_sales_service().print_task_done(int(resolved_id))
        status_code = 404 if isinstance(result, dict) and result.get("code") == 404 else 200
        return jsonify(result), status_code
    except Exception as e:
        logger.error(f"print agent sales task done failed: task_id={resolved_id}, error={e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/print-agent/sales/tasks/<int:task_id>/fail", methods=["POST"])
def print_agent_sales_task_fail_api(task_id: int):
    """Mark a native sales print task as failed so it can be retried intentionally."""
    if not _print_agent_authorized():
        return _print_agent_required_response()
    payload = request.get_json(silent=True) or {}
    reason = str(payload.get("reason") or request.values.get("reason") or "print failed")[:200]
    row = _print_job_row(task_id)
    if not row:
        return jsonify({"code": 404, "msg": "打印任务不存在"}), 404
    try:
        result = get_sales_service().print_task_failed(
            int(task_id),
            sales_id=int(row.get("document_id") or 0),
            reason=reason,
        )
        return jsonify(result)
    except Exception as e:
        logger.error(f"print agent sales task fail failed: task_id={task_id}, error={e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/sales/<int:sales_id>/print-html", methods=["GET"])
def sales_print_html_api(sales_id: int):
    """Open native printable sales-order HTML directly."""
    if sales_id <= 0:
        return Response("sales_id is required", status=400, mimetype="text/plain")
    try:
        auto_print = request.args.get("auto", "1") not in ("0", "false", "False")
        show_actions = request.args.get("chrome", "1") not in ("0", "false", "False")
        html = get_sales_service().sales_print_html(
            sales_id,
            auto_print=auto_print,
            show_actions=show_actions,
        )
        return Response(html, mimetype="text/html")
    except Exception as e:
        logger.error(f"sales print html failed: sales_id={sales_id}, error={e}")
        return Response(f"打印页面打开失败：{e}", status=500, mimetype="text/plain")


@app.route("/api/sales/<int:sales_id>/detail", methods=["GET"])
def sales_detail_api(sales_id: int):
    """Sales order bill details backed by sjagent_core."""
    if sales_id <= 0:
        return jsonify({"code": 400, "msg": "sales_id is required"}), 400
    try:
        result = get_sales_service().detail(sales_id)
        status_code = 404 if isinstance(result, dict) and result.get("code") == 404 else 200
        return jsonify(result), status_code
    except Exception as e:
        logger.error(f"sales detail failed: sales_id={sales_id}, error={e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/sales/<int:sales_id>", methods=["DELETE"])
def sales_delete_api(sales_id: int):
    """Soft-delete a sales order in sjagent_core and rollback native inventory ledgers."""
    if sales_id <= 0:
        return jsonify({"code": 400, "msg": "sales_id is required"}), 400
    try:
        user = _current_web_user() or {}
        operator_user_id = user.get("native_user_id") or user.get("id")
        result = get_sales_service().delete_order(sales_id, operator_user_id=operator_user_id)
        if isinstance(result, dict) and result.get("code") not in (None, 0):
            return jsonify(result), 400 if int(result.get("code") or 0) == 400 else 500
        return jsonify(result if isinstance(result, dict) else {"code": 0, "data": result})
    except Exception as e:
        logger.error(f"sales delete failed: sales_id={sales_id}, error={e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/inventory/cards", methods=["GET"])
def inventory_cards():
    """
    Inventory cards for the UniApp mini-program.
    GET /api/inventory/cards?keyword=岩味&only_in_stock=1&limit=30
    """
    keyword = _normalize_inventory_keyword((request.args.get("keyword", "") or "").strip())
    only_in_stock = request.args.get("only_in_stock", "1") not in ("0", "false", "False")
    limit = request.args.get("limit", 30, type=int)
    limit = max(1, min(limit, 200))
    try:
        product_rows = []
        if not only_in_stock:
            try:
                product_rows, _ = get_product_service().list(
                    keyword=keyword,
                    page=1,
                    page_size=max(limit * 30, 1200),
                    group=False,
                )
            except Exception as product_error:
                logger.warning(f"native product rows for zero-stock inventory failed: {product_error}")
        rows = get_inventory_service().search(
            keyword=keyword,
            only_in_stock=only_in_stock,
            limit=max(limit * 30, 1200),
        )
        cards = _inventory_cards(
            rows if isinstance(rows, list) else [],
            limit,
            only_in_stock=only_in_stock,
            product_rows=product_rows,
        )
        return jsonify({
            "code": 0,
            "data": {
                "list": cards,
                "source": "db",
            }
        })
    except Exception as e:
        logger.warning(f"库存数据库查询失败，回退 API: {e}")
        try:
            from src.core.tools.caller import get_tool_caller
            caller = get_tool_caller()
            rows = caller.call(
                "inventory_search",
                keyword=keyword,
                only_in_stock=only_in_stock,
                limit=max(limit * 30, 1200),
            )
            product_rows = []
            if not only_in_stock:
                try:
                    product_rows = caller.call("product_search", keyword=keyword) or []
                except Exception as product_error:
                    logger.warning(f"库存卡片商品颜色补充失败: {product_error}")
            cards = _inventory_cards(
                rows if isinstance(rows, list) else [],
                limit,
                only_in_stock=only_in_stock,
                product_rows=product_rows if isinstance(product_rows, list) else [],
            )
            return jsonify({"code": 0, "data": {"list": cards, "source": "api"}})
        except Exception as api_error:
            logger.error(f"库存卡片查询失败: {api_error}")
            return jsonify({"code": 500, "msg": str(api_error)}), 500


@app.route("/api/product/color-options", methods=["GET"])
def product_color_options():
    """Return all color/spec options for the same gift-box product series."""
    from src.core.tools.caller import get_tool_caller
    caller = get_tool_caller()
    title = (request.args.get("title", "") or "").strip()
    if not title:
        return jsonify({"code": 400, "msg": "title is required"}), 400
    try:
        card = {"title": title, "colors": []}
        product_rows = _load_product_color_options(caller, card)
        _merge_product_color_options(card, product_rows)
        return jsonify({
            "code": 0,
            "data": {
                "title": title,
                "series": _product_series_keyword(title),
                "colors": card.get("colors", []),
            }
        })
    except Exception as e:
        logger.error(f"商品颜色选项查询失败: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


def _inventory_action_response(result):
    """Normalize InventoryService action results for React admin."""
    if isinstance(result, dict):
        if result.get("error"):
            return jsonify({"code": 500, "msg": str(result.get("error"))}), 500
        code = int(result.get("code") or 0)
        if code != 0:
            status = 400 if code < 500 else 500
            return jsonify({"code": code, "msg": result.get("msg") or "库存操作失败"}), status
        data = result.get("data") if "data" in result else result
        return jsonify({"code": 0, "data": _safe_json(data)})
    return jsonify({"code": 0, "data": _safe_json(result)})


@app.route("/api/inventory/transfer", methods=["POST"])
def inventory_transfer_api():
    """Transfer inventory between warehouses for the UniApp inventory page."""
    body = request.get_json() or {}
    product_id = body.get("product_id")
    quantity = body.get("quantity")
    color = (body.get("color") or "").strip()
    out_warehouse_id = int(body.get("out_warehouse_id") or body.get("from_warehouse_id") or 2)
    enter_warehouse_id = int(body.get("enter_warehouse_id") or body.get("to_warehouse_id") or 1)
    if not product_id:
        return jsonify({"code": 400, "msg": "product_id is required"}), 400
    try:
        quantity = int(quantity or 0)
    except (TypeError, ValueError):
        quantity = 0
    if quantity <= 0:
        return jsonify({"code": 400, "msg": "quantity must be greater than 0"}), 400
    if out_warehouse_id == enter_warehouse_id:
        return jsonify({"code": 400, "msg": "调出仓库和调入仓库不能相同"}), 400
    try:
        user = _current_web_user() or {}
        operator_user_id = user.get("native_user_id") or user.get("id")
        result = get_inventory_service().create_transfer(
            out_warehouse_id=out_warehouse_id,
            enter_warehouse_id=enter_warehouse_id,
            products=[{
                "product_id": int(product_id),
                "unit_id": int(body.get("unit_id") or 1),
                "transfer_number": quantity,
            }],
            note=(body.get("note") or f"小程序调货{f'（{color}）' if color else ''}").strip(),
            operator_user_id=operator_user_id,
        )
        return _inventory_action_response(result)
    except Exception as e:
        logger.error(f"库存调货失败: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/inventory/purchase", methods=["POST"])
def inventory_purchase_api():
    """Create an inventory inbound record for the UniApp inventory page."""
    body = request.get_json() or {}
    product_id = body.get("product_id")
    quantity = body.get("quantity")
    color = (body.get("color") or "").strip()
    warehouse_id = int(body.get("warehouse_id") or 2)
    if not product_id:
        return jsonify({"code": 400, "msg": "product_id is required"}), 400
    try:
        quantity = int(quantity or 0)
    except (TypeError, ValueError):
        quantity = 0
    if quantity <= 0:
        return jsonify({"code": 400, "msg": "quantity must be greater than 0"}), 400
    try:
        user = _current_web_user() or {}
        operator_user_id = user.get("native_user_id") or user.get("id")
        result = get_inventory_service().create_stock_in(
            warehouse_id=warehouse_id,
            products=[{
                "product_id": int(product_id),
                "unit_id": int(body.get("unit_id") or 1),
                "buy_number": quantity,
            }],
            note=(body.get("note") or f"小程序进货{f'（{color}）' if color else ''}").strip(),
            operator_user_id=operator_user_id,
        )
        return _inventory_action_response(result)
    except Exception as e:
        logger.error(f"库存进货失败: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/inventory/stocktaking", methods=["POST"])
def inventory_stocktaking_api():
    """Set target inventory for one product in one warehouse."""
    body = request.get_json() or {}
    product_id = body.get("product_id")
    quantity = body.get("quantity")
    color = (body.get("color") or "").strip()
    warehouse_id = int(body.get("warehouse_id") or 2)
    if not product_id:
        return jsonify({"code": 400, "msg": "product_id is required"}), 400
    try:
        quantity = int(quantity or 0)
    except (TypeError, ValueError):
        quantity = -1
    if quantity < 0:
        return jsonify({"code": 400, "msg": "quantity must be greater than or equal to 0"}), 400
    try:
        user = _current_web_user() or {}
        operator_user_id = user.get("native_user_id") or user.get("id")
        result = get_inventory_service().create_stocktake(
            warehouse_id=warehouse_id,
            products=[{
                "product_id": int(product_id),
                "unit_id": int(body.get("unit_id") or 1),
                "number": quantity,
            }],
            note=(body.get("note") or f"WebUI盘点{f'（{color}）' if color else ''}").strip(),
            operator_user_id=operator_user_id,
        )
        return _inventory_action_response(result)
    except Exception as e:
        logger.error(f"库存盘点失败: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/workflow/orders", methods=["GET", "POST"])
def workflow_orders():
    """
    GET  /api/workflow/orders?page=1&page_size=10&keyword=xxx
    POST /api/workflow/orders
    """
    from src.core.tools.caller import get_tool_caller
    caller = get_tool_caller()
    if request.method == "GET":
        keyword = (request.args.get("keyword", "") or "").strip()
        status_filter = (request.args.get("filter", "active") or "active").strip()
        page = max(1, request.args.get("page", 1, type=int))
        page_size = max(1, min(request.args.get("page_size", 10, type=int), 120))
        try:
            cards, total = _db_workflow_orders(keyword, page, page_size, status_filter)
            return jsonify({
                "code": 0,
                "data": {
                    "page": page,
                    "page_size": page_size,
                    "total": total,
                    "list": cards,
                    "source": "db",
                }
            })
        except Exception as e:
            logger.warning(f"工作流订单数据库查询失败，回退 API: {e}")
        try:
            result = caller.call("workflow_order_list", keyword=keyword or None, page=page, page_size=page_size)
            data = result.get("data", {}) if isinstance(result, dict) else {}
            rows = data.get("list") or []
            return jsonify({
                "code": 0,
                "data": {
                    "page": data.get("page", page) if isinstance(data, dict) else page,
                    "page_size": data.get("page_size", page_size) if isinstance(data, dict) else page_size,
                    "total": data.get("total", len(rows)) if isinstance(data, dict) else len(rows),
                    "list": [_workflow_card(row) for row in rows],
                }
            })
        except Exception as e:
            logger.error(f"工作流订单查询失败: {e}")
            return jsonify({"code": 500, "msg": str(e)}), 500

    body = request.get_json() or {}
    customer_name = (body.get("customer_name") or "").strip()
    goods_name = (body.get("goods_name") or "").strip()
    if not customer_name:
        return jsonify({"code": 400, "msg": "customer_name is required"}), 400
    if not goods_name:
        return jsonify({"code": 400, "msg": "goods_name is required"}), 400
    try:
        order_images_provided = "order_images" in body
        order_images = body.get("order_images") if order_images_provided else []
        if isinstance(order_images, str):
            try:
                parsed_images = json.loads(order_images)
                order_images = parsed_images if isinstance(parsed_images, list) else ([parsed_images] if parsed_images else [])
            except Exception:
                order_images = [part.strip() for part in order_images.split(",") if part.strip()]
        elif not isinstance(order_images, list):
            order_images = []
        order_images = [str(url).strip() for url in order_images if str(url or "").strip()]

        result = get_workflow_service().save_order(
            order_id=body.get("id"),
            customer_name=customer_name,
            customer_phone=(body.get("customer_phone") or "").strip(),
            goods_name=goods_name,
            color=(body.get("goods_color") or body.get("color") or "").strip(),
            order_quantity=int(body.get("order_quantity") or 0),
            is_screen_print=int(body.get("is_screen_print") or 0),
            order_type=int(body.get("order_type") or 0),
            order_images=order_images,
            remark=(body.get("remark") or "").strip(),
        )
        if isinstance(result, dict) and result.get("code", 0) != 0:
            return jsonify({"code": result.get("code", 500), "msg": result.get("msg", "保存失败")}), 400
        return jsonify({"code": 0, "data": result.get("data", result) if isinstance(result, dict) else result})
    except Exception as e:
        logger.error(f"工作流订单保存失败: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/workflow/orders/<int:order_id>/status", methods=["POST"])
def workflow_order_status(order_id: int):
    """Update workflow order status fields."""
    body = request.get_json() or {}
    field = body.get("field")
    value = body.get("value")
    if field not in ("is_made", "is_delivered", "order_type"):
        return jsonify({"code": 400, "msg": "field is invalid"}), 400
    try:
        result = get_workflow_service().update_status(order_id=order_id, field=field, value=int(value or 0))
        if isinstance(result, dict) and result.get("code", 0) != 0:
            return jsonify({"code": result.get("code", 500), "msg": result.get("msg", "操作失败")}), 400
        return jsonify({"code": 0, "data": result.get("data", result) if isinstance(result, dict) else result})
    except Exception as e:
        logger.error(f"工作流订单状态更新失败: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/workflow/orders/<int:order_id>", methods=["DELETE"])
def workflow_order_delete_api(order_id: int):
    """Delete one workflow order."""
    try:
        result = get_workflow_service().delete_orders(str(order_id))
        if isinstance(result, dict) and result.get("code", 0) != 0:
            return jsonify({"code": result.get("code", 500), "msg": result.get("msg", "删除失败")}), 400
        return jsonify({"code": 0, "data": result.get("data", result) if isinstance(result, dict) else result})
    except Exception as e:
        logger.error(f"工作流订单删除失败: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/inventory/query", methods=["GET"])
def inventory_query():
    """
    库存查询接口
    GET /api/inventory/query?product_id=123
    GET /api/inventory/query?keyword=喜悦
    GET /api/inventory/query?warehouse_id=2
    """
    product_id = request.args.get("product_id")
    keyword = _normalize_inventory_keyword(request.args.get("keyword") or "")
    warehouse_id = request.args.get("warehouse_id")

    try:
        if product_id:
            results = get_inventory_service().product_inventory(int(product_id))
        elif keyword:
            # 先搜索商品，再查库存
            products = get_product_service().search(keyword)
            results = []
            for p in products[:5]:
                inv = get_inventory_service().product_inventory(int(p["id"]))
                results.extend(inv)
        elif warehouse_id:
            results = get_inventory_service().warehouse_inventory(int(warehouse_id))
        else:
            return jsonify({"code": 400, "msg": "product_id/keyword/warehouse_id 至少传一个"}), 400

        return jsonify({"code": 0, "data": results})
    except Exception as e:
        logger.error(f"库存查询异常: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/product/search", methods=["GET"])
def product_search():
    """
    商品搜索接口
    GET /api/product/search?keyword=喜悦
    """
    keyword = normalize_product_name(request.args.get("keyword", ""), specs=PRODUCT_SPECS)
    if not keyword:
        return jsonify({"code": 400, "msg": "keyword is required"}), 400
    listed_only = _request_truthy_arg("listed_only", "only_listed", "is_listed")

    try:
        results = get_product_service().search(keyword, limit=100, listed_only=listed_only)
        return jsonify({"code": 0, "data": results[:100], "source": "db"})
    except Exception as e:
        logger.error(f"商品自有库搜索异常: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/product/list", methods=["GET"])
def product_list():
    """商品管理列表，优先走 MySQL 直查，写操作仍走 API。"""
    keyword = normalize_product_name(request.args.get("keyword") or "", specs=PRODUCT_SPECS)
    page = request.args.get("page", default=1, type=int)
    page_size = max(1, min(request.args.get("page_size", default=20, type=int), 200))
    status = request.args.get("status", type=int) if request.args.get("status") not in (None, "") else None
    category_id = request.args.get("category_id", type=int) or None
    category_ids = [
        int(item)
        for item in (request.args.get("category_ids") or "").split(",")
        if item.strip().isdigit()
    ]
    product_type = str(request.args.get("product_type") or "").strip()
    listed_state = str(request.args.get("listed_state") or "").strip()
    listed_only = _request_truthy_arg("listed_only", "only_listed", "is_listed")
    stock_mode = str(request.args.get("stock_mode") or "").strip()
    quality = str(request.args.get("quality") or "").strip()
    group = request.args.get("group", default=1, type=int) == 1

    try:
        items, total = _db_product_list(
            keyword,
            max(1, page),
            page_size,
            status,
            category_id,
            group,
            category_ids=category_ids,
            product_type=product_type,
            listed_only=listed_only,
            listed_state=listed_state,
            stock_mode=stock_mode,
            quality=quality,
        )
        return jsonify({
            "code": 0,
            "data": {
                "page": max(1, page),
                "page_size": page_size,
                "total": total,
                "list": items,
                "source": "db",
            }
        })
    except Exception as e:
        logger.error(f"商品自有库列表异常: {e}")
        return _api_exception_response(e)


@app.route("/api/product/categories", methods=["GET", "POST", "PATCH"])
def product_categories():
    """商品分类。"""
    try:
        if request.method in {"POST", "PATCH"}:
            body = request.get_json(silent=True) or {}
            user = _current_web_user() or {}
            operator_user_id = user.get("native_user_id") or user.get("id")
            result = get_product_service().save_category(body, operator_user_id=operator_user_id)
            if isinstance(result, dict) and result.get("code") not in (None, 0):
                return jsonify(result), 400
            return jsonify(result if isinstance(result, dict) else {"code": 0, "data": result})
        categories = _db_product_categories()
        _, total = get_product_service().list(page=1, page_size=1, group=True)
        return jsonify({
            "code": 0,
            "data": {
                "list": [{"id": "", "name": "全部产品", "total": total}] + categories,
                "total": total,
                "source": "db",
            },
        })
    except Exception as e:
        logger.error(f"商品分类查询异常: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


def _mini_home_design_payload() -> dict:
    return get_miniapp_service().design_payload()


def _mini_home_first_items(modules: list[dict], module_type: str) -> list[dict]:
    for module in modules:
        if not isinstance(module, dict):
            continue
        if module.get("type") != module_type or int(module.get("enabled") or 0) != 1:
            continue
        items = module.get("items")
        return items if isinstance(items, list) else []
    return []


def _mini_home_products_for_shelf(module: dict) -> list[dict]:
    items = get_miniapp_service().product_shelf_items(module)
    return [_mini_product_payload(item, list_item=True) for item in items]


@app.route("/api/miniapp/config", methods=["GET", "POST"])
def miniapp_config_api():
    """Database-backed mini-program visual/link configuration."""
    try:
        return jsonify({"code": 0, "data": get_miniapp_service().config_payload()})
    except Exception as e:
        logger.error(f"小程序配置数据异常: {e}")
        return _api_exception_response(e)


@app.route("/api/miniapp/image-config", methods=["GET"])
def miniapp_image_config_api():
    """WebUI editor payload for mini-program images."""
    try:
        return jsonify({"code": 0, "data": get_miniapp_service().image_config_payload()})
    except Exception as e:
        logger.error(f"小程序图片配置加载异常: {e}")
        return _api_exception_response(e)


@app.route("/api/miniapp/image-config", methods=["POST", "PATCH"])
def miniapp_image_config_update_api():
    """Update mini-program image URLs from WebUI."""
    try:
        body = request.get_json(silent=True)
        if body is None:
            body = request.form.to_dict(flat=True)
        result = get_miniapp_service().update_image_config(body or {})
        status = 200 if int(result.get("code") or 0) == 0 else int(result.get("code") or 400)
        return jsonify(result), status
    except Exception as e:
        logger.error(f"小程序图片配置保存异常: {e}")
        return _api_exception_response(e)


@app.route("/api/mini/home", methods=["GET", "POST"])
def mini_home_api():
    """Mini-program home data backed by sjagent_core."""
    try:
        design = _mini_home_design_payload()
        home = design.get("home") if isinstance(design.get("home"), dict) else {}
        modules = home.get("modules") if isinstance(home.get("modules"), list) else []
        first_products: list[dict] = []
        prepared_modules: list[dict] = []
        for module in modules:
            if not isinstance(module, dict):
                continue
            prepared = dict(module)
            if prepared.get("type") == "product_shelf" and int(prepared.get("enabled") or 0) == 1:
                prepared["products"] = _mini_home_products_for_shelf(prepared)
                if not first_products:
                    first_products = prepared["products"]
            prepared_modules.append(prepared)
        if not first_products:
            items, _total = _db_product_list("", 1, 8, status=0, group=True, listed_only=True)
            first_products = [_mini_product_payload(item, list_item=True) for item in items]
        design["home"] = {**home, "modules": prepared_modules}
        tabbar = design.get("tabbar") if isinstance(design.get("tabbar"), dict) else {}
        banners = _mini_home_first_items(prepared_modules, "banner")
        navs = _mini_home_first_items(prepared_modules, "nav")
        return jsonify({
            "code": 0,
            "data": {
                "design": design,
                "tabbar": tabbar,
                "banners": banners,
                "banner_list": banners,
                "navs": navs,
                "navigation": navs,
                "products": first_products,
                "data_mode": 0,
                "data_list": design,
                "article_list": [],
                "right_icon_list": [],
                "message_total": 0,
                "cart_total": _mini_empty_cart_total(),
                "source": "sjagent_core",
            },
        })
    except Exception as e:
        logger.error(f"小程序首页数据异常: {e}")
        return _api_exception_response(e)


@app.route("/api/mini/user/center", methods=["GET", "POST"])
def mini_user_center_api():
    """Mini-program user center data backed by native auth and order-flow data."""
    token = _auth_token_from_request()
    user = None
    if token:
        try:
            user = _verify_native_token(token)
        except Exception as e:
            logger.warning(f"mini user center token verify failed: {e}")

    return jsonify({"code": 0, "data": get_miniapp_service().user_center_payload(user=user)})


@app.route("/api/mini/customer/summary", methods=["GET"])
def mini_customer_summary_api():
    """Bound customer balance and recent workflow orders for the mini-program My page."""
    user = _mini_request_user()
    if not user:
        return jsonify({"code": 401, "msg": "请先登录账号"}), 401
    try:
        return jsonify({"code": 0, "data": _safe_json(get_miniapp_service().customer_summary(user))})
    except Exception as e:
        logger.error(f"mini customer summary failed: {e}")
        return _api_exception_response(e)


@app.route("/api/mini/cart/empty", methods=["GET", "POST"])
def mini_cart_empty_api():
    """Compatibility endpoint for removed cart reads."""
    return jsonify({
        "code": 0,
        "data": {
            "buy_number": 0,
            "data": [],
            "source": "sjagent_core",
            "disabled": True,
            "reason": "new mini-program does not use cart",
        },
    })


@app.route("/api/mini/disabled", methods=["GET", "POST"])
def mini_disabled_api():
    """Explicitly stop removed ShopXO mall functions from falling back."""
    payload = _mini_request_payload()
    feature = str(_mini_value(payload, "feature", "route", default="")).strip()
    return jsonify({
        "code": 410,
        "msg": "该功能已停用，新小程序不再使用购物车、支付或旧商城订单。",
        "data": {
            "feature": feature,
            "source": "sjagent_core",
            "disabled": True,
        },
    }), 410


@app.route("/api/mini/goods/category", methods=["GET", "POST"])
def mini_goods_category_api():
    """ShopXO uni-app compatible category data backed by sjagent_core."""
    try:
        categories = _db_product_categories(
            listed_only=True,
            exclude_names=MINIAPP_EXCLUDED_CATEGORY_NAMES,
        )
        return jsonify({
            "code": 0,
            "data": {
                "category": _mini_category_tree(categories),
                "plugins_label_data": None,
                "source": "sjagent_core",
            },
        })
    except Exception as e:
        logger.error(f"小程序商品分类查询异常: {e}")
        return _api_exception_response(e)


@app.route("/api/mini/search/index", methods=["GET", "POST"])
def mini_search_index_api():
    """ShopXO uni-app compatible search metadata backed by sjagent_core."""
    try:
        categories = _mini_category_tree(_db_product_categories(
            listed_only=True,
            exclude_names=MINIAPP_EXCLUDED_CATEGORY_NAMES,
        ))
        return jsonify({
            "code": 0,
            "data": {
                "search_map_info": [],
                "brand_list": [],
                "category_list": categories,
                "screening_price_list": [],
                "goods_produce_region_list": [],
                "goods_params_list": [],
                "goods_spec_list": [],
                "cart_total": _mini_empty_cart_total(),
                "plugins_label_data": None,
                "source": "sjagent_core",
            },
        })
    except Exception as e:
        logger.error(f"小程序商品搜索初始化异常: {e}")
        return _api_exception_response(e)


@app.route("/api/mini/search/datalist", methods=["GET", "POST"])
def mini_search_datalist_api():
    """ShopXO uni-app compatible product list backed by sjagent_core."""
    payload = _mini_request_payload()
    keyword = normalize_product_name(
        str(_mini_value(payload, "wd", "keyword", "keywords", "q", default="")),
        specs=PRODUCT_SPECS,
    )
    page, page_size = _mini_page_payload(payload)
    category_id = _mini_category_id(payload)
    sort = str(_mini_value(payload, "sort", "order_by", default="")).strip()

    try:
        items, total = _db_product_list(
            keyword,
            page,
            page_size,
            status=0,
            category_id=category_id,
            group=True,
            listed_only=True,
            sort=sort,
        )
        return jsonify({"code": 0, "data": _mini_product_page_data(items, total, page, page_size)})
    except Exception as e:
        logger.error(f"小程序商品列表查询异常: {e}")
        return _api_exception_response(e)


@app.route("/api/mini/goods/detail", methods=["GET", "POST"])
def mini_goods_detail_api():
    """ShopXO uni-app compatible product detail backed by sjagent_core."""
    payload = _mini_request_payload()
    product_id = _mini_int(_mini_value(payload, "id", "goods_id", "product_id", default=0), 0)
    if not product_id:
        return jsonify({"code": 400, "msg": "id is required"}), 400

    try:
        product = get_product_service().info(product_id, listed_only=True)
        if not product:
            return jsonify({"code": 404, "msg": "商品已下架或不存在"}), 404
        goods = _mini_product_payload(product, list_item=False)
        return jsonify({
            "code": 0,
            "data": {
                "goods": goods,
                "guess_you_like": [],
                "nav_more_list": [],
                "buy_button": {"is_buy": 0, "is_cart": 0, "is_show": 0},
                "buy_left_nav": [],
                "middle_tabs_nav": [],
                "cart_total": _mini_empty_cart_total(),
                "plugins_label_data": None,
                "plugins_seckill_data": None,
                "plugins_coupon_data": None,
                "plugins_salerecords_data": None,
                "plugins_shop_data": None,
                "plugins_wholesale_data": None,
                "plugins_intellectstools_data": None,
                "plugins_realstore_data": None,
                "plugins_binding_data": None,
                "plugins_goodsservice_data": None,
                "plugins_batchbuy_data": None,
                "plugins_ask_data": None,
                "plugins_categorylimit_data": None,
                "source": "sjagent_core",
            },
        })
    except Exception as e:
        logger.error(f"小程序商品详情查询异常: {e}")
        return _api_exception_response(e)


@app.route("/api/mini/orderflow/list", methods=["GET", "POST"])
def mini_orderflow_list_api():
    """Mini-program order flow backed by existing workflow and sales order data."""
    payload = _mini_request_payload()
    keyword = str(_mini_value(payload, "keyword", "wd", "q", default="")).strip()
    page, page_size = _mini_page_payload(payload)
    user = _mini_request_user()
    customer_id = _mini_order_customer_id(user)

    if not _mini_orderflow_should_query(keyword, user):
        return jsonify({"code": 0, "data": _mini_orderflow_empty_payload(page, page_size)})

    workflows = []
    workflow_total = 0
    sales = []
    sales_total = 0

    try:
        workflows, workflow_total = _db_workflow_orders(keyword, page, page_size, "active", customer_id=customer_id if not keyword else None)
    except Exception as e:
        logger.warning(f"mini orderflow workflow query failed: {e}")

    try:
        sales, sales_total = _db_sales_cards(keyword, page, page_size, None, customer_id=customer_id if not keyword else None)
    except Exception as e:
        logger.warning(f"mini orderflow sales query failed: {e}")

    return jsonify({
        "code": 0,
        "data": {
            "page": page,
            "page_size": page_size,
            "workflows": _safe_json(workflows),
            "workflow_total": int(workflow_total or 0),
            "sales": _safe_json(sales),
            "sales_total": int(sales_total or 0),
            "total": int(workflow_total or 0) + int(sales_total or 0),
            "source": "sjagent_core",
        },
    })


def _mini_workflow_order_images(value) -> list[str]:
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


def _mini_workflow_quantity(value) -> int:
    text = str(value or "").strip()
    if not text:
        return 0
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return 0
    try:
        return int(float(match.group(0)))
    except Exception:
        return 0


def _mini_workflow_order_list(keyword: str, page: int = 1, page_size: int = 100, status_filter: str = "active") -> tuple[list[dict], int]:
    cards, total = _db_workflow_orders(keyword, max(1, page), min(max(1, page_size), 200), status_filter)
    return _safe_json(cards), int(total or 0)


def _mini_number(value) -> float:
    try:
        return float(str(value or "0").replace(",", ""))
    except Exception:
        return 0.0


def _mini_inventory_qty_text(value: float) -> int | str:
    if abs(value - round(value)) < 0.000001:
        return int(round(value))
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _mini_workflow_inventory_payload(keyword: str = "") -> dict:
    rows = get_inventory_service().search(keyword=keyword, only_in_stock=False, limit=3000)
    grouped: dict[str, dict] = {}
    for row in (rows if isinstance(rows, list) else []):
        code = str(row.get("sku_no") or row.get("code") or row.get("product_code") or "").strip()
        name = str(row.get("title") or row.get("name") or "").strip()
        color = str(row.get("color") or "").strip()
        key = f"{code}|{name}|{color}"
        item = grouped.setdefault(key, {
            "id": row.get("product_id") or row.get("id"),
            "name": name or "商品",
            "code": code,
            "spec": color,
            "color": color,
            "box_spec": row.get("simple_desc") or "",
            "qty_baixin": 0.0,
            "qty_shop": 0.0,
            "total_qty": 0.0,
        })
        qty = _mini_number(row.get("inventory") or row.get("stock") or row.get("quantity"))
        warehouse_name = str(row.get("warehouse_name") or row.get("warehouse") or "").strip()
        warehouse_id = _mini_int(row.get("warehouse_id"), 0)
        if "店" in warehouse_name or "门店" in warehouse_name or warehouse_id == 1:
            item["qty_shop"] += qty
        else:
            item["qty_baixin"] += qty
        item["total_qty"] += qty
    items = []
    total_qty = 0.0
    for item in grouped.values():
        total_qty += _mini_number(item.get("total_qty"))
        item["qty_baixin"] = _mini_inventory_qty_text(_mini_number(item.get("qty_baixin")))
        item["qty_shop"] = _mini_inventory_qty_text(_mini_number(item.get("qty_shop")))
        item["total_qty"] = _mini_inventory_qty_text(_mini_number(item.get("total_qty")))
        items.append(item)
    items.sort(key=lambda item: (-_mini_number(item.get("total_qty")), str(item.get("name") or "")))
    return {
        "items": _safe_json(items),
        "total_qty": _mini_inventory_qty_text(total_qty),
        "total_items": len(items),
        "source": "sjagent_core",
    }


@app.route("/api/mini/workflow-order/customer-list", methods=["GET", "POST"])
def mini_workflow_customer_list_api():
    payload = _mini_request_payload()
    nickname = str(_mini_value(payload, "nickname", "customer_name", "keyword", default="")).strip()
    if not nickname:
        return jsonify({"code": 0, "data": []})
    cards, _total = _mini_workflow_order_list(nickname, 1, 100, "active")
    return jsonify({"code": 0, "data": cards})


@app.route("/api/mini/workflow-order/employee-list", methods=["GET", "POST"])
def mini_workflow_employee_list_api():
    if not _mini_order_user_can_edit(_mini_request_user()):
        return _mini_order_edit_denied_response()
    payload = _mini_request_payload()
    page, page_size = _mini_page_payload(payload)
    cards, _total = _mini_workflow_order_list("", page, max(page_size, 100), "active")
    return jsonify({"code": 0, "data": cards})


@app.route("/api/mini/workflow-order/search", methods=["GET", "POST"])
def mini_workflow_search_api():
    payload = _mini_request_payload()
    keyword = str(_mini_value(payload, "keyword", "q", "wd", default="")).strip()
    user = _mini_request_user()
    if not _mini_orderflow_should_query(keyword, user):
        return jsonify({"code": 0, "data": []})
    cards, _total = _mini_workflow_order_list(keyword, 1, 100, "active")
    return jsonify({"code": 0, "data": cards})


@app.route("/api/mini/workflow-order/inventory-search", methods=["GET", "POST"])
def mini_workflow_inventory_search_api():
    payload = _mini_request_payload()
    keyword = _normalize_inventory_keyword(str(_mini_value(payload, "keyword", "q", "wd", default="")).strip())
    try:
        return jsonify({"code": 0, "data": _mini_workflow_inventory_payload(keyword)})
    except Exception as e:
        logger.error(f"mini workflow inventory query failed: {e}")
        return _api_exception_response(e)


@app.route("/api/mini/workflow-order/save", methods=["POST"])
def mini_workflow_save_api():
    if not _mini_order_user_can_edit(_mini_request_user()):
        return _mini_order_edit_denied_response()
    payload = _mini_request_payload()
    customer_name = str(_mini_value(payload, "customer_name", default="")).strip()
    if not customer_name:
        return jsonify({"code": 400, "msg": "请输入客户名字"}), 400
    try:
        result = get_workflow_service().save_order(
            order_id=_mini_int(_mini_value(payload, "id", "order_id", default=0), 0) or None,
            customer_name=customer_name,
            customer_phone=str(_mini_value(payload, "customer_phone", "phone", default="")).strip(),
            goods_name=str(_mini_value(payload, "goods_name", default="商品未填写")).strip() or "商品未填写",
            color=str(_mini_value(payload, "goods_color", "color", default="")).strip(),
            order_quantity=_mini_workflow_quantity(_mini_value(payload, "order_quantity", "quantity", default=0)),
            order_images=_mini_workflow_order_images(_mini_value(payload, "order_images", "images", default=[])),
            is_screen_print=_mini_int(_mini_value(payload, "is_screen_print", default=0), 0),
            order_type=_mini_int(_mini_value(payload, "order_type", default=0), 0),
            remark=str(_mini_value(payload, "remark", default="")).strip(),
        )
        if isinstance(result, dict) and result.get("code", 0) != 0:
            return jsonify({"code": result.get("code", 500), "msg": result.get("msg", "保存失败")}), 400
        return jsonify({"code": 0, "data": result.get("data", result) if isinstance(result, dict) else result})
    except Exception as e:
        logger.error(f"mini workflow save failed: {e}")
        return _api_exception_response(e)


@app.route("/api/mini/workflow-order/status-update", methods=["POST"])
def mini_workflow_status_update_api():
    if not _mini_order_user_can_edit(_mini_request_user()):
        return _mini_order_edit_denied_response()
    payload = _mini_request_payload()
    order_id = _mini_int(_mini_value(payload, "id", "order_id", default=0), 0)
    field = str(_mini_value(payload, "field", default="")).strip()
    value = _mini_int(_mini_value(payload, "value", default=0), 0)
    if not order_id:
        return jsonify({"code": 400, "msg": "缺少订单ID"}), 400
    if field not in {"is_made", "is_delivered", "order_type"}:
        return jsonify({"code": 400, "msg": "字段不允许更新"}), 400
    try:
        result = get_workflow_service().update_status(order_id=order_id, field=field, value=value)
        if isinstance(result, dict) and result.get("code", 0) != 0:
            return jsonify({"code": result.get("code", 500), "msg": result.get("msg", "操作失败")}), 400
        return jsonify({"code": 0, "data": result.get("data", result) if isinstance(result, dict) else result})
    except Exception as e:
        logger.error(f"mini workflow status update failed: {e}")
        return _api_exception_response(e)


@app.route("/api/product/options", methods=["GET"])
def product_options():
    """商品编辑基础数据。"""
    try:
        product_id = request.args.get("id", type=int)
        return jsonify({"code": 0, "data": _safe_json(get_product_service().options(product_id))})
    except Exception as e:
        logger.error(f"商品基础数据异常: {e}")
        return _api_exception_response(e)


@app.route("/api/product/<int:product_id>", methods=["GET"])
def product_detail_api(product_id: int):
    """商品详情。"""
    try:
        product = get_product_service().info(product_id)
        if not product:
            return jsonify({"code": 404, "msg": "商品不存在"}), 404
        return jsonify({"code": 0, "data": _safe_json(product)})
    except Exception as e:
        logger.error(f"商品详情异常: {e}")
        return _api_exception_response(e)


@app.route("/api/product/save", methods=["POST"])
def product_save_api():
    """创建/编辑商品。"""
    try:
        body = request.get_json(silent=True)
        if body is None:
            body = request.form.to_dict(flat=True)
        result = get_product_service().save(body or {})
        return jsonify(result)
    except Exception as e:
        logger.error(f"商品保存异常: {e}")
        return _api_exception_response(e)


@app.route("/api/product/delete", methods=["POST"])
def product_delete_api():
    """删除商品。"""
    try:
        body = request.get_json(silent=True)
        if body is None:
            body = request.form.to_dict(flat=True)
        ids = (body or {}).get("ids")
        if not ids:
            return jsonify({"code": 400, "msg": "缺少商品ID"}), 400
        result = get_product_service().delete(ids)
        return jsonify(result)
    except Exception as e:
        logger.error(f"商品删除异常: {e}")
        return _api_exception_response(e)


def _product_crop_number(body: dict, snake_key: str, camel_key: str, default: float = 0) -> float:
    raw = body.get(snake_key)
    if raw is None:
        raw = body.get(camel_key, default)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return float(default)


def _open_product_crop_image(source_url: str):
    """Open a crop source image from OSS/http or local preview URLs."""
    source_url = str(source_url or "").strip()
    if not source_url:
        raise ValueError("缺少图片地址")
    if source_url.startswith("/api/images/file/"):
        safe_name = secure_filename(source_url.rsplit("/", 1)[-1])
        if not safe_name:
            raise ValueError("图片地址无效")
        local_path = UPLOAD_DIR / safe_name
        if not local_path.exists():
            raise ValueError("本地图片不存在")
        from PIL import Image

        return Image.open(local_path)
    if source_url.startswith("/"):
        source_url = urljoin(request.host_url, source_url.lstrip("/"))
    parsed = urlparse(source_url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("只支持 http/https 图片地址")

    import requests
    from PIL import Image

    response = requests.get(source_url, timeout=20, headers={"User-Agent": "sjagent-admin/1.0"})
    response.raise_for_status()
    if len(response.content) > 25 * 1024 * 1024:
        raise ValueError("图片文件过大")
    return Image.open(io.BytesIO(response.content))


@app.route("/api/product/upload", methods=["POST"])
def product_upload_api():
    """上传商品图片到 OSS。"""
    try:
        file = request.files.get("image")
        if file is None:
            return jsonify({"code": 400, "msg": "缺少图片文件"}), 400
        filename = secure_filename(file.filename or f"product_{int(time.time())}.jpg")
        if not _allowed_image(filename):
            return jsonify({"code": 400, "msg": "只支持 png/jpg/jpeg/webp/bmp 图片"}), 400

        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        suffix = _safe_upload_suffix(file.filename, ALLOWED_IMAGE_EXTENSIONS, ".jpg")
        save_name = f"product_{int(time.time())}_{uuid.uuid4().hex[:10]}{suffix}"
        save_path = UPLOAD_DIR / save_name
        file.save(save_path)
        if not save_path.exists() or save_path.stat().st_size <= 0:
            return jsonify({"code": 400, "msg": "图片文件为空"}), 400

        from scripts.oss_uploader import OSSUploader
        from src.core.config import get_config

        result = OSSUploader(get_config().oss_config).upload(str(save_path))
        if not isinstance(result, dict):
            return jsonify({"code": 500, "msg": "OSS 上传返回异常", "data": result}), 500
        if result.get("error"):
            return jsonify({"code": 500, "msg": result.get("error"), "data": result}), 500
        url = result.get("url") or result.get("full_url") or result.get("images") or result.get("path") or ""
        if url:
            try:
                get_product_service().record_upload(str(url), storage="oss")
            except Exception as asset_error:
                logger.warning(f"商品图片待绑定资产记录失败: {asset_error}")
        _delete_local_upload(save_path, "商品图片")
        return jsonify({"code": 0, "data": result})
    except Exception as e:
        logger.error(f"商品图片上传异常: {e}")
        return _api_exception_response(e)


@app.route("/api/product/crop-square", methods=["POST"])
def product_crop_square_api():
    """Crop an existing product image to a square and upload it to OSS."""
    try:
        body = request.get_json(silent=True)
        if body is None:
            body = request.form.to_dict(flat=True)
        body = body or {}
        source_url = body.get("url") or body.get("source_url") or body.get("sourceUrl") or ""
        source_x = _product_crop_number(body, "source_x", "sourceX", 0)
        source_y = _product_crop_number(body, "source_y", "sourceY", 0)
        source_size = _product_crop_number(body, "source_size", "sourceSize", 0)
        output_size = int(_product_crop_number(body, "output_size", "outputSize", 1200) or 1200)
        output_size = max(256, min(output_size, 2000))

        image = _open_product_crop_image(source_url)
        image.load()
        width, height = image.size
        if width <= 0 or height <= 0:
            return jsonify({"code": 400, "msg": "图片尺寸无效"}), 400
        if source_size <= 0:
            source_size = min(width, height)
        left = int(round(max(0, min(source_x, max(0, width - 1)))))
        top = int(round(max(0, min(source_y, max(0, height - 1)))))
        size = int(round(max(1, min(source_size, width - left, height - top))))
        if size <= 0:
            return jsonify({"code": 400, "msg": "裁切区域无效"}), 400

        from PIL import Image

        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        save_name = f"product_crop_{int(time.time())}_{uuid.uuid4().hex[:10]}.jpg"
        save_path = UPLOAD_DIR / save_name
        cropped = image.crop((left, top, left + size, top + size)).convert("RGB")
        cropped = cropped.resize((output_size, output_size), Image.Resampling.LANCZOS)
        cropped.save(save_path, "JPEG", quality=92, optimize=True)
        if not save_path.exists() or save_path.stat().st_size <= 0:
            return jsonify({"code": 400, "msg": "裁切图片生成失败"}), 400

        from scripts.oss_uploader import OSSUploader
        from src.core.config import get_config

        result = OSSUploader(get_config().oss_config).upload(str(save_path))
        if not isinstance(result, dict):
            return jsonify({"code": 500, "msg": "OSS 上传返回异常", "data": result}), 500
        if result.get("error"):
            return jsonify({"code": 500, "msg": result.get("error"), "data": result}), 500
        url = result.get("url") or result.get("full_url") or result.get("images") or result.get("path") or ""
        if url:
            try:
                get_product_service().record_upload(str(url), storage="oss")
            except Exception as asset_error:
                logger.warning(f"商品裁切图片待绑定资产记录失败: {asset_error}")
        _delete_local_upload(save_path, "商品裁切图片")
        return jsonify({"code": 0, "data": result})
    except ValueError as e:
        return jsonify({"code": 400, "msg": str(e)}), 400
    except Exception as e:
        logger.error(f"商品图片裁切异常: {e}")
        return _api_exception_response(e)


@app.route("/api/miniapp/image-config/upload", methods=["POST"])
def miniapp_image_config_upload_api():
    """Upload mini-program configuration images to OSS."""
    try:
        file = request.files.get("image")
        if file is None:
            return jsonify({"code": 400, "msg": "缺少图片文件"}), 400
        filename = secure_filename(file.filename or f"miniapp_{int(time.time())}.jpg")
        if not _allowed_image(filename):
            return jsonify({"code": 400, "msg": "只支持 png/jpg/jpeg/webp/bmp 图片"}), 400

        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        suffix = _safe_upload_suffix(file.filename, ALLOWED_IMAGE_EXTENSIONS, ".jpg")
        save_name = f"miniapp_{int(time.time())}_{uuid.uuid4().hex[:10]}{suffix}"
        save_path = UPLOAD_DIR / save_name
        file.save(save_path)
        if not save_path.exists() or save_path.stat().st_size <= 0:
            return jsonify({"code": 400, "msg": "图片文件为空"}), 400

        from scripts.oss_uploader import OSSUploader
        from src.core.config import get_config

        result = OSSUploader(get_config().oss_config).upload(str(save_path))
        if not isinstance(result, dict):
            return jsonify({"code": 500, "msg": "OSS 上传返回异常", "data": result}), 500
        if result.get("error"):
            return jsonify({"code": 500, "msg": result.get("error"), "data": result}), 500
        _delete_local_upload(save_path, "小程序配置图片")
        return jsonify({"code": 0, "data": result})
    except Exception as e:
        logger.error(f"小程序配置图片上传异常: {e}")
        return _api_exception_response(e)


@app.route("/api/product/media", methods=["GET"])
def product_media_api():
    """商品图片资产。"""
    try:
        product_id = request.args.get("product_id", type=int)
        page = max(1, request.args.get("page", 1, type=int) or 1)
        page_size_arg = request.args.get("page_size", type=int)
        has_page_size = page_size_arg is not None
        page_size = max(1, min(page_size_arg or 80, 200))
        limit = max(1, min(request.args.get("limit", 500, type=int), 6000))
        fetch_limit = 6000 if has_page_size else limit
        media_type = (request.args.get("media_type") or "").strip()
        if product_id:
            product = get_product_service().info(product_id)
            if not product:
                return jsonify({"code": 404, "msg": "商品不存在"}), 404
            rows = get_product_service().media_assets(
                spu_id=int(product.get("spu_id") or 0),
                sku_ids=[int(product.get("id") or product_id)],
                media_type=media_type,
                include_pending=True,
                limit=fetch_limit,
            )
        else:
            rows = get_product_service().media_assets(media_type=media_type, include_pending=True, limit=fetch_limit)
        total = len(rows)
        if has_page_size:
            start = (page - 1) * page_size
            rows = rows[start:start + page_size]
        data = {"list": _safe_json(rows), "total": total, "source": "native"}
        if has_page_size:
            data.update({"page": page, "page_size": page_size})
        return jsonify({"code": 0, "data": data})
    except Exception as e:
        logger.error(f"商品图片资产查询异常: {e}")
        return _api_exception_response(e)


@app.route("/api/product/media/<int:media_id>", methods=["DELETE", "POST"])
def product_media_delete_api(media_id: int):
    """Disable a product image asset."""
    try:
        return jsonify(get_product_service().delete_media(media_id))
    except Exception as e:
        logger.error(f"商品图片资产删除异常: {e}")
        return _api_exception_response(e)


@app.route("/api/product/<int:product_id>/shelves", methods=["POST"])
def product_shelves_api(product_id: int):
    """Update product listing state."""
    try:
        body = request.get_json(silent=True) or request.form.to_dict(flat=True) or {}
        state = int(body.get("state", 0))
        spu_id = _mini_int(body.get("spu_id") or body.get("spuId"), 0)
        sku_ids = _payload_id_list(body.get("sku_ids") or body.get("skuIds") or body.get("ids"))
        result = get_product_service().update_shelves(product_id, state, spu_id=spu_id or None, sku_ids=sku_ids)
        return jsonify(result)
    except Exception as e:
        logger.error(f"商品上下架异常: {e}")
        return _api_exception_response(e)


@app.route("/api/customer/list", methods=["GET"])
def customer_list():
    """
    Customer list from sjagent_core.
    GET /api/customer/list?keyword=xxx
    """
    keyword = request.args.get("keyword", "")
    try:
        return jsonify({"code": 0, "data": _db_customer_list(keyword), "source": "db"})
    except Exception as e:
        logger.error(f"客户列表查询异常: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/customer/create", methods=["POST"])
def customer_create_api():
    """Create a native customer for the WebUI sales form."""
    from src.core.customer_name import normalize_customer_name

    body = request.get_json(silent=True)
    if body is None:
        body = request.form.to_dict(flat=True)
    body = body or {}
    name = normalize_customer_name(
        body.get("name")
        or body.get("customer_name")
        or body.get("customer")
        or ""
    )
    contacts_name = str(body.get("contacts_name") or body.get("contact") or "").strip()
    contacts_tel = str(body.get("contacts_tel") or body.get("phone") or body.get("mobile") or "").strip()

    if not name:
        return jsonify({"code": 400, "msg": "客户名称不能为空"}), 400

    def display_name(row: dict) -> str:
        return str(
            row.get("name")
            or row.get("customer_name")
            or row.get("company_name")
            or row.get("title")
            or row.get("contacts_name")
            or ""
        ).strip()

    def normalize_row(row: dict, *, existed: bool = False) -> dict:
        cid = row.get("id") or row.get("customer_id") or row.get("company_id") or ""
        row_name = display_name(row) or name
        return {
            "id": cid,
            "customer_id": cid,
            "name": row_name,
            "customer_name": row_name,
            "company_name": row.get("company_name") or row_name,
            "contacts_name": row.get("contacts_name") or contacts_name,
            "mobile": row.get("mobile") or row.get("contacts_mobile") or row.get("contacts_tel") or contacts_tel,
            "address": row.get("address") or "",
            "existed": existed,
        }

    def exact_customer(rows: list[dict]) -> dict | None:
        target = normalize_customer_name(name)
        for row in rows or []:
            if normalize_customer_name(display_name(row)) == target:
                return row
        return None

    try:
        existing = exact_customer(_db_customer_list(name, limit=20))
        if existing:
            return jsonify({
                "code": 0,
                "msg": "客户已存在，已选中",
                "data": normalize_row(existing, existed=True),
            })

        result = get_customer_service().create(
            name=name,
            contacts_name=contacts_name,
            contacts_tel=contacts_tel,
        )
        if isinstance(result, dict) and result.get("code") not in (None, 0):
            return jsonify(result), 400

        created_row = exact_customer(_db_customer_list(name, limit=20))
        if created_row:
            return jsonify({"code": 0, "msg": "客户创建成功", "data": normalize_row(created_row)})

        data = result.get("data") if isinstance(result, dict) else {}
        customer_id = data.get("id") if isinstance(data, dict) else ""
        return jsonify({
            "code": 0,
            "msg": "客户创建成功",
            "data": {
                "id": customer_id,
                "customer_id": customer_id,
                "name": name,
                "customer_name": name,
                "company_name": name,
                "contacts_name": contacts_name,
                "mobile": contacts_tel,
                "existed": False,
            },
        })
    except Exception as e:
        logger.error(f"客户创建异常: {e}")
        return _api_exception_response(e)


@app.route("/api/warehouse/list", methods=["GET"])
def warehouse_list():
    """Warehouse list from sjagent_core."""
    try:
        return jsonify({"code": 0, "data": get_inventory_service().warehouse_list()})
    except Exception as e:
        logger.error(f"仓库列表查询异常: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/customer/price", methods=["GET"])
def customer_price():
    """
    客户历史成交价查询
    GET /api/customer/price?customer_id=1&product_id=123
    """
    customer_id = request.args.get("customer_id", type=int)
    product_id = request.args.get("product_id", type=int)

    if not customer_id or not product_id:
        return jsonify({"code": 400, "msg": "customer_id and product_id are required"}), 400

    try:
        price = get_sales_service().history_price(customer_id, product_id)
        return jsonify({"code": 0, "data": {"price": price}})
    except Exception as e:
        logger.error(f"客户价格查询异常: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/product/retail-price", methods=["GET"])
def product_retail_price():
    """
    商品零售价查询
    GET /api/product/retail-price?product_id=123
    """
    product_id = request.args.get("product_id", type=int)
    if not product_id:
        return jsonify({"code": 400, "msg": "product_id is required"}), 400

    try:
        price = get_product_service().price(product_id)
        return jsonify({"code": 0, "data": {"price": price}})
    except Exception as e:
        logger.error(f"零售价查询异常: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


def _page_args(default_size: int = 50, max_size: int = 200) -> tuple[int, int]:
    page = max(1, request.args.get("page", 1, type=int))
    page_size = max(1, min(request.args.get("page_size", default_size, type=int), max_size))
    return page, page_size


@app.route("/api/customers", methods=["GET"])
def native_customers_api():
    """Native customer management list."""
    keyword = (request.args.get("keyword") or "").strip()
    filter_value = (request.args.get("filter") or "all").strip()
    try:
        if "page" not in request.args and "page_size" not in request.args:
            limit = max(1, min(request.args.get("limit", 200, type=int), 500))
            rows = get_customer_service().list(keyword, limit=limit)
            return jsonify({"code": 0, "data": {"list": _safe_json(rows), "total": len(rows), "source": "native"}})
        page, page_size = _page_args(default_size=12, max_size=100)
        rows, total, summary = get_customer_service().list_page(
            keyword,
            page=page,
            page_size=page_size,
            filter_value=filter_value,
        )
        return jsonify({
            "code": 0,
            "data": {
                "list": _safe_json(rows),
                "total": total,
                "summary": _safe_json(summary),
                "page": page,
                "page_size": page_size,
                "filter": filter_value,
                "source": "native",
            },
        })
    except Exception as e:
        logger.error(f"自有库客户管理列表异常: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/customers/<int:customer_id>", methods=["POST", "PATCH"])
def native_customer_update_api(customer_id: int):
    """Native customer business flags."""
    body = request.get_json(silent=True)
    if body is None:
        body = request.form.to_dict(flat=True)
    body = body or {}
    try:
        response_data: dict = {}
        phone = body.get("phone") or body.get("contacts_tel") or body.get("mobile")
        if phone is not None:
            user = _current_web_user() or {}
            operator_user_id = user.get("native_user_id") or user.get("id")
            link_result = get_customer_service().sync_phone(
                customer_id,
                str(phone),
                operator_user_id=operator_user_id,
            )
            if link_result.get("code") not in (None, 0):
                return jsonify(_safe_json(link_result)), int(link_result.get("_http_status") or 400)
            response_data["identity_link"] = link_result.get("data") or {}
        profile_keys = {"name", "customer_name", "company_name", "contacts_name", "contact_name", "address"}
        if any(key in body for key in profile_keys):
            result = get_customer_service().update_profile(
                customer_id,
                name=body.get("name") if "name" in body else body.get("customer_name") or body.get("company_name"),
                contacts_name=body.get("contacts_name") if "contacts_name" in body else body.get("contact_name"),
                address=body.get("address") if "address" in body else None,
            )
            if result.get("code") not in (None, 0):
                return jsonify(_safe_json(result)), int(result.get("_http_status") or 400)
            response_data.update(result.get("data") or {})
        if "is_monthly_customer" in body:
            result = get_customer_service().update_monthly(customer_id, body.get("is_monthly_customer"))
            if result.get("code") not in (None, 0):
                return jsonify(_safe_json(result)), 400
            response_data.update(result.get("data") or {})
        if response_data:
            return jsonify({"code": 0, "data": _safe_json(response_data)})
        return jsonify({"code": 400, "msg": "没有可更新的客户字段"}), 400
    except Exception as e:
        logger.error(f"自有库客户更新异常: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/customers/<int:customer_id>/sales", methods=["GET"])
def native_customer_sales_api(customer_id: int):
    """Native customer bound sales orders."""
    page, page_size = _page_args(default_size=50, max_size=200)
    period = (request.args.get("period") or "").strip()
    month = (request.args.get("month") or "").strip()
    try:
        rows, total, summary = get_customer_service().sales(
            customer_id,
            page=page,
            page_size=page_size,
            period=period,
            month=month,
        )
        return jsonify({
            "code": 0,
            "data": {
                "list": _safe_json(rows),
                "total": total,
                "summary": _safe_json(summary),
                "page": page,
                "page_size": page_size,
                "source": "native",
            },
        })
    except Exception as e:
        logger.error(f"自有库客户销售单异常: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/customers/<int:customer_id>/statement", methods=["GET"])
def native_customer_statement_api(customer_id: int):
    """Native customer statement preview."""
    try:
        statement = get_customer_service().statement(
            customer_id,
            month=(request.args.get("month") or "").strip(),
            date_from=(request.args.get("date_from") or "").strip(),
            date_to=(request.args.get("date_to") or "").strip(),
        )
        return jsonify({"code": 0, "data": _safe_json(statement)})
    except DBError as e:
        logger.warning(f"customer statement rejected: customer_id={customer_id}, error={e}")
        return _api_exception_response(e)
    except Exception as e:
        logger.error(f"customer statement failed: customer_id={customer_id}, error={e}")
        return _api_exception_response(e)


@app.route("/api/customers/<int:customer_id>/statement.pdf", methods=["GET"])
def native_customer_statement_pdf_api(customer_id: int):
    """Native customer statement PDF download."""
    try:
        statement = get_customer_service().statement(
            customer_id,
            month=(request.args.get("month") or "").strip(),
            date_from=(request.args.get("date_from") or "").strip(),
            date_to=(request.args.get("date_to") or "").strip(),
        )
        pdf_bytes = build_customer_statement_pdf(statement)
        customer_name = str((statement.get("customer") or {}).get("name") or "客户").strip() or "客户"
        period_label = str(statement.get("period_label") or "").replace(" 至 ", "-")
        filename = f"{customer_name}-{period_label}-对账单.pdf"
        response = Response(pdf_bytes, mimetype="application/pdf")
        response.headers["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(filename)}"
        return response
    except DBError as e:
        logger.warning(f"customer statement pdf rejected: customer_id={customer_id}, error={e}")
        return _api_exception_response(e)
    except Exception as e:
        logger.error(f"customer statement pdf failed: customer_id={customer_id}, error={e}")
        return _api_exception_response(e)


@app.route("/api/customers/<int:customer_id>/balance-ledger", methods=["GET"])
def native_customer_balance_ledger_api(customer_id: int):
    """Native customer balance ledger."""
    page, page_size = _page_args()
    try:
        rows, total, summary = get_customer_balance_service().ledger(
            customer_id,
            page=page,
            page_size=page_size,
        )
        return jsonify({
            "code": 0,
            "data": {
                "list": _safe_json(rows),
                "total": total,
                "summary": _safe_json(summary),
                "page": page,
                "page_size": page_size,
                "source": "native",
            },
        })
    except DBError as e:
        logger.warning(f"customer balance ledger rejected: customer_id={customer_id}, error={e}")
        return _api_exception_response(e)
    except Exception as e:
        logger.error(f"customer balance ledger failed: customer_id={customer_id}, error={e}")
        return _api_exception_response(e)


@app.route("/api/customers/<int:customer_id>/balance", methods=["POST"])
def native_customer_balance_api(customer_id: int):
    """Customer receipt/recharge/monthly settlement/balance adjustment."""
    body = request.get_json(silent=True) or {}
    action = (body.get("action") or "").strip()
    amount = body.get("amount")
    pay_type = (body.get("pay_type") or "").strip()
    note = (body.get("note") or "").strip()
    try:
        user = _current_web_user() or {}
        operator_user_id = user.get("native_user_id") or user.get("id")
        result = get_customer_balance_service().apply_action(
            customer_id,
            action=action,
            amount=amount,
            pay_type=pay_type,
            note=note,
            month=body.get("month") or "",
            operator_user_id=operator_user_id,
        )
        return jsonify(_safe_json(result))
    except DBError as e:
        logger.warning(f"customer balance action rejected: customer_id={customer_id}, action={action}, error={e}")
        return _api_exception_response(e)
    except Exception as e:
        logger.error(f"customer balance action failed: customer_id={customer_id}, action={action}, error={e}")
        return _api_exception_response(e)


@app.route("/api/users", methods=["GET"])
def native_users_api():
    """Native user management list."""
    keyword = (request.args.get("keyword") or "").strip()
    page, page_size = _page_args()
    try:
        rows, total = get_user_service().list(keyword=keyword, page=page, page_size=page_size)
        return jsonify({
            "code": 0,
            "data": {
                "list": _safe_json(rows),
                "total": total,
                "page": page,
                "page_size": page_size,
                "source": "native",
            },
        })
    except Exception as e:
        logger.error(f"自有库用户管理列表异常: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/users/<int:user_id>", methods=["POST", "PATCH"])
def native_user_update_api(user_id: int):
    """Native user role / enabled update."""
    body = request.get_json(silent=True)
    if body is None:
        body = request.form.to_dict(flat=True)
    body = body or {}
    try:
        role = body.get("role") if "role" in body else None
        is_active = body.get("is_active") if "is_active" in body else None
        phone = body.get("phone") if "phone" in body else None
        display_name = body.get("display_name") if "display_name" in body else None
        user = _current_web_user() or {}
        operator_user_id = user.get("native_user_id") or user.get("id")
        result = get_user_service().update(
            user_id,
            role=role,
            is_active=is_active,
            phone=phone,
            display_name=display_name,
            operator_user_id=operator_user_id,
        )
        if isinstance(result, dict) and result.get("code") not in (None, 0):
            return jsonify(result), 400
        return jsonify(result)
    except Exception as e:
        logger.error(f"自有库用户更新异常: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/warehouses", methods=["GET"])
def native_warehouses_api():
    try:
        rows = get_inventory_service().warehouse_list()
        return jsonify({"code": 0, "data": {"list": _safe_json(rows), "total": len(rows), "source": "native"}})
    except Exception as e:
        logger.error(f"自有库仓库列表异常: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/inventory/balances", methods=["GET"])
def native_inventory_balances_api():
    keyword = _normalize_inventory_keyword((request.args.get("keyword") or "").strip())
    warehouse_id = request.args.get("warehouse_id", type=int)
    page, page_size = _page_args()
    try:
        rows, total = get_inventory_service().balances(keyword=keyword, warehouse_id=warehouse_id, page=page, page_size=page_size)
        return jsonify({"code": 0, "data": {"list": _safe_json(rows), "total": total, "page": page, "page_size": page_size, "source": "native"}})
    except Exception as e:
        logger.error(f"自有库库存明细异常: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/inventory/ledger", methods=["GET"])
def native_inventory_ledger_api():
    keyword = (request.args.get("keyword") or "").strip()
    page, page_size = _page_args()
    try:
        rows, total = get_inventory_service().ledger(keyword=keyword, page=page, page_size=page_size)
        return jsonify({"code": 0, "data": {"list": _safe_json(rows), "total": total, "page": page, "page_size": page_size, "source": "native"}})
    except Exception as e:
        logger.error(f"自有库库存日志异常: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/stock-documents", methods=["GET"])
def native_stock_documents_api():
    keyword = (request.args.get("keyword") or "").strip()
    page, page_size = _page_args()
    try:
        rows, total = get_inventory_service().stock_documents(keyword=keyword, page=page, page_size=page_size)
        return jsonify({"code": 0, "data": {"list": _safe_json(rows), "total": total, "page": page, "page_size": page_size, "source": "native"}})
    except Exception as e:
        logger.error(f"自有库出入库明细异常: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/stocktakes", methods=["GET"])
def native_stocktakes_api():
    keyword = (request.args.get("keyword") or "").strip()
    page, page_size = _page_args()
    try:
        rows, total = get_inventory_service().stocktakes(keyword=keyword, page=page, page_size=page_size)
        return jsonify({"code": 0, "data": {"list": _safe_json(rows), "total": total, "page": page, "page_size": page_size, "source": "native"}})
    except Exception as e:
        logger.error(f"自有库盘点明细异常: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/transfers", methods=["GET"])
def native_transfers_api():
    keyword = (request.args.get("keyword") or "").strip()
    page, page_size = _page_args()
    try:
        rows, total = get_inventory_service().transfers(keyword=keyword, page=page, page_size=page_size)
        return jsonify({"code": 0, "data": {"list": _safe_json(rows), "total": total, "page": page, "page_size": page_size, "source": "native"}})
    except Exception as e:
        logger.error(f"自有库调拨明细异常: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


def _normalize_sales_add_products(products: list[dict]) -> list[dict]:
    """Fill the native product base unit before SalesAdd."""
    return get_sales_service().normalize_products(products)


@app.route("/api/sales/add", methods=["POST"])
def sales_add():
    """
    开销售单接口
    POST /api/sales/add
    {
        "customer_id": 1,
        "warehouse_id": 2,
        "products": [
            {"product_id": 123, "unit_id": 1, "buy_number": 10, "price": 28.0}
        ]
    }
    """
    body = request.get_json()
    customer_id = body.get("customer_id")
    warehouse_id = body.get("warehouse_id", 2)
    products = body.get("products", [])
    create_time = body.get("create_time") or ""
    pay_status = body.get("pay_status")
    pay_type = body.get("pay_type")

    if not customer_id or not products:
        return jsonify({"code": 400, "msg": "customer_id and products are required"}), 400

    try:
        user = _current_web_user() or {}
        operator_user_id = user.get("native_user_id") or user.get("id")
        result = get_sales_service().create_order(
            customer_id=customer_id,
            warehouse_id=warehouse_id,
            products=products,
            create_time=create_time,
            pay_status=pay_status,
            pay_type=pay_type,
            operator_user_id=operator_user_id,
        )
        if isinstance(result, dict) and result.get("code") not in (None, 0):
            return jsonify(result), 400
        return jsonify(result if isinstance(result, dict) else {"code": 0, "data": result})
    except Exception as e:
        logger.error(f"开单异常: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/tools/list", methods=["GET"])
def tools_list():
    """
    列出所有可用工具
    GET /api/tools/list
    """
    from src.core.tools import list_all_tools
    tools = list_all_tools()
    return jsonify({"code": 0, "data": tools})


@app.route("/api/auth/login", methods=["POST"])
def auth_login():
    """Login with sjagent_core auth_user and return a native session token."""
    body = request.get_json(silent=True) or request.form.to_dict() or {}
    accounts = (body.get("accounts") or body.get("username") or body.get("mobile") or body.get("email") or "").strip()
    password = body.get("pwd") or body.get("password") or ""
    try:
        client_type = (body.get("client_type") or request.headers.get("X-SJ-Client") or "miniapp").strip()
        result = get_auth_service().native_login(
            account=accounts,
            password=password,
            client_type=client_type,
            ip=request.headers.get("X-Forwarded-For") or request.remote_addr or "",
            user_agent=request.headers.get("User-Agent") or "",
        )
        return _json_service_result(result)
    except Exception as e:
        logger.error(f"北极星登录异常: {e}")
        return jsonify({"code": 500, "msg": f"北极星登录异常: {e}"}), 500


@app.route("/api/auth/register", methods=["POST"])
def auth_register():
    """Register a native mini-program customer account and return a session token."""
    body = request.get_json(silent=True) or request.form.to_dict() or {}
    account = (
        body.get("account")
        or body.get("accounts")
        or body.get("username")
        or body.get("mobile")
        or body.get("phone")
        or body.get("email")
        or ""
    ).strip()
    password = body.get("pwd") or body.get("password") or ""
    display_name = (
        body.get("display_name")
        or body.get("displayName")
        or body.get("nickname")
        or body.get("name")
        or account
    )
    try:
        client_type = (body.get("client_type") or request.headers.get("X-SJ-Client") or "miniapp").strip()
        result = get_auth_service().native_register(
            account=account,
            password=password,
            display_name=display_name,
            client_type=client_type,
            ip=request.headers.get("X-Forwarded-For") or request.remote_addr or "",
            user_agent=request.headers.get("User-Agent") or "",
        )
        return _json_service_result(result)
    except Exception as e:
        logger.error(f"北极星注册异常: {e}")
        return jsonify({"code": 500, "msg": f"北极星注册异常: {e}"}), 500


@app.route("/api/auth/wechat-quick-login", methods=["POST"])
def auth_wechat_quick_login():
    """Login through native WeChat identity binding."""
    body = request.get_json(silent=True) or request.form.to_dict() or {}
    phone_code = (body.get("phone_code") or body.get("phoneCode") or "").strip()
    authcode = (
        body.get("authcode")
        or body.get("login_code")
        or body.get("loginCode")
        or body.get("js_code")
        or body.get("jsCode")
        or ""
    ).strip()
    if not authcode:
        fallback_code = (body.get("code") or "").strip()
        if fallback_code and fallback_code != phone_code:
            authcode = fallback_code
    openid = (body.get("openid") or body.get("open_id") or "").strip()
    unionid = (body.get("unionid") or body.get("union_id") or "").strip()
    profile = body.get("userInfo") if isinstance(body.get("userInfo"), dict) else body
    try:
        miniapp_appid = body.get("appid") or os.environ.get("WECHAT_MINIAPP_APPID") or os.environ.get("WX_MINIAPP_APPID") or ""
        result = get_auth_service().wechat_quick_login(
            openid=openid,
            unionid=unionid,
            profile=profile,
            authcode=authcode,
            phone_code=phone_code,
            appid=miniapp_appid,
            ip=request.headers.get("X-Forwarded-For") or request.remote_addr or "",
            user_agent=request.headers.get("User-Agent") or "",
        )
        return _json_service_result(result)
    except Exception as e:
        logger.error(f"微信快捷登录异常: {e}")
        return jsonify({"code": 500, "msg": f"微信快捷登录异常: {e}"}), 500


@app.route("/api/auth/change-password", methods=["POST"])
def auth_change_password():
    """Change or set the password for the current native mini-program account."""
    token = _auth_token_from_request()
    if not token:
        return jsonify({"code": 401, "msg": "请先登录账号"}), 401
    body = request.get_json(silent=True) or request.form.to_dict() or {}
    old_password = body.get("old_password") or body.get("current_password") or body.get("oldPassword") or ""
    new_password = body.get("new_password") or body.get("password") or body.get("newPassword") or ""
    try:
        user = get_auth_service().verify_token(token, force=True)
        if not user:
            return jsonify({"code": 401, "msg": "登录已失效，请重新登录"}), 401
        result = get_auth_service().change_native_password(
            user_id=int(user.get("id") or user.get("user_id") or 0),
            old_password=old_password,
            new_password=new_password,
        )
        return _json_service_result(result)
    except Exception as e:
        logger.error(f"账号密码设置异常: {e}")
        return jsonify({"code": 500, "msg": f"账号密码设置异常: {e}"}), 500


@app.route("/api/auth/captcha", methods=["GET"])
def auth_captcha():
    """Native login does not need image captcha; keep the endpoint compatible."""
    transparent_gif = (
        b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00"
        b"\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,"
        b"\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
    )
    response = Response(transparent_gif, content_type="image/gif")
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["X-SJ-Captcha"] = "disabled"
    return response


@app.route("/api/auth/me", methods=["GET", "POST"])
def auth_me():
    """Validate the current native token and return normalized user info."""
    token = _auth_token_from_request()
    if not token:
        return jsonify({"code": 401, "msg": "缺少登录 token"}), 401
    try:
        user = get_auth_service().verify_token(token, force=request.args.get("force") in ("1", "true", "True"))
        if not user:
            return jsonify({"code": 401, "msg": "登录已失效，请重新登录"}), 401
        if request.method == "POST":
            body = request.get_json(silent=True) or request.form.to_dict() or {}
            display_name = (
                body.get("display_name")
                or body.get("displayName")
                or body.get("nickname")
                or body.get("name")
                or ""
            )
            result = get_auth_service().update_native_profile(
                user_id=int(user.get("id") or user.get("user_id") or 0),
                display_name=display_name,
                token=token,
            )
            return _json_service_result(result)
        return jsonify({"code": 0, "data": {"token": token, "user": user}})
    except Exception as e:
        logger.error(f"北极星用户信息校验异常: {e}")
        return jsonify({"code": 500, "msg": f"北极星用户信息校验异常: {e}"}), 500


@app.route("/api/asr/aliyun-token", methods=["GET"])
def aliyun_asr_token():
    """Return a short-lived Aliyun NLS token for mini-program ASR."""
    try:
        from src.services.aliyun_asr import create_aliyun_token
        token = create_aliyun_token(force=request.args.get("force") in ("1", "true", "True"))
        return jsonify({
            "code": 0,
            "data": {
                "token": token.get("token"),
                "expire_time": token.get("expire_time"),
                "appkey": token.get("appkey"),
                "vocabulary_id": token.get("vocabulary_id") or "",
            }
        })
    except Exception as e:
        logger.error(f"阿里云 ASR Token 获取失败: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/asr/hotwords/status", methods=["GET"])
def aliyun_asr_hotwords_status():
    """Return local hotword sync status."""
    try:
        from src.services.aliyun_asr import get_hotword_state
        return jsonify({"code": 0, "data": get_hotword_state()})
    except Exception as e:
        logger.error(f"阿里云 ASR 热词状态获取失败: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/asr/hotwords/sync", methods=["POST"])
def aliyun_asr_hotwords_sync():
    """Manually sync ERP hotwords to Aliyun ASR."""
    try:
        from src.services.aliyun_asr import sync_hotwords
        force = request.args.get("force") in ("1", "true", "True")
        body = request.get_json(silent=True) or {}
        if body.get("force") is not None:
            force = bool(body.get("force"))
        result = sync_hotwords(force=force)
        return jsonify({"code": 0, "data": result})
    except Exception as e:
        logger.error(f"阿里云 ASR 热词同步失败: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/health", methods=["GET"])
def health():
    """健康检查"""
    return jsonify({"status": "ok", "agent": "sjagent"})


def run_api_server(host: str = "127.0.0.1", port: int = 8080):
    """启动 HTTP API 服务器"""
    app.run(host=host, port=port, debug=False)
