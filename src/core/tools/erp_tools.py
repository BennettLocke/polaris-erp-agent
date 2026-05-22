"""Self-owned business tools.

The module name is historical. Runtime business operations use sjagent_core
through NativeDBClient and no longer call the old ERP API.
"""

from src.core.customer_name import normalize_customer_name
from src.core.product_name import PRODUCT_SPECS, normalize_product_name
from src.core.tools.registry import tool
from src.engine.native_db import get_native_db_client
from src.utils import get_logger

logger = get_logger("sjagent.tools.erp")


def _native_db():
    return get_native_db_client()


@tool("inventory_query_by_id", "按商品ID查询库存")
def inventory_query_by_id(product_id: int) -> list[dict]:
    try:
        rows = _native_db().get_product_inventory(product_id)
        logger.info(f"native inventory by product: product_id={product_id}, rows={len(rows)}")
        return rows
    except Exception as e:
        logger.error(f"native inventory by product failed: {e}")
        return []


@tool("inventory_query_by_warehouse", "查询某仓库全部库存")
def inventory_query_by_warehouse(warehouse_id: int) -> list[dict]:
    try:
        rows = _native_db().get_warehouse_inventory(warehouse_id)
        logger.info(f"native inventory by warehouse: warehouse_id={warehouse_id}, rows={len(rows)}")
        return rows
    except Exception as e:
        logger.error(f"native inventory by warehouse failed: {e}")
        return []


@tool("inventory_search", "按商品名/颜色查询库存")
def inventory_search(keyword: str, color: str = "", only_in_stock: bool = False, limit: int = 100) -> list[dict]:
    keyword = normalize_product_name(keyword, specs=PRODUCT_SPECS)
    try:
        rows = _native_db().search_inventory(
            keyword=keyword,
            color=color,
            only_in_stock=only_in_stock,
            limit=limit,
        )
        logger.info(f"native inventory search: keyword={keyword}, color={color}, rows={len(rows)}")
        return rows
    except Exception as e:
        logger.error(f"native inventory search failed: {e}")
        return []


@tool("product_search", "搜索商品")
def product_search(keyword: str) -> list[dict]:
    keyword = normalize_product_name(keyword, specs=PRODUCT_SPECS)
    try:
        rows = _native_db().product_search(keyword)
        logger.info(f"native product search: keyword={keyword}, rows={len(rows)}")
        return rows
    except Exception as e:
        logger.error(f"native product search failed: {e}")
        return []


@tool("product_info", "获取商品详细信息")
def product_info(product_id: int) -> dict | None:
    try:
        info = _native_db().product_info(product_id)
        if info:
            logger.info(f"native product info: product_id={product_id}, title={info.get('title')}")
        return info
    except Exception as e:
        logger.error(f"native product info failed: {e}")
        return None


@tool("customer_query", "查询客户")
def customer_query(keyword: str) -> list[dict]:
    try:
        rows = _native_db().customer_list(keyword)
        logger.info(f"native customer query: keyword={keyword}, rows={len(rows)}")
        return rows
    except Exception as e:
        logger.error(f"native customer query failed: {e}")
        return []


@tool("customer_create", "创建客户")
def customer_create(name: str, contacts_name: str = "", contacts_tel: str = "") -> dict:
    name = normalize_customer_name(name)
    if not name:
        return {"error": "客户名称为空，无法创建客户"}
    try:
        result = _native_db().customer_create(
            name=name,
            contacts_name=contacts_name,
            contacts_tel=contacts_tel,
        )
        logger.info(f"native customer created: name={name}, result={result}")
        return result
    except Exception as e:
        logger.error(f"native customer create failed: {e}")
        return {"error": str(e)}


