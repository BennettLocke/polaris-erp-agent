"""Sales order query workflow."""
import re
from src.skills.base import BaseWorkflow
from src.core.tools.caller import get_tool_caller
from src.core.session import SessionManager, get_current_session_id
from src.utils import get_logger

logger = get_logger("sjagent.skills.sales_query")


class SalesQueryWorkflow(BaseWorkflow):
    """Query recent sales orders and sales order details."""

    def __init__(self):
        self.caller = get_tool_caller()

    def execute(self, user_input: str, params: dict = None) -> dict:
        params = params or {}
        sales_id = params.get("sales_id") or self._extract_sales_id(user_input)
        customer = params.get("customer") or self._extract_customer(user_input)
        count = self._normalize_count(params.get("count") or self._extract_count(user_input))
        session = SessionManager(get_current_session_id())

        if sales_id:
            return self._reply(self._format_sales_detail(int(sales_id)))

        if not customer:
            last_customer = session.get_meta("last_sales_query_customer")
            if last_customer:
                customer = last_customer
            elif count > 1:
                return self._ask(
                    "请告诉我要查哪个客户的最近几单。",
                    {"partial_params": params},
                )
            else:
                last_order = session.get_meta("last_order")
                if last_order and last_order.get("type") == "sales":
                    return self._reply(self._format_sales_detail(int(last_order["id"])))
                return self._ask(
                    "请告诉我要查哪个客户或哪个销售单号，例如：查测试客户最近一次下单了什么。",
                    {"partial_params": params},
                )

        session.set_meta("last_sales_query_customer", customer)

        if not customer:
            last_order = session.get_meta("last_order")
            if last_order and last_order.get("type") == "sales":
                return self._reply(self._format_sales_detail(int(last_order["id"])))

        customer_id = params.get("customer_id")
        if not customer_id:
            resolved = self._resolve_customer(customer, params, count)
            if isinstance(resolved, dict) and resolved.get("status") == "ask":
                return resolved
            if not resolved:
                return self._reply(f"未找到准确匹配「{customer}」的客户。请换一个更完整的客户名再查。")
            customer_id, customer = resolved

        orders = self._get_recent_sales_orders(customer_id, count)
        if not orders:
            return self._reply(f"没有找到客户「{customer}」的销售单记录。")

        return self._reply(self._format_sales_orders(orders, customer))

    def resume(self, user_input: str, state: dict) -> dict:
        if state.get("pending_action") == "confirm_sales_query_customer":
            selected = self._select_candidate(user_input, state.get("candidates", []))
            if not selected:
                return self._ask(
                    "我没确认你选的是哪个客户，请回复序号或客户全称。",
                    state,
                )
            params = {**state.get("original_params", {})}
            params["customer"] = selected["name"]
            params["customer_id"] = selected["id"]
            if state.get("count"):
                params["count"] = state["count"]
            return self.execute(user_input, params)

        merged = {**state.get("partial_params", {}), **self._parse(user_input)}
        return self.execute(user_input, merged)

    def _parse(self, text: str) -> dict:
        return {
            "customer": self._extract_customer(text),
            "sales_id": self._extract_sales_id(text),
            "count": self._extract_count(text),
        }

    def _extract_count(self, text: str) -> int:
        m = re.search(r'(?:最近|近|最后)\s*(\d+|一|二|两|三|四|五|六|七|八|九|十)\s*(?:个|条|单)?', text)
        if not m:
            return 1
        return self._normalize_count(m.group(1))

    def _normalize_count(self, value) -> int:
        if isinstance(value, int):
            return max(1, min(value, 10))
        if isinstance(value, str) and value.isdigit():
            return max(1, min(int(value), 10))
        mapping = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
        return mapping.get(str(value), 1)

    def _extract_sales_id(self, text: str) -> int | None:
        m = re.search(r'(?:销售单|订单|单号)\D*(\d+)', text)
        return int(m.group(1)) if m else None

    def _extract_customer(self, text: str) -> str:
        cleaned = text
        for word in ["帮我", "帮看看", "帮", "看看", "查一下", "查下", "查", "最近一次", "最近", "客户"]:
            cleaned = cleaned.replace(word, " ")
        cleaned = re.sub(r'\d+\s*(?:个|条|单)', " ", cleaned)
        m = re.search(r'([^\s，,]+?)(?:下单|买了|订了|订单|销售单)', cleaned)
        if m:
            return m.group(1).strip()
        parts = [p for p in re.split(r'[\s，,]+', cleaned.strip()) if p and p not in {"下单", "订单", "销售单", "买了", "什么", "了什么", "东西", "内容", "详情"}]
        if parts:
            return parts[0]
        m = re.search(r'([^\s，,]+?)(?:最近一次)?(?:下单|买了|订了)', text)
        return m.group(1).strip() if m else ""

    def _resolve_customer(self, customer_name: str, params: dict, count: int):
        try:
            result = self.caller.call("customer_query", keyword=customer_name)
        except Exception as e:
            logger.warning(f"[SalesQuery] 客户查询失败: {e}")
            return None

        if not result or not isinstance(result, list):
            return None

        candidates = self._normalize_customer_candidates(result)
        if not candidates:
            return None

        target = self._normalize_customer_name(customer_name)
        exact = [c for c in candidates if self._normalize_customer_name(c["name"]) == target]
        if len(exact) == 1:
            return exact[0]["id"], exact[0]["name"]

        if len(candidates) == 1:
            only = candidates[0]
            only_norm = self._normalize_customer_name(only["name"])
            if target and (target in only_norm or only_norm in target):
                return only["id"], only["name"]

        return self._ask(
            self._format_customer_confirm_question(customer_name, exact or candidates[:5]),
            {
                "pending_action": "confirm_sales_query_customer",
                "candidates": exact or candidates[:5],
                "original_params": params,
                "count": count,
            },
        )

    def _normalize_customer_candidates(self, rows: list[dict]) -> list[dict]:
        candidates = []
        seen = set()
        for row in rows:
            if not isinstance(row, dict):
                continue
            cid = row.get("id") or row.get("customer_id") or row.get("company_id")
            name = (
                row.get("name")
                or row.get("company_name")
                or row.get("customer_name")
                or row.get("title")
                or row.get("short_name")
            )
            if not cid or not name:
                continue
            key = str(cid)
            if key in seen:
                continue
            seen.add(key)
            candidates.append({"id": int(cid), "name": str(name)})
        return candidates

    def _normalize_customer_name(self, name: str) -> str:
        return re.sub(r'[\s（）()【】\-_]+', "", str(name or "")).lower()

    def _resolve_customer_name_by_id(self, customer_id) -> str:
        if not customer_id:
            return ""
        key = str(customer_id)
        for keyword in (key, ""):
            try:
                rows = self.caller.call("customer_query", keyword=keyword)
            except Exception as e:
                logger.warning(f"[SalesQuery] 客户名称反查失败: customer_id={customer_id}, error={e}")
                rows = []
            for row in rows if isinstance(rows, list) else []:
                if not isinstance(row, dict):
                    continue
                row_id = row.get("id") or row.get("customer_id") or row.get("company_id")
                if str(row_id or "") != key:
                    continue
                name = (
                    row.get("name")
                    or row.get("company_name")
                    or row.get("customer_name")
                    or row.get("title")
                    or row.get("short_name")
                    or row.get("contacts_name")
                )
                if name:
                    return str(name).strip()
        return ""

    def _format_customer_confirm_question(self, keyword: str, candidates: list[dict]) -> str:
        lines = [f"「{keyword}」匹配到多个客户，请确认要查哪一个："]
        for idx, c in enumerate(candidates, 1):
            lines.append(f"{idx}. {c['name']}（ID {c['id']}）")
        return "\n".join(lines)

    def _select_candidate(self, text: str, candidates: list[dict]) -> dict | None:
        text = text.strip()
        m = re.search(r'\d+', text)
        if m:
            idx = int(m.group(0))
            if 1 <= idx <= len(candidates):
                return candidates[idx - 1]
            for c in candidates:
                if str(c["id"]) == str(idx):
                    return c
        target = self._normalize_customer_name(text)
        exact = [c for c in candidates if self._normalize_customer_name(c["name"]) == target]
        if len(exact) == 1:
            return exact[0]
        contains = [c for c in candidates if target and target in self._normalize_customer_name(c["name"])]
        if len(contains) == 1:
            return contains[0]
        return None

    def _get_recent_sales_orders(self, customer_id: int, count: int = 1) -> list[dict]:
        matched = []
        page_size = max(1, min(max(count, 10), 100))
        for page in range(1, 6):
            try:
                result = self.caller.call("sales_list", customer_id=customer_id, page=page, page_size=page_size)
            except Exception as e:
                logger.warning(f"[SalesQuery] 销售单列表查询失败: {e}")
                return matched
            if not isinstance(result, dict) or result.get("error"):
                return matched
            orders = self._extract_order_rows(result)
            if not orders:
                return matched
            for order in orders:
                matched.append(order)
                if len(matched) >= count:
                    return matched
            if len(orders) < page_size:
                return matched
        return matched

    def _get_recent_sales_orders_by_keyword(self, keyword: str, count: int = 1) -> list[dict]:
        try:
            result = self.caller.call("sales_list", keyword=keyword, page=1, page_size=count)
        except Exception as e:
            logger.warning(f"[SalesQuery] 关键词销售单查询失败: {e}")
            return []
        if not isinstance(result, dict) or result.get("error"):
            return []
        orders = self._extract_order_rows(result)
        return orders[:count] if isinstance(orders, list) else []

    def _extract_order_rows(self, result: dict) -> list[dict]:
        data = result.get("data", result)
        if isinstance(data, dict):
            return data.get("list") or data.get("data") or data.get("rows") or []
        return data if isinstance(data, list) else []

    def _format_sales_orders(self, orders: list[dict], customer_name: str) -> str:
        if len(orders) == 1:
            sid = self._get_order_id(orders[0])
            if not sid:
                return f"找到了客户「{customer_name}」的订单记录，但没有取到销售单号。"
            if isinstance(orders[0], dict) and orders[0].get("products"):
                return self._format_sales_card(orders[0], customer_name=customer_name)
            return self._format_sales_detail(int(sid), customer_name=customer_name)

        lines = [f"客户「{customer_name}」最近 {len(orders)} 单："]
        for idx, order in enumerate(orders, 1):
            sid = self._get_order_id(order)
            if not sid:
                lines.append(f"{idx}. 未取到销售单号：{str(order)[:120]}")
                continue
            lines.append(f"{idx}. {self._format_sales_card(order, customer_name=customer_name)}")
        return "\n\n".join(lines)

    def _format_sales_card(self, order: dict, customer_name: str = "") -> str:
        sid = self._get_order_id(order) or order.get("sales_no") or ""
        lines = [f"销售单 {sid} 的内容："]
        customer = order.get("customer_name") or order.get("company_name") or customer_name
        if customer:
            lines.append(f"客户：{customer}")
        items = order.get("products") or order.get("items") or order.get("detail") or []
        if not items:
            summary = order.get("product_summary") or ""
            if summary:
                lines.append(f"商品：{summary}")
        else:
            lines.append("商品：")
            for item in items:
                if not isinstance(item, dict):
                    lines.append(f"- {item}")
                    continue
                name = item.get("title") or item.get("product_name") or item.get("goods_name") or item.get("name") or "未知商品"
                spec = item.get("spec") or item.get("color") or item.get("goods_color") or ""
                qty = item.get("buy_number") or item.get("number") or item.get("quantity") or item.get("qty") or ""
                unit = item.get("unit_name") or item.get("unit") or ""
                price = item.get("price") or item.get("sale_price") or ""
                line = f"- {name}"
                if spec:
                    line += f" {spec}"
                if qty != "":
                    line += f" x {qty}{unit}"
                if price != "":
                    line += f"，单价 {price}"
                lines.append(line)
        total = order.get("total_price") or order.get("receivable_amount") or ""
        pay = order.get("pay_status_text") or ""
        if total or pay:
            lines.append(f"合计：{total or '-'}{('，付款：' + pay) if pay else ''}")
        return "\n".join(lines)

    def _get_order_id(self, order: dict):
        if not isinstance(order, dict):
            return None
        return order.get("id") or order.get("sales_id") or order.get("sales_no")

    def _format_sales_detail(self, sales_id: int, customer_name: str = "") -> str:
        try:
            result = self.caller.call("sales_detail", sales_id=sales_id)
        except Exception as e:
            return f"查询销售单 {sales_id} 失败：{e}"
        if not isinstance(result, dict) or result.get("error"):
            return f"查询销售单 {sales_id} 失败：{result}"
        if result.get("code") not in (None, 0):
            return f"查询销售单 {sales_id} 失败：{result.get('msg', result)}"

        data = result.get("data", result)
        if isinstance(data, dict):
            info = data.get("info") if isinstance(data.get("info"), dict) else {}
            actual_customer = str(
                data.get("customer_name")
                or data.get("company_name")
                or data.get("customer")
                or info.get("customer_name")
                or info.get("company_name")
                or info.get("customer")
                or ""
            )
            customer_id = (
                data.get("customer_id")
                or data.get("company_id")
                or info.get("customer_id")
                or info.get("company_id")
            )
            if (not actual_customer or actual_customer.isdigit()) and customer_id:
                actual_customer = self._resolve_customer_name_by_id(customer_id)
            customer_name = actual_customer or customer_name
            items = (
                data.get("products")
                or data.get("goods")
                or data.get("items")
                or data.get("detail")
                or data.get("details")
                or data.get("product_list")
                or info.get("detail")
                or info.get("details")
                or []
            )
        else:
            items = []

        lines = [f"销售单 {sales_id} 的内容："]
        if customer_name:
            lines.append(f"客户：{customer_name}")
        if not items:
            lines.append("没有解析到商品明细，原始返回如下：")
            lines.append(str(data)[:800])
            return "\n".join(lines)

        lines.append("商品：")
        for item in items:
            if not isinstance(item, dict):
                lines.append(f"- {item}")
                continue
            name = item.get("title") or item.get("product_name") or item.get("goods_name") or item.get("name") or "未知商品"
            spec = item.get("spec") or item.get("color") or item.get("goods_color") or ""
            qty = item.get("buy_number") or item.get("number") or item.get("quantity") or item.get("qty") or ""
            unit = item.get("unit_name") or item.get("unit") or ""
            price = item.get("price") or item.get("sale_price") or ""
            line = f"- {name}"
            if spec:
                line += f" {spec}"
            if qty != "":
                line += f" x {qty}{unit}"
            if price != "":
                line += f"，单价 {price}"
            lines.append(line)
        return "\n".join(lines)
