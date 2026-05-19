"""
标准下单工作流节点（完整实现 B 流程）
严格按 order-flow SKILL.md B 流程实现

流程：
B1. 接收资料（客户名称、商品名称/规格/数量）
B2. 查询信息（客户 + 商品）
    - 客户查询/新建
    - 商品查询/模糊匹配
    - 件套换算
B3. 烫金泡袋档位选择（仅烫金泡袋类）
B4. 库存决策（传递到 inventory_decision_node）
B5. 开单（传递到 executor_node）
"""
import re
from typing import Optional
from src.core.state import AgentState
from src.core.tools.caller import get_tool_caller
from src.core.llm import llm_json
from src.utils import get_logger
from src.core.customer_name import has_customer_name_craft_noise, normalize_customer_name
from src.core.product_matcher import ProductMatcher
from src.core.product_name import PRODUCT_SPECS, normalize_product_name
from scripts.common.unit_converter import (
    calculate_order_quantity,
    is_one_piece_order,
    calculate_purchase_quantity,
    parse_unit_from_simple_desc,
)
from scripts.common.color_filter import extract_color_from_text, filter_uv

logger = get_logger("sjagent.nodes.order_workflow")


# ---- LLM 订单解析 ----

ORDER_PARSE_PROMPT = """你是肆计包装-北极星订单管理机器人的订单解析器。
从用户输入中提取客户名称和订单商品列表。

业务背景：
- 这是一家茶包装公司，商品包括礼盒、泡袋、提袋、内衬等
- 常见单位：件、个、套、张、捆
- "件"是大单位，1件可能包含多套（如1件=20套）
- 用户可能用各种方式描述数量，如"3两"可能是"3件"的口语说法

请从用户输入中提取：
1. 客户名称（如果有）
2. 商品列表（商品名、数量、单位、颜色）

返回JSON格式：
{
  "customer": "客户名称（没有则为null）",
  "items": [
    {
      "product_name": "商品名称",
      "quantity": 数量（整数）,
      "unit": "件/个/套/张/捆",
      "color": "颜色（没有则为空字符串）"
    }
  ]
}

注意：
- 如果用户说"喜悦3两"，"两"可能是"件"的口语，unit应为"件"
- 如果用户说"标签2张"，unit应为"张"
- 如果用户说"10个泡袋"，unit应为"个"
- 商品名要尽量完整，如"喜悦三小盒"不要截断为"喜悦"
- 如果有多个商品用顿号、逗号或"和"分隔，都要提取出来"""


def llm_parse_order(user_input: str, history: list[dict] | None = None) -> tuple[Optional[str], list[dict]]:
    """
    用 LLM 解析订单

    Returns:
        (customer_name, items_list) 元组
        customer_name: 客户名称，没有则为 None
        items_list: [{"product_name": ..., "quantity": ..., "unit": ..., "color": ...}]
    """
    try:
        result = llm_json(ORDER_PARSE_PROMPT, user_input, history)
        customer = result.get("customer")
        items = result.get("items", [])

        # 验证和清洗
        valid_items = []
        for item in items:
            name = item.get("product_name", "").strip()
            qty = item.get("quantity", 0)
            unit = item.get("unit", "件")
            color = item.get("color", "")

            if not name or not isinstance(qty, (int, float)) or qty <= 0:
                continue

            valid_items.append({
                "product_name": name,
                "quantity": int(qty),
                "unit": unit,
                "color": color,
            })

        if not valid_items:
            return customer, []

        return customer, valid_items
    except Exception as e:
        logger.warning(f"LLM 订单解析失败: {e}")
        return None, []


# 烫金泡袋关键词
HOT_STAMP_KEYWORDS = ["烫金泡袋", "烫金", "泡袋烫金"]