@tool("sales_add", "开销售单")
def sales_add(
    customer_id: int,
    warehouse_id: int,
    products: list[dict],
    create_time: str = "",
    pay_status: str | None = None,
    pay_type: str | None = None,
) -> dict:
    try:
        result = _native_db().create_sales_order(
            customer_id=customer_id,
            warehouse_id=warehouse_id,
            products=products,
            create_time=create_time,
            pay_status=pay_status,
            pay_type=pay_type,
        )
        logger.info(f"native sales order created: {result}")
        return result
    except Exception as e:
        logger.error(f"native sales order create failed: {e}")
        return {"error": str(e)}


@tool("sales_delete", "删除销售单")
def sales_delete(ids: str) -> dict:
    try:
        results = []
        for item in str(ids or "").split(","):
            item = item.strip()
            if item:
                results.append(_native_db().delete_sales_order(int(item)))
        logger.info(f"native sales order deleted: ids={ids}, result={results}")
        return {"code": 0, "data": results}
    except Exception as e:
        logger.error(f"native sales order delete failed: {e}")
        return {"error": str(e)}


@tool("other_enter_add", "其他入库")
def other_enter_add(warehouse_id: int, products: list[dict], note: str = "智能体进货") -> dict:
    try:
        result = _native_db().create_stock_in(warehouse_id=warehouse_id, products=products, note=note)
        logger.info(f"native stock-in created: {result}")
        return result
    except Exception as e:
        logger.error(f"native stock-in failed: {e}")
        return {"error": str(e)}


@tool("inventory_transfer", "仓库调拨")
def inventory_transfer(
    out_warehouse_id: int,
    enter_warehouse_id: int,
    products: list[dict],
    note: str = "智能体调拨",
) -> dict:
    try:
        result = _native_db().create_transfer(
            out_warehouse_id=out_warehouse_id,
            enter_warehouse_id=enter_warehouse_id,
            products=products,
            note=note,
        )
        logger.info(f"native transfer created: {result}")
        return result
    except Exception as e:
        logger.error(f"native transfer failed: {e}")
        return {"error": str(e)}


@tool("inventory_sync", "盘点同步")
def inventory_sync(warehouse_id: int, products: list[dict], note: str = "智能体盘点同步") -> dict:
    try:
        result = _native_db().create_stocktake(warehouse_id=warehouse_id, products=products, note=note)
        logger.info(f"native stocktake created: {result}")
        return result
    except Exception as e:
        logger.error(f"native stocktake failed: {e}")
        return {"error": str(e)}


@tool("sales_detail", "销售单详情")
def sales_detail(sales_id: int) -> dict:
    try:
        return _native_db().sales_detail(sales_id)
    except Exception as e:
        logger.error(f"native sales detail failed: {e}")
        return {"error": str(e)}


@tool("sales_list", "销售单列表")
def sales_list(keyword: str = None, customer_id: int = None, status: int = None, page: int = 1, page_size: int = 20) -> dict:
    try:
        cards, total = _native_db().sales_cards(keyword=keyword or "", page=page, page_size=page_size, status=status)
        if customer_id:
            cards = [card for card in cards if int(card.get("customer_id") or 0) == int(customer_id)]
            total = len(cards)
        return {"code": 0, "data": {"list": cards, "total": total, "page": page, "page_size": page_size}}
    except Exception as e:
        logger.error(f"native sales list failed: {e}")
        return {"error": str(e)}


@tool("warehouse_list", "仓库列表")
def warehouse_list() -> list[dict]:
    try:
        return _native_db().warehouse_list()
    except Exception as e:
        logger.error(f"native warehouse list failed: {e}")
        return []


@tool("product_add", "添加商品")
def product_add(title: str, spec: str = "", unit_id: int = 1, simple_desc: str = "", brand_name: str = "") -> dict:
    try:
        return _native_db().save_product({
            "title": title,
            "simple_desc": simple_desc,
            "base": {
                "new_0": {
                    "spec": spec,
                    "unit": {
                        "new_0": {
                            "unit_id": unit_id,
                            "price": 0,
                            "cost_price": 0,
                        }
                    },
                }
            },
        })
    except Exception as e:
        logger.error(f"native product add failed: {e}")
        return {"error": str(e)}
