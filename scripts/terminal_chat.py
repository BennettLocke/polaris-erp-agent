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

from src.core.agent import Agent  # noqa: E402
from src.services.screen_state import notify_screen_state  # noqa: E402


_AGENT: Agent | None = None


def compact_reply(text: str, *, max_chars: int = 180) -> str:
    value = (text or "").strip()
    if "库存查询" in value and "|" in value:
        product = ""
        rows: list[tuple[str, str, int]] = []
        for raw in value.splitlines():
            line = raw.strip()
            if line.startswith("库存查询"):
                product = line.split("：", 1)[-1].replace(" ", "").strip()
                continue
            if not line.startswith("|") or "---" in line:
                continue
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if len(cells) < 4 or cells[0] == "仓库" or cells[1] == "合计":
                continue
            try:
                qty = int(float(cells[-1]))
            except ValueError:
                continue
            warehouse, item_name, color = cells[0], cells[1], cells[2]
            if not product:
                product = item_name.replace("【", "").replace("】", "").replace(" ", "")
            rows.append((warehouse, color, qty))
        if rows:
            grouped: dict[str, list[tuple[str, int]]] = {}
            for warehouse, color, qty in rows:
                label = "百鑫库存" if "百鑫" in warehouse else "自己店里" if ("自己" in warehouse or "店" in warehouse) else warehouse
                grouped.setdefault(label, []).append((color, qty))
            parts = []
            for warehouse, items in grouped.items():
                details = "，".join(f"{color or '未标颜色'}{qty}套" for color, qty in items)
                parts.append(f"{warehouse}{details}")
            return f"{product}：" + "；".join(parts)

    lines = []
    for raw in value.splitlines():
        line = raw.strip()
        if not line or line.startswith("|") or set(line) <= {"-", ":", "|", " "}:
            continue
        line = line.replace("**", "").replace("#", "").replace("`", "")
        lines.append(line)
    short = "。".join(lines) if lines else value
    if len(short) > max_chars:
        short = short[:max_chars].rstrip("，。；; ") + "。"
    return short


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
    display_reply = compact_reply(reply)
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
    args = parser.parse_args()

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
