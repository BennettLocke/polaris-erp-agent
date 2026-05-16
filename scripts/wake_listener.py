"""Simple wake-word listener for the Orange Pi desktop robot.

Record short chunks from INMP441, send speech-like chunks to ASR, and play a
cached wake prompt when the transcript resembles
"小星".
"""
from __future__ import annotations

import argparse
import audioop
import math
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

from src.services.aliyun_short_asr import recognize_pcm16 as recognize_pcm16_aliyun  # noqa: E402
from src.services.volc_realtime_asr import recognize_pcm16 as recognize_pcm16_volc  # noqa: E402
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
    "小明",
    "小鸣",
    "小名",
    "小红",
    "小机",
    "小鸡",
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
        # INMP441 is wired to left channel (L/R -> GND).
        frames = audioop.tomono(frames, width, 1, 0)
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


def raw_to_pcm16(raw: bytes, *, gain: float, state) -> tuple[bytes, int, object]:
    """Convert INMP441 S32_LE stereo 48k raw bytes to debiased PCM16 16k mono."""
    width = 4
    frames = audioop.tomono(raw, width, 1, 0)
    frames, state = audioop.ratecv(frames, width, 1, 48000, 16000, state)
    frames = audioop.lin2lin(frames, width, 2)
    if gain and gain != 1.0:
        frames = audioop.mul(frames, 2, gain)
    avg = audioop.avg(frames, 2)
    if avg:
        frames = audioop.bias(frames, 2, -avg)
    return frames, audioop.rms(frames, 2), state


def recognize(args, pcm: bytes) -> str:
    if args.asr_provider == "aliyun":
        return recognize_pcm16_aliyun(
            pcm,
            sample_rate=16000,
            timeout=args.asr_timeout,
            enable_voice_detection=not args.no_cloud_vad,
        )
    return recognize_pcm16_volc(pcm, timeout=args.asr_timeout)


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
        text = recognize(args, pcm)
    except Exception as exc:
        print(f"ASR_ERROR {exc}", flush=True)
        return False

    print(f"ASR {text}", flush=True)
    if is_wake_text(text):
        play_prompt("wake", device=args.output_device)
        return True
    return False


def _vad_threshold(noise_floor: float, args) -> float:
    return max(args.vad_min_rms, noise_floor * args.vad_start_ratio + args.vad_start_margin)


def run_stream(args) -> None:
    frame_seconds = args.vad_frame_ms / 1000
    raw_frame_bytes = int(48000 * frame_seconds) * 2 * 4
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

    print("wake listener stream started", flush=True)
    state = None
    noise_floor = 0.0
    speaking = False
    speech_frames: list[bytes] = []
    pre_roll: list[bytes] = []
    silence_frames = 0
    speech_frames_count = 0
    max_pre_roll = max(1, int(args.vad_pre_roll_ms / args.vad_frame_ms))
    end_silence_frames = max(1, int(args.vad_end_silence_ms / args.vad_frame_ms))
    max_speech_frames = max(1, int(args.vad_max_seconds / frame_seconds))
    min_speech_frames = max(1, int(args.vad_min_speech_ms / args.vad_frame_ms))
    calibration_frames = max(1, int(args.vad_calibration_ms / args.vad_frame_ms))
    calibration: list[int] = []

    while True:
        raw = process.stdout.read(raw_frame_bytes)
        if not raw:
            raise RuntimeError("arecord stopped")
        pcm, rms, state = raw_to_pcm16(raw, gain=args.gain, state=state)
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
        active = rms >= threshold
        if args.verbose:
            print(f"rms={rms} noise={int(noise_floor)} threshold={int(threshold)} active={int(active)}", flush=True)

        if not speaking:
            pre_roll.append(pcm)
            if len(pre_roll) > max_pre_roll:
                pre_roll.pop(0)
            if active:
                speaking = True
                speech_frames = list(pre_roll)
                pre_roll.clear()
                silence_frames = 0
                speech_frames_count = 1
            continue

        speech_frames.append(pcm)
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
            continue

        utterance = b"".join(speech_frames)
        speech_frames = []
        try:
            text = recognize(args, utterance)
        except Exception as exc:
            print(f"ASR_ERROR {exc}", flush=True)
            continue

        print(f"ASR {text}", flush=True)
        if is_wake_text(text):
            play_prompt("wake", device=args.output_device)
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
    parser.add_argument("--no-cloud-vad", action="store_true", help="Disable Aliyun endpoint VAD")
    parser.add_argument("--asr-provider", choices=["volc", "aliyun"], default="volc")
    parser.add_argument("--asr-timeout", type=int, default=15)
    parser.add_argument("--once", action="store_true", help="Record and process one chunk")
    parser.add_argument("--stream-vad", action="store_true", help="Use continuous local VAD before ASR")
    parser.add_argument("--vad-frame-ms", type=int, default=100)
    parser.add_argument("--vad-pre-roll-ms", type=int, default=300)
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
