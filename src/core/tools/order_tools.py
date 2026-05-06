"""
订单工具 - 工作流订单、销售单、打印相关操作
"""
from src.engine.api_client import ERPSystemClient
from src.engine.db_client import get_db_client
from src.core.tools.registry import tool
from src.utils import get_logger

logger = get_logger("sjagent.tools.order")


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
    """
    创建工作流订单

    Args:
        customer_name: 客户名称
        goods_name: 商品名称（用数据库标准值）
        order_quantity: 订单数量
        color: 颜色
        order_images: 图片URL列表
        is_screen_print: 是否丝印（0/1）
        remark: 备注
    """
    client = ERPSystemClient()
    try:
        result = client.workflow_order_save(
            order_id=order_id,
            customer_name=customer_name,
            customer_phone=customer_phone,
            goods_name=goods_name,
            order_quantity=order_quantity,
            goods_color=color,
            order_images=order_images or [],
            is_screen_print=is_screen_print,
            order_type=order_type,
            remark=remark,
        )
        logger.info(f"工作流订单创建: goods_name={goods_name}, result={result}")
        return result
    except Exception as e:
        logger.error(f"工作流订单创建失败: {e}")
        return {"error": str(e)}


@tool("workflow_order_list", "工作流订单列表")
def workflow_order_list(
    keyword: str = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """查询工作流订单列表"""
    client = ERPSystemClient()
    try:
        return client.workflow_order_list(keyword=keyword, page=page, page_size=page_size)
    except Exception as e:
        logger.error(f"工作流订单列表查询失败: {e}")
        return {"error": str(e)}


@tool("workflow_order_detail", "工作流订单详情")
def workflow_order_detail(order_id: int) -> dict:
    """查询工作流订单详情"""
    client = ERPSystemClient()
    try:
        return client.workflow_order_detail(order_id)
    except Exception as e:
        logger.error(f"工作流订单详情查询失败: {e}")
        return {"error": str(e)}


@tool("workflow_order_delete", "删除工作流订单")
def workflow_order_delete(ids: str) -> dict:
    """
    删除工作流订单

    Args:
        ids: 工作流订单ID（多个用逗号分隔）
    """
    client = ERPSystemClient()
    try:
        result = client.workflow_order_delete(ids=ids)
        logger.info(f"工作流订单删除: ids={ids}")
        return result
    except Exception as e:
        logger.error(f"工作流订单删除失败: {e}")
        return {"error": str(e)}


@tool("workflow_order_status_update", "更新工作流订单状态")
def workflow_order_status_update(order_id: int, field: str, value: int) -> dict:
    """
    更新工作流订单状态。

    Args:
        order_id: 工作流订单ID
        field: is_made/is_delivered/order_type
        value: 0/1，order_type 可为 0/1/2
    """
    client = ERPSystemClient()
    try:
        result = client.workflow_order_status_update(order_id=order_id, field=field, value=value)
        logger.info(f"工作流订单状态更新: id={order_id}, field={field}, value={value}")
        return result
    except Exception as e:
        logger.error(f"工作流订单状态更新失败: {e}")
        return {"error": str(e)}


@tool("sales_print_task", "创建打印任务")
def sales_print_task(sales_id: int) -> dict:
    """
    为销售单创建打印任务

    Args:
        sales_id: 销售单ID
    """
    client = ERPSystemClient()
    try:
        result = client.sales_print_task(sales_id=sales_id)
        logger.info(f"打印任务创建: sales_id={sales_id}")
        return result
    except Exception as e:
        logger.error(f"打印任务创建失败: {e}")
        return {"error": str(e)}


@tool("sales_print", "获取销售单打印数据")
def sales_print(sales_id: int) -> dict:
    """获取销售单打印数据"""
    client = ERPSystemClient()
    try:
        return client.sales_print(sales_id)
    except Exception as e:
        logger.error(f"获取打印数据失败: {e}")
        return {"error": str(e)}


@tool("sales_history_price", "查询客户历史成交价")
def sales_history_price(customer_id: int, product_id: int) -> float | None:
    """
    查询客户对某商品的历史成交价

    Returns:
        历史成交价，未查到返回 None
    """
    db = get_db_client()
    try:
        # 查数据库获取历史价格
        sql = """
        SELECT sd.price
        FROM sxo_plugins_erp_sales_detail sd
        JOIN sxo_plugins_erp_sales s ON s.id = sd.sales_id
        WHERE s.customer_id = %s AND sd.product_id = %s
        ORDER BY s.add_time DESC
        LIMIT 1
        """
        rows = db.query(sql, (customer_id, product_id))
        if rows and rows[0].get("price"):
            price = float(rows[0]["price"])
            logger.info(f"历史价格: customer_id={customer_id}, product_id={product_id}, price={price}")
            return price
        return None
    except Exception as e:
        logger.error(f"历史价格查询失败: {e}")
        return None


@tool("get_product_price", "获取商品价格")
def get_product_price(product_id: int) -> float | None:
    """
    获取商品零售价（price字段，不是 retail_price）

    Returns:
        价格，未查到返回 None
    """
    db = get_db_client()
    try:
        info = db.get_product_info(product_id)
        if info and info.get("price"):
            return float(info["price"])
        return None
    except Exception as e:
        logger.error(f"商品价格查询失败: {e}")
        return None


@tool("sales_print_task_list", "待打印任务列表")
def sales_print_task_list() -> dict:
    """查询待打印任务列表"""
    client = ERPSystemClient()
    try:
        return client.sales_print_task_list()
    except Exception as e:
        logger.error(f"待打印任务列表查询失败: {e}")
        return {"error": str(e)}


@tool("sales_print_task_done", "标记打印完成")
def sales_print_task_done(task_id: int) -> dict:
    """标记打印任务已完成"""
    client = ERPSystemClient()
    try:
        return client.sales_print_task_done(task_id)
    except Exception as e:
        logger.error(f"标记打印完成失败: {e}")
        return {"error": str(e)}


@tool("purchase_add", "创建采购单")
def purchase_add(
    company_id: int,
    products: list[dict],
    note: str = "",
) -> dict:
    """
    创建采购单

    Args:
        company_id: 供应商ID
        products: [{"product_id": X, "unit_id": 1, "buy_number": Y, "price": Z}, ...]
        note: 备注
    """
    client = ERPSystemClient()
    try:
        return client.purchase_add(company_id=company_id, products=products, note=note)
    except Exception as e:
        logger.error(f"采购单创建失败: {e}")
        return {"error": str(e)}
