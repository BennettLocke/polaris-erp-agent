"""渠道适配器基类"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
from src.utils import get_logger

logger = get_logger("sjagent.channels.base")


@dataclass
class ChannelMessage:
    """统一消息格式"""
    user_id: str           # 用户标识
    session_id: str        # 会话ID
    content: str           # 消息内容（文本）
    image_urls: list[str]  # 图片URL列表（可选）
    channel: str           # 来源渠道（如 feishu/http）
    raw: dict              # 原始消息体


class ChannelAdapter(ABC):
    """
    渠道适配器基类
    所有渠道接入（飞书/Web/HTTP）都实现此接口
    """

    def __init__(self):
        self.logger = logger.bind(channel=self.__class__.__name__)

    @abstractmethod
    def handle_message(self, message: ChannelMessage) -> str:
        """
        处理收到的消息，返回 Agent 输出

        Args:
            message: 统一格式的消息

        Returns:
            Agent 响应字符串
        """
        pass

    @abstractmethod
    def send_message(self, user_id: str, content: str) -> bool:
        """
        主动发送消息给用户（如异步通知）

        Args:
            user_id: 用户标识
            content: 消息内容

        Returns:
            是否发送成功
        """
        pass

    def extract_message(self, raw: dict) -> ChannelMessage:
        """
        从原始消息体中提取统一格式
        子类实现
        """
        raise NotImplementedError
