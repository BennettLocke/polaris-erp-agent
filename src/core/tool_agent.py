"""
意图分类模块 - LLM 理解 + 正则 fallback

LLM 理解用户意图（灵活，不需要手动加关键词），
正则作为 LLM 失败时的快速 fallback。
"""
import re
from src.core.learning import get_prompt_examples, match_learned, record_example
from src.utils import get_logger

logger = get_logger("sjagent.tool_agent")


# ---- 意图类型定义 ----

INTENT_DESCRIPTIONS = """你是肆计包装-北极星订单管理机器人的意图分类器。根据用户输入，判断属于哪种意图。

意图类型：
- order: 下单、开单、订货（包含商品名+数量的下单请求）
- inventory: 查询库存（问某商品有多少、还有多少、够不够、查库存）
- stocktaking: 盘点同步（设置库存为某个值）
- purchase: 进货、入库、采购
- transfer: 仓库间调拨、调货
- sales_query: 查询销售单列表、订单记录
- sales_manage: 删除销售单、作废订单
- customer_manage: 创建客户、添加客户档案
- series_manage: 管理1件起订/非1件起订系列规则
- print: 打印销售单、创建打印任务
- workflow: 工作流订单（图片下单、设计稿）
- product_manage: 添加新产品
- knowledge: 礼盒、包装、商品、工艺、业务规则等资料库知识咨询（什么是xxx、怎么选、流程、规格）
- help: 询问北极星是谁、你能做什么、是否支持某功能、机器人自身能力
- chat: 闲聊（你好、谢谢、天气等）

不要把“你是谁”“你叫什么”“你会不会/能不能通知企业微信”“你支持什么功能”这类机器人自身能力问题判为 knowledge，应判为 help 或 chat。
请只返回JSON：{"intent": "类型"}"""

VALID_INTENTS = {
    "order", "inventory", "stocktaking", "purchase", "transfer",
    "sales_query", "sales_manage", "customer_manage", "print", "workflow",
    "series_manage", "product_manage", "knowledge", "help", "chat",
}


def llm_classify_intent(user_input: str, history: list[dict] | None = None) -> str | None:
    """用 LLM 分类意图（理解自然语言）"""
    try:
        from src.core.llm import llm_json
        result = llm_json(INTENT_DESCRIPTIONS, user_input, history)
        intent = result.get("intent", "")
        if intent in VALID_INTENTS:
            return intent
    except Exception as e:
        logger.warning(f"LLM 意图分类失败: {e}")
    return None


# ---- 正则 fallback（LLM 失败时使用）----

INTENT_KEYWORDS = {
    "order": [
        r"开单", r"下单", r"做\d+[个件]", r"要\d+[个件套]",
        r"帮我.*做", r"帮我.*下", r"给.*做", r"订\d+",
        r"开.*单", r"下.*单",
    ],
    "stocktaking": [
        r"盘点", r"设置.*库存为", r"库存.*设为", r"库存.*改成",
        r"同步.*库存", r"修正.*库存",
    ],
    "purchase": [
        r"进货", r"入库", r"采购", r"补货",
    ],
    "transfer": [
        r"调拨", r"调货", r"调.*仓库", r"从.*调到", r"从.*调.*到",
    ],
    "inventory": [
        r"库存", r"还有.*货", r"有没有.*货", r"还剩多少",
        r"够不够", r"够吗", r"查.*库存",
        r"有多少[个件套张捆斤]?", r"有几个", r"几个",
        r"还[有剩].*\d", r"数量",
    ],
    "sales_query": [
        r"销售单", r"查.*单", r"订单.*列表", r"销售.*记录",
        r"最近一次", r"下单了什么", r"买了什么", r"订单详情", r"订单内容",
    ],
    "sales_manage": [
        r"删.*销售单", r"删.*单", r"作废",
    ],
    "series_manage": [
        r"1件起", r"一件起", r"件起订", r"非1件起", r"非一件起",
    ],
    "print": [
        r"打印", r"打印.*任务", r"打单",
    ],
    "workflow": [
        r"工作流", r"图片.*下单", r"设计稿", r"按图",
    ],
    "product_manage": [
        r"添加.*产品", r"新增.*产品", r"创建.*产品", r"新产品",
    ],
    "knowledge": [
        r"是什么", r"怎么", r"如何", r"流程",
        r"规则", r"要求", r"规格", r"怎么选",
        r"什么是", r"介绍一下",
    ],
    "help": [
        r"能.{0,4}干.{0,4}[嘛么]?", r"能.{0,4}做.{0,4}什么",
        r"你会.{0,6}什么", r"功能", r"介绍.{0,2}一下",
    ],
    "chat": [
        r"你好", r"谢谢", r"不错", r"厉害",
        r"再见", r"OK", r"好的", r"嗯", r"哈哈",
    ],
}


def regex_classify_intent(user_input: str) -> str:
    """正则 fallback 意图分类"""
    best_score = 0
    best_intent = "unknown"
    for intent_name, patterns in INTENT_KEYWORDS.items():
        score = sum(1 for p in patterns if re.search(p, user_input))
        if score > best_score:
            best_score = score
            best_intent = intent_name
    return best_intent if best_score > 0 else "unknown"


# ---- 统一意图+参数提取 ----

