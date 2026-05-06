"""
LLM 客户端模块
提供统一的大模型调用接口，支持对话上下文
"""
import json
import re
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from src.core.config import get_config
from src.utils import get_logger

logger = get_logger("sjagent.llm")

_llm_instance = None

# 最多保留的历史轮数
MAX_HISTORY_TURNS = 10


def get_llm() -> ChatAnthropic:
    """获取 LLM 客户端单例"""
    global _llm_instance
    if _llm_instance is None:
        config = get_config()
        _llm_instance = ChatAnthropic(
            model=config.llm_model,
            anthropic_api_key=config.llm_api_key,
            base_url=config.llm_base_url,
            max_tokens=config.llm_max_tokens,
            temperature=0.1,
        )
        logger.info(f"LLM 客户端初始化: model={config.llm_model}, base_url={config.llm_base_url}")
    return _llm_instance


def _build_messages(
    system_prompt: str,
    user_prompt: str,
    history: list[dict] | None = None,
) -> list:
    """
    构建消息列表，包含系统提示 + 历史对话 + 当前用户输入

    Args:
        system_prompt: 系统提示词
        user_prompt: 当前用户输入
        history: 历史对话 [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
    """
    messages = [SystemMessage(content=system_prompt)]

    # 加入历史对话（只保留最近 N 轮）
    if history:
        recent = history[-(MAX_HISTORY_TURNS * 2):]
        for turn in recent:
            role = turn.get("role", "")
            content = turn.get("content", "")
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))

    # 当前用户输入
    messages.append(HumanMessage(content=user_prompt))
    return messages


def llm_chat(
    system_prompt: str,
    user_prompt: str,
    history: list[dict] | None = None,
) -> str:
    """
    调用 LLM 获取文本回复（支持上下文）

    Args:
        system_prompt: 系统提示词
        user_prompt: 当前用户输入
        history: 历史对话 [{"role": "user/assistant", "content": "..."}]

    Returns:
        LLM 回复文本
    """
    try:
        llm = get_llm()
        messages = _build_messages(system_prompt, user_prompt, history)
        response = llm.invoke(messages)
        content = response.content
        # 处理 content blocks 格式（MIMO 返回数组）
        if isinstance(content, list):
            text_parts = [block.get("text", "") for block in content if isinstance(block, dict) and block.get("type") == "text"]
            content = "\n".join(text_parts)
        return content.strip()
    except Exception as e:
        logger.error(f"LLM 调用失败: {e}")
        raise


def llm_stream(
    system_prompt: str,
    user_prompt: str,
    history: list[dict] | None = None,
):
    """
    流式输出 LLM 回复（yield 每个 token）

    Args:
        system_prompt: 系统提示词
        user_prompt: 当前用户输入
        history: 历史对话

    Yields:
        每次 yield 一个 token 字符串
    """
    llm = get_llm()
    messages = _build_messages(system_prompt, user_prompt, history)
    for chunk in llm.stream(messages):
        text = chunk.content
        if isinstance(text, list):
            text = "".join(
                block.get("text", "")
                for block in text
                if isinstance(block, dict) and block.get("type") == "text"
            )
        if text:
            yield text


def llm_json(
    system_prompt: str,
    user_prompt: str,
    history: list[dict] | None = None,
) -> dict:
    """
    调用 LLM 并解析返回的 JSON（支持上下文）

    Args:
        system_prompt: 系统提示词（要求返回 JSON）
        user_prompt: 当前用户输入
        history: 历史对话

    Returns:
        解析后的 dict
    """
    text = llm_chat(system_prompt, user_prompt, history)
    return _parse_json_response(text)


def _parse_json_response(text: str) -> dict:
    """从 LLM 回复中提取并解析 JSON"""
    text = text.strip()

    # 如果被 markdown 代码块包裹，提取内容
    code_block = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if code_block:
        text = code_block.group(1).strip()

    # 尝试找到 JSON 对象
    json_match = re.search(r'\{.*\}', text, re.DOTALL)
    if json_match:
        text = json_match.group(0)

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.warning(f"JSON 解析失败: {e}, 原文: {text[:200]}")
        raise ValueError(f"LLM 返回的不是有效 JSON: {text[:200]}")


