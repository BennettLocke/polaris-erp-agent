"""Volcengine bigmodel streaming ASR client for short PCM chunks."""
from __future__ import annotations

import asyncio
import gzip
import inspect
import json
import os
import re
import time
import uuid
from dataclasses import dataclass
from queue import Queue
from threading import Thread
from typing import Any


from src.core.config import get_config
from src.engine.native_db import get_native_db_client


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
    hotwords: tuple[str, ...]


DEFAULT_HOTWORDS = (
    "小星",
    "晓星",
    "小新",
    "查询",
    "查库存",
    "查一下库存",
    "查询库存",
    "库存",
    "库存查询",
    "有库存",
    "有货",
    "仓库库存",
    "库存记录",
    "库存数量",
    "百鑫库存",
    "店里库存",
    "自己店里库存",
    "客户",
    "开单",
    "礼盒",
    "半斤",
    "长半斤",
    "短半斤",
    "三两",
    "二三两",
    "二两",
    "一两",
    "小盒",
    "中盒",
    "大盒",
    "三小盒",
    "六小盒",
    "两大盒",
)

_HOTWORD_CACHE: dict[str, Any] = {"expires_at": 0.0, "words": ()}
_HOTWORD_BLOCKLIST = {"小宁", "晓宁"}
_GIFT_KEYWORDS = (
    "半斤",
    "长半斤",
    "短半斤",
    "3两",
    "三两",
    "二三两",
    "2两",
    "二两",
    "1两",
    "一两",
    "2大盒",
    "二大盒",
    "两大盒",
    "3小盒",
    "三小盒",
    "6小盒",
    "六小盒",
    "10小盒",
    "十小盒",
    "小盒",
    "中盒",
    "大盒",
)
_NON_GIFT_TITLE_KEYWORDS = (
    "泡袋",
    "长泡袋",
    "红茶泡袋",
    "岩茶泡袋",
    "提袋",
    "内衬",
    "纸箱",
    "快递",
    "打包",
    "包装箱",
    "PVC",
)


def _clean_hotword(value: Any) -> str:
    text = str(value or "").strip()
    text = re.sub(r"SJ\d+", "", text, flags=re.IGNORECASE)
    text = text.replace("【", "").replace("】", "")
    text = re.sub(r"[^\w\u4e00-\u9fff]", "", text)
    return text[:24]


def _is_gift_box_title(title: str) -> bool:
    text = _clean_hotword(title)
    if any(keyword in text for keyword in _NON_GIFT_TITLE_KEYWORDS):
        return False
    return any(keyword in text for keyword in _GIFT_KEYWORDS)


def _add_hotword(words: list[str], seen: set[str], value: Any) -> None:
    word = _clean_hotword(value)
    if word in _HOTWORD_BLOCKLIST:
        return
    if len(word) < 2 or word in seen or not re.search(r"[\u4e00-\u9fff]", word):
        return
    seen.add(word)
    words.append(word)


def _series_from_title(title: str) -> str:
    text = _clean_hotword(title)
    for keyword in _GIFT_KEYWORDS:
        pos = text.find(keyword)
        if pos > 0:
            return text[:pos]
    return ""


def _fetch_dynamic_hotwords(limit: int) -> tuple[str, ...]:
    db = get_native_db_client()
    words: list[str] = []
    seen: set[str] = set()

    customer_rows = db.query(
        """
        SELECT name, contact_name
        FROM party
        WHERE deleted_at IS NULL
          AND status = 'active'
          AND kind IN ('customer', 'both')
        ORDER BY id DESC
        LIMIT %s
        """,
        (limit,),
    )
    for row in customer_rows:
        _add_hotword(words, seen, row.get("name"))
        _add_hotword(words, seen, row.get("contact_name"))

    product_rows = db.query(
        """
        SELECT DISTINCT sp.title, sp.series
        FROM product_spu sp
        JOIN product_sku s ON s.spu_id = sp.id AND s.deleted_at IS NULL
        WHERE sp.deleted_at IS NULL
          AND s.status = 'active'
          AND s.primary_category_id IN (1,2,3,4,7,8,9,10,11,14,15,18,19)
        ORDER BY sp.id DESC
        LIMIT %s
        """,
        (limit,),
    )
    for row in product_rows:
        title = row.get("title") or ""
        if not _is_gift_box_title(title):
            continue
        _add_hotword(words, seen, title)
        _add_hotword(words, seen, row.get("series"))
        _add_hotword(words, seen, _series_from_title(title))
    return tuple(words[:limit])

