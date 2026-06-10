"""Shared product-name normalization helpers."""

from __future__ import annotations

import re
from collections.abc import Iterable


PRODUCT_SPECS = [
    "五格短半斤",
    "短半斤",
    "二三两",
    "两大盒",
    "两泡装小盒",
    "二小盒",
    "三小盒",
    "六小盒",
    "十小盒",
    "半斤",
    "一两",
]


def normalize_half_jin_aliases(text: str) -> str:
    """Map long-half-jin aliases to half-jin while preserving short-half-jin."""
    value = str(text or "")
    if not value:
        return ""

    short_tokens: list[tuple[str, str]] = []

    def hold_short(match: re.Match) -> str:
        token = f"__SJ_SHORT_HALF_{len(short_tokens)}__"
        short_tokens.append((token, match.group(0)))
        return token

    value = re.sub(r"五格\s*短\s*款?\s*半\s*斤|短\s*款?\s*半\s*斤", hold_short, value)
    value = re.sub(r"长\s*款\s*半\s*斤|长\s*半\s*斤", "半斤", value)
    value = re.sub(r"0\.5\s*斤|半\s*斤", "半斤", value)

    for token, original in short_tokens:
        normalized_short = re.sub(r"\s+", "", original).replace("短款半斤", "短半斤")
        value = value.replace(token, normalized_short)
    return value


def normalize_liang_aliases(text: str) -> str:
    """Map 2/3-liang OCR and typing variants to 二三两."""
    value = str(text or "")
    return re.sub(r"(?:2\s*两|3\s*两|二\s*两|三\s*两|二\s*三\s*两)", "二三两", value)


def normalize_small_box_aliases(text: str) -> str:
    """Normalize common numeric/Chinese 小盒 specs."""
    value = str(text or "")
    replacements = (
        (r"(?:2|二|两)\s*小\s*盒", "二小盒"),
        (r"(?:3|三)\s*小\s*盒", "三小盒"),
        (r"(?:6|六)\s*小\s*盒", "六小盒"),
        (r"(?:10|十)\s*小\s*盒", "十小盒"),
    )
    for pattern, normalized in replacements:
        value = re.sub(pattern, normalized, value)
    return value


def normalize_product_name(
    name: str,
    *,
    colors: Iterable[str] | None = None,
    strip_brackets: bool = True,
    remove_colors: bool = True,
    specs: Iterable[str] | None = None,
) -> str:
    """Normalize OCR/order/search product text before matching ERP products."""
    value = str(name or "").strip()
    if strip_brackets:
        value = value.replace("【", "").replace("】", "").strip()
    if remove_colors and colors:
        for color in sorted({str(c) for c in colors if c}, key=len, reverse=True):
            value = value.replace(color, "")

    value = normalize_liang_aliases(value)
    value = re.sub(r"(?:2\s*大盒|两\s*大盒|二\s*大盒)", "两大盒", value)
    value = re.sub(r"(?:2\s*泡(?:盒|装小盒)?|二\s*泡(?:盒|装小盒)?|两\s*泡(?:盒|装小盒)?)", "两泡装小盒", value)
    value = normalize_half_jin_aliases(value)
    value = re.sub(r"(?:1\s*两|一\s*两)", "一两", value)

    value = normalize_small_box_aliases(value)

    spec_list = sorted(dict.fromkeys(specs or PRODUCT_SPECS), key=len, reverse=True)
    for spec in spec_list:
        index = value.find(spec)
        if index < 0:
            continue
        if index > 0 and not value[index - 1].isspace():
            value = f"{value[:index]} {value[index:]}"
        break
    return re.sub(r"\s+", " ", value).strip()


def product_keywords(name: str, *, specs: Iterable[str] | None = None) -> list[str]:
    normalized = normalize_product_name(name, specs=specs)
    spec_list = list(specs or PRODUCT_SPECS)
    keywords = [normalized]
    for spec in spec_list:
        if spec in normalized:
            brand = normalized.replace(spec, "").strip()
            if brand:
                keywords.append(f"{brand} {spec}")
                keywords.append(brand)
            keywords.append(spec)
            break
    compact = normalized.replace(" ", "")
    if compact != normalized:
        keywords.append(compact)
    return list(dict.fromkeys(k for k in keywords if k))


def product_terms(name: str, *, specs: Iterable[str] | None = None) -> list[str]:
    normalized = normalize_product_name(name, specs=specs)
    spec_list = list(specs or PRODUCT_SPECS)
    for spec in spec_list:
        if spec in normalized:
            brand = normalized.replace(spec, "").strip()
            return [term for term in (brand, spec) if term]
    return [normalized] if normalized else []
