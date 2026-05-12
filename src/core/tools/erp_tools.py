"""
ERP 工具 - 数据库直查 + API 调用
库存查询用 MySQL 直查（省 Token），开单用 API
"""
from typing import Any, Optional
from src.engine.db_client import get_db_client
from src.engine.api_client import ERPSystemClient
from src.core.tools.registry import tool
from src.utils import get_logger

logger = get_logger("sjagent.tools.erp")

# 共享 ERP 客户端实例
_erp_client: Optional[ERPSystemClient] = None


def _get_erp_client() -> ERPSystemClient:
    global _erp_client
    if _erp_client is None:
        _erp_client = ERPSystemClient()
    return _erp_client


def _api_data_list(result: dict) -> list[dict]:
    """Return list rows from common ERP API response shapes."""
    data = result.get("data", [])
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        rows = data.get("list", [])
        return rows if isinstance(rows, list) else []
    return []


def _pick_first(row: dict, keys: tuple[str, ...], default: Any = "") -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return default


def _normalize_product_rows(rows: list[dict]) -> list[dict]:
    """Normalize ProductList/API rows to the DB product_search shape."""
    normalized = []
    seen = set()
    for row in rows or []:
        product_id = _pick_first(row, ("id", "product_id"))
        title = _pick_first(row, ("title", "name", "product_name", "产品名称"))
        spec = _pick_first(row, ("spec", "color", "颜色", "【颜色】"))
        key = (product_id, title, spec)
        if not product_id or not title or key in seen:
            continue
        seen.add(key)
        normalized.append({
            "id": product_id,
            "title": title,
            "spec": spec,
            "simple_desc": _pick_first(row, ("simple_desc", "desc", "description")),
            "unit_id": _pick_first(row, ("unit_id",)),
            "unit_name": _pick_first(row, ("unit_name",)),
            "price": _pick_first(row, ("price", "sale_price", "retail_price"), 0),
        })
    return normalized


def _product_search_api(keyword: str) -> list[dict]:
    """Fallback to ERP ProductList when local DB search misses."""
    try:
        result = _get_erp_client().product_list(keyword=keyword, page_size=50)
        rows = _normalize_product_rows(_api_data_list(result))
        logger.info(f"商品搜索API兜底: keyword={keyword}, 结果={len(rows)}条")
        return rows
    except Exception as e:
        logger.warning(f"商品搜索API兜底失败: keyword={keyword}, error={e}")
        return []


@tool("inventory_query_by_id", "按产品ID查询库存")
def inventory_query_by_id(product_id: int) -> list[dict]:
    """
    按产品ID查询库存（MySQL直查，不走API）

    Returns:
        [{"产品名称": ..., "【颜色】": ..., "【仓库】": ..., "库存数量": ...}]
    """
    db = get_db_client()
    try:
        results = db.get_product_inventory(product_id)
        logger.info(f"库存查询: product_id={product_id}, 结果={len(results)}条")
        return results
    except Exception as e:
        logger.error(f"库存查询失败: {e}")
        return []


@tool("inventory_query_by_warehouse", "查询某仓库全部库存")
def inventory_query_by_warehouse(warehouse_id: int) -> list[dict]:
    """
    查询某仓库全部有库存的产品

    Args:
        warehouse_id: 1=自己店里, 2=百鑫仓库
    """
    db = get_db_client()
    try:
        results = db.get_warehouse_inventory(warehouse_id)
        logger.info(f"仓库库存查询: warehouse_id={warehouse_id}, 结果={len(results)}条")
        return results
    except Exception as e:
        logger.error(f"仓库库存查询失败: {e}")
        return []


@tool("inventory_search", "按商品名/颜色一次性查询库存")
def inventory_search(
    keyword: str,
    color: str = "",
    only_in_stock: bool = False,
    limit: int = 100,
) -> list[dict]:
    """
    一次性按商品名/颜色查询库存，避免 N+1 查询。

    Returns:
        [{"product_id": ..., "产品名称": ..., "【颜色】": ..., "【仓库】": ..., "库存数量": ...}]
    """
    db = get_db_client()
    try:
        results = db.search_inventory(
            keyword=keyword,
            color=color,
            only_in_stock=only_in_stock,
            limit=limit,
        )
        logger.info(
            f"库存批量查询: keyword={keyword}, color={color}, only_in_stock={only_in_stock}, 结果={len(results)}条"
        )
        return results
    except Exception as e:
        logger.error(f"库存批量查询失败: {e}")
        return []