def order_workflow_node(state: AgentState) -> AgentState:
    """
    标准下单工作流节点（完整实现）
    优先用 LLM 解析，失败时回退正则
    """
    user_input = state.get("input", "")
    state["node_name"] = "order_workflow"

    caller = get_tool_caller()
    product_matcher = ProductMatcher(caller)

    # 1. 用 LLM 解析客户和商品（传入对话历史）
    history = state.get("recent_turns", [])
    llm_customer, llm_items = llm_parse_order(user_input, history)

    if llm_items:
        # LLM 解析成功
        customer_name = llm_customer
        items = llm_items
        logger.info(f"LLM 订单解析成功: 客户={customer_name}, 商品数={len(items)}")
    else:
        # LLM 失败，回退正则
        logger.info("LLM 订单解析失败，回退正则")
        customer_name = extract_customer_name(user_input)
        items = parse_order_items(user_input)

    # 2. 解析客户名称
    customer_info = resolve_customer(customer_name, caller)
    state["customer_info"] = customer_info

    if not items:
        state["output"] = "未识别到商品信息，请说明商品名称和数量"
        return state

    # 3. 查询匹配商品
    matched_products = []
    product_warnings = []

    for item in items:
        product_name = item.get("product_name", "")
        color = item.get("color", "")
        if not color:
            color = extract_color_from_text(user_input) or ""
        color = filter_uv(color)

        match = product_matcher.match(
            product_name,
            color=color,
            use_inventory=True,
            allow_product_fallback=True,
            allow_llm=True,
        )

        if not match.product:
            product_warnings.append(f"商品未找到: {product_name}")
            matched_products.append({
                "product_name": product_name,
                "product_id": None,
                "product_warning": f"商品未找到: {product_name}",
                "quantity": item.get("quantity", 1),
                "unit": item.get("unit", "件"),
                "color": item.get("color", ""),
            })
            continue

        matched = match.product
        product_id = matched.get("id")

        # 查询完整商品信息
        product_detail = caller.call("product_info", product_id=product_id)

        # 件套换算
        order_qty = item.get("quantity", 1)
        unit = item.get("unit", "件")
        simple_desc = matched.get("simple_desc", "") or ""
        per_piece = parse_unit_from_simple_desc(simple_desc) or 1

        if unit == "件" and per_piece > 1:
            order_qty = calculate_order_quantity(
                user_reported=f"{order_qty}件",
                quantity=order_qty,
                simple_desc=simple_desc,
            )

        # 根据单位名称确定 unit_id
        unit_name_to_id = {"套": 1, "捆": 2, "个": 3, "斤": 4, "张": 5}
        unit_id = unit_name_to_id.get(unit, 1)

        matched_products.append({
            "product_id": product_id,
            "product_name": matched.get("title", product_name),
            "color": color or matched.get("spec", ""),
            "quantity": order_qty,
            "unit": unit,
            "simple_desc": simple_desc,
            "per_piece": per_piece,
            "unit_id": unit_id,
            "price": matched.get("price"),
            "product_detail": product_detail,
        })

    state["order_items"] = matched_products
    state["product_warnings"] = product_warnings if product_warnings else None

    # 4. 烫金泡袋档位处理（仅烫金泡袋类）
    hot_stamp_choices = handle_hot_stamp(user_input, matched_products, caller)
    if hot_stamp_choices:
        state["hot_stamp_choices"] = hot_stamp_choices

    logger.info(
        f"标准下单解析：客户={customer_name}，商品数={len(matched_products)}，"
        f"警告={len(product_warnings)}"
    )
    return state


def resolve_customer(customer_name: str, caller) -> dict:
    """
    解析客户：
    1. 客户已存在 → 返回已有客户信息
    2. 客户不存在 → 自动创建并返回新客户信息
    """
    customer_name = normalize_customer_name(customer_name)
    if not customer_name:
        # 无客户名 → 散客
        return {"name": "散客", "customer_id": 1}

    # 查询客户
    customers = caller.call("customer_query", keyword=customer_name)

    exact_customers = []
    fuzzy_customers = []
    for row in customers or []:
        row_name = str(row.get("name") or row.get("customer_name") or row.get("company_name") or "").strip()
        if row_name == customer_name:
            exact_customers.append(row)
        elif customer_name in row_name and not has_customer_name_craft_noise(row_name):
            fuzzy_customers.append(row)

    picked_customers = exact_customers or (fuzzy_customers[:1] if len(fuzzy_customers) == 1 else [])
    if picked_customers:
        # 客户已存在
        c = picked_customers[0]
        return {
            "name": customer_name,
            "customer_id": c.get("id"),
            "contacts_tel": c.get("contacts_tel", ""),
        }
    else:
        # 客户不存在，自动创建
        result = caller.call("customer_create", name=customer_name)
        if result and result.get("data"):
            new_id = result["data"]
            logger.info(f"自动创建客户: {customer_name}, id={new_id}")
            return {
                "name": customer_name,
                "customer_id": new_id,
            }
        else:
            logger.warning(f"客户创建失败: {customer_name}, result={result}")
            return {
                "name": customer_name,
                "customer_id": None,
                "need_create": True,
            }


