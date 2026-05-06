"""
库存决策节点（完整实现 - B4 规则）
严格按 order-flow SKILL.md B4 库存决策规则

规则：
B4.1 判断是否需要查库存
    - 不查库存类别（直接标记待开单）：泡袋/包茶/内衬/PVC/标签/纸箱/烫金泡袋/提袋UV/提袋丝印/烫膜
    - 礼盒类 → 继续 B4.2

B4.2 礼盒类库存决策
    - 百鑫有货 → 标记待开单（百鑫发货）
    - 百鑫无货/本店有货 → 必须询问调拨
    - 都没货 → 必须询问进货

B4.3 进货规则
    - 1件起订系列：件数 = ceil(订单数量 / 每件套数)
    - 非1件起：入库数量 = 订单数量

⚠️ 从自己店里发货必须先问用户确认！
"""
import math
from src.core.state import AgentState
from src.core.tools.caller import get_tool_caller
from src.utils import get_logger
from src.utils.formatters import fmt_inventory
from scripts.common.unit_converter import is_one_piece_order, calculate_purchase_quantity
from src.models.constants import NON_INVENTORY_CATEGORIES, GIFT_BOX_KEYWORDS

logger = get_logger("sjagent.nodes.inventory")


INVENTORY_KEYWORD_PROMPT = """你是肆计包装-北极星订单管理机器人，名字叫北极星。
用户想查库存或询问库存相关问题，请从输入中提取要查询的商品名称。

规则：
- 只返回商品名称，不要返回其他内容
- 如果用户说"查下喜悦库存"，返回"喜悦"
- 如果用户说"百鑫仓库还有什么货"，返回"全部"（表示查所有）
- 如果用户说"还有没有大吉礼盒"，返回"大吉礼盒"
- 如果用户说"库存够吗"或"还够吗"等追问，根据对话历史判断用户在问哪个商品，返回那个商品名
- 如果无法判断商品名，返回"未知"

请只返回商品名称，不要JSON，不要其他内容。"""


def _extract_inventory_keyword(user_input: str, state: AgentState) -> str:
    """用 LLM 从用户输入中提取库存查询的商品关键词"""
    # 先尝试正则快速提取
    import re
    keyword = re.sub(r'(查|下|一下|的?库存|还有.*货|有没有|还剩多少|帮我|请|帮忙)', '', user_input).strip()

    # 如果正则提取的结果太长、太短或明显不是商品名，用 LLM
    if len(keyword) > 10 or len(keyword) < 1 or keyword in ("够吗", "够不够", "怎么样", "多少"):
        try:
            from src.core.llm import llm_chat
            history = state.get("recent_turns", [])
            keyword = llm_chat(INVENTORY_KEYWORD_PROMPT, user_input, history).strip()
            # 去掉可能的引号
            keyword = keyword.strip('"\'「」')
            if keyword in ("未知", "全部", ""):
                keyword = keyword if keyword != "未知" else user_input
        except Exception as e:
            logger.warning(f"LLM 关键词提取失败: {e}")

    return keyword


