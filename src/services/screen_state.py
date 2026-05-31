"""Shared state helpers for the Orange Pi screen page."""

from __future__ import annotations

import os
import time
from collections import deque
from typing import Any

import requests


MAX_MESSAGES = int(os.getenv("SJ_SCREEN_MAX_MESSAGES", "8"))
DEFAULT_SCREEN_STATE_URL = os.getenv("SJ_SCREEN_STATE_URL", "http://127.0.0.1:8080/api/screen/state")

_messages: deque[dict[str, Any]] = deque(maxlen=MAX_MESSAGES)
_state: dict[str, Any] = {
    "status": "idle",
    "expression": "idle",
    "message": "",
    "latest": {},
    "display": {},
    "messages": [],
    "updated_at": int(time.time()),
    "version": 0,
}


def _normalize_status(status: str | None) -> str:
    value = (status or "idle").strip().lower()
    aliases = {
        "listening": "listen",
        "speaking": "talk",
        "processing": "processing",
        "error": "error",
    }
    value = aliases.get(value, value)
    return value if value in {"idle", "listen", "talk", "processing", "error"} else "idle"


def update_screen_state(
    *,
    status: str | None = None,
    role: str | None = None,
    text: str | None = None,
    display: dict[str, Any] | None = None,
    source: str = "api",
    reset: bool = False,
) -> dict[str, Any]:
    """Update the in-process screen state and return a serializable snapshot."""

    if reset:
        _messages.clear()
    now = int(time.time())
    normalized_status = _normalize_status(status)
    clean_text = (text or "").strip()
    clean_role = (role or "").strip().lower()
    clean_display = display if isinstance(display, dict) else None
    if normalized_status == "processing":
        clean_text = ""
        clean_role = ""
    if clean_text and clean_role in {"user", "assistant", "system"}:
        item = {
            "role": clean_role,
            "text": clean_text,
            "source": source,
            "time": now,
        }
        if clean_display is not None:
            item["display"] = clean_display
        _messages.append(item)
        _state["latest"] = item
    if clean_display is not None:
        _state["display"] = clean_display
    _state.update(
        {
            "status": normalized_status,
            "expression": normalized_status,
            "message": clean_text or _state.get("message", ""),
            "messages": list(_messages),
            "updated_at": now,
            "version": int(_state.get("version") or 0) + 1,
        }
    )
    return get_screen_state()


def get_screen_state() -> dict[str, Any]:
    snapshot = dict(_state)
    snapshot["messages"] = list(_messages)
    return snapshot


def notify_screen_state(
    status: str,
    *,
    role: str | None = None,
    text: str | None = None,
    display: dict[str, Any] | None = None,
    url: str | None = None,
    timeout: float = 0.35,
) -> bool:
    """Best-effort HTTP update for processes outside the HTTP server."""

    target = url if url is not None else DEFAULT_SCREEN_STATE_URL
    if not target:
        return False
    try:
        response = requests.post(
            target,
            json={"status": status, "role": role, "text": text, "display": display},
            timeout=timeout,
        )
        return response.status_code < 400
    except Exception:
        return False
