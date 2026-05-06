"""
业务执行节点（完整实现）
执行业务操作：进货、调拨、开销售单
按 order-flow B4.3 规则输出进货汇总
"""
from src.core.state import AgentState
from src.core.config import get_config
from src.core.tools.caller import get_tool_caller
from src.utils import get_logger
from src.models.constants import (
    CUSTOMER_DEFAULT, WAREHOUSE_SELF, WAREHOUSE_BAIXIN,
    TRANSFER_FROM, TRANSFER_TO, DEFAULT_WAREHOUSE,
)

logger = get_logger("sjagent.nodes.executor")


def executor_node(state: AgentState) -> AgentState:
    """
    业务执行节点（完整实现）

    按 order-flow B4 库存决策后的执行：
    1. 处理进货（OtherEnterAdd）
    2. 处理调拨（InventoryTransfer）
    3. 统一开单（SalesAdd 一次性包含所有待开单商品）
    4. 自动打印（齐唯茶叶 customer_id=1）
    """
    state["node_name"] = "executor"

    caller = get_tool_caller()
    config = get_config()

    pending = state.get("pending_orders", [])
    if not pending:
        logger.info("没有待执行的订单")
        return state

    results = {
        "purchase": [],   # 进货结果
        "transfer": [],  # 调拨结果
        "sales": [],     # 开单结果
        "errors": [],    # 错误列表
    }

    # 1. 先处理进货（所有需要进货的商品）
    purchase_orders = [p for p in pending if p.get("action") == "purchase"]
    if purchase_orders:
        for order in purchase_orders:
            r = execute_purchase(caller, order)
            if r.get("error"):
                results["errors"].append(f"进货失败: {order.get('product_name')}, {r['error']}")
            else:
                results["purchase"].append({
                    **order,
                    "purchase_id": r.get("data"),
                })
                logger.info(f"进货成功: {order.get('product_name')}, 数量={order.get('purchase_quantity')}")

    # 2. 处理调拨（所有需要调拨的商品）
    transfer_orders = [p for p in pending if p.get("action") == "transfer"]
    if transfer_orders:
        for order in transfer_orders:
            r = execute_transfer(caller, order)
            if r.get("error"):
                results["errors"].append(f"调拨失败: {order.get('product_name')}, {r['error']}")
            else:
                results["transfer"].append({
                    **order,
                    "transfer_id": r.get("data"),
                })
                logger.info(f"调拨成功: {order.get('product_name')}")

    # 3. 收集待开单商品（所有 action != product_not_found 的商品）
    direct_orders = [p for p in pending if p.get("action") in ("direct", "purchase", "transfer")]

    if direct_orders:
        # 查价格并组装开单数据
        sales_items = []
        for order in direct_orders:
            product_id = order.get("product_id")
            if not product_id:
                continue

            # 查价格（优先客户历史价）
            customer_info = state.get("customer_info", {})
            customer_id = customer_info.get("customer_id", CUSTOMER_DEFAULT)

            price = get_price(caller, customer_id, product_id)

            sales_items.append({
                "product_id": product_id,
                "unit_id": order.get("unit_id", 1),
                "warehouse_id": order.get("warehouse_id", 2),
                "buy_number": order.get("quantity", 1),
                "price": price,
                "product_name": order.get("product_name", ""),
                "color": order.get("color", ""),
            })

        # 合并同商品+颜色的多数量
        sales_items = merge_sales_items(sales_items)

        # 开单
        if sales_items:
            r = execute_sales(caller, state, sales_items)
            if r.get("error"):
                results["errors"].append(f"开单失败: {r['error']}")
            else:
                sales_id = r.get("data") or r.get("sales_id")
                results["sales"].append({
                    "sales_id": sales_id,
                    "sales_no": r.get("sales_no", ""),
                    "items": sales_items,
                })
                logger.info(f"开单成功: sales_id={sales_id}")

                # 自动打印（齐唯茶叶 customer_id=1）
                if customer_id == config.qiwu_tea_id:
                    if sales_id:
                        try:
                            caller.call("sales_print_task", sales_id=sales_id)
                            logger.info(f"自动打印任务创建: sales_id={sales_id}")
                        except Exception as e:
                            logger.warning(f"自动打印失败: {e}")

    # 保存结果
    state["purchase_results"] = results["purchase"]
    state["transfer_results"] = results["transfer"]
    state["sales_results"] = results["sales"]
    state["execution_errors"] = results["errors"]

    logger.info(
        f"业务执行完成：进货={len(results['purchase'])}, "
        f"调拨={len(results['transfer'])}, 开单={len(results['sales'])}, "
        f"错误={len(results['errors'])}"
    )
    return state


def execute_purchase(caller, order: dict) -> dict:
    """执行进货入库"""
    try:
        return caller.call(
            "other_enter_add",
            warehouse_id=WAREHOUSE_BAIXIN,
            products=[{
                "product_id": order.get("product_id"),
                "unit_id": order.get("unit_id", 1),
                "buy_number": order.get("purchase_quantity", order.get("quantity")),
            }],
            note="智能体进货",
        )
    except Exception as e:
        return {"error": str(e)}


def execute_transfer(caller, order: dict) -> dict:
    """执行调拨"""
    try:
        return caller.call(
            "inventory_transfer",
            out_warehouse_id=order.get("from_warehouse", TRANSFER_FROM),
            enter_warehouse_id=order.get("to_warehouse", TRANSFER_TO),
            products=[{
                "product_id": order.get("product_id"),
                "unit_id": order.get("unit_id", 1),
                "transfer_number": order.get("quantity"),
            }],
            note="智能体调拨",
        )
    except Exception as e:
        return {"error": str(e)}


def execute_sales(caller, state: AgentState, sales_items: list[dict]) -> dict:
    """执行销售单开单"""
    try:
        customer_info = state.get("customer_info", {})
        customer_id = customer_info.get("customer_id") or CUSTOMER_DEFAULT

        # 转换为 API 格式
        products = []
        for item in sales_items:
            products.append({
                "product_id": item["product_id"],
                "unit_id": item["unit_id"],
                "warehouse_id": item["warehouse_id"],
                "buy_number": item["buy_number"],
                "price": item.get("price"),
            })

        result = caller.call(
            "sales_add",
            customer_id=customer_id,
            warehouse_id=WAREHOUSE_BAIXIN,
            products=products,
        )

        # 统一响应格式：确保 sales_id 和 sales_no 字段存在
        if "sales_id" not in result and "data" in result:
            result["sales_id"] = result["data"]
        if "sales_no" not in result:
            result["sales_no"] = ""

        return result
    except Exception as e:
        return {"error": str(e)}


def get_price(caller, customer_id: int, product_id: int) -> float | None:
    """获取商品价格（优先客户历史价）"""
    try:
        # 优先查客户历史成交价
        history_price = caller.call("sales_history_price", customer_id=customer_id, product_id=product_id)
        if history_price:
            return history_price
    except Exception:
        pass

    try:
        # 查不到则用零售价
        price = caller.call("get_product_price", product_id=product_id)
        return price
    except Exception:
        return None


def merge_sales_items(items: list[dict]) -> list[dict]:
    """
    合并同商品+颜色的多数量
    用于多订单合并开单
    """
    merged = {}

    for item in items:
        key = (item.get("product_id"), item.get("color", ""))
        if key in merged:
            merged[key]["buy_number"] += item.get("buy_number", 1)
            # 保留最新价格（如有）
            if item.get("price") is not None:
                merged[key]["price"] = item["price"]
        else:
            merged[key] = dict(item)

    return list(merged.values())
