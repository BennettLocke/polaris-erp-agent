"""Volcengine bigmodel streaming ASR client for short PCM chunks."""
from __future__ import annotations

import asyncio
import gzip
import inspect
import json
import os
import uuid
from dataclasses import dataclass
from typing import Any

from src.core.config import get_config


class VolcRealtimeAsrError(RuntimeError):
    """Raised when Volcengine realtime ASR fails."""


@dataclass(frozen=True)
class VolcRealtimeAsrConfig:
    api_key: str
    app_key: str
    access_key: str
    resource_id: str
    ws_url: str
    model: str
    sample_rate: int
    chunk_ms: int
    send_interval_ms: int
    enable_nonstream: bool


def get_volc_realtime_asr_config() -> VolcRealtimeAsrConfig:
    config = get_config()
    return VolcRealtimeAsrConfig(
        api_key=os.getenv("VOLC_ASR_API_KEY") or config.get_with_env("volc_asr.api_key", ""),
        app_key=os.getenv("VOLC_ASR_APP_KEY") or config.get_with_env("volc_asr.app_key", ""),
        access_key=os.getenv("VOLC_ASR_ACCESS_KEY") or config.get_with_env("volc_asr.access_key", ""),
        resource_id=os.getenv("VOLC_ASR_RESOURCE_ID")
        or config.get_with_env("volc_asr.resource_id", "volc.bigasr.sauc.duration"),
        ws_url=os.getenv("VOLC_ASR_WS_URL")
        or config.get_with_env("volc_asr.ws_url", "wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_async"),
        model=os.getenv("VOLC_ASR_MODEL") or config.get_with_env("volc_asr.model", "bigmodel"),
        sample_rate=int(os.getenv("VOLC_ASR_SAMPLE_RATE") or config.get("volc_asr.sample_rate", 16000)),
        chunk_ms=int(os.getenv("VOLC_ASR_CHUNK_MS") or config.get("volc_asr.chunk_ms", 200)),
        send_interval_ms=int(os.getenv("VOLC_ASR_SEND_INTERVAL_MS") or config.get("volc_asr.send_interval_ms", 120)),
        enable_nonstream=str(
            os.getenv("VOLC_ASR_ENABLE_NONSTREAM") or config.get("volc_asr.enable_nonstream", "true")
        ).lower()
        not in {"0", "false", "no"},
    )


def _build_headers(cfg: VolcRealtimeAsrConfig) -> dict[str, str]:
    headers = {
        "X-Api-Resource-Id": cfg.resource_id,
        "X-Api-Connect-Id": str(uuid.uuid4()),
    }
    if cfg.api_key:
        headers["X-Api-Key"] = cfg.api_key
        return headers
    if cfg.app_key and cfg.access_key:
        headers["X-Api-App-Key"] = cfg.app_key
        headers["X-Api-Access-Key"] = cfg.access_key
        return headers
    raise VolcRealtimeAsrError("VOLC_ASR_API_KEY is not configured")


def _init_payload(cfg: VolcRealtimeAsrConfig) -> bytes:
    payload = {
        "user": {
            "uid": "sjagent-orangepi",
            "platform": "Linux",
        },
        "audio": {
            "format": "pcm",
            "codec": "raw",
            "rate": cfg.sample_rate,
            "bits": 16,
            "channel": 1,
            "language": "zh-CN",
        },
        "request": {
            "model_name": cfg.model,
            "enable_itn": True,
            "enable_punc": False,
            "enable_ddc": False,
            "show_utterances": True,
            "enable_nonstream": cfg.enable_nonstream,
            "end_window_size": 600,
            "force_to_speech_time": 500,
            "corpus": {
                "context": json.dumps(
                    {"hotwords": [{"word": "小星"}, {"word": "库存"}, {"word": "泡袋"}]},
                    ensure_ascii=False,
                ),
            },
        },
    }
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def _extract_transcript(event: dict[str, Any]) -> str:
    result = event.get("result")
    if isinstance(result, dict):
        text = result.get("text")
        if isinstance(text, str) and text.strip():
            return text.strip()
        utterances = result.get("utterances")
        if isinstance(utterances, list):
            parts = [str(item.get("text") or "").strip() for item in utterances if isinstance(item, dict)]
            return "".join(part for part in parts if part).strip()
    text = event.get("text") or event.get("transcript")
    if isinstance(text, str):
        return text.strip()
    return ""