def _dynamic_hotwords(config, limit: int) -> tuple[str, ...]:
    enabled = str(config.get("volc_asr.dynamic_hotwords", "true")).lower() not in {"0", "false", "no"}
    if not enabled:
        return ()
    now = time.time()
    if now < float(_HOTWORD_CACHE.get("expires_at") or 0):
        return tuple(_HOTWORD_CACHE.get("words") or ())
    try:
        words = _fetch_dynamic_hotwords(limit)
        _HOTWORD_CACHE.update({"expires_at": now + 3600, "words": words})
        return words
    except Exception as exc:
        print(f"VOLC_HOTWORDS_WARNING {exc}", flush=True)
        _HOTWORD_CACHE.update({"expires_at": now + 300, "words": ()})
        return ()


def _split_hotwords(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        words = [part.strip() for part in value.replace("\n", ",").replace("，", ",").split(",")]
    elif isinstance(value, (list, tuple)):
        words = [str(item).strip() for item in value]
    else:
        words = []
    result: list[str] = []
    seen: set[str] = set()
    for word in [*DEFAULT_HOTWORDS, *words]:
        if word and word not in _HOTWORD_BLOCKLIST and word not in seen:
            seen.add(word)
            result.append(word)
    return tuple(result)


def _build_hotwords(config) -> tuple[str, ...]:
    configured = _split_hotwords(os.getenv("VOLC_ASR_HOTWORDS") or config.get("volc_asr.hotwords", []))
    limit = int(os.getenv("VOLC_ASR_HOTWORD_LIMIT") or config.get("volc_asr.hotword_limit", 500))
    result: list[str] = []
    seen: set[str] = set()
    for word in (*configured, *_dynamic_hotwords(config, limit)):
        if word and word not in seen:
            seen.add(word)
            result.append(word)
    return tuple(result[:limit])


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
        send_interval_ms=int(os.getenv("VOLC_ASR_SEND_INTERVAL_MS") or config.get("volc_asr.send_interval_ms", 0)),
        enable_nonstream=str(
            os.getenv("VOLC_ASR_ENABLE_NONSTREAM") or config.get("volc_asr.enable_nonstream", "true")
        ).lower()
        not in {"0", "false", "no"},
        hotwords=_build_hotwords(config),
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
    corpus = {"hotwords": [{"word": word} for word in cfg.hotwords]}
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
            "corpus": {"context": json.dumps(corpus, ensure_ascii=False)},
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


class VolcStreamingRecognizer:
    """Thread-backed streaming ASR session for live command capture."""

    def __init__(self, *, timeout: float = 15.0) -> None:
        self.timeout = timeout
        self._chunks: Queue[bytes | None] = Queue()
        self._result: Queue[str | BaseException] = Queue(maxsize=1)
        self._thread = Thread(target=self._thread_main, name="volc-streaming-asr", daemon=True)
        self._thread.start()

    def feed(self, pcm: bytes) -> None:
        if pcm:
            self._chunks.put(bytes(pcm))

    def finish(self) -> str:
        self._chunks.put(None)
        result = self._result.get(timeout=self.timeout + 5)
        self._thread.join(timeout=1)
        if isinstance(result, BaseException):
            raise result
        return result

    def _thread_main(self) -> None:
        try:
            self._result.put(asyncio.run(self._run()))
        except BaseException as exc:
            self._result.put(exc)

    async def _run(self) -> str:
        cfg = get_volc_realtime_asr_config()
        try:
            import websockets
        except ImportError as exc:
            raise VolcRealtimeAsrError("websockets is not installed") from exc

        headers = _build_headers(cfg)
        final_text = ""

        async def receive_loop(client: Any) -> str:
            nonlocal final_text
            while True:
                message_type, flags, event = _parse_frame(await client.recv())
                text = _extract_transcript(event)
                if text:
                    final_text = text
                if flags == 0x03:
                    return _extract_transcript(event) or final_text

        async with await _connect(websockets, cfg.ws_url, headers) as client:
            await client.send(_full_client_request(_init_payload(cfg)))
            _, _, event = _parse_frame(await client.recv())
            final_text = _extract_transcript(event) or final_text
            receiver = asyncio.create_task(receive_loop(client))
            pending: bytes | None = None
            try:
                while True:
                    chunk = await asyncio.to_thread(self._chunks.get)
                    if chunk is None:
                        if pending is not None:
                            await client.send(_audio_request(pending, is_last=True))
                        else:
                            await client.send(_audio_request(b"", is_last=True))
                        return await asyncio.wait_for(receiver, timeout=self.timeout)
                    if pending is not None:
                        await client.send(_audio_request(pending, is_last=False))
                    pending = chunk
            finally:
                if not receiver.done():
                    receiver.cancel()
