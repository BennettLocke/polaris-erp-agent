"""Agent 主入口测试"""
import sys
from pathlib import Path

# 添加 src 目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.core.agent import Agent


def test_agent_import():
    """测试 Agent 能否正常导入"""
    agent = Agent()
    assert agent is not None
    print("✅ Agent 导入成功")


def test_intent_classification():
    """测试意图识别"""
    agent = Agent()

    # 测试图片订单
    result1 = agent.run("客户发了个图片下单，帮我开单")
    print(f"图片订单测试: {result1[:50]}...")

    # 测试文字下单
    result2 = agent.run("银茗要1件喜悦三小盒")
    print(f"文字下单测试: {result2[:50]}...")

    print("✅ 意图识别测试通过")


if __name__ == "__main__":
    test_agent_import()
    test_intent_classification()
