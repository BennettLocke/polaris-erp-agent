"""API 客户端测试"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.engine.api_client import ERPSystemClient


def test_api_client_init():
    """测试 API 客户端初始化"""
    client = ERPSystemClient()
    assert client.base_url is not None
    assert "shop.513sjbz.com" in client.base_url
    print("✅ API 客户端初始化成功")


if __name__ == "__main__":
    test_api_client_init()
