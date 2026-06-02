"""Simple wake-word listener for the Orange Pi desktop robot.

Record short chunks from INMP441, send speech-like chunks to ASR, and play a
cached wake prompt when the transcript resembles
"小星".
"""
from __future__ import annotations

import argparse
import audioop
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import wave
from pathlib import Path
from array import array

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.services.local_robot_features import handle_local_robot_command, is_local_robot_command  # noqa: E402
from src.services.mimo_tts import synthesize  # noqa: E402
from src.services.volc_tts import synthesize_stream as synthesize_volc_stream  # noqa: E402
from src.services.volc_realtime_asr import VolcStreamingRecognizer  # noqa: E402
from src.services.volc_realtime_asr import recognize_pcm16 as recognize_pcm16_volc  # noqa: E402
from src.services.screen_state import notify_screen_state  # noqa: E402
from src.services.voice_reply_formatter import format_voice_reply  # noqa: E402
from src.services.voice_prompts import ensure_group, play_file, play_prompt  # noqa: E402


WAKE_WORDS = {
    "小星",
    "小新",
    "小兴",
    "小鑫",
    "小行",
    "小型",
    "小心",
    "小幸",
    "小明",
    "小鸣",
    "小名",
    "小红",
    "小机",
    "小鸡",
    "小宁",
    "小拧",
    "晓宁",
    "晓星",
    "晓新",
}
LEARNED_WAKE_PATH = ROOT / "data" / "generated" / "voice" / "wake_words.json"
IGNORABLE_VOICE_COMMANDS = {
    "\u55ef",
    "\u554a",
    "\u989d",
    "\u5443",
    "\u54e6",
    "\u597d",
    "\u597d\u7684",
    "\u884c",
    "\u53ef\u4ee5",
}
CANCEL_VOICE_COMMANDS = {
    "\u6ca1\u4e8b",
    "\u6ca1\u4e8b\u4e86",
    "\u6ca1\u4e8b\u513f",
    "\u4e0d\u7528",
    "\u4e0d\u7528\u4e86",
    "\u4e0d\u7528\u67e5\u4e86",
    "\u4e0d\u67e5\u4e86",
    "\u7b97\u4e86",
    "\u53d6\u6d88",
    "\u7ed3\u675f",
    "\u5148\u8fd9\u6837",
    "\u597d\u4e86",
    "\u505c",
    "\u505c\u4e00\u4e0b",
    "\u9000\u51fa",
}
UNCLEAR_VOICE_COMMANDS = {
    "\u770b\u4e00\u4e0b",
    "\u770b\u4e0b",
    "\u627e\u4e00\u4e0b",
    "\u627e\u4e0b",
    "\u67e5\u4e00\u4e0b",
    "\u67e5\u4e0b",
    "\u540c\u5b66",
}
VOICE_COMMAND_KEYWORDS = (
    "\u5e93\u5b58",
    "\u67e5",
    "\u627e",
    "\u770b",
    "\u5ba2\u6237",
    "\u5f00\u5355",
    "\u4e0b\u5355",
    "\u8ba2\u5355",
    "\u6253\u5370",
    "\u4e0a\u4f20",
    "\u6ce1\u888b",
    "\u793c\u76d2",
    "\u89c4\u5219",
)
INVENTORY_QUERY_MISHEARS = (
    "\u7ec3\u4e60",
    "\u8054\u7cfb",
    "\u8fde\u7eed",
    "\u7ec3\u7ec3",
    "\u641c\u7d22",
)


def load_learned_wake_words() -> set[str]:
    try:
        data = json.loads(LEARNED_WAKE_PATH.read_text(encoding="utf-8"))
        words = data.get("words", []) if isinstance(data, dict) else data
        return {str(word).strip() for word in words if str(word).strip()}
    except FileNotFoundError:
        return set()
    except Exception as exc:
        print(f"WAKE_LEARN_LOAD_ERROR {exc}", flush=True)
        return set()


def all_wake_words() -> set[str]:
    return WAKE_WORDS | load_learned_wake_words()