@tool("product_search", "搜索商品")
def product_search(keyword: str) -> list[dict]:
    """
    模糊搜索商品（MySQL优先，查不到时用ERP API兜底）

    Returns:
        [{"id": ..., "title": ..., "spec": ..., "simple_desc": ..., "unit_id": ..., "price": ...}]
    """
    db = get_db_client()
    try:
        results = db.search_products(keyword)
        logger.info(f"商品搜索: keyword={keyword}, 结果={len(results)}条")
        if results:
            return results
    except Exception as e:
        logger.error(f"商品搜索失败: {e}")
    return _product_search_api(keyword)


@tool("product_info", "获取商品详细信息")
def product_info(product_id: int) -> dict | None:
    """获取商品完整信息（含每件套数）"""
    db = get_db_client()
    try:
        info = db.get_product_info(product_id)
        if info:
            logger.info(f"商品信息: product_id={product_id}, title={info.get('title')}")
        return info
    except Exception as e:
        logger.error(f"商品信息查询失败: {e}")
        return None


@tool("customer_query", "查询客户")
def customer_query(keyword: str) -> list[dict]:
    """查询客户（按名称模糊搜索）"""
    client = _get_erp_client()
    try:
        result = client.company_list(keyword=keyword)
        data = result.get("data", [])
        # API 返回格式：data 直接是列表，或 data.list 是列表
        if isinstance(data, list):
            customers = data
        elif isinstance(data, dict):
            customers = data.get("list", [])
        else:
            customers = []
        logger.info(f"客户查询: keyword={keyword}, 结果={len(customers)}条")
        return customers
    except Exception as e:
        logger.error(f"客户查询失败: {e}")
        return []


@tool("customer_create", "创建客户")
def customer_create(
    name: str,
    contacts_name: str = "",
    contacts_tel: str = "",
) -> dict:
    """
    创建新客户

    Args:
        name: 客户名称（必填）
        contacts_name: 联系人（选填）
        contacts_tel: 联系电话（选填）
    """
    client = _get_erp_client()
    try:
        result = client.company_add(
            name=name,
            contacts_name=contacts_name,
            contacts_tel=contacts_tel,
        )
        logger.info(f"客户创建: name={name}, result={result}")
        return result
    except Exception as e:
        logger.error(f"客户创建失败: {e}")
        return {"error": str(e)}


@tool("sales_add", "开销售单")
def sales_add(
    customer_id: int,
    warehouse_id: int,
    products: list[dict],
    create_time: str = "",
) -> dict:
    """
    开销售单（一次性包含所有商品，自动扣库存）

    Args:
        customer_id: 客户ID
        warehouse_id: 仓库ID（1=自己店里, 2=百鑫）
        products: 商品列表
            [{"product_id": X, "unit_id": 1, "buy_number": Y, "price": Z}, ...]
    """
    client = _get_erp_client()
    try:
        result = client.sales_add(
            customer_id=customer_id,
            warehouse_id=warehouse_id,
            products=products,
            create_time=create_time,
        )
        logger.info(f"销售单创建成功: {result}")
        return result
    except Exception as e:
        logger.error(f"销售单创建失败: {e}")
        return {"error": str(e)}


@tool("sales_delete", "删除销售单")
def sales_delete(ids: str) -> dict:
    """
    删除销售单（自动回滚库存）

    Args:
        ids: 销售单ID（多个用逗号分隔）
    """
    client = _get_erp_client()
    try:
        result = client.sales_delete(ids=ids)
        logger.info(f"销售单删除: ids={ids}, result={result}")
        return result
    except Exception as e:
        logger.error(f"销售单删除失败: {e}")
        return {"error": str(e)}


