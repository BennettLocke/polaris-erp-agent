"""Device-facing voice command response builder."""

from __future__ import annotations

import time
import uuid
from collections import OrderedDict
from typing import Any

from src.core.skill_engine import SkillEngine
from src.services.business import get_inventory_service, get_product_service


UNCLEAR_REPLY = "没听清商品名，再说一遍。"
NO_SERVER_REPLY = "服务器没连上，稍后再试。"
TEXT_REPLACEMENTS = (
    ("喜越", "喜悦"),
    ("喜语", "喜悦"),
    ("裤存", "库存"),
    ("库子", "库存"),
    ("酷存", "库存"),
    ("裤子", "库存"),
)
PRICE_QUERY_WORDS = (
    "多少钱",
    "什么价格",
    "啥价格",
    "价格",
    "售价",
    "卖价",
    "单价",
    "多少钱一套",
    "一套多少钱",
    "多少一套",
    "几块",
    "几元",
    "几钱",
)


def build_device_voice_command_response(
    *,
    text: str,
    device_id: str = "",
    session_id: str = "",
    trace_id: str = "",
    asr_confidence: float | None = None,
) -> dict:
    started_at = time.perf_counter()
    trace_id = str(trace_id or f"voice-{int(time.time() * 1000)}-{uuid.uuid4().hex[:6]}")
    raw_text = str(text or "").strip()
    normalized_text = _normalize_command_text(raw_text)

    if _is_cancel_command(raw_text):
        return _base_response(
            trace_id=trace_id,
            intent="cancel",
            speak="好的。",
            display={"mode": "idle", "title": "待机", "summary": "", "items": []},
            device_action={"next_state": "idle", "listen_again": False, "command_window_seconds": 2, "screen_mode": "idle"},
            started_at=started_at,
        )

    if _is_unclear_command(normalized_text, asr_confidence):
        return _clarification_response(trace_id, started_at)

    if _is_price_query(normalized_text):
        return _build_price_response(
            raw_text=raw_text,
            normalized_text=normalized_text,
            trace_id=trace_id,
            started_at=started_at,
        )

    params = _extract_inventory_params(normalized_text)
    product_name = str(params.get("product_name") or "").strip()
    if not product_name:
        return _clarification_response(trace_id, started_at)

    color = str(params.get("color") or "").strip()
    warehouse_id = params.get("warehouse_id")
    rows = get_inventory_service().search(
        keyword=product_name,
        color=color,
        warehouse_id=warehouse_id,
        only_in_stock=True,
        limit=100,
    )
    rows = [row for row in rows if _row_qty(row) > 0]

    if not rows:
        return _base_response(
            trace_id=trace_id,
            intent="inventory_query",
            speak=f"没找到{product_name}的有库存记录，你再说一下名称。",
            display={
                "mode": "inventory_empty",
                "title": f"{product_name}库存",
                "summary": f"按{product_name}查询，未找到有库存记录",
                "query": _query_payload(
                    original_text=raw_text,
                    normalized_text=normalized_text,
                    product_name=product_name,
                    color=color,
                    warehouse_id=warehouse_id,
                ),
                "items": [],
            },
            device_action={"next_state": "listening", "listen_again": True, "command_window_seconds": 5, "screen_mode": "result"},
            started_at=started_at,
        )

    display = _inventory_display(
        product_name,
        rows,
        query=_query_payload(
            original_text=raw_text,
            normalized_text=normalized_text,
            product_name=product_name,
            color=color,
            warehouse_id=warehouse_id,
        ),
    )
    return _base_response(
        trace_id=trace_id,
        intent="inventory_query",
        speak=_inventory_speak(product_name, display["items"]),
        display=display,
        device_action={"next_state": "idle", "listen_again": False, "command_window_seconds": 2, "screen_mode": "result"},
        started_at=started_at,
    )


def _base_response(
    *,
    trace_id: str,
    intent: str,
    speak: str,
    display: dict,
    device_action: dict,
    started_at: float,
) -> dict:
    return {
        "ok": True,
        "trace_id": trace_id,
        "intent": intent,
        "speak": speak,
        "display": display,
        "device_action": device_action,
        "timing": {"server_ms": int((time.perf_counter() - started_at) * 1000)},
    }


