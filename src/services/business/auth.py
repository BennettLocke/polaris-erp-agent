"""Authentication and account service for WebUI and mini-program clients."""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import threading
import time
from datetime import datetime, timedelta
from typing import Any

from werkzeug.security import check_password_hash, generate_password_hash

from .base import BusinessService


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

_AUTH_READY = False
_AUTH_LOCK = threading.Lock()
_TOKEN_CACHE: dict[str, tuple[float, dict]] = {}
_TOKEN_CACHE_TTL = 60
_WECHAT_ACCESS_TOKEN_CACHE: dict[str, tuple[float, str]] = {}


def phone_digits(value: Any) -> str:
    return re.sub(r"\D+", "", str(value or ""))


def normalized_phone(value: Any) -> str:
    digits = phone_digits(value)
    return digits if re.fullmatch(r"1\d{10}", digits or "") else ""


def token_hash(token: str) -> str:
    return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()


def role_code(value: Any) -> str:
    role = str(value or "").strip()
    if not role:
        return "guest"
    role = ROLE_LABEL_TO_CODE.get(role, role)
    if role in {"warehouse", "designer"}:
        return "staff"
    if role == "readonly":
        return "guest"
    return role if role in ROLE_CODE_TO_LABEL else "guest"


def role_label(value: Any) -> str:
    return ROLE_CODE_TO_LABEL.get(role_code(value), "访客")


