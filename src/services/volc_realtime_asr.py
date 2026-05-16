"""Volcengine Realtime ASR client for short PCM chunks."""
from __future__ import annotations

import asyncio
import base64
import inspect
import json
import os
from dataclasses import dataclass
from typing import Any

from src.core.config import get_config


class VolcRealtimeAsrError(RuntimeError):
    """Raised when Volcengine realtime ASR fails."""


@dataclass(frozen=True)
class VolcRealtimeAsrConfig:
    api_key: str
    ws_url: str
    model: str
    sample_rate: int
    chunk_ms: int
    send_interval_ms: int


def get_volc_realtime_asr_config() -> VolcRealtimeAsrConfig:
    config = get_config()
    return VolcRealtimeAsrConfig(
        api_key=os.getenv("VOLC_ASR_API_KEY") or config.get_with_env("volc_asr.api_key", ""),
        ws_url=os.getenv("VOLC_ASR_WS_URL")
        or config.get_with_env("volc_asr.ws_url", "wss://ai-gateway.vei.volces.com/v1/realtime"),
        model=os.getenv("VOLC_ASR_MODEL") or config.get_with_env("volc_asr.model", "bigmodel"),
        sample_rate=int(os.getenv("VOLC_ASR_SAMPLE_RATE") or config.get("volc_asr.sample_rate", 16000)),
        chunk_ms=int(os.getenv("VOLC_ASR_CHUNK_MS") or config.get("volc_asr.chunk_ms", 100)),
        send_interval_ms=int(os.getenv("VOLC_ASR_SEND_INTERVAL_MS") or config.get("volc_asr.send_interval_ms", 20)),
    )


def _session_update_payload(cfg: VolcRealtimeAsrConfig) -> str:
    return json.dumps(
        {
            "type": "transcription_session.update",
            "session": {
                "input_audio_format": "pcm",
                "input_audio_codec": "raw",
                "input_audio_sample_rate": cfg.sample_rate,
                "input_audio_bits": 16,
                "input_audio_channel": 1,
                "input_audio_transcription": {
                    "model": cfg.model,
                },
            },
        },
        ensure_ascii=False,
    )


def _extract_transcript(event: dict[str, Any]) -> str:
    value = event.get("transcript")
    if isinstance(value, str):
        return value.strip()
    return ""


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
    """Recognize raw PCM S16_LE mono audio through Volcengine Realtime API."""
    if not pcm:
        return ""
    cfg = get_volc_realtime_asr_config()
    if not cfg.api_key:
        raise VolcRealtimeAsrError("VOLC_ASR_API_KEY is not configured")

    try:
        import websockets
    except ImportError as exc:
        raise VolcRealtimeAsrError("websockets is not installed") from exc

    url = f"{cfg.ws_url}?model={cfg.model}"
    headers = {"Authorization": f"Bearer {cfg.api_key}"}
    bytes_per_chunk = int(cfg.sample_rate * (cfg.chunk_ms / 1000) * 2)
    send_interval = max(0, cfg.send_interval_ms) / 1000
    final_text = ""

    async def run() -> str:
        nonlocal final_text
        async with await _connect(websockets, url, headers) as client:
            await client.send(_session_update_payload(cfg))
            for offset in range(0, len(pcm), bytes_per_chunk):
                if send_interval:
                    await asyncio.sleep(send_interval)
                chunk = pcm[offset : offset + bytes_per_chunk]
                await client.send(
                    json.dumps(
                        {
                            "type": "input_audio_buffer.append",
                            "audio": base64.b64encode(chunk).decode("ascii"),
                        },
                        ensure_ascii=False,
                    )
                )
            await client.send(json.dumps({"type": "input_audio_buffer.commit"}))

            while True:
                message = await client.recv()
                event = json.loads(message)
                event_type = event.get("type")
                if event_type == "conversation.item.input_audio_transcription.result":
                    final_text = _extract_transcript(event) or final_text
                elif event_type == "conversation.item.input_audio_transcription.completed":
                    return _extract_transcript(event) or final_text
                elif event_type == "error":
                    raise VolcRealtimeAsrError(str(event)[:500])

    return await asyncio.wait_for(run(), timeout=timeout)


def recognize_pcm16(pcm: bytes, *, timeout: float = 15.0) -> str:
    return asyncio.run(recognize_pcm16_async(pcm, timeout=timeout))
