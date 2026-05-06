"""
确认节点 - 高危操作/本店发货必须确认
按 order-flow 规则：
- 本店发货（warehouse_id=1）必须先问用户确认
- 商品未找到（product_warning）必须先问用户确认
- 需要调拨/进货必须先问用户确认
- 删除订单等高危操作必须先问用户确认
"""
from src.core.state import AgentState
from src.models.constants import WAREHOUSE_SELF
from src.utils import get_logger

logger = get_logger("sjagent.nodes.confirmation")


def confirmation_node(state: AgentState) -> AgentState:
    """
    确认节点
    检查是否需要用户确认，如果需要则设置 confirmation_required=True
    实际等待用户回复 confirmed=True/False 由上层处理
    """
    state["node_name"] = "confirmation"

    # 如果上游已设置 confirmation_required，则使用上游的值
    if state.get("confirmation_required") is True:
        # 确保有确认消息
        if not state.get("confirmation_message"):
            state["confirmation_message"] = build_default_confirmation_message(state)
        logger.info("需要用户确认")
        return state

    # 主动检查是否需要确认
    needs_confirm, message = should_confirm(state)

    state["confirmation_required"] = needs_confirm
    if needs_confirm:
        state["confirmation_message"] = message
        state["confirmed"] = False
    else:
        state["confirmed"] = True

    return state


def should_confirm(state: AgentState) -> tuple[bool, str]:
    """
    判断是否需要用户确认

    Returns:
        (是否需要确认, 确认消息)
    """
    messages = []

    # 1. 商品未找到警告
    product_warnings = state.get("product_warnings", [])
    if product_warnings:
        messages.append(
            "⚠️ 以下商品在数据库中未找到，请确认商品名称：\n" +
            "\n".join(f"- {w}" for w in product_warnings) +
            "\n\n请回复正确的商品名称，或回复【取消】"
        )

    # 2. 本店发货（warehouse_id=1）
    pending_orders = state.get("pending_orders", [])
    self_delivery = [o for o in pending_orders if o.get("warehouse_id") == WAREHOUSE_SELF]
    if self_delivery:
        items_text = "\n".join(
            f"- {o.get('product_name', '')} {o.get('color', '')} × {o.get('quantity', '')}"
            for o in self_delivery
        )
        messages.append(
            f"⚠️ 以下商品将从【自己店里】发货，是否确认？\n{items_text}\n\n请回复【确认】或【取消】"
        )

    # 3. 需要调拨
    if state.get("need_transfer"):
        transfer_orders = [o for o in pending_orders if o.get("action") == "transfer"]
        if transfer_orders:
            items_text = "\n".join(
                f"- {o.get('product_name', '')} {o.get('color', '')} × {o.get('quantity', '')}"
                for o in transfer_orders
            )
            messages.append(
                f"⚠️ 以下商品需要从【自己店里】调拨至【百鑫仓库】，是否继续？\n{items_text}\n\n请回复【确认】或【取消】"
            )

    # 4. 需要进货
    if state.get("need_purchase"):
        purchase_orders = [o for o in pending_orders if o.get("action") == "purchase"]
        if purchase_orders:
            items_text = "\n".join(
                f"- {o.get('product_name', '')} {o.get('color', '')} × {o.get('quantity', '')}（需进{o.get('purchase_quantity', '')}件）"
                for o in purchase_orders
            )
            messages.append(
                f"⚠️ 以下商品需要进货，是否继续？\n{items_text}\n\n请回复【确认】或【取消】"
            )

    if messages:
        return True, "\n\n".join(messages)

    return False, ""


def build_default_confirmation_message(state: AgentState) -> str:
    """构建默认确认消息"""
    pending_orders = state.get("pending_orders", [])

    if not pending_orders:
        return "请确认是否继续操作？"

    lines = ["请确认以下操作："]
    for o in pending_orders:
        action = o.get("action", "direct")
        name = o.get("product_name", "")
        color = o.get("color", "")
        qty = o.get("quantity", "")

        if action == "direct":
            lines.append(f"  ✅ 开单：{name} {color} × {qty}")
        elif action == "transfer":
            lines.append(f"  🔄 调拨：{name} {color} × {qty}")
        elif action == "purchase":
            lines.append(f"  📦 进货：{name} {color} × {qty}（需进{o.get('purchase_quantity', '')}件）")
        elif action == "product_not_found":
            lines.append(f"  ⚠️ 商品未找到：{name}")

    lines.append("")
    lines.append("请回复【确认】或【取消】")

    return "\n".join(lines)
