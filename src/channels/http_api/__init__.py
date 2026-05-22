"""
HTTP API 渠道（预留 WebUI 和外部调用）
提供 RESTful API 供前端或外部系统调用 Agent
"""
import json
import hmac
import hashlib
import os
import re
import secrets
import threading
import uuid
import time
from datetime import datetime, timedelta
from pathlib import Path
from flask import Flask, request, jsonify, Response, send_from_directory, session, redirect
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from src.core.agent import Agent
from src.engine.exceptions import DBError
from src.core.features import feature_enabled
from src.core.product_name import PRODUCT_SPECS, normalize_product_name
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
ALLOWED_BAG_ARCHIVE_EXTENSIONS = {"zip"}
ROLE_CODE_TO_LABEL = {
    "admin": "管理员",
    "staff": "员工",
    "customer": "客户",
    "guest": "访客",
}
ROLE_LABEL_TO_CODE = {
    "管理员": "admin",
    "老板": "admin",
    "员工": "staff",
    "客户": "customer",
    "访客": "guest",
}
PERMISSION_CATALOG = {"开单", "删单", "打印", "查看库存", "调库存", "盘点", "调拨", "调余额", "图片上传", "图片绑定", "设置", "查看"}
FIXED_ROLE_PERMISSIONS = {
    "admin": set(PERMISSION_CATALOG),
    "staff": {"开单", "打印", "查看库存", "图片上传", "图片绑定", "查看"},
    "customer": {"查看"},
    "guest": set(),
}


def _role_code(value) -> str:
    role = str(value or "").strip()
    if not role:
        return "guest"
    role = ROLE_LABEL_TO_CODE.get(role, role)
    legacy_staff_roles = {"warehouse", "designer"}
    if role in legacy_staff_roles:
        return "staff"
    if role == "readonly":
        return "guest"
    return role if role in ROLE_CODE_TO_LABEL else "guest"


def _role_label(value) -> str:
    return ROLE_CODE_TO_LABEL.get(_role_code(value), "访客")


def _api_exception_response(e: Exception):
    response = getattr(e, "response", None)
    if isinstance(response, dict) and response:
        return jsonify(response)
    if isinstance(e, DBError):
        return jsonify({"code": 400, "msg": str(e)}), 400
    return jsonify({"code": 500, "msg": str(e)}), 500


def _web_auth_db():
    from src.engine.native_db import get_native_db_client
    return get_native_db_client()


_NATIVE_AUTH_READY = False
_NATIVE_AUTH_LOCK = threading.Lock()
NATIVE_AUTH_CACHE: dict[str, tuple[float, dict]] = {}
NATIVE_AUTH_CACHE_TTL = 60


def _native_phone_digits(value) -> str:
    return re.sub(r"\D+", "", str(value or ""))


def _token_hash(token: str) -> str:
    return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()