def learn_wake_variants(text: str) -> None:
    candidates = set(re.findall(r"[小晓][\u4e00-\u9fff]", text or ""))
    candidates = {word for word in candidates if 2 <= len(word) <= 3}
    if not candidates:
        return
    existing = load_learned_wake_words()
    updated = sorted((existing | candidates) - WAKE_WORDS)
    if sorted(existing) == updated:
        return
    try:
        LEARNED_WAKE_PATH.parent.mkdir(parents=True, exist_ok=True)
        LEARNED_WAKE_PATH.write_text(json.dumps({"words": updated}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"WAKE_LEARNED {','.join(sorted(candidates))}", flush=True)
    except Exception as exc:
        print(f"WAKE_LEARN_SAVE_ERROR {exc}", flush=True)


def normalize_text(text: str) -> str:
    return re.sub(r"[\s，。！？、,.!?]+", "", text or "")


def is_wake_text(text: str) -> bool:
    normalized = normalize_text(text)
    return any(word in normalized for word in all_wake_words())


def strip_wake_words(text: str) -> str:
    value = text or ""
    for word in sorted(all_wake_words(), key=len, reverse=True):
        value = value.replace(word, "")
    value = re.sub(r"^[，。！？、,.!?\s]+", "", value)
    return value.strip()


def normalize_command_text(text: str) -> str:
    value = (text or "").strip()
    for word in sorted(all_wake_words(), key=len, reverse=True):
        value = re.sub(rf"^{re.escape(word)}[，。！？、,.!?\s]*", "", value)
    value = re.sub(r"^(帮我|帮忙|麻烦|请|去|给我|你去|帮我去)", "", value).strip()
    value = re.sub(r"^(查一下|查下|查询|找一下|找下|看一下|看下)", "", value).strip()
    value = re.sub(r"(裤子|库子|酷子)", "库存", value)
    if "\u5e93\u5b58" in value:
        for misheard in INVENTORY_QUERY_MISHEARS:
            if value.startswith(misheard):
                value = "\u67e5\u8be2" + value[len(misheard) :]
                break
    return value


def is_ignorable_voice_command(text: str) -> bool:
    normalized = normalize_text(text)
    return normalized in IGNORABLE_VOICE_COMMANDS or len(normalized) <= 1


def is_cancel_voice_command(text: str) -> bool:
    normalized = normalize_text(text)
    return normalized in CANCEL_VOICE_COMMANDS


def is_unclear_voice_command(text: str) -> bool:
    normalized = normalize_text(text)
    if normalized in UNCLEAR_VOICE_COMMANDS:
        return True
    if len(normalized) <= 2:
        return True
    if len(normalized) <= 4 and not any(keyword in normalized for keyword in VOICE_COMMAND_KEYWORDS):
        return True
    return bool(re.fullmatch(r"(?:\u5e2e\u6211)?(?:\u770b|\u627e|\u67e5)(?:\u4e00\u4e0b|\u4e0b)?", normalized))


def is_uncertain_agent_result(text: str) -> bool:
    value = normalize_text(text)
    return (
        "\u672a\u627e\u5230\u5546\u54c1" in value
        or "\u6ca1\u627e\u5230\u5546\u54c1" in value
        or ("\u672a\u627e\u5230" in value and "\u5e93\u5b58\u8bb0\u5f55" in value)
    )


def _spoken_inventory_summary(text: str, *, max_chars: int) -> str | None:
    if "库存查询" not in text or "总计" not in text:
        return None

    product = ""
    total_qty = ""
    total_rows = ""
    items: list[tuple[str, str, str, int]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("库存查询"):
            product = line.split("：", 1)[-1].strip()
            continue
        match = re.search(r"总计[:：]\s*(\d+)\s*条有库存记录[，,]\s*(\d+)\s*套", line)
        if match:
            total_rows, total_qty = match.groups()
            continue
        if not line.startswith("|") or "---" in line or "仓库" in line and "库存" in line:
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 4:
            continue
        try:
            qty = int(float(cells[-1]))
        except ValueError:
            continue
        warehouse, item_name, color = cells[0], cells[1], cells[2]
        if item_name == "合计":
            continue
        items.append((warehouse, item_name, color, qty))

    if not total_qty and not items:
        return None
    if not product and items:
        product = items[0][1].replace("【", "").replace("】", "")

    warehouses = []
    for warehouse, *_ in items:
        if warehouse and warehouse not in warehouses:
            warehouses.append(warehouse)

    by_warehouse: dict[str, list[tuple[str, int]]] = {}
    for warehouse, _, color, qty in items:
        label = "百鑫库存" if "百鑫" in warehouse else "自己店里" if ("自己" in warehouse or "店" in warehouse) else warehouse
        by_warehouse.setdefault(label, []).append((color, qty))
    colors = [color for _, _, color, _ in items if color]
    unique_colors = []
    for color in colors:
        if color not in unique_colors:
            unique_colors.append(color)
    product_prefix = product.replace(" ", "")
    if len(unique_colors) == 1 and unique_colors[0] not in product_prefix:
        product_prefix += unique_colors[0]
    warehouse_summaries = []
    for warehouse, rows in by_warehouse.items():
        details = "，".join(f"{color or '未标颜色'}有{qty}套" for color, qty in rows)
        warehouse_summaries.append(f"{warehouse}{details}")
    if warehouse_summaries:
        prefix = f"{product_prefix}，" if product_prefix else ""
        summary = prefix + "；".join(warehouse_summaries) + "。"
        if len(summary) > max_chars:
            summary = summary[:max_chars].rstrip("，。；; ") + "。"
        return summary

    color_parts = [f"{color}{qty}套" if color else f"{qty}套" for _, _, color, qty in items[:6]]
    if len(items) > 6:
        color_parts.append(f"另外还有{len(items) - 6}条")

    prefix = f"{product}，" if product else ""
    if total_qty:
        summary = f"{prefix}共{total_qty}套"
        if total_rows:
            summary += f"，{total_rows}条库存"
    else:
        summary = prefix.rstrip("，")
    if warehouses:
        summary += f"，在{'、'.join(warehouses[:2])}"
        if len(warehouses) > 2:
            summary += f"等{len(warehouses)}个仓库"
    if color_parts:
        summary += f"。明细：{'，'.join(color_parts)}。"
    else:
        summary += "。"
    if len(summary) > max_chars:
        summary = summary[:max_chars].rstrip("，。；; ") + "。"
    return summary


def spoken_text(text: str, *, max_chars: int = 180) -> str:
    return format_voice_reply(text, max_chars=max_chars)

    value = (text or "").strip()
    inventory_summary = _spoken_inventory_summary(value, max_chars=max_chars)
    if inventory_summary:
        return inventory_summary

    value = re.sub(r"https?://\S+", "", value)
    value = value.replace("```", "")
    lines = []
    for line in value.splitlines():
        clean = line.strip()
        if not clean or set(clean) <= {"|", "-", ":", " "}:
            continue
        clean = clean.strip("|").replace("|", "，")
        clean = re.sub(r"\s+", " ", clean)
        lines.append(clean)
    value = "。".join(lines) if lines else value
    value = re.sub(r"[#*_`>]+", "", value)
    value = re.sub(r"\s+", " ", value).strip()
    if len(value) > max_chars:
        value = value[:max_chars].rstrip("，。；; ") + "。后面内容我已经查到，可以在网页里看完整结果。"
    return value or "处理完成。"


_AGENT = None


def run_agent_command(command: str, *, session_id: str) -> str:
    global _AGENT
    if _AGENT is None:
        from src.core.agent import Agent

        _AGENT = Agent()
    return _AGENT.run(command, user_id="orangepi_voice", session_id=session_id)


def post_device_command(args, command: str) -> dict:
    payload = {
        "device_id": getattr(args, "device_id", "") or "",
        "session_id": getattr(args, "agent_session_id", "") or "orangepi_voice",
        "trace_id": f"voice-{int(time.time() * 1000)}",
        "source": "voice",
        "text": command,
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        getattr(args, "device_command_url"),
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=getattr(args, "device_command_timeout", 8)) as response:
        raw = response.read().decode("utf-8", "replace")
    body = json.loads(raw or "{}")
    if int(body.get("code") or 0) != 0:
        raise RuntimeError(body.get("msg") or "device command api failed")
    result = body.get("data") if isinstance(body.get("data"), dict) else {}
    return result


def record_wav(path: Path, *, device: str, seconds: float) -> None:
    subprocess.run(
        [
            "arecord",
            "-q",
            "-D",
            device,
            "-f",
            "S32_LE",
            "-r",
            "48000",
            "-c",
            "2",
            "-d",
            str(max(1, math.ceil(seconds))),
            str(path),
        ],
        check=True,
    )


def wav_to_pcm16(path: Path, *, gain: float = 1.0) -> tuple[bytes, int]:
    with wave.open(str(path), "rb") as wav:
        channels = wav.getnchannels()
        width = wav.getsampwidth()
        rate = wav.getframerate()
        frames = wav.readframes(wav.getnframes())

    if channels >= 2:
        frames = best_stereo_channel(frames, width)
        channels = 1
    if rate != 16000:
        frames, _ = audioop.ratecv(frames, width, channels, rate, 16000, None)
        rate = 16000
    if width != 2:
        frames = audioop.lin2lin(frames, width, 2)
        width = 2
    if gain and gain != 1.0:
        frames = audioop.mul(frames, width, gain)
    avg = audioop.avg(frames, width)
    if avg:
        frames = audioop.bias(frames, width, -avg)
    return frames, activity_rms(frames, width, rate)


def pcm16_duration_ms(pcm: bytes, *, rate: int = 16000) -> int:
    return int(len(pcm) / 2 / rate * 1000) if pcm else 0


def _pcm16_frame_size(rate: int, frame_ms: int) -> int:
    return max(2, int(rate * frame_ms / 1000) * 2)


def _pcm16_frame_rms(pcm: bytes, *, rate: int = 16000, frame_ms: int = 20) -> list[int]:
    frame_size = _pcm16_frame_size(rate, frame_ms)
    return [
        audioop.rms(pcm[offset : offset + frame_size], 2)
        for offset in range(0, len(pcm) - frame_size + 1, frame_size)
    ]


def _percentile(values: list[int], ratio: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * ratio))))
    return ordered[index]


