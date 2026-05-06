"""销售单管理流程（删除订单等）- LLM理解意图"""
import re
from src.skills.base import BaseWorkflow
from src.core.tools.caller import get_tool_caller
from src.core.session import SessionManager, get_current_session_id
from src.utils import get_logger

logger = get_logger("sjagent.skills.sales_manage")

# LLM 理解删除意图的 prompt
DELETE_INTENT_PROMPT = """你是肆计包装-北极星订单管理机器人，名字叫北极星。根据用户输入，理解用户想删除哪些销售单。

返回JSON格式：
{
  "action": "delete",
  "target": "single" | "multiple" | "customer_all" | "last_n" | "unknown",
  "customer": "客户名|null",
  "sales_ids": [142, 143] | [],
  "count": 2 | null,
  "original_input": "用户原始输入"
}

规则：
- "删除销售单142" → target=single, sales_ids=[142]
- "删除142和143" → target=multiple, sales_ids=[142,143]
- "删除测试客户的所有销售单" → target=customer_all, customer="测试客户"
- "删除最后2个订单" → target=last_n, count=2
- "删除这个订单" → target=single, 需要从对话历史找最近的销售单号
- 如果用户输入中没有明确的销售单号或客户名，target=unknown

请只返回JSON。"""


class SalesManageWorkflow(BaseWorkflow):
    """销售单管理 - LLM理解意图"""

    def __init__(self):
        self.caller = get_tool_caller()

    def execute(self, user_input: str, params: dict = None) -> dict:
        """执行删除请求 - 优先用 LLM 预提取参数"""
        session = SessionManager(get_current_session_id())
        history = session.get_history()
        last_order = session.get_meta("last_order")

        workflow_ids = self._extract_workflow_delete_ids(user_input)
        if workflow_ids:
            return self._ask_confirm_workflow(workflow_ids)

        if self._is_deictic_delete(user_input) and last_order:
            if last_order.get("type") == "workflow":
                return self._ask_confirm_workflow([str(last_order.get("id"))])
            if last_order.get("type") == "sales":
                return self._ask_confirm([str(last_order.get("id"))])

        if params and params.get("action") == "modify":
            sales_id = params.get("sales_id")
            target = f" {sales_id}" if sales_id else ""
            return self._reply(
                f"销售单{target}不能直接由我静默修改，避免库存和金额被改乱。请告诉我要改客户、商品、颜色、数量还是价格；如果系统没有修改接口，我会建议先删除原销售单再重新开一张。"
            )

        # 优先使用预提取参数
        if params and params.get("action") == "delete":
            intent = params
        else:
            intent = self._understand_intent(user_input, history)
        logger.info(f"[SalesManage] LLM理解意图: {intent}")

        target = intent.get("target", "unknown")

        # 2. 根据意图类型处理
        if target == "single":
            sales_ids = [str(sid) for sid in intent.get("sales_ids", []) if sid]
            if not sales_ids:
                # 从历史中找最近的销售单号
                sales_ids = self._get_recent_sales_ids(history, 1)
            if not sales_ids:
                return self._reply("请提供要删除的销售单号，例如：删除销售单142")
            return self._ask_confirm(sales_ids)

        elif target == "multiple":
            sales_ids = [str(sid) for sid in intent.get("sales_ids", []) if sid]
            if not sales_ids:
                return self._reply("请提供要删除的销售单号")
            return self._ask_confirm(sales_ids)

        elif target == "customer_all":
            customer = intent.get("customer")
            if not customer:
                return self._reply("请告诉我要删除哪个客户的订单")
            return self._handle_customer_delete(customer)

        elif target == "last_n":
            count = intent.get("count", 1)
            sales_ids = self._get_recent_sales_ids(history, count)
            if not sales_ids:
                return self._reply("没有找到最近的销售单")
            return self._ask_confirm(sales_ids)

        else:
            # unknown - 从历史中找最近的销售单号
            sales_ids = self._get_recent_sales_ids(history, 1)
            if sales_ids:
                return self._ask_confirm(sales_ids)
            return self._reply("请提供要删除的销售单号，例如：删除销售单142")

    def _handle_customer_delete(self, customer: str) -> dict:
        """处理删除客户所有订单的请求"""
        # 1. 先查客户ID
        customer_id = self._query_customer_id(customer)
        if not customer_id:
            return self._reply(f"未找到客户「{customer}」")

        # 2. 用customer_id查询销售单
        sales_ids = []
        try:
            result = self.caller.call("sales_list", customer_id=customer_id, page_size=200)
            if isinstance(result, dict) and "error" not in result:
                data = result.get("data", result)
                orders = data.get("list", []) if isinstance(data, dict) else data

                for order in orders:
                    sid = order.get("id") or order.get("sales_no")
                    if sid:
                        sales_ids.append(str(sid))

                logger.info(f"[SalesManage] sales_list查询成功: 客户={customer}(id={customer_id}), 找到{len(sales_ids)}个订单")
        except Exception as e:
            logger.error(f"[SalesManage] sales_list查询失败: {e}")
            return self._reply(f"查询销售单失败：{str(e)}，请稍后重试")

        if not sales_ids:
            return self._reply(f"客户「{customer}」没有销售单")

        # 确认删除
        ids_str = "、".join(sales_ids[:10])
        more = f" 等共{len(sales_ids)}个" if len(sales_ids) > 10 else ""
        return self._ask(
            f"确认要删除客户「{customer}」的 {len(sales_ids)} 个销售单吗？\n{ids_str}{more}\n删除后库存会自动恢复。",
            {"sales_ids": sales_ids, "customer": customer}
        )

    def _query_customer_id(self, customer_name: str) -> int | None:
        """查询客户ID"""
        try:
            result = self.caller.call("customer_query", keyword=customer_name)
            if result and isinstance(result, list) and len(result) > 0:
                cid = result[0].get("id")
                if cid:
                    return int(cid)
        except Exception as e:
            logger.warning(f"[SalesManage] 客户查询失败: {e}")
        return None

    def _ask_confirm(self, sales_ids: list[str]) -> dict:
        """确认删除"""
        if len(sales_ids) == 1:
            return self._ask(
                f"确认要删除销售单 {sales_ids[0]} 吗？删除后库存会自动恢复。",
                {"sales_ids": sales_ids}
            )
        else:
            ids_str = "、".join(sales_ids)
            return self._ask(
                f"确认要删除以下 {len(sales_ids)} 个销售单吗？\n{ids_str}\n删除后库存会自动恢复。",
                {"sales_ids": sales_ids}
            )

    def _ask_confirm_workflow(self, workflow_ids: list[str]) -> dict:
        """确认删除工作流订单"""
        if len(workflow_ids) == 1:
            return self._ask(
                f"确认要删除工作流订单 {workflow_ids[0]} 吗？这不会回滚销售库存。",
                {"workflow_ids": workflow_ids, "delete_type": "workflow"}
            )
        ids_str = "、".join(workflow_ids)
        return self._ask(
            f"确认要删除以下 {len(workflow_ids)} 个工作流订单吗？\n{ids_str}",
            {"workflow_ids": workflow_ids, "delete_type": "workflow"}
        )

    def resume(self, user_input: str, state: dict) -> dict:
        """用户确认删除"""
        if state.get("delete_type") == "workflow":
            workflow_ids = state.get("workflow_ids", [])
            if not workflow_ids:
                return self._reply("工作流订单号丢失，请重新操作。")
            if not self._is_confirmation(user_input):
                return self._reply("已取消删除操作。")

            results = []
            errors = []
            for wid in workflow_ids:
                try:
                    result = self.caller.call("workflow_order_delete", ids=str(wid))
                    if isinstance(result, dict) and result.get("error"):
                        errors.append(f"{wid}: {result['error']}")
                    elif isinstance(result, dict) and result.get("code") not in (None, 0):
                        errors.append(f"{wid}: {result.get('msg', result)}")
                    else:
                        results.append(str(wid))
                except Exception as e:
                    errors.append(f"{wid}: {str(e)}")

            lines = []
            if results:
                ids_str = "、".join(results)
                lines.append(f"已删除 {len(results)} 个工作流订单：{ids_str}。")
            if errors:
                lines.append("以下删除失败：")
                lines.extend(errors)
            return self._reply("\n".join(lines))

        sales_ids = state.get("sales_ids", [])
        if not sales_ids:
            return self._reply("订单号丢失，请重新操作。")

        # 判断是否是确认
        if not self._is_confirmation(user_input):
            return self._reply("已取消删除操作。")

        # 执行批量删除
        results = []
        errors = []
        for sid in sales_ids:
            try:
                self.caller.call("sales_delete", ids=str(sid))
                results.append(sid)
            except Exception as e:
                errors.append(f"{sid}: {str(e)}")

        # 汇报结果
        lines = []
        if results:
            ids_str = "、".join(results)
            lines.append(f"已删除 {len(results)} 个销售单：{ids_str}，库存已自动恢复。")
        if errors:
            lines.append("以下删除失败：")
            lines.extend(errors)
        return self._reply("\n".join(lines))

    def _is_confirmation(self, user_input: str) -> bool:
        """判断是否为确认回复"""
        text = user_input.strip()
        # 简短回复（<=8字）且包含肯定词
        if len(text) <= 8:
            confirm_words = ["确认", "是", "对", "好的", "删", "删除", "yes", "ok"]
            return any(w in text for w in confirm_words)
        return False

    def _is_deictic_delete(self, user_input: str) -> bool:
        """是否是“删除这个/这订单”这类依赖上下文的删除请求。"""
        text = user_input.strip()
        if "删除" not in text and "删" not in text:
            return False
        return any(w in text for w in ["这个", "这订单", "这个订单", "这单", "这个单", "刚才", "上一单"])

    def _extract_workflow_delete_ids(self, user_input: str) -> list[str]:
        """Explicit workflow-order deletion requests should not be treated as sales deletes."""
        if "工作流" not in user_input or not any(w in user_input for w in ["删", "删除", "作废"]):
            return []
        return re.findall(r'\d+', user_input)

    def _understand_intent(self, user_input: str, history: list[dict]) -> dict:
        """用LLM理解用户的删除意图"""
        try:
            from src.core.llm import llm_json
            result = llm_json(DELETE_INTENT_PROMPT, user_input, history)
            return result
        except Exception as e:
            logger.warning(f"[SalesManage] LLM理解意图失败: {e}")
            return {"target": "unknown"}

    def _get_recent_sales_ids(self, history: list[dict], count: int) -> list[str]:
        """从对话历史中提取最近N个销售单号"""
        sales_ids = []
        for msg in reversed(history):
            content = msg.get("content", "")
            if msg.get("role") == "assistant":
                # 匹配 "销售单号：142" 格式
                matches = re.findall(r'销售单[^\d]*(\d+)', content)
                for mid in matches:
                    if mid not in sales_ids:
                        sales_ids.append(mid)
                        if len(sales_ids) >= count:
                            return sales_ids
        return sales_ids[:count] if sales_ids else []

    def _get_all_sales_ids_from_history(self) -> list[str]:
        """从对话历史中提取所有销售单号"""
        session = SessionManager(get_current_session_id())
        history = session.get_history()
        sales_ids = []
        for msg in history:
            content = msg.get("content", "")
            if msg.get("role") == "assistant":
                # 匹配 "销售单号：142" 格式
                matches = re.findall(r'销售单[^\d]*(\d+)', content)
                for mid in matches:
                    if mid not in sales_ids:
                        sales_ids.append(mid)
        return sales_ids
