"""Cached voice prompts for the Orange Pi desktop robot."""
from __future__ import annotations

import os
import shutil
import subprocess
import threading
import time
import wave
from dataclasses import dataclass
from pathlib import Path

from src.core.config import get_config
from src.services.mimo_tts import synthesize as synthesize_mimo
from src.services.volc_tts import synthesize_stream as synthesize_volc_stream
from src.utils import get_logger

logger = get_logger("sjagent.services.voice_prompts")
_PLAY_LOCK = threading.Lock()
_PROMPT_CYCLE_LOCK = threading.Lock()
_PROMPT_CYCLE_INDEX: dict[str, int] = {}
_PROMPT_PATH_CACHE: dict[str, Path] = {}
_SILENCE_TAIL_MS = 220
_TARGET_PROMPT_RMS = 2200
_PROMPT_PEAK_LIMIT = 26000


@dataclass(frozen=True)
class VoicePrompt:
    key: str
    text: str
    context: str = "你是桌面机器人小星，请用自然中文普通话回复。"


PROMPT_GROUPS: dict[str, list[VoicePrompt]] = {
    "wake": [
        VoicePrompt("wake_wozai", "我在", "用户刚刚喊了小星。"),
        VoicePrompt("wake_zaine", "在呢", "用户刚刚喊了小星。"),
        VoicePrompt("wake_xiaoxing", "小星在", "用户刚刚喊了小星。"),
    ],
    "processing": [
        VoicePrompt("processing_favorite", "收到啦，正在给你处理。", "用户给小星发送了一条中文语音指令。"),
        VoicePrompt("processing_ok", "好的，我来处理。", "用户给小星发送了一条中文语音指令。"),
    ],
    "slow_8s": [
        VoicePrompt("slow_8s_chazhao", "还在查，稍等一下。", "小星正在处理查询任务，时间稍微有点久。"),
        VoicePrompt("slow_8s_chuli", "我还在处理，稍等。", "小星正在处理查询任务，时间稍微有点久。"),
    ],
    "slow_25s": [
        VoicePrompt("slow_25s_jixu", "这个稍微慢一点，我继续看。", "小星正在等待业务系统返回结果。"),
        VoicePrompt("slow_25s_xitong", "系统响应有点慢，我继续处理。", "小星正在等待业务系统返回结果。"),
    ],
    "failed": [
        VoicePrompt("failed_retry", "刚才没处理成功，你再说一遍。", "小星处理语音指令失败，需要用户重试。"),
        VoicePrompt("failed_again", "这个我没处理好，再试一次。", "小星处理语音指令失败，需要用户重试。"),
    ],
}


def voice_output_dir() -> Path:
    cfg = get_config().tts_config
    return Path(cfg.get("output_dir") or "./data/generated/voice") / "prompts"


def prompt_path(prompt: VoicePrompt) -> Path:
    return voice_output_dir() / f"{prompt.key}.wav"


def get_prompts(group: str) -> list[VoicePrompt]:
    prompts = PROMPT_GROUPS.get(group)
    if not prompts:
        raise KeyError(f"Unknown voice prompt group: {group}")
    return prompts


def reset_prompt_cycle(group: str | None = None) -> None:
    with _PROMPT_CYCLE_LOCK:
        if group is None:
            _PROMPT_CYCLE_INDEX.clear()
        else:
            _PROMPT_CYCLE_INDEX[group] = 0


def pick_prompt(group: str) -> VoicePrompt:
    prompts = get_prompts(group)
    with _PROMPT_CYCLE_LOCK:
        index = _PROMPT_CYCLE_INDEX.get(group, 0)
        prompt = prompts[index % len(prompts)]
        _PROMPT_CYCLE_INDEX[group] = index + 1
        return prompt


def _prompt_target_rms() -> int:
    raw = os.getenv("VOICE_PROMPT_TARGET_RMS", "").strip()
    if raw:
        try:
            return max(0, int(raw))
        except ValueError:
            logger.warning(f"Invalid VOICE_PROMPT_TARGET_RMS: {raw}")
    return _TARGET_PROMPT_RMS


