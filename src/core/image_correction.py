"""Validate per-design selections against the product catalogue before any writes."""
from copy import deepcopy
from decimal import Decimal, InvalidOperation

from scripts.common.unit_converter import parse_unit_from_simple_desc
from src.core.customer_name import normalize_customer_name


def _enabled(value) -> bool:
    return str(value).strip().lower() not in {"0", "false", "no", "off"}


def prepare_correction_state(submitted: dict, original: dict, product_lookup) -> dict:
    token = str(original.get("correction_batch_id") or "")
    if token and submitted.get("correction_batch_id") != token:
        raise ValueError("这批校正已变化，请重新打开最新校正弹窗")
    old_rows = original.get("parsed_list") or []
    rows = submitted.get("parsed_list") or []
    if not rows or not isinstance(rows, list) or len(rows) != len(old_rows):
        raise ValueError("设计稿数量发生变化，请重新打开校正弹窗")
    customer = normalize_customer_name(submitted.get("customer_name", submitted.get("customer", "")))
    if not customer:
        raise ValueError("请先填写本批客户名称")

    cleaned_rows = []
    errors = []
    for index, (incoming, old) in enumerate(zip(rows, old_rows), 1):
        old = old if isinstance(old, dict) else {}
        incoming = incoming if isinstance(incoming, dict) else {}
        label = f"第 {index} 张设计稿（{old.get('source_filename') or index}）"
        if old.get("correction_id") and incoming.get("correction_id") != old["correction_id"]:
            errors.append(f"{label}顺序或标识发生变化，请重新打开校正弹窗")
            continue
        try:
            product_id = int(incoming.get("selected_sku_id") or incoming.get("product_id") or 0)
        except (TypeError, ValueError, OverflowError):
            product_id = 0
        if product_id <= 0:
            errors.append(f"{label}请先搜索并选择商品及颜色")
            continue
        try:
            product = product_lookup(product_id)
        except Exception:
            errors.append(f"{label}商品查询失败，请稍后重试")
            continue
        status = str((product or {}).get("native_status", (product or {}).get("status", "active"))).lower()
        if (not isinstance(product, dict) or product.get("error")
                or int(product.get("id") or product.get("product_id") or 0) != product_id
                or product.get("deleted_at") or status not in {"active", "normal", "enabled", "0"}
                or not _enabled(product.get("is_sellable", True))):
            errors.append(f"{label}所选商品已不可用，请重新选择商品及颜色")
            continue
        name = str(product.get("title") or product.get("name") or "").strip()
        color = str(product.get("color") or product.get("spec") or "默认颜色").strip()
        if not name:
            errors.append(f"{label}所选商品缺少名称，请重新选择")
            continue
        try:
            raw_quantity = Decimal(str(incoming.get("raw_quantity", incoming.get("quantity", old.get("quantity", "")))))
            if not raw_quantity.is_finite() or raw_quantity <= 0:
                raise ValueError()
        except (InvalidOperation, TypeError, ValueError):
            errors.append(f"{label}的数量必须大于 0")
            continue
        raw_unit = str(incoming.get("raw_unit", incoming.get("unit", old.get("unit", "套"))) or "").strip()
        if raw_unit not in {"件", "套", "个", "只", "盒", "张", "捆"}:
            errors.append(f"{label}的单位无效，请选择件、套、个、只、盒、张或捆")
            continue
        quantity = raw_quantity
        unit = raw_unit
        if raw_unit == "件":
            try:
                pack = Decimal(str(product.get("case_pack_qty") or parse_unit_from_simple_desc(
                    str(product.get("piece_text") or product.get("simple_desc") or "")) or 0))
                if not pack.is_finite() or pack <= 0:
                    raise ValueError()
            except (InvalidOperation, ValueError, TypeError):
                errors.append(f"{label}所选商品没有有效件规，请按套填写数量或先补全商品件规")
                continue
            quantity *= pack
            unit = str(product.get("unit_name") or "套")

        row = deepcopy(old)
        original_name = str(old.get("original_goods_name", old.get("goods_name") or ""))
        original_color = str(old.get("original_color", old.get("color") or ""))
        remark = str(incoming.get("remark", incoming.get("note", old.get("remark") or "")) or "")
        previous_name = str(old.get("goods_name") or original_name)
        previous_color = str(old.get("color") or original_color)
        for previous in dict.fromkeys([previous_name, original_name]):
            if previous and previous != name:
                remark = remark.replace(previous, name)
        for previous in dict.fromkeys([previous_color, original_color]):
            if previous and previous != color:
                remark = remark.replace(previous, color)
        row.update({
            "original_goods_name": original_name, "original_color": original_color,
            "original_remark": old.get("original_remark", old.get("remark") or ""),
            "customer": customer, "customer_name": customer,
            "selected_sku_id": product_id, "product_id": product_id,
            "goods_name": name, "color": color,
            "quantity": float(quantity) if quantity % 1 else int(quantity), "unit": unit,
            "raw_quantity": float(raw_quantity) if raw_quantity % 1 else int(raw_quantity), "raw_unit": raw_unit,
            "unit_id": int(product.get("unit_id") or 1),
            "remark": remark, "recognition_status": "corrected",
            "is_screen_print": any(word in remark for word in ("丝印", "印刷")),
        })
        cleaned_rows.append(row)
    if errors:
        raise ValueError("\n".join(errors))

    state = deepcopy(original)
    state.update(customer_name=customer, customer=customer, parsed_list=cleaned_rows)
    params = dict(original.get("order_params") or {})
    params.update(customer=customer, customer_name=customer, customers=[customer], products=[{
        "name": row["goods_name"], "color": row["color"], "qty": row["quantity"],
        "quantity": row["quantity"], "unit": row["unit"], "unit_id": row["unit_id"],
        "product_id": row["product_id"],
    } for row in cleaned_rows])
    state["order_params"] = params
    return state
