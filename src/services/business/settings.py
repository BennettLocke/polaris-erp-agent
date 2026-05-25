"""Settings business service."""

from __future__ import annotations

from typing import Any

from .base import BusinessService


class SettingsService(BusinessService):
    def get(self, key: str) -> dict:
        return self.db.system_setting(key)

    def save(self, key: str, payload: dict, *, operator_user_id: Any = None) -> dict:
        return self.db.save_system_setting(key, payload, operator_user_id=operator_user_id)

    def sku_number_settings(self) -> dict:
        return self.db.sku_number_settings()

    def save_sku_number_settings(self, payload: dict, *, operator_user_id: Any = None) -> dict:
        return self.db.save_sku_number_settings(payload, operator_user_id=operator_user_id)

    def sales_print_settings(self) -> dict:
        return self.db.sales_print_settings()

    def save_sales_print_settings(self, payload: dict) -> dict:
        return self.db.save_sales_print_settings(payload)


def get_settings_service() -> SettingsService:
    return SettingsService()
