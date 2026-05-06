"""
数据库工具 - MySQL 直查封装
库存查询 SQL 严格按 order-flow 规范
"""
import re
from src.engine.db_client import get_db_client
from src.core.tools.registry import tool
from src.utils import get_logger

logger = get_logger("sjagent.tools.db")


@tool("db_query", "执行SQL查询")
def db_query(sql: str, params: tuple = None) -> list[dict]:
    """
    执行 SQL 查询（仅限 SELECT）

    Args:
        sql: SQL 语句
        params: 参数元组

    Returns:
        查询结果列表
    """
    # 安全检查：只允许 SELECT
    sql_upper = sql.strip().upper()
    if not sql_upper.startswith("SELECT"):
        logger.warning(f"禁止执行非查询SQL: {sql[:50]}")
        from src.engine.exceptions import ToolError
        raise ToolError("只允许 SELECT 查询")

    db = get_db_client()
    try:
        results = db.query(sql, params)
        logger.info(f"SQL查询: {sql[:80]}, 返回{len(results)}条")
        return results
    except Exception as e:
        logger.error(f"SQL查询失败: {e}")
        return [{"error": str(e)}]


@tool("get_unit_list", "查询单位列表")
def get_unit_list() -> list[dict]:
    """
    查询计量单位表
    unit_id=1 是「套」，unit_id=3 是「个」，unit_id=5 是「张」
    """
    db = get_db_client()
    sql = "SELECT id, name FROM sxo_plugins_erp_unit"
    try:
        results = db.query(sql)
        logger.info(f"单位列表查询: 返回{len(results)}条")
        return results
    except Exception as e:
        logger.error(f"单位列表查询失败: {e}")
        return []


@tool("get_warehouse_list", "查询仓库列表")
def get_warehouse_list() -> list[dict]:
    """
    查询仓库列表
    返回: [{"id": 1, "name": "自己店里"}, {"id": 2, "name": "百鑫仓库"}]
    """
    client_db = get_db_client()
    sql = "SELECT id, name FROM sxo_plugins_erp_warehouse WHERE is_enable = 1"
    try:
        results = client_db.query(sql)
        logger.info(f"仓库列表查询: 返回{len(results)}条")
        return results
    except Exception as e:
        logger.error(f"仓库列表查询失败: {e}")
        return []


@tool("inventory_query_format", "格式化库存查询")
def inventory_query_format(product_id: int) -> str:
    """
    查询库存并格式化为标准输出
    输出格式：产品名称 | 【颜色】 | 【仓库】 | 库存数量

    这是库存查询的标准入口，优先使用此方法
    """
    db = get_db_client()
    sql = """
    SELECT
        p.title AS 产品名称,
        p.spec AS `【颜色】`,
        w.name AS `【仓库】`,
        wi.inventory AS 库存数量
    FROM sxo_plugins_erp_warehouse_product_inventory wi
    JOIN sxo_plugins_erp_product p ON p.id = wi.product_id
    JOIN sxo_plugins_erp_warehouse w ON w.id = wi.warehouse_id
    WHERE wi.product_id = %s
    ORDER BY w.id
    """
    try:
        results = db.query(sql, (product_id,))
        if not results:
            return f"product_id={product_id} 未查到库存数据"

        lines = []
        for r in results:
            lines.append(
                f"{r['产品名称']} | 【{r['【颜色】']}】 | 【{r['【仓库】']}】 | {r['库存数量']}"
            )
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"库存查询格式化失败: {e}")
        return f"库存查询失败: {e}"


@tool("find_product_by_name", "按名称查商品ID和规格")
def find_product_by_name(keyword: str) -> list[dict]:
    """
    按名称模糊搜索商品，返回商品ID和颜色规格

    Returns:
        [{"id": ..., "title": ..., "spec": ..., "simple_desc": ...}]
    """
    db = get_db_client()
    sql = """
    SELECT id, title, spec, simple_desc
    FROM sxo_plugins_erp_product
    WHERE title LIKE %s
    LIMIT 20
    """
    try:
        results = db.query(sql, (f"%{keyword}%",))
        logger.info(f"商品查找: keyword={keyword}, 结果={len(results)}条")
        return results
    except Exception as e:
        logger.error(f"商品查找失败: {e}")
        return []


@tool("get_simple_desc", "获取商品simple_desc字段")
def get_simple_desc(product_id: int) -> str | None:
    """
    获取商品的 simple_desc 字段，用于件套换算

    Returns:
        simple_desc 值，如 "规格:28套/件"
    """
    db = get_db_client()
    sql = "SELECT simple_desc FROM sxo_plugins_erp_product WHERE id = %s"
    try:
        results = db.query(sql, (product_id,))
        if results:
            return results[0].get("simple_desc")
        return None
    except Exception as e:
        logger.error(f"simple_desc查询失败: {e}")
        return None
