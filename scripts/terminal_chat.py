#!/usr/bin/env python3
"""Terminal text tester for the running sjagent HTTP API."""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request


def post_chat(url: str, message: str, *, user_id: str, session_id: str, timeout: float) -> str:
    payload = {
        "message": message,
        "user_id": user_id,
        "session_id": session_id,
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8", "replace")
    result = json.loads(body)
    if result.get("code") != 0:
        raise RuntimeError(result.get("msg") or body)
    return str((result.get("data") or {}).get("response") or "")


def run_once(args: argparse.Namespace, message: str) -> int:
    started = time.time()
    print("你：", message, flush=True)
    try:
        reply = post_chat(
            args.url,
            message,
            user_id=args.user_id,
            session_id=args.session_id,
            timeout=args.timeout,
        )
    except urllib.error.URLError as exc:
        print(f"请求失败：{exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"处理失败：{exc}", file=sys.stderr)
        return 1
    elapsed = time.time() - started
    print(f"小星：{reply}")
    print(f"耗时：{elapsed:.1f}s")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Type text commands and see sjagent replies.")
    parser.add_argument("message", nargs="*", help="Optional one-shot message.")
    parser.add_argument("--url", default="http://127.0.0.1:8080/api/agent/chat")
    parser.add_argument("--user-id", default="orangepi_terminal")
    parser.add_argument("--session-id", default="terminal_test")
    parser.add_argument("--timeout", type=float, default=90)
    args = parser.parse_args()

    if args.message:
        return run_once(args, " ".join(args.message).strip())

    print("终端文字测试已启动。输入内容后回车，输入 q 退出。")
    print(f"接口：{args.url}")
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
