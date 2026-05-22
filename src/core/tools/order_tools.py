"""Native order, workflow and print tools.

The tool names stay compatible with earlier agent flows, but every runtime
operation now goes through sjagent_core.
"""

from src.engine.native_db import get_native_db_client
from src.core.tools.registry import tool
from src.utils import get_logger

logger = get_logger("sjagent.tools.order")


def _native_db():
    return get_native_db_client()


@tool("workflow_order_save", "保存工作流订单")
def workflow_order_save(
    customer_name: str,
    goods_name: str,
    order_quantity: int,
    order_id: int = None,
    customer_phone: str = "",
    color: str = "",
    order_images: list[str] = None,
    is_screen_print: int = 0,
    order_type: int = 0,
    remark: str = "",
) -> dict:
    try:
        result = _native_db().save_workflow_order(
            order_id=order_id,
            customer_name=customer_name,
            customer_phone=customer_phone,
            goods_name=goods_name,
            order_quantity=order_quantity,
            color=color,
            order_images=order_images or [],
            is_screen_print=is_screen_print,
            order_type=order_type,
            remark=remark,
        )
        logger.info(f"native workflow order saved: goods_name={goods_name}, result={result}")
        return result
    except Exception as e:
        logger.error(f"native workflow order save failed: {e}")
        return {"error": str(e)}


@tool("workflow_order_list", "工作流订单列表")
def workflow_order_list(keyword: str = None, page: int = 1, page_size: int = 20) -> dict:
    try:
        cards, total = _native_db().workflow_orders(
            keyword=keyword or "",
            page=page,
            page_size=page_size,
            status_filter="all",
        )
        return {"code": 0, "data": {"list": cards, "total": total, "page": page, "page_size": page_size}}
    except Exception as e:
        logger.error(f"native workflow order list failed: {e}")
        return {"error": str(e)}


@tool("workflow_order_detail", "工作流订单详情")
def workflow_order_detail(order_id: int) -> dict:
    try:
        rows = _native_db().query(
            "SELECT * FROM workflow_order WHERE id=%s AND deleted_at IS NULL LIMIT 1",
            (order_id,),
        )
        if not rows:
            return {"code": 404, "msg": "工作流订单不存在"}
        return {"code": 0, "data": rows[0]}
    except Exception as e:
        logger.error(f"native workflow order detail failed: {e}")
        return {"error": str(e)}


@tool("workflow_order_delete", "删除工作流订单")
def workflow_order_delete(ids: str) -> dict:
    try:
        result = _native_db().delete_workflow_orders(ids)
        logger.info(f"native workflow order deleted: ids={ids}")
        return result
    except Exception as e:
        logger.error(f"native workflow order delete failed: {e}")
        return {"error": str(e)}


@tool("workflow_order_status_update", "更新工作流订单状态")
def workflow_order_status_update(order_id: int, field: str, value: int) -> dict:
    try:
        result = _native_db().update_workflow_status(order_id=order_id, field=field, value=value)
        logger.info(f"native workflow status updated: id={order_id}, field={field}, value={value}")
        return result
    except Exception as e:
        logger.error(f"native workflow status update failed: {e}")
        return {"error": str(e)}


@tool("sales_print_task", "创建销售单打印任务")
def sales_print_task(sales_id: int) -> dict:
    try:
        result = _native_db().create_sales_print_task(sales_id=sales_id)
        logger.info(f"native sales print task created: sales_id={sales_id}")
        return result
    except Exception as e:
        logger.error(f"native sales print task failed: {e}")
        return {"error": str(e)}


@tool("sales_print", "获取销售单打印数据")
def sales_print(sales_id: int) -> dict:
    try:
        return _native_db().sales_print_data(sales_id)
    except Exception as e:
        logger.error(f"native sales print data failed: {e}")
        return {"error": str(e)}


@tool("sales_history_price", "查询客户历史成交价")
def sales_history_price(customer_id: int, product_id: int) -> float | None:
    try:
        price = _native_db().sales_history_price(customer_id, product_id)
        if price:
            logger.info(f"native history price: customer_id={customer_id}, product_id={product_id}, price={price}")
        return price
    except Exception as e:
        logger.error(f"native history price failed: {e}")
        return None


@tool("get_product_price", "获取商品价格")
def get_product_price(product_id: int) -> float | None:
    try:
        return _native_db().get_product_price(product_id)
    except Exception as e:
        logger.error(f"native product price failed: {e}")
        return None


@tool("sales_print_task_list", "待打印任务列表")
def sales_print_task_list() -> dict:
    try:
        return _native_db().sales_print_task_list()
    except Exception as e:
        logger.error(f"native sales print task list failed: {e}")
        return {"error": str(e)}


@tool("sales_print_task_done", "标记打印完成")
def sales_print_task_done(task_id: int) -> dict:
    try:
        return _native_db().sales_print_task_done(task_id)
    except Exception as e:
        logger.error(f"native sales print task done failed: {e}")
        return {"error": str(e)}


@tool("purchase_add", "创建采购入库")
def purchase_add(company_id: int, products: list[dict], note: str = "") -> dict:
    try:
        warehouse_id = 2
        for item in products or []:
            if item.get("warehouse_id"):
                warehouse_id = int(item.get("warehouse_id"))
                break
        final_note = note or f"供应商#{company_id} 采购入库"
        return _native_db().create_stock_in(
            warehouse_id=warehouse_id,
            products=products,
            note=final_note,
        )
    except Exception as e:
        logger.error(f"native purchase stock-in failed: {e}")
        return {"error": str(e)}
