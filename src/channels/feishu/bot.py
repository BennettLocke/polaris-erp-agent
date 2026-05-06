"""
飞书机器人接入（完整实现）
支持：消息接收、被动回复、主动推送、事件订阅
"""
import time
import json
from typing import Optional
from src.channels.base import ChannelAdapter, ChannelMessage
from src.core.agent import Agent
from src.utils import get_logger

logger = get_logger("sjagent.feishu.bot")


class FeishuBot(ChannelAdapter):
    """
    飞书机器人完整实现

    功能：
    - 接收用户消息 → 调用 Agent 处理 → 回复
    - 主动推送消息到用户/群
    - 支持文本消息
    """

    def __init__(self, app_id: str, app_secret: str, bot_name: str = "门店智能体"):
        super().__init__()
        self.app_id = app_id
        self.app_secret = app_secret
        self.bot_name = bot_name
        self.agent = Agent()
        self.access_token: Optional[str] = None
        self.token_expires_at: float = 0

    def handle_message(self, message: ChannelMessage) -> str:
        """处理飞书消息"""
        self.logger.info(f"收到飞书消息: user={message.user_id}, content={message.content[:50]}...")

        try:
            response = self.agent.run(
                user_input=message.content,
                user_id=message.user_id,
                session_id=message.session_id,
            )
            return response
        except Exception as e:
            self.logger.error(f"处理消息异常: {e}")
            return f"处理异常：{str(e)}"

    def send_message(self, user_id: str, content: str) -> bool:
        """主动发送消息给用户"""
        try:
            token = self._get_access_token()
            if not token:
                return False

            url = "https://open.feishu.cn/open-apis/im/v1/messages"
            params = {"receive_id_type": "open_id"}
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
            payload = {
                "receive_id": user_id,
                "msg_type": "text",
                "content": json.dumps({"text": content}),
            }

            import requests
            resp = requests.post(url, params=params, json=payload, headers=headers, timeout=10)
            result = resp.json()

            if result.get("code") == 0:
                self.logger.info(f"飞书消息发送成功: user_id={user_id}")
                return True
            else:
                self.logger.error(f"飞书消息发送失败: {result}")
                return False
        except Exception as e:
            self.logger.error(f"飞书消息发送异常: {e}")
            return False

    def send_card_message(self, user_id: str, card_content: dict) -> bool:
        """发送卡片消息"""
        try:
            token = self._get_access_token()
            if not token:
                return False

            url = "https://open.feishu.cn/open-apis/im/v1/messages"
            params = {"receive_id_type": "open_id"}
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
            payload = {
                "receive_id": user_id,
                "msg_type": "interactive",
                "content": json.dumps(card_content),
            }

            import requests
            resp = requests.post(url, params=params, json=payload, headers=headers, timeout=10)
            result = resp.json()
            return result.get("code") == 0
        except Exception as e:
            self.logger.error(f"飞书卡片消息发送异常: {e}")
            return False

    def _get_access_token(self) -> Optional[str]:
        """获取 tenant_access_token（带缓存）"""
        now = time.time()
        if self.access_token and now < self.token_expires_at - 60:
            return self.access_token

        try:
            import requests
            url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
            resp = requests.post(
                url,
                json={"app_id": self.app_id, "app_secret": self.app_secret},
                timeout=10,
            )
            result = resp.json()

            if result.get("code") == 0:
                self.access_token = result["tenant_access_token"]
                self.token_expires_at = now + result.get("expire", 7200)
                return self.access_token
            else:
                self.logger.error(f"获取飞书 access_token 失败: {result}")
                return None
        except Exception as e:
            self.logger.error(f"获取飞书 access_token 异常: {e}")
            return None

    def extract_message(self, raw: dict) -> ChannelMessage:
        """从飞书事件提取统一消息格式"""
        event = raw.get("event", {})
        sender = event.get("sender", {})
        message = event.get("message", {})

        content_str = message.get("content", "{}")
        try:
            content_obj = json.loads(content_str)
        except Exception:
            content_obj = {"text": content_str}

        text = content_obj.get("text", "")

        image_urls = []
        if message.get("msg_type") == "image":
            image_urls = [f"https://open.feishu.cn/open-apis/im/v1/images/{message.get('media_id')}"]

        return ChannelMessage(
            user_id=sender.get("sender_id", {}).get("open_id", "unknown"),
            session_id=raw.get("header", {}).get("event_id", "unknown"),
            content=text,
            image_urls=image_urls,
            channel="feishu",
            raw=raw,
        )

    def build_text_card(self, text: str, header: str = None) -> dict:
        """构建飞书文本卡片"""
        card = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": header or "门店智能体"},
                    "template": "blue",
                },
                "elements": [
                    {"tag": "markdown", "content": text},
                ],
            },
        }
        return card
