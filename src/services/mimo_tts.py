"""MiMo text-to-speech service."""
from __future__ import annotations

import base64
import os
import time
from pathlib import Path
from typing import Any

import requests

from src.core.config import get_config
from src.utils import get_logger

logger = get_logger("sjagent.services.mimo_tts")


class MimoTTSError(RuntimeError):
    """Raised when MiMo TTS synthesis fails."""


def _cfg() -> dict[str, Any]:
    config = get_config().tts_config
    return {
        **config,
        "base_url": os.environ.get("MIMO_TTS_BASE_URL") or config.get("base_url"),
        "model": os.environ.get("MIMO_TTS_MODEL") or config.get("model"),
        "voice": os.environ.get("MIMO_TTS_VOICE") or config.get("voice"),
        "format": os.environ.get("MIMO_TTS_FORMAT") or config.get("format"),
        "api_key": os.environ.get("MIMO_TTS_API_KEY") or config.get("api_key"),
        "output_dir": os.environ.get("MIMO_TTS_OUTPUT_DIR") or config.get("output_dir"),
    }


def _output_path(path: str | Path | None, text: str, audio_format: str) -> Path:
    if path:
        return Path(path)
    safe_ts = time.strftime("%Y%m%d_%H%M%S")
    compact = "".join(ch for ch in text.strip()[:16] if ch.isalnum() or "\u4e00" <= ch <= "\u9fff")
    stem = compact or "tts"
    out_dir = Path(_cfg().get("output_dir") or "./data/generated/voice")
    return out_dir / f"{safe_ts}_{stem}.{audio_format}"


def synthesize(
    text: str,
    output: str | Path | None = None,
    *,
    context: str = "",
    voice: str | None = None,
    audio_format: str | None = None,
    timeout: int = 90,
) -> Path:
    """Synthesize speech with MiMo TTS and save it to a local file."""
    text = (text or "").strip()
    if not text:
        raise ValueError("TTS text is required")

    cfg = _cfg()
    api_key = cfg.get("api_key")
    if not api_key:
        raise MimoTTSError("MIMO_API_KEY is not configured")

    fmt = (audio_format or cfg.get("format") or "wav").strip().lower()
    target = _output_path(output, text, fmt)
    target.parent.mkdir(parents=True, exist_ok=True)

    messages = []
    if context:
        messages.append({"role": "user", "content": context})
    messages.append({"role": "assistant", "content": text})

    payload = {
        "model": cfg.get("model") or "mimo-v2-tts",
        "messages": messages,
        "audio": {
            "format": fmt,
            "voice": voice or cfg.get("voice") or "mimo_default",
        },
    }
    url = str(cfg.get("base_url") or "https://token-plan-cn.xiaomimimo.com/v1").rstrip("/")
    endpoint = f"{url}/chat/completions"

    logger.info(f"MiMo TTS synthesize: chars={len(text)}, voice={payload['audio']['voice']}, format={fmt}")
    response = requests.post(
        endpoint,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=timeout,
    )
    if response.status_code >= 400:
        raise MimoTTSError(f"MiMo TTS HTTP {response.status_code}: {response.text[:300]}")

    data = response.json()
    try:
        audio_b64 = data["choices"][0]["message"]["audio"]["data"]
    except (KeyError, IndexError, TypeError) as exc:
        raise MimoTTSError(f"MiMo TTS response missing audio data: {str(data)[:300]}") from exc

    target.write_bytes(base64.b64decode(audio_b64))
    logger.info(f"MiMo TTS wrote: {target}")
    return target


def synthesize_wake_reply(output: str | Path | None = None) -> Path:
    return synthesize("在呢", output, context="用户刚刚喊了小星。")
