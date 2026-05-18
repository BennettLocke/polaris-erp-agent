#!/usr/bin/env python3
"""Terminal text tester for Orange Pi voice-style agent runs."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
if VENV_PYTHON.exists() and os.environ.get("SJ_TERMINAL_CHAT_NO_REEXEC") != "1":
    current = Path(sys.executable).absolute()
    target = VENV_PYTHON.absolute()
    if current != target:
        env = dict(os.environ)
        env["SJ_TERMINAL_CHAT_NO_REEXEC"] = "1"
        os.execve(str(target), [str(target), *sys.argv], env)

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(dotenv_path=ROOT / ".env")

from loguru import logger  # noqa: E402

logger.remove()

from src.core.agent import Agent  # noqa: E402
from src.services.screen_state import notify_screen_state  # noqa: E402
from src.services.voice_reply_formatter import format_voice_reply  # noqa: E402

logger.remove()

_AGENT: Agent | None = None


def get_agent() -> Agent:
    global _AGENT
    if _AGENT is None:
        _AGENT = Agent()
    return _AGENT


def screen_notify(args: argparse.Namespace, status: str, *, role: str | None = None, text: str | None = None) -> None:
    notify_screen_state(status, role=role, text=text, url=args.screen_state_url, timeout=0.7)


def run_once(args: argparse.Namespace, message: str) -> int:
    started = time.time()
    print("你：", message, flush=True)
    screen_notify(args, "listen", role="user", text=message)
    screen_notify(args, "processing")
    try:
        reply = get_agent().run(message, user_id=args.user_id, session_id=args.session_id)
    except Exception as exc:
        print(f"处理失败：{exc}", file=sys.stderr)
        screen_notify(args, "error", role="assistant", text=f"处理失败：{exc}")
        return 1
    display_reply = format_voice_reply(reply)
    screen_notify(args, "talk", role="assistant", text=display_reply)
    elapsed = time.time() - started
    print(f"小星：{display_reply}")
    print(f"耗时：{elapsed:.1f}s")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Type text commands and see sjagent replies.")
    parser.add_argument("message", nargs="*", help="Optional one-shot message.")
    parser.add_argument("--user-id", default="orangepi_terminal")
    parser.add_argument("--session-id", default="terminal_test")
    parser.add_argument("--screen-state-url", default="http://127.0.0.1:8080/api/screen/state")
    parser.add_argument("--verbose-logs", action="store_true")
    args = parser.parse_args()
    if args.verbose_logs:
        logger.add(sys.stderr, level="INFO")

    if args.message:
        return run_once(args, " ".join(args.message).strip())

    print("终端文字测试已启动。输入内容后回车，输入 q 退出。")
    print(f"屏幕状态接口：{args.screen_state_url}")
    while True:
        try:
            message = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not message:
            continue
        if message.lower() in {"q", "quit", "exit"}:
            return 0
        run_once(args, message)


if __name__ == "__main__":
    raise SystemExit(main())