def extract_customer_name(text: str) -> Optional[str]:
    """从文本中提取客户名称"""
    patterns = [
        r"客户[：:]\s*([^\s，,。!?]+)",
        r"给\s*([^\s，,。!?]+)\s*(?:做|订|开|拿|送)",
        r"([^\s，,。!?]+)\s*(?:要|订|做|拿|送)",
        r"([^\s，,。!?]+)\s*(?:的|这位)\s*(?:客户|老板)",
        # 格式：客户名 + 商品信息 + 下单/开单
        r"^([^\s，,。!?]+)\s+.*(?:下单|开单)",
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            name = m.group(1).strip()
            # 排除商品关键词
            goods_keywords = ["礼盒", "泡袋", "提袋", "内衬", "盒", "件", "个"]
            if name not in goods_keywords:
                return name
    return None


def parse_order_items(text: str) -> list[dict]:
    """
    从文本中解析订单商品列表
    支持格式：
    - "1件喜悦三小盒"
    - "3个泡袋"
    - "5套内衬袋"
    - "喜悦三小盒 咖色 1件"
    - "银茗要1件喜悦三小盒、3个泡袋"
    """
    items = []

    # 匹配模式：优先商品名+数量，再数量+商品名
    patterns = [
        # 商品名 + X件/个/套/张/捆（优先匹配）
        r"([^\s，,。!?]+?)\s*(\d+)\s*件",
        r"([^\s，,。!?]+?)\s*(\d+)\s*个",
        r"([^\s，,。!?]+?)\s*(\d+)\s*套",
        r"([^\s，,。!?]+?)\s*(\d+)\s*张",
        r"([^\s，,。!?]+?)\s*(\d+)\s*捆",
        # X件 + 商品名
        r"(\d+)\s*件\s*([^\s，,。!?]+?(?:礼盒|泡袋|提袋|内衬|PVC|盒))",
        # X个 + 商品名
        r"(\d+)\s*个\s*([^\s，,。!?]+?(?:礼盒|泡袋|提袋|内衬|PVC|盒))",
        # X套 + 商品名
        r"(\d+)\s*套\s*([^\s，,。!?]+?(?:礼盒|泡袋|提袋|内衬|PVC|盒))",
        # X张 + 商品名
        r"(\d+)\s*张\s*([^\s，,。!?]+)",
        # X捆 + 商品名
        r"(\d+)\s*捆\s*([^\s，,。!?]+)",
    ]

    found_spans = []

    for i, pattern in enumerate(patterns):
        for m in re.finditer(pattern, text):
            start, end = m.span()
            if any(start < s[1] and end > s[0] for s in found_spans):
                continue
            found_spans.append((start, end))

            # 前5个模式：group(1)=商品名, group(2)=数量
            # 后5个模式：group(1)=数量, group(2)=商品名
            if i < 5:
                product_raw = m.group(1).strip()
                qty = int(m.group(2))
            else:
                qty = int(m.group(1))
                product_raw = m.group(2).strip()

            # 提取数量单位
            unit = "件"
            match_text = m.group(0)
            if "个" in match_text:
                unit = "个"
            elif "套" in match_text:
                unit = "套"
            elif "张" in match_text:
                unit = "张"
            elif "捆" in match_text:
                unit = "捆"

            # 提取颜色（从商品描述中）
            color = extract_color_from_text(product_raw) or ""

            items.append({
                "product_name": product_name_normalize(product_raw),
                "quantity": qty,
                "unit": unit,
                "color": color,
            })

    # 去重（按商品名称）
    seen = set()
    unique_items = []
    for item in items:
        key = item["product_name"]
        if key not in seen:
            seen.add(key)
            unique_items.append(item)

    return unique_items


def product_name_normalize(name: str) -> str:
    """标准化商品名称"""
    # 去除多余空格
    name = normalize_product_name(" ".join(str(name or "").split()), specs=PRODUCT_SPECS)

    # 去除常见前缀
    for prefix in ["要", "订", "做", "拿"]:
        if name.startswith(prefix):
            name = name[1:].strip()

    return name


def handle_hot_stamp(user_input: str, products: list[dict], caller) -> dict | None:
    """
    处理烫金泡袋档位选择
    仅烫金泡袋类执行此步骤

    规则（order-flow B3）：
    - 厂里烫金泡袋：选最接近档位，数量用客户实际数量
    - 小机器烫金泡袋：
      - ≥500个 + 单面 → 大量单面
      - <500个 + 单面 → 单面
      - ≥500个 + 双面 → 大量双面
      - <500个 + 双面 → 双面
    """
    # 检测是否包含烫金泡袋
    is_hot_stamp = any(
        any(kw in p.get("product_name", "") for kw in HOT_STAMP_KEYWORDS)
        for p in products
    )

    if not is_hot_stamp:
        return None

    # 解析数量和单双面
    quantity = 0
    for p in products:
        if any(kw in p.get("product_name", "") for kw in HOT_STAMP_KEYWORDS):
            quantity = p.get("quantity", 0)
            break

    # 检测单双面
    is_double_side = "双面" in user_input
    is_single_side = "单面" in user_input

    if is_double_side or is_single_side:
        # 小机器烫金泡袋
        if is_double_side:
            if quantity >= 500:
                choice = "大量双面"
            else:
                choice = "双面"
        else:
            if quantity >= 500:
                choice = "大量单面"
            else:
                choice = "单面"

        return {
            "type": "small_machine",
            "choice": choice,
            "quantity": quantity,
        }

    # 厂里烫金泡袋 → 选最接近档位
    # 档位：5000/3000/2000/1000
    return {
        "type": "factory",
        "quantity": quantity,
    }
