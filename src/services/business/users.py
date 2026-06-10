"""User-management business service."""

from __future__ import annotations

from .base import BusinessService
from .identity import IdentityLinkService


ROLE_ALIASES = {
    "管理员": "admin",
    "老板": "admin",
    "员工": "staff",
    "客户": "customer",
    "访客": "guest",
}
ALLOWED_ROLES = {"admin", "staff", "customer", "guest"}
_UNSET = object()


def _normalize_role(role: str | None) -> str | None:
    if role is None:
        return None
    value = str(role or "").strip()
    return ROLE_ALIASES.get(value, value)


def _normalize_active(value) -> int | None:
    if value is None:
        return None
    if isinstance(value, str):
        clean = value.strip().lower()
        if clean in {"false", "off", "no"}:
            return 0
        if clean in {"true", "on", "yes"}:
            return 1
    return 1 if int(value or 0) else 0


def _as_int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _is_admin_user(user: dict | None) -> bool:
    if not isinstance(user, dict):
        return False
    return _as_int(user.get("is_admin")) == 1 or str(user.get("role") or "") == "admin"


class UserService(BusinessService):
    def list(self, *, keyword: str = "", page: int = 1, page_size: int = 50) -> tuple[list[dict], int]:
        return self.db.users(keyword=keyword, page=page, page_size=page_size)

    def _user_snapshot(self, user_id: int) -> dict | None:
        rows = self.db.query(
            """
            SELECT id, role, is_admin, is_active
            FROM auth_user
            WHERE id=%s
            LIMIT 1
            """,
            (int(user_id),),
        )
        return rows[0] if rows else None

    def _active_admin_count_excluding(self, user_id: int) -> int:
        rows = self.db.query(
            """
            SELECT COUNT(*) AS total
            FROM auth_user
            WHERE id<>%s AND is_active=1 AND (is_admin=1 OR role='admin')
            """,
            (int(user_id),),
        )
        return int((rows[0] if rows else {}).get("total") or 0)

    def _permission_update_guard(
        self,
        user_id: int,
        *,
        role: str | None = None,
        is_active: int | None = None,
        operator_user_id=None,
    ) -> dict | None:
        if role is None and is_active is None:
            return None

        target_id = int(user_id)
        current = self._user_snapshot(target_id)
        if not current:
            return None

        current_role = _normalize_role(current.get("role")) or ""
        next_role = _normalize_role(role) if role is not None else current_role
        if role is not None and next_role not in ALLOWED_ROLES:
            return {"code": 400, "msg": "角色不正确"}

        current_active = _normalize_active(current.get("is_active"))
        next_active = _normalize_active(is_active) if is_active is not None else current_active
        operator_id = _as_int(operator_user_id)

        if operator_id and operator_id == target_id:
            if is_active is not None and next_active == 0:
                return {"code": 400, "msg": "不能停用当前登录账号"}
            if role is not None and next_role != current_role:
                return {"code": 400, "msg": "不能修改当前登录账号角色"}

        if _is_admin_user(current) and current_active == 1:
            next_is_admin = next_role == "admin"
            if next_active != 1 or not next_is_admin:
                if self._active_admin_count_excluding(target_id) <= 0:
                    return {"code": 400, "msg": "不能停用或降权最后一个管理员"}

        return None

    def update(
        self,
        user_id: int,
        *,
        role: str | None = None,
        is_active: int | None = None,
        phone: str | None = None,
        display_name: str | None = None,
        linked_party_id=_UNSET,
        operator_user_id=None,
    ) -> dict:
        result = None
        if role is not None or is_active is not None or display_name is not None or linked_party_id is not _UNSET:
            blocked = self._permission_update_guard(
                user_id,
                role=role,
                is_active=is_active,
                operator_user_id=operator_user_id,
            )
            if blocked is not None:
                return blocked
            update_kwargs = {
                "role": _normalize_role(role) if role is not None else None,
                "is_active": _normalize_active(is_active) if is_active is not None else None,
                "display_name": display_name,
            }
            if linked_party_id is not _UNSET:
                update_kwargs["linked_party_id"] = linked_party_id
            result = self.db.update_user(user_id, **update_kwargs)
            if isinstance(result, dict) and result.get("code") not in (None, 0):
                return result
        if phone is not None:
            link_result = IdentityLinkService(db=self.db).sync_user_phone(
                user_id,
                phone,
                operator_user_id=operator_user_id,
            )
            if result is None:
                return link_result
            data = result.setdefault("data", {})
            data["identity_link"] = link_result.get("data") if isinstance(link_result, dict) else link_result
            if isinstance(link_result, dict) and link_result.get("code") not in (None, 0):
                result["code"] = link_result.get("code")
                result["msg"] = link_result.get("msg")
        if result is None:
            return {"code": 400, "msg": "没有要更新的字段"}
        return result


def get_user_service() -> UserService:
    return UserService()
