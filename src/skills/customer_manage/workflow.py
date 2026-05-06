"""客户管理流程。"""
import re

from src.core.tools.caller import get_tool_caller
from src.skills.base import BaseWorkflow
from src.utils import get_logger

logger = get_logger("sjagent.skills.customer_manage")


class CustomerManageWorkflow(BaseWorkflow):
    """创建客户，保留确认状态，避免被闲聊流程吞掉。"""

    def __init__(self):
        self.caller = get_tool_caller()

    def execute(self, user_input: str, params: dict = None) -> dict:
        params = params or {}
        name = self._clean_name(params.get("name") or params.get("customer") or self._extract_name(user_input))
        contacts_name = (params.get("contacts_name") or params.get("contact") or "").strip()
        contacts_tel = (params.get("contacts_tel") or params.get("phone") or "").strip()

        if not name:
            return self._ask(
                "请告诉我要创建的客户名称。",
                {"pending_action": "collect_customer_name", "customer": "", "contacts_name": "", "contacts_tel": ""},
            )

        if self._is_create_confirm(user_input):
            return self._create_customer(name, contacts_name, contacts_tel)

        return self._ask(
            self._format_confirm_question(name, contacts_name, contacts_tel),
            {
                "pending_action": "confirm_create_customer",
                "customer": name,
                "contacts_name": contacts_name,
                "contacts_tel": contacts_tel,
            },
        )

    def resume(self, user_input: str, state: dict) -> dict:
        action = state.get("pending_action")
        text = user_input.strip()

        if action == "collect_customer_name":
            name = self._clean_name(self._extract_name(text) or text)
            if not name:
                return self._ask("请告诉我要创建的客户名称。", state)
            if self._is_create_confirm(text):
                return self._create_customer(name, "", "")
            return self._ask(
                self._format_confirm_question(name, "", ""),
                {"pending_action": "confirm_create_customer", "customer": name, "contacts_name": "", "contacts_tel": ""},
            )

        if action == "confirm_create_customer":
            if self._is_no(text):
                return self._reply("已取消创建客户。")
            name = state.get("customer", "")
            contacts_name = state.get("contacts_name", "")
            contacts_tel = state.get("contacts_tel", "")
            if not self._is_yes(text):
                updated = self._merge_extra_info(text, name, contacts_name, contacts_tel)
                return self._ask(
                    self._format_confirm_question(updated["customer"], updated["contacts_name"], updated["contacts_tel"]),
                    {"pending_action": "confirm_create_customer", **updated},
                )
            return self._create_customer(name, contacts_name, contacts_tel)

        return self._reply("当前没有需要继续的客户创建操作。")

    def _create_customer(self, name: str, contacts_name: str = "", contacts_tel: str = "") -> dict:
        name = self._clean_name(name)
        if not name:
            return self._ask(
                "请告诉我要创建的客户名称。",
                {"pending_action": "collect_customer_name", "customer": "", "contacts_name": "", "contacts_tel": ""},
            )
        existing = self._query_customer(name)
        if existing:
            cid = existing.get("id") or existing.get("customer_id")
            return self._reply(f"客户「{name}」已存在，客户ID：{cid}。")

        result = self.caller.call(
            "customer_create",
            name=name,
            contacts_name=contacts_name,
            contacts_tel=contacts_tel,
        )
        if isinstance(result, dict) and result.get("error"):
            return self._reply(f"创建客户失败：{result['error']}")
        if isinstance(result, dict) and result.get("code") not in (None, 0):
            return self._reply(f"创建客户失败：{result.get('msg', result)}")

        created = self._query_customer(name)
        cid = created.get("id") if created else self._extract_created_id(result)
        suffix = f"，客户ID：{cid}" if cid else ""
        return self._reply(f"客户「{name}」创建成功{suffix}。")

    def _query_customer(self, name: str) -> dict | None:
        try:
            rows = self.caller.call("customer_query", keyword=name)
        except Exception as e:
            logger.warning(f"客户查询失败: {e}")
            return None
        for row in rows or []:
            row_name = str(row.get("name") or row.get("company_name") or "")
            if row_name == name:
                return row
        return rows[0] if rows and len(rows) == 1 else None

    def _extract_created_id(self, result) -> str:
        if not isinstance(result, dict):
            return ""
        data = result.get("data")
        if isinstance(data, dict):
            return str(data.get("id") or data.get("customer_id") or "")
        if isinstance(data, (str, int)):
            return str(data)
        return str(result.get("id") or "")

    def _format_confirm_question(self, name: str, contacts_name: str, contacts_tel: str) -> str:
        lines = [f"确认创建客户「{name}」吗？"]
        if contacts_name:
            lines.append(f"联系人：{contacts_name}")
        if contacts_tel:
            lines.append(f"电话：{contacts_tel}")
        lines.append("回复「确认」创建；如果没有联系人和电话，也可以回复「没有了」。")
        return "\n".join(lines)

    def _extract_name(self, text: str) -> str:
        value = text.strip()
        value = re.sub(r"(?:帮我|给我|请|麻烦|把|将)", " ", value)
        value = re.sub(r"(?:创建|新增|添加|新建|建立)\s*(?:一个)?\s*(?:客户|客户档案)?", " ", value)
        value = re.sub(r"(?:客户|客户名|名称)[:：]\s*", " ", value)
        value = re.sub(r"(?:创建吧|创建一下|确认创建|建吧|吧|啊|呀)", " ", value)
        value = re.sub(r"\s+", " ", value).strip(" ，,。")
        return value

    def _clean_name(self, name: str) -> str:
        value = str(name or "").strip()
        for word in ["客户", "创建", "新增", "添加", "新建", "建立", "创建吧", "确认", "没有了", "没了"]:
            value = value.replace(word, " ")
        return re.sub(r"\s+", "", value).strip("，,。")

    def _merge_extra_info(self, text: str, name: str, contacts_name: str, contacts_tel: str) -> dict:
        phone = contacts_tel
        m = re.search(r"1[3-9]\d{9}", text)
        if m:
            phone = m.group(0)
        contact = contacts_name
        cm = re.search(r"(?:联系人|老板|对接人)[:：]?\s*([\u4e00-\u9fa5A-Za-z]{2,6})", text)
        if cm:
            contact = cm.group(1)
        return {"customer": name, "contacts_name": contact, "contacts_tel": phone}

    def _is_create_confirm(self, text: str) -> bool:
        return any(w in text for w in ["创建吧", "确认创建", "直接创建", "建吧"])

    def _is_yes(self, text: str) -> bool:
        value = text.strip().lower()
        if self._is_no(value):
            return False
        return any(w in value for w in ["确认", "可以", "好的", "好", "是", "对", "创建", "创建吧", "没有了", "没了", "无", "yes", "ok"])

    def _is_no(self, text: str) -> bool:
        return any(w in text for w in ["取消", "不要", "不用", "不创建", "算了", "no"])