class AuthService(BusinessService):
    def ensure_session_table(self) -> None:
        global _AUTH_READY
        if _AUTH_READY:
            return
        with _AUTH_LOCK:
            if _AUTH_READY:
                return
            self.db.execute(
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
            _AUTH_READY = True

    def user_public(self, row: dict | None, token: str = "") -> dict:
        if not isinstance(row, dict):
            row = {}
        role = role_code(row.get("role"))
        is_admin = int(row.get("is_admin") or 0) == 1 or role == "admin"
        user_id = row.get("id") or row.get("user_id") or ""
        public_phone = normalized_phone(row.get("phone"))
        account_display_name = (
            row.get("display_name")
            or row.get("nickname")
            or row.get("username")
            or public_phone
            or (f"用户{user_id}" if user_id else "北极星用户")
        )
        linked_party_id = row.get("linked_party_id")
        linked_party_name = row.get("linked_party_name") or ""
        has_customer_binding = bool(linked_party_id)
        display_name = linked_party_name or account_display_name
        return {
            "id": user_id,
            "user_id": user_id,
            "token": token,
            "display_name": display_name,
            "user_display_name": account_display_name,
            "display_name_source": "customer" if has_customer_binding else "user",
            "can_edit_display_name": not has_customer_binding,
            "nickname": row.get("nickname") or display_name,
            "username": row.get("username") or "",
            "mobile": public_phone,
            "phone": public_phone,
            "email": row.get("email") or "",
            "avatar": row.get("avatar") or "",
            "role": role,
            "role_text": role_label(role),
            "linked_party_id": linked_party_id,
            "linked_party_name": linked_party_name,
            "approval_status": row.get("approval_status") or "",
            "is_active": int(row.get("is_active") or 0),
            "is_admin": is_admin,
            "miniapp_allowed": is_admin or role in {"staff", "customer"},
            "source": "native",
            "raw": row,
        }

    def web_user_payload(self, user: dict | None) -> dict:
        if not isinstance(user, dict):
            user = {}
        user_id = int(user.get("id") or user.get("user_id") or 0)
        return {
            "id": user_id,
            "native_user_id": user_id,
            "username": user.get("username") or "",
            "display_name": user.get("display_name") or user.get("username") or "",
            "role": role_code(user.get("role")),
            "role_text": role_label(user.get("role")),
            "approval_status": user.get("approval_status") or "",
            "is_admin": int(user.get("is_admin") or 0),
            "is_active": int(user.get("is_active") or 0),
            "last_login_at": str(user.get("last_login_at") or ""),
        }

    def user_by_id(self, user_id: int) -> dict | None:
        rows = self.db.query(
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

    def user_by_account(self, account: str) -> dict | None:
        account = str(account or "").strip()
        if not account:
            return None
        phone = normalized_phone(account)
        rows = self.db.query(
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

    def user_by_identity(self, provider: str, external_id: str) -> dict | None:
        rows = self.db.query(
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

    def find_party_id_by_phone(self, phone: str) -> int | None:
        digits = normalized_phone(phone)
        if not digits:
            return None
        rows = self.db.query(
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

    def current_web_user(self, user_id: Any) -> dict | None:
        if not user_id:
            return None
        user = self.user_by_id(int(user_id))
        if not user or int(user.get("is_active") or 0) != 1 or str(user.get("approval_status") or "") != "approved":
            return None
        user["native_user_id"] = int(user.get("id") or 0) or None
        return user

    def is_admin(self, user: dict | None) -> bool:
        return bool(isinstance(user, dict) and int(user.get("is_admin") or 0) == 1)

    def web_user_can_access_webui(self, user: dict | None) -> bool:
        if not isinstance(user, dict):
            return False
        if self.is_admin(user):
            return True
        return role_code(user.get("role")) in {"admin", "staff"}

    def user_can_access_miniapp(self, user: dict | None) -> bool:
        return bool(isinstance(user, dict) and user.get("miniapp_allowed") is True)

    def _profile_phone(self, profile: dict | None) -> str:
        profile = profile if isinstance(profile, dict) else {}
        for key in ("phone", "mobile", "purePhoneNumber", "phoneNumber", "customer_phone"):
            value = profile.get(key)
            digits = normalized_phone(value)
            if digits:
                return digits
        return ""

    def has_permission(self, permission: str, user: dict | None) -> bool:
        if not isinstance(user, dict):
            return False
        role = role_code(user.get("role"))
        if self.is_admin(user):
            role = "admin"
        return permission in FIXED_ROLE_PERMISSIONS.get(role, set())

    def register_web_user(self, *, username: str, password: str, display_name: str = "") -> dict:
        username = str(username or "").strip()
        password = str(password or "")
        display_name = str(display_name or username).strip()
        if not re.fullmatch(r"[A-Za-z0-9_@.\-]{3,80}", username or ""):
            return {"code": 400, "msg": "账号需为 3-80 位，可用字母、数字、下划线、邮箱符号", "_http_status": 400}
        if len(password) < 6:
            return {"code": 400, "msg": "密码至少 6 位", "_http_status": 400}
        if self.user_by_account(username):
            return {"code": 409, "msg": "账号已存在，请直接登录", "_http_status": 409}
        admin_rows = self.db.query(
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
        phone = normalized_phone(username)
        linked_party_id = self.find_party_id_by_phone(phone) if phone else None
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        affected = self.db.execute(
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
            return {"code": 500, "msg": "注册失败，请稍后重试", "_http_status": 500}
        user = self.user_by_account(username)
        user_id = int((user or {}).get("id") or 0)
        return {
            "code": 0,
            "data": {
                "user": self.web_user_payload(user),
                "pending": not is_first_user,
                "auto_login": is_first_user,
                "session_user_id": user_id if is_first_user else None,
            },
        }

    def login_web_user(self, *, username: str, password: str) -> dict:
        username = str(username or "").strip()
        password = str(password or "")
        if not username or not password:
            return {"code": 400, "msg": "请输入账号和密码", "_http_status": 400}
        user = self.user_by_account(username)
        if not user or not check_password_hash(user.get("password_hash") or "", password):
            return {"code": 401, "msg": "账号或密码不正确", "_http_status": 401}
        if str(user.get("approval_status") or "") != "approved" or int(user.get("is_active") or 0) != 1:
            return {"code": 403, "msg": "账号还在审批中，请联系管理员通过后再登录", "_http_status": 403}
        if not self.web_user_can_access_webui(user):
            return {"code": 403, "msg": "当前账号没有后台访问权限", "_http_status": 403}
        self.db.execute(
            "UPDATE auth_user SET last_login_at=NOW(), updated_at=NOW() WHERE id=%s",
            (int(user["id"]),),
        )
        user = self.user_by_id(int(user["id"])) or user
        return {
            "code": 0,
            "data": {
                "user": self.web_user_payload(user),
                "session_user_id": int(user["id"]),
            },
        }

    def web_users(self, *, status: str = "pending") -> dict:
        clean_status = str(status or "pending").strip()
        if clean_status not in {"pending", "approved", "rejected", "all"}:
            clean_status = "pending"
        sql = """
            SELECT id, username, display_name, role, approval_status, is_admin, is_active, created_at, last_login_at
            FROM auth_user
            WHERE (is_admin=1 OR role IN ('admin','staff'))
        """
        params: list[Any] = []
        if clean_status != "all":
            sql += " AND approval_status=%s"
            params.append(clean_status)
        sql += " ORDER BY id DESC LIMIT 100"
        rows = self.db.query(sql, params)
        return {"code": 0, "data": {"items": rows}}

    def approve_user(self, user_id: int) -> dict:
        affected = self.db.execute(
            """
            UPDATE auth_user
            SET approval_status='approved', is_active=1, updated_at=NOW()
            WHERE id=%s
            """,
            (int(user_id),),
        )
        return {"code": 0, "data": {"affected": affected}}

    def reject_user(self, user_id: int, *, admin_user_id: int | None = None) -> dict:
        if admin_user_id and int(admin_user_id) == int(user_id):
            return {"code": 400, "msg": "不能拒绝自己的账号", "_http_status": 400}
        affected = self.db.execute(
            """
            UPDATE auth_user
            SET approval_status='rejected', is_active=0, updated_at=NOW()
            WHERE id=%s
            """,
            (int(user_id),),
        )
        return {"code": 0, "data": {"affected": affected}}

    def issue_session(self, user_id: int, *, client_type: str = "miniapp", ip: str = "", user_agent: str = "") -> str:
        self.ensure_session_table()
        token = "sj_" + secrets.token_urlsafe(32)
        now = datetime.now()
        expires_at = now + timedelta(days=30)
        self.db.execute(
            """
            INSERT INTO auth_session
                (user_id, token_hash, client_type, ip, user_agent, expires_at, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                int(user_id),
                token_hash(token),
                str(client_type or "miniapp")[:30],
                str(ip or "")[:80],
                str(user_agent or "")[:500],
                expires_at.strftime("%Y-%m-%d %H:%M:%S"),
                now.strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )
        self.db.execute("DELETE FROM auth_session WHERE expires_at < NOW() OR revoked_at IS NOT NULL")
        return token

    def verify_token(self, token: str, *, force: bool = False) -> dict | None:
        if not token:
            return None
        now = time.time()
        cached = _TOKEN_CACHE.get(token)
        if cached and not force and cached[0] > now:
            return cached[1]
        self.ensure_session_table()
        rows = self.db.query(
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
            (token_hash(token),),
        )
        if not rows:
            _TOKEN_CACHE.pop(token, None)
            return None
        row = rows[0]
        if int(row.get("is_active") or 0) != 1 or str(row.get("approval_status") or "") != "approved":
            _TOKEN_CACHE.pop(token, None)
            return None
        user = self.user_public(row, token=token)
        _TOKEN_CACHE[token] = (now + _TOKEN_CACHE_TTL, user)
        return user

    def native_login(
        self,
        *,
        account: str,
        password: str,
        client_type: str = "miniapp",
        ip: str = "",
        user_agent: str = "",
    ) -> dict:
        account = str(account or "").strip()
        password = str(password or "")
        if not account:
            return {"code": 400, "msg": "请输入北极星账号或手机号", "_http_status": 400}
        if not password:
            return {"code": 400, "msg": "请输入北极星密码", "_http_status": 400}
        user_row = self.user_by_account(account)
        password_hash = (user_row or {}).get("password_hash") or ""
        if not user_row or not password_hash or not check_password_hash(password_hash, password):
            return {"code": 401, "msg": "账号或密码不正确", "_http_status": 401}
        if int(user_row.get("is_active") or 0) != 1 or str(user_row.get("approval_status") or "") != "approved":
            return {"code": 403, "msg": "账号未启用或还未审批通过", "_http_status": 403}
        token = self.issue_session(int(user_row["id"]), client_type=client_type, ip=ip, user_agent=user_agent)
        self.db.execute(
            "UPDATE auth_user SET last_login_at=NOW(), updated_at=NOW() WHERE id=%s",
            (int(user_row["id"]),),
        )
        user = self.user_public(user_row, token=token)
        _TOKEN_CACHE[token] = (time.time() + _TOKEN_CACHE_TTL, user)
        return {"code": 0, "data": {"token": token, "user": user}}

    def native_register(
        self,
        *,
        account: str,
        password: str,
        display_name: str = "",
        client_type: str = "miniapp",
        ip: str = "",
        user_agent: str = "",
    ) -> dict:
        account = str(account or "").strip()
        password = str(password or "")
        display_name = str(display_name or account).strip()
        if not account:
            return {"code": 400, "msg": "请输入手机号或账号", "_http_status": 400}
        if len(account) > 80:
            return {"code": 400, "msg": "账号不能超过 80 位", "_http_status": 400}
        if len(password) < 6:
            return {"code": 400, "msg": "密码至少 6 位", "_http_status": 400}
        if not display_name:
            display_name = account
        if self.user_by_account(account):
            return {"code": 409, "msg": "账号已存在，请直接登录", "_http_status": 409}

        phone = normalized_phone(account)
        linked_party_id = self.find_party_id_by_phone(phone) if phone else None
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        affected = self.db.execute(
            """
            INSERT INTO auth_user
                (username, password_hash, display_name, phone, role, linked_party_id,
                 approval_status, is_active, is_admin, last_login_at, created_at, updated_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                account,
                generate_password_hash(password),
                display_name[:80],
                phone or None,
                "customer",
                linked_party_id,
                "approved",
                1,
                0,
                now,
                now,
                now,
            ),
        )
        if affected != 1:
            return {"code": 500, "msg": "注册失败，请稍后重试", "_http_status": 500}

        user_row = self.user_by_account(account)
        user_id = int((user_row or {}).get("id") or 0)
        if not user_id:
            return {"code": 500, "msg": "注册后未找到账号，请稍后重试", "_http_status": 500}
        if phone:
            self.db.execute(
                """
                INSERT INTO auth_identity
                    (user_id, provider, external_user_id, is_enabled, created_at, updated_at)
                VALUES (%s,'phone',%s,1,%s,%s)
                ON DUPLICATE KEY UPDATE
                    user_id=VALUES(user_id),
                    is_enabled=1,
                    updated_at=VALUES(updated_at)
                """,
                (user_id, phone, now, now),
            )
        token = self.issue_session(user_id, client_type=client_type, ip=ip, user_agent=user_agent)
        user_row = self.user_by_id(user_id) or user_row
        user = self.user_public(user_row, token=token)
        _TOKEN_CACHE[token] = (time.time() + _TOKEN_CACHE_TTL, user)
        return {"code": 0, "data": {"token": token, "user": user}}

    def change_native_password(self, *, user_id: int, old_password: str = "", new_password: str = "") -> dict:
        user_id = int(user_id or 0)
        old_password = str(old_password or "")
        new_password = str(new_password or "")
        if not user_id:
            return {"code": 401, "msg": "请先登录账号", "_http_status": 401}
        if len(new_password) < 6:
            return {"code": 400, "msg": "新密码至少 6 位", "_http_status": 400}
        user_row = self.user_by_id(user_id)
        if not user_row:
            return {"code": 401, "msg": "登录已失效，请重新登录", "_http_status": 401}
        password_hash = user_row.get("password_hash") or ""
        if password_hash and not check_password_hash(password_hash, old_password):
            return {"code": 401, "msg": "当前密码不正确", "_http_status": 401}
        affected = self.db.execute(
            "UPDATE auth_user SET password_hash=%s, updated_at=NOW() WHERE id=%s",
            (generate_password_hash(new_password), user_id),
        )
        _TOKEN_CACHE.clear()
        return {"code": 0, "data": {"affected": affected}}

    def update_native_profile(self, *, user_id: int, display_name: str = "", token: str = "") -> dict:
        user_id = int(user_id or 0)
        display_name = str(display_name or "").strip()
        if not user_id:
            return {"code": 401, "msg": "Please login first", "_http_status": 401}
        if not display_name:
            return {"code": 400, "msg": "Username cannot be empty", "_http_status": 400}
        if len(display_name) > 80:
            display_name = display_name[:80]

        current = self.user_by_id(user_id)
        if not current:
            _TOKEN_CACHE.pop(token, None)
            return {"code": 401, "msg": "Login expired, please login again", "_http_status": 401}
        if current.get("linked_party_id"):
            user = self.user_public(current, token=token)
            return {
                "code": 403,
                "msg": "Customer-bound accounts use the customer name and cannot edit the display name here",
                "data": {"user": user},
                "_http_status": 403,
            }

        result = self.db.update_user(user_id, display_name=display_name)
        if int(result.get("code") or 0) != 0:
            return {**result, "_http_status": 400}

        row = self.user_by_id(user_id)
        if not row:
            _TOKEN_CACHE.pop(token, None)
            return {"code": 401, "msg": "Login expired, please login again", "_http_status": 401}
        user = self.user_public(row, token=token)
        if token:
            _TOKEN_CACHE[token] = (time.time() + _TOKEN_CACHE_TTL, user)
        else:
            _TOKEN_CACHE.clear()
        return {"code": 0, "data": {"user": user, "affected": (result.get("data") or {}).get("affected", 0)}}

    def wechat_session_from_code(self, authcode: str, appid: str) -> dict:
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

    def wechat_access_token(self, appid: str) -> dict:
        appid = str(appid or "").strip()
        secret = os.environ.get("WECHAT_MINIAPP_SECRET") or os.environ.get("WX_MINIAPP_SECRET") or ""
        if not appid or not secret:
            return {"code": 400, "msg": "未配置微信小程序 appid/secret，不能换取手机号"}
        now = time.time()
        cached = _WECHAT_ACCESS_TOKEN_CACHE.get(appid)
        if cached and cached[0] > now:
            return {"code": 0, "data": {"access_token": cached[1], "cached": True}}
        import requests

        resp = requests.get(
            "https://api.weixin.qq.com/cgi-bin/token",
            params={
                "grant_type": "client_credential",
                "appid": appid,
                "secret": secret,
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, dict):
            return {"code": 500, "msg": "微信 access_token 返回格式异常"}
        if data.get("errcode"):
            return {"code": 401, "msg": data.get("errmsg") or "微信 access_token 获取失败", "raw": data}
        access_token = str(data.get("access_token") or "").strip()
        if not access_token:
            return {"code": 500, "msg": "微信 access_token 为空", "raw": data}
        try:
            expires_in = int(data.get("expires_in") or 7200)
        except (TypeError, ValueError):
            expires_in = 7200
        _WECHAT_ACCESS_TOKEN_CACHE[appid] = (now + max(60, expires_in - 300), access_token)
        return {"code": 0, "data": {"access_token": access_token, "cached": False}}

    def wechat_phone_from_code(self, phone_code: str, appid: str) -> dict:
        phone_code = str(phone_code or "").strip()
        if not phone_code:
            return {"code": 400, "msg": "缺少微信手机号 code", "_http_status": 400}
        token_result = self.wechat_access_token(appid)
        if int(token_result.get("code", -1)) != 0:
            return {**token_result, "_http_status": int(token_result.get("_http_status") or 400)}
        access_token = str(((token_result.get("data") or {}).get("access_token")) or "").strip()
        if not access_token:
            return {"code": 500, "msg": "微信 access_token 为空", "_http_status": 500}
        import requests

        resp = requests.post(
            "https://api.weixin.qq.com/wxa/business/getuserphonenumber",
            params={"access_token": access_token},
            json={"code": phone_code},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, dict):
            return {"code": 500, "msg": "微信手机号返回格式异常", "_http_status": 500}
        if int(data.get("errcode") or 0) != 0:
            return {
                "code": 401,
                "msg": data.get("errmsg") or "微信手机号换取失败",
                "raw": data,
                "_http_status": 400,
            }
        phone_info = data.get("phone_info") if isinstance(data.get("phone_info"), dict) else {}
        phone = self._profile_phone(phone_info)
        if not phone:
            return {"code": 500, "msg": "微信手机号返回为空", "raw": data, "_http_status": 500}
        return {"code": 0, "data": {"phone": phone, "phone_info": phone_info, "raw": data}}

    def upsert_wechat_user(self, openid: str, unionid: str = "", profile: dict | None = None) -> dict:
        openid = str(openid or "").strip()
        unionid = str(unionid or "").strip()
        profile = profile if isinstance(profile, dict) else {}
        if not openid:
            raise ValueError("缺少微信 openid")
        from .identity import IdentityLinkService

        link_result = IdentityLinkService(db=self.db).link_wechat(
            openid=openid,
            unionid=unionid,
            phone=self._profile_phone(profile),
            profile=profile,
        )
        if int(link_result.get("code") or 0) != 0:
            raise ValueError(link_result.get("msg") or "微信身份绑定失败")
        user_id = int((link_result.get("data") or {}).get("user_id") or 0)
        native = self.user_by_id(user_id)
        return native or {
            "id": user_id,
            "username": f"wechat:{hashlib.sha1(openid.encode('utf-8')).hexdigest()[:24]}",
            "display_name": profile.get("nickName") or profile.get("nickname") or "微信用户",
            "role": "customer",
            "approval_status": "approved" if self._profile_phone(profile) else "pending",
            "is_active": 1,
            "is_admin": 0,
        }

    def wechat_quick_login(
        self,
        *,
        openid: str = "",
        unionid: str = "",
        profile: dict | None = None,
        authcode: str = "",
        phone_code: str = "",
        appid: str = "",
        ip: str = "",
        user_agent: str = "",
    ) -> dict:
        openid = str(openid or "").strip()
        unionid = str(unionid or "").strip()
        profile = profile if isinstance(profile, dict) else {}
        if not openid:
            if not authcode:
                return {"code": 400, "msg": "缺少微信登录 code 或 openid", "_http_status": 400}
            wx_result = self.wechat_session_from_code(authcode, appid)
            if int(wx_result.get("code", -1)) != 0:
                return {**wx_result, "_http_status": 400}
            wx_data = wx_result.get("data") or {}
            openid = str(wx_data.get("openid") or "")
            unionid = str(wx_data.get("unionid") or unionid or "")
        if phone_code and not self._profile_phone(profile):
            phone_result = self.wechat_phone_from_code(phone_code, appid)
            if int(phone_result.get("code", -1)) != 0:
                return {**phone_result, "_http_status": int(phone_result.get("_http_status") or 400)}
            phone_info = (phone_result.get("data") or {}).get("phone_info")
            if isinstance(phone_info, dict):
                profile = {**profile, **phone_info}
        from .identity import IdentityLinkService

        link_result = IdentityLinkService(db=self.db).link_wechat(
            openid=openid,
            unionid=unionid,
            phone=self._profile_phone(profile),
            profile=profile,
        )
        if int(link_result.get("code") or 0) != 0:
            return {**link_result, "_http_status": int(link_result.get("_http_status") or 400)}
        user_id = int((link_result.get("data") or {}).get("user_id") or 0)
        user_row = self.user_by_id(user_id)
        if not user_row:
            return {"code": 404, "msg": "微信账号绑定后未找到用户", "_http_status": 404}
        user = self.user_public(user_row)
        if int(user.get("is_active") or 0) != 1 or str(user.get("approval_status") or "") != "approved":
            return {"code": 403, "msg": "微信账号已绑定，等待后台启用或审批", "data": {"user": user}, "_http_status": 403}
        if not self.user_can_access_miniapp(user):
            return {"code": 403, "msg": "当前微信账号未开通业务操作权限", "data": {"user": user}, "_http_status": 403}
        token = self.issue_session(int(user["id"]), client_type="miniapp", ip=ip, user_agent=user_agent)
        user = self.user_public(user_row, token=token)
        _TOKEN_CACHE[token] = (time.time() + _TOKEN_CACHE_TTL, user)
        return {"code": 0, "data": {"token": token, "user": user}}


def get_auth_service() -> AuthService:
    return AuthService()
