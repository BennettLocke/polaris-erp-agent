"""Shared concise reply formatter for voice and small-screen output."""

from __future__ import annotations

import re


def _inventory_summary(text: str, *, max_chars: int) -> str | None:
    if "库存查询" not in text or "|" not in text:
        return None

    product = ""
    rows: list[tuple[str, str, int]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("库存查询"):
            product = line.split("：", 1)[-1].replace(" ", "").strip()
            continue
        if not line.startswith("|") or "---" in line:
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 4 or cells[0] == "仓库" or cells[1] == "合计":
            continue
        try:
            qty = int(float(cells[-1]))
        except ValueError:
            continue
        warehouse, item_name, color = cells[0], cells[1], cells[2]
        if not product:
            product = item_name.replace("【", "").replace("】", "").replace(" ", "")
        rows.append((warehouse, color, qty))

    if not rows:
        return None

    grouped: dict[str, list[tuple[str, int]]] = {}
    for warehouse, color, qty in rows:
        label = "百鑫库存" if "百鑫" in warehouse else "自己店里" if ("自己" in warehouse or "店" in warehouse) else warehouse
        grouped.setdefault(label, []).append((color, qty))

    parts = []
    for warehouse, items in grouped.items():
        details = "，".join(f"{color or '未标颜色'}{qty}套" for color, qty in items)
        parts.append(f"{warehouse}{details}")
    summary = f"{product}：" + "；".join(parts)
    if len(summary) > max_chars:
        summary = summary[:max_chars].rstrip("，。；; ") + "。"
    return summary


def format_voice_reply(text: str, *, max_chars: int = 180) -> str:
    """Turn full agent output into the short version used by voice/screen."""

    value = (text or "").strip()
    inventory = _inventory_summary(value, max_chars=max_chars)
    if inventory:
        return inventory

    value = re.sub(r"https?://\S+", "", value)
    value = value.replace("```", "")
    lines: list[str] = []
    for raw in value.splitlines():
        line = raw.strip()
        if not line or line.startswith("|") or set(line) <= {"-", ":", "|", " "}:
            continue
        line = line.replace("**", "").replace("#", "").replace("`", "")
        line = re.sub(r"\s+", " ", line).strip()
        if line:
            lines.append(line)

    short = "。".join(lines) if lines else value
    short = re.sub(r"\s+", " ", short).strip()
    if len(short) > max_chars:
        short = short[:max_chars].rstrip("，。；; ") + "。"
    return short or "处理完成。"
