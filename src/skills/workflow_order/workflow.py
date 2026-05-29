"""Workflow order creation flow."""
import re
from src.skills.base import BaseWorkflow
from src.core.tools.caller import get_tool_caller
from src.core.session import SessionManager, get_current_session_id
from src.utils import get_logger

logger = get_logger("sjagent.skills.workflow_order")


class WorkflowOrderWorkflow(BaseWorkflow):
    """Create ERP workflow orders without opening a sales order."""

    def __init__(self):
        self.caller = get_tool_caller()

    def execute(self, user_input: str, params: dict = None) -> dict:
        action = (params or {}).get("action")
        if action == "query":
            return self._query(user_input, params)
        if action == "delete":
            return self._ask_delete_confirm(user_input, params or {})

        parsed = self._parse(user_input, params or {})

        missing = []
        if not parsed.get("customer"):
            missing.append("客户")
        if not parsed.get("goods_name"):
            missing.append("商品")
        if not parsed.get("quantity"):
            missing.append("数量")
        if missing:
            return self._ask(
                f"创建工作流订单还缺：{'、'.join(missing)}。请补充客户、商品、颜色和数量。",
                {"pending_action": "collect_workflow_order", "partial_params": parsed},
            )

        return self._confirm_create(parsed)

    def resume(self, user_input: str, state: dict) -> dict:
        if state.get("pending_action") == "confirm_create_workflow_order":
            if not self._is_confirmation(user_input):
                return self._reply("已取消创建工作流订单。")
            return self._create(state.get("parsed") or {})

        if state.get("pending_action") == "confirm_image_workflow_orders":
            if not self._is_confirmation(user_input):
                return self._reply("已取消创建工作流订单，没有写入系统。")
            create_result = self._create_many(state.get("parsed_list") or [])
            parsed_list = state.get("parsed_list") or []
            order_params = self._ensure_order_customer(state.get("order_params") or {}, parsed_list)
            created_ids = create_result.get("workflow_order_ids") or []
            if created_ids:
                order_params = dict(order_params)
                order_params.setdefault("workflow_order_id", created_ids[0])
            if order_params.get("products"):
                from src.skills.order_flow.workflow import OrderFlowWorkflow
                order_result = OrderFlowWorkflow().execute("图片识别结果确认开单", params=order_params)
                if order_result.get("status") == "ask":
                    order_result["intent"] = "order"
                    order_result["question"] = create_result.get("reply", "") + "\n\n" + order_result["question"]
                    return order_result
                return self._reply(create_result.get("reply", "") + "\n\n" + order_result.get("reply", "开单流程已处理。"))
            optional_order_params = self._ensure_order_customer(state.get("optional_order_params") or {}, parsed_list)
            if created_ids:
                optional_order_params = dict(optional_order_params)
                optional_order_params.setdefault("workflow_order_id", created_ids[0])
            if optional_order_params.get("products"):
                return {
                    "status": "ask",
                    "intent": "order",
                    "question": (
                        create_result.get("reply", "")
                        + "\n\n备注里没有看到「开单」或「下单」，是否需要继续开销售单？\n"
                        + "确认后会进入销售单确认；取消则只保留工作流订单。"
                    ),
                    "state": {
                        "pending_action": "confirm_image_sales",
                        "order_params": optional_order_params,
                    },
                }
            return create_result

        if state.get("pending_action") == "confirm_workflow_delete" or state.get("delete_type") == "workflow":
            workflow_ids = state.get("workflow_ids", [])
            if not workflow_ids:
                return self._reply("工作流订单号丢失，请重新操作。")
            if not self._is_confirmation(user_input):
                return self._reply("已取消删除操作。")
            return self._delete(workflow_ids)

        if state.get("pending_action") == "collect_workflow_delete":
            workflow_ids = self._extract_delete_ids(user_input, state.get("partial_params", {}))
            if not workflow_ids:
                return self._ask(
                    "请告诉我要删除哪个工作流订单号，例如：删除工作流订单139",
                    {"pending_action": "collect_workflow_delete", "partial_params": {"action": "delete"}},
                )
            return self._confirm_delete(workflow_ids)

        partial = state.get("partial_params", {})
        parsed = self._parse(user_input, partial)
        merged = {**partial, **{k: v for k, v in parsed.items() if v not in (None, "", [])}}

        missing = []
        if not merged.get("customer"):
            missing.append("客户")
        if not merged.get("goods_name"):
            missing.append("商品")
        if not merged.get("quantity"):
            missing.append("数量")
        if missing:
            return self._ask(
                f"创建工作流订单还缺：{'、'.join(missing)}。请继续补充。",
                {"pending_action": "collect_workflow_order", "partial_params": merged},
            )

        return self._confirm_create(merged)

    def _ensure_order_customer(self, order_params: dict, parsed_list: list[dict]) -> dict:
        params = dict(order_params or {})
        customer = str(params.get("customer") or params.get("customer_name") or "").strip()
        customers = [
            str(item.get("customer") or item.get("customer_name") or "").strip()
            for item in parsed_list or []
            if isinstance(item, dict) and str(item.get("customer") or item.get("customer_name") or "").strip()
        ]
        customers = list(dict.fromkeys(customers))
        if not customer and customers:
            customer = customers[0]
        if customer:
            params["customer"] = customer
            params.setdefault("customer_name", customer)
        if customers and not params.get("customers"):
            params["customers"] = customers
        return params

    def _ask_delete_confirm(self, user_input: str, params: dict) -> dict:
        workflow_ids = self._extract_delete_ids(user_input, params)
        if not workflow_ids:
            return self._ask(
                "请告诉我要删除哪个工作流订单号，例如：删除工作流订单139",
                {"pending_action": "collect_workflow_delete", "partial_params": {"action": "delete"}},
            )
        return self._confirm_delete(workflow_ids)

    def _confirm_delete(self, workflow_ids: list[str]) -> dict:
        workflow_ids = [str(wid) for wid in workflow_ids if str(wid).strip()]
        if len(workflow_ids) == 1:
            return self._ask(
                f"确认要删除工作流订单 {workflow_ids[0]} 吗？这不会回滚销售库存。",
                {"pending_action": "confirm_workflow_delete", "workflow_ids": workflow_ids, "delete_type": "workflow"},
            )
        ids_str = "、".join(workflow_ids)
        return self._ask(
            f"确认要删除以下 {len(workflow_ids)} 个工作流订单吗？\n{ids_str}\n这不会回滚销售库存。",
            {"pending_action": "confirm_workflow_delete", "workflow_ids": workflow_ids, "delete_type": "workflow"},
        )

    def _delete(self, workflow_ids: list[str]) -> dict:
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
            lines.append(f"已删除 {len(results)} 个工作流订单：{'、'.join(results)}。")
        if errors:
            lines.append("以下删除失败：")
            lines.extend(errors)
        return self._reply("\n".join(lines) if lines else "没有执行删除。")

    def _extract_delete_ids(self, user_input: str, params: dict) -> list[str]:
        raw_ids = params.get("workflow_ids") or params.get("ids") or []
        if isinstance(raw_ids, (str, int)):
            raw_ids = re.findall(r'\d+', str(raw_ids))
        ids = [str(wid) for wid in raw_ids if str(wid).strip()]
        order_id = params.get("order_id")
        if order_id:
            ids.append(str(order_id))
        ids.extend(re.findall(r'\d+', user_input or ""))
        deduped = []
        for wid in ids:
            if wid not in deduped:
                deduped.append(wid)
        return deduped

    def _is_confirmation(self, user_input: str) -> bool:
        text = user_input.strip().lower()
        if len(text) <= 8:
            return any(w in text for w in ["确认", "是", "对", "好的", "删", "删除", "yes", "ok"])
        return False

    def _is_confirmation(self, user_input: str) -> bool:
        text = user_input.strip().lower()
        if len(text) <= 8:
            return any(w in text for w in ["确认", "是", "对", "好的", "可以", "执行", "创建", "删除", "yes", "ok"])
        return False

    def _query(self, user_input: str, params: dict) -> dict:
        order_id = params.get("order_id") or self._extract_order_id(user_input)
        if order_id:
            return self._reply(self._format_workflow_detail(int(order_id)))

        count = self._normalize_count(params.get("count") or self._extract_count(user_input))
        keyword = params.get("keyword") or self._extract_query_keyword(user_input)
        try:
            result = self.caller.call("workflow_order_list", keyword=keyword or None, page=1, page_size=count)
        except Exception as e:
            return self._reply(f"查询工作流订单失败：{e}")

        if not isinstance(result, dict) or result.get("error"):
            return self._reply(f"查询工作流订单失败：{result}")
        if result.get("code") not in (None, 0):
            return self._reply(f"查询工作流订单失败：{result.get('msg', result)}")

        data = result.get("data", result)
        if isinstance(data, dict):
            orders = data.get("list") or data.get("data") or data.get("rows") or []
        else:
            orders = data if isinstance(data, list) else []
        if not orders:
            desc = f"「{keyword}」相关的" if keyword else ""
            return self._reply(f"没有找到{desc}工作流订单。")

        orders = orders[:count]
        if len(orders) == 1:
            oid = self._get_order_id(orders[0])
            if oid:
                return self._reply(self._format_workflow_detail(int(oid)))

        title = f"最近 {len(orders)} 个工作流订单："
        if keyword:
            title = f"「{keyword}」相关的{title}"
        lines = [title]
        for idx, order in enumerate(orders, 1):
            lines.append(self._format_workflow_summary(order, idx))
        return self._reply("\n".join(lines))

    def _format_workflow_detail(self, order_id: int) -> str:
        try:
            result = self.caller.call("workflow_order_detail", order_id=order_id)
        except Exception as e:
            return f"查询工作流订单 {order_id} 失败：{e}"
        if not isinstance(result, dict) or result.get("error"):
            return f"查询工作流订单 {order_id} 失败：{result}"
        if result.get("code") not in (None, 0):
            return f"查询工作流订单 {order_id} 失败：{result.get('msg', result)}"

        data = result.get("data", result)
        if not isinstance(data, dict):
            return f"工作流订单 {order_id}：{data}"

        SessionManager(get_current_session_id()).set_meta("last_order", {
            "type": "workflow",
            "id": str(order_id),
            "customer": data.get("customer_name") or data.get("company_name") or data.get("customer") or "",
            "goods_name": data.get("goods_name") or data.get("product_name") or data.get("title") or "",
        })

        lines = [f"工作流订单 {order_id}："]
        customer = data.get("customer_name") or data.get("company_name") or data.get("customer")
        goods = data.get("goods_name") or data.get("product_name") or data.get("title") or data.get("name")
        color = data.get("goods_color") or data.get("color") or data.get("spec")
        qty = data.get("order_quantity") or data.get("quantity") or data.get("qty") or data.get("number")
        status = data.get("status_name") or data.get("status_text") or data.get("status")
        if customer:
            lines.append(f"客户：{customer}")
        if goods:
            lines.append(f"商品：{goods}{(' ' + str(color)) if color else ''}")
        if qty:
            lines.append(f"数量：{qty}")
        if status not in (None, ""):
            lines.append(f"状态：{status}")
        if len(lines) == 1:
            lines.append(str(data)[:800])
        return "\n".join(lines)

    def _format_workflow_summary(self, order: dict, idx: int) -> str:
        if not isinstance(order, dict):
            return f"{idx}. {order}"
        oid = self._get_order_id(order) or ""
        customer = order.get("customer_name") or order.get("company_name") or order.get("customer") or ""
        goods = order.get("goods_name") or order.get("product_name") or order.get("title") or order.get("name") or ""
        color = order.get("goods_color") or order.get("color") or order.get("spec") or ""
        qty = order.get("order_quantity") or order.get("quantity") or order.get("qty") or order.get("number") or ""
        status = order.get("status_name") or order.get("status_text") or order.get("status") or ""
        parts = [f"{idx}.", f"单号 {oid}" if oid else "未取到单号"]
        if customer:
            parts.append(f"客户：{customer}")
        if goods:
            parts.append(f"商品：{goods}{(' ' + str(color)) if color else ''}")
        if qty:
            parts.append(f"数量：{qty}")
        if status not in (None, ""):
            parts.append(f"状态：{status}")
        return "，".join(parts)

    def _get_order_id(self, order: dict):
        if not isinstance(order, dict):
            return None
        return order.get("id") or order.get("order_id") or order.get("workflow_order_id")

    def _extract_order_id(self, text: str) -> int | None:
        m = re.search(r'(?:工作流订单|工作流单|设计稿订单|单号)\D*(\d+)', text)
        return int(m.group(1)) if m else None

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

    def _extract_query_keyword(self, text: str) -> str:
        cleaned = text
        for word in ["帮我", "帮看看", "查看", "看看", "看下", "查询", "查一下", "查下", "查", "最近", "最后", "工作流订单", "工作流单", "设计稿订单", "的"]:
            cleaned = cleaned.replace(word, " ")
        cleaned = re.sub(r'\d+\s*(?:个|条|单)?', " ", cleaned)
        parts = [p for p in re.split(r'[\s，,]+', cleaned.strip()) if p and p not in {"一个", "一条", "一单", "列表", "详情"}]
        return parts[0] if parts else ""

    def _confirm_create(self, parsed: dict) -> dict:
        question = "\n".join([
            "请确认是否创建工作流订单：",
            f"客户：{parsed.get('customer') or '未填写'}",
            f"商品：{parsed.get('goods_name') or '未填写'}",
            f"颜色：{parsed.get('color') or '未填写'}",
            f"数量：{parsed.get('quantity') or 1}",
            "确认后才会真正写入工作流订单。",
        ])
        return self._ask(
            question,
            {"pending_action": "confirm_create_workflow_order", "parsed": parsed},
        )

    def _create_many(self, parsed_list: list[dict]) -> dict:
        if not parsed_list:
            return self._reply("没有可创建的工作流订单。")

        ok_lines = []
        errors = []
        created_ids = []
        for idx, parsed in enumerate(parsed_list, 1):
            goods_name = str(parsed.get("goods_name") or "").strip()
            if not goods_name:
                errors.append(f"{idx}. 未识别到商品，已跳过")
                continue
            try:
                result = self.caller.call(
                    "workflow_order_save",
                    customer_name=parsed.get("customer") or "散客",
                    goods_name=goods_name,
                    order_quantity=int(parsed.get("quantity") or 1),
                    color=parsed.get("color", ""),
                    order_images=parsed.get("order_images") or [],
                    is_screen_print=1 if parsed.get("is_screen_print") else 0,
                    remark=parsed.get("remark", ""),
                )
            except Exception as e:
                errors.append(f"{idx}. {goods_name}：{e}")
                continue

            if isinstance(result, dict) and result.get("error"):
                errors.append(f"{idx}. {goods_name}：{result['error']}")
                continue
            if isinstance(result, dict) and result.get("code") not in (None, 0):
                errors.append(f"{idx}. {goods_name}：{result.get('msg', result)}")
                continue

            order_id = ""
            if isinstance(result, dict):
                order_id = result.get("data") or result.get("id") or ""
                if isinstance(order_id, dict):
                    order_id = order_id.get("id") or order_id.get("order_id") or ""
            if order_id:
                try:
                    created_ids.append(int(order_id))
                except (TypeError, ValueError):
                    pass
            suffix = f"单号 {order_id}" if order_id else "已提交"
            ok_lines.append(f"{idx}. {parsed.get('customer') or '散客'} | {goods_name} {parsed.get('color', '')} | {parsed.get('quantity') or 1} | {suffix}")

        lines = []
        if ok_lines:
            lines.append(f"已创建 {len(ok_lines)} 个工作流订单：")
            lines.extend(ok_lines)
        if errors:
            lines.append("以下工作流订单创建失败：")
            lines.extend(errors)
        reply = self._reply("\n".join(lines) if lines else "没有成功创建工作流订单。")
        reply["workflow_order_ids"] = created_ids
        return reply

    def _create(self, parsed: dict) -> dict:
        try:
            result = self.caller.call(
                "workflow_order_save",
                customer_name=parsed["customer"],
                goods_name=parsed["goods_name"],
                order_quantity=int(parsed["quantity"]),
                color=parsed.get("color", ""),
                order_images=parsed.get("order_images") or [],
                is_screen_print=1 if parsed.get("is_screen_print") else 0,
                remark=parsed.get("remark", ""),
            )
        except Exception as e:
            return self._reply(f"工作流订单创建失败：{e}")

        if isinstance(result, dict) and result.get("error"):
            return self._reply(f"工作流订单创建失败：{result['error']}")
        if isinstance(result, dict) and result.get("code") not in (None, 0):
            return self._reply(f"工作流订单创建失败：{result.get('msg', result)}")

        order_id = ""
        if isinstance(result, dict):
            order_id = result.get("data") or result.get("id") or ""
            if isinstance(order_id, dict):
                order_id = order_id.get("id") or order_id.get("order_id") or ""
        if order_id:
            SessionManager(get_current_session_id()).set_meta("last_order", {
                "type": "workflow",
                "id": str(order_id),
                "customer": parsed["customer"],
                "goods_name": parsed["goods_name"],
            })
        suffix = f"单号：{order_id}" if order_id else "已提交"
        return self._reply(
            f"工作流订单创建成功，{suffix}\n"
            f"客户：{parsed['customer']}\n"
            f"商品：{parsed['goods_name']}"
            f"{(' ' + parsed.get('color', '')) if parsed.get('color') else ''}\n"
            f"数量：{parsed['quantity']}"
        )

    def _parse(self, user_input: str, params: dict) -> dict:
        parsed = {
            "customer": params.get("customer") or params.get("customer_name") or "",
            "goods_name": params.get("goods_name") or params.get("product_name") or "",
            "quantity": params.get("quantity") or params.get("qty") or 0,
            "color": params.get("color") or "",
            "remark": params.get("remark") or "",
            "order_images": params.get("order_images") or [],
            "is_screen_print": bool(params.get("is_screen_print", False)),
        }

        products = params.get("products") or []
        if products:
            first = products[0]
            parsed["goods_name"] = parsed["goods_name"] or first.get("name", "")
            parsed["quantity"] = parsed["quantity"] or first.get("qty") or first.get("quantity") or 0
            parsed["color"] = parsed["color"] or first.get("color", "")

        text = user_input.strip()
        customer_match = re.search(r'(?:客户|客户[:：])\s*([^\s，,]+)', text)
        if customer_match:
            parsed["customer"] = customer_match.group(1).strip()

        product_match = re.search(r'(?:商品|产品|货品)\s*([^\s，,]+)', text)
        if product_match:
            parsed["goods_name"] = product_match.group(1).strip()

        qty_match = re.search(r'(\d+)\s*(张|套|个|件|捆|斤)?', text)
        if qty_match:
            parsed["quantity"] = int(qty_match.group(1))

        colors = ["红色", "黄色", "橙色", "蓝色", "绿色", "橄榄绿", "咖色", "深咖色", "古铜色", "黑色", "白色", "紫色", "粉色"]
        for color in colors:
            if color in text:
                parsed["color"] = color
                break

        if "丝印" in text or "印刷" in text:
            parsed["is_screen_print"] = True
            parsed["remark"] = parsed["remark"] or "丝印"

        return parsed