def _pcm16_rms_and_peak(frames: bytes) -> tuple[int, int]:
    if len(frames) < 2:
        return 0, 0
    count = len(frames) // 2
    total = 0
    peak = 0
    for index in range(0, count * 2, 2):
        sample = int.from_bytes(frames[index:index + 2], "little", signed=True)
        total += sample * sample
        peak = max(peak, abs(sample))
    return int((total / count) ** 0.5), peak


def _scale_pcm16(frames: bytes, gain: float) -> bytes:
    output = bytearray(len(frames))
    usable = (len(frames) // 2) * 2
    for index in range(0, usable, 2):
        sample = int.from_bytes(frames[index:index + 2], "little", signed=True)
        scaled = max(-32768, min(32767, int(round(sample * gain))))
        output[index:index + 2] = scaled.to_bytes(2, "little", signed=True)
    if usable < len(frames):
        output[usable:] = frames[usable:]
    return bytes(output)


def normalize_prompt_wav(
    path: str | Path,
    *,
    target_rms: int | None = None,
    peak_limit: int = _PROMPT_PEAK_LIMIT,
) -> Path:
    """Normalize cached PCM16 wav prompts so fixed replies have similar loudness."""
    wav_path = Path(path)
    target = _prompt_target_rms() if target_rms is None else target_rms
    if target <= 0 or not wav_path.exists() or wav_path.suffix.lower() != ".wav":
        return wav_path
    try:
        with wave.open(str(wav_path), "rb") as source:
            params = source.getparams()
            frames = source.readframes(source.getnframes())
    except Exception as exc:
        logger.warning(f"Skip prompt normalization for {wav_path}: {exc}")
        return wav_path
    if params.sampwidth != 2 or not frames:
        return wav_path
    rms, peak = _pcm16_rms_and_peak(frames)
    if rms <= 0 or peak <= 0:
        return wav_path
    gain = min(target / rms, peak_limit / peak)
    if abs(gain - 1.0) < 0.03:
        return wav_path
    normalized = _scale_pcm16(frames, gain)
    temp_path = wav_path.with_suffix(f"{wav_path.suffix}.normalizing")
    with wave.open(str(temp_path), "wb") as target_file:
        target_file.setparams(params)
        target_file.writeframes(normalized)
    os.replace(temp_path, wav_path)
    next_rms, next_peak = _pcm16_rms_and_peak(normalized)
    logger.info(
        f"Normalized voice prompt: path={wav_path.name}, rms={rms}->{next_rms}, peak={peak}->{next_peak}"
    )
    return wav_path


def _prompt_provider() -> str:
    cfg = get_config().tts_config
    return (os.getenv("VOICE_PROMPT_TTS_PROVIDER") or cfg.get("provider") or "mimo").strip().lower()


def _synthesize_with_volc(text: str, path: Path) -> Path:
    audio_format = (
        os.getenv("VOLC_TTS_FORMAT") or get_config().get_with_env("volc_tts.format", "mp3") or "mp3"
    ).strip().lower()
    temp_audio = path.with_suffix(f".prompt.{audio_format}")
    try:
        audio_path = synthesize_volc_stream(text, temp_audio)
        if audio_format == "wav":
            shutil.move(str(audio_path), str(path))
        else:
            subprocess.run(["mpg123", "-q", "-w", str(path), str(audio_path)], check=True)
        return path
    finally:
        if temp_audio.exists():
            try:
                temp_audio.unlink()
            except OSError:
                pass


def ensure_prompt(prompt: VoicePrompt, *, force: bool = False) -> Path:
    path = prompt_path(prompt)
    cached = _PROMPT_PATH_CACHE.get(prompt.key)
    if cached and cached.exists() and not force:
        return cached
    if path.exists() and path.stat().st_size > 0 and not force:
        path = normalize_prompt_wav(path)
        _PROMPT_PATH_CACHE[prompt.key] = path
        return path
    if _prompt_provider() == "volc":
        path = normalize_prompt_wav(_synthesize_with_volc(prompt.text, path))
    else:
        path = normalize_prompt_wav(synthesize_mimo(prompt.text, path, context=prompt.context))
    _PROMPT_PATH_CACHE[prompt.key] = path
    return path


def ensure_group(group: str, *, force: bool = False) -> list[Path]:
    return [ensure_prompt(prompt, force=force) for prompt in get_prompts(group)]


def ensure_all_prompts(*, force: bool = False) -> list[Path]:
    paths: list[Path] = []
    for group in PROMPT_GROUPS:
        paths.extend(ensure_group(group, force=force))
    return paths


def _silence_tail_for_wav(path: Path, *, milliseconds: int = _SILENCE_TAIL_MS) -> Path | None:
    try:
        with wave.open(str(path), "rb") as source:
            channels = source.getnchannels()
            sample_width = source.getsampwidth()
            frame_rate = source.getframerate()
    except Exception:
        return None
    if channels <= 0 or sample_width <= 0 or frame_rate <= 0:
        return None
    frames = max(1, int(frame_rate * milliseconds / 1000))
    tail_dir = voice_output_dir() / ".tails"
    tail_dir.mkdir(parents=True, exist_ok=True)
    tail_path = tail_dir / f"silence_{frame_rate}_{channels}_{sample_width}_{milliseconds}.wav"
    if tail_path.exists() and tail_path.stat().st_size > 0:
        return tail_path
    with wave.open(str(tail_path), "wb") as target:
        target.setnchannels(channels)
        target.setsampwidth(sample_width)
        target.setframerate(frame_rate)
        target.writeframes(b"\x00" * frames * channels * sample_width)
    return tail_path


def _play_wav_with_alsa(path: Path, *, device: str = "") -> bool:
    try:
        import alsaaudio
    except ImportError:
        return False
    try:
        with wave.open(str(path), "rb") as source:
            channels = source.getnchannels()
            sample_width = source.getsampwidth()
            frame_rate = source.getframerate()
            frames = source.readframes(source.getnframes())
    except Exception as exc:
        logger.debug(f"Fast ALSA prompt playback skipped for {path}: {exc}")
        return False
    if channels <= 0 or sample_width != 2 or frame_rate <= 0:
        return False
    tail_frames = max(1, int(frame_rate * _SILENCE_TAIL_MS / 1000))
    frames += b"\x00" * tail_frames * channels * sample_width
    try:
        output = alsaaudio.PCM(
            type=alsaaudio.PCM_PLAYBACK,
            mode=alsaaudio.PCM_NORMAL,
            device=device or "default",
        )
        output.setchannels(channels)
        output.setrate(frame_rate)
        output.setformat(alsaaudio.PCM_FORMAT_S16_LE)
        period_frames = max(256, min(2048, frame_rate // 50))
        output.setperiodsize(period_frames)
        chunk_size = period_frames * channels * sample_width
        for offset in range(0, len(frames), chunk_size):
            chunk = frames[offset : offset + chunk_size]
            if chunk:
                output.write(chunk)
        return True
    except Exception as exc:
        logger.warning(f"Fast ALSA prompt playback failed for {path}: {exc}")
        return False


def play_file(path: str | Path, *, device: str = "") -> None:
    audio_path = Path(path)
    with _PLAY_LOCK:
        if audio_path.suffix.lower() == ".wav" and _play_wav_with_alsa(audio_path, device=device):
            return
        args = ["aplay", "-q"]
        if device:
            args.extend(["-D", device])
        args.append(str(audio_path))
        if audio_path.suffix.lower() == ".wav":
            tail_path = _silence_tail_for_wav(audio_path)
            if tail_path:
                args.append(str(tail_path))
        last_exc: subprocess.CalledProcessError | None = None
        for attempt in range(3):
            try:
                subprocess.run(args, check=True)
                return
            except subprocess.CalledProcessError as exc:
                last_exc = exc
                time.sleep(0.25 * (attempt + 1))
        if last_exc:
            raise last_exc


def play_prompt(group: str, *, device: str = "", force: bool = False) -> Path:
    prompt = pick_prompt(group)
    path = ensure_prompt(prompt, force=force)
    logger.info(f"Play voice prompt: group={group}, key={prompt.key}, text={prompt.text}")
    play_file(path, device=device)
    return path


def should_play_processing(elapsed_seconds: float, expected_slow: bool = False) -> bool:
    """Avoid colliding with fast result speech.

    The voice loop should call this after command execution has been running for
    a moment. Fast results can be spoken directly without an extra processing
    prompt.
    """
    return expected_slow or elapsed_seconds >= 3.0
