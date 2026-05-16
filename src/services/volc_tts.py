"""Volcengine Doubao streaming TTS service."""
from __future__ import annotations

import base64
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Callable

import requests

from src.core.config import get_config
from src.utils import get_logger

logger = get_logger("sjagent.services.volc_tts")


class VolcTTSError(RuntimeError):
    """Raised when Volcengine TTS fails."""


def _cfg() -> dict[str, Any]:
    config = get_config()
    return {
        "api_key": os.getenv("VOLC_TTS_API_KEY")
        or config.get_with_env("volc_tts.api_key", "")
        or os.getenv("VOLC_ASR_API_KEY")
        or config.get_with_env("volc_asr.api_key", ""),
        "app_id": os.getenv("VOLC_TTS_APP_ID") or config.get_with_env("volc_tts.app_id", ""),
        "access_key": os.getenv("VOLC_TTS_ACCESS_KEY") or config.get_with_env("volc_tts.access_key", ""),
        "resource_id": os.getenv("VOLC_TTS_RESOURCE_ID")
        or config.get_with_env("volc_tts.resource_id", "seed-tts-2.0"),
        "url": os.getenv("VOLC_TTS_URL")
        or config.get_with_env("volc_tts.url", "https://openspeech.bytedance.com/api/v3/tts/unidirectional"),
        "speaker": os.getenv("VOLC_TTS_SPEAKER")
        or config.get_with_env("volc_tts.speaker", "zh_female_vv_uranus_bigtts"),
        "format": os.getenv("VOLC_TTS_FORMAT") or config.get_with_env("volc_tts.format", "mp3"),
        "sample_rate": int(os.getenv("VOLC_TTS_SAMPLE_RATE") or config.get("volc_tts.sample_rate", 24000)),
        "speech_rate": int(os.getenv("VOLC_TTS_SPEECH_RATE") or config.get("volc_tts.speech_rate", 0)),
        "loudness_rate": int(os.getenv("VOLC_TTS_LOUDNESS_RATE") or config.get("volc_tts.loudness_rate", 0)),
        "output_dir": os.getenv("VOLC_TTS_OUTPUT_DIR")
        or config.get_with_env("volc_tts.output_dir", "./data/generated/voice/responses"),
    }


def _headers(cfg: dict[str, Any]) -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "Connection": "keep-alive",
        "X-Api-Resource-Id": str(cfg["resource_id"]),
        "X-Api-Request-Id": str(uuid.uuid4()),
    }
    if cfg.get("api_key"):
        headers["X-Api-Key"] = str(cfg["api_key"])
        return headers
    if cfg.get("app_id") and cfg.get("access_key"):
        headers["X-Api-App-Id"] = str(cfg["app_id"])
        headers["X-Api-Access-Key"] = str(cfg["access_key"])
        return headers
    raise VolcTTSError("VOLC_TTS_API_KEY or VOLC_TTS_APP_ID/VOLC_TTS_ACCESS_KEY is not configured")


def _output_path(path: str | Path | None, text: str, audio_format: str) -> Path:
    if path:
        return Path(path)
    safe_ts = time.strftime("%Y%m%d_%H%M%S")
    compact = "".join(ch for ch in text.strip()[:16] if ch.isalnum() or "\u4e00" <= ch <= "\u9fff")
    out_dir = Path(_cfg().get("output_dir") or "./data/generated/voice/responses")
    return out_dir / f"{safe_ts}_{compact or 'volc_tts'}.{audio_format}"


def _iter_json_lines(response: requests.Response):
    buffer = ""
    for chunk in response.iter_content(chunk_size=None):
        if not chunk:
            continue
        buffer += chunk.decode("utf-8", "replace")
        lines = buffer.splitlines()
        if buffer and not buffer.endswith(("\n", "\r")):
            buffer = lines.pop() if lines else buffer
        else:
            buffer = ""
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.startswith("data:"):
                line = line[5:].strip()
            if line == "[DONE]":
                continue
            yield json.loads(line)
    if buffer.strip():
        line = buffer.strip()
        if line.startswith("data:"):
            line = line[5:].strip()
        if line and line != "[DONE]":
            yield json.loads(line)


def synthesize_stream(
    text: str,
    output: str | Path | None = None,
    *,
    speaker: str | None = None,
    chunk_callback: Callable[[bytes], None] | None = None,
    timeout: int = 90,
) -> Path:
    """Synthesize text with Volcengine HTTP chunked TTS and save audio."""
    text = (text or "").strip()
    if not text:
        raise ValueError("TTS text is required")
    cfg = _cfg()
    audio_format = str(cfg["format"]).lower()
    target = _output_path(output, text, audio_format)
    target.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "user": {"uid": "sjagent-orangepi"},
        "req_params": {
            "text": text,
            "speaker": speaker or cfg["speaker"],
            "audio_params": {
                "format": audio_format,
                "sample_rate": cfg["sample_rate"],
                "speech_rate": cfg["speech_rate"],
                "loudness_rate": cfg["loudness_rate"],
            },
        },
    }
    logger.info(f"Volc TTS synthesize: chars={len(text)}, speaker={payload['req_params']['speaker']}")
    with requests.Session() as session:
        response = session.post(cfg["url"], headers=_headers(cfg), json=payload, stream=True, timeout=timeout)
        if response.status_code >= 400:
            raise VolcTTSError(f"Volc TTS HTTP {response.status_code}: {response.text[:300]}")
        wrote = 0
        with target.open("wb") as f:
            for item in _iter_json_lines(response):
                code = item.get("code")
                if code not in (None, 0, 20000000):
                    raise VolcTTSError(f"Volc TTS failed: {str(item)[:300]}")
                audio_b64 = item.get("data")
                if not audio_b64:
                    continue
                audio = base64.b64decode(audio_b64)
                f.write(audio)
                wrote += len(audio)
                if chunk_callback:
                    chunk_callback(audio)
    if wrote <= 0:
        raise VolcTTSError("Volc TTS returned no audio data")
    logger.info(f"Volc TTS wrote: {target}, bytes={wrote}")
    return target
