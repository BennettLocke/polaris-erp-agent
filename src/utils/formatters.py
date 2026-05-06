"""结果格式化工具 - 统一各模块输出格式"""
from typing import Any


def fmt_inventory(inventory_list: list[dict]) -> str:
    """
    格式化库存查询结果
    必须输出格式：产品名称 | 【颜色】 | 【仓库】 | 库存数量
    """
    if not inventory_list:
        return "未查询到库存数据"

    lines = []
    for item in inventory_list:
        title = item.get("产品名称", item.get("title", ""))
        spec = item.get("【颜色】", item.get("spec", ""))
        warehouse = item.get("【仓库】", item.get("warehouse", ""))
        inventory = item.get("库存数量", item.get("inventory", 0))
        lines.append(f"{title} | 【{spec}】 | 【{warehouse}】 | {inventory}")

    return "\n".join(lines)


def fmt_purchase_summary(products: list[dict]) -> str:
    """
    格式化进货汇总
    1件起系列显示「件数(套数)」，非1件起系列显示套数
    """
    if not products:
        return ""

    from scripts.common.unit_converter import is_one_piece_order

    sections = []
    for p in products:
        name = p.get("商品名称", p.get("product_name", p.get("name", "")))
        color = p.get("颜色", p.get("color", ""))
        order_qty = p.get("quantity", 0)
        purchase_qty = p.get("purchase_quantity", order_qty)
        note = p.get("备注", p.get("note", "送至百鑫"))

        if is_one_piece_order(name):
            qty_text = f"{purchase_qty}件({order_qty}套)"
        else:
            qty_text = f"{order_qty}套"

        sections.append(f"商品:{name}\n颜色:{color}\n数量:{qty_text}\n备注:{note}")

    return "\n\n".join(sections)


def fmt_sales_result(result: dict) -> str:
    """格式化销售单结果"""
    sales_id = result.get("data") or result.get("sales_id", "")
    sales_no = result.get("sales_no", "")
    msg = result.get("msg", "开单成功")

    if sales_no:
        return f"{msg}，销售单号：{sales_no}，ID：{sales_id}"
    return f"{msg}，ID：{sales_id}"


def fmt_error(errors: list[str]) -> str:
    """格式化错误信息"""
    if not errors:
        return ""
    return "错误汇总：\n" + "\n".join(f"- {e}" for e in errors)
