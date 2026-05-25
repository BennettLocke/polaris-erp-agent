"""User-management business service."""

from __future__ import annotations

from .base import BusinessService
from .identity import IdentityLinkService


class UserService(BusinessService):
    def list(self, *, keyword: str = "", page: int = 1, page_size: int = 50) -> tuple[list[dict], int]:
        return self.db.users(keyword=keyword, page=page, page_size=page_size)

    def update(
        self,
        user_id: int,
        *,
        role: str | None = None,
        is_active: int | None = None,
        phone: str | None = None,
        display_name: str | None = None,
        operator_user_id=None,
    ) -> dict:
        result = None
        if role is not None or is_active is not None or display_name is not None:
            result = self.db.update_user(user_id, role=role, is_active=is_active, display_name=display_name)
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
