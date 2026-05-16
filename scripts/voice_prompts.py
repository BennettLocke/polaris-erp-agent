"""Manage cached desktop robot voice prompts."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.services.voice_prompts import (  # noqa: E402
    PROMPT_GROUPS,
    ensure_all_prompts,
    ensure_group,
    get_prompts,
    play_prompt,
    prompt_path,
)


def main() -> None:
    load_dotenv(dotenv_path=ROOT / ".env")
    parser = argparse.ArgumentParser(description="Generate/play cached voice prompts")
    parser.add_argument(
        "group",
        nargs="?",
        default="wake",
        choices=sorted(PROMPT_GROUPS.keys()) + ["all"],
        help="Prompt group to generate or play",
    )
    parser.add_argument("--ensure", action="store_true", help="Generate missing audio files")
    parser.add_argument("--force", action="store_true", help="Regenerate existing files")
    parser.add_argument("--play", action="store_true", help="Play one random prompt from the group")
    parser.add_argument("--list", action="store_true", help="List prompt text and file paths")
    parser.add_argument("--device", default="", help="Optional aplay device, e.g. plughw:CARD=M230,DEV=0")
    args = parser.parse_args()

    if args.list:
        groups = PROMPT_GROUPS.keys() if args.group == "all" else [args.group]
        for group in groups:
            for prompt in get_prompts(group):
                print(f"{group}\t{prompt.key}\t{prompt.text}\t{prompt_path(prompt)}")
        return

    if args.ensure:
        paths = ensure_all_prompts(force=args.force) if args.group == "all" else ensure_group(args.group, force=args.force)
        for path in paths:
            print(path)

    if args.play:
        if args.group == "all":
            raise SystemExit("--play requires a concrete group")
        print(play_prompt(args.group, device=args.device, force=args.force))


if __name__ == "__main__":
    main()