# ---- 业务参数提取 ----

EXTRACT_ORDER_PROMPT = """你是肆计包装-北极星订单管理机器人的订单参数提取器。
从用户输入中提取订单信息，返回JSON。

用户说：{user_input}

返回格式：
{{
  "customer": "客户名称（没有则为null）",
  "products": [
    {{
      "name": "商品名（去掉颜色和数量，如'岩味半斤红色1套'→'岩味半斤'）",
      "quantity": 数量（整数）,
      "unit": "件/套/张/个/捆/斤",
      "color": "颜色（没有则为空字符串）"
    }}
  ],
  "warehouse": "自己店里/百鑫/不指定"
}}

注意：
- "喜悦3两"、"喜悦三两" 中的 "3两/三两" 是商品规格，不是数量；商品名应提取为 "喜悦3两"，数量没有明说则默认1套
- "喜悦3两红色5套" = 商品名"喜悦3两"，颜色"红色"，数量5，单位"套"
- "喜悦3小盒黄色5套" = 商品名"喜悦3小盒"，颜色"黄色"，数量5，单位"套"
- "标签2张" = 商品名"标签"，数量2，单位"张"
- "岩味半斤红色1套" = 商品名"岩味半斤"，颜色"红色"，数量1，单位"套"
- "标签4张 + 岩味半斤红色1套" = 2个商品
- "自己店里" 或 "百鑫" 出现在末尾 → warehouse 字段
- 如果用户没说客户名 → customer 为 null
- 如果没说数量 → quantity 默认 1
- 如果没说单位 → 根据商品名推断（标签=张，泡袋=个，斤/半斤=斤，其他=套）"""


def llm_extract_order_params(user_input: str) -> dict:
    """
    从用户输入中提取订单参数。

    Returns:
        {"customer": "测试客户|null", "products": [{"name":"", "qty":0, "unit":"套", "color":""}], "warehouse": "自己店里|null"}
    """
    prompt = EXTRACT_ORDER_PROMPT.format(user_input=user_input)
    try:
        result = llm_json(prompt, user_input)
        # 标准化字段名
        if "items" in result and "products" not in result:
            result["products"] = result.pop("items")
        for p in result.get("products", []):
            if "qty" not in p and "quantity" in p:
                p["qty"] = p.pop("quantity")
            elif "qty" not in p:
                p["qty"] = 1
            if "color" not in p:
                p["color"] = ""
            if "unit" not in p:
                p["unit"] = "套"
        return result
    except Exception as e:
        logger.warning(f"LLM 提取订单参数失败: {e}")
        return {"customer": None, "products": [], "warehouse": None}


EXTRACT_WAREHOUSE_PROMPT = """从用户回答中判断仓库选择。
用户说：{user_input}

返回JSON：
{{
  "warehouse_id": 1或2,
  "warehouse_name": "自己店里"或"百鑫仓库"
}}

规则：
- "自己"、"店里"、"自己店里" → 1
- "百鑫"、"仓库"、"百鑫仓库" → 2
- 其他 → 2（默认百鑫）"""


def llm_extract_warehouse(user_input: str) -> dict:
    """从用户回答中提取仓库选择"""
    prompt = EXTRACT_WAREHOUSE_PROMPT.format(user_input=user_input)
    try:
        result = llm_json(prompt, user_input)
        wid = result.get("warehouse_id", 2)
        if wid not in (1, 2):
            wid = 2
        return {"warehouse_id": wid, "warehouse_name": result.get("warehouse_name", "百鑫仓库")}
    except Exception:
        # fallback: 关键词匹配
        if "自己" in user_input or "店里" in user_input:
            return {"warehouse_id": 1, "warehouse_name": "自己店里"}
        return {"warehouse_id": 2, "warehouse_name": "百鑫仓库"}
