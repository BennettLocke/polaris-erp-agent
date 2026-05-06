"""意图识别节点 - LLM 驱动 + 正则 fallback"""
import re
from src.core.state import AgentState
from src.core.config import get_config
from src.utils import get_logger

logger = get_logger("sjagent.nodes.intent")

# ---- LLM 意图分类 ----

INTENT_SYSTEM_PROMPT = """你是肆计包装-北极星订单管理机器人的意图分类器。
根据用户输入和对话历史，判断属于哪种意图。

意图类型：
- image_order: 用户发送了图片/设计稿/截图，要按图下单
- text_order: 用户用文字描述要下单、进货、调拨（包含商品名+数量）
- inventory_query: 查询库存（问某商品仓库里还有多少、查库存、有没有货、够不够）
- knowledge_qa: 礼盒、包装、商品、工艺、业务规则等资料库知识咨询（问什么是xxx、怎么选、流程、规格等）
- help: 询问你是谁、你能做什么、功能介绍、是否支持某功能
- chat: 闲聊（你好、谢谢、再见、夸奖等）
- unknown: 无法判断

重要规则：
- "有几套""每件几套""一件多少个"这类问商品规格/换算关系的，属于 knowledge_qa，不是 inventory_query
- "有几套库存""库存还有几套"才是 inventory_query
- "够吗""还够吗"等简短追问，结合对话历史判断意图
- "你是谁""你会通知到企业微信吗"这类机器人身份/能力问题属于 help 或 chat，不属于 knowledge_qa

请只返回JSON，不要其他内容：
{"intent": "类型", "confidence": 0.0到1.0}"""

VALID_INTENTS = {"image_order", "text_order", "inventory_query", "knowledge_qa", "help", "chat", "unknown"}


def llm_classify_intent(user_input: str, history: list[dict] | None = None) -> tuple[str, float]:
    """
    用 LLM 分类用户意图

    Returns:
        (intent, confidence) 元组
    """
    try:
        from src.core.llm import llm_json
        result = llm_json(INTENT_SYSTEM_PROMPT, user_input, history)
        intent = result.get("intent", "unknown")
        confidence = float(result.get("confidence", 0.5))

        if intent not in VALID_INTENTS:
            logger.warning(f"LLM 返回无效意图: {intent}, 回退 unknown")
            return "unknown", 0.3

        return intent, confidence
    except Exception as e:
        logger.warning(f"LLM 意图分类失败: {e}")
        return "unknown", 0.0


# ---- 正则 fallback（保留作为备用）----

DEFAULT_INTENT_PATTERNS = {
    "image_order": [
        r"图片", r"发图", r"下单.*图", r"设计稿",
        r"\.jpg", r"\.png", r"\.jpeg", r"收到.*图",
        r"这个.*礼盒", r"按这个.*做", r"照图片",
    ],
    "text_order": [
        r"要[^\s]+个?[礼盒泡袋提袋]", r"[^\s]+个?[礼盒泡袋提袋内衬]",
        r"客户[^\s]+[礼盒泡袋]", r"订[^\s]+[礼盒泡袋]",
        r"开单", r"下单", r"帮我.*下单", r"做个?[礼盒泡袋]",
        r"进货", r"调货", r"调拨",
    ],
    "inventory_query": [
        r"库存", r"还有.*货", r"查[一下]?库存",
        r"有没有.*礼盒", r"还剩多少",
    ],
    "knowledge_qa": [
        r"是什么", r"怎么", r"如何", r"流程",
        r"规则", r"要求", r"规格", r"价格",
        r"哪个", r"多少.*钱", r"怎么选",
    ],
    "help": [
        r"能.{0,4}干.{0,4}[嘛么]?", r"能.{0,4}做.{0,4}什么",
        r"能.{0,4}干什么", r"你会.{0,6}什么", r"功能", r"帮忙",
        r"介绍.{0,2}一下", r"有什么.{0,4}用",
    ],
    "chat": [
        r"你好", r"谢谢", r"不错", r"厉害",
        r"再见", r"OK", r"好的", r"嗯",
        r"哈哈", r"可以", r"行",
    ],
}


def _regex_classify(user_input: str) -> tuple[str, float]:
    """正则 fallback 意图分类"""
    if has_image_url(user_input) or has_image_extension(user_input):
        return "image_order", 0.9

    best_score = 0
    best_intent = "unknown"
    for intent_name, patterns in DEFAULT_INTENT_PATTERNS.items():
        score = sum(1 for p in patterns if re.search(p, user_input))
        if score > best_score:
            best_score = score
            best_intent = intent_name

    confidence = min(best_score * 0.3, 0.9) if best_score > 0 else 0.0
    return best_intent, confidence


# ---- 节点函数 ----

def intent_classify_node(state: AgentState) -> AgentState:
    """
    意图识别节点
    优先用 LLM 分类，失败时回退正则
    """
    user_input = state.get("input", "")
    logger.info(f"意图识别输入: {user_input[:80]}")

    # 图片检测（快速路径，不需要 LLM）
    if has_image_url(user_input) or has_image_extension(user_input):
        intent, confidence = "image_order", 0.95
    else:
        # 先尝试 LLM（传入对话历史）
        history = state.get("recent_turns", [])
        intent, confidence = llm_classify_intent(user_input, history)

        # LLM 失败时回退正则
        if intent == "unknown" and confidence == 0.0:
            logger.info("LLM 分类失败，回退正则")
            intent, confidence = _regex_classify(user_input)

    state["intent"] = intent
    state["intent_confidence"] = confidence
    state["node_name"] = "intent_classify"

    logger.info(f"意图识别结果: {intent} (置信度: {confidence:.2f})")
    return state


def has_image_url(text: str) -> bool:
    """检测文本中是否包含图片URL"""
    url_pattern = r"https?://[^\s]+\.(jpg|jpeg|png|gif|webp)"
    return bool(re.search(url_pattern, text, re.IGNORECASE))


def has_image_extension(text: str) -> bool:
    """检测文本中是否包含图片路径"""
    ext_pattern = r"[^\s]+\.(jpg|jpeg|png|gif|webp)"
    return bool(re.search(ext_pattern, text, re.IGNORECASE))
