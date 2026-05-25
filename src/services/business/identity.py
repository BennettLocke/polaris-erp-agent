"""Identity linking service for users, customers, and WeChat identities."""

from __future__ import annotations

from typing import Any

from src.services.business.auth import phone_digits

from .base import BusinessService


class IdentityLinkService(BusinessService):
    """Centralize phone and external identity binding rules."""

    def link_wechat(
        self,
        *,
        openid: str,
        unionid: str = "",
        phone: str = "",
        profile: dict | None = None,
    ) -> dict:
        return self.db.identity_link_wechat(
            openid=str(openid or "").strip(),
            unionid=str(unionid or "").strip(),
            phone=phone_digits(phone),
            profile=profile if isinstance(profile, dict) else {},
        )

    def sync_user_phone(self, user_id: int, phone: str, *, operator_user_id: Any = None) -> dict:
        return self.db.identity_sync_user_phone(
            int(user_id),
            phone=phone_digits(phone),
            operator_user_id=operator_user_id,
        )

    def sync_customer_phone(self, customer_id: int, phone: str, *, operator_user_id: Any = None) -> dict:
        return self.db.identity_sync_customer_phone(
            int(customer_id),
            phone=phone_digits(phone),
            operator_user_id=operator_user_id,
        )


def get_identity_link_service() -> IdentityLinkService:
    return IdentityLinkService()