@tool("other_enter_add", "其他入库（进货）")
def other_enter_add(
    warehouse_id: int,
    products: list[dict],
    note: str = "智能体进货",
) -> dict:
    """
    其他入库（进货入库，入库到指定仓库）

    Args:
        warehouse_id: 仓库ID（默认2=百鑫）
        products: [{"product_id": X, "unit_id": 1, "buy_number": Y}, ...]
        note: 备注
    """
    client = _get_erp_client()
    try:
        result = client.other_enter_add(
            warehouse_id=warehouse_id,
            products=products,
            note=note,
        )
        logger.info(f"入库成功: {result}")
        return result
    except Exception as e:
        logger.error(f"入库失败: {e}")
        return {"error": str(e)}


@tool("inventory_transfer", "仓库调拨")
def inventory_transfer(
    out_warehouse_id: int,
    enter_warehouse_id: int,
    products: list[dict],
    note: str = "智能体调拨",
) -> dict:
    """
    仓库间调拨

    Args:
        out_warehouse_id: 调出仓库（1=自己店里）
        enter_warehouse_id: 调入仓库（2=百鑫）
        products: [{"product_id": X, "unit_id": 1, "transfer_number": Y}, ...]
    """
    client = _get_erp_client()
    try:
        result = client.inventory_transfer(
            out_warehouse_id=out_warehouse_id,
            enter_warehouse_id=enter_warehouse_id,
            products=products,
            note=note,
        )
        logger.info(f"调拨成功: {result}")
        return result
    except Exception as e:
        logger.error(f"调拨失败: {e}")
        return {"error": str(e)}


@tool("inventory_sync", "盘点同步（设置目标库存）")
def inventory_sync(
    warehouse_id: int,
    products: list[dict],
    note: str = "智能体盘点同步",
) -> dict:
    """
    盘点同步（推荐）
    设置目标库存数（绝对值），立即生效

    Args:
        warehouse_id: 仓库ID
        products: [{"product_id": X, "unit_id": 1, "number": 目标库存}, ...]
    """
    client = _get_erp_client()
    try:
        result = client.inventory_sync(
            warehouse_id=warehouse_id,
            products=products,
            note=note,
        )
        logger.info(f"盘点同步成功: {result}")
        return result
    except Exception as e:
        logger.error(f"盘点同步失败: {e}")
        return {"error": str(e)}


@tool("sales_detail", "销售单详情")
def sales_detail(sales_id: int) -> dict:
    """查询销售单详情（含产品明细）"""
    client = _get_erp_client()
    try:
        return client.sales_detail(sales_id)
    except Exception as e:
        logger.error(f"销售单详情查询失败: {e}")
        return {"error": str(e)}


@tool("sales_list", "销售单列表")
def sales_list(
    keyword: str = None,
    customer_id: int = None,
    status: int = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """查询销售单列表"""
    client = _get_erp_client()
    try:
        return client.sales_list(keyword=keyword, customer_id=customer_id, status=status, page=page, page_size=page_size)
    except Exception as e:
        logger.error(f"销售单列表查询失败: {e}")
        return {"error": str(e)}


@tool("warehouse_list", "仓库列表")
def warehouse_list() -> list[dict]:
    """
    查询仓库列表

    Returns:
        [{"id": 1, "name": "自己店里"}, {"id": 2, "name": "百鑫仓库"}]
    """
    client = _get_erp_client()
    try:
        result = client.warehouse_list()
        return result.get("data", [])
    except Exception as e:
        logger.error(f"仓库列表查询失败: {e}")
        return []


@tool("product_add", "添加产品")
def product_add(
    title: str,
    spec: str = "",
    unit_id: int = 1,
    simple_desc: str = "",
    brand_name: str = "",
) -> dict:
    """
    添加产品
    产品已存在返回已有ID，不重复创建
    """
    client = _get_erp_client()
    try:
        return client.product_add(
            title=title,
            spec=spec,
            unit_id=unit_id,
            simple_desc=simple_desc,
            brand_name=brand_name,
        )
    except Exception as e:
        logger.error(f"产品添加失败: {e}")
        return {"error": str(e)}