UNIFIED_PROMPT = """你是肆计包装-北极星订单管理机器人，名字叫北极星。根据用户输入，判断意图并提取参数。

意图类型和参数：
- order: 下单 → {"intent":"order", "customer":"客户名", "products":[{"name":"商品名","qty":数量,"unit":"件/套/张/个/捆/斤","color":"颜色或空"}], "warehouse":"自己店里/百鑫/null"}
- inventory: 查库存 → {"intent":"inventory", "product_name":"商品名", "color":"颜色或空"}
- stocktaking: 盘点 → {"intent":"stocktaking", "warehouse":"自己店里/百鑫", "products":[{"name":"商品名","quantity":数量,"unit":"套/个/张/捆/斤"}]}
- purchase: 进货 → {"intent":"purchase", "warehouse":"百鑫/自己店里", "products":[{"name":"商品名","quantity":数量,"unit":"套/个/张/捆/斤"}]}
- transfer: 调拨 → {"intent":"transfer", "from":"自己店里/百鑫", "to":"自己店里/百鑫", "products":[{"name":"商品名","quantity":数量,"unit":"套/个/张/捆/斤","color":"颜色或空"}]}
- sales_query: 查询销售单/订单详情/客户最近做了什么 → {"intent":"sales_query", "customer":"客户名或关键词", "sales_id":销售单号或null, "count":最近几单或null}
- sales_manage: 管理销售单(删除/作废) → {"intent":"sales_manage", "action":"delete", "target":"single/multiple/customer_all/last_n", "customer":"客户名或null", "sales_ids":[], "count":null}
- customer_manage: 创建客户/添加客户档案 → {"intent":"customer_manage", "action":"create", "customer":"客户名或null", "contacts_name":"联系人或空", "contacts_tel":"电话或空"}
- series_manage: 管理1件起订/非1件起订系列 → {"intent":"series_manage", "action":"set_one_piece/set_non_one_piece/remove_non_one_piece/query", "series":["系列名"]}
- workflow: 工作流订单/设计稿订单 → 查询时 {"intent":"workflow", "action":"query", "keyword":"客户名或关键词", "count":最近几个或null, "order_id":单号或null}；创建时 {"intent":"workflow", "action":"create", "customer":"客户名", "goods_name":"商品名", "quantity":数量, "color":"颜色或空"}
- print: 打印销售单/客户最新订单 → {"intent":"print", "customer":"客户名或null", "sales_id":销售单号或null, "count":最近几个或null}
- knowledge: 礼盒、包装、商品、工艺、业务规则等资料库知识问答 → {"intent":"knowledge"}
- help: 询问北极星是谁、能做什么、是否支持某功能、机器人自身能力 → {"intent":"help"}
- chat: 闲聊/其他 → {"intent":"chat"}

注意：
1. 商品名去掉颜色和数量（如"岩味半斤红色1套"→商品名"岩味半斤"）
2. 数字量词转中文（如"3两"→"三两"，"2斤"→"二斤"）
3. 结合历史对话理解“他的呢”“最近3单呢”“这个单”等指代；如果上一轮刚查了某客户，用户问“最近3单呢”，沿用该客户并返回 sales_query/count=3
4. 如果用户明显换话题，不要沿用旧追问强行补参数
5. “你是谁”“你叫什么”“你会通知到企业微信吗”“你支持语音吗”“你能做什么”是机器人能力/身份问题，返回 help 或 chat，不要返回 knowledge
6. 只返回JSON，不要其他内容"""


def classify_and_extract(user_input: str, history: list[dict] | None = None) -> dict:
    """
    统一 LLM 调用：意图分类 + 参数提取（一次 LLM 调用）

    Returns:
        {"intent": "inventory", "product_name": "半斤", "color": "黄色"}
        intent 必定存在，其余字段取决于意图类型
    """
    learned = match_learned(user_input)
    if learned:
        return learned

    # 短回复（1-4字）且无明确意图时，看对话历史
    if len(user_input.strip()) <= 4 and history:
        last_assistant = ""
        for msg in reversed(history):
            if msg.get("role") == "assistant":
                last_assistant = msg.get("content", "")
                break
        if "仓库" in last_assistant and ("发货" in last_assistant or "自己店里" in last_assistant):
            return {"intent": "order"}
        if "确认" in last_assistant and ("下单" in last_assistant or "开单" in last_assistant):
            return {"intent": "order"}

    # 尝试 LLM 统一提取
    try:
        from src.core.llm import llm_json
        prompt = UNIFIED_PROMPT + get_prompt_examples()
        result = llm_json(prompt, user_input, history)
        intent = result.get("intent", "")
        if intent in VALID_INTENTS:
            logger.info(f"LLM 意图+参数: {intent} (输入: {user_input[:50]})")
            record_example(user_input, result, source="llm")
            return result
    except Exception as e:
        logger.warning(f"LLM 统一提取失败: {e}")

    # LLM 失败，回退正则（只有 intent，没有 params）
    intent = regex_classify_intent(user_input)
    logger.info(f"正则意图分类: {intent} (输入: {user_input[:50]})")
    return {"intent": intent}


# ---- 保留旧接口（兼容）----

def classify_intent(user_input: str, history: list[dict] | None = None) -> str:
    """意图分类（兼容旧调用）"""
    return classify_and_extract(user_input, history)["intent"]
