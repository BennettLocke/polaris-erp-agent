"""
结果输出节点 - LLM 增强回复
业务结果保持结构化格式，闲聊/帮助/未知用 LLM 生成自然回复
"""
from src.core.state import AgentState
from src.core.config import get_config
from src.utils import get_logger

logger = get_logger("sjagent.nodes.response")

# ---- LLM Prompt ----

CHAT_SYSTEM_PROMPT = """你是肆计包装-北极星订单管理机器人，名字叫北极星。
性格：热情、专业、简洁。
职责：帮助门店处理订单、库存查询、业务咨询。

规则：
1. 闲聊时保持亲切自然，不要太长
2. 提到业务时可以适当介绍你的能力
3. 不要说自己是AI/人工智能，你是北极星
4. 回复用中文，语气像门店员工"""


HELP_SYSTEM_PROMPT = """你是肆计包装-北极星订单管理机器人，名字叫北极星。
用户想知道你能做什么，请简洁介绍你的核心能力。

你的能力：
1. 接收图片设计稿，自动识别商品并开单
2. 文字下单：如"测试客户 岩彩礼盒10个 下单"
3. 查询库存：如"查下喜悦库存"
4. 进货调拨：库存不足时自动建议
5. 业务咨询：什么是烫金泡袋、礼盒怎么选等

请用简洁友好的方式介绍，不要超过200字。"""


def result_format_node(state: AgentState) -> AgentState:
    """
    结果格式化节点
    业务结果保持结构化格式，闲聊/帮助用 LLM 生成
    """
    state["node_name"] = "result_format"

    # 如果 LLM 已经生成了回复，直接使用
    llm_response = state.get("llm_response")
    if llm_response:
        state["output"] = llm_response
        logger.info(f"使用 LLM 回复: {llm_response[:100]}")
        return state

    lines = []
    confirmed = state.get("confirmed")
    intent = state.get("intent", "")

    # 用户拒绝
    if confirmed is False:
        state["output"] = "操作已取消，无变动。"
        return state

    # 非订单意图：不显示历史业务结果，直接走 intent 分支
    if intent not in ("text_order", "image_order"):
        if intent in ("knowledge_qa", "inventory_query", "help", "chat", "unknown"):
            logger.info(f"结果输出（{intent}）: {state.get('output', '')[:100]}")
            return state
        lines = ["处理完成，无变动。"]
        state["output"] = "\n".join(lines)
        return state

    # 1. 进货汇总（严格按 B4.3.1 格式）
    purchase_results = state.get("purchase_results", [])
    if purchase_results:
        purchase_text = format_purchase_summary(purchase_results)
        if purchase_text:
            lines.append("【进货汇总】")
            lines.append(purchase_text)
            lines.append("")

    # 2. 调拨汇总
    transfer_results = state.get("transfer_results", [])
    if transfer_results:
        lines.append("【调拨汇总】")
        for t in transfer_results:
            name = t.get("product_name", "")
            color = t.get("color", "")
            qty = t.get("quantity", "")
            lines.append(f"商品：{name}")
            if color:
                lines.append(f"颜色：{color}")
            lines.append(f"数量：{qty}")
            from src.models.constants import TRANSFER_FROM, TRANSFER_TO
            from src.core.config import get_config
            cfg = get_config()
            warehouse_names = {1: "自己店里", 2: "百鑫仓库"}
            from_name = warehouse_names.get(TRANSFER_FROM, f"仓库{TRANSFER_FROM}")
            to_name = warehouse_names.get(TRANSFER_TO, f"仓库{TRANSFER_TO}")
            lines.append(f"已将商品从【{from_name}】调至【{to_name}】")
            lines.append("")
        lines.append("")

    # 3. 开单结果
    sales_results = state.get("sales_results", [])
    if sales_results:
        lines.append("【开单结果】")
        for sale in sales_results:
            sales_id = sale.get("sales_id", "")
            sales_no = sale.get("sales_no", "")
            if sales_no:
                lines.append(f"销售单号：{sales_no}，ID：{sales_id}")
            else:
                lines.append(f"开单成功，ID：{sales_id}")

            items = sale.get("items", [])
            for item in items:
                pname = item.get("product_name", "")
                color = item.get("color", "")
                qty = item.get("buy_number", "")
                lines.append(f"  - {pname} {color} × {qty}")
        lines.append("")

    # 4. 错误信息
    errors = state.get("execution_errors", [])
    if errors:
        lines.append("【错误汇总】")
        for err in errors:
            lines.append(f"- {err}")

    # 5. 商品未找到警告
    product_warnings = state.get("product_warnings", [])
    if product_warnings:
        lines.append("【商品未找到】")
        for w in product_warnings:
            lines.append(f"- {w}")

    if not lines:
        # 知识库问答和库存查询的 output 已由前置节点设置，不应覆盖
        intent = state.get("intent", "")
        if intent in ("knowledge_qa", "inventory_query", "help", "chat", "unknown"):
            logger.info(f"结果输出（{intent}）: {state.get('output', '')[:100]}")
            return state
        lines = ["处理完成，无变动。"]

    state["output"] = "\n".join(lines)
    logger.info(f"结果输出: {state['output'][:100]}")
    return state