def _asr_activity_threshold(values: list[int], args) -> int:
    if not values:
        return args.asr_trim_min_rms
    noise = _percentile(values, 0.20)
    peak = max(values)
    adaptive = int(noise * args.asr_noise_ratio + args.asr_noise_margin)
    # Do not let one loud transient force the gate too high.
    ceiling = max(args.asr_trim_min_rms, int(peak * 0.45))
    return min(max(args.asr_trim_min_rms, adaptive), ceiling)


def trim_pcm16_silence(pcm: bytes, *, threshold: int, rate: int = 16000, frame_ms: int = 20, keep_ms: int = 120) -> bytes:
    if not pcm:
        return pcm
    frame_size = _pcm16_frame_size(rate, frame_ms)
    frames = [
        (offset, pcm[offset : offset + frame_size])
        for offset in range(0, len(pcm) - frame_size + 1, frame_size)
    ]
    if not frames:
        return pcm
    active = [i for i, (_, frame) in enumerate(frames) if audioop.rms(frame, 2) >= threshold]
    if not active:
        return pcm
    keep_frames = max(1, int(keep_ms / frame_ms))
    start_frame = max(0, active[0] - keep_frames)
    end_frame = min(len(frames), active[-1] + keep_frames + 1)
    start = frames[start_frame][0]
    end = frames[end_frame - 1][0] + len(frames[end_frame - 1][1])
    return pcm[start:end]


def noise_gate_pcm16(
    pcm: bytes,
    *,
    threshold: int,
    attenuation: float,
    rate: int = 16000,
    frame_ms: int = 20,
) -> bytes:
    if not pcm or attenuation >= 1.0:
        return pcm
    frame_size = _pcm16_frame_size(rate, frame_ms)
    chunks: list[bytes] = []
    for offset in range(0, len(pcm), frame_size):
        frame = pcm[offset : offset + frame_size]
        if len(frame) < 2:
            continue
        if len(frame) >= frame_size and audioop.rms(frame, 2) < threshold:
            frame = audioop.mul(frame, 2, max(0.0, attenuation))
        chunks.append(frame)
    return b"".join(chunks)


def normalize_pcm16_for_asr(pcm: bytes, args) -> bytes:
    if not pcm:
        return pcm
    active_rms = activity_rms(pcm, 2, 16000)
    if active_rms <= 0:
        return pcm
    peak = audioop.max(pcm, 2)
    target = max(1, args.asr_target_rms)
    factor = target / max(1, active_rms)
    factor = min(args.asr_max_gain, max(args.asr_min_gain, factor))
    if peak > 0:
        factor = min(factor, args.asr_peak_limit / peak)
    if abs(factor - 1.0) > 0.03:
        pcm = audioop.mul(pcm, 2, factor)
    return pcm


