"""盘点同步流程"""
import re

from src.skills.base import BaseWorkflow
from src.core.tools.caller import get_tool_caller
from src.core.product_name import PRODUCT_SPECS, normalize_product_name
from src.utils import get_logger

logger = get_logger("sjagent.skills.stocktaking")


class StocktakingWorkflow(BaseWorkflow):
    """盘点同步。盘点会直接改库存，所以必须先确认。"""

    def __init__(self):
        self.caller = get_tool_caller()

    def execute(self, user_input: str, params: dict = None) -> dict:
        params = self._ensure_params(user_input, params)
        warehouse = params.get("warehouse", "百鑫")
        warehouse_id = 1 if "自己" in warehouse or "店里" in warehouse else 2
        warehouse_name = "自己店里" if warehouse_id == 1 else "百鑫仓库"
        products = self._enrich_products(params.get("products", []), user_input)

        if not products:
            return self._reply("没有识别到盘点商品，请重新描述，例如：盘点 喜悦3两黄色 10套 百鑫仓库。")

        items = []
        for p in products:
            if not p.get("color"):
                return self._ask(
                    f"请问「{p.get('name', '这个商品')}」要盘点哪个颜色？",
                    {"pending_action": "collect_stocktaking_color", "params": params},
                )
            if p.get("quantity") is None:
                return self._ask(
                    f"请问「{p.get('name', '这个商品')} {p.get('color', '')}」盘点后是多少套？",
                    {"pending_action": "collect_stocktaking_quantity", "params": params},
                )

            try:
                product = self._resolve_product(p, warehouse_name)
            except Exception as e:
                logger.warning(f"搜索盘点商品失败: {e}")
                product = None

            if product and product.get("candidates"):
                return self._reply(self._format_ambiguous_product_message(p, product["candidates"], warehouse_name))
            if not product:
                desc = self._product_desc(p)
                return self._reply(f"没有找到可盘点的商品：{desc}。请确认商品名称、规格和颜色。")

            unit_map = {"套": 1, "件": 1, "个": 3, "张": 5, "捆": 2, "斤": 4}
            unit = p.get("unit", "套") or "套"
            quantity = int(p.get("quantity", 1))
            items.append({
                "product_id": product["id"],
                "unit_id": unit_map.get(unit, 1),
                "number": quantity,
                "title": product.get("title", ""),
                "spec": product.get("spec", ""),
                "qty": quantity,
                "unit": unit,
                "current_stock": product.get("stock", ""),
            })

        question = self._format_confirm_question(items, warehouse_name)
        return self._ask(
            question,
            {
                "pending_action": "confirm_stocktaking",
                "warehouse_id": warehouse_id,
                "warehouse_name": warehouse_name,
                "items": items,
            },
        )

    def resume(self, user_input: str, state: dict) -> dict:
        action = state.get("pending_action")

        if action == "collect_stocktaking_color":
            params = state.get("params", {})
            products = params.get("products", [])
            if products:
                color = self._extract_color(user_input)
                if not color:
                    return self._ask("请直接回复颜色，例如：黄色、咖色、红色。", state)
                products[0]["color"] = color
                products[0]["name"] = str(products[0].get("name", "")).replace(color, "").strip()
                params["products"] = products
            return self.execute(user_input, params)

        if action == "collect_stocktaking_quantity":
            params = state.get("params", {})
            products = params.get("products", [])
            if products:
                m = re.search(r"\d+", user_input)
                if not m:
                    return self._ask("请直接回复数量，例如：10套。", state)
                products[0]["quantity"] = int(m.group(0))
                params["products"] = products
            return self.execute(user_input, params)

        if action == "confirm_stocktaking":
            if not self._is_confirmation(user_input):
                return self._reply("已取消盘点，没有修改库存。")
            return self._sync_inventory(state)

        return self._reply("盘点状态已失效，请重新发起。")

    def _ensure_params(self, user_input: str, params: dict | None) -> dict:
        if params and params.get("products"):
            return params

        from src.core.llm import llm_json
        try:
            return llm_json(
                """从用户输入中提取盘点信息，返回JSON：
{
  "warehouse": "自己店里/百鑫",
  "products": [{"name": "商品名和规格", "color": "颜色或空", "quantity": 数量, "unit": "套/个/张/件/捆/斤"}]
}""",
                user_input,
            )
        except Exception as e:
            logger.warning(f"解析盘点信息失败: {e}")
            return {}

    def _enrich_products(self, products: list[dict], user_input: str) -> list[dict]:
        text_color = self._extract_color(user_input)
        enriched = []
        for product in products or []:
            p = dict(product)
            if text_color and not p.get("color"):
                p["color"] = text_color
            if p.get("name") and p.get("color"):
                p["name"] = str(p["name"]).replace(str(p["color"]), "").strip()
            p["name"] = self._normalize_product_name(p.get("name", ""))
            if "qty" in p and "quantity" not in p:
                p["quantity"] = p.get("qty")
            enriched.append(p)
        return enriched

    def _resolve_product(self, product: dict, warehouse_name: str) -> dict | None:
        name = self._normalize_product_name(product.get("name", ""))
        color = product.get("color", "")

        inventory_matches = []
        for keyword in self._product_keywords(name):
            try:
                rows = self.caller.call(
                    "inventory_search",
                    keyword=keyword,
                    color=color,
                    only_in_stock=False,
                    limit=80,
                )
            except Exception:
                rows = []
            inventory_matches.extend(self._filter_inventory_rows(rows, name, color, warehouse_name))

        unique_inventory = self._unique_matches(inventory_matches, id_key="product_id")
        if len(unique_inventory) == 1:
            row = unique_inventory[0]
            return {
                "id": row.get("product_id"),
                "title": row.get("产品名称"),
                "spec": row.get("【颜色】"),
                "stock": int(row.get("库存数量", 0) or 0),
            }
        if len(unique_inventory) > 1:
            return {"candidates": unique_inventory}

        product_matches = []
        for keyword in self._product_keywords(name):
            try:
                candidates = self.caller.call("product_search", keyword=keyword)
            except Exception:
                candidates = []
            product_matches.extend(self._filter_products(candidates, name, color))

        unique_products = self._unique_matches(product_matches, id_key="id")
        if len(unique_products) == 1:
            p = unique_products[0]
            return {"id": p.get("id"), "title": p.get("title"), "spec": p.get("spec"), "stock": ""}
        if len(unique_products) > 1:
            return {"candidates": [
                {
                    "product_id": p.get("id"),
                    "产品名称": p.get("title"),
                    "【颜色】": p.get("spec"),
                    "【仓库】": warehouse_name,
                    "库存数量": "",
                }
                for p in unique_products
            ]}
        return None

    def _filter_inventory_rows(self, rows: list[dict], target_name: str, color: str, warehouse_name: str) -> list[dict]:
        target_terms = self._target_terms(target_name)
        matches = []
        for row in rows or []:
            title = str(row.get("产品名称", ""))
            spec = str(row.get("【颜色】", ""))
            wh = str(row.get("【仓库】", ""))
            if warehouse_name and warehouse_name not in wh:
                continue
            if color and color not in spec:
                continue
            if all(term in title for term in target_terms):
                matches.append(row)
        return matches

    def _filter_products(self, candidates: list[dict], target_name: str, color: str) -> list[dict]:
        target_terms = self._target_terms(target_name)
        matches = []
        for p in candidates or []:
            title = str(p.get("title", ""))
            spec = str(p.get("spec", ""))
            if color and color not in spec:
                continue
            if all(term in title for term in target_terms):
                matches.append(p)
        return matches

    def _normalize_product_name(self, name: str) -> str:
        return normalize_product_name(name, specs=PRODUCT_SPECS)

    def _product_keywords(self, name: str) -> list[str]:
        specs = PRODUCT_SPECS
        keywords = [name]
        for spec in specs:
            if spec in name:
                brand = name.replace(spec, "").strip()
                if brand:
                    keywords.append(f"{brand} {spec}")
                    keywords.append(brand)
                keywords.append(spec)
                break
        return list(dict.fromkeys(k for k in keywords if k))

    def _target_terms(self, name: str) -> list[str]:
        specs = PRODUCT_SPECS
        for spec in specs:
            if spec in name:
                brand = name.replace(spec, "").strip()
                return [t for t in [brand, spec] if t]
        return [name] if name else []

    def _unique_matches(self, rows: list[dict], id_key: str) -> list[dict]:
        unique = []
        seen = set()
        for row in rows:
            key = (row.get(id_key), row.get("【颜色】") or row.get("spec"))
            if key in seen:
                continue
            seen.add(key)
            unique.append(row)
        return unique

    def _extract_color(self, text: str) -> str:
        colors = ["橄榄绿", "深咖色", "古铜色", "红色", "黄色", "金色", "橙色", "蓝色", "绿色", "咖色", "黑色", "白色", "银色", "灰色", "紫色", "粉色"]
        for color in colors:
            if color in str(text or ""):
                return color
        return ""

    def _product_desc(self, product: dict) -> str:
        name = product.get("name", "")
        color = product.get("color", "")
        qty = product.get("quantity", "")
        unit = product.get("unit", "套")
        return f"{name}{(' ' + color) if color else ''}{(' ' + str(qty) + unit) if qty else ''}".strip()

    def _format_confirm_question(self, items: list[dict], warehouse_name: str) -> str:
        lines = [f"请确认盘点到{warehouse_name}："]
        for item in items:
            stock = item.get("current_stock", "")
            stock_text = f"，当前库存 {stock}" if stock != "" else ""
            lines.append(
                f"- {item.get('title', '商品')}{(' ' + item.get('spec', '')) if item.get('spec') else ''}，盘点为 {item.get('qty')} {item.get('unit', '套')}{stock_text}"
            )
        lines.append("确认后我再同步库存。")
        return "\n".join(lines)

    def _format_ambiguous_product_message(self, product: dict, candidates: list[dict], warehouse_name: str) -> str:
        lines = [
            f"在{warehouse_name}找到多个符合「{product.get('name', '')} {product.get('color', '')}」的商品，我不确定要盘点哪一个，请补充规格或颜色："
        ]
        for idx, row in enumerate(candidates[:8], 1):
            stock = row.get("库存数量", "")
            stock_text = f"，当前库存 {stock}" if stock != "" else ""
            lines.append(f"{idx}. {row.get('产品名称', '')} {row.get('【颜色】', '')}{stock_text}")
        return "\n".join(lines)

    def _is_confirmation(self, user_input: str) -> bool:
        text = user_input.strip().lower()
        if len(text) <= 8:
            return any(w in text for w in ["确认", "是", "对", "好的", "可以", "执行", "盘吧", "ok", "yes"])
        return False

    def _sync_inventory(self, state: dict) -> dict:
        items = state.get("items", [])
        if not items:
            return self._reply("盘点商品信息丢失，请重新操作。")

        warehouse_id = int(state.get("warehouse_id") or 2)
        state["warehouse_id"] = warehouse_id
        state["warehouse_name"] = "自己店里" if warehouse_id == 1 else "百鑫仓库"
        payload = [
            {"product_id": item["product_id"], "unit_id": item.get("unit_id", 1), "number": item.get("qty", item.get("number", 1))}
            for item in items
        ]
        try:
            self.caller.call(
                "inventory_sync",
                warehouse_id=state["warehouse_id"],
                products=payload,
                note="智能体盘点",
            )
            changed = "、".join(
                f"{item.get('title', '商品')}{(' ' + item.get('spec', '')) if item.get('spec') else ''} {item.get('qty')}{item.get('unit', '套')}"
                for item in items
            )
            return self._reply(f"盘点完成！已同步到{state.get('warehouse_name', '仓库')}：{changed}。")
        except Exception as e:
            return self._reply(f"盘点失败：{str(e)}")
