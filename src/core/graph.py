"""LangGraph 图结构定义"""
from langgraph.graph import StateGraph, END
from src.core.state import AgentState
from src.core.nodes.intent import intent_classify_node
from src.core.nodes.image_workflow import image_workflow_node
from src.core.nodes.order_workflow import order_workflow_node
from src.core.nodes.inventory import inventory_decision_node
from src.core.nodes.knowledge import knowledge_retrieval_node
from src.core.nodes.executor import executor_node
from src.core.nodes.confirmation import confirmation_node
from src.core.nodes.script import script_execute_node
from src.core.nodes.response import result_format_node, response_unknown_node, response_help_node, response_chat_node
from src.utils import get_logger

logger = get_logger("sjagent.graph")


def build_graph() -> StateGraph:
    """
    构建 LangGraph 状态机图

    流程：
      START → intent_classify
                    │
        ┌───────────┼───────────┬────────────┐
        ▼           ▼           ▼            ▼
    [图片订单] [标准下单] [库存查询] [知识库问答] [其他]
        │           │           │            │
        ▼           ▼           ▼            ▼
    image_    order_      inventory_  knowledge_
    workflow   workflow    query       retrieval
        │           │           │            │
        │           ▼           │            │
        │      inventory_      │            │
        │      decision         │            │
        │           │           │            │
        │           ▼           │            │
        │    confirmation ──────┼────────────┤
        │      (询问确认)       │            │
        │           │           │            │
        │    ┌──────┴──────┐    │            │
        │    ▼             ▼    ▼            ▼
        │ executor    response_   → result_format → END
        │ (执行业务)    cancel
        │    │
        │    ▼
        │ script_execute
        │    │
        │    ▼
        └──────→ result_format → END
    """

    g = StateGraph(AgentState)

    # ---- 节点注册 ----
    g.add_node("intent_classify", intent_classify_node)
    g.add_node("image_workflow", image_workflow_node)
    g.add_node("order_workflow", order_workflow_node)
    g.add_node("inventory_decision", inventory_decision_node)
    g.add_node("knowledge_retrieval", knowledge_retrieval_node)
    g.add_node("confirmation", confirmation_node)
    g.add_node("executor", executor_node)
    g.add_node("script_execute", script_execute_node)
    g.add_node("result_format", result_format_node)
    g.add_node("response_unknown", response_unknown_node)
    g.add_node("response_help", response_help_node)
    g.add_node("response_chat", response_chat_node)

    # ---- 入口 ----
    g.set_entry_point("intent_classify")

    # ---- 意图路由 ----
    g.add_conditional_edges(
        "intent_classify",
        route_intent,
        {
            "image_order": "image_workflow",
            "text_order": "order_workflow",
            "inventory_query": "inventory_decision",
            "knowledge_qa": "knowledge_retrieval",
            "help": "response_help",
            "chat": "response_chat",
            "unknown": "response_unknown",
        },
    )

    # ---- 图片订单流程 ----
    g.add_edge("image_workflow", "inventory_decision")

    # ---- 标准下单流程 ----
    g.add_edge("order_workflow", "inventory_decision")

    # ---- inventory_decision 出边：根据意图分流 ----
    g.add_conditional_edges(
        "inventory_decision",
        route_after_inventory,
        {
            "to_confirmation": "confirmation",
            "to_result": "result_format",
        },
    )

    # ---- 确认节点出边 ----
    g.add_conditional_edges(
        "confirmation",
        route_confirmation,
        {
            "confirmed": "executor",
            "rejected": "result_format",
        },
    )

    # ---- 执行流程 ----
    g.add_edge("executor", "script_execute")
    g.add_edge("script_execute", "result_format")

    # ---- 知识库问答 ----
    g.add_edge("knowledge_retrieval", "result_format")

    # ---- 未知意图 ----
    g.add_edge("response_unknown", "result_format")

    # ---- 帮助/闲聊 ----
    g.add_edge("response_help", "result_format")
    g.add_edge("response_chat", "result_format")

    # ---- 最终节点 ----
    g.add_edge("result_format", END)

    return g


def route_intent(state: AgentState) -> str:
    """意图识别后的路由分发"""
    intent = state.get("intent", "unknown")
    logger.info(f"路由意图: {intent}")
    return intent


def route_after_inventory(state: AgentState) -> str:
    """inventory_decision 节点后的路由：库存查询直接到结果，下单流程到确认"""
    intent = state.get("intent", "unknown")
    if intent == "inventory_query":
        return "to_result"
    return "to_confirmation"


def route_confirmation(state: AgentState) -> str:
    """确认节点后的路由"""
    confirmed = state.get("confirmed", False)
    if confirmed:
        return "confirmed"
    return "rejected"