def pad_pcm16_min_duration(pcm: bytes, *, min_ms: int, rate: int = 16000) -> bytes:
    if min_ms <= 0:
        return pcm
    current_ms = pcm16_duration_ms(pcm, rate=rate)
    if current_ms >= min_ms:
        return pcm
    missing_samples = int((min_ms - current_ms) * rate / 1000)
    padding = b"\x00\x00" * max(0, missing_samples)
    left = padding[: len(padding) // 2 // 2 * 2]
    right = padding[len(left) :]
    return left + pcm + right


def prepare_asr_pcm16(pcm: bytes, args, *, source: str = "") -> bytes:
    """Prepare a 16 kHz mono PCM16 utterance before sending it to cloud ASR."""
    if not args.asr_preprocess or not pcm:
        return pcm
    before_ms = pcm16_duration_ms(pcm)
    before_rms = activity_rms(pcm, 2, 16000) if pcm else 0
    if len(pcm) % 2:
        pcm = pcm[:-1]
    avg = audioop.avg(pcm, 2)
    if avg:
        pcm = audioop.bias(pcm, 2, -avg)
    values = _pcm16_frame_rms(pcm, frame_ms=args.asr_frame_ms)
    threshold = _asr_activity_threshold(values, args)
    if args.asr_trim_silence:
        pcm = trim_pcm16_silence(
            pcm,
            threshold=threshold,
            frame_ms=args.asr_frame_ms,
            keep_ms=args.asr_trim_keep_ms,
        )
    if args.asr_noise_gate:
        pcm = noise_gate_pcm16(
            pcm,
            threshold=max(args.asr_trim_min_rms, int(threshold * args.asr_noise_gate_ratio)),
            attenuation=args.asr_noise_gate_attenuation,
            frame_ms=args.asr_frame_ms,
        )
    pcm = normalize_pcm16_for_asr(pcm, args)
    pcm = pad_pcm16_min_duration(pcm, min_ms=args.asr_min_audio_ms)
    if args.verbose:
        after_ms = pcm16_duration_ms(pcm)
        after_rms = activity_rms(pcm, 2, 16000) if pcm else 0
        print(
            "ASR_PREPROCESS "
            f"source={source or '-'} before_ms={before_ms} after_ms={after_ms} "
            f"before_rms={before_rms} after_rms={after_rms} threshold={threshold}",
            flush=True,
        )
    return pcm


def activity_rms(frames: bytes, width: int, rate: int, *, window_ms: int = 200) -> int:
    """Use short-window peak RMS so quick wake words do not get averaged away."""
    window_bytes = max(width, int(rate * window_ms / 1000) * width)
    if len(frames) <= window_bytes:
        return audioop.rms(frames, width)
    values = [
        audioop.rms(frames[offset : offset + window_bytes], width)
        for offset in range(0, len(frames) - window_bytes + 1, window_bytes)
    ]
    return max(values) if values else audioop.rms(frames, width)


def best_stereo_channel(frames: bytes, width: int) -> bytes:
    left = audioop.tomono(frames, width, 1, 0)
    right = audioop.tomono(frames, width, 0, 1)
    return right if audioop.rms(right, width) > audioop.rms(left, width) else left


def raw_to_pcm16(raw: bytes, *, gain: float, state) -> tuple[bytes, int, object]:
    """Convert I2S S32_LE stereo 48k raw bytes to debiased PCM16 16k mono."""
    width = 4
    frames = best_stereo_channel(raw, width)
    frames, state = audioop.ratecv(frames, width, 1, 48000, 16000, state)
    frames = audioop.lin2lin(frames, width, 2)
    if gain and gain != 1.0:
        frames = audioop.mul(frames, 2, gain)
    avg = audioop.avg(frames, 2)
    if avg:
        frames = audioop.bias(frames, 2, -avg)
    return frames, audioop.rms(frames, 2), state


def _normalize_vad_frame(pcm: bytes, frame_ms: int) -> bytes:
    expected = int(16000 * frame_ms / 1000) * 2
    if len(pcm) == expected:
        return pcm
    if len(pcm) > expected:
        return pcm[:expected]
    return pcm + (b"\x00" * (expected - len(pcm)))


def _open_webrtc_vad(args):
    if not args.vad_use_webrtc:
        return None
    try:
        import webrtcvad
    except ImportError:
        print("VAD_WARNING webrtcvad is not installed; falling back to energy VAD", flush=True)
        return None
    return webrtcvad.Vad(args.vad_mode)


class LocalWakeDetector:
    continuous = False

    def process(self, pcm16: bytes, *, force: bool = False) -> bool:
        return False

    def reset(self) -> None:
        return

    def finish(self) -> bool:
        self.reset()
        return False


class PorcupineWakeDetector(LocalWakeDetector):
    def __init__(self, args) -> None:
        import pvporcupine

        access_key = args.porcupine_access_key
        if not access_key:
            raise RuntimeError("Porcupine needs --porcupine-access-key or PICOVOICE_ACCESS_KEY")
        keyword_paths = [p for p in args.porcupine_keyword_path if p]
        if not keyword_paths:
            raise RuntimeError("Porcupine needs --porcupine-keyword-path /path/to/xiaoxing.ppn")
        self.engine = pvporcupine.create(
            access_key=access_key,
            keyword_paths=keyword_paths,
            sensitivities=[args.porcupine_sensitivity] * len(keyword_paths),
        )
        self.frame_length = self.engine.frame_length
        self.buffer = array("h")
        print(f"local_wake=porcupine frame_length={self.frame_length}", flush=True)

    def process(self, pcm16: bytes, *, force: bool = False) -> bool:
        samples = array("h")
        samples.frombytes(pcm16)
        self.buffer.extend(samples)
        detected = False
        while len(self.buffer) >= self.frame_length:
            frame = self.buffer[: self.frame_length]
            del self.buffer[: self.frame_length]
            if self.engine.process(frame) >= 0:
                detected = True
        return detected


class OpenWakeWordDetector(LocalWakeDetector):
    continuous = True

    def __init__(self, args) -> None:
        from openwakeword.model import Model

        model_paths = [p for p in args.openwakeword_model_path if p]
        if not model_paths:
            raise RuntimeError("openWakeWord needs --openwakeword-model-path /path/to/model.onnx")
        feature_dir = ROOT / "models" / "openwakeword"
        feature_kwargs = {}
        melspec_model = feature_dir / "melspectrogram.onnx"
        embedding_model = feature_dir / "embedding_model.onnx"
        if melspec_model.exists() and embedding_model.exists():
            feature_kwargs = {
                "melspec_model_path": str(melspec_model),
                "embedding_model_path": str(embedding_model),
            }
        self.model = Model(wakeword_models=model_paths, inference_framework="onnx", **feature_kwargs)
        self.threshold = args.openwakeword_threshold
        self.debug = args.wake_debug
        self._debug_count = 0
        self._debug_best = 0.0
        self.buffer = array("h")
        print(f"local_wake=openwakeword threshold={self.threshold}", flush=True)

    def process(self, pcm16: bytes, *, force: bool = False) -> bool:
        import numpy as np

        samples = array("h")
        samples.frombytes(pcm16)
        self.buffer.extend(samples)
        detected = False
        # openWakeWord expects 1280 samples (80 ms at 16 kHz) per prediction.
        while len(self.buffer) >= 1280:
            frame = self.buffer[:1280]
            del self.buffer[:1280]
            prediction = self.model.predict(np.array(frame, dtype=np.int16))
            score = max((float(v) for v in prediction.values()), default=0.0) if prediction else 0.0
            if self.debug:
                self._debug_count += 1
                self._debug_best = max(self._debug_best, score)
                if self._debug_count >= 12:
                    print(f"LOCAL_WAKE_BEST best={self._debug_best:.4f} last={score:.4f}", flush=True)
                    self._debug_count = 0
                    self._debug_best = 0.0
            if prediction and score >= self.threshold:
                print(f"LOCAL_WAKE_SCORE {prediction}", flush=True)
                detected = True
        return detected

    def reset(self) -> None:
        self.buffer = array("h")
        self._debug_count = 0
        self._debug_best = 0.0
        try:
            self.model.reset()
        except Exception:
            pass

    def finish(self) -> bool:
        self.reset()
        return False


class SherpaKeywordWakeDetector(LocalWakeDetector):
    def __init__(self, args) -> None:
        import numpy as np
        import sherpa_onnx

        self.np = np
        model_dir = Path(args.sherpa_model_dir)
        if not model_dir.is_absolute():
            model_dir = ROOT / model_dir
        keywords_file = Path(args.sherpa_keywords_file)
        if not keywords_file.is_absolute():
            keywords_file = ROOT / keywords_file

        self.min_rms = args.sherpa_min_rms
        chunk = args.sherpa_chunk
        encoder_name = f"encoder-epoch-13-avg-2-chunk-{chunk}-left-64"
        joiner_name = f"joiner-epoch-13-avg-2-chunk-{chunk}-left-64"
        if args.sherpa_int8:
            encoder_name += ".int8"
            joiner_name += ".int8"

        self.spotter = sherpa_onnx.KeywordSpotter(
            tokens=str(model_dir / "tokens.txt"),
            encoder=str(model_dir / f"{encoder_name}.onnx"),
            decoder=str(model_dir / f"decoder-epoch-13-avg-2-chunk-{chunk}-left-64.onnx"),
            joiner=str(model_dir / f"{joiner_name}.onnx"),
            keywords_file=str(keywords_file),
            num_threads=args.sherpa_num_threads,
            max_active_paths=args.sherpa_max_active_paths,
            keywords_score=args.sherpa_keywords_score,
            keywords_threshold=args.sherpa_keywords_threshold,
            num_trailing_blanks=args.sherpa_num_trailing_blanks,
            provider="cpu",
        )
        self.stream = self.spotter.create_stream()
        self.tail_padding = self.np.zeros(int(0.66 * 16000), dtype=self.np.float32)
        print(
            f"local_wake=sherpa model={model_dir.name} keywords={keywords_file} "
            f"chunk={chunk} int8={args.sherpa_int8}",
            flush=True,
        )

    def process(self, pcm16: bytes, *, force: bool = False) -> bool:
        if not force and audioop.rms(pcm16, 2) < self.min_rms:
            return False
        samples = self.np.frombuffer(pcm16, dtype=self.np.int16).astype(self.np.float32) / 32768.0
        self.stream.accept_waveform(16000, samples)
        detected = False
        while self.spotter.is_ready(self.stream):
            self.spotter.decode_stream(self.stream)
            result = self.spotter.get_result(self.stream)
            if result:
                print(f"LOCAL_WAKE_SHERPA {result}", flush=True)
                self.reset()
                detected = True
        return detected

    def reset(self) -> None:
        self.spotter.reset_stream(self.stream)
        self.stream = self.spotter.create_stream()

    def finish(self) -> bool:
        self.stream.accept_waveform(16000, self.tail_padding)
        self.stream.input_finished()
        detected = False
        while self.spotter.is_ready(self.stream):
            self.spotter.decode_stream(self.stream)
            result = self.spotter.get_result(self.stream)
            if result:
                print(f"LOCAL_WAKE_SHERPA {result}", flush=True)
                detected = True
                break
        self.stream = self.spotter.create_stream()
        return detected


def _open_local_wake_detector(args) -> LocalWakeDetector | None:
    if args.local_wake_provider == "none":
        return None
    try:
        if args.local_wake_provider == "porcupine":
            return PorcupineWakeDetector(args)
        if args.local_wake_provider == "openwakeword":
            return OpenWakeWordDetector(args)
        if args.local_wake_provider == "sherpa":
            return SherpaKeywordWakeDetector(args)
    except Exception as exc:
        print(f"LOCAL_WAKE_WARNING {exc}", flush=True)
    return None


def _capture_arecord(args, raw_frame_bytes: int):
    process = subprocess.Popen(
        [
            "arecord",
            "-q",
            "-D",
            args.input_device,
            "-f",
            "S32_LE",
            "-r",
            "48000",
            "-c",
            "2",
            "-t",
            "raw",
        ],
        stdout=subprocess.PIPE,
        bufsize=raw_frame_bytes * 4,
    )
    if not process.stdout:
        raise RuntimeError("arecord stdout is not available")
    while True:
        raw = process.stdout.read(raw_frame_bytes)
        if not raw:
            raise RuntimeError("arecord stopped")
        yield raw


def _capture_alsa(args, period_size: int):
    try:
        import alsaaudio
    except ImportError as exc:
        raise RuntimeError("pyalsaaudio is not installed") from exc

    capture = alsaaudio.PCM(
        type=alsaaudio.PCM_CAPTURE,
        mode=getattr(alsaaudio, "PCM_NONBLOCK", alsaaudio.PCM_NORMAL),
        device=args.input_device,
    )
    capture.setchannels(2)
    capture.setrate(48000)
    capture.setformat(alsaaudio.PCM_FORMAT_S32_LE)
    capture.setperiodsize(period_size)
    empty_sleep = min(0.05, max(0.005, period_size / 48000.0))
    while True:
        length, raw = capture.read()
        if length <= 0:
            time.sleep(empty_sleep)
            continue
        yield raw


def recognize(args, pcm: bytes) -> str:
    return recognize_pcm16_volc(pcm, timeout=args.asr_timeout)


def _start_stream_player(args):
    if not args.stream_tts_play:
        return None
    player = args.stream_tts_player
    if not player:
        player = "mpg123" if args.tts_provider == "volc" else "aplay"
    cmd = [player]
    if player == "mpg123":
        cmd.extend(["-q", "-o", "alsa"])
        if args.output_device:
            cmd.extend(["-a", args.output_device])
        cmd.append("-")
    elif player == "ffplay":
        cmd.extend(["-nodisp", "-autoexit", "-loglevel", "quiet", "-"])
    else:
        return None
    try:
        return subprocess.Popen(cmd, stdin=subprocess.PIPE)
    except FileNotFoundError:
        print(f"TTS_STREAM_WARNING player not found: {player}", flush=True)
        return None


def _finish_stream_player(process) -> None:
    if not process:
        return False
    try:
        if process.stdin:
            process.stdin.close()
        return process.wait(timeout=20) == 0
    except Exception:
        process.kill()
        return False


def _play_mp3_file(path: Path, args) -> None:
    wav_path = path.with_suffix(".wav")
    subprocess.run(["mpg123", "-q", "-w", str(wav_path), str(path)], check=True)
    try:
        play_file(wav_path, device=args.output_device)
    finally:
        try:
            wav_path.unlink()
        except OSError:
            pass


def play_prompt_async(group: str, *, device: str = "", requested_at: float | None = None) -> None:
    queued_at = time.monotonic() if requested_at is None else requested_at

    def _play() -> None:
        started_at = time.monotonic()
        print(f"PROMPT_START group={group} queue_ms={(started_at - queued_at) * 1000:.0f}", flush=True)
        play_prompt(group, device=device)
        print(f"PROMPT_DONE group={group} total_ms={(time.monotonic() - queued_at) * 1000:.0f}", flush=True)

    threading.Thread(target=_play, name=f"voice-prompt-{group}", daemon=True).start()


def screen_notify(args, status: str, *, role: str | None = None, text: str | None = None, display: dict | None = None) -> None:
    url = getattr(args, "screen_state_url", "") or ""
    if not url:
        return
    threading.Thread(
        target=lambda: notify_screen_state(status, role=role, text=text, display=display, url=url),
        name="screen-state-update",
        daemon=True,
    ).start()


def speak_text(args, text: str, *, stem: str = "response") -> None:
    if not args.speak_results:
        return
    message = spoken_text(text, max_chars=args.tts_max_chars)
    player = None
    try:
        out_dir = ROOT / "data" / "generated" / "voice" / "responses"
        out_dir.mkdir(parents=True, exist_ok=True)
        if args.tts_provider == "volc":
            path = out_dir / f"{stem}_{int(time.time())}.mp3"
            player = _start_stream_player(args)

            def on_chunk(audio: bytes) -> None:
                if player and player.stdin:
                    try:
                        player.stdin.write(audio)
                        player.stdin.flush()
                    except BrokenPipeError:
                        pass

            audio_path = synthesize_volc_stream(message, path, chunk_callback=on_chunk if player else None)
            stream_ok = _finish_stream_player(player) if player else False
            player = None
            if not stream_ok:
                _play_mp3_file(audio_path, args)
        else:
            path = out_dir / f"{stem}_{int(time.time())}.wav"
            audio_path = synthesize(message, path, context="你是桌面机器人小星，请用自然中文普通话播报业务查询结果。")
            play_file(audio_path, device=args.output_device)
    except Exception as exc:
        print(f"TTS_ERROR {exc}", flush=True)
        if args.tts_provider == "volc":
            try:
                path = out_dir / f"{stem}_{int(time.time())}_fallback.wav"
                audio_path = synthesize(message, path, context="你是桌面机器人小星，请用自然中文普通话播报业务查询结果。")
                play_file(audio_path, device=args.output_device)
            except Exception as fallback_exc:
                print(f"TTS_FALLBACK_ERROR {fallback_exc}", flush=True)
    finally:
        _finish_stream_player(player)


def handle_command(args, command: str) -> bool:
    command = normalize_command_text(command)
    if not command:
        print("COMMAND_EMPTY_IGNORED", flush=True)
        return False
    if is_wake_text(command):
        print(f"COMMAND_WAKE_IGNORED {command}", flush=True)
        return False
    if is_cancel_voice_command(command):
        print(f"COMMAND_CANCELLED {command}", flush=True)
        screen_notify(args, "idle")
        return True
    if is_ignorable_voice_command(command):
        print(f"COMMAND_IGNORED {command}", flush=True)
        return False
    if is_local_robot_command(command):
        print(f"COMMAND_LOCAL {command}", flush=True)
        screen_notify(args, "listen", role="user", text=command)
        local_reply = handle_local_robot_command(command, output_device=args.output_device) or "已处理。"
        screen_notify(args, "talk", role="assistant", text=local_reply)
        return True
    if is_unclear_voice_command(command):
        print(f"COMMAND_UNCLEAR {command}", flush=True)
        screen_notify(args, "error", role="assistant", text="没听清，再说一遍。")
        play_prompt("failed", device=args.output_device)
        return False
    print(f"COMMAND {command}", flush=True)
    screen_notify(args, "listen", role="user", text=command)
    screen_notify(args, "processing")
    if args.processing_prompt:
        play_prompt_async("processing", device=args.output_device)
    if getattr(args, "device_command_url", ""):
        try:
            device_result = post_device_command(args, command)
            print(f"DEVICE_COMMAND {json.dumps(device_result, ensure_ascii=False)}", flush=True)
        except Exception as exc:
            print(f"DEVICE_COMMAND_ERROR {exc}", flush=True)
            result = "服务器没连上，稍后再试。"
            screen_notify(args, "error", role="assistant", text=result)
            speak_text(args, result)
            return True
        speak = str(device_result.get("speak") or "处理完成。")
        display = device_result.get("display") if isinstance(device_result.get("display"), dict) else {}
        action = device_result.get("device_action") if isinstance(device_result.get("device_action"), dict) else {}
        screen_text = display.get("summary") or display.get("title") or speak
        screen_notify(args, "talk", role="assistant", text=str(screen_text or ""), display=display)
        speak_text(args, speak)
        return not bool(action.get("listen_again"))
    try:
        result = run_agent_command(command, session_id=args.agent_session_id)
    except Exception as exc:
        result = f"处理异常：{exc}"
    print(f"AGENT {result}", flush=True)
    if is_uncertain_agent_result(result):
        screen_notify(args, "error", role="assistant", text="没听清，再说一遍。")
        play_prompt("failed", device=args.output_device)
        return False
    screen_notify(args, "talk", role="assistant", text=spoken_text(str(result or ""), max_chars=args.tts_max_chars))
    speak_text(args, result)
    return True


def should_continue_command_window(command: str) -> bool:
    command = normalize_command_text(command)
    if not command:
        return False
    if is_wake_text(command):
        return False
    if is_cancel_voice_command(command):
        return False
    if is_ignorable_voice_command(command):
        return False
    return True


def command_window_deadline(args, *, after_wake_reply: bool = False) -> float:
    extra = args.wake_reply_ignore_seconds if after_wake_reply else 0.0
    return time.monotonic() + max(0.0, extra) + args.command_window_seconds


def run_once(args) -> bool:
    with tempfile.TemporaryDirectory(prefix="sjagent-wake-") as tmp:
        wav_path = Path(tmp) / "chunk.wav"
        record_wav(wav_path, device=args.input_device, seconds=args.chunk_seconds)
        pcm, rms = wav_to_pcm16(wav_path, gain=args.gain)
    if args.verbose:
        print(f"rms={rms}")
    if rms < args.rms_threshold:
        return False

    try:
        pcm = prepare_asr_pcm16(pcm, args, source="chunk")
        text = recognize(args, pcm)
    except Exception as exc:
        print(f"ASR_ERROR {exc}", flush=True)
        return False

    print(f"ASR {text}", flush=True)
    if is_wake_text(text):
        screen_notify(args, "listen", role="assistant", text="我在听。")
        play_prompt("wake", device=args.output_device)
        return True
    return False


def _vad_threshold(noise_floor: float, args) -> float:
    return max(args.vad_min_rms, noise_floor * args.vad_start_ratio + args.vad_start_margin)


def run_stream(args) -> None:
    frame_seconds = args.vad_frame_ms / 1000
    period_size = int(48000 * frame_seconds)
    raw_frame_bytes = period_size * 2 * 4
    if args.capture_backend == "alsa":
        raw_frames = _capture_alsa(args, period_size)
    else:
        raw_frames = _capture_arecord(args, raw_frame_bytes)
    vad = _open_webrtc_vad(args)
    local_wake = _open_local_wake_detector(args)

    print(f"wake listener stream started backend={args.capture_backend}", flush=True)
    state = None
    noise_floor = 0.0
    speaking = False
    speech_frames: list[bytes] = []
    pre_roll: list[bytes] = []
    silence_frames = 0
    speech_frames_count = 0
    active_streak = 0
    max_pre_roll = max(1, int(args.vad_pre_roll_ms / args.vad_frame_ms))
    end_silence_frames = max(1, int(args.vad_end_silence_ms / args.vad_frame_ms))
    max_speech_frames = max(1, int(args.vad_max_seconds / frame_seconds))
    min_speech_frames = max(1, int(args.vad_min_speech_ms / args.vad_frame_ms))
    start_speech_frames = max(1, args.vad_start_frames)
    local_wake_reset_frames = max(1, int(350 / args.vad_frame_ms))
    local_wake_max_frames = max(1, int(2500 / args.vad_frame_ms))
    local_wake_segment_active = False
    local_wake_segment_frames = 0
    local_wake_segment_peak = 0
    local_wake_inactive_frames = 0
    calibration_frames = max(1, int(args.vad_calibration_ms / args.vad_frame_ms))
    calibration: list[int] = []
    waiting_command_until = 0.0
    ignore_audio_until = 0.0
    streaming_asr: VolcStreamingRecognizer | None = None
    expecting_command_utterance = False

    while True:
        if waiting_command_until and not speaking and time.monotonic() > waiting_command_until:
            waiting_command_until = 0.0
            if args.verbose:
                print("command_window=timeout", flush=True)
        raw = next(raw_frames)
        pcm, rms, state = raw_to_pcm16(raw, gain=args.gain, state=state)
        if ignore_audio_until and time.monotonic() < ignore_audio_until:
            continue
        ignore_audio_until = 0.0
        if calibration_frames:
            calibration.append(rms)
            calibration_frames -= 1
            if not calibration_frames:
                values = sorted(calibration)
                noise_floor = values[len(values) // 2]
                if args.verbose:
                    print(f"calibrated_noise={int(noise_floor)}", flush=True)
            continue
        if not noise_floor:
            noise_floor = rms
        if not speaking:
            noise_floor = noise_floor * 0.94 + rms * 0.06

        threshold = _vad_threshold(noise_floor, args)
        energy_active = rms >= threshold
        vad_active = False
        if vad:
            vad_frame = _normalize_vad_frame(pcm, args.vad_frame_ms)
            vad_active = vad.is_speech(vad_frame, 16000) and rms >= args.vad_min_rms
        active = vad_active if vad else energy_active
        if args.verbose:
            print(
                f"rms={rms} noise={int(noise_floor)} threshold={int(threshold)} "
                f"vad={int(vad_active)} active={int(active)}",
                flush=True,
            )

        if local_wake and getattr(local_wake, "continuous", False) and not waiting_command_until:
            if local_wake.process(pcm, force=True):
                print("LOCAL_WAKE detected", flush=True)
                local_wake.reset()
                if args.wake_only:
                    screen_notify(args, "listen", role="assistant", text="listening")
                    if not args.no_wake_prompt:
                        play_prompt_async("wake", device=args.output_device)
                    ignore_audio_until = time.monotonic() + max(args.wake_reply_ignore_seconds, args.cooldown)
                    time.sleep(args.cooldown)
                    continue
                waiting_command_until = command_window_deadline(args, after_wake_reply=True)
                print("command_window=opened", flush=True)
                screen_notify(args, "listen", role="assistant", text="listening")
                if not args.no_wake_prompt:
                    play_prompt_async("wake", device=args.output_device)
                ignore_audio_until = time.monotonic() + args.wake_reply_ignore_seconds
                pre_roll.clear()
                speaking = False
                speech_frames = []
                silence_frames = 0
                speech_frames_count = 0
                active_streak = 0
                expecting_command_utterance = False
                continue

        if local_wake and not waiting_command_until and not getattr(local_wake, "continuous", False):
            if active:
                if not local_wake_segment_active and args.wake_debug:
                    print(
                        f"WAKE_SEGMENT start rms={rms} noise={int(noise_floor)} "
                        f"threshold={int(threshold)}",
                        flush=True,
                    )
                local_wake_segment_active = True
                local_wake_segment_frames = 0 if not local_wake_segment_frames else local_wake_segment_frames
                local_wake_segment_peak = max(local_wake_segment_peak, rms)
                local_wake_inactive_frames = 0
            else:
                local_wake_inactive_frames += 1
                if local_wake_inactive_frames >= local_wake_reset_frames and not local_wake_segment_active:
                    local_wake.reset()
                    local_wake_inactive_frames = 0
            if local_wake_segment_active:
                local_wake_segment_frames += 1
                if local_wake.process(pcm, force=True):
                    print("LOCAL_WAKE detected", flush=True)
                    local_wake_segment_active = False
                    local_wake_segment_frames = 0
                    local_wake_segment_peak = 0
                    local_wake_inactive_frames = 0
                    local_wake.reset()
                    if args.wake_only:
                        screen_notify(args, "listen", role="assistant", text="我在听。")
                        if not args.no_wake_prompt:
                            play_prompt_async("wake", device=args.output_device)
                        ignore_audio_until = time.monotonic() + max(args.wake_reply_ignore_seconds, args.cooldown)
                        time.sleep(args.cooldown)
                        continue
                    waiting_command_until = command_window_deadline(args, after_wake_reply=True)
                    print("command_window=opened", flush=True)
                    screen_notify(args, "listen", role="assistant", text="我在听。")
                    if not args.no_wake_prompt:
                        play_prompt_async("wake", device=args.output_device)
                    ignore_audio_until = time.monotonic() + args.wake_reply_ignore_seconds
                    pre_roll.clear()
                    speaking = False
                    speech_frames = []
                    silence_frames = 0
                    speech_frames_count = 0
                    active_streak = 0
                    expecting_command_utterance = False
                    continue
                if (
                    local_wake_inactive_frames >= local_wake_reset_frames
                    or local_wake_segment_frames >= local_wake_max_frames
                ):
                    detected_on_finish = local_wake.finish()
                    if detected_on_finish:
                        print("LOCAL_WAKE detected", flush=True)
                        local_wake_segment_active = False
                        local_wake_segment_frames = 0
                        local_wake_segment_peak = 0
                        local_wake_inactive_frames = 0
                        local_wake.reset()
                        if args.wake_only:
                            screen_notify(args, "listen", role="assistant", text="我在听。")
                            if not args.no_wake_prompt:
                                play_prompt_async("wake", device=args.output_device)
                            ignore_audio_until = time.monotonic() + max(args.wake_reply_ignore_seconds, args.cooldown)
                            time.sleep(args.cooldown)
                            continue
                        waiting_command_until = command_window_deadline(args, after_wake_reply=True)
                        print("command_window=opened", flush=True)
                        screen_notify(args, "listen", role="assistant", text="我在听。")
                        if not args.no_wake_prompt:
                            play_prompt_async("wake", device=args.output_device)
                        ignore_audio_until = time.monotonic() + args.wake_reply_ignore_seconds
                        pre_roll.clear()
                        speaking = False
                        speech_frames = []
                        silence_frames = 0
                        speech_frames_count = 0
                        active_streak = 0
                        expecting_command_utterance = False
                        continue
                    if args.wake_debug:
                        print(
                            f"WAKE_SEGMENT end frames={local_wake_segment_frames} "
                            f"peak={local_wake_segment_peak} detected=0",
                            flush=True,
                        )
                    local_wake_segment_active = False
                    local_wake_segment_frames = 0
                    local_wake_segment_peak = 0
                    local_wake_inactive_frames = 0

        if not speaking:
            pre_roll.append(pcm)
            if len(pre_roll) > max_pre_roll:
                pre_roll.pop(0)
            if active:
                active_streak += 1
            else:
                active_streak = 0
            if active_streak >= start_speech_frames:
                speaking = True
                speech_frames = list(pre_roll)
                expecting_command_utterance = bool(waiting_command_until)
                if (
                    expecting_command_utterance
                    and args.asr_provider == "volc"
                    and args.stream_command_asr
                    and not args.asr_preprocess
                ):
                    streaming_asr = VolcStreamingRecognizer(timeout=args.asr_timeout)
                    for frame in speech_frames:
                        streaming_asr.feed(frame)
                pre_roll.clear()
                silence_frames = 0
                speech_frames_count = active_streak
                active_streak = 0
            continue

        speech_frames.append(pcm)
        if streaming_asr is not None:
            streaming_asr.feed(pcm)
        speech_frames_count += 1
        if active:
            silence_frames = 0
        else:
            silence_frames += 1

        should_end = silence_frames >= end_silence_frames or speech_frames_count >= max_speech_frames
        if not should_end:
            continue

        speaking = False
        if speech_frames_count < min_speech_frames:
            speech_frames = []
            expecting_command_utterance = False
            continue

        utterance = b"".join(speech_frames)
        speech_frames = []
        if local_wake and not waiting_command_until:
            # Pure local wake mode: do not spend cloud ASR calls before the
            # local wake engine opens the command window.
            streaming_asr = None
            expecting_command_utterance = False
            continue
        try:
            if streaming_asr is not None:
                text = streaming_asr.finish()
                streaming_asr = None
            else:
                utterance = prepare_asr_pcm16(utterance, args, source="stream")
                text = recognize(args, utterance)
        except Exception as exc:
            streaming_asr = None
            print(f"ASR_ERROR {exc}", flush=True)
            continue

        print(f"ASR {text}", flush=True)
        if waiting_command_until or expecting_command_utterance:
            expecting_command_utterance = False
            if handle_command(args, text):
                waiting_command_until = 0.0
            elif not should_continue_command_window(text):
                print("command_window=kept", flush=True)
            else:
                waiting_command_until = command_window_deadline(args)
                print("command_window=continued", flush=True)
            continue

        woke = is_wake_text(text)
        command_tail = strip_wake_words(text) if woke else ""
        if woke:
            learn_wake_variants(text)
            if command_tail:
                screen_notify(args, "listen", role="assistant", text="我在听。")
                if not args.no_wake_prompt:
                    play_prompt_async("wake", device=args.output_device)
                ignore_audio_until = time.monotonic() + args.wake_reply_ignore_seconds
                handle_command(args, command_tail)
            elif args.assistant_mode:
                waiting_command_until = command_window_deadline(args, after_wake_reply=True)
                print("command_window=opened", flush=True)
                screen_notify(args, "listen", role="assistant", text="我在听。")
                if not args.no_wake_prompt:
                    play_prompt_async("wake", device=args.output_device)
                ignore_audio_until = time.monotonic() + args.wake_reply_ignore_seconds
            if not waiting_command_until:
                time.sleep(args.cooldown)


def main() -> None:
    load_dotenv(dotenv_path=ROOT / ".env")
    parser = argparse.ArgumentParser(description="Listen for 小星 and play a wake reply")
    parser.add_argument("--input-device", default="hw:CARD=ahubi2s3,DEV=0")
    parser.add_argument("--output-device", default="")
    parser.add_argument("--chunk-seconds", type=float, default=2.2)
    parser.add_argument("--cooldown", type=float, default=2.5)
    parser.add_argument("--rms-threshold", type=int, default=120)
    parser.add_argument("--gain", type=float, default=8.0, help="PCM gain before ASR")
    parser.add_argument("--asr-provider", choices=["volc"], default="volc")
    parser.add_argument("--asr-timeout", type=int, default=15)
    parser.add_argument("--stream-command-asr", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--asr-preprocess", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--asr-frame-ms", type=int, default=20, choices=[10, 20, 30])
    parser.add_argument("--asr-trim-silence", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--asr-trim-keep-ms", type=int, default=120)
    parser.add_argument("--asr-trim-min-rms", type=int, default=120)
    parser.add_argument("--asr-noise-ratio", type=float, default=1.8)
    parser.add_argument("--asr-noise-margin", type=int, default=90)
    parser.add_argument("--asr-noise-gate", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--asr-noise-gate-ratio", type=float, default=0.85)
    parser.add_argument("--asr-noise-gate-attenuation", type=float, default=0.18)
    parser.add_argument("--asr-target-rms", type=int, default=2800)
    parser.add_argument("--asr-min-gain", type=float, default=0.45)
    parser.add_argument("--asr-max-gain", type=float, default=3.0)
    parser.add_argument("--asr-peak-limit", type=int, default=26000)
    parser.add_argument("--asr-min-audio-ms", type=int, default=1000)
    parser.add_argument("--once", action="store_true", help="Record and process one chunk")
    parser.add_argument("--stream-vad", action="store_true", help="Use continuous local VAD before ASR")
    parser.add_argument("--assistant-mode", action="store_true", help="After wake word, listen for one command")
    parser.add_argument("--wake-only", action="store_true", help="Only test local wake; do not open command ASR window")
    parser.add_argument("--wake-debug", action="store_true", help="Print compact local wake segment debug logs")
    parser.add_argument("--no-wake-prompt", action="store_true", help="Do not play a wake prompt after local wake")
    parser.add_argument("--command-window-seconds", type=float, default=8.0)
    parser.add_argument("--wake-reply-ignore-seconds", type=float, default=0.8)
    parser.add_argument("--agent-session-id", default="orangepi_voice")
    parser.add_argument("--device-id", default=os.getenv("SJ_DEVICE_ID", "orangepi-xiaoxing-01"))
    parser.add_argument("--device-command-url", default=os.getenv("SJ_DEVICE_COMMAND_URL", ""))
    parser.add_argument("--device-command-timeout", type=int, default=int(os.getenv("SJ_DEVICE_COMMAND_TIMEOUT", "8") or 8))
    parser.add_argument("--speak-results", action="store_true")
    parser.add_argument("--processing-prompt", action="store_true")
    parser.add_argument("--tts-provider", choices=["mimo", "volc"], default="mimo")
    parser.add_argument("--tts-max-chars", type=int, default=180)
    parser.add_argument("--stream-tts-play", action="store_true")
    parser.add_argument("--stream-tts-player", default="mpg123")
    parser.add_argument("--screen-state-url", default=os.getenv("SJ_SCREEN_STATE_URL", "http://127.0.0.1:8080/api/screen/state"))
    parser.add_argument("--capture-backend", choices=["alsa", "arecord"], default="arecord")
    parser.add_argument("--local-wake-provider", choices=["none", "porcupine", "openwakeword", "sherpa"], default="none")
    parser.add_argument("--porcupine-access-key", default=os.getenv("PICOVOICE_ACCESS_KEY", ""))
    parser.add_argument("--porcupine-keyword-path", action="append", default=[])
    parser.add_argument("--porcupine-sensitivity", type=float, default=0.65)
    parser.add_argument("--openwakeword-model-path", action="append", default=[])
    parser.add_argument("--openwakeword-threshold", type=float, default=0.55)
    parser.add_argument(
        "--sherpa-model-dir",
        default="models/sherpa-onnx-kws-zipformer-zh-en-3M-2025-12-20",
    )
    parser.add_argument("--sherpa-keywords-file", default="models/xiaoxing_keywords.txt")
    parser.add_argument("--sherpa-chunk", type=int, default=8, choices=[8, 16])
    parser.add_argument("--sherpa-int8", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--sherpa-num-threads", type=int, default=1)
    parser.add_argument("--sherpa-max-active-paths", type=int, default=8)
    parser.add_argument("--sherpa-keywords-score", type=float, default=3.5)
    parser.add_argument("--sherpa-keywords-threshold", type=float, default=0.15)
    parser.add_argument("--sherpa-num-trailing-blanks", type=int, default=1)
    parser.add_argument("--sherpa-min-rms", type=int, default=60)
    parser.add_argument("--vad-frame-ms", type=int, default=20, choices=[10, 20, 30])
    parser.add_argument("--vad-use-webrtc", action="store_true")
    parser.add_argument("--vad-mode", type=int, default=2, choices=[0, 1, 2, 3])
    parser.add_argument("--vad-pre-roll-ms", type=int, default=300)
    parser.add_argument("--vad-start-frames", type=int, default=3)
    parser.add_argument("--vad-min-speech-ms", type=int, default=350)
    parser.add_argument("--vad-end-silence-ms", type=int, default=600)
    parser.add_argument("--vad-max-seconds", type=float, default=4.0)
    parser.add_argument("--vad-calibration-ms", type=int, default=1000)
    parser.add_argument("--vad-start-ratio", type=float, default=1.04)
    parser.add_argument("--vad-start-margin", type=int, default=350)
    parser.add_argument("--vad-min-rms", type=int, default=9500)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    ensure_group("wake")
    if args.once:
        raise SystemExit(0 if run_once(args) else 1)
    if args.stream_vad:
        run_stream(args)
        return

    print("wake listener started", flush=True)
    while True:
        woke = run_once(args)
        if woke:
            time.sleep(args.cooldown)


if __name__ == "__main__":
    main()