def inventory_decision_node(state: AgentState) -> AgentState:
    """
    库存决策节点（完整实现）
    """
    state["node_name"] = "inventory_decision"

    caller = get_tool_caller()

    # 获取商品列表（来自 A 流程或 B 流程）
    order_items = state.get("order_items", [])
    image_parsed = state.get("image_parsed", [])
    product_warnings = state.get("product_warnings", [])

    # 统一商品列表
    products = []
    if image_parsed:
        for parsed in image_parsed:
            products.append({
                "product_name": parsed.get("goods_name", ""),
                "color": parsed.get("color", ""),
                "quantity": parsed.get("quantity", 1),
                "source": "image",
                "product_id": parsed.get("product_id"),
                "simple_desc": parsed.get("product_info", {}).get("simple_desc", "") if isinstance(parsed.get("product_info"), dict) else "",
            })
    elif order_items:
        products = order_items

    # 直接库存查询：从用户输入中提取关键词查询
    intent = state.get("intent", "")
    if not products and intent == "inventory_query":
        user_input = state.get("input", "")
        # 用 LLM 提取商品关键词
        keyword = _extract_inventory_keyword(user_input, state)
        if keyword:
            logger.info(f"直接库存查询，关键词: {keyword}")
            # 搜索商品
            search_results = caller.call("find_product_by_name", keyword=keyword)

            if search_results:
                # 查询每个商品的库存
                inventory_output = []
                for product in search_results[:5]:  # 最多查5个
                    pid = product.get("product_id") or product.get("id")
                    pname = product.get("title") or product.get("product_name", keyword)
                    if pid:
                        inv_results = caller.call("inventory_query_by_id", product_id=pid)
                        if inv_results:
                            inventory_output.append(f"【{pname}】")
                            for inv in inv_results:
                                warehouse = inv.get("【仓库】", "")
                                qty = inv.get("库存数量", 0)
                                inventory_output.append(f"  {warehouse}: {qty}")
                        else:
                            inventory_output.append(f"【{pname}】无库存记录")
                    else:
                        inventory_output.append(f"【{pname}】未找到商品ID")

                state["output"] = "库存查询结果：\n" + "\n".join(inventory_output)
            else:
                state["output"] = f'未找到与"{keyword}"相关的商品'

            state["pending_orders"] = []
            return state

    if not products:
        logger.info("无待处理商品")
        state["pending_orders"] = []
        return state

    # 库存决策
    pending_orders = []
    inventory_results = []
    need_transfer = False
    need_purchase = False
    confirmation_required = False
    confirmation_messages = []

    for p in products:
        product_name = p.get("product_name", "")
        color = p.get("color", "")
        order_qty = p.get("quantity", 1)
        product_id = p.get("product_id")
        simple_desc = p.get("simple_desc", "")

        # 1. 判断是否需要查库存
        is_gift_box = any(kw in product_name for kw in GIFT_BOX_KEYWORDS)
        is_non_inventory = any(kw in product_name for kw in NON_INVENTORY_CATEGORIES)

        if is_non_inventory or not is_gift_box:
            # 非礼盒类 → 直接待开单，百鑫发货
            pending_orders.append({
                "product_name": product_name,
                "color": color,
                "quantity": order_qty,
                "unit": p.get("unit", "个"),
                "product_id": product_id,
                "unit_id": p.get("unit_id", 1),
                "action": "direct",
                "warehouse_id": 2,  # 百鑫
                "note": "非礼盒类，直接开单",
            })
            logger.info(f"非礼盒类，直接待开单: {product_name}")
            continue

        # 2. 礼盒类 → 查库存
        if not product_id:
            pending_orders.append({
                "product_name": product_name,
                "color": color,
                "quantity": order_qty,
                "action": "product_not_found",
                "note": "商品未找到",
            })
            continue

        # 查库存
        inv_results = caller.call("inventory_query_by_id", product_id=product_id)
        inventory_results.append({
            "product_id": product_id,
            "product_name": product_name,
            "inventory": inv_results,
        })

        # 解析库存
        baixin_qty = 0
        self_qty = 0
        for inv in inv_results:
            warehouse = str(inv.get("【仓库】", ""))
            qty = int(inv.get("库存数量", 0) or 0)
            if "百鑫" in warehouse:
                baixin_qty = qty
            elif "自己" in warehouse or "店里" in warehouse:
                self_qty = qty

        # 3. 库存决策
        if baixin_qty >= order_qty:
            # 百鑫有货
            pending_orders.append({
                "product_name": product_name,
                "color": color,
                "quantity": order_qty,
                "unit": p.get("unit", "个"),
                "product_id": product_id,
                "unit_id": p.get("unit_id", 1),
                "action": "direct",
                "warehouse_id": 2,
                "note": "百鑫有货",
            })
            logger.info(f"百鑫有货，直接待开单: {product_name}, 库存={baixin_qty}")

        elif self_qty >= order_qty:
            # 百鑫无货，本店有货 → 必须询问调拨
            pending_orders.append({
                "product_name": product_name,
                "color": color,
                "quantity": order_qty,
                "unit": p.get("unit", "个"),
                "product_id": product_id,
                "unit_id": p.get("unit_id", 1),
                "action": "transfer",
                "warehouse_id": 1,  # 本店（需确认）
                "from_warehouse": 1,
                "to_warehouse": 2,
                "note": "本店有货，需调拨",
                "self_qty": self_qty,
            })
            need_transfer = True
            logger.info(f"本店有货，需调拨: {product_name}, 本店={self_qty}")

        else:
            # 都没货 → 进货
            per_piece = parse_per_piece(simple_desc)

            if is_one_piece_order(product_name):
                # 1件起订系列
                purchase_qty = math.ceil(order_qty / per_piece) if per_piece > 0 else order_qty
            else:
                # 非1件起
                purchase_qty = order_qty

            pending_orders.append({
                "product_name": product_name,
                "color": color,
                "quantity": order_qty,
                "unit": p.get("unit", "个"),
                "product_id": product_id,
                "unit_id": p.get("unit_id", 1),
                "action": "purchase",
                "warehouse_id": 2,
                "purchase_quantity": purchase_qty,
                "per_piece": per_piece,
                "note": f"需进货{purchase_qty}件",
            })
            need_purchase = True
            logger.info(f"需进货: {product_name}, 进货数量={purchase_qty}")

    # 4. 设置确认状态
    if product_warnings:
        confirmation_required = True
        confirmation_messages.append(
            "以下商品在数据库中未找到，请确认商品名称：\n" +
            "\n".join(f"- {w}" for w in product_warnings)
        )

    if need_transfer:
        confirmation_required = True
        confirmation_messages.append(
            "以下商品百鑫仓库无货，本店有货，需要调拨至百鑫仓库：\n" +
            "\n".join(
                f"- {o['product_name']} {o.get('color', '')} × {o['quantity']}（本店库存{o.get('self_qty', 0)}）"
                for o in pending_orders if o.get("action") == "transfer"
            )
        )

    if need_purchase:
        confirmation_required = True
        confirmation_messages.append(
            "以下商品各仓库均无货，需要进货：\n" +
            "\n".join(
                f"- {o['product_name']} {o.get('color', '')} × {o['quantity']}（需进{o['purchase_quantity']}件）"
                for o in pending_orders if o.get("action") == "purchase"
            )
        )

    state["inventory_results"] = inventory_results
    state["pending_orders"] = pending_orders
    state["need_transfer"] = need_transfer
    state["need_purchase"] = need_purchase
    state["confirmation_required"] = confirmation_required

    if confirmation_messages:
        state["confirmation_message"] = "\n\n".join(confirmation_messages)
        state["confirmed"] = False

    logger.info(
        f"库存决策完成：{len(pending_orders)} 个商品，"
        f"need_transfer={need_transfer}, need_purchase={need_purchase}"
    )
    return state


def parse_per_piece(simple_desc: str) -> int:
    """从 simple_desc 提取每件套数"""
    import re
    match = re.search(r"(\d+)\s*套\s*/\s*件", simple_desc)
    if match:
        return int(match.group(1))
    return 1
