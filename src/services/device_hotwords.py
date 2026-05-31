"""Device ASR hotword response builder."""

from __future__ import annotations

import hashlib

from src.services.volc_realtime_asr import get_volc_realtime_asr_config


FIXED_DEVICE_HOTWORDS = (
    "小星",
    "晓星",
    "小新",
    "库存",
    "查库存",
    "查询库存",
    "多少钱",
    "价格",
    "售价",
    "单价",
    "客户",
    "礼盒",
    "见喜",
    "喜悦",
    "喜语",
    "岩味",
    "岩彩",
    "茶派",
    "半斤",
    "长半斤",
    "短半斤",
    "三两",
    "二三两",
    "二两",
    "一两",
    "三小盒",
    "六小盒",
    "十小盒",
    "百鑫",
    "百鑫仓库",
    "自己店里",
    "店里",
    "本店",
    "红色",
    "黄色",
    "橙色",
    "蓝色",
    "咖色",
    "卡其色",
)


def build_device_asr_hotwords_response(*, device_id: str = "") -> dict:
    words = _merge_hotwords(FIXED_DEVICE_HOTWORDS, get_volc_realtime_asr_config().hotwords)
    digest = hashlib.sha1("\n".join(words).encode("utf-8")).hexdigest()[:12]
    return {
        "version": f"device-hotwords-{digest}",
        "device_id": device_id,
        "ttl_seconds": 3600,
        "hotwords": words,
    }


def _merge_hotwords(*groups) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for raw in group or ():
            word = str(raw or "").strip()
            if not word or word in seen:
                continue
            seen.add(word)
            result.append(word)
    return result
