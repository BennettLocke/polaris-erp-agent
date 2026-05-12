"""库存查询流程"""
import re
from src.skills.base import BaseWorkflow
from src.core.tools.caller import get_tool_caller
from src.utils import get_logger

logger = get_logger("sjagent.skills.inventory")


class InventoryWorkflow(BaseWorkflow):
    """库存查询"""

    def __init__(self):
        self.caller = get_tool_caller()

    def _search_product(self, name: str) -> list:
        """多级搜索商品"""
        keywords = [name]
        # 去掉【品牌】前缀
        stripped = re.sub(r'【[^】]+】', '', name).strip()
        if stripped and stripped != name:
            keywords.append(stripped)
        # 逐字缩短
        base = stripped if stripped and stripped != name else name
        for i in range(len(base) - 1, 1, -1):
            sub = base[:i]
            if sub not in keywords:
                keywords.append(sub)

        for kw in keywords:
            try:
                results = self.caller.call("product_search", keyword=kw)
                if results:
                    return results
            except Exception:
                continue
        return []

    def _preprocess_input(self, text: str) -> str:
        """预处理用户输入，数字量词转中文"""
        import re
        # 数字+两/斤 → 中文
        replacements = {
            "0.5斤": "半斤",
            "1两": "一两",
            "2两": "二两",
            "3两": "三两",
            "4两": "四两",
            "5两": "五两",
            "3小盒": "三小盒",
            "6小盒": "六小盒",
            "10小盒": "十小盒",
        }
        for raw, normalized in replacements.items():
            text = text.replace(raw, normalized)
        return text

    def execute(self, user_input: str, params: dict = None) -> dict:
        # 优先使用 LLM 预提取的参数
        if params and params.get("product_name"):
            product_name = params["product_name"]
            color_filter = params.get("color", "")
        elif params and not params.get("product_name"):
            return self._reply("没有识别到商品名，请重新描述，例如：查下半斤库存")
        else:
            from src.core.llm import llm_json
            # 预处理：数字量词转中文
            processed_input = self._preprocess_input(user_input)
            # LLM 提取商品名和颜色（fallback）
            color_filter = ""
            try:
                result = llm_json(
                    '从用户输入中提取商品名和颜色（如果有指定颜色的话）。返回JSON：{"product_name": "商品名", "color": "颜色或空字符串"}',
                    processed_input,
                )
                product_name = result.get("product_name", "")
                color_filter = result.get("color", "")
            except Exception:
                # fallback: 去掉常见前缀，尝试提取颜色
                product_name = processed_input.replace("查", "").replace("库存", "").replace("一下", "").strip()
                colors = ["红色", "黄色", "橙色", "蓝色", "绿色", "橄榄绿", "咖色", "深咖色", "古铜色", "黑色", "白色", "紫色", "粉色"]
                for c in colors:
                    if c in product_name:
                        color_filter = c
                        product_name = product_name.replace(c, "").strip()
                        break

        if not product_name:
            return self._reply("请告诉我您要查询哪个商品的库存，例如：查下岩味库存")

        product_name = self._normalize_inventory_keyword(product_name, user_input)

        # 优先用一次 SQL 批量查询库存，避免先查商品再逐个查库存的 N+1 查询。
        try:
            rows = self.caller.call(
                "inventory_search",
                keyword=product_name,
                color=color_filter,
                only_in_stock=True,
                limit=100,
            )
        except Exception as e:
            logger.warning(f"[Inventory] 批量库存查询失败，回退旧路径: {e}")
            rows = []

        if rows:
            return self._reply(self._format_inventory_rows(rows, product_name))

        # 搜索商品（多级搜索），作为兼容回退路径。
        products = self._search_product(product_name)

        if not products:
            return self._reply(f"未找到商品「{product_name}」")

        # 查每个商品的库存，按仓库分组，只展示有库存的记录。
        fallback_rows = []
        for p in products[:50]:  # 最多查50个
            pid = p.get("id")
            name = p.get("title", "")
            spec = p.get("spec", "")
            try:
                inventory = self.caller.call("inventory_query_by_id", product_id=pid)
                if inventory:
                    for inv in inventory:
                        wh = inv.get("【仓库】", "")
                        qty = int(inv.get("库存数量", 0)) if inv.get("库存数量") else 0
                        color = inv.get("【颜色】", "") or spec
                        # 如果指定了颜色，过滤不匹配的
                        if color_filter and color_filter not in color:
                            continue
                        if qty <= 0:
                            continue
                        fallback_rows.append({
                            "产品名称": name,
                            "【颜色】": color,
                            "【仓库】": wh,
                            "库存数量": qty,
                        })
            except Exception:
                continue

        if not fallback_rows:
            return self._reply(f"未找到「{product_name}」的有库存记录")

        return self._reply(self._format_inventory_rows(fallback_rows, product_name))

    def _format_inventory_rows(self, rows: list[dict], keyword: str = "") -> str:
        """按仓库分组输出库存查询结果，只显示库存大于 0 的记录。"""
        warehouse_data = {}
        for row in rows:
            wh = row.get("【仓库】", "")
            qty = int(row.get("库存数量", 0) or 0)
            if qty <= 0:
                continue
            if wh not in warehouse_data:
                warehouse_data[wh] = []
            warehouse_data[wh].append((
                row.get("产品名称", ""),
                row.get("【颜色】", ""),
                qty,
            ))

        if not warehouse_data:
            return f"未找到「{keyword or '该商品'}」的有库存记录"

        total_qty = sum(qty for items in warehouse_data.values() for _, _, qty in items)
        total_skus = sum(len(items) for items in warehouse_data.values())
        lines = [f"库存查询：{keyword or '全部'}", f"总计：{total_skus} 条有库存记录，{total_qty} 套", ""]
        for wh_name, items in warehouse_data.items():
            warehouse_total = sum(qty for _, _, qty in items)
            lines.append(f"**{wh_name or '未知仓库'}**")
            lines.append("| 仓库 | 产品 | 颜色 | 库存 |")
            lines.append("| --- | --- | --- | ---: |")
            for name, color, qty in items:
                lines.append(f"| {wh_name or '未知仓库'} | {name} | {color or '-'} | {qty} |")
            lines.append(f"| {wh_name or '未知仓库'} | 合计 | {len(items)} 条记录 | {warehouse_total} |")
            lines.append("")
        return "\n".join(lines)

    def _normalize_inventory_keyword(self, product_name: str, user_input: str) -> str:
        """修正常见库存查询口语，避免把“礼盒”等泛词当商品名。"""
        text = f"{product_name} {user_input}"
        generic_words = ("礼盒", "盒子", "茶盒", "有什么", "有货", "库存")
        keyword = product_name
        for word in generic_words:
            keyword = keyword.replace(word, "")

        for word in ("吗", "嘛", "呢"):
            keyword = keyword.replace(word, "")

        keyword = re.sub(r"(?:3\s*两|2\s*两|(?<!二)三两|二两)", "二三两", keyword)
        keyword = re.sub(r"(?:0\.5\s*斤|半\s*斤)", "半斤", keyword)
        keyword = re.sub(r"(?:1\s*两|一\s*两)", "一两", keyword)
        keyword = re.sub(r"3\s*小盒", "三小盒", keyword)
        keyword = re.sub(r"6\s*小盒", "六小盒", keyword)
        keyword = re.sub(r"10\s*小盒", "十小盒", keyword)

        specs = ["二三两", "半斤", "一两", "三小盒", "六小盒", "十小盒", "长半斤"]
        for spec in specs:
            keyword = re.sub(rf"(?<!^)(?<!\s)({re.escape(spec)})", r" \1", keyword)
        keyword = keyword.strip()
        keyword = re.sub(r"\s+", " ", keyword)
        return keyword or product_name
