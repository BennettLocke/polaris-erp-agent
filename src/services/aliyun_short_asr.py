"""Short-sentence ASR through Aliyun NLS REST API."""
from __future__ import annotations

from urllib.parse import urlencode

import requests

from src.services.aliyun_asr import create_aliyun_token


class ShortAsrError(RuntimeError):
    """Raised when short ASR fails."""


def recognize_pcm16(
    pcm: bytes,
    *,
    sample_rate: int = 16000,
    timeout: int = 30,
    enable_voice_detection: bool = True,
) -> str:
    """Recognize a PCM S16_LE mono buffer with Aliyun one-shot ASR."""
    if not pcm:
        return ""
    token_info = create_aliyun_token()
    params = {
        "appkey": token_info["appkey"],
        "format": "pcm",
        "sample_rate": str(sample_rate),
        "enable_punctuation_prediction": "false",
        "enable_inverse_text_normalization": "true",
        "enable_voice_detection": "true" if enable_voice_detection else "false",
    }
    vocabulary_id = token_info.get("vocabulary_id") or ""
    if vocabulary_id:
        params["vocabulary_id"] = vocabulary_id
    url = f"https://nls-gateway-cn-shanghai.aliyuncs.com/stream/v1/asr?{urlencode(params)}"
    response = requests.post(
        url,
        data=pcm,
        headers={
            "X-NLS-Token": token_info["token"],
            "Content-Type": "application/octet-stream",
        },
        timeout=timeout,
    )
    if response.status_code >= 400:
        raise ShortAsrError(f"Aliyun ASR HTTP {response.status_code}: {response.text[:300]}")
    data = response.json()
    if int(data.get("status") or 0) != 20000000:
        raise ShortAsrError(f"Aliyun ASR failed: {str(data)[:300]}")
    return str(data.get("result") or "").strip()
