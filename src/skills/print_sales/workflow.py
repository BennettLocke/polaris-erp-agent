"""销售单打印流程。"""
import re

from src.core.session import SessionManager, get_current_session_id
from src.core.tools.caller import get_tool_caller
from src.skills.base import BaseWorkflow
from src.utils import get_logger

logger = get_logger("sjagent.skills.print_sales")


class PrintSalesWorkflow(BaseWorkflow):
    """Create print tasks for explicit sales IDs or a customer's latest order."""

    def __init__(self):
        self.caller = get_tool_caller()

    def execute(self, user_input: str, params: dict = None) -> dict:
        params = params or {}
        sales_id = params.get("sales_id") or self._extract_sales_id(user_input)
        customer = params.get("customer") or self._extract_customer(user_input)
        count = self._normalize_count(params.get("count") or self._extract_count(user_input))

        if sales_id:
            return self._print_sales_ids([int(sales_id)])

        if not customer:
            last_order = SessionManager(get_current_session_id()).get_meta("last_order")
            if last_order and last_order.get("type") == "sales" and last_order.get("id"):
                return self._print_sales_ids([int(last_order["id"])])
            return self._ask(
                "请告诉我要打印哪个客户的最新销售单，或直接说销售单号。",
                {"partial_params": params},
            )

        resolved = self._resolve_customer(customer, params, count)
        if isinstance(resolved, dict) and resolved.get("status") == "ask":
            return resolved
        if not resolved:
            return self._reply(f"未找到客户「{customer}」，无法打印最新销售单。")
        customer_id, customer_name = resolved

        orders = self._get_recent_sales_orders(customer_id, count)
        if not orders:
            return self._reply(f"没有找到客户「{customer_name}」的销售单，无法打印。")
        sales_ids = [int(oid) for oid in [self._get_order_id(order) for order in orders] if oid]
        if not sales_ids:
            return self._reply(f"找到了客户「{customer_name}」的订单记录，但没有取到销售单号。")
        return self._print_sales_ids(sales_ids, customer_name=customer_name)

    def resume(self, user_input: str, state: dict) -> dict:
        if state.get("pending_action") == "confirm_print_customer":
            selected = self._select_candidate(user_input, state.get("candidates", []))
            if not selected:
                return self._ask("我没确认你选的是哪个客户，请回复序号或客户全称。", state)
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

    def _print_sales_ids(self, sales_ids: list[int], customer_name: str = "") -> dict:
        done = []
        failed = []
        for sid in sales_ids:
            try:
                result = self.caller.call("sales_print_task", sales_id=sid)
            except Exception as e:
                failed.append(f"{sid}：{e}")
                continue
            if isinstance(result, dict) and result.get("error"):
                failed.append(f"{sid}：{result['error']}")
                continue
            if isinstance(result, dict) and result.get("code") not in (None, 0):
                failed.append(f"{sid}：{result.get('msg', result)}")
                continue
            done.append(str(sid))

        lines = []
        if done:
            prefix = f"客户「{customer_name}」" if customer_name else ""
            lines.append(f"已创建{prefix}销售单 {', '.join(done)} 的打印任务。")
        if failed:
            lines.append("以下销售单打印任务创建失败：" + "；".join(failed))
        return self._reply("\n".join(lines) if lines else "没有创建任何打印任务。")

    def _resolve_customer(self, customer_name: str, params: dict, count: int):
        if params.get("customer_id"):
            return int(params["customer_id"]), customer_name
        try:
            result = self.caller.call("customer_query", keyword=customer_name)
        except Exception as e:
            logger.warning(f"客户查询失败: {e}")
            return None
        candidates = self._normalize_customer_candidates(result if isinstance(result, list) else [])
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
                "pending_action": "confirm_print_customer",
                "candidates": exact or candidates[:5],
                "original_params": params,
                "count": count,
            },
        )

    def _get_recent_sales_orders(self, customer_id: int, count: int = 1) -> list[dict]:
        try:
            result = self.caller.call("sales_list", customer_id=customer_id, page=1, page_size=max(1, count))
        except Exception as e:
            logger.warning(f"销售单列表查询失败: {e}")
            return []
        orders = self._extract_order_rows(result if isinstance(result, dict) else {})
        if orders:
            return orders[:count]

        matched = []
        page_size = 100
        for page in range(1, 6):
            try:
                result = self.caller.call("sales_list", page=page, page_size=page_size)
            except Exception:
                return matched
            orders = self._extract_order_rows(result if isinstance(result, dict) else {})
            if not orders:
                return matched
            for order in orders:
                oid_customer = order.get("customer_id") or order.get("company_id")
                if str(oid_customer or "") == str(customer_id):
                    matched.append(order)
                    if len(matched) >= count:
                        return matched
            if len(orders) < page_size:
                return matched
        return matched

    def _extract_order_rows(self, result: dict) -> list[dict]:
        data = result.get("data", result)
        if isinstance(data, dict):
            return data.get("list") or data.get("data") or data.get("rows") or []
        return data if isinstance(data, list) else []

    def _get_order_id(self, order: dict):
        if not isinstance(order, dict):
            return None
        return order.get("id") or order.get("sales_id") or order.get("sales_no")

    def _extract_sales_id(self, text: str) -> int | None:
        m = re.search(r'(?:销售单|订单|单号)\D*(\d+)', text)
        return int(m.group(1)) if m else None

    def _extract_count(self, text: str) -> int:
        m = re.search(r'(?:最近|近|最后|最新)\s*(\d+|一|二|两|三|四|五|六|七|八|九|十)?\s*(?:个|条|单|张)?', text)
        if not m:
            return 1
        return self._normalize_count(m.group(1) or 1)

    def _normalize_count(self, value) -> int:
        if isinstance(value, int):
            return max(1, min(value, 10))
        if isinstance(value, str) and value.isdigit():
            return max(1, min(int(value), 10))
        mapping = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
        return mapping.get(str(value), 1)

    def _extract_customer(self, text: str) -> str:
        cleaned = text
        for word in [
            "帮我", "帮", "请", "打印一下", "打印", "打单", "最新一个", "最新一单",
            "最近一个", "最近一单", "最近一次", "最新", "最近", "最后", "客户", "的", "销售单", "订单", "单子",
        ]:
            cleaned = cleaned.replace(word, " ")
        cleaned = re.sub(r'\d+\s*(?:个|条|单|张)?', " ", cleaned)
        parts = [p for p in re.split(r'[\s，,]+', cleaned.strip()) if p]
        return parts[0] if parts else ""

    def _normalize_customer_candidates(self, rows: list[dict]) -> list[dict]:
        candidates = []
        seen = set()
        for row in rows:
            if not isinstance(row, dict):
                continue
            cid = row.get("id") or row.get("customer_id") or row.get("company_id")
            name = row.get("name") or row.get("company_name") or row.get("customer_name") or row.get("title")
            if not cid or not name or str(cid) in seen:
                continue
            seen.add(str(cid))
            candidates.append({"id": int(cid), "name": str(name)})
        return candidates

    def _normalize_customer_name(self, name: str) -> str:
        return re.sub(r'[\s（）()【】\-_]+', "", str(name or "")).lower()

    def _format_customer_confirm_question(self, keyword: str, candidates: list[dict]) -> str:
        lines = [f"「{keyword}」匹配到多个客户，请确认要打印哪一个："]
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
        return contains[0] if len(contains) == 1 else None