def _clarification_response(trace_id: str, started_at: float) -> dict:
    return _base_response(
        trace_id=trace_id,
        intent="clarification",
        speak=UNCLEAR_REPLY,
        display={"mode": "clarification", "title": "没听清", "summary": UNCLEAR_REPLY, "items": []},
        device_action={"next_state": "listening", "listen_again": True, "command_window_seconds": 5, "screen_mode": "listen"},
        started_at=started_at,
    )


def _extract_inventory_params(text: str) -> dict:
    engine = object.__new__(SkillEngine)
    return engine._extract_inventory_params(text)


def _build_price_response(*, raw_text: str, normalized_text: str, trace_id: str, started_at: float) -> dict:
    query_text = _strip_price_query_words(normalized_text)
    params = _extract_inventory_params(query_text)
    product_name = str(params.get("product_name") or "").strip()
    if not product_name:
        return _clarification_response(trace_id, started_at)

    color = str(params.get("color") or "").strip()
    rows = get_product_service().search(product_name, limit=50, listed_only=False)
    items = _price_items(rows, product_name=product_name, color=color)
    query = _query_payload(
        original_text=raw_text,
        normalized_text=normalized_text,
        product_name=product_name,
        color=color,
        warehouse_id=None,
    )
    if not items:
        return _base_response(
            trace_id=trace_id,
            intent="price_query",
            speak=f"没找到{product_name}的价格，你再说一下名称。",
            display={
                "mode": "price_empty",
                "title": f"{product_name}价格",
                "summary": f"按{product_name}查询，未找到价格",
                "query": query,
                "items": [],
            },
            device_action={"next_state": "listening", "listen_again": True, "command_window_seconds": 5, "screen_mode": "result"},
            started_at=started_at,
        )

    display = _price_display(product_name, items, query=query)
    return _base_response(
        trace_id=trace_id,
        intent="price_query",
        speak=f"{product_name}{display['summary']}。",
        display=display,
        device_action={"next_state": "idle", "listen_again": False, "command_window_seconds": 2, "screen_mode": "result"},
        started_at=started_at,
    )


def _is_price_query(text: str) -> bool:
    compact = str(text or "").replace(" ", "")
    return any(word in compact for word in PRICE_QUERY_WORDS)


def _strip_price_query_words(text: str) -> str:
    value = str(text or "").strip()
    for word in sorted(PRICE_QUERY_WORDS, key=len, reverse=True):
        value = value.replace(word, "")
    return value.strip()


def _normalize_command_text(text: str) -> str:
    value = str(text or "").strip()
    for old, new in TEXT_REPLACEMENTS:
        value = value.replace(old, new)
    return value


def _is_cancel_command(text: str) -> bool:
    compact = text.replace(" ", "")
    return compact in {"没事", "没事了", "不用了", "取消", "算了", "好了"}


def _is_unclear_command(text: str, asr_confidence: float | None) -> bool:
    compact = text.replace(" ", "")
    if not compact:
        return True
    if asr_confidence is not None:
        try:
            if float(asr_confidence) < 0.35:
                return True
        except (TypeError, ValueError):
            pass
    if compact in {"嗯", "啊", "哦", "呃", "那个", "这个", "查一下", "查下", "库存"}:
        return True
    return len(compact) <= 1