def _frame(message_type: int, flags: int, serialization: int, compression: int, payload: bytes) -> bytes:
    body = gzip.compress(payload) if compression == 1 else payload
    header = bytes(
        [
            0x11,
            ((message_type & 0x0F) << 4) | (flags & 0x0F),
            ((serialization & 0x0F) << 4) | (compression & 0x0F),
            0x00,
        ]
    )
    return header + len(body).to_bytes(4, "big", signed=False) + body


def _full_client_request(payload: bytes) -> bytes:
    return _frame(0x01, 0x00, 0x01, 0x01, payload)


def _audio_request(payload: bytes, *, is_last: bool = False) -> bytes:
    return _frame(0x02, 0x02 if is_last else 0x00, 0x00, 0x01, payload)


def _parse_frame(data: bytes) -> tuple[int, int, dict[str, Any]]:
    if len(data) < 8:
        raise VolcRealtimeAsrError("Volc ASR returned a short frame")
    header_size = (data[0] & 0x0F) * 4
    message_type = data[1] >> 4
    flags = data[1] & 0x0F
    serialization = data[2] >> 4
    compression = data[2] & 0x0F
    offset = header_size

    if message_type == 0x0F:
        if len(data) < offset + 8:
            raise VolcRealtimeAsrError("Volc ASR returned a short error frame")
        code = int.from_bytes(data[offset : offset + 4], "big", signed=False)
        size = int.from_bytes(data[offset + 4 : offset + 8], "big", signed=False)
        message = data[offset + 8 : offset + 8 + size].decode("utf-8", "replace")
        raise VolcRealtimeAsrError(f"Volc ASR error {code}: {message}")

    if message_type != 0x09:
        return message_type, flags, {}

    if flags in {0x01, 0x03}:
        offset += 4
    if len(data) < offset + 4:
        raise VolcRealtimeAsrError("Volc ASR returned a response without payload size")
    size = int.from_bytes(data[offset : offset + 4], "big", signed=False)
    payload = data[offset + 4 : offset + 4 + size]
    if compression == 1:
        payload = gzip.decompress(payload)
    if serialization == 1 and payload:
        return message_type, flags, json.loads(payload.decode("utf-8"))
    return message_type, flags, {}


async def _connect(websockets_module: Any, url: str, headers: dict[str, str]):
    connect = websockets_module.connect
    kwargs = {"ping_interval": None}
    params = inspect.signature(connect).parameters
    if "additional_headers" in params:
        kwargs["additional_headers"] = headers
    else:
        kwargs["extra_headers"] = headers
    return connect(url, **kwargs)


async def recognize_pcm16_async(pcm: bytes, *, timeout: float = 15.0) -> str:
    """Recognize raw PCM S16_LE mono audio through Volcengine streaming ASR."""
    if not pcm:
        return ""
    cfg = get_volc_realtime_asr_config()

    try:
        import websockets
    except ImportError as exc:
        raise VolcRealtimeAsrError("websockets is not installed") from exc

    headers = _build_headers(cfg)
    bytes_per_chunk = int(cfg.sample_rate * (cfg.chunk_ms / 1000) * 2)
    send_interval = max(0, cfg.send_interval_ms) / 1000
    final_text = ""

    async def run() -> str:
        nonlocal final_text
        async with await _connect(websockets, cfg.ws_url, headers) as client:
            await client.send(_full_client_request(_init_payload(cfg)))
            message_type, flags, event = _parse_frame(await client.recv())
            final_text = _extract_transcript(event) or final_text

            for offset in range(0, len(pcm), bytes_per_chunk):
                if send_interval:
                    await asyncio.sleep(send_interval)
                chunk = pcm[offset : offset + bytes_per_chunk]
                is_last = offset + bytes_per_chunk >= len(pcm)
                await client.send(_audio_request(chunk, is_last=is_last))

            while True:
                message_type, flags, event = _parse_frame(await client.recv())
                text = _extract_transcript(event)
                if text:
                    final_text = text
                if flags == 0x03:
                    return _extract_transcript(event) or final_text

    return await asyncio.wait_for(run(), timeout=timeout)


def recognize_pcm16(pcm: bytes, *, timeout: float = 15.0) -> str:
    return asyncio.run(recognize_pcm16_async(pcm, timeout=timeout))
