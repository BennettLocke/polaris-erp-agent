"""Customer name cleanup helpers."""
from __future__ import annotations

import re


CRAFT_NAME_TOKENS = (
    "提袋丝印",
    "提袋UV",
    "提袋uv",
    "丝印",
    "UV",
    "uv",
    "印刷",
    "烫金",
    "烫银",
    "覆膜",
    "过膜",
)


def normalize_customer_name(name: str | None) -> str:
    """Remove OCR craft/remark fragments that are often glued to a customer name."""
    value = str(name or "").strip()
    if not value:
        return ""
    value = re.sub(r"^(客户|客人|客户名称|客户名)\s*[:：]?\s*", "", value).strip()
    value = re.split(r"[\n\r|｜,，;；]", value, maxsplit=1)[0].strip()
    value = re.sub(r"\s+", " ", value)
    for token in sorted(CRAFT_NAME_TOKENS, key=len, reverse=True):
        value = re.sub(rf"(?:\s+|^){re.escape(token)}$", "", value, flags=re.IGNORECASE).strip()
    return value


def has_customer_name_craft_noise(name: str | None) -> bool:
    value = str(name or "")
    return any(token.lower() in value.lower() for token in CRAFT_NAME_TOKENS)
