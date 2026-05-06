"""知识库检索节点 - LLM 增强问答"""
import threading
from src.core.state import AgentState
from src.core.config import get_config
from src.knowledge.retriever import KnowledgeRetriever
from src.utils import get_logger

logger = get_logger("sjagent.nodes.knowledge")

# 全局知识库检索器（常驻内存，线程安全）
_kb_retriever: KnowledgeRetriever | None = None
_kb_lock = threading.Lock()

KNOWLEDGE_QA_PROMPT = """你是肆计包装-北极星订单管理机器人，名字叫北极星，是知识库问答助手。
根据检索到的资料片段，回答用户的问题。

要求：
1. 直接回答用户问题，不要说"根据资料库"之类的开头
2. 用简洁明了的中文回答
3. 如果资料中有具体数据（价格、规格、数量），直接引用
4. 如果资料不足以回答，如实说明
5. 不要编造系统能力，不要使用旧品牌名
6. 语气亲切自然，像门店员工在解答客户疑问"""


def get_retriever() -> KnowledgeRetriever:
    """获取知识库检索器单例（线程安全）"""
    global _kb_retriever
    if _kb_retriever is None:
        with _kb_lock:
            if _kb_retriever is None:
                _kb_retriever = KnowledgeRetriever()
                _kb_retriever.load()
    return _kb_retriever


def knowledge_retrieval_node(state: AgentState) -> AgentState:
    """
    知识库检索节点
    从 sjbzwiki 知识库中检索相关内容，用 LLM 生成自然语言回答
    """
    user_input = state.get("input", "")
    state["node_name"] = "knowledge_retrieval"

    try:
        config = get_config()
        top_k = config.get("business_rules.knowledge_qa.top_k", 5)
        retriever = get_retriever()
        chunks = retriever.retrieve(user_input, top_k=top_k)
        state["knowledge_chunks"] = chunks

        if chunks:
            history = state.get("recent_turns", [])
            answer = build_knowledge_answer(chunks, user_input, history)
            state["output"] = answer
        else:
            state["output"] = "知识库中未找到相关内容，请换个问法或联系管理员补充资料。"

    except Exception as e:
        logger.error(f"知识库检索异常: {e}")
        state["output"] = f"知识库检索异常：{str(e)}"

    return state


def build_knowledge_answer(chunks: list[dict], query: str, history: list[dict] | None = None) -> str:
    """用 LLM 基于检索片段生成自然语言回答"""
    # 组装上下文
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        title = chunk.get("title", "未知")
        content = chunk.get("content", "")
        source = chunk.get("source", "")
        context_parts.append(f"【{title}】{content[:800]}")
        if source:
            context_parts[-1] += f" (来源: {source})"

    context = "\n\n".join(context_parts)

    user_prompt = f"""资料内容：
{context}

用户问题：{query}

请根据以上资料回答用户问题："""

    try:
        from src.core.llm import llm_chat
        answer = llm_chat(KNOWLEDGE_QA_PROMPT, user_prompt, history)
        if answer and len(answer) > 10:
            return answer
    except Exception as e:
        logger.warning(f"LLM 知识问答生成失败，回退模板: {e}")

    # fallback: 拼接原文
    lines = ["根据资料库查询结果：\n"]
    for chunk in chunks:
        title = chunk.get("title", "未知")
        content = chunk.get("content", "")
        lines.append(f"--- {title} ---")
        lines.append(content[:500])
        lines.append("")
    return "\n".join(lines)
