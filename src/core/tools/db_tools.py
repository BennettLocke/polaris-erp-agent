"""Native database read tools.

This module keeps the old tool names for agent compatibility, but runtime
queries now read sjagent_core through NativeDBClient instead of ShopXO/ERP
tables.
"""

from src.core.tools.registry import tool
from src.engine.exceptions import ToolError
from src.engine.native_db import get_native_db_client
from src.utils import get_logger

logger = get_logger("sjagent.tools.db")


def _native_db():
    return get_native_db_client()


@tool("db_query", "执行自有库 SELECT 查询")
def db_query(sql: str, params: tuple = None) -> list[dict]:
    """Execute a SELECT query against sjagent_core."""
    sql_upper = sql.strip().upper()
    if not sql_upper.startswith("SELECT"):
        logger.warning(f"blocked non-SELECT SQL: {sql[:80]}")
        raise ToolError("只允许 SELECT 查询")
    forbidden_tokens = (" SLEEP(", " INTO OUTFILE", " LOAD_FILE(", " INFORMATION_SCHEMA.", " MYSQL.")
    if any(token in sql_upper for token in forbidden_tokens):
        logger.warning(f"blocked unsafe SELECT SQL: {sql[:80]}")
        raise ToolError("该查询不允许执行")
    try:
        results = _native_db().query(sql, params)
        logger.info(f"native SQL query returned {len(results)} rows")
        return results
    except Exception as e:
        logger.error(f"native SQL query failed: {e}")
        return [{"error": str(e)}]


@tool("get_unit_list", "查询单位列表")
def get_unit_list() -> list[dict]:
    """Return enabled product units from sjagent_core."""
    try:
        rows = _native_db().query(
            "SELECT id, name, code FROM product_unit WHERE is_enabled=1 ORDER BY id ASC"
        )
        logger.info(f"native unit list returned {len(rows)} rows")
        return rows
    except Exception as e:
        logger.error(f"native unit list failed: {e}")
        return []


@tool("get_warehouse_list", "查询仓库列表")
def get_warehouse_list() -> list[dict]:
    """Return enabled warehouses from sjagent_core."""
    try:
        rows = _native_db().warehouse_list()
        logger.info(f"native warehouse list returned {len(rows)} rows")
        return rows
    except Exception as e:
        logger.error(f"native warehouse list failed: {e}")
        return []


@tool("inventory_query_format", "格式化库存查询")
def inventory_query_format(product_id: int) -> str:
    """Return a readable inventory summary for one SKU."""
    try:
        rows = _native_db().get_product_inventory(product_id)
    except Exception as e:
        logger.error(f"native inventory format query failed: {e}")
        return f"库存查询失败: {e}"
    if not rows:
        return f"product_id={product_id} 未查到库存数据"

    lines = []
    for row in rows:
        title = row.get("title") or row.get("产品名称") or row.get("商品名称") or ""
        color = row.get("color") or row.get("spec") or row.get("【颜色】") or "默认颜色"
        warehouse = row.get("warehouse_name") or row.get("【仓库】") or ""
        qty = row.get("inventory") or row.get("库存数量") or row.get("stock") or "0"
        lines.append(f"{title} | 【{color}】 | 【{warehouse}】 | {qty}")
    return "\n".join(lines)


@tool("find_product_by_name", "按名称查商品")
def find_product_by_name(keyword: str) -> list[dict]:
    """Search active products in sjagent_core."""
    try:
        rows = _native_db().product_search(keyword, limit=20)
        logger.info(f"native product lookup keyword={keyword} returned {len(rows)} rows")
        return [
            {
                "id": row.get("id"),
                "title": row.get("title") or row.get("name"),
                "spec": row.get("spec") or row.get("color") or "默认颜色",
                "simple_desc": row.get("simple_desc") or row.get("piece_text") or "",
                "sku_no": row.get("sku_no") or row.get("coding") or "",
                "unit_id": row.get("unit_id"),
                "unit_name": row.get("unit_name") or "",
                "price": row.get("price"),
            }
            for row in rows
        ]
    except Exception as e:
        logger.error(f"native product lookup failed: {e}")
        return []


@tool("get_simple_desc", "获取商品件规")
def get_simple_desc(product_id: int) -> str | None:
    """Return the native case-pack text, e.g. '件规：1件28套'."""
    try:
        info = _native_db().product_info(product_id)
        if not info:
            return None
        piece = info.get("piece_text") or info.get("simple_desc") or ""
        if piece and not str(piece).startswith("件规"):
            return f"件规：{piece}"
        return piece or None
    except Exception as e:
        logger.error(f"native case-pack query failed: {e}")
        return None
