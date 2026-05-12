"""
HTTP API 渠道（预留 WebUI 和外部调用）
提供 RESTful API 供前端或外部系统调用 Agent
"""
import json
import os
import re
import threading
import uuid
import time
from pathlib import Path
from urllib.parse import urlencode
from flask import Flask, request, jsonify, Response, send_from_directory, session, redirect
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from src.core.agent import Agent
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
ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "bmp"}
SHOPXO_AUTH_CACHE: dict[str, tuple[float, dict]] = {}
SHOPXO_AUTH_CACHE_TTL = 86400 * 30
WEB_AUTH_TABLE = "sjagent_web_users"
_WEB_AUTH_TABLE_READY = False
_WEB_AUTH_TABLE_LOCK = threading.Lock()


def _api_exception_response(e: Exception):
    response = getattr(e, "response", None)
    if isinstance(response, dict) and response:
        return jsonify(response)
    return jsonify({"code": 500, "msg": str(e)}), 500


def _web_auth_db():
    from src.engine.db_client import get_db_client
    return get_db_client()


def _ensure_web_auth_table():
    global _WEB_AUTH_TABLE_READY
    if _WEB_AUTH_TABLE_READY:
        return
    with _WEB_AUTH_TABLE_LOCK:
        if _WEB_AUTH_TABLE_READY:
            return
        db = _web_auth_db()
        db.execute(f"""
            CREATE TABLE IF NOT EXISTS `{WEB_AUTH_TABLE}` (
                `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
                `username` VARCHAR(64) NOT NULL,
                `password_hash` VARCHAR(255) NOT NULL,
                `display_name` VARCHAR(80) NOT NULL DEFAULT '',
                `approval_status` VARCHAR(16) NOT NULL DEFAULT 'approved',
                `is_admin` TINYINT(1) NOT NULL DEFAULT 0,
                `is_active` TINYINT(1) NOT NULL DEFAULT 1,
                `created_at` INT UNSIGNED NOT NULL DEFAULT 0,
                `updated_at` INT UNSIGNED NOT NULL DEFAULT 0,
                `last_login_at` INT UNSIGNED NOT NULL DEFAULT 0,
                `approved_at` INT UNSIGNED NOT NULL DEFAULT 0,
                `approved_by` INT UNSIGNED NOT NULL DEFAULT 0,
                PRIMARY KEY (`id`),
                UNIQUE KEY `uk_username` (`username`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        columns = {
            str(row.get("Field"))
            for row in db.query(f"SHOW COLUMNS FROM `{WEB_AUTH_TABLE}`")
        }
        additions = {
            "approval_status": "ALTER TABLE `{table}` ADD COLUMN `approval_status` VARCHAR(16) NOT NULL DEFAULT 'approved' AFTER `display_name`",
            "is_admin": "ALTER TABLE `{table}` ADD COLUMN `is_admin` TINYINT(1) NOT NULL DEFAULT 0 AFTER `approval_status`",
            "approved_at": "ALTER TABLE `{table}` ADD COLUMN `approved_at` INT UNSIGNED NOT NULL DEFAULT 0 AFTER `last_login_at`",
            "approved_by": "ALTER TABLE `{table}` ADD COLUMN `approved_by` INT UNSIGNED NOT NULL DEFAULT 0 AFTER `approved_at`",
        }
        for column, sql in additions.items():
            if column not in columns:
                db.execute(sql.format(table=WEB_AUTH_TABLE))
        _WEB_AUTH_TABLE_READY = True


def _web_auth_user_by_username(username: str) -> dict | None:
    _ensure_web_auth_table()
    rows = _web_auth_db().query(
        f"SELECT id, username, password_hash, display_name, approval_status, is_admin, is_active FROM `{WEB_AUTH_TABLE}` WHERE username=%s LIMIT 1",
        (username,),
    )
    return rows[0] if rows else None


def _web_auth_user_by_id(user_id: int) -> dict | None:
    _ensure_web_auth_table()
    rows = _web_auth_db().query(
        f"SELECT id, username, display_name, approval_status, is_admin, is_active, last_login_at FROM `{WEB_AUTH_TABLE}` WHERE id=%s LIMIT 1",
        (int(user_id),),
    )
    return rows[0] if rows else None


def _current_web_user() -> dict | None:
    user_id = session.get("web_user_id")
    if not user_id:
        return None
    user = _web_auth_user_by_id(int(user_id))
    if not user or int(user.get("is_active") or 0) != 1 or str(user.get("approval_status") or "") != "approved":
        session.pop("web_user_id", None)
        return None
    return user


def _current_web_user_is_admin() -> bool:
    user = _current_web_user()
    return bool(user and int(user.get("is_admin") or 0) == 1)


def _web_auth_required_response():
    if request.path == "/web" or request.accept_mimetypes.accept_html:
        return redirect("/login")
    return jsonify({"code": 401, "msg": "请先登录北极星"}), 401


def _shopxo_base_url() -> str:
    try:
        from src.core.config import get_config
        configured = get_config().get("shopxo.base_url", "") or ""
        erp_api_base = get_config().erp_api_base or ""
    except Exception:
        configured = ""
        erp_api_base = ""
    base = os.environ.get("SHOPXO_BASE_URL") or configured
    if not base and erp_api_base:
        base = erp_api_base.split("/api.php", 1)[0]
    return (base or "https://shop.513sjbz.com").rstrip("/")


def _shopxo_api_url(
    controller: str,
    action: str,
    token: str = "",
    uuid_value: str = "",
    extra_params: dict | None = None,
) -> str:
    application = os.environ.get("SHOPXO_APPLICATION", "app")
    client_type = os.environ.get("SHOPXO_CLIENT_TYPE", "weixin")
    client_brand = os.environ.get("SHOPXO_CLIENT_BRAND", "WeChat")
    uuid_value = uuid_value or f"sjagent_{uuid.uuid4().hex}"
    params = (
        f"s={controller}/{action}"
        f"&application={application}"
        f"&application_client_type={client_type}"
        f"&application_client_brand={client_brand}"
        f"&uuid={uuid_value}"
        f"&ajax=ajax"
    )
    if token:
        params += f"&token={token}"
    if extra_params:
        params += f"&{urlencode(extra_params)}"
    return f"{_shopxo_base_url()}/api.php?{params}"


def _shopxo_post(controller: str, action: str, data: dict | None = None, token: str = "", uuid_value: str = "") -> dict:
    import requests
    resp = requests.post(
        _shopxo_api_url(controller, action, token=token, uuid_value=uuid_value),
        data=data or {},
        timeout=15,
    )
    resp.raise_for_status()
    result = resp.json()
    return result if isinstance(result, dict) else {"code": -1, "msg": "商城返回格式异常", "data": result}


def _shopxo_get(controller: str, action: str, token: str = "", uuid_value: str = "", extra_params: dict | None = None):
    import requests
    resp = requests.get(
        _shopxo_api_url(controller, action, token=token, uuid_value=uuid_value, extra_params=extra_params),
        timeout=15,
    )
    resp.raise_for_status()
    return resp


def _nested_token(value) -> str:
    if isinstance(value, dict):
        for key in ("token", "user_token", "access_token"):
            if value.get(key):
                return str(value.get(key))
        for item in value.values():
            token = _nested_token(item)
            if token:
                return token
    if isinstance(value, list):
        for item in value:
            token = _nested_token(item)
            if token:
                return token
    return ""


def _shopxo_user_by_account(accounts: str) -> dict | None:
    """Resolve a ShopXO user after ShopXO itself has already accepted the login."""
    try:
        from src.engine.db_client import get_db_client
        db = get_db_client()
        rows = db.query(
            """
            SELECT
                u.id, u.username, u.nickname, u.mobile, u.email, u.avatar,
                u.status, u.user_role,
                up.token AS platform_token
            FROM sxo_user u
            LEFT JOIN sxo_user_platform up
                ON up.user_id = u.id AND up.platform = %s
            WHERE u.is_delete_time = 0
              AND u.is_logout_time = 0
              AND (u.username = %s OR u.mobile = %s OR u.email = %s OR u.number_code = %s)
            ORDER BY up.token DESC
            LIMIT 1
            """,
            (
                os.environ.get("SHOPXO_CLIENT_TYPE", "weixin"),
                accounts,
                accounts,
                accounts,
                accounts,
            ),
        )
    except Exception as e:
        logger.warning(f"商城登录用户资料兜底查询失败: {e}")
        return None
    if not rows:
        return None
    row = dict(rows[0])
    token = row.pop("platform_token", "") or f"sj_local_{uuid.uuid4().hex}"
    return _normalize_shopxo_user(row, token)


def _shopxo_user_permission(user_id) -> dict:
    if not user_id:
        return {"status": None, "user_role": None, "is_admin": False, "miniapp_allowed": False}
    try:
        from src.engine.db_client import get_db_client
        db = get_db_client()
        rows = db.query(
            """
            SELECT id, status, user_role
            FROM sxo_user
            WHERE id = %s
              AND is_delete_time = 0
              AND is_logout_time = 0
            LIMIT 1
            """,
            (user_id,),
        )
    except Exception as e:
        logger.warning(f"商城用户权限查询失败: {e}")
        return {"status": None, "user_role": None, "is_admin": False, "miniapp_allowed": False}
    if not rows:
        return {"status": None, "user_role": None, "is_admin": False, "miniapp_allowed": False}
    row = rows[0]
    status = int(row.get("status") or 0)
    user_role = int(row.get("user_role") or 0)
    is_admin = status == 0 and user_role == 0
    return {
        "status": status,
        "user_role": user_role,
        "is_admin": is_admin,
        "miniapp_allowed": is_admin,
    }


def _auth_token_from_request() -> str:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    return request.headers.get("X-Shopxo-Token", "") or request.args.get("token", "")


def _normalize_shopxo_user(user: dict, token: str = "") -> dict:
    if not isinstance(user, dict):
        user = {}
    user_id = user.get("id") or user.get("user_id") or ""
    display_name = (
        user.get("user_name_view")
        or user.get("nickname")
        or user.get("username")
        or user.get("mobile")
        or user.get("email")
        or (f"用户{user_id}" if user_id else "商城用户")
    )
    normalized = {
        "id": user_id,
        "token": token or user.get("token") or "",
        "display_name": display_name,
        "nickname": user.get("nickname") or "",
        "username": user.get("username") or "",
        "mobile": user.get("mobile") or "",
        "email": user.get("email") or "",
        "avatar": user.get("avatar") or "",
        "raw": user,
    }
    normalized.update(_shopxo_user_permission(user_id))
    return normalized


def _shopxo_user_can_access_miniapp(user: dict | None) -> bool:
    return bool(isinstance(user, dict) and user.get("miniapp_allowed") is True)


def _verify_shopxo_token(token: str, force: bool = False) -> dict | None:
    if not token:
        return None
    now = time.time()
    cached = SHOPXO_AUTH_CACHE.get(token)
    if cached and not force and cached[0] > now:
        return cached[1]
    if token.startswith("sj_local_"):
        return cached[1] if cached and cached[0] > now else None
    result = _shopxo_post("user", "tokenuserinfo", token=token)
    if int(result.get("code", -1)) != 0 or not isinstance(result.get("data"), dict):
        SHOPXO_AUTH_CACHE.pop(token, None)
        return None
    user = _normalize_shopxo_user(result.get("data") or {}, token)
    SHOPXO_AUTH_CACHE[token] = (now + 300, user)
    return user


@app.before_request
def _miniapp_auth_guard():
    if request.method == "OPTIONS":
        return None
    path = request.path or ""
    if not path.startswith("/api/"):
        return None
    if path.startswith("/api/auth/"):
        return None
    if request.headers.get("X-SJ-Client") != "miniapp":
        return None
    token = _auth_token_from_request()
    try:
        user = _verify_shopxo_token(token)
    except Exception as e:
        logger.warning(f"商城用户 token 校验异常: {e}")
        user = None
    if not user:
        return jsonify({"code": 401, "msg": "请先登录商城账号"}), 401
    if not _shopxo_user_can_access_miniapp(user):
        return jsonify({"code": 403, "msg": "当前账号不是管理员，暂无小程序业务权限"}), 403
    request.shopxo_user = user
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
        "/api/web-auth/login",
        "/api/web-auth/register",
        "/api/web-auth/me",
        "/api/web-auth/logout",
    }
    if path in public_paths or path.startswith("/api/auth/"):
        return None
    if path == "/web" or path.startswith("/api/"):
        if not _current_web_user():
            return _web_auth_required_response()
    return None


def _request_user_id(default: str = "http_user") -> str:
    web_user = _current_web_user()
    if isinstance(web_user, dict) and web_user.get("id"):
        return f"web_{web_user.get('id')}"
    user = getattr(request, "shopxo_user", None)
    if isinstance(user, dict) and user.get("id"):
        return f"shopxo_{user.get('id')}"
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
        name = (product.get("name") or product.get("title") or old.get("name") or old.get("title") or "").strip()
        color = (product.get("color") or old.get("color") or "").strip()
        qty = _pending_number(product.get("qty", product.get("quantity", old.get("qty", 1))), old.get("qty", 1) or 1)
        edited_price = product.get("price", None)
        price = _pending_price(edited_price, old.get("price", 0) or 0) if edited_price not in (None, "") else old.get("price", 0) or 0
        old_name = (old.get("name") or old.get("title") or "").strip()
        old_color = (old.get("color") or "").strip()
        name_changed = bool(name and name != old_name)
        color_changed = color != old_color

        if name_changed or color_changed or not old.get("product_id") or not old.get("unit_id"):
            candidate = dict(old)
            candidate.update(product)
            candidate["name"] = name
            candidate["color"] = color
            candidate["qty"] = qty
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


def _db_client():
    from src.engine.db_client import get_db_client
    return get_db_client()


def _like_keyword(keyword: str) -> str:
    return f"%{str(keyword or '').strip()}%"


def _normalize_inventory_keyword(keyword: str) -> str:
    text = str(keyword or "").strip()
    if not text:
        return ""
    for word in ("库存", "有货", "有库存", "查货", "查一下", "查下", "查询", "看看", "帮我", "礼盒", "盒子", "的", "吗", "呢"):
        text = text.replace(word, " ")
    text = re.sub(r"(^|\s)查(?=\s|[\u4e00-\u9fa5A-Za-z0-9])", " ", text)
    text = re.sub(r"(?:3\s*两|2\s*两|(?<!二)三两|二两)", "二三两", text)
    text = re.sub(r"(?:0\.5\s*斤|半\s*斤)", "半斤", text)
    text = re.sub(r"(?:1\s*两|一\s*两)", "一两", text)
    text = re.sub(r"3\s*小盒", "三小盒", text)
    text = re.sub(r"6\s*小盒", "六小盒", text)
    text = re.sub(r"10\s*小盒", "十小盒", text)
    specs = ["二三两", "半斤", "一两", "三小盒", "六小盒", "十小盒", "长半斤"]
    for spec in specs:
        text = re.sub(rf"(?<!^)(?<!\s)({re.escape(spec)})", r" \1", text)
    return re.sub(r"\s+", " ", text).strip()


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


def _db_sales_cards(keyword: str, page: int, page_size: int, status: int | None = None) -> tuple[list[dict], int]:
    db = _db_client()
    where = ["1=1"]
    join_extra = ""
    params: list = []
    if status is not None:
        where.append("s.status = %s")
        params.append(status)
    if keyword:
        like = _like_keyword(keyword)
        where.append(
            "("
            "s.sales_no LIKE %s OR c.name LIKE %s OR c.company_name LIKE %s "
            "OR sd.title LIKE %s OR sd.spec LIKE %s"
            ")"
        )
        params.extend([like, like, like, like, like])
        join_extra = " LEFT JOIN sxo_plugins_erp_sales_detail sd ON sd.sales_id = s.id"
    where_sql = " AND ".join(where)
    offset = (page - 1) * page_size
    group_sql = "GROUP BY s.id" if keyword else ""
    total_rows = db.query(
        f"""
        SELECT COUNT({ 'DISTINCT s.id' if keyword else '*' }) AS total
        FROM sxo_plugins_erp_sales s
        LEFT JOIN sxo_plugins_erp_company c ON c.id = s.customer_id
        {join_extra}
        WHERE {where_sql}
        """,
        tuple(params),
    )
    total = int(total_rows[0].get("total") or 0) if total_rows else 0
    sales_rows = db.query(
        f"""
        SELECT
            s.id, s.sales_no, s.customer_id, s.status, s.pay_status, s.total_price,
            s.price, s.buy_number_count, s.note, s.admin_note, s.add_time,
            COALESCE(NULLIF(c.name, ''), NULLIF(c.company_name, ''), s.contacts_name, CONCAT('客户#', s.customer_id)) AS customer_name
        FROM sxo_plugins_erp_sales s
        LEFT JOIN sxo_plugins_erp_company c ON c.id = s.customer_id
        {join_extra}
        WHERE {where_sql}
        {group_sql}
        ORDER BY s.add_time DESC, s.id DESC
        LIMIT %s OFFSET %s
        """,
        tuple(params + [page_size, offset]),
    )
    ids = [int(row["id"]) for row in sales_rows if row.get("id")]
    details_by_sales: dict[int, list[dict]] = {sid: [] for sid in ids}
    if ids:
        placeholders = ",".join(["%s"] * len(ids))
        detail_rows = db.query(
            f"""
            SELECT sales_id, product_id, title, spec, images, warehouse_id, price, buy_number, total_price
            FROM sxo_plugins_erp_sales_detail
            WHERE sales_id IN ({placeholders})
            ORDER BY id ASC
            """,
            tuple(ids),
        )
        for item in detail_rows:
            sid = int(item.get("sales_id") or 0)
            details_by_sales.setdefault(sid, []).append({
                "product_id": item.get("product_id"),
                "title": item.get("title") or "商品",
                "spec": item.get("spec") or "",
                "quantity": item.get("buy_number") or 0,
                "price": _as_money(item.get("price")),
                "total_price": _as_money(item.get("total_price")),
                "image": _image_first(item.get("images")),
                "warehouse_id": item.get("warehouse_id"),
            })
    cards = []
    for row in sales_rows:
        sid = int(row.get("id") or 0)
        products = details_by_sales.get(sid, [])
        total_quantity = 0
        for product in products:
            try:
                total_quantity += float(product.get("quantity") or 0)
            except (TypeError, ValueError):
                pass
        cards.append({
            "id": sid,
            "sales_no": row.get("sales_no") or str(sid),
            "customer_name": row.get("customer_name") or "客户未识别",
            "status": row.get("status"),
            "status_text": _sales_status_text(row.get("status")),
            "pay_status": row.get("pay_status"),
            "total_price": _as_money(row.get("total_price") or row.get("price")),
            "buy_number_count": row.get("buy_number_count") or 0,
            "total_quantity": total_quantity or row.get("buy_number_count") or 0,
            "date_text": _date_text(row.get("add_time")),
            "product_summary": _first_product_line(products),
            "products": products,
            "note": row.get("note") or row.get("admin_note") or "",
        })
    return cards, total


def _db_workflow_orders(keyword: str, page: int, page_size: int, status_filter: str = "active") -> tuple[list[dict], int]:
    db = _db_client()
    where = ["1=1"]
    params: list = []
    now = int(time.time())
    seven_days_ago = now - 86400 * 7
    if status_filter == "unmade":
        where.append("COALESCE(is_made, 0) <> 1")
    elif status_filter == "pending":
        where.append("(COALESCE(order_type, 0) <> 1 OR COALESCE(is_made, 0) <> 1 OR COALESCE(is_delivered, 0) <> 1)")
    elif status_filter != "all":
        where.append(
            "("
            "COALESCE(order_type, 0) <> 1 "
            "OR COALESCE(is_made, 0) <> 1 "
            "OR COALESCE(is_delivered, 0) <> 1 "
            "OR COALESCE(complete_time, order_time, add_time, 0) >= %s"
            ")"
        )
        params.append(seven_days_ago)
    if keyword:
        like = _like_keyword(keyword)
        where.append("(customer_name LIKE %s OR customer_phone LIKE %s OR goods_name LIKE %s OR goods_color LIKE %s)")
        params.extend([like, like, like, like])
    where_sql = " AND ".join(where)
    total_rows = db.query(f"SELECT COUNT(*) AS total FROM sxo_workflow_order WHERE {where_sql}", tuple(params))
    total = int(total_rows[0].get("total") or 0) if total_rows else 0
    offset = (page - 1) * page_size
    rows = db.query(
        f"""
        SELECT *
        FROM sxo_workflow_order
        WHERE {where_sql}
        ORDER BY COALESCE(order_time, add_time) DESC, id DESC
        LIMIT %s OFFSET %s
        """,
        tuple(params + [page_size, offset]),
    )
    return [_workflow_card(row) for row in rows], total


def _db_product_list_flat(keyword: str, page: int, page_size: int, status=None, category_id: int | None = None) -> tuple[list[dict], int]:
    db = _db_client()
    where = ["1=1"]
    join_category = ""
    params: list = []
    if status not in (None, ""):
        where.append("p.status = %s")
        params.append(int(status))
    if category_id:
        join_category = " JOIN sxo_plugins_erp_product_category_join pcj ON pcj.product_id = p.id"
        where.append("pcj.product_category_id = %s")
        params.append(int(category_id))
    if keyword:
        like = _like_keyword(keyword)
        compact = f"%{str(keyword).replace(' ', '').replace('　', '')}%"
        where.append(
            "("
            "p.title LIKE %s OR p.spec LIKE %s OR p.coding LIKE %s OR p.simple_desc LIKE %s "
            "OR REPLACE(REPLACE(REPLACE(REPLACE(p.title, '【', ''), '】', ''), ' ', ''), '　', '') LIKE %s"
            ")"
        )
        params.extend([like, like, like, like, compact])
    where_sql = " AND ".join(where)
    total_rows = db.query(
        f"SELECT COUNT(DISTINCT p.id) AS total FROM sxo_plugins_erp_product p {join_category} WHERE {where_sql}",
        tuple(params),
    )
    total = int(total_rows[0].get("total") or 0) if total_rows else 0
    offset = (page - 1) * page_size
    rows = db.query(
        f"""
        SELECT p.id, p.title, p.spec, p.coding, p.simple_desc, p.images, p.main_images, p.price, p.min_price, p.max_price,
               p.inventory, p.status, p.group_key, p.content, p.cost_price, p.add_time, p.upd_time,
               g.id AS system_goods_id, g.is_shelves AS system_goods_is_shelves, sg.unit_id AS unit_id,
               GROUP_CONCAT(DISTINCT pcj2.product_category_id ORDER BY pcj2.product_category_id) AS product_category_ids,
               GROUP_CONCAT(DISTINCT pc.name ORDER BY pc.sort DESC, pc.id ASC SEPARATOR ' / ') AS product_category_text
        FROM sxo_plugins_erp_product p
        {join_category}
        LEFT JOIN sxo_plugins_erp_system_goods_sync_product_log sg
          ON sg.id = (
            SELECT MAX(sg2.id)
            FROM sxo_plugins_erp_system_goods_sync_product_log sg2
            WHERE sg2.product_id = p.id
          )
        LEFT JOIN sxo_goods g ON g.id = sg.goods_id
        LEFT JOIN sxo_plugins_erp_product_category_join pcj2 ON pcj2.product_id = p.id
        LEFT JOIN sxo_plugins_erp_product_category pc ON pc.id = pcj2.product_category_id
        WHERE {where_sql}
        GROUP BY p.id
        ORDER BY p.upd_time DESC, p.id DESC
        LIMIT %s OFFSET %s
        """,
        tuple(params + [page_size, offset]),
    )
    items = []
    for row in rows:
        image = _image_first(row.get("main_images") or row.get("images"))
        items.append({
            "id": row.get("id"),
            "product_id": row.get("id"),
            "title": row.get("title") or "商品",
            "name": row.get("title") or "商品",
            "spec": row.get("spec") or "",
            "coding": row.get("coding") or "",
            "simple_desc": row.get("simple_desc") or "",
            "price": _as_money(row.get("price") or row.get("min_price")),
            "min_price": _as_money(row.get("min_price") or row.get("price")),
            "max_price": _as_money(row.get("max_price") or row.get("price")),
            "inventory": row.get("inventory") or 0,
            "status": row.get("status"),
            "status_text": _product_status_text(row.get("status")),
            "images": image,
            "main_images": image,
            "content": row.get("content") or "",
            "cost_price": _as_money(row.get("cost_price")),
            "group_key": row.get("group_key") or "",
            "product_category_ids": [
                int(item) for item in str(row.get("product_category_ids") or "").split(",") if str(item).isdigit()
            ],
            "product_category_text": row.get("product_category_text") or "",
            "system_goods_id": row.get("system_goods_id") or 0,
            "system_goods_is_shelves": int(row.get("system_goods_is_shelves") or 0),
            "unit_id": int(row.get("unit_id") or 1),
        })
    return items, total


def _db_product_grouped_list(keyword: str, page: int, page_size: int, status=None, category_id: int | None = None) -> tuple[list[dict], int]:
    db = _db_client()
    where = ["1=1"]
    join_category = ""
    params: list = []
    if status not in (None, ""):
        where.append("p.status = %s")
        params.append(int(status))
    if category_id:
        join_category = " JOIN sxo_plugins_erp_product_category_join pcj ON pcj.product_id = p.id"
        where.append("pcj.product_category_id = %s")
        params.append(int(category_id))
    if keyword:
        like = _like_keyword(keyword)
        compact = f"%{str(keyword).replace(' ', '').replace('　', '')}%"
        where.append(
            "("
            "p.title LIKE %s OR p.spec LIKE %s OR p.coding LIKE %s OR p.simple_desc LIKE %s "
            "OR REPLACE(REPLACE(REPLACE(REPLACE(p.title, '【', ''), '】', ''), ' ', ''), '　', '') LIKE %s"
            ")"
        )
        params.extend([like, like, like, like, compact])

    where_sql = " AND ".join(where)
    group_expr = "COALESCE(NULLIF(p.group_key, ''), CAST(p.id AS CHAR))"
    total_rows = db.query(
        f"SELECT COUNT(DISTINCT {group_expr}) AS total FROM sxo_plugins_erp_product p {join_category} WHERE {where_sql}",
        tuple(params),
    )
    total = int(total_rows[0].get("total") or 0) if total_rows else 0
    offset = (page - 1) * page_size
    group_rows = db.query(
        f"""
        SELECT {group_expr} AS product_group_key, MAX(p.upd_time) AS latest_time, MAX(p.id) AS latest_id
        FROM sxo_plugins_erp_product p
        {join_category}
        WHERE {where_sql}
        GROUP BY product_group_key
        ORDER BY latest_time DESC, latest_id DESC
        LIMIT %s OFFSET %s
        """,
        tuple(params + [page_size, offset]),
    )
    group_keys = [str(row.get("product_group_key") or "") for row in group_rows if row.get("product_group_key") is not None]
    if not group_keys:
        return [], total

    placeholders = ",".join(["%s"] * len(group_keys))
    rows = db.query(
        f"""
        SELECT p.id, p.title, p.spec, p.coding, p.simple_desc, p.images, p.main_images, p.price, p.min_price, p.max_price,
               p.inventory, p.status, p.group_key, p.content, p.cost_price, p.add_time, p.upd_time,
               g.id AS system_goods_id, g.is_shelves AS system_goods_is_shelves, sg.unit_id AS unit_id,
               GROUP_CONCAT(DISTINCT pcj2.product_category_id ORDER BY pcj2.product_category_id) AS product_category_ids,
               GROUP_CONCAT(DISTINCT pc.name ORDER BY pc.sort DESC, pc.id ASC SEPARATOR ' / ') AS product_category_text
        FROM sxo_plugins_erp_product p
        LEFT JOIN sxo_plugins_erp_system_goods_sync_product_log sg
          ON sg.id = (
            SELECT MAX(sg2.id)
            FROM sxo_plugins_erp_system_goods_sync_product_log sg2
            WHERE sg2.product_id = p.id
          )
        LEFT JOIN sxo_goods g ON g.id = sg.goods_id
        LEFT JOIN sxo_plugins_erp_product_category_join pcj2 ON pcj2.product_id = p.id
        LEFT JOIN sxo_plugins_erp_product_category pc ON pc.id = pcj2.product_category_id
        WHERE COALESCE(NULLIF(p.group_key, ''), CAST(p.id AS CHAR)) IN ({placeholders})
        GROUP BY p.id
        ORDER BY p.title ASC, p.id ASC
        """,
        tuple(group_keys),
    )

    grouped: dict[str, list[dict]] = {key: [] for key in group_keys}
    for row in rows:
        key = str(row.get("group_key") or row.get("id") or "")
        image = _image_first(row.get("main_images") or row.get("images"))
        item = {
            "id": row.get("id"),
            "product_id": row.get("id"),
            "title": row.get("title") or "商品",
            "name": row.get("title") or "商品",
            "spec": row.get("spec") or "",
            "coding": row.get("coding") or "",
            "simple_desc": row.get("simple_desc") or "",
            "price": _as_money(row.get("price") or row.get("min_price")),
            "min_price": _as_money(row.get("min_price") or row.get("price")),
            "max_price": _as_money(row.get("max_price") or row.get("price")),
            "inventory": row.get("inventory") or 0,
            "status": row.get("status"),
            "status_text": _product_status_text(row.get("status")),
            "images": image,
            "main_images": image,
            "content": row.get("content") or "",
            "cost_price": _as_money(row.get("cost_price")),
            "group_key": row.get("group_key") or "",
            "product_category_ids": [
                int(item) for item in str(row.get("product_category_ids") or "").split(",") if str(item).isdigit()
            ],
            "product_category_text": row.get("product_category_text") or "",
            "system_goods_id": row.get("system_goods_id") or 0,
            "system_goods_is_shelves": int(row.get("system_goods_is_shelves") or 0),
            "unit_id": int(row.get("unit_id") or 1),
        }
        grouped.setdefault(key, []).append(item)

    items = []
    for key in group_keys:
        variants = grouped.get(key) or []
        if not variants:
            continue
        primary = next((item for item in variants if item.get("images")), variants[0]).copy()
        inventories: list[float] = []
        prices: list[float] = []
        category_ids: list[int] = []
        category_texts: list[str] = []
        shelves_values: list[int] = []
        for item in variants:
            try:
                inventories.append(float(item.get("inventory") or 0))
            except (TypeError, ValueError):
                pass
            try:
                prices.append(float(item.get("price") or item.get("min_price") or 0))
            except (TypeError, ValueError):
                pass
            shelves_values.append(int(item.get("system_goods_is_shelves") or 0))
            for cid in item.get("product_category_ids") or []:
                if cid not in category_ids:
                    category_ids.append(cid)
            text = item.get("product_category_text") or ""
            if text and text not in category_texts:
                category_texts.append(text)
        inventory_total = sum(inventories)
        primary["product_group_data"] = variants
        primary["spec_count"] = len(variants)
        primary["inventory"] = int(inventory_total) if inventory_total.is_integer() else inventory_total
        if prices:
            primary["price"] = _as_money(min(prices))
            primary["min_price"] = _as_money(min(prices))
            primary["max_price"] = _as_money(max(prices))
        primary["product_category_ids"] = category_ids
        primary["product_category_text"] = " / ".join(category_texts[:2]) if category_texts else primary.get("product_category_text", "")
        primary["system_goods_is_shelves"] = 1 if any(value == 1 for value in shelves_values) else 0
        items.append(primary)
    return items, total


def _db_product_list(keyword: str, page: int, page_size: int, status=None, category_id: int | None = None, group: bool = False) -> tuple[list[dict], int]:
    if group:
        return _db_product_grouped_list(keyword, page, page_size, status, category_id)
    return _db_product_list_flat(keyword, page, page_size, status, category_id)


def _db_product_categories() -> list[dict]:
    db = _db_client()
    rows = db.query(
        """
        SELECT c.id, c.name, c.pid, c.sort, c.is_enable,
               COUNT(DISTINCT COALESCE(NULLIF(p.group_key, ''), CAST(p.id AS CHAR))) AS total
        FROM sxo_plugins_erp_product_category c
        LEFT JOIN sxo_plugins_erp_product_category_join pcj ON pcj.product_category_id = c.id
        LEFT JOIN sxo_plugins_erp_product p ON p.id = pcj.product_id
        WHERE c.is_enable = 1
        GROUP BY c.id
        ORDER BY c.sort DESC, c.id ASC
        """
    )
    return [
        {
            "id": row.get("id"),
            "name": row.get("name") or f"分类#{row.get('id')}",
            "pid": row.get("pid") or 0,
            "total": int(row.get("total") or 0),
        }
        for row in rows
    ]


def _db_customer_list(keyword: str, limit: int = 50) -> list[dict]:
    db = _db_client()
    where = ["is_customer = 1"]
    params: list = []
    if keyword:
        like = _like_keyword(keyword)
        where.append("(name LIKE %s OR company_name LIKE %s OR contacts_name LIKE %s OR contacts_mobile LIKE %s OR contacts_tel LIKE %s)")
        params.extend([like, like, like, like, like])
    params.append(max(1, min(limit, 100)))
    rows = db.query(
        f"""
        SELECT id, name, company_name, contacts_name, contacts_mobile, contacts_tel, address, is_enable
        FROM sxo_plugins_erp_company
        WHERE {' AND '.join(where)}
        ORDER BY upd_time DESC, id DESC
        LIMIT %s
        """,
        tuple(params),
    )
    return [
        {
            "id": row.get("id"),
            "name": row.get("name") or row.get("company_name") or row.get("contacts_name") or f"客户#{row.get('id')}",
            "customer_name": row.get("name") or row.get("company_name") or row.get("contacts_name") or f"客户#{row.get('id')}",
            "company_name": row.get("company_name") or "",
            "contacts_name": row.get("contacts_name") or "",
            "mobile": row.get("contacts_mobile") or row.get("contacts_tel") or "",
            "address": row.get("address") or "",
            "is_enable": row.get("is_enable"),
        }
        for row in rows
    ]


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


def _date_text(timestamp) -> str:
    try:
        ts = int(timestamp or 0)
    except (TypeError, ValueError):
        ts = 0
    if not ts:
        return ""
    return time.strftime("%Y-%m-%d", time.localtime(ts))


def _sales_status_text(status) -> str:
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


def _inventory_cards(rows: list[dict], limit: int) -> list[dict]:
    cards: dict[str, dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        product_id = row.get("product_id") or row.get("产品ID") or row.get("id")
        title = row.get("产品名称") or row.get("title") or row.get("name") or "商品"
        if not _is_gift_box_title(title):
            continue
        color = row.get("【颜色】") or row.get("spec") or row.get("color") or ""
        key = _clean_product_title(title)
        stock = row.get("库存数量") or row.get("inventory") or row.get("stock") or 0
        try:
            stock = int(float(stock))
        except (TypeError, ValueError):
            stock = 0
        if stock <= 0:
            continue
        warehouse = _normalize_warehouse_name(row.get("【仓库】") or row.get("warehouse_name") or row.get("warehouse") or "仓库")
        if key not in cards:
            cards[key] = {
                "product_id": product_id,
                "title": key,
                "piece_text": _piece_text(row.get("simple_desc") or row.get("simple_desc_text") or ""),
                "total_stock": 0,
                "status_text": "有库存",
                "colors": [],
                "_color_map": {},
            }
        cards[key]["total_stock"] += stock
        if not cards[key].get("piece_text"):
            cards[key]["piece_text"] = _piece_text(row.get("simple_desc") or "")
        color_key = str(color or "默认")
        if color_key not in cards[key]["_color_map"]:
            cards[key]["_color_map"][color_key] = {
                "product_id": product_id,
                "color": color_key,
                "total_stock": 0,
                "warehouses": {
                    "百鑫仓库": 0,
                    "店里仓库": 0,
                },
            }
            cards[key]["colors"].append(cards[key]["_color_map"][color_key])
        color_row = cards[key]["_color_map"][color_key]
        if not color_row.get("product_id") and product_id:
            color_row["product_id"] = product_id
        color_row["total_stock"] += stock
        color_row["warehouses"][warehouse] = color_row["warehouses"].get(warehouse, 0) + stock
    result = list(cards.values())
    for card in result:
        card.pop("_color_map", None)
        card["colors"] = [item for item in card.get("colors", []) if item.get("total_stock", 0) > 0]
        total = card["total_stock"]
        if total <= 0:
            card["status_text"] = "缺货"
        elif total <= 10:
            card["status_text"] = "库存紧张"
        else:
            card["status_text"] = "有库存"
    result.sort(key=lambda item: item.get("total_stock", 0), reverse=True)
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
    if not re.fullmatch(r"[A-Za-z0-9_@.\-]{3,64}", username or ""):
        return jsonify({"code": 400, "msg": "账号需为 3-64 位，可用字母、数字、下划线、邮箱符号"}), 400
    if len(password) < 6:
        return jsonify({"code": 400, "msg": "密码至少 6 位"}), 400
    try:
        _ensure_web_auth_table()
        if _web_auth_user_by_username(username):
            return jsonify({"code": 409, "msg": "账号已存在，请直接登录"}), 409
        now = int(time.time())
        user_count = _web_auth_db().query(f"SELECT COUNT(*) AS total FROM `{WEB_AUTH_TABLE}`")
        is_first_user = not user_count or int(user_count[0].get("total") or 0) == 0
        approval_status = "approved" if is_first_user else "pending"
        is_active = 1 if is_first_user else 0
        is_admin = 1 if is_first_user else 0
        affected = _web_auth_db().execute(
            f"""
            INSERT INTO `{WEB_AUTH_TABLE}`
                (username, password_hash, display_name, approval_status, is_admin, is_active, created_at, updated_at, last_login_at, approved_at, approved_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0)
            """,
            (username, generate_password_hash(password), display_name[:80], approval_status, is_admin, is_active, now, now, now if is_first_user else 0, now if is_first_user else 0),
        )
        if affected != 1:
            return jsonify({"code": 500, "msg": "注册失败，请稍后重试"}), 500
        user = _web_auth_user_by_username(username)
        if is_first_user:
            session["web_user_id"] = int(user["id"])
            session.permanent = True
        return jsonify({"code": 0, "data": {"user": {
            "id": user.get("id"),
            "username": user.get("username"),
            "display_name": user.get("display_name") or user.get("username"),
            "approval_status": user.get("approval_status"),
            "is_admin": int(user.get("is_admin") or 0),
        }, "pending": not is_first_user}})
    except Exception as e:
        logger.error(f"WebUI 注册异常: {e}")
        return jsonify({"code": 500, "msg": f"注册异常: {e}"}), 500


@app.route("/api/web-auth/login", methods=["POST"])
def web_auth_login():
    body = request.get_json(silent=True) or request.form.to_dict() or {}
    username = (body.get("username") or body.get("account") or "").strip()
    password = body.get("password") or ""
    if not username or not password:
        return jsonify({"code": 400, "msg": "请输入账号和密码"}), 400
    try:
        user = _web_auth_user_by_username(username)
        if not user or not check_password_hash(user.get("password_hash") or "", password):
            return jsonify({"code": 401, "msg": "账号或密码不正确"}), 401
        if str(user.get("approval_status") or "") != "approved" or int(user.get("is_active") or 0) != 1:
            return jsonify({"code": 403, "msg": "账号还在审批中，请联系管理员通过后再登录"}), 403
        now = int(time.time())
        _web_auth_db().execute(
            f"UPDATE `{WEB_AUTH_TABLE}` SET last_login_at=%s, updated_at=%s WHERE id=%s",
            (now, now, int(user["id"])),
        )
        session["web_user_id"] = int(user["id"])
        session.permanent = True
        return jsonify({"code": 0, "data": {"user": {
            "id": user.get("id"),
            "username": user.get("username"),
            "display_name": user.get("display_name") or user.get("username"),
            "approval_status": user.get("approval_status"),
            "is_admin": int(user.get("is_admin") or 0),
        }}})
    except Exception as e:
        logger.error(f"WebUI 登录异常: {e}")
        return jsonify({"code": 500, "msg": f"登录异常: {e}"}), 500


@app.route("/api/web-auth/logout", methods=["POST", "GET"])
def web_auth_logout():
    session.pop("web_user_id", None)
    if request.method == "GET":
        return redirect("/login")
    return jsonify({"code": 0, "data": {}})


@app.route("/api/web-auth/me", methods=["GET"])
def web_auth_me():
    user = _current_web_user()
    if not user:
        return jsonify({"code": 401, "msg": "未登录"}), 401
    return jsonify({"code": 0, "data": {"user": {
        "id": user.get("id"),
        "username": user.get("username"),
        "display_name": user.get("display_name") or user.get("username"),
        "approval_status": user.get("approval_status"),
        "is_admin": int(user.get("is_admin") or 0),
        "last_login_at": user.get("last_login_at"),
    }}})


@app.route("/api/web-auth/users", methods=["GET"])
def web_auth_users():
    if not _current_web_user_is_admin():
        return jsonify({"code": 403, "msg": "只有管理员可以审批账号"}), 403
    status = (request.args.get("status") or "pending").strip()
    allowed = {"pending", "approved", "rejected", "all"}
    if status not in allowed:
        status = "pending"
    _ensure_web_auth_table()
    sql = f"""
        SELECT id, username, display_name, approval_status, is_admin, is_active, created_at, last_login_at, approved_at, approved_by
        FROM `{WEB_AUTH_TABLE}`
    """
    params = ()
    if status != "all":
        sql += " WHERE approval_status=%s"
        params = (status,)
    sql += " ORDER BY id DESC LIMIT 100"
    rows = _web_auth_db().query(sql, params)
    return jsonify({"code": 0, "data": {"items": rows}})


@app.route("/api/web-auth/users/<int:user_id>/approve", methods=["POST"])
def web_auth_user_approve(user_id: int):
    admin = _current_web_user()
    if not admin or int(admin.get("is_admin") or 0) != 1:
        return jsonify({"code": 403, "msg": "只有管理员可以审批账号"}), 403
    now = int(time.time())
    affected = _web_auth_db().execute(
        f"""
        UPDATE `{WEB_AUTH_TABLE}`
        SET approval_status='approved', is_active=1, approved_at=%s, approved_by=%s, updated_at=%s
        WHERE id=%s
        """,
        (now, int(admin["id"]), now, int(user_id)),
    )
    return jsonify({"code": 0, "data": {"affected": affected}})


@app.route("/api/web-auth/users/<int:user_id>/reject", methods=["POST"])
def web_auth_user_reject(user_id: int):
    admin = _current_web_user()
    if not admin or int(admin.get("is_admin") or 0) != 1:
        return jsonify({"code": 403, "msg": "只有管理员可以审批账号"}), 403
    if int(admin["id"]) == int(user_id):
        return jsonify({"code": 400, "msg": "不能拒绝自己的账号"}), 400
    now = int(time.time())
    affected = _web_auth_db().execute(
        f"""
        UPDATE `{WEB_AUTH_TABLE}`
        SET approval_status='rejected', is_active=0, approved_at=%s, approved_by=%s, updated_at=%s
        WHERE id=%s
        """,
        (now, int(admin["id"]), now, int(user_id)),
    )
    return jsonify({"code": 0, "data": {"affected": affected}})


@app.route("/web", methods=["GET"])
def webui():
    """WebUI 聊天界面"""
    from src.channels.http_api.webui import get_webui_html
    response = Response(get_webui_html(), content_type="text/html; charset=utf-8")
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


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
        response = _agent.run(
            user_input=message,
            user_id=user_id,
            session_id=session_id,
        )
        return jsonify({
            "code": 0,
            "data": {
                "response": response,
                "session_id": session_id,
                "session": _session_snapshot(session_id),
            }
        })
    except Exception as e:
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
            response = _agent.run(
                user_input=message,
                user_id=user_id,
                session_id=session_id,
            )
            # 分 token 发送（按自然段落分割，避免单字碎片）
            for line in response.split("\n"):
                if line.strip():
                    token_text = line + "\n"
                else:
                    token_text = "\n"
                yield f"data: {json.dumps({'type': 'token', 'text': token_text}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'session_id': session_id}, ensure_ascii=False)}\n\n"
        except Exception as e:
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
    if not _allowed_image(file.filename):
        return jsonify({"code": 400, "msg": "只支持 png/jpg/jpeg/webp/bmp 图片"}), 400

    from src.core.session import SessionManager
    from src.core.tools.caller import get_tool_caller
    from src.core.nodes.image_workflow import process_single_image

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    original_name = secure_filename(file.filename) or "upload.jpg"
    suffix = Path(original_name).suffix.lower() or ".jpg"
    save_name = f"{int(time.time())}_{uuid.uuid4().hex[:10]}{suffix}"
    save_path = UPLOAD_DIR / save_name
    file.save(save_path)

    try:
        session = SessionManager(session_id)
        if session.has_pending() and session.get_pending_intent() == "bag_upload":
            if _agent is None:
                return jsonify({"code": 500, "msg": "Agent not initialized"}), 500
            preview_url = f"/api/images/file/{save_name}"
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
        return jsonify({"code": 0, "data": result})
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
    from src.core.tools.caller import get_tool_caller
    caller = get_tool_caller()
    limit = request.args.get("limit", 6, type=int)
    limit = max(1, min(limit, 20))

    sales = []
    workflows = []
    try:
        sales_result = caller.call("sales_list", page=1, page_size=limit)
        sales = _enrich_sales_rows(caller, _extract_list_rows(sales_result)[:limit])
    except Exception as e:
        logger.warning(f"最近销售单查询失败: {e}")

    try:
        workflow_result = caller.call("workflow_order_list", page=1, page_size=limit)
        workflows = _extract_list_rows(workflow_result)[:limit]
    except Exception as e:
        logger.warning(f"最近工作流订单查询失败: {e}")

    return jsonify({
        "code": 0,
        "data": {
            "sales": sales,
            "workflows": workflows,
        }
    })


@app.route("/api/dashboard/summary", methods=["GET"])
def dashboard_summary():
    """Live dashboard numbers for the WebUI workbench."""
    try:
        db = _db_client()
        now = time.time()
        local_now = time.localtime(now)
        day_start_tuple = (
            local_now.tm_year,
            local_now.tm_mon,
            local_now.tm_mday,
            0,
            0,
            0,
            local_now.tm_wday,
            local_now.tm_yday,
            local_now.tm_isdst,
        )
        start_ts = int(time.mktime(day_start_tuple))
        end_ts = start_ts + 86400
        sales_rows = db.query(
            """
            SELECT COUNT(*) AS count, COALESCE(SUM(COALESCE(total_price, price, 0)), 0) AS amount
            FROM sxo_plugins_erp_sales
            WHERE add_time >= %s AND add_time < %s
            """,
            (start_ts, end_ts),
        )
        workflow_rows = db.query(
            """
            SELECT COUNT(*) AS count
            FROM sxo_workflow_order
            WHERE COALESCE(order_type, 0) <> 1
               OR COALESCE(is_made, 0) <> 1
               OR COALESCE(is_delivered, 0) <> 1
            """,
        )
        sales = sales_rows[0] if sales_rows else {}
        workflow = workflow_rows[0] if workflow_rows else {}
        return jsonify({
            "code": 0,
            "data": {
                "today_sales_count": int(sales.get("count") or 0),
                "today_sales_amount": _as_money(sales.get("amount") or 0),
                "pending_workflow_count": int(workflow.get("count") or 0),
                "updated_at": int(now),
            }
        })
    except Exception as e:
        logger.warning(f"工作台概览查询失败: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


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
    page = max(1, page)
    page_size = max(1, min(page_size, 100))
    status = int(status_arg) if status_arg not in ("", None) else None

    try:
        cards, total = _db_sales_cards(keyword, page, page_size, status)
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


@app.route("/api/sales/<int:sales_id>/print-task", methods=["POST"])
def sales_print_task_api(sales_id: int):
    """Create a print task for a sales order without going through chat."""
    from src.core.tools.caller import get_tool_caller
    caller = get_tool_caller()
    if sales_id <= 0:
        return jsonify({"code": 400, "msg": "sales_id is required"}), 400
    try:
        result = caller.call("sales_print_task", sales_id=sales_id)
        if isinstance(result, dict):
            if result.get("error"):
                return jsonify({"code": 500, "msg": result.get("error")}), 500
            result_code = result.get("code")
            if result_code not in (None, 0, "0"):
                msg = result.get("msg") or result.get("message") or "打印任务创建失败"
                return jsonify({"code": result_code, "msg": msg, "data": result}), 500
        return jsonify({"code": 0, "data": result})
    except Exception as e:
        logger.error(f"sales print task failed: sales_id={sales_id}, error={e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/sales/<int:sales_id>/print-html", methods=["GET"])
def sales_print_html_api(sales_id: int):
    """Open the ERP printable sales-order HTML directly."""
    from src.engine.api_client import ERPSystemClient
    if sales_id <= 0:
        return Response("sales_id is required", status=400, mimetype="text/plain")
    try:
        html, content_type = ERPSystemClient().sales_print_html_raw(sales_id)
        if request.args.get("auto", "1") not in ("0", "false", "False"):
            html = html.replace(
                "</body>",
                "<script>window.addEventListener('load',function(){setTimeout(function(){window.print();},600);});</script></body>",
                1,
            )
        return Response(html, mimetype=content_type.split(";")[0] or "text/html")
    except Exception as e:
        logger.error(f"sales print html failed: sales_id={sales_id}, error={e}")
        return Response(f"打印页面打开失败：{e}", status=500, mimetype="text/plain")


@app.route("/api/sales/<int:sales_id>", methods=["DELETE"])
def sales_delete_api(sales_id: int):
    """Delete a sales order directly from the WebUI/mini app API."""
    from src.core.tools.caller import get_tool_caller
    caller = get_tool_caller()
    if sales_id <= 0:
        return jsonify({"code": 400, "msg": "sales_id is required"}), 400
    try:
        result = caller.call("sales_delete", ids=str(sales_id))
        if isinstance(result, dict) and result.get("error"):
            return jsonify({"code": 500, "msg": result.get("error")}), 500
        return jsonify({"code": 0, "data": result})
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
        rows = _db_client().search_inventory(
            keyword=keyword,
            only_in_stock=only_in_stock,
            limit=max(limit * 30, 1200),
        )
        cards = _inventory_cards(rows if isinstance(rows, list) else [], limit)
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
            cards = _inventory_cards(rows if isinstance(rows, list) else [], limit)
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


@app.route("/api/inventory/transfer", methods=["POST"])
def inventory_transfer_api():
    """Transfer inventory between warehouses for the UniApp inventory page."""
    from src.core.tools.caller import get_tool_caller
    caller = get_tool_caller()
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
    try:
        result = caller.call(
            "inventory_transfer",
            out_warehouse_id=out_warehouse_id,
            enter_warehouse_id=enter_warehouse_id,
            products=[{
                "product_id": int(product_id),
                "unit_id": int(body.get("unit_id") or 1),
                "transfer_number": quantity,
            }],
            note=(body.get("note") or f"小程序调货{f'（{color}）' if color else ''}").strip(),
        )
        if isinstance(result, dict) and result.get("error"):
            return jsonify({"code": 500, "msg": result.get("error")}), 500
        return jsonify({"code": 0, "data": result})
    except Exception as e:
        logger.error(f"库存调货失败: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/inventory/purchase", methods=["POST"])
def inventory_purchase_api():
    """Create an inventory inbound record for the UniApp inventory page."""
    from src.core.tools.caller import get_tool_caller
    caller = get_tool_caller()
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
        result = caller.call(
            "other_enter_add",
            warehouse_id=warehouse_id,
            products=[{
                "product_id": int(product_id),
                "unit_id": int(body.get("unit_id") or 1),
                "buy_number": quantity,
            }],
            note=(body.get("note") or f"小程序进货{f'（{color}）' if color else ''}").strip(),
        )
        if isinstance(result, dict) and result.get("error"):
            return jsonify({"code": 500, "msg": result.get("error")}), 500
        return jsonify({"code": 0, "data": result})
    except Exception as e:
        logger.error(f"库存进货失败: {e}")
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

        result = caller.call(
            "workflow_order_save",
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
        if order_images_provided:
            saved_id = body.get("id")
            if not saved_id and isinstance(result, dict):
                data = result.get("data") if isinstance(result.get("data"), dict) else {}
                saved_id = data.get("id") or data.get("order_id")
            if saved_id:
                try:
                    _db_client().execute(
                        "UPDATE sxo_workflow_order SET order_images = %s WHERE id = %s",
                        (json.dumps(order_images, ensure_ascii=False), int(saved_id)),
                    )
                except Exception as db_error:
                    logger.warning(f"宸ヤ綔娴佽鍗曞浘鐗囨暟鎹簱鍚屾澶辫触: {db_error}")
        return jsonify({"code": 0, "data": result.get("data", result) if isinstance(result, dict) else result})
    except Exception as e:
        logger.error(f"工作流订单保存失败: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/workflow/orders/<int:order_id>/status", methods=["POST"])
def workflow_order_status(order_id: int):
    """Update workflow order status fields."""
    from src.core.tools.caller import get_tool_caller
    caller = get_tool_caller()
    body = request.get_json() or {}
    field = body.get("field")
    value = body.get("value")
    if field not in ("is_made", "is_delivered", "order_type"):
        return jsonify({"code": 400, "msg": "field is invalid"}), 400
    try:
        result = caller.call("workflow_order_status_update", order_id=order_id, field=field, value=int(value or 0))
        if isinstance(result, dict) and result.get("code", 0) != 0:
            return jsonify({"code": result.get("code", 500), "msg": result.get("msg", "操作失败")}), 400
        return jsonify({"code": 0, "data": result.get("data", result) if isinstance(result, dict) else result})
    except Exception as e:
        logger.error(f"工作流订单状态更新失败: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/workflow/orders/<int:order_id>", methods=["DELETE"])
def workflow_order_delete_api(order_id: int):
    """Delete one workflow order."""
    from src.core.tools.caller import get_tool_caller
    caller = get_tool_caller()
    try:
        result = caller.call("workflow_order_delete", ids=str(order_id))
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
    from src.core.tools.caller import get_tool_caller
    caller = get_tool_caller()

    product_id = request.args.get("product_id")
    keyword = _normalize_inventory_keyword(request.args.get("keyword") or "")
    warehouse_id = request.args.get("warehouse_id")

    try:
        if product_id:
            results = caller.call("inventory_query_by_id", product_id=int(product_id))
        elif keyword:
            # 先搜索商品，再查库存
            products = caller.call("product_search", keyword=keyword)
            results = []
            for p in products[:5]:
                inv = caller.call("inventory_query_by_id", product_id=p["id"])
                results.extend(inv)
        elif warehouse_id:
            results = caller.call("inventory_query_by_warehouse", warehouse_id=int(warehouse_id))
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
    keyword = request.args.get("keyword", "")
    if not keyword:
        return jsonify({"code": 400, "msg": "keyword is required"}), 400

    try:
        rows = _db_client().search_products(keyword)
        results = [
            {
                "id": row.get("id"),
                "product_id": row.get("id"),
                "title": row.get("title") or "商品",
                "name": row.get("title") or "商品",
                "spec": row.get("spec") or "",
                "simple_desc": row.get("simple_desc") or "",
                "price": _as_money(row.get("price")),
                "min_price": _as_money(row.get("price")),
            }
            for row in rows
        ]
        return jsonify({"code": 0, "data": results[:100], "source": "db"})
    except Exception as e:
        logger.warning(f"商品数据库搜索失败，回退 API: {e}")

    try:
        from src.core.tools.caller import get_tool_caller
        caller = get_tool_caller()
        results = caller.call("product_search", keyword=keyword)
        return jsonify({"code": 0, "data": results, "source": "api"})
    except Exception as e:
        logger.error(f"商品搜索异常: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/product/list", methods=["GET"])
def product_list():
    """商品管理列表，优先走 MySQL 直查，写操作仍走 API。"""
    keyword = request.args.get("keyword") or ""
    page = request.args.get("page", default=1, type=int)
    page_size = max(1, min(request.args.get("page_size", default=20, type=int), 200))
    status = request.args.get("status", type=int) if request.args.get("status") not in (None, "") else None
    category_id = request.args.get("category_id", type=int) or None
    group = request.args.get("group", default=1, type=int) == 1

    try:
        items, total = _db_product_list(keyword, max(1, page), page_size, status, category_id, group)
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
        logger.warning(f"商品数据库列表失败，回退 API: {e}")

    try:
        from src.engine.api_client import ERPSystemClient
        client = ERPSystemClient()
        result = client.product_list(
            keyword=keyword or None,
            brand_name=request.args.get("brand_name") or None,
            status=request.args.get("status", type=int) if request.args.get("status") not in (None, "") else None,
            category_id=request.args.get("category_id", type=int) or None,
            group=request.args.get("group", default=1, type=int) == 1,
            page=max(1, page),
            page_size=page_size,
        )
        return jsonify(result)
    except Exception as e:
        logger.error(f"商品列表异常: {e}")
        return _api_exception_response(e)


@app.route("/api/product/categories", methods=["GET"])
def product_categories():
    """商品分类。"""
    try:
        categories = _db_product_categories()
        total_rows = _db_client().query(
            "SELECT COUNT(DISTINCT COALESCE(NULLIF(group_key, ''), CAST(id AS CHAR))) AS total FROM sxo_plugins_erp_product"
        )
        total = int(total_rows[0].get("total") or 0) if total_rows else 0
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


@app.route("/api/product/options", methods=["GET"])
def product_options():
    """商品编辑基础数据。"""
    from src.engine.api_client import ERPSystemClient

    try:
        product_id = request.args.get("id", type=int)
        result = ERPSystemClient().product_save_info(product_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"商品基础数据异常: {e}")
        return _api_exception_response(e)


@app.route("/api/product/<int:product_id>", methods=["GET"])
def product_detail_api(product_id: int):
    """商品详情。"""
    from src.engine.api_client import ERPSystemClient

    try:
        result = ERPSystemClient().product_detail(product_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"商品详情异常: {e}")
        return _api_exception_response(e)


@app.route("/api/product/save", methods=["POST"])
def product_save_api():
    """创建/编辑商品。"""
    from src.engine.api_client import ERPSystemClient

    try:
        body = request.get_json(silent=True)
        if body is None:
            body = request.form.to_dict(flat=True)
        result = ERPSystemClient().product_save(body or {})
        return jsonify(result)
    except Exception as e:
        logger.error(f"商品保存异常: {e}")
        return _api_exception_response(e)


@app.route("/api/product/delete", methods=["POST"])
def product_delete_api():
    """删除商品。"""
    from src.engine.api_client import ERPSystemClient

    try:
        body = request.get_json(silent=True)
        if body is None:
            body = request.form.to_dict(flat=True)
        ids = (body or {}).get("ids")
        if not ids:
            return jsonify({"code": 400, "msg": "缺少商品ID"}), 400
        result = ERPSystemClient().product_delete(ids)
        return jsonify(result)
    except Exception as e:
        logger.error(f"商品删除异常: {e}")
        return _api_exception_response(e)


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
        suffix = Path(filename).suffix.lower() or ".jpg"
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
        return jsonify({"code": 0, "data": result})
    except Exception as e:
        logger.error(f"商品图片上传异常: {e}")
        return _api_exception_response(e)


@app.route("/api/product/<int:product_id>/shelves", methods=["POST"])
def product_shelves_api(product_id: int):
    """同步商城商品上下架。"""
    from src.engine.api_client import ERPSystemClient

    try:
        body = request.get_json(silent=True) or request.form.to_dict(flat=True) or {}
        state = int(body.get("state", 0))
        result = ERPSystemClient().product_shelves_update(product_id, state)
        return jsonify(result)
    except Exception as e:
        logger.error(f"商品上下架异常: {e}")
        return _api_exception_response(e)


@app.route("/api/customer/list", methods=["GET"])
def customer_list():
    """
    客户列表接口
    GET /api/customer/list?keyword=xxx
    """
    keyword = request.args.get("keyword", "")

    try:
        return jsonify({"code": 0, "data": _db_customer_list(keyword), "source": "db"})
    except Exception as e:
        logger.warning(f"客户数据库查询失败，回退 API: {e}")

    try:
        from src.core.tools.caller import get_tool_caller
        caller = get_tool_caller()
        results = caller.call("customer_query", keyword=keyword)
        return jsonify({"code": 0, "data": results, "source": "api"})
    except Exception as e:
        logger.error(f"客户列表查询异常: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/warehouse/list", methods=["GET"])
def warehouse_list():
    """
    仓库列表接口
    GET /api/warehouse/list
    """
    from src.core.tools.caller import get_tool_caller
    caller = get_tool_caller()

    try:
        results = caller.call("warehouse_list")
        return jsonify({"code": 0, "data": results})
    except Exception as e:
        logger.error(f"仓库列表查询异常: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/customer/price", methods=["GET"])
def customer_price():
    """
    客户历史成交价查询
    GET /api/customer/price?customer_id=1&product_id=123
    """
    from src.core.tools.caller import get_tool_caller
    caller = get_tool_caller()

    customer_id = request.args.get("customer_id", type=int)
    product_id = request.args.get("product_id", type=int)

    if not customer_id or not product_id:
        return jsonify({"code": 400, "msg": "customer_id and product_id are required"}), 400

    try:
        price = caller.call("sales_history_price", customer_id=customer_id, product_id=product_id)
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
    from src.core.tools.caller import get_tool_caller
    caller = get_tool_caller()

    product_id = request.args.get("product_id", type=int)
    if not product_id:
        return jsonify({"code": 400, "msg": "product_id is required"}), 400

    try:
        price = caller.call("get_product_price", product_id=product_id)
        return jsonify({"code": 0, "data": {"price": price}})
    except Exception as e:
        logger.error(f"零售价查询异常: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


def _normalize_sales_add_products(products: list[dict]) -> list[dict]:
    """Fill the ERP product base unit before SalesAdd."""
    from src.engine.api_client import ERPSystemClient

    client = ERPSystemClient()
    normalized = []
    detail_cache: dict[int, dict] = {}
    for item in products:
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
            try:
                raw = client.product_detail(pid)
                data = raw.get("data") if isinstance(raw, dict) else {}
                detail = data.get("data") if isinstance(data, dict) and isinstance(data.get("data"), dict) else data
            except Exception as e:
                logger.warning(f"开单商品单位兜底查询失败: product_id={pid}, error={e}")
                detail = {}
            detail_cache[pid] = detail if isinstance(detail, dict) else {}
        base_rows = detail_cache[pid].get("base") if isinstance(detail_cache[pid].get("base"), list) else []
        selected_base = None
        current_unit_id = item.get("unit_id")
        for base in base_rows:
            try:
                if current_unit_id and int(base.get("unit_id") or 0) == int(current_unit_id):
                    selected_base = base
                    break
            except (TypeError, ValueError):
                continue
        selected_base = selected_base or (base_rows[0] if base_rows else None)
        next_item = dict(item)
        if selected_base and selected_base.get("unit_id"):
            next_item["unit_id"] = int(selected_base["unit_id"])
        elif not next_item.get("unit_id"):
            next_item["unit_id"] = 1
        normalized.append(next_item)
    return normalized


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
    from src.core.tools.caller import get_tool_caller
    caller = get_tool_caller()

    body = request.get_json()
    customer_id = body.get("customer_id")
    warehouse_id = body.get("warehouse_id", 2)
    products = body.get("products", [])
    create_time = body.get("create_time") or ""

    if not customer_id or not products:
        return jsonify({"code": 400, "msg": "customer_id and products are required"}), 400

    try:
        products = _normalize_sales_add_products(products)
        result = caller.call(
            "sales_add",
            customer_id=customer_id,
            warehouse_id=warehouse_id,
            products=products,
            create_time=create_time,
        )
        if isinstance(result, dict) and result.get("error"):
            return jsonify({"code": 500, "msg": result.get("error"), "data": result}), 500
        return jsonify({"code": 0, "data": result})
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
    """Login with the existing ShopXO mall account and return its token."""
    body = request.get_json(silent=True) or request.form.to_dict() or {}
    accounts = (body.get("accounts") or body.get("username") or body.get("mobile") or body.get("email") or "").strip()
    password = body.get("pwd") or body.get("password") or ""
    login_type = (body.get("type") or "username").strip()
    if not accounts:
        return jsonify({"code": 400, "msg": "请输入商城账号"}), 400
    if login_type == "username" and not password:
        return jsonify({"code": 400, "msg": "请输入商城密码"}), 400

    payload = {
        "type": login_type,
        "accounts": accounts,
        "pwd": password,
    }
    if body.get("verify"):
        payload["verify"] = body.get("verify")
    try:
        result = _shopxo_post("user", "login", payload, uuid_value=body.get("uuid") or "")
        if int(result.get("code", -1)) != 0:
            return jsonify({"code": 401, "msg": result.get("msg") or "商城登录失败"}), 401
        data = result.get("data") if isinstance(result.get("data"), dict) else {}
        token = _nested_token(data) or _nested_token(result)
        if not token:
            user = _shopxo_user_by_account(accounts)
            if not user:
                logger.warning(f"商城登录成功但无法解析 token/user: data_keys={list(data.keys())}")
                return jsonify({"code": 500, "msg": "商城登录成功但未返回 token"}), 500
            token = user.get("token", "")
        else:
            user = _normalize_shopxo_user(data, token)
        SHOPXO_AUTH_CACHE[token] = (time.time() + SHOPXO_AUTH_CACHE_TTL, user)
        return jsonify({"code": 0, "data": {"token": token, "user": user}})
    except Exception as e:
        logger.error(f"商城登录异常: {e}")
        return jsonify({"code": 500, "msg": f"商城登录异常: {e}"}), 500


@app.route("/api/auth/wechat-quick-login", methods=["POST"])
def auth_wechat_quick_login():
    """Login through ShopXO's mini-program auth flow, avoiding password captcha."""
    body = request.get_json(silent=True) or request.form.to_dict() or {}
    authcode = (body.get("authcode") or body.get("code") or "").strip()
    if not authcode:
        return jsonify({"code": 400, "msg": "缺少微信登录 code"}), 400
    miniapp_appid = (
        body.get("appid")
        or os.environ.get("SHOPXO_MINIAPP_AUTH_APPID")
        or "wx6fcdcf7f0f4cd033"
    )

    try:
        result = _shopxo_post("user", "appminiuserauth", {"authcode": authcode, "appid": miniapp_appid})
        if int(result.get("code", -1)) != 0:
            return jsonify({"code": 401, "msg": result.get("msg") or "微信快捷登录失败"}), 401

        data = result.get("data") if isinstance(result.get("data"), dict) else {}
        user_data = data.get("user") if isinstance(data.get("user"), dict) else data
        token = _nested_token(data) or _nested_token(result)
        if not token:
            token = f"sj_local_{uuid.uuid4().hex}"

        user = _normalize_shopxo_user(user_data, token)
        if not user.get("id") and isinstance(data, dict):
            user = _normalize_shopxo_user(data, token)
        SHOPXO_AUTH_CACHE[token] = (time.time() + SHOPXO_AUTH_CACHE_TTL, user)
        return jsonify({"code": 0, "data": {"token": token, "user": user}})
    except Exception as e:
        logger.error(f"微信快捷登录异常: {e}")
        return jsonify({"code": 500, "msg": f"微信快捷登录异常: {e}"}), 500


@app.route("/api/auth/captcha", methods=["GET"])
def auth_captcha():
    """Proxy the ShopXO image captcha so the miniapp can keep using the sjagent API host."""
    uuid_value = (request.args.get("uuid") or "").strip() or f"sjagent_{uuid.uuid4().hex}"
    verify_type = (request.args.get("type") or "user_login").strip()
    try:
        resp = _shopxo_get(
            "user",
            "userverifyentry",
            uuid_value=uuid_value,
            extra_params={
                "type": verify_type,
                "t": request.args.get("t") or str(int(time.time() * 1000)),
            },
        )
        content_type = "image/gif" if resp.content.startswith((b"GIF87a", b"GIF89a")) else resp.headers.get("Content-Type", "image/gif")
        response = Response(resp.content, content_type=content_type)
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        return response
    except Exception as e:
        logger.error(f"商城验证码获取异常: {e}")
        return jsonify({"code": 500, "msg": f"商城验证码获取异常: {e}"}), 500


@app.route("/api/auth/me", methods=["GET", "POST"])
def auth_me():
    """Validate the current ShopXO token and return normalized user info."""
    token = _auth_token_from_request()
    if not token:
        return jsonify({"code": 401, "msg": "缺少登录 token"}), 401
    try:
        user = _verify_shopxo_token(token, force=request.args.get("force") in ("1", "true", "True"))
        if not user:
            return jsonify({"code": 401, "msg": "登录已失效，请重新登录"}), 401
        return jsonify({"code": 0, "data": {"token": token, "user": user}})
    except Exception as e:
        logger.error(f"商城用户信息校验异常: {e}")
        return jsonify({"code": 500, "msg": f"商城用户信息校验异常: {e}"}), 500


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
