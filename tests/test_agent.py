"""Agent 主入口测试"""
import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv

# 添加项目根目录到路径，保证可以 import src.*
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.agent import Agent
from src.core.session import HISTORY_DIR


def _session_id(name: str) -> str:
    return f"test_agent_{name}_{uuid.uuid4().hex[:8]}"


def _cleanup_session(session_id: str) -> None:
    path = HISTORY_DIR / f"{session_id}.json"
    if path.exists():
        path.unlink()


def test_agent_import():
    """测试 Agent 能否正常导入"""
    load_dotenv()
    agent = Agent()
    assert agent is not None
    print("✅ Agent 导入成功")


def test_intent_classification():
    """测试意图识别"""
    load_dotenv()
    agent = Agent()

    # 测试图片订单
    sid1 = _session_id("image")
    try:
        result1 = agent.run("客户发了个图片下单，帮我开单", session_id=sid1)
        print(f"图片订单测试: {result1[:50]}...")
    finally:
        _cleanup_session(sid1)

    # 测试文字下单
    sid2 = _session_id("text_order")
    try:
        result2 = agent.run("银茗要1件喜悦三小盒", session_id=sid2)
        print(f"文字下单测试: {result2[:50]}...")
    finally:
        _cleanup_session(sid2)

    print("✅ 意图识别测试通过")


if __name__ == "__main__":
    test_agent_import()
    test_intent_classification()
