"""进货入库流程"""
import re

from src.skills.base import BaseWorkflow
from src.core.tools.caller import get_tool_caller
from src.utils import get_logger
from scripts.common.unit_converter import calculate_purchase_quantity, is_one_piece_order

logger = get_logger("sjagent.skills.purchase")


class PurchaseWorkflow(BaseWorkflow):
    """进货入库。进货会改库存，所以先确认再执行。"""

    def __init__(self):
        self.caller = get_tool_caller()

    def execute(self, user_input: str, params: dict = None) -> dict:
        if not params or not params.get("products"):
            from src.core.llm import llm_json
            try:
                params = llm_json(
                    """从用户输入中提取进货信息，返回JSON：
{
  "warehouse": "百鑫/自己店里",
  "products": [{"name": "商品名和规格", "color": "颜色或空", "quantity": 数量, "unit": "套/个/张/件/捆/斤"}]
}""",
                    user_input,
                )
            except Exception as e:
                return self._reply(f"解析进货信息失败：{str(e)}")

        warehouse = params.get("warehouse", "百鑫")
        warehouse_id = 1 if "自己" in warehouse or "店里" in warehouse else 2
        warehouse_name = "自己店里" if warehouse_id == 1 else "百鑫仓库"
        products = self._enrich_products(params.get("products", []), user_input)

        if not products:
            return self._reply("没有识别到进货商品，请重新描述，例如：进货 喜悦3两红色5套 百鑫仓库。")

        items = []
        for p in products:
            if not p.get("quantity"):
                return self._ask(
                    f"请问「{self._product_desc(p)}」要进货多少？例如：5套。",
                    {"pending_action": "collect_purchase_quantity", "params": params},
                )
            if not p.get("color") and self._looks_like_gift_box(p.get("name", "")):
                return self._ask(
                    f"请问「{p.get('name', '这个商品')}」要进哪个颜色？",
                    {"pending_action": "collect_purchase_color", "params": params},
                )

            product = self._resolve_product(p)
            if product and product.get("candidates"):
                return self._reply(self._format_ambiguous_product_message(p, product["candidates"]))
            if not product:
                return self._reply(f"没有找到可进货的商品：{self._product_desc(p)}。请确认商品名称、规格和颜色。")

            unit_map = {"套": 1, "个": 3, "张": 5, "捆": 2, "斤": 4}
            unit = p.get("unit") or "套"
            qty = int(p.get("quantity") or 1)
            purchase_qty, purchase_unit, per_piece = self._purchase_plan(product, qty, unit)
            api_unit = "套" if purchase_unit == "件" and per_piece else purchase_unit
            api_buy_number = purchase_qty * per_piece if purchase_unit == "件" and per_piece else purchase_qty
            items.append({
                "product_id": product["id"],
                "unit_id": unit_map.get(api_unit, unit_map.get(unit, 1)),
                "buy_number": api_buy_number,
                "title": product.get("title", ""),
                "spec": product.get("spec", ""),
                "qty": qty,
                "unit": unit,
                "purchase_qty": purchase_qty,
                "purchase_unit": purchase_unit,
                "purchase_per_piece": per_piece,
                "api_buy_number": api_buy_number,
                "api_unit": api_unit,
            })

        return self._ask(
            self._format_confirm_question(items, warehouse_name),
            {
                "pending_action": "confirm_purchase_enter",
                "warehouse_id": warehouse_id,
                "warehouse_name": warehouse_name,
                "items": items,
            },
        )

    def resume(self, user_input: str, state: dict) -> dict:
        action = state.get("pending_action")
        if action == "collect_purchase_quantity":
            params = state.get("params", {})
            products = params.get("products", [])
            if products:
                match = re.search(r"\d+", user_input)
                if not match:
                    return self._ask("请直接回复数量，例如：5套。", state)
                products[0]["quantity"] = int(match.group(0))
                unit_match = re.search(r"(套|张|个|件|捆|斤)", user_input)
                if unit_match:
                    products[0]["unit"] = unit_match.group(1)
                params["products"] = products
            return self.execute(user_input, params)

        if action == "collect_purchase_color":
            params = state.get("params", {})
            products = params.get("products", [])
            if products:
                color = self._extract_color(user_input)
                if not color:
                    return self._ask("请直接回复颜色，例如：黄色、红色、橙色。", state)
                products[0]["color"] = color
                params["products"] = products
            return self.execute(user_input, params)

        if action == "confirm_purchase_enter":
            if not self._is_confirmation(user_input):
                return self._reply("已取消进货，没有修改库存。")
            return self._do_purchase(state)

        return self._reply("进货状态已失效，请重新发起。")

    def _do_purchase(self, state: dict) -> dict:
        items = state.get("items") or []
        if not items:
            return self._reply("进货商品信息丢失，请重新操作。")
        payload = [
            {"product_id": item["product_id"], "unit_id": item.get("unit_id", 1), "buy_number": item.get("buy_number", item.get("qty", 1))}
            for item in items
        ]
        try:
            self.caller.call(
                "other_enter_add",
                warehouse_id=state["warehouse_id"],
                products=payload,
                note="智能体进货",
            )
            desc = "、".join(
                self._format_item_desc(item)
                for item in items
            )
            return self._reply(f"进货完成！已入库到{state.get('warehouse_name', '仓库')}：{desc}。")
        except Exception as e:
            return self._reply(f"进货失败：{str(e)}")

    def _enrich_products(self, products: list[dict], user_input: str = "") -> list[dict]:
        text_color = self._extract_color(user_input)
        enriched = []
        for product in products or []:
            p = dict(product)
            if text_color and not p.get("color"):
                p["color"] = text_color
            if p.get("name") and p.get("color"):
                p["name"] = str(p["name"]).replace(str(p["color"]), "").strip()
            p["name"] = self._normalize_product_name(p.get("name", ""))
            if p.get("qty") and not p.get("quantity"):
                p["quantity"] = p.get("qty")
            if p.get("quantity") is not None:
                p["quantity"] = int(p.get("quantity") or 0)
            p["unit"] = p.get("unit") or "套"
            enriched.append(p)
        return enriched

    def _resolve_product(self, product: dict) -> dict | None:
        name = self._normalize_product_name(product.get("name", ""))
        color = product.get("color", "")
        candidates = []
        seen = set()

        for keyword in self._product_keywords(name):
            try:
                rows = self.caller.call("product_search", keyword=keyword)
            except Exception as e:
                logger.warning(f"搜索商品失败: {e}")
                rows = []
            for row in rows or []:
                key = (row.get("id"), row.get("spec"))
                if key in seen:
                    continue
                seen.add(key)
                candidates.append(row)

            if color:
                try:
                    inv_rows = self.caller.call("inventory_search", keyword=keyword, color=color, only_in_stock=False, limit=60)
                except Exception:
                    inv_rows = []
                for row in inv_rows or []:
                    key = (row.get("product_id"), row.get("【颜色】"))
                    if key in seen:
                        continue
                    seen.add(key)
                    candidates.append({
                        "id": row.get("product_id"),
                        "title": row.get("产品名称"),
                        "spec": row.get("【颜色】"),
                        "simple_desc": row.get("simple_desc", ""),
                        "price": 0,
                    })

        selected = self._select_product(candidates, name, color)
        if selected:
            return selected
        if candidates:
            return {"candidates": candidates}
        return None

    def _select_product(self, candidates: list[dict], keyword: str, color: str = "") -> dict | None:
        rows = candidates or []
        if color:
            rows = [row for row in rows if color in str(row.get("spec", ""))]
        terms = self._product_terms(keyword)
        if terms:
            rows = [
                row for row in rows
                if all(term in re.sub(r"[【】]", "", str(row.get("title", ""))) for term in terms)
            ]
        return rows[0] if len(rows) == 1 else None

    def _normalize_product_name(self, name: str) -> str:
        normalized = re.sub(r'【[^】]+】', '', str(name or '')).strip()
        for color in self._colors():
            normalized = normalized.replace(color, "")
        normalized = re.sub(r"(?:3\s*两|2\s*两|(?<!二)三两|二两)", "二三两", normalized)
        normalized = re.sub(r"(?:0\.5\s*斤|半\s*斤)", "半斤", normalized)
        normalized = re.sub(r"(?:1\s*两|一\s*两)", "一两", normalized)
        for raw, new in [("2小盒", "二小盒"), ("3小盒", "三小盒"), ("6小盒", "六小盒"), ("10小盒", "十小盒")]:
            normalized = normalized.replace(raw, new)
        for spec in ["五格短半斤", "短半斤", "二三两", "三小盒", "六小盒", "十小盒", "长半斤", "半斤", "一两"]:
            normalized = re.sub(rf"(?<!^)(?<!\s)({re.escape(spec)})", r" \1", normalized)
        return re.sub(r"\s+", " ", normalized).strip()

    def _product_keywords(self, name: str) -> list[str]:
        normalized = self._normalize_product_name(name)
        keywords = [normalized]
        for spec in ["五格短半斤", "短半斤", "二三两", "三小盒", "六小盒", "十小盒", "长半斤", "半斤", "一两"]:
            if spec in normalized:
                brand = normalized.replace(spec, "").strip()
                if brand:
                    keywords.append(f"{brand} {spec}")
                    keywords.append(brand)
                keywords.append(spec)
                break
        compact = normalized.replace(" ", "")
        if compact != normalized:
            keywords.append(compact)
        return list(dict.fromkeys(k for k in keywords if k))

    def _product_terms(self, name: str) -> list[str]:
        normalized = self._normalize_product_name(name)
        for spec in ["五格短半斤", "短半斤", "二三两", "三小盒", "六小盒", "十小盒", "长半斤", "半斤", "一两"]:
            if spec in normalized:
                brand = normalized.replace(spec, "").strip()
                return [term for term in (brand, spec) if term]
        return [normalized] if normalized else []

    def _extract_color(self, text: str) -> str:
        for color in self._colors():
            if color in str(text or ""):
                return color
        return ""

    def _colors(self) -> list[str]:
        return ["香槟金", "橄榄绿", "深咖色", "古铜色", "红色", "黄色", "金色", "橙色", "蓝色", "绿色", "咖色", "黑色", "白色", "银色", "灰色", "紫色", "粉色"]

    def _looks_like_gift_box(self, name: str) -> bool:
        return any(word in str(name or "") for word in ["两", "斤", "盒", "礼盒"])

    def _parse_sets_per_case(self, simple_desc: str) -> int:
        if not simple_desc:
            return 0
        patterns = [
            r"(\d+)\s*套\s*/\s*件",
            r"(\d+)\s*个\s*/\s*件",
            r"(\d+)\s*张\s*/\s*件",
            r"1\s*件\s*(\d+)\s*套",
            r"每\s*件\s*(\d+)\s*套",
        ]
        for pattern in patterns:
            m = re.search(pattern, simple_desc)
            if m:
                return int(m.group(1))
        return 0

    def _purchase_plan(self, product: dict, qty: int, unit: str) -> tuple[int, str, int]:
        per_piece = self._parse_sets_per_case(product.get("simple_desc", ""))
        product_name = f"{product.get('title', '')} {product.get('name', '')}".strip()
        if unit == "件":
            return qty, "件", per_piece
        if per_piece > 1 and is_one_piece_order(product_name):
            return calculate_purchase_quantity(qty, per_piece, product_name), "件", per_piece
        return qty, unit or "套", per_piece

    def _format_item_desc(self, item: dict) -> str:
        name = f"{item.get('title', '商品')}{(' ' + item.get('spec', '')) if item.get('spec') else ''}"
        purchase_qty = item.get("purchase_qty", item.get("buy_number", item.get("qty")))
        purchase_unit = item.get("purchase_unit", item.get("unit", "套"))
        if purchase_unit == "件" and item.get("purchase_per_piece"):
            return f"{name} 订单{item.get('qty')}{item.get('unit', '套')}，进货{purchase_qty}件（{item.get('purchase_per_piece')}套/件）"
        return f"{name} {purchase_qty}{purchase_unit}"

    def _product_desc(self, product: dict) -> str:
        return (
            f"{product.get('name', '')}"
            f"{(' ' + product.get('color', '')) if product.get('color') else ''}"
            f" {product.get('quantity') or ''}{product.get('unit', '套')}"
        ).strip()

    def _format_confirm_question(self, items: list[dict], warehouse_name: str) -> str:
        lines = [f"请确认进货到{warehouse_name}："]
        for item in items:
            lines.append(f"- {self._format_item_desc(item)}")
        lines.append("回复「确认」执行进货，回复「取消」停止。")
        return "\n".join(lines)

    def _format_ambiguous_product_message(self, product: dict, candidates: list[dict]) -> str:
        lines = [f"找到多个符合「{self._product_desc(product)}」的商品，我不确定要进哪一个，请补充更准确的规格或颜色："]
        for idx, row in enumerate(candidates[:8], 1):
            lines.append(f"{idx}. {row.get('title', '')} {row.get('spec', '')}")
        return "\n".join(lines)

    def _is_confirmation(self, user_input: str) -> bool:
        text = user_input.strip().lower()
        if len(text) <= 8:
            return any(w in text for w in ["确认", "是", "对", "好的", "可以", "执行", "进货", "ok", "yes"])
        return False
