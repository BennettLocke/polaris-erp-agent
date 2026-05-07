"""闲聊/帮助流程"""
from src.skills.base import BaseWorkflow
from src.utils import get_logger

logger = get_logger("sjagent.skills.chat")

HELP_TEXT = """我是肆计包装-北极星订单管理机器人，名字叫北极星，可以帮您：

**订单相关：**
- 下单：直接告诉我客户名和商品，例如"测试客户 下单 标签4张 岩味半斤红色1套"
- 查库存：例如"查下岩味库存"
- 盘点：例如"盘点 岩味半斤红色 设为20套"
- 进货：例如"进货 标签100张"
- 调拨：例如"调拨 从自己店里调10套岩味到百鑫"

**其他：**
- 业务咨询：例如"什么是烫金泡袋"
- 删除订单：例如"删除销售单60"

有什么可以帮您的？"""


class ChatWorkflow(BaseWorkflow):
    """闲聊/帮助"""

    def execute(self, user_input: str, params: dict = None) -> dict:
        params = params or {}
        history = params.get("history") or []
        contextual_reply = self._reply_from_history(user_input, history)
        if contextual_reply:
            return self._reply(contextual_reply)

        if any(kw in user_input for kw in ["企业微信", "微信通知", "通知到企业微信"]):
            return self._reply(
                "目前北极星还没有接入企业微信通知。我现在能在 WebUI 里处理库存、调货、销售单、工作流订单和确认/取消操作。"
                "企业微信通知可以后续接：比如订单创建成功、工作流新单、库存不足、删除确认这些节点推送到企业微信。"
            )
        if "语音" in user_input:
            return self._reply("目前北极星还没接语音识别，先走文字和按钮操作。后续可以接语音识别，再加礼盒名称、颜色、规格这些本店词库纠错。")

        # 帮助类
        help_keywords = ["能干什么", "能做什么", "你会什么", "功能", "介绍", "帮忙", "help"]
        if any(kw in user_input for kw in help_keywords):
            return self._reply(HELP_TEXT)

        text = user_input.strip().lower()
        if text in {"你好", "您好", "hello", "hi", "嗨"}:
            return self._reply("你好，我是北极星，肆计包装-北极星订单管理机器人。")
        if any(kw in user_input for kw in ["你是谁", "叫什么", "你的名字"]):
            return self._reply("我是北极星，肆计包装-北极星订单管理机器人。")

        # 闲聊
        from src.core.llm import llm_chat
        try:
            recent = self._format_recent_history(history)
            prompt = (
                "你是肆计包装-北极星订单管理机器人，名字叫北极星。"
                "用简短亲切的语气回复用户，不要使用emoji。"
                "如果用户在追问上一轮订单、图片识别、库存、工作流或销售单，要结合最近对话回答，不要说看不到上下文。"
                f"\n\n最近对话：\n{recent}"
            )
            reply = llm_chat(prompt, user_input)
            return self._reply(reply)
        except Exception:
            return self._reply("你好！有什么可以帮您的？")

    def _reply_from_history(self, user_input: str, history: list[dict]) -> str:
        text = user_input.strip()
        if not history:
            return ""
        if any(kw in text for kw in ["不是已经识别", "明明识别", "识别出来了", "刚才识别"]):
            for item in reversed(history):
                content = item.get("content", "")
                if item.get("role") == "assistant" and "图片识别完成" in content:
                    return "看到了，刚才确实已经识别出内容了。上一条结果是：\n" + content
        return ""

    def _format_recent_history(self, history: list[dict]) -> str:
        if not history:
            return "无"
        lines = []
        for item in history[-8:]:
            role = "用户" if item.get("role") == "user" else "北极星"
            content = str(item.get("content", "")).strip()
            if len(content) > 500:
                content = content[:500] + "..."
            lines.append(f"{role}: {content}")
        return "\n".join(lines)