def _row_text(row: dict, *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return ""


def _row_qty(row: dict) -> int:
    value = row.get("库存数量")
    if value in (None, ""):
        value = row.get("inventory", row.get("stock", row.get("qty", 0)))
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _money_value(row: dict) -> float:
    value = row.get("price")
    if value in (None, "", 0, "0", "0.00"):
        value = row.get("retail_price") or row.get("min_price") or row.get("max_price")
    try:
        return float(str(value or 0).replace(",", "").replace("¥", "").strip())
    except (TypeError, ValueError):
        return 0.0


def _money_text(value: float) -> str:
    if value <= 0:
        return ""
    if float(value).is_integer():
        return f"{int(value)}元"
    return f"{value:.2f}".rstrip("0").rstrip(".") + "元"


def _normalize_warehouse(name: str) -> str:
    if "百鑫" in name:
        return "百鑫库存"
    if "自己" in name or "店" in name or "本店" in name:
        return "自己店里"
    return name or "未知仓库"


def _clean_product_title(value: str) -> str:
    return str(value or "").replace("【", "").replace("】", "").strip()


def _compact_product_title(value: str) -> str:
    return _clean_product_title(value).replace(" ", "")


def _query_payload(
    *,
    original_text: str,
    normalized_text: str,
    product_name: str,
    color: str,
    warehouse_id,
) -> dict:
    return {
        "original_text": original_text,
        "normalized_text": normalized_text,
        "product_name": product_name,
        "color": color,
        "warehouse_id": warehouse_id,
    }


def _inventory_display(product_name: str, rows: list[dict], *, query: dict) -> dict:
    items = []
    total_qty = 0
    for row in rows:
        qty = _row_qty(row)
        total_qty += qty
        raw_warehouse = _row_text(row, "【仓库】", "warehouse", "warehouse_name", "仓库")
        items.append(
            {
                "product_id": row.get("product_id") or row.get("产品ID") or row.get("id"),
                "product_name": _row_text(row, "产品名称", "title", "name", "product_name") or product_name,
                "warehouse": raw_warehouse or "未知仓库",
                "warehouse_label": _normalize_warehouse(raw_warehouse),
                "warehouse_id": row.get("warehouse_id"),
                "color": _row_text(row, "【颜色】", "color", "spec", "颜色") or "默认",
                "qty": qty,
            }
        )
    corrected = query.get("original_text") != query.get("normalized_text")
    summary = f"共{len(items)}项，{total_qty}套"
    if corrected:
        summary = f"按{product_name}查询，{summary}"
    return {
        "mode": "inventory_result",
        "title": f"{product_name}库存",
        "summary": summary,
        "query": query,
        "items": items,
    }


def _price_items(rows: list[dict], *, product_name: str, color: str) -> list[dict]:
    items = []
    seen: set[tuple[str, str, str]] = set()
    for row in rows:
        row_color = _row_text(row, "color", "spec", "颜色", "【颜色】") or "默认"
        if color and color not in row_color:
            continue
        price = _money_value(row)
        price_text = _money_text(price)
        if not price_text:
            continue
        title = _clean_product_title(_row_text(row, "title", "name", "产品名称", "product_name") or product_name)
        key = (title, row_color, price_text)
        if key in seen:
            continue
        seen.add(key)
        items.append(
            {
                "product_id": row.get("product_id") or row.get("id"),
                "product_name": title,
                "color": row_color,
                "price": price,
                "price_text": price_text,
            }
        )
    return items


def _price_display(product_name: str, items: list[dict], *, query: dict) -> dict:
    price_values = {item.get("price_text") for item in items if item.get("price_text")}
    color = str(query.get("color") or "").strip()
    if color and len(items) == 1:
        summary = f"{items[0].get('color')}{items[0].get('price_text')}"
    elif len(price_values) == 1:
        summary = f"售价{next(iter(price_values))}"
    else:
        summary = "，".join(f"{item.get('color')}{item.get('price_text')}" for item in items[:6])
    return {
        "mode": "price_result",
        "title": f"{product_name}价格",
        "summary": summary,
        "query": query,
        "items": items,
    }


def _inventory_speak(product_name: str, items: list[dict]) -> str:
    grouped: OrderedDict[str, list[dict]] = OrderedDict()
    for item in items:
        grouped.setdefault(item.get("warehouse_label") or "未知仓库", []).append(item)

    query_name = _compact_product_title(product_name)
    item_names = [_compact_product_title(str(item.get("product_name") or product_name)) for item in items]
    include_item_names = any(name and name != query_name for name in item_names)

    parts = []
    for warehouse, rows in grouped.items():
        color_parts = []
        for row in rows:
            color = row.get("color") or "默认"
            qty = int(row.get("qty") or 0)
            if include_item_names:
                title = _clean_product_title(str(row.get("product_name") or product_name))
                color_parts.append(f"{title}{color}有{qty}套")
            else:
                color_parts.append(f"{color}有{qty}套")
        parts.append(f"{warehouse}{'，'.join(color_parts)}")
    return f"{product_name}，{'；'.join(parts)}。"
