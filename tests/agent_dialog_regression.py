"""Agent dialog-chain smoke tests and lightweight latency sampling.

This script intentionally avoids confirming destructive actions. It validates
the agent body from text input through intent extraction, workflow execution,
pending-state handling, and reply generation.
"""
from __future__ import annotations

import time
import uuid
from pathlib import Path
import sys

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.agent import Agent
from src.core.session import HISTORY_DIR, SessionManager


def _cleanup_session(session_id: str) -> None:
    path = HISTORY_DIR / f"{session_id}.json"
    if path.exists():
        path.unlink()


def _run_case(agent: Agent, name: str, text: str, expect_any: list[str], max_ms: float | None = None) -> tuple[str, float, str]:
    session_id = f"agent_reg_{name}_{uuid.uuid4().hex[:8]}"
    try:
        start = time.perf_counter()
        reply = agent.run(text, session_id=session_id)
        elapsed_ms = (time.perf_counter() - start) * 1000
        if expect_any and not any(token in reply for token in expect_any):
            raise AssertionError(f"{name}: reply did not contain any of {expect_any!r}: {reply[:300]}")
        if max_ms is not None and elapsed_ms > max_ms:
            raise AssertionError(f"{name}: too slow {elapsed_ms:.1f}ms > {max_ms:.1f}ms")
        return name, elapsed_ms, reply
    finally:
        _cleanup_session(session_id)


def _pending_switch_case(agent: Agent) -> tuple[str, float, str]:
    session_id = f"agent_reg_pending_{uuid.uuid4().hex[:8]}"
    try:
        session = SessionManager(session_id)
        session.clear_pending()
        session.save_pending(
            "inventory",
            {"partial_params": {"intent": "inventory"}},
        )
        start = time.perf_counter()
        reply = agent.run("查下半斤库存", session_id=session_id)
        elapsed_ms = (time.perf_counter() - start) * 1000
        if "库存查询" not in reply and "未找到" not in reply:
            raise AssertionError(f"pending switch failed: {reply[:300]}")
        session_after = SessionManager(session_id)
        if session_after.get_pending_intent() == "inventory" and session_after.get_state() == {"partial_params": {"intent": "inventory"}}:
            raise AssertionError("pending state was not advanced or cleared")
        return "pending_switch", elapsed_ms, reply
    finally:
        _cleanup_session(session_id)


def main() -> None:
    load_dotenv()
    agent = Agent()
    cases = [
        ("identity", "你是谁", ["北极星"], 500),
        ("help", "你能做什么", ["订单相关", "查库存"], 500),
        ("image_workflow", "客户发了个图片下单，帮我开单", ["工作流订单", "客户"], 500),
        ("inventory", "查下半斤库存", ["库存查询", "未找到"], 3500),
        ("sales_query", "齐唯茶业最近3单", ["齐唯茶业", "销售单", "没有找到"], 3000),
        ("order_preview", "开单 齐唯茶业 标签2张", ["确认", "开单", "标签", "未找到"], 5000),
    ]
    results = [_run_case(agent, *case) for case in cases]
    results.append(_pending_switch_case(agent))
    for name, elapsed_ms, reply in results:
        preview = " ".join(str(reply).split())[:140]
        print(f"{name}\t{elapsed_ms:.1f}ms\t{preview}")
    print("agent dialog regression ok")


if __name__ == "__main__":
    main()
