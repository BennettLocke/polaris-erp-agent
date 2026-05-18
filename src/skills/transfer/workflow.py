"""仓库调拨流程"""
import re
from src.skills.base import BaseWorkflow
from src.core.tools.caller import get_tool_caller
from src.core.product_name import PRODUCT_SPECS, normalize_product_name
from src.utils import get_logger

logger = get_logger("sjagent.skills.transfer")


class TransferWorkflow(BaseWorkflow):
    """仓库调拨"""

    def __init__(self):
        self.caller = get_tool_caller()

    def execute(self, user_input: str, params: dict = None) -> dict:
        # 优先使用 LLM 预提取的参数
        if not params or not params.get("from"):
            from src.core.llm import llm_json
            try:
                params = llm_json(
                    """从用户输入中提取调拨信息，返回JSON：
{
  "from": "自己店里/百鑫",
  "to": "自己店里/百鑫",
  "products": [{"name": "商品名", "quantity": 数量, "unit": "套/个/张/捆/斤", "color": "颜色或空"}]
}""",
                    user_input,
                )
            except Exception as e:
                return self._reply(f"解析调拨信息失败：{str(e)}")

        def parse_wh(s):
            if "自己" in s or "店里" in s:
                return 1
            return 2

        from_wh = parse_wh(params.get("from", "百鑫"))
        to_wh = parse_wh(params.get("to", "自己店里"))

        if from_wh == to_wh:
            return self._reply("调出和调入仓库不能相同。")

        products = self._enrich_products(params.get("products", []), user_input)
        if not products:
            return self._reply("没有识别到调拨商品，请重新描述。")

        from_name = "自己店里" if from_wh == 1 else "百鑫仓库"
        to_name = "自己店里" if to_wh == 1 else "百鑫仓库"
        items = []
        for p in products:
            if not p.get("color"):
                return self._ask(
                    f"请问「{p.get('name', '这个商品')}」要调哪个颜色？",
                    {"pending_action": "collect_transfer_color", "params": params},
                )
            if not p.get("quantity"):
                return self._ask(
                    f"请问「{p.get('name', '这个商品')} {p.get('color', '')}」要调多少套？",
                    {"pending_action": "collect_transfer_quantity", "params": params},
                )
            try:
                product = self._resolve_product(p, from_wh)
                if product and product.get("candidates"):
                    return self._reply(self._format_ambiguous_product_message(p, product["candidates"], from_name))
                if product:
                    unit_map = {"套": 1, "个": 3, "张": 5, "捆": 2, "斤": 4}
                    uid = unit_map.get(p.get("unit", "套"), 1)
                    items.append({
                        "product_id": product["id"],
                        "unit_id": uid,
                        "transfer_number": p.get("quantity", 1),
                        "title": product.get("title", ""),
                        "spec": product.get("spec", ""),
                        "qty": p.get("quantity", 1),
                        "stock": product.get("stock", ""),
                    })
            except Exception as e:
                logger.warning(f"搜索商品失败: {e}")

        if not items:
            opposite = self._find_reverse_direction_matches(products, from_wh, to_wh)
            if opposite:
                reverse_from = to_wh
                reverse_to = from_wh
                reverse_from_name = "自己店里" if reverse_from == 1 else "百鑫仓库"
                reverse_to_name = "自己店里" if reverse_to == 1 else "百鑫仓库"
                question = self._format_reverse_direction_question(
                    products, from_name, to_name, opposite, reverse_from_name, reverse_to_name
                )
                return self._ask(
                    question,
                    {
                        "pending_action": "confirm_transfer",
                        "from_wh": reverse_from,
                        "to_wh": reverse_to,
                        "from_name": reverse_from_name,
                        "to_name": reverse_to_name,
                        "items": opposite,
                    },
                )

            desc = "、".join(
                f"{p.get('name', '')}{(' ' + p.get('color', '')) if p.get('color') else ''} {p.get('quantity', 1)}{p.get('unit', '套')}"
                for p in products
            )
            return self._reply(f"没有在{from_name}找到可调拨且库存足够的商品：{desc}。请先查库存或换颜色/数量。")

        question = self._format_confirm_question(items, from_name, to_name)
        return self._ask(
            question,
            {
                "pending_action": "confirm_transfer",
                "from_wh": from_wh,
                "to_wh": to_wh,
                "from_name": from_name,
                "to_name": to_name,
                "items": items,
            },
        )

    def resume(self, user_input: str, state: dict) -> dict:
        action = state.get("pending_action")
        if action == "collect_transfer_color":
            params = state.get("params", {})
            products = params.get("products", [])
            if products:
                color = self._extract_color(user_input)
                if not color:
                    return self._ask("请直接回复颜色，例如：黄色、咖色、红色。", state)
                products[0]["color"] = color
                params["products"] = products
            return self.execute(user_input, params)

        if action == "collect_transfer_quantity":
            params = state.get("params", {})
            products = params.get("products", [])
            if products:
                m = re.search(r'\d+', user_input)
                if not m:
                    return self._ask("请直接回复数量，例如：7套。", state)
                products[0]["quantity"] = int(m.group(0))
                params["products"] = products
            return self.execute(user_input, params)

        if action == "confirm_transfer":
            if not self._is_confirmation(user_input):
                return self._reply("已取消调拨。")
            return self._do_transfer(state)

        return self._reply("调拨状态已失效，请重新发起。")

    def _do_transfer(self, state: dict) -> dict:
        items = state.get("items", [])
        if not items:
            return self._reply("调拨商品信息丢失，请重新操作。")

        from_wh = int(state.get("from_wh") or 2)
        to_wh = int(state.get("to_wh") or 1)
        if from_wh == to_wh:
            return self._reply("调出仓库和调入仓库不能相同。")
        state["from_wh"] = from_wh
        state["to_wh"] = to_wh
        state["from_name"] = "自己店里" if from_wh == 1 else "百鑫仓库"
        state["to_name"] = "自己店里" if to_wh == 1 else "百鑫仓库"
        for item in items:
            item["transfer_number"] = item.get("qty", item.get("transfer_number", 1))

        try:
            result = self.caller.call("inventory_transfer",
                out_warehouse_id=state["from_wh"],
                enter_warehouse_id=state["to_wh"],
                products=items,
                note="智能体调拨",
            )
            moved = "、".join(
                f"{item.get('title', '商品')}{(' ' + item.get('spec', '')) if item.get('spec') else ''} {item.get('qty')}套"
                for item in items
            )
            return self._reply(f"调拨完成！已将 {moved} 从{state['from_name']}调到{state['to_name']}。")
        except Exception as e:
            return self._reply(f"调拨失败：{str(e)}")

    def _format_confirm_question(self, items: list[dict], from_name: str, to_name: str) -> str:
        lines = [f"请确认调拨：{from_name} → {to_name}"]
        for item in items:
            title = item.get("title", "商品")
            spec = item.get("spec", "")
            qty = item.get("qty", "")
            stock = item.get("stock", "")
            stock_text = f"，当前库存 {stock}" if stock != "" else ""
            lines.append(f"- {title}{(' ' + spec) if spec else ''}，调 {qty} 套{stock_text}")
        lines.append("确认后我再执行调拨。")
        return "\n".join(lines)

    def _is_confirmation(self, user_input: str) -> bool:
        text = user_input.strip().lower()
        if len(text) <= 8:
            return any(w in text for w in ["确认", "是", "对", "好的", "可以", "执行", "调吧", "ok", "yes"])
        return False

    def _find_reverse_direction_matches(self, products: list[dict], from_wh: int, to_wh: int) -> list[dict]:
        """If requested direction has no stock, check the opposite direction before giving up."""
        items = []
        for p in products:
            product = self._resolve_product(p, to_wh)
            if not product or product.get("candidates"):
                return []
            unit_map = {"套": 1, "个": 3, "张": 5, "捆": 2, "斤": 4}
            uid = unit_map.get(p.get("unit", "套"), 1)
            items.append({
                "product_id": product["id"],
                "unit_id": uid,
                "transfer_number": p.get("quantity", 1),
                "title": product.get("title", ""),
                "spec": product.get("spec", ""),
                "qty": p.get("quantity", 1),
                "stock": product.get("stock", ""),
            })
        return items

    def _format_reverse_direction_question(
        self,
        products: list[dict],
        from_name: str,
        to_name: str,
        items: list[dict],
        reverse_from_name: str,
        reverse_to_name: str,
    ) -> str:
        desc = "、".join(
            f"{p.get('name', '')}{(' ' + p.get('color', '')) if p.get('color') else ''} {p.get('quantity', 1)}{p.get('unit', '套')}"
            for p in products
        )
        lines = [
            f"我按「{from_name} → {to_name}」理解，但{from_name}库存不够：{desc}。",
            f"反方向「{reverse_from_name} → {reverse_to_name}」有可调库存，是否按这个方向调？",
        ]
        for item in items:
            lines.append(
                f"- {item.get('title', '商品')}{(' ' + item.get('spec', '')) if item.get('spec') else ''}，调 {item.get('qty')} 套，当前库存 {item.get('stock')}"
            )
        lines.append("确认后我再执行。")
        return "\n".join(lines)

    def _enrich_products(self, products: list[dict], user_input: str) -> list[dict]:
        text_color = self._extract_color(user_input)

        enriched = []
        for product in products or []:
            p = dict(product)
            if text_color and not p.get("color"):
                p["color"] = text_color
            if p.get("name") and p.get("color"):
                p["name"] = str(p["name"]).replace(str(p["color"]), "").strip()
            enriched.append(p)
        return enriched

    def _extract_color(self, text: str) -> str:
        colors = ["红色", "黄色", "橙色", "蓝色", "绿色", "橄榄绿", "咖色", "深咖色", "古铜色", "黑色", "白色", "紫色", "粉色", "灰色", "金色"]
        for color in colors:
            if color in text:
                return color
        return ""

    def _resolve_product(self, product: dict, from_wh: int) -> dict | None:
        name = self._normalize_product_name(product.get("name", ""))
        color = product.get("color", "")
        qty = int(product.get("quantity", 1) or 1)
        warehouse_name = "自己店里" if from_wh == 1 else "百鑫"

        all_matches = []
        for keyword in self._product_keywords(name):
            try:
                rows = self.caller.call(
                    "inventory_search",
                    keyword=keyword,
                    color=color,
                    only_in_stock=True,
                    limit=50,
                )
            except Exception:
                rows = []
            matches = self._filter_inventory_rows(rows, name, color, warehouse_name, qty)
            if matches:
                all_matches.extend(matches)
        unique = self._unique_inventory_matches(all_matches)
        if len(unique) == 1:
            row = unique[0]
            return {
                "id": row.get("product_id"),
                "title": row.get("产品名称"),
                "spec": row.get("【颜色】"),
                "stock": int(row.get("库存数量", 0) or 0),
            }
        if len(unique) > 1:
            return {"candidates": unique}
        return None

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
                    keywords.append(spec)
                    keywords.append(brand)
                break
        return list(dict.fromkeys(k for k in keywords if k))

    def _filter_inventory_rows(self, rows: list[dict], target_name: str, color: str, warehouse_name: str, qty: int) -> list[dict]:
        target_terms = self._target_terms(target_name)
        matches = []
        for row in rows or []:
            title = str(row.get("产品名称", ""))
            spec = str(row.get("【颜色】", ""))
            wh = str(row.get("【仓库】", ""))
            stock = int(row.get("库存数量", 0) or 0)
            if warehouse_name not in wh:
                continue
            if color and color not in spec:
                continue
            if stock < qty:
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

    def _target_terms(self, name: str) -> list[str]:
        specs = PRODUCT_SPECS
        for spec in specs:
            if spec in name:
                brand = name.replace(spec, "").strip()
                return [t for t in [brand, spec] if t]
        return [name]

    def _unique_inventory_matches(self, rows: list[dict]) -> list[dict]:
        unique = []
        seen = set()
        for row in rows:
            key = (row.get("product_id"), row.get("【颜色】"), row.get("【仓库】"))
            if key in seen:
                continue
            seen.add(key)
            unique.append(row)
        return unique

    def _format_ambiguous_product_message(self, product: dict, candidates: list[dict], warehouse_name: str) -> str:
        lines = [
            f"在{warehouse_name}找到多个符合「{product.get('name', '')} {product.get('color', '')}」的商品，我不确定要调哪一个，请补充规格："
        ]
        for idx, row in enumerate(candidates[:8], 1):
            lines.append(
                f"{idx}. {row.get('产品名称', '')} {row.get('【颜色】', '')}，库存 {row.get('库存数量', 0)}"
            )
        return "\n".join(lines)
