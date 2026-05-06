"""知识问答流程"""
from src.skills.base import BaseWorkflow
from src.utils import get_logger

logger = get_logger("sjagent.skills.knowledge")


class KnowledgeWorkflow(BaseWorkflow):
    """知识问答"""

    def execute(self, user_input: str, params: dict = None) -> dict:
        from src.core.llm import llm_chat

        # 搜索知识库
        try:
            from src.core.nodes.knowledge import get_retriever
            retriever = get_retriever()
            chunks = retriever.retrieve(user_input, top_k=5)
        except Exception as e:
            logger.warning(f"知识库检索失败: {e}")
            chunks = []

        if not chunks:
            return self._reply("知识库中未找到相关内容，您可以试试换个关键词问我。")

        # 用 LLM 生成回答
        context = "\n\n".join([
            f"【{c.get('title', '')}】\n{c.get('content', '')[:500]}"
            for c in chunks
        ])

        prompt = f"""你是肆计包装-北极星订单管理机器人，名字叫北极星。根据以下知识库内容回答用户问题。

知识库内容：
{context}

用户问题：{user_input}

请用中文回答，语气亲切自然。不要使用emoji表情符号。如果知识库内容不足以回答，请直接说明资料不足，不要编造系统能力，不要使用旧品牌名。"""

        try:
            answer = llm_chat(prompt, user_input)
            return self._reply(answer)
        except Exception as e:
            # fallback: 直接返回知识库内容
            lines = [f"【{c.get('title', '')}】\n{c.get('content', '')[:300]}" for c in chunks[:3]]
            return self._reply("\n\n".join(lines))
