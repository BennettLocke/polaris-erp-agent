"""Record once from Orange Pi INMP441 and recognize it with Volcengine ASR."""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.wake_listener import record_wav, wav_to_pcm16  # noqa: E402
from src.services.volc_realtime_asr import recognize_pcm16  # noqa: E402


def main() -> None:
    load_dotenv(dotenv_path=ROOT / ".env")
    parser = argparse.ArgumentParser(description="Test Volcengine Realtime ASR")
    parser.add_argument("--input-device", default="hw:CARD=ahubi2s3,DEV=0")
    parser.add_argument("--seconds", type=float, default=4.0)
    parser.add_argument("--gain", type=float, default=12.0)
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--wav", help="Recognize an existing WAV instead of recording")
    args = parser.parse_args()

    if args.wav:
        pcm, rms = wav_to_pcm16(Path(args.wav), gain=args.gain)
    else:
        with tempfile.TemporaryDirectory(prefix="sjagent-volc-asr-") as tmp:
            wav_path = Path(tmp) / "chunk.wav"
            record_wav(wav_path, device=args.input_device, seconds=args.seconds)
            pcm, rms = wav_to_pcm16(wav_path, gain=args.gain)

    print(f"rms={rms}", flush=True)
    text = recognize_pcm16(pcm, timeout=args.timeout)
    print(f"ASR {text}", flush=True)


if __name__ == "__main__":
    main()
