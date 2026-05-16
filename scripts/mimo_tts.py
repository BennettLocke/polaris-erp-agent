"""Command line helper for MiMo TTS."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.services.mimo_tts import synthesize, synthesize_wake_reply


def main() -> None:
    load_dotenv(dotenv_path=ROOT / ".env")
    parser = argparse.ArgumentParser(description="Generate speech with MiMo TTS")
    parser.add_argument("text", nargs="?", default="在呢", help="Text to synthesize")
    parser.add_argument("-o", "--output", help="Output audio path")
    parser.add_argument("--context", default="", help="Optional user context for tone")
    parser.add_argument("--voice", default=None, help="MiMo voice, e.g. mimo_default/default_zh")
    parser.add_argument("--format", default=None, help="Audio format, e.g. wav/mp3/pcm16")
    parser.add_argument("--wake-reply", action="store_true", help="Generate the fixed wake reply: 在呢")
    args = parser.parse_args()

    if args.wake_reply:
        path = synthesize_wake_reply(args.output)
    else:
        path = synthesize(
            args.text,
            args.output,
            context=args.context,
            voice=args.voice,
            audio_format=args.format,
        )
    print(path)


if __name__ == "__main__":
    main()