def _ensure_native_auth_tables():
    global _NATIVE_AUTH_READY
    if _NATIVE_AUTH_READY:
        return
    with _NATIVE_AUTH_LOCK:
        if _NATIVE_AUTH_READY:
            return
        db = _web_auth_db()
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS auth_session (
                id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                user_id BIGINT UNSIGNED NOT NULL,
                token_hash CHAR(64) NOT NULL,
                client_type VARCHAR(30) NULL,
                ip VARCHAR(80) NULL,
                user_agent VARCHAR(500) NULL,
                expires_at DATETIME NOT NULL,
                revoked_at DATETIME NULL,
                created_at DATETIME NOT NULL,
                PRIMARY KEY (id),
                UNIQUE KEY uk_auth_session_token_hash (token_hash),
                KEY idx_auth_session_user (user_id),
                KEY idx_auth_session_expires (expires_at),
                KEY idx_auth_session_revoked (revoked_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
        )
        _NATIVE_AUTH_READY = True


def _native_user_public(row: dict | None, token: str = "") -> dict:
    if not isinstance(row, dict):
        row = {}
    role = _role_code(row.get("role"))
    is_admin = int(row.get("is_admin") or 0) == 1 or role == "admin"
    user_id = row.get("id") or row.get("user_id") or ""
    display_name = (
        row.get("display_name")
        or row.get("nickname")
        or row.get("username")
        or row.get("phone")
        or (f"用户{user_id}" if user_id else "北极星用户")
    )
    return {
        "id": user_id,
        "user_id": user_id,
        "token": token,
        "display_name": display_name,
        "nickname": row.get("nickname") or display_name,
        "username": row.get("username") or "",
        "mobile": row.get("phone") or "",
        "phone": row.get("phone") or "",
        "email": row.get("email") or "",
        "avatar": row.get("avatar") or "",
        "role": role,
        "role_text": _role_label(role),
        "linked_party_id": row.get("linked_party_id"),
        "linked_party_name": row.get("linked_party_name") or "",
        "approval_status": row.get("approval_status") or "",
        "is_active": int(row.get("is_active") or 0),
        "is_admin": is_admin,
        "miniapp_allowed": is_admin or role == "staff",
        "source": "native",
        "raw": row,
    }


def _native_user_by_id(user_id: int) -> dict | None:
    rows = _web_auth_db().query(
        """
        SELECT u.*, p.name AS linked_party_name
        FROM auth_user u
        LEFT JOIN party p ON p.id = u.linked_party_id
        WHERE u.id=%s
        LIMIT 1
        """,
        (int(user_id),),
    )
    return rows[0] if rows else None


def _native_user_by_account(account: str) -> dict | None:
    account = str(account or "").strip()
    if not account:
        return None
    phone = _native_phone_digits(account)
    rows = _web_auth_db().query(
        """
        SELECT u.*, p.name AS linked_party_name
        FROM auth_user u
        LEFT JOIN party p ON p.id = u.linked_party_id
        WHERE u.username=%s
           OR u.phone=%s
           OR EXISTS (
                SELECT 1
                FROM auth_identity ai
                WHERE ai.user_id=u.id
                  AND ai.is_enabled=1
                  AND ai.external_user_id IN (%s, %s)
           )
        ORDER BY u.is_admin DESC, u.id ASC
        LIMIT 1
        """,
        (account, phone or account, account, phone or account),
    )
    return rows[0] if rows else None


def _native_user_by_identity(provider: str, external_id: str) -> dict | None:
    rows = _web_auth_db().query(
        """
        SELECT u.*, p.name AS linked_party_name
        FROM auth_identity ai
        JOIN auth_user u ON u.id = ai.user_id
        LEFT JOIN party p ON p.id = u.linked_party_id
        WHERE ai.provider=%s
          AND ai.external_user_id=%s
          AND ai.is_enabled=1
        LIMIT 1
        """,
        (provider, external_id),
    )
    return rows[0] if rows else None


def _find_party_id_by_phone(phone: str) -> int | None:
    digits = _native_phone_digits(phone)
    if not digits:
        return None
    rows = _web_auth_db().query(
        """
        SELECT id
        FROM party
        WHERE phone_normalized=%s OR phone=%s
        ORDER BY id ASC
        LIMIT 1
        """,
        (digits, phone),
    )
    return int(rows[0]["id"]) if rows else None


def _issue_native_session(user_id: int, client_type: str = "miniapp") -> str:
    _ensure_native_auth_tables()
    token = "sj_" + secrets.token_urlsafe(32)
    now = datetime.now()
    expires_at = now + timedelta(days=30)
    db = _web_auth_db()
    db.execute(
        """
        INSERT INTO auth_session
            (user_id, token_hash, client_type, ip, user_agent, expires_at, created_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s)
        """,
        (
            int(user_id),
            _token_hash(token),
            client_type[:30],
            (request.headers.get("X-Forwarded-For") or request.remote_addr or "")[:80],
            (request.headers.get("User-Agent") or "")[:500],
            expires_at.strftime("%Y-%m-%d %H:%M:%S"),
            now.strftime("%Y-%m-%d %H:%M:%S"),
        ),
    )
    db.execute("DELETE FROM auth_session WHERE expires_at < NOW() OR revoked_at IS NOT NULL")
    return token


def _verify_native_token(token: str, force: bool = False) -> dict | None:
    if not token:
        return None
    now = time.time()
    cached = NATIVE_AUTH_CACHE.get(token)
    if cached and not force and cached[0] > now:
        return cached[1]
    _ensure_native_auth_tables()
    rows = _web_auth_db().query(
        """
        SELECT u.*, p.name AS linked_party_name
        FROM auth_session s
        JOIN auth_user u ON u.id = s.user_id
        LEFT JOIN party p ON p.id = u.linked_party_id
        WHERE s.token_hash=%s
          AND s.revoked_at IS NULL
          AND s.expires_at > NOW()
        LIMIT 1
        """,
        (_token_hash(token),),
    )
    if not rows:
        NATIVE_AUTH_CACHE.pop(token, None)
        return None
    row = rows[0]
    if int(row.get("is_active") or 0) != 1 or str(row.get("approval_status") or "") != "approved":
        NATIVE_AUTH_CACHE.pop(token, None)
        return None
    user = _native_user_public(row, token=token)
    NATIVE_AUTH_CACHE[token] = (now + NATIVE_AUTH_CACHE_TTL, user)
    return user


def _native_user_can_access_miniapp(user: dict | None) -> bool:
    return bool(isinstance(user, dict) and user.get("miniapp_allowed") is True)


def _wechat_session_from_code(authcode: str, appid: str) -> dict:
    secret = os.environ.get("WECHAT_MINIAPP_SECRET") or os.environ.get("WX_MINIAPP_SECRET") or ""
    if not appid or not secret:
        return {"code": 400, "msg": "未配置微信小程序 appid/secret，不能用 code 换 openid"}
    import requests

    resp = requests.get(
        "https://api.weixin.qq.com/sns/jscode2session",
        params={
            "appid": appid,
            "secret": secret,
            "js_code": authcode,
            "grant_type": "authorization_code",
        },
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, dict):
        return {"code": 500, "msg": "微信登录返回格式异常"}
    if data.get("errcode"):
        return {"code": 401, "msg": data.get("errmsg") or "微信登录失败", "raw": data}
    return {"code": 0, "data": data}


def _upsert_wechat_user(openid: str, unionid: str = "", profile: dict | None = None) -> dict:
    openid = str(openid or "").strip()
    unionid = str(unionid or "").strip()
    profile = profile if isinstance(profile, dict) else {}
    if not openid:
        raise ValueError("缺少微信 openid")
    existing = _native_user_by_identity("wechat", openid)
    if existing:
        return existing

    display_name = (
        profile.get("nickName")
        or profile.get("nickname")
        or profile.get("display_name")
        or "微信用户"
    )
    username = f"wechat:{hashlib.sha1(openid.encode('utf-8')).hexdigest()[:24]}"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _web_auth_db().transaction() as cursor:
        cursor.execute(
            """
            INSERT INTO auth_user
                (username, password_hash, display_name, phone, role, linked_party_id,
                 approval_status, is_active, is_admin, created_at, updated_at)
            VALUES (%s,NULL,%s,NULL,'customer',NULL,'pending',1,0,%s,%s)
            ON DUPLICATE KEY UPDATE display_name=VALUES(display_name), updated_at=VALUES(updated_at)
            """,
            (username, str(display_name)[:80], now, now),
        )
        cursor.execute("SELECT id FROM auth_user WHERE username=%s LIMIT 1", (username,))
        row = cursor.fetchone()
        user_id = int(row["id"])
        cursor.execute(
            """
            INSERT INTO auth_identity
                (user_id, provider, external_user_id, openid, unionid, raw_profile, is_enabled, created_at, updated_at)
            VALUES (%s,'wechat',%s,%s,%s,%s,1,%s,%s)
            ON DUPLICATE KEY UPDATE
                user_id=VALUES(user_id),
                openid=VALUES(openid),
                unionid=VALUES(unionid),
                raw_profile=VALUES(raw_profile),
                is_enabled=1,
                updated_at=VALUES(updated_at)
            """,
            (user_id, openid, openid, unionid or None, json.dumps(profile, ensure_ascii=False), now, now),
        )
    native = _native_user_by_id(user_id)
    return native or {"id": user_id, "username": username, "display_name": display_name, "role": "customer", "approval_status": "pending", "is_active": 1, "is_admin": 0}


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
    user = _web_auth_user_by_id(int(user_id))
    if not user or int(user.get("is_active") or 0) != 1 or str(user.get("approval_status") or "") != "approved":
        session.pop("auth_user_id", None)
        session.pop("web_user_id", None)
        session.pop("native_user_id", None)
        return None
    user["native_user_id"] = int(user.get("id") or 0) or None
    session["native_user_id"] = user["native_user_id"]
    return user


def _current_web_user_is_admin() -> bool:
    user = _current_web_user()
    return bool(user and int(user.get("is_admin") or 0) == 1)


def _web_auth_user_payload(user: dict | None) -> dict:
    if not isinstance(user, dict):
        user = {}
    user_id = int(user.get("id") or user.get("user_id") or 0)
    return {
        "id": user_id,
        "native_user_id": user_id,
        "username": user.get("username") or "",
        "display_name": user.get("display_name") or user.get("username") or "",
        "role": _role_code(user.get("role")),
        "role_text": _role_label(user.get("role")),
        "approval_status": user.get("approval_status") or "",
        "is_admin": int(user.get("is_admin") or 0),
        "is_active": int(user.get("is_active") or 0),
        "last_login_at": str(user.get("last_login_at") or ""),
    }


def _web_user_can_access_webui(user: dict | None) -> bool:
    if not isinstance(user, dict):
        return False
    if int(user.get("is_admin") or 0) == 1:
        return True
    return _role_code(user.get("role")) in {"admin", "staff"}


def _request_user_for_permission() -> dict | None:
    native_user = getattr(request, "native_user", None)
    if isinstance(native_user, dict) and native_user.get("id"):
        return native_user
    return _current_web_user()


def _has_permission(permission: str, user: dict | None = None) -> bool:
    user = user if isinstance(user, dict) else _request_user_for_permission()
    if not isinstance(user, dict):
        return False
    role = _role_code(user.get("role"))
    if int(user.get("is_admin") or 0) == 1:
        role = "admin"
    return permission in FIXED_ROLE_PERMISSIONS.get(role, set())


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
    ({"POST"}, re.compile(r"^/api/customers/\d+/balance$"), "调余额"),
    ({"POST"}, re.compile(r"^/api/product/upload$"), "图片上传"),
    ({"POST"}, re.compile(r"^/api/workflow/images/upload$"), "图片上传"),
    ({"POST", "DELETE"}, re.compile(r"^/api/product/media/\d+$"), "图片绑定"),
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
    rows = _native_db().query(
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


def _db_sales_cards(keyword: str, page: int, page_size: int, status: int | None = None) -> tuple[list[dict], int]:
    return _native_db().sales_cards(keyword=keyword, page=page, page_size=page_size, status=status)

def _db_workflow_orders(keyword: str, page: int, page_size: int, status_filter: str = "active") -> tuple[list[dict], int]:
    return _native_db().workflow_orders(keyword=keyword, page=page, page_size=page_size, status_filter=status_filter)

def _db_product_list(
    keyword: str,
    page: int,
    page_size: int,
    status=None,
    category_id: int | None = None,
    group: bool = False,
    category_ids: list[int] | None = None,
) -> tuple[list[dict], int]:
    return _native_db().product_list(
        keyword=keyword,
        page=page,
        page_size=page_size,
        status=status,
        category_id=category_id,
        group=group,
        category_ids=category_ids,
    )

def _db_product_categories() -> list[dict]:
    return _native_db().product_categories()

def _db_customer_list(keyword: str, limit: int = 50) -> list[dict]:
    return _native_db().customer_list(keyword, limit=limit)

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
    if not re.fullmatch(r"[A-Za-z0-9_@.\-]{3,80}", username or ""):
        return jsonify({"code": 400, "msg": "账号需为 3-80 位，可用字母、数字、下划线、邮箱符号"}), 400
    if len(password) < 6:
        return jsonify({"code": 400, "msg": "密码至少 6 位"}), 400
    try:
        if _web_auth_user_by_username(username):
            return jsonify({"code": 409, "msg": "账号已存在，请直接登录"}), 409
        admin_rows = _web_auth_db().query(
            """
            SELECT COUNT(*) AS total
            FROM auth_user
            WHERE is_admin=1 OR role IN ('admin','staff')
            """
        )
        is_first_user = not admin_rows or int(admin_rows[0].get("total") or 0) == 0
        approval_status = "approved" if is_first_user else "pending"
        is_active = 1 if is_first_user else 0
        is_admin = 1 if is_first_user else 0
        role = "admin" if is_first_user else "staff"
        phone = _native_phone_digits(username)
        linked_party_id = _find_party_id_by_phone(phone) if phone else None
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        affected = _web_auth_db().execute(
            """
            INSERT INTO auth_user
                (username, password_hash, display_name, phone, role, linked_party_id,
                 approval_status, is_active, is_admin, last_login_at, created_at, updated_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                username,
                generate_password_hash(password),
                display_name[:80],
                phone or None,
                role,
                linked_party_id,
                approval_status,
                is_active,
                is_admin,
                now if is_first_user else None,
                now,
                now,
            ),
        )
        if affected != 1:
            return jsonify({"code": 500, "msg": "注册失败，请稍后重试"}), 500
        user = _web_auth_user_by_username(username)
        if is_first_user:
            session["auth_user_id"] = int(user["id"])
            session["native_user_id"] = int(user["id"])
            session.permanent = True
        return jsonify({"code": 0, "data": {"user": _web_auth_user_payload(user), "pending": not is_first_user}})
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
        if not _web_user_can_access_webui(user):
            return jsonify({"code": 403, "msg": "当前账号没有后台访问权限"}), 403
        _web_auth_db().execute(
            "UPDATE auth_user SET last_login_at=NOW(), updated_at=NOW() WHERE id=%s",
            (int(user["id"]),),
        )
        user = _web_auth_user_by_id(int(user["id"])) or user
        session["auth_user_id"] = int(user["id"])
        session["native_user_id"] = int(user["id"])
        session.permanent = True
        return jsonify({"code": 0, "data": {"user": _web_auth_user_payload(user)}})
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
    status = (request.args.get("status") or "pending").strip()
    allowed = {"pending", "approved", "rejected", "all"}
    if status not in allowed:
        status = "pending"
    sql = """
        SELECT id, username, display_name, role, approval_status, is_admin, is_active, created_at, last_login_at
        FROM auth_user
        WHERE (is_admin=1 OR role IN ('admin','staff'))
    """
    params: list = []
    if status != "all":
        sql += " AND approval_status=%s"
        params.append(status)
    sql += " ORDER BY id DESC LIMIT 100"
    rows = _web_auth_db().query(sql, params)
    return jsonify({"code": 0, "data": {"items": rows}})


@app.route("/api/web-auth/users/<int:user_id>/approve", methods=["POST"])
def web_auth_user_approve(user_id: int):
    admin = _current_web_user()
    if not admin or int(admin.get("is_admin") or 0) != 1:
        return jsonify({"code": 403, "msg": "只有管理员可以审批账号"}), 403
    affected = _web_auth_db().execute(
        """
        UPDATE auth_user
        SET approval_status='approved', is_active=1, updated_at=NOW()
        WHERE id=%s
        """,
        (int(user_id),),
    )
    return jsonify({"code": 0, "data": {"affected": affected}})


@app.route("/api/web-auth/users/<int:user_id>/reject", methods=["POST"])
def web_auth_user_reject(user_id: int):
    admin = _current_web_user()
    if not admin or int(admin.get("is_admin") or 0) != 1:
        return jsonify({"code": 403, "msg": "只有管理员可以审批账号"}), 403
    if int(admin["id"]) == int(user_id):
        return jsonify({"code": 400, "msg": "不能拒绝自己的账号"}), 400
    affected = _web_auth_db().execute(
        """
        UPDATE auth_user
        SET approval_status='rejected', is_active=0, updated_at=NOW()
        WHERE id=%s
        """,
        (int(user_id),),
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
    db = _native_db()
    now = time.time()
    summary = db.dashboard_summary()
    sales_cards, _sales_total = _db_sales_cards("", 1, 4, None)
    workflow_cards, _workflow_total = _db_workflow_orders("", 1, 6, "active")
    inventory_rows = db.search_inventory(keyword="", only_in_stock=True, limit=900)
    inventory_cards = _inventory_cards(inventory_rows if isinstance(inventory_rows, list) else [], 12)
    low_inventory = [card for card in inventory_cards if int(card.get("total_stock") or 0) <= 30][:4]
    if not low_inventory:
        low_inventory = inventory_cards[-4:]

    delivery_rows = db.query(
        """
        SELECT COUNT(*) AS count
        FROM workflow_order
        WHERE deleted_at IS NULL AND COALESCE(is_delivered, 0) <> 1
        """
    )
    delivery = delivery_rows[0] if delivery_rows else {}

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
        "pending_delivery_count": int(delivery.get("count") or 0),
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
        return jsonify({"code": 0, "data": _native_db().dashboard_summary()})
    except Exception as e:
        logger.warning(f"?????????: {e}")
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


@app.route("/api/settings/print/sales", methods=["GET"])
def sales_print_settings_api():
    """Sales-order print settings stored in sjagent_core."""
    try:
        return jsonify(_native_db().sales_print_settings())
    except Exception as e:
        logger.error(f"sales print settings failed: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/settings/number/sku", methods=["GET"])
def sku_number_settings_api():
    """Product SKU number settings stored in sjagent_core."""
    try:
        return jsonify(_native_db().sku_number_settings())
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
        result = _native_db().save_sku_number_settings(payload, operator_user_id=operator_user_id)
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
            return jsonify(_native_db().system_setting(clean_key))
        payload = request.get_json(silent=True) or {}
        user = _current_web_user() or {}
        operator_user_id = user.get("native_user_id") or user.get("id")
        result = _native_db().save_system_setting(clean_key, payload, operator_user_id=operator_user_id)
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
        result = _native_db().save_sales_print_settings(payload)
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
        result = _native_db().create_sales_print_task(
            sales_id=sales_id,
            template_id=payload.get("template_id"),
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
        result = _native_db().sales_print_task_list(page=page, page_size=page_size)
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
        html = _native_db().sales_print_html(int(row.get("document_id")), auto_print=auto_print)
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
        result = _native_db().sales_print_task_done(int(resolved_id))
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
        _native_db().execute(
            "UPDATE print_job SET status='failed', updated_at=NOW() WHERE id=%s",
            (int(task_id),),
        )
        _native_db().execute(
            "UPDATE sales_order SET print_status='failed', note=CONCAT(COALESCE(note, ''), %s), updated_at=NOW() WHERE id=%s",
            (f"\n打印失败：{reason}", int(row.get("document_id") or 0)),
        )
        return jsonify({"code": 0, "data": {"id": int(task_id), "status": "failed"}})
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
        html = _native_db().sales_print_html(sales_id, auto_print=auto_print)
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
        result = _native_db().sales_detail(sales_id)
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
        result = _native_db().delete_sales_order(sales_id)
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
                product_rows, _ = _native_db().product_list(
                    keyword=keyword,
                    page=1,
                    page_size=max(limit * 30, 1200),
                    group=False,
                )
            except Exception as product_error:
                logger.warning(f"native product rows for zero-stock inventory failed: {product_error}")
        rows = _native_db().search_inventory(
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
    if out_warehouse_id == enter_warehouse_id:
        return jsonify({"code": 400, "msg": "调出仓库和调入仓库不能相同"}), 400
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


@app.route("/api/inventory/stocktaking", methods=["POST"])
def inventory_stocktaking_api():
    """Set target inventory for one product in one warehouse."""
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
        quantity = -1
    if quantity < 0:
        return jsonify({"code": 400, "msg": "quantity must be greater than or equal to 0"}), 400
    try:
        result = caller.call(
            "inventory_sync",
            warehouse_id=warehouse_id,
            products=[{
                "product_id": int(product_id),
                "unit_id": int(body.get("unit_id") or 1),
                "number": quantity,
            }],
            note=(body.get("note") or f"WebUI盘点{f'（{color}）' if color else ''}").strip(),
        )
        if isinstance(result, dict) and result.get("error"):
            return jsonify({"code": 500, "msg": result.get("error")}), 500
        return jsonify({"code": 0, "data": result})
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
                    _native_db().execute(
                        "UPDATE workflow_order SET order_image_urls = %s, updated_at = NOW() WHERE id = %s",
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
    keyword = normalize_product_name(request.args.get("keyword", ""), specs=PRODUCT_SPECS)
    if not keyword:
        return jsonify({"code": 400, "msg": "keyword is required"}), 400

    try:
        results = _native_db().product_search(keyword, limit=100)
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
    group = request.args.get("group", default=1, type=int) == 1

    try:
        items, total = _db_product_list(keyword, max(1, page), page_size, status, category_id, group, category_ids=category_ids)
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


@app.route("/api/product/categories", methods=["GET"])
def product_categories():
    """商品分类。"""
    try:
        categories = _db_product_categories()
        _, total = _native_db().product_list(page=1, page_size=1, group=True)
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
    result = _native_db().system_setting("miniapp_design")
    data = result.get("data") if isinstance(result, dict) else {}
    value = data.get("value") if isinstance(data, dict) else {}
    return value if isinstance(value, dict) else {}


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
    items, _total = _db_product_list(
        keyword,
        1,
        limit,
        status=0,
        category_id=clean_category_id,
        group=True,
    )
    return [_mini_product_payload(item, list_item=True) for item in items]


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
            items, _total = _db_product_list("", 1, 8, status=0, group=True)
            first_products = [_mini_product_payload(item, list_item=True) for item in items]
        design["home"] = {**home, "modules": prepared_modules}
        banners = _mini_home_first_items(prepared_modules, "banner")
        navs = _mini_home_first_items(prepared_modules, "nav")
        return jsonify({
            "code": 0,
            "data": {
                "design": design,
                "banners": banners,
                "navs": navs,
                "products": first_products,
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

    workflow_total = 0
    sales_total = 0
    try:
        _rows, workflow_total = _db_workflow_orders("", 1, 1, "active")
    except Exception as e:
        logger.warning(f"mini user center workflow count failed: {e}")
    try:
        _rows, sales_total = _db_sales_cards("", 1, 1, None)
    except Exception as e:
        logger.warning(f"mini user center sales count failed: {e}")

    order_total = int(workflow_total or 0) + int(sales_total or 0)
    return jsonify({
        "code": 0,
        "data": {
            "user": user,
            "message_total": 0,
            "cart_total": {"buy_number": 0},
            "user_order_count": order_total,
            "user_goods_favor_count": 0,
            "user_goods_browse_count": 0,
            "integral": 0,
            "user_order_status": [
                {"status": 0, "name": "全部订单", "count": order_total},
                {"status": 1, "name": "订单流", "count": int(workflow_total or 0)},
                {"status": 2, "name": "销售单", "count": int(sales_total or 0)},
            ],
            "navigation": [
                {"name": "订单", "event_value": "/pages/order/order", "event_type": 1, "desc": "查看订单流和销售单"},
                {"name": "商品分类", "event_value": "/pages/goods-category/goods-category", "event_type": 1, "desc": "查看产品资料"},
            ],
            "source": "sjagent_core",
        },
    })


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
        categories = _db_product_categories()
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
        categories = _mini_category_tree(_db_product_categories())
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

    try:
        items, total = _db_product_list(keyword, page, page_size, status=0, category_id=category_id, group=True)
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
        product = _native_db().product_info(product_id)
        if not product:
            return jsonify({"code": 404, "msg": "商品不存在"}), 404
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

    workflows = []
    workflow_total = 0
    sales = []
    sales_total = 0

    try:
        workflows, workflow_total = _db_workflow_orders(keyword, page, page_size, "active")
    except Exception as e:
        logger.warning(f"mini orderflow workflow query failed: {e}")

    try:
        sales, sales_total = _db_sales_cards(keyword, page, page_size, None)
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


@app.route("/api/product/options", methods=["GET"])
def product_options():
    """商品编辑基础数据。"""
    try:
        product_id = request.args.get("id", type=int)
        return jsonify({"code": 0, "data": _safe_json(_native_db().product_options(product_id))})
    except Exception as e:
        logger.error(f"商品基础数据异常: {e}")
        return _api_exception_response(e)


@app.route("/api/product/<int:product_id>", methods=["GET"])
def product_detail_api(product_id: int):
    """商品详情。"""
    try:
        product = _native_db().product_info(product_id)
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
        result = _native_db().save_product(body or {})
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
        result = _native_db().delete_product(ids)
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
                _native_db().record_product_upload(str(url), storage="oss")
            except Exception as asset_error:
                logger.warning(f"商品图片待绑定资产记录失败: {asset_error}")
        _delete_local_upload(save_path, "商品图片")
        return jsonify({"code": 0, "data": result})
    except Exception as e:
        logger.error(f"商品图片上传异常: {e}")
        return _api_exception_response(e)


@app.route("/api/product/media", methods=["GET"])
def product_media_api():
    """商品图片资产。"""
    try:
        product_id = request.args.get("product_id", type=int)
        limit = max(1, min(request.args.get("limit", 500, type=int), 6000))
        media_type = (request.args.get("media_type") or "").strip()
        if product_id:
            product = _native_db().product_info(product_id)
            if not product:
                return jsonify({"code": 404, "msg": "商品不存在"}), 404
            rows = _native_db().product_media_assets(
                spu_id=int(product.get("spu_id") or 0),
                sku_ids=[int(product.get("id") or product_id)],
                media_type=media_type,
                include_pending=True,
                limit=limit,
            )
        else:
            rows = _native_db().product_media_assets(media_type=media_type, include_pending=True, limit=limit)
        return jsonify({"code": 0, "data": {"list": _safe_json(rows), "total": len(rows), "source": "native"}})
    except Exception as e:
        logger.error(f"商品图片资产查询异常: {e}")
        return _api_exception_response(e)


@app.route("/api/product/media/<int:media_id>", methods=["DELETE", "POST"])
def product_media_delete_api(media_id: int):
    """Disable a product image asset."""
    try:
        return jsonify(_native_db().delete_product_media(media_id))
    except Exception as e:
        logger.error(f"商品图片资产删除异常: {e}")
        return _api_exception_response(e)


@app.route("/api/product/<int:product_id>/shelves", methods=["POST"])
def product_shelves_api(product_id: int):
    """Update product listing state."""
    try:
        body = request.get_json(silent=True) or request.form.to_dict(flat=True) or {}
        state = int(body.get("state", 0))
        result = _native_db().update_product_shelves(product_id, state)
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


@app.route("/api/customer/create", methods=["POST"])
def customer_create_api():
    """Create an ERP customer for the WebUI sales form."""
    from src.core.customer_name import normalize_customer_name
    from src.core.tools.caller import get_tool_caller

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
            "company_name": row.get("company_name") or "",
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
    except Exception as e:
        logger.warning(f"创建客户前数据库查重失败，继续走 API: {e}")

    caller = get_tool_caller()
    try:
        result = caller.call(
            "customer_create",
            name=name,
            contacts_name=contacts_name,
            contacts_tel=contacts_tel,
        )
        if isinstance(result, dict) and result.get("error"):
            return jsonify({"code": 500, "msg": result.get("error"), "data": result}), 500
        if isinstance(result, dict) and result.get("code") not in (None, 0):
            return jsonify({"code": 500, "msg": result.get("msg", "创建客户失败"), "data": result}), 500

        created = None
        try:
            created = exact_customer(_db_customer_list(name, limit=20))
        except Exception as e:
            logger.warning(f"创建客户后数据库回查失败，回退 API: {e}")
        if not created:
            rows = caller.call("customer_query", keyword=name) or []
            created = exact_customer(rows) or (rows[0] if len(rows) == 1 else None)

        if created:
            return jsonify({"code": 0, "msg": "客户创建成功", "data": normalize_row(created)})

        data = result.get("data") if isinstance(result, dict) else {}
        fallback_id = ""
        if isinstance(data, dict):
            fallback_id = data.get("id") or data.get("customer_id") or data.get("company_id") or ""
        elif isinstance(data, (str, int)):
            fallback_id = data
        return jsonify({
            "code": 0,
            "msg": "客户创建成功",
            "data": {
                "id": fallback_id,
                "customer_id": fallback_id,
                "name": name,
                "customer_name": name,
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


def _page_args(default_size: int = 50, max_size: int = 200) -> tuple[int, int]:
    page = max(1, request.args.get("page", 1, type=int))
    page_size = max(1, min(request.args.get("page_size", default_size, type=int), max_size))
    return page, page_size


@app.route("/api/customers", methods=["GET"])
def native_customers_api():
    """Native customer management list."""
    keyword = (request.args.get("keyword") or "").strip()
    limit = max(1, min(request.args.get("limit", 200, type=int), 500))
    try:
        rows = _native_db().customer_list(keyword, limit=limit)
        return jsonify({"code": 0, "data": {"list": _safe_json(rows), "total": len(rows), "source": "native"}})
    except Exception as e:
        logger.error(f"自有库客户管理列表异常: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/customers/<int:customer_id>/sales", methods=["GET"])
def native_customer_sales_api(customer_id: int):
    """Native customer bound sales orders."""
    page, page_size = _page_args(default_size=50, max_size=200)
    period = (request.args.get("period") or "").strip()
    month = (request.args.get("month") or "").strip()
    try:
        rows, total, summary = _native_db().customer_sales(
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


@app.route("/api/customers/<int:customer_id>/balance-ledger", methods=["GET"])
def native_customer_balance_ledger_api(customer_id: int):
    """Native customer balance ledger."""
    page, page_size = _page_args()
    try:
        rows, total, summary = _native_db().customer_balance_ledger(
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
        if action == "settlement":
            result = _native_db().customer_month_settlement(
                customer_id,
                month=body.get("month") or "",
                amount=amount,
                pay_type=pay_type or "wechat",
                note=note,
            )
        elif action in ("receipt", "recharge"):
            result = _native_db().customer_balance_entry(
                customer_id,
                entry_type=action,
                amount=amount,
                pay_type=pay_type or action,
                note=note,
            )
        elif action == "adjust":
            result = _native_db().customer_balance_adjust(
                customer_id,
                amount=amount,
                note=note,
            )
        else:
            return jsonify({"code": 400, "msg": "action is required"}), 400
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
        rows, total = _native_db().users(keyword=keyword, page=page, page_size=page_size)
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
        result = _native_db().update_user(user_id, role=role, is_active=is_active)
        if isinstance(result, dict) and result.get("code") not in (None, 0):
            return jsonify(result), 400
        return jsonify(result)
    except Exception as e:
        logger.error(f"自有库用户更新异常: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/warehouses", methods=["GET"])
def native_warehouses_api():
    try:
        rows = _native_db().warehouse_list()
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
        rows, total = _native_db().inventory_balances(keyword=keyword, warehouse_id=warehouse_id, page=page, page_size=page_size)
        return jsonify({"code": 0, "data": {"list": _safe_json(rows), "total": total, "page": page, "page_size": page_size, "source": "native"}})
    except Exception as e:
        logger.error(f"自有库库存明细异常: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/inventory/ledger", methods=["GET"])
def native_inventory_ledger_api():
    keyword = (request.args.get("keyword") or "").strip()
    page, page_size = _page_args()
    try:
        rows, total = _native_db().inventory_ledger(keyword=keyword, page=page, page_size=page_size)
        return jsonify({"code": 0, "data": {"list": _safe_json(rows), "total": total, "page": page, "page_size": page_size, "source": "native"}})
    except Exception as e:
        logger.error(f"自有库库存日志异常: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/stock-documents", methods=["GET"])
def native_stock_documents_api():
    keyword = (request.args.get("keyword") or "").strip()
    page, page_size = _page_args()
    try:
        rows, total = _native_db().stock_documents(keyword=keyword, page=page, page_size=page_size)
        return jsonify({"code": 0, "data": {"list": _safe_json(rows), "total": total, "page": page, "page_size": page_size, "source": "native"}})
    except Exception as e:
        logger.error(f"自有库出入库明细异常: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/stocktakes", methods=["GET"])
def native_stocktakes_api():
    keyword = (request.args.get("keyword") or "").strip()
    page, page_size = _page_args()
    try:
        rows, total = _native_db().stocktakes(keyword=keyword, page=page, page_size=page_size)
        return jsonify({"code": 0, "data": {"list": _safe_json(rows), "total": total, "page": page, "page_size": page_size, "source": "native"}})
    except Exception as e:
        logger.error(f"自有库盘点明细异常: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/transfers", methods=["GET"])
def native_transfers_api():
    keyword = (request.args.get("keyword") or "").strip()
    page, page_size = _page_args()
    try:
        rows, total = _native_db().transfers(keyword=keyword, page=page, page_size=page_size)
        return jsonify({"code": 0, "data": {"list": _safe_json(rows), "total": total, "page": page, "page_size": page_size, "source": "native"}})
    except Exception as e:
        logger.error(f"自有库调拨明细异常: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


def _normalize_sales_add_products(products: list[dict]) -> list[dict]:
    """Fill the native product base unit before SalesAdd."""
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
                detail = _native_db().product_info(pid) or {}
            except Exception as e:
                logger.warning(f"开单商品单位查询失败: product_id={pid}, error={e}")
                detail = {}
            detail_cache[pid] = detail if isinstance(detail, dict) else {}
        next_item = dict(item)
        if not next_item.get("unit_id"):
            next_item["unit_id"] = int(detail_cache[pid].get("unit_id") or 1)
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
    body = request.get_json()
    customer_id = body.get("customer_id")
    warehouse_id = body.get("warehouse_id", 2)
    products = body.get("products", [])
    create_time = body.get("create_time") or ""
    pay_status = body.get("pay_status") or "paid"
    pay_type = body.get("pay_type") or "wechat"

    if not customer_id or not products:
        return jsonify({"code": 400, "msg": "customer_id and products are required"}), 400

    try:
        products = _normalize_sales_add_products(products)
        result = _native_db().create_sales_order(
            customer_id=customer_id,
            warehouse_id=warehouse_id,
            products=products,
            create_time=create_time,
            pay_status=pay_status,
            pay_type=pay_type,
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
    if not accounts:
        return jsonify({"code": 400, "msg": "请输入北极星账号或手机号"}), 400
    if not password:
        return jsonify({"code": 400, "msg": "请输入北极星密码"}), 400
    try:
        user_row = _native_user_by_account(accounts)
        password_hash = (user_row or {}).get("password_hash") or ""
        if not user_row or not password_hash or not check_password_hash(password_hash, password):
            return jsonify({"code": 401, "msg": "账号或密码不正确"}), 401
        if int(user_row.get("is_active") or 0) != 1 or str(user_row.get("approval_status") or "") != "approved":
            return jsonify({"code": 403, "msg": "账号未启用或还未审批通过"}), 403
        client_type = (body.get("client_type") or request.headers.get("X-SJ-Client") or "miniapp").strip()
        token = _issue_native_session(int(user_row["id"]), client_type=client_type)
        _web_auth_db().execute(
            "UPDATE auth_user SET last_login_at=NOW(), updated_at=NOW() WHERE id=%s",
            (int(user_row["id"]),),
        )
        user = _native_user_public(user_row, token=token)
        NATIVE_AUTH_CACHE[token] = (time.time() + NATIVE_AUTH_CACHE_TTL, user)
        return jsonify({"code": 0, "data": {"token": token, "user": user}})
    except Exception as e:
        logger.error(f"北极星登录异常: {e}")
        return jsonify({"code": 500, "msg": f"北极星登录异常: {e}"}), 500


@app.route("/api/auth/wechat-quick-login", methods=["POST"])
def auth_wechat_quick_login():
    """Login through native WeChat identity binding."""
    body = request.get_json(silent=True) or request.form.to_dict() or {}
    authcode = (body.get("authcode") or body.get("code") or "").strip()
    openid = (body.get("openid") or body.get("open_id") or "").strip()
    unionid = (body.get("unionid") or body.get("union_id") or "").strip()
    profile = body.get("userInfo") if isinstance(body.get("userInfo"), dict) else body
    try:
        if not openid:
            if not authcode:
                return jsonify({"code": 400, "msg": "缺少微信登录 code 或 openid"}), 400
            miniapp_appid = body.get("appid") or os.environ.get("WECHAT_MINIAPP_APPID") or os.environ.get("WX_MINIAPP_APPID") or ""
            wx_result = _wechat_session_from_code(authcode, miniapp_appid)
            if int(wx_result.get("code", -1)) != 0:
                return jsonify(wx_result), 400
            wx_data = wx_result.get("data") or {}
            openid = str(wx_data.get("openid") or "")
            unionid = str(wx_data.get("unionid") or unionid or "")
        user_row = _upsert_wechat_user(openid, unionid=unionid, profile=profile)
        user = _native_user_public(user_row)
        if int(user.get("is_active") or 0) != 1 or str(user.get("approval_status") or "") != "approved":
            return jsonify({"code": 403, "msg": "微信账号已绑定，等待后台启用或审批", "data": {"user": user}}), 403
        if not _native_user_can_access_miniapp(user):
            return jsonify({"code": 403, "msg": "当前微信账号未开通业务操作权限", "data": {"user": user}}), 403
        token = _issue_native_session(int(user["id"]), client_type="miniapp")
        user = _native_user_public(user_row, token=token)
        NATIVE_AUTH_CACHE[token] = (time.time() + NATIVE_AUTH_CACHE_TTL, user)
        return jsonify({"code": 0, "data": {"token": token, "user": user}})
    except Exception as e:
        logger.error(f"微信快捷登录异常: {e}")
        return jsonify({"code": 500, "msg": f"微信快捷登录异常: {e}"}), 500


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
        user = _verify_native_token(token, force=request.args.get("force") in ("1", "true", "True"))
        if not user:
            return jsonify({"code": 401, "msg": "登录已失效，请重新登录"}), 401
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
