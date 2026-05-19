"""Shared color normalization and extraction helpers."""

from __future__ import annotations

from scripts.common.color_filter import (
    COLOR_ALIASES as CONFIG_COLOR_ALIASES,
    STANDARD_COLORS as CONFIG_STANDARD_COLORS,
    filter_uv,
)


EXTRA_STANDARD_COLORS = [
    "紫色",
    "粉色",
]

EXTRA_COLOR_ALIASES = {
    "深咖色": "咖色",
    "深咖": "咖色",
    "咖啡色": "咖色",
    "棕咖色": "咖色",
}


STANDARD_COLORS = list(dict.fromkeys([*CONFIG_STANDARD_COLORS, *EXTRA_STANDARD_COLORS]))
COLOR_ALIASES = {**CONFIG_COLOR_ALIASES, **EXTRA_COLOR_ALIASES}


def known_colors() -> list[str]:
    """Return all color tokens that should be removed from product names."""
    return list(dict.fromkeys([*STANDARD_COLORS, *COLOR_ALIASES.keys(), *COLOR_ALIASES.values()]))


def normalize_color(color: str | None) -> str:
    """Normalize aliases and UV suffixes to one ERP-facing color value."""
    value = filter_uv(str(color or "").strip())
    return COLOR_ALIASES.get(value, value)


def extract_color_from_text(text: str | None) -> str:
    """Extract the longest known color token from arbitrary product text."""
    value = filter_uv(str(text or ""))
    if not value:
        return ""

    for color in sorted(STANDARD_COLORS, key=len, reverse=True):
        if color and color in value:
            return normalize_color(color)

    for alias in sorted(COLOR_ALIASES, key=len, reverse=True):
        if alias and alias in value:
            return normalize_color(alias)

    return ""
