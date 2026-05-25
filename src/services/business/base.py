"""Shared helpers for business services."""

from __future__ import annotations

from typing import Any

from src.engine.native_db import get_native_db_client


class BusinessService:
    """Thin service base around the sjagent_core data gateway."""

    def __init__(self, db: Any | None = None):
        self.db = db or get_native_db_client()