def format_purchase_summary(purchase_results: list[dict]) -> str:
    """格式化进货汇总（严格按 B4.3.1 格式）"""
    if not purchase_results:
        return ""

    from scripts.common.unit_converter import is_one_piece_order
    config = get_config()
    purchase_note = config.get("business_rules.purchase_rules.note", "送至百鑫")

    sections = []
    for p in purchase_results:
        name = p.get("product_name", "")
        color = p.get("color", "")
        order_qty = p.get("quantity", 0)
        purchase_qty = p.get("purchase_quantity", order_qty)

        if is_one_piece_order(name):
            qty_text = f"{purchase_qty}件({order_qty}套)"
        else:
            qty_text = f"{order_qty}套"

        sections.append(f"""商品:{name}
颜色:{color}
数量:{qty_text}
备注:{purchase_note}""")

    return "\n\n".join(sections)


# ---- LLM 驱动的响应节点 ----

def response_unknown_node(state: AgentState) -> AgentState:
    """未知意图 - 用 LLM 生成友好回复"""
    state["node_name"] = "response_unknown"
    user_input = state.get("input", "")
    history = state.get("recent_turns", [])

    try:
        from src.core.llm import llm_chat
        answer = llm_chat(CHAT_SYSTEM_PROMPT, f"用户说了：{user_input}\n\n你不确定用户想做什么，请友好回复并引导用户说明需求。", history)
        if answer and len(answer) > 5:
            state["output"] = answer
            return state
    except Exception as e:
        logger.warning(f"LLM 未知意图回复失败: {e}")

    state["output"] = (
        "抱歉，我没有理解您的需求。\n"
        "我可以帮您：\n"
        "- 接收图片设计稿，自动识别并开单\n"
        "- 文字下单，查询库存、进货、调拨\n"
        "- 查询商品信息、库存数量\n"
        "- 业务流程咨询\n\n"
        "请告诉我您需要什么帮助？"
    )
    return state


def response_help_node(state: AgentState) -> AgentState:
    """能力介绍 - 用 LLM 生成"""
    state["node_name"] = "response_help"
    history = state.get("recent_turns", [])

    try:
        from src.core.llm import llm_chat
        answer = llm_chat(HELP_SYSTEM_PROMPT, "用户想知道你能做什么，请介绍你的能力。", history)
        if answer and len(answer) > 20:
            state["output"] = answer
            return state
    except Exception as e:
        logger.warning(f"LLM 帮助回复失败: {e}")

    state["output"] = (
        "我是肆计茶的门店智能助手，可以帮您：\n\n"
        "- 发图片设计稿 → 自动识别商品并开单\n"
        "- 文字下单：如「测试客户 岩彩礼盒10个 下单」\n"
        "- 查询库存：如「查下喜悦库存」\n"
        "- 进货调拨：库存不足时自动建议\n"
        "- 业务咨询：如「什么是烫金泡袋」\n\n"
        "试试看吧！"
    )
    return state


def response_chat_node(state: AgentState) -> AgentState:
    """闲聊回复 - 用 LLM 生成自然对话"""
    state["node_name"] = "response_chat"
    user_input = state.get("input", "")
    history = state.get("recent_turns", [])

    try:
        from src.core.llm import llm_chat
        answer = llm_chat(CHAT_SYSTEM_PROMPT, f"用户说：{user_input}", history)
        if answer and len(answer) > 2:
            state["output"] = answer
            return state
    except Exception as e:
        logger.warning(f"LLM 闲聊回复失败: {e}")

    # fallback
    if any(kw in user_input for kw in ["你好", "hi", "hello"]):
        state["output"] = "你好！我是肆计茶的门店智能助手，有什么可以帮您的？"
    elif any(kw in user_input for kw in ["谢谢", "感谢", "多谢"]):
        state["output"] = "不客气！有其他需要随时找我。"
    elif any(kw in user_input for kw in ["再见", "拜拜", "bye"]):
        state["output"] = "再见！祝您生意兴隆！"
    else:
        state["output"] = "收到！有什么业务上的问题可以随时问我。"

    return state
