"""Small local-only features for the Orange Pi desktop robot."""

from __future__ import annotations

import math
import os
import shlex
import signal
import subprocess
import wave
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MUSIC_DIR = ROOT / "data" / "generated" / "voice" / "music"
MUSIC_PATH = MUSIC_DIR / "light_loop.wav"
PID_PATH = MUSIC_DIR / "music.pid"


def _normalized(text: str) -> str:
    return "".join(ch for ch in (text or "").strip() if not ch.isspace())


def is_local_robot_command(text: str) -> bool:
    value = _normalized(text)
    if not value:
        return False
    if "音乐" not in value:
        return False
    return any(word in value for word in ("放", "播放", "来点", "听", "停", "暂停", "停止", "关掉", "关闭", "不要"))


def _is_music_playing() -> bool:
    try:
        pid = int(PID_PATH.read_text(encoding="utf-8").strip())
    except Exception:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        try:
            PID_PATH.unlink()
        except FileNotFoundError:
            pass
        return False


def ensure_light_music() -> Path:
    if MUSIC_PATH.exists() and MUSIC_PATH.stat().st_size > 0:
        return MUSIC_PATH

    MUSIC_DIR.mkdir(parents=True, exist_ok=True)
    sample_rate = 24000
    seconds = 12
    notes = [261.63, 329.63, 392.0, 523.25, 392.0, 329.63, 293.66, 349.23]
    frames = bytearray()
    for i in range(sample_rate * seconds):
        t = i / sample_rate
        beat = int(t / 1.5) % len(notes)
        local = t % 1.5
        env = min(1.0, local / 0.08) * max(0.0, min(1.0, (1.5 - local) / 0.35))
        freq = notes[beat]
        value = (
            0.36 * math.sin(2 * math.pi * freq * t)
            + 0.18 * math.sin(2 * math.pi * (freq * 1.5) * t)
            + 0.10 * math.sin(2 * math.pi * (freq * 2.0) * t)
        )
        sample = int(max(-1.0, min(1.0, value * env)) * 12000)
        frames.extend(sample.to_bytes(2, "little", signed=True))

    with wave.open(str(MUSIC_PATH), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(bytes(frames))
    return MUSIC_PATH


def start_music(*, device: str = "") -> str:
    if os.name != "posix":
        return "这台设备暂时不支持本地播放。"
    if _is_music_playing():
        return "音乐已经在播放。"

    path = ensure_light_music()
    args = ["aplay", "-q"]
    if device:
        args.extend(["-D", device])
    args.append(str(path))
    quoted = " ".join(shlex.quote(part) for part in args)
    proc = subprocess.Popen(
        ["bash", "-lc", f"while true; do {quoted} || exit $?; done"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    PID_PATH.write_text(str(proc.pid), encoding="utf-8")
    return "开始放音乐。"


def stop_music() -> str:
    if not _is_music_playing():
        return "音乐没有在播放。"
    pid = int(PID_PATH.read_text(encoding="utf-8").strip())
    try:
        os.killpg(pid, signal.SIGTERM)
    except OSError:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
    try:
        PID_PATH.unlink()
    except FileNotFoundError:
        pass
    return "音乐已停止。"


def handle_local_robot_command(text: str, *, output_device: str = "") -> str | None:
    value = _normalized(text)
    if not is_local_robot_command(value):
        return None
    if any(word in value for word in ("停", "暂停", "停止", "关掉", "关闭", "不要")):
        return stop_music()
    return start_music(device=output_device)
