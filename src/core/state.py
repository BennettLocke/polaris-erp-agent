"""Agent 状态定义 - LangGraph StateGraph 的状态结构"""
from typing import TypedDict, Optional, Literal
from datetime import datetime


class AgentState(TypedDict, total=False):
    """
    LangGraph 状态机流转的全局状态。
    每个节点可以在状态上读写，后续节点能读到前置节点的输出。
    """

    # ---- 对话上下文 ----
    user_id: str                          # 用户标识
    session_id: str                       # 会话ID
    input: str                            # 用户原始输入
    output: str                           # Agent 最终输出（用于返回给用户）

    # ---- 意图识别 ----
    intent: Optional[str]                 # 识别出的意图类型
    intent_confidence: Optional[float]    # 置信度 0~1
    intent_related_knowledge: Optional[list[str]]  # 检索到的相关知识库片段

    # ---- 图片订单流程（A流程）----
    image_paths: Optional[list[str]]      # 图片路径列表
    image_crop_results: Optional[list[dict]]   # 裁切结果
    image_ocr_results: Optional[list[dict]]   # OCR 识别结果
    image_parsed: Optional[list[dict]]   # 解析后的订单信息
    workflow_orders: Optional[list[dict]] # 创建的工作流订单
    has_kaipiao: Optional[bool]          # 图片是否写了"开单"
    product_warnings: Optional[list[str]]  # 商品未找到警告

    # ---- 标准下单流程（B流程）----
    order_items: Optional[list[dict]]    # 订单商品列表
    customer_info: Optional[dict]         # 客户信息
    matched_products: Optional[list[dict]]  # 匹配到的商品
    unit_conversions: Optional[dict]       # 件套换算结果 {product_id: 换算后数量}
    hot_stamp_choices: Optional[dict]    # 烫金泡袋档位选择

    # ---- 库存决策 ----
    inventory_results: Optional[list[dict]]  # 各商品库存查询结果
    inventory_decisions: Optional[list[dict]]  # 库存决策结果
    pending_orders: Optional[list[dict]]   # 待开单商品列表（含进货/调拨标记）
    need_transfer: Optional[bool]          # 是否需要调拨
    need_purchase: Optional[bool]         # 是否需要进货

    # ---- 确认节点 ----
    confirmation_required: Optional[bool]  # 是否需要用户确认
    confirmation_message: Optional[str]     # 确认提示信息
    confirmed: Optional[bool]             # 用户是否确认

    # ---- 业务执行结果 ----
    purchase_results: Optional[list[dict]]    # 进货结果
    transfer_results: Optional[list[dict]]    # 调拨结果
    sales_results: Optional[list[dict]]       # 销售单结果
    print_results: Optional[list[dict]]       # 打印结果
    execution_errors: Optional[list[str]]     # 执行错误列表

    # ---- 知识库检索 ----
    knowledge_query: Optional[str]        # 知识库检索词
    knowledge_chunks: Optional[list[dict]]  # 检索到的知识片段

    # ---- 工具调用记录 ----
    tool_calls: Optional[list[dict]]     # 历史工具调用 [{tool, args, result}]
    last_tool_call: Optional[dict]        # 最近一次工具调用

    # ---- 会话历史（上下文精简）----
    history_summary: Optional[str]        # 历史摘要
    recent_turns: Optional[list[dict]]   # 最近 N 轮对话 [{role, content}]

    # ---- LLM 解析结果 ----
    llm_parsed: Optional[dict]           # LLM 解析的结构化结果（意图/订单等）
    llm_response: Optional[str]          # LLM 生成的回复文本

    # ---- 元信息 ----
    timestamp: datetime                  # 时间戳
    node_name: Optional[str]             # 当前所在节点（用于调试追踪）
