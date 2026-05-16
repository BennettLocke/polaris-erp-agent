"""Simple wake-word listener for the Orange Pi desktop robot.

First version: record short chunks from INMP441, send speech-like chunks to
Aliyun short ASR, and play a cached wake prompt when the transcript resembles
"小星".
"""
from __future__ import annotations

import argparse
import audioop
import re
import subprocess
import sys
import tempfile
import time
import wave
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.services.aliyun_short_asr import recognize_pcm16  # noqa: E402
from src.services.voice_prompts import ensure_group, play_prompt  # noqa: E402


WAKE_WORDS = {
    "小星",
    "小新",
    "小兴",
    "小鑫",
    "小行",
    "小型",
    "小心",
    "小幸",
    "晓星",
    "晓新",
}


def normalize_text(text: str) -> str:
    return re.sub(r"[\s，。！？、,.!?]+", "", text or "")


def is_wake_text(text: str) -> bool:
    normalized = normalize_text(text)
    return any(word in normalized for word in WAKE_WORDS)


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
            str(seconds),
            str(path),
        ],
        check=True,
    )


def wav_to_pcm16(path: Path) -> tuple[bytes, int]:
    with wave.open(str(path), "rb") as wav:
        channels = wav.getnchannels()
        width = wav.getsampwidth()
        rate = wav.getframerate()
        frames = wav.readframes(wav.getnframes())

    if channels >= 2:
        # INMP441 is wired to left channel (L/R -> GND).
        frames = audioop.tomono(frames, width, 1, 0)
        channels = 1
    if rate != 16000:
        frames, _ = audioop.ratecv(frames, width, channels, rate, 16000, None)
        rate = 16000
    if width != 2:
        frames = audioop.lin2lin(frames, width, 2)
        width = 2
    return frames, audioop.rms(frames, width)


def run_once(args) -> bool:
    with tempfile.TemporaryDirectory(prefix="sjagent-wake-") as tmp:
        wav_path = Path(tmp) / "chunk.wav"
        record_wav(wav_path, device=args.input_device, seconds=args.chunk_seconds)
        pcm, rms = wav_to_pcm16(wav_path)
    if args.verbose:
        print(f"rms={rms}")
    if rms < args.rms_threshold:
        return False

    try:
        text = recognize_pcm16(pcm, sample_rate=16000, timeout=args.asr_timeout)
    except Exception as exc:
        print(f"ASR_ERROR {exc}", flush=True)
        return False

    print(f"ASR {text}", flush=True)
    if is_wake_text(text):
        play_prompt("wake", device=args.output_device)
        return True
    return False


def main() -> None:
    load_dotenv(dotenv_path=ROOT / ".env")
    parser = argparse.ArgumentParser(description="Listen for 小星 and play a wake reply")
    parser.add_argument("--input-device", default="hw:CARD=ahubi2s3,DEV=0")
    parser.add_argument("--output-device", default="")
    parser.add_argument("--chunk-seconds", type=float, default=2.2)
    parser.add_argument("--cooldown", type=float, default=2.5)
    parser.add_argument("--rms-threshold", type=int, default=120)
    parser.add_argument("--asr-timeout", type=int, default=30)
    parser.add_argument("--once", action="store_true", help="Record and process one chunk")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    ensure_group("wake")
    if args.once:
        raise SystemExit(0 if run_once(args) else 1)

    print("wake listener started", flush=True)
    while True:
        woke = run_once(args)
        if woke:
            time.sleep(args.cooldown)


if __name__ == "__main__":
    main()
