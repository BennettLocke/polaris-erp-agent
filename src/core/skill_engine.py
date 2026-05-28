"""
Skill 执行引擎

按意图加载对应的 skill workflow，按固定步骤执行。
"""
import hmac
import os
import re
from src.core.features import disabled_feature_reply, feature_enabled
from src.core.tool_agent import classify_and_extract
from src.core.learning import match_learned, parse_correction, record_example
from src.core.colors import extract_color_from_text as extract_known_color
from src.core.colors import known_colors
from src.core.product_name import PRODUCT_SPECS, normalize_product_name
from src.core.session import SessionManager, set_current_session_id
from src.skills.base import BaseWorkflow
from src.utils import get_logger

logger = get_logger("sjagent.skill_engine")


class SkillEngine:
    """
    Skill 加载器 + 执行引擎。

    流程：
    1. 加载会话状态
    2. 如果有未完成的 skill → 恢复执行
    3. 否则 → 正则分类意图 → 启动新 skill
    4. 保存会话状态
    """

    def __init__(self):
        self.workflows: dict[str, BaseWorkflow] = {}
        self._register()

    def _register(self):
        """注册所有 skill workflow"""
        from src.skills.order_flow.workflow import OrderFlowWorkflow
        from src.skills.inventory.workflow import InventoryWorkflow
        from src.skills.stocktaking.workflow import StocktakingWorkflow
        from src.skills.purchase.workflow import PurchaseWorkflow
        from src.skills.transfer.workflow import TransferWorkflow
        from src.skills.knowledge.workflow import KnowledgeWorkflow
        from src.skills.chat.workflow import ChatWorkflow
        from src.skills.sales_manage.workflow import SalesManageWorkflow
        from src.skills.workflow_order.workflow import WorkflowOrderWorkflow
        from src.skills.sales_query.workflow import SalesQueryWorkflow
        from src.skills.series_manage.workflow import SeriesManageWorkflow
        from src.skills.customer_manage.workflow import CustomerManageWorkflow
        from src.skills.print_sales.workflow import PrintSalesWorkflow

        self.workflows = {
            "order": OrderFlowWorkflow(),
            "workflow": WorkflowOrderWorkflow(),
            "inventory": InventoryWorkflow(),
            "stocktaking": StocktakingWorkflow(),
            "purchase": PurchaseWorkflow(),
            "transfer": TransferWorkflow(),
            "knowledge": KnowledgeWorkflow(),
            "sales_manage": SalesManageWorkflow(),
            "sales_query": SalesQueryWorkflow(),
            "customer_manage": CustomerManageWorkflow(),
            "print": PrintSalesWorkflow(),
            "series_manage": SeriesManageWorkflow(),
            "chat": ChatWorkflow(),
            "help": ChatWorkflow(),
            "unknown": ChatWorkflow(),
        }
        if feature_enabled("bag_upload"):
            from src.skills.bag_upload.workflow import BagUploadWorkflow
            self.workflows["bag_upload"] = BagUploadWorkflow()
        else:
            logger.info("bag_upload skill disabled by device feature switch")
        logger.info(f"已注册 {len(self.workflows)} 个 skill")

    def run(self, user_input: str, session_id: str = "default") -> str:
        """
        主入口。

        Args:
            user_input: 用户输入
            session_id: 会话 ID

        Returns:
            回复文本
        """
        set_current_session_id(session_id)
        session = SessionManager(session_id)
        history = session.get_history()

        admin_reply = self._handle_admin_query(user_input)
        if admin_reply:
            session.save_turn(user_input, admin_reply)
            return admin_reply
        wiki_memory_reply = self._handle_wiki_memory_request(user_input)
        if wiki_memory_reply:
            session.save_turn(user_input, wiki_memory_reply)
            return wiki_memory_reply
        if self._is_internal_info_query(user_input):
            reply = "这属于内部配置信息。需要查询时请使用：管理查询 <口令> <数据库名|数据库配置|知识库路径|智能体路径>。"
            session.save_turn(user_input, reply)
            return reply

        correction_intent = parse_correction(user_input)
        if correction_intent:
            reply = self._handle_learning_correction(session, user_input, correction_intent)
            if reply:
                return reply

        # 检查是否有未完成的 skill（用户在回答上一步的问题）
        if session.has_pending():
            intent = session.get_pending_intent()
            state = session.get_state()
            workflow = self.workflows.get(intent)
            if intent == "bag_upload" and not feature_enabled("bag_upload"):
                session.clear_pending()
                reply = disabled_feature_reply("bag_upload")
                session.save_turn(user_input, reply)
                return reply

            if self._is_cancel_request(user_input) and not self._route_cancel_to_pending(intent, state, user_input):
                session.clear_pending()
                reply = "已取消当前操作。"
                session.save_turn(user_input, reply)
                return reply

            if workflow and state:
                pending_action = self._decide_pending_action(user_input, intent, state, history)
                if pending_action == "cancel":
                    session.clear_pending()
                    reply = "已取消当前操作。"
                    session.save_turn(user_input, reply)
                    return reply
                if pending_action == "new_request":
                    logger.info(f"[SkillEngine] 上下文判断为新请求，清除 pending: {intent}")
                    session.clear_pending()
                # 判断用户是否在回复上一步的问题（短回复、确认词）
                # 如果是新请求（长输入、包含新数字、明确的新指令），清除 pending 并走新流程
                elif pending_action != "answer_pending" and self._is_new_request(user_input, state):
                    logger.info(f"[SkillEngine] 检测到新请求，清除 pending: {intent}")
                    session.clear_pending()
                elif "partial_params" in state:
                    # 参数验证阶段的追问 → 直接合并用户回答，不重新分类意图
                    logger.info(f"[SkillEngine] 合并追问回答: {intent}")
                    partial = state["partial_params"]
                    # 根据意图类型，从用户回答中提取对应参数
                    new_params = self._extract_answer_params(intent, user_input, partial)
                    # 合并：旧 params + 新 params（新的覆盖旧的）
                    merged = {**partial, **new_params}
                    logger.info(f"[SkillEngine] 合并后参数: {merged}")

                    # 重新验证
                    check = self._validate_params(intent, merged, user_input)
                    if check:
                        session.save_pending(intent, check.get("state", {}))
                        return check["question"]

                    # 参数完整 → 执行
                    session.clear_pending()
                    try:
                        result = workflow.execute(user_input, params=merged)
                    except Exception as e:
                        logger.error(f"[SkillEngine] skill 执行失败: {e}")
                        return f"处理出错：{str(e)}"
                    return self._handle_result(session, intent, user_input, result)
                else:
                    logger.info(f"[SkillEngine] 恢复 skill: {intent}")
                    try:
                        result = workflow.resume(user_input, state)
                    except Exception as e:
                        logger.error(f"[SkillEngine] skill 恢复失败: {e}")
                        session.clear_pending()
                        return f"处理出错：{str(e)}"

                    return self._handle_result(session, intent, user_input, result)

        # 大模型优先理解自然语言；规则只用于高置信加速或兜底，避免关键词规则抢错方向。
        contextual_cancel = self._extract_contextual_sales_cancel(user_input, session, history)
        if contextual_cancel:
            intent = contextual_cancel.pop("intent", "sales_manage")
            params = contextual_cancel
            logger.info(f"[SkillEngine] 上下文撤销销售单: 参数={params} (输入: {user_input[:50]})")
            session.set_meta("last_extraction", {"user_input": user_input, "intent": intent, "params": params})
            workflow = self.workflows.get(intent, self.workflows["chat"])
            try:
                result = workflow.execute(user_input, params=params)
            except Exception as e:
                logger.error(f"[SkillEngine] skill 执行失败: {e}")
                return f"处理出错：{str(e)}"
            return self._handle_result(session, intent, user_input, result)

        learned_extracted = match_learned(user_input)
        fast_extracted = self._fast_extract(user_input)
        if learned_extracted:
            extracted = self._merge_learned_with_fast(user_input, learned_extracted, fast_extracted)
        elif self._should_use_fast_without_llm(user_input, fast_extracted):
            extracted = fast_extracted
        else:
            llm_extracted = classify_and_extract(user_input, history)
            extracted = self._choose_extraction(llm_extracted, fast_extracted)
        intent = extracted.pop("intent", "chat")
        if intent == "bag_upload" and not feature_enabled("bag_upload"):
            reply = disabled_feature_reply("bag_upload")
            session.save_turn(user_input, reply)
            return reply
        # 提取参数（去掉 intent 字段，剩下的都是 params）
        params = {k: v for k, v in extracted.items() if v is not None and not str(k).startswith("_")}
        logger.info(f"[SkillEngine] 意图: {intent}, 参数: {params} (输入: {user_input[:50]})")
        session.set_meta("last_extraction", {"user_input": user_input, "intent": intent, "params": params})

        # 验证参数完整性
        check = self._validate_params(intent, params, user_input)
        if check:
            logger.info(f"[SkillEngine] 参数不完整，追问用户: {check['question']}")
            session.save_pending(intent, check.get("state", {}))
            return check["question"]

        # 获取对应的 workflow
        workflow = self.workflows.get(intent)
        if not workflow:
            workflow = self.workflows["chat"]

        # 执行（传入 pre-extracted params）
        try:
            if intent in {"chat", "unknown", "help"}:
                params = {**params, "history": history}
            result = workflow.execute(user_input, params=params)
        except Exception as e:
            logger.error(f"[SkillEngine] skill 执行失败: {e}")
            return f"处理出错：{str(e)}"

        return self._handle_result(session, intent, user_input, result)

    def _handle_admin_query(self, user_input: str) -> str | None:
        match = re.match(r"^\s*(?:管理查询|管理员查询|admin\s+query)\s+(\S+)\s+(.+?)\s*$", user_input, re.IGNORECASE)
        if not match:
            return None

        provided_token, query = match.group(1).strip(), match.group(2).strip()
        expected_token = os.environ.get("SJAGENT_ADMIN_QUERY_TOKEN", "").strip()
        if not expected_token:
            return "管理员查询未启用：请先在服务器或本地 .env 设置 SJAGENT_ADMIN_QUERY_TOKEN。"
        if not hmac.compare_digest(provided_token, expected_token):
            return "管理员口令不正确，不能查询内部配置。"

        return self._admin_query_answer(query)

    def _admin_query_answer(self, query: str) -> str:
        from src.core.config import get_config

        config = get_config()
        normalized = re.sub(r"[\s:：，。,./\\_-]+", "", query).lower()

        if any(word in normalized for word in ["数据库名", "databasename", "dbname"]):
            name = config.db_config.get("name") or "未配置"
            return f"数据库名：{name}"

        if any(word in normalized for word in ["数据库配置", "databaseconfig", "dbconfig"]):
            db = config.db_config
            return "\n".join([
                "数据库配置：",
                f"- host：{db.get('host') or '未配置'}",
                f"- port：{db.get('port') or '未配置'}",
                f"- name：{db.get('name') or '未配置'}",
                f"- user：{db.get('user') or '未配置'}",
                f"- charset：{db.get('charset') or '未配置'}",
                "- password：已隐藏",
            ])

        if any(word in normalized for word in ["知识库路径", "wikipath", "knowledgebasepath"]):
            from src.knowledge.loader import KnowledgeLoader

            return f"知识库路径：{KnowledgeLoader().base_path}"

        if any(word in normalized for word in ["项目路径", "智能体路径", "agentpath", "projectroot"]):
            return f"智能体项目路径：{config.project_root}"

        return "管理员查询只支持：数据库名、数据库配置、知识库路径、智能体路径。密码、API Key、SSH 私钥等敏感密钥不会返回。"

    def _is_internal_info_query(self, user_input: str) -> bool:
        text = user_input.strip()
        lowered = text.lower()
        if re.match(r"^\s*(?:管理查询|管理员查询|admin\s+query)\b", text, re.IGNORECASE):
            return False

        direct_markers = [
            "config_query",
            "db_query",
            "select database",
            "sjagent_admin_query_token",
            "sjagent_wiki_path",
            ".env",
            "api key",
            "apikey",
            "ssh",
            "私钥",
            "密钥",
        ]
        if any(marker in lowered for marker in direct_markers):
            return True

        internal_subjects = [
            "数据库",
            "database",
            "知识库路径",
            "配置在哪里",
            "配置路径",
            "服务器路径",
            "项目路径",
            "智能体路径",
            "密码",
            "口令",
            "token",
        ]
        owner_scope = ["你的", "你们的", "服务器", "系统", "智能体", "北极星", "内部"]
        return any(word in text or word in lowered for word in internal_subjects) and any(scope in text for scope in owner_scope)

    def _handle_learning_correction(self, session: SessionManager, user_input: str, intent: str) -> str | None:
        last = session.get_meta("last_extraction") or {}
        last_text = last.get("user_input")
        if not last_text:
            return None

        corrected = {"intent": intent}
        old_params = last.get("params") or {}
        for key in ("customer", "keyword", "product_name", "color", "products", "from", "to", "count", "action"):
            if key in old_params:
                corrected[key] = old_params[key]
        record_example(last_text, corrected, source="correction")
        self._record_correction_to_wiki(last_text, corrected, intent)
        session.clear_pending()
        reply = f"已记住：以后遇到「{last_text}」这类说法，优先按「{self._intent_label(intent)}」处理。"
        session.save_turn(user_input, reply)
        return reply

    def _handle_wiki_memory_request(self, user_input: str) -> str | None:
        match = re.match(r"^\s*(?:记到知识库|写入知识库|更新知识库|知识库记一下)[:：]?\s*(.+?)\s*$", user_input)
        if not match:
            return None
        note = match.group(1).strip()
        if not note:
            return "请把要记录的内容写在「记到知识库：」后面。"
        try:
            from src.knowledge.wiki_inbox import record_wiki_inbox

            path = record_wiki_inbox(
                title="人工补充知识",
                body=note,
                category="manual_note",
                source="user_command",
            )
            if not path:
                return "这条内容为空或包含疑似敏感信息，已跳过写入知识库。"
            return f"已写入知识库待确认区：{path.name}。确认无误后再合并到正式页面。"
        except Exception as e:
            logger.warning(f"写入知识库待确认区失败: {e}")
            return f"写入知识库失败：{e}"

    def _record_correction_to_wiki(self, last_text: str, corrected: dict, intent: str) -> None:
        try:
            from src.knowledge.wiki_inbox import record_wiki_inbox

            record_wiki_inbox(
                title=f"意图纠错：{self._intent_label(intent)}",
                category="correction",
                source="learning_correction",
                body=(
                    f"用户纠正了一条说法：\n\n"
                    f"- 原句：{last_text}\n"
                    f"- 正确意图：{intent}\n"
                    f"- 结构化结果：{corrected}"
                ),
            )
        except Exception as e:
            logger.warning(f"写入纠错到知识库失败: {e}")

    def _intent_label(self, intent: str) -> str:
        labels = {
            "order": "下单/开单",
            "inventory": "查库存",
            "stocktaking": "盘点",
            "purchase": "进货",
            "transfer": "调货/调拨",
            "sales_query": "查客户订单",
            "sales_manage": "订单管理",
            "customer_manage": "客户管理",
            "print": "打印销售单",
            "series_manage": "1件起订规则",
            "workflow": "工作流订单",
            "knowledge": "知识问答",
            "chat": "闲聊",
        }
        return labels.get(intent, intent)

    def _is_workflow_order_request(self, user_input: str) -> bool:
        keywords = ["工作流订单", "工作流单", "创建工作流", "设计稿订单", "设计稿下单", "按图下单"]
        if any(k in user_input for k in keywords):
            return True
        return bool(re.search(r"(?:图片|照片|截图).{0,8}(?:下单|开单|订单)", user_input))

    def _is_workflow_query_request(self, user_input: str) -> bool:
        workflow_words = ["工作流订单", "工作流单", "设计稿订单"]
        query_words = ["查", "查询", "最近", "列表", "详情", "订单内容", "看下", "看看"]
        return any(w in user_input for w in workflow_words) and any(w in user_input for w in query_words)

    def _is_workflow_delete_request(self, user_input: str) -> bool:
        workflow_words = ["工作流订单", "工作流单", "工作流", "设计稿订单"]
        delete_words = ["删", "删除", "作废", "取消订单"]
        return any(w in user_input for w in workflow_words) and any(w in user_input for w in delete_words)

    def _fast_extract(self, user_input: str) -> dict | None:
        """Fast-path parser for common business requests."""
        text = user_input.strip()
        if not text:
            return None
        if self._is_identity_or_help_request(text):
            return {"intent": "help"}
        if self._is_agent_capability_request(text):
            return {"intent": "chat"}
        if self._is_customer_manage_request(text):
            return self._extract_customer_manage_params(text)
        if self._is_print_request(text):
            return self._extract_print_params(text)
        if self._is_series_manage_request(text):
            return self._extract_series_manage_params(text)
        if self._is_bag_upload_request(text):
            return self._extract_bag_upload_params(text)
        if self._is_workflow_delete_request(text):
            return self._extract_workflow_delete_params(text)
        if self._is_workflow_query_request(text):
            return self._extract_workflow_query_params(text)
        if self._is_workflow_order_request(text):
            return self._extract_workflow_order_params(text)
        if self._is_sales_modify_request(text):
            return self._extract_sales_modify_params(text)
        if self._is_sales_query_request(text):
            return self._extract_sales_query_params(text)
        if self._is_sales_delete_request(text):
            return self._extract_sales_delete_params(text)
        if self._is_transfer_request(text):
            return self._extract_transfer_params(text)
        if self._is_stocktaking_request(text):
            return self._extract_stocktaking_params(text)
        if self._is_inventory_request(text):
            return self._extract_inventory_params(text)
        if self._is_order_request(text):
            parsed = self._extract_order_params_fast(text)
            if parsed:
                return parsed
        return None

    def _should_use_fast_without_llm(self, user_input: str, fast_extracted: dict | None) -> bool:
        if not fast_extracted:
            return False
        intent = fast_extracted.get("intent")
        if intent == "sales_manage":
            return True
        if intent == "customer_manage":
            return True
        if intent == "print":
            return True
        if intent == "series_manage":
            return True
        if intent == "bag_upload":
            return True
        if intent == "workflow" and fast_extracted.get("action") in {"query", "delete", "create"}:
            return True
        if intent == "sales_query" and (
            fast_extracted.get("customer") or fast_extracted.get("sales_id") or fast_extracted.get("count")
        ):
            return True
        if intent in {"help", "chat"}:
            return True
        if intent == "inventory" and fast_extracted.get("product_name") and any(
            w in user_input for w in ["库存", "有货", "有库存", "还有", "还剩"]
        ):
            return True
        if intent == "stocktaking" and fast_extracted.get("products"):
            return True
        if intent == "transfer" and fast_extracted.get("from") and fast_extracted.get("to") and fast_extracted.get("products"):
            return True
        if intent == "order" and fast_extracted.get("products") and fast_extracted.get("customer"):
            return True
        return False

    def _merge_learned_with_fast(self, user_input: str, learned: dict, fast: dict | None) -> dict:
        if fast and learned.get("_source") != "correction" and self._should_use_fast_without_llm(user_input, fast):
            return fast
        if fast and fast.get("intent") == "series_manage":
            return fast
        if fast and fast.get("intent") == "sales_manage" and fast.get("action") == "modify":
            return fast
        if not fast or learned.get("intent") != fast.get("intent"):
            return learned
        merged = {k: v for k, v in fast.items() if v is not None}
        prefer_fast_keys = {"products", "product_name", "color", "warehouse", "from", "to", "workflow_ids", "order_id"}
        for key, value in learned.items():
            if value is None:
                continue
            if key in prefer_fast_keys and merged.get(key):
                continue
            merged[key] = value
        return merged

    def _choose_extraction(self, llm_extracted: dict, fast_extracted: dict | None) -> dict:
        llm_intent = (llm_extracted or {}).get("intent")
        if llm_intent and llm_intent not in {"unknown", "chat"}:
            if fast_extracted and fast_extracted.get("intent") in {"help", "chat"} and llm_intent == "knowledge":
                return fast_extracted
            return llm_extracted
        return fast_extracted or llm_extracted or {"intent": "chat"}

    def _is_identity_or_help_request(self, user_input: str) -> bool:
        text = user_input.strip()
        if text in {"你是谁", "你叫什么", "你叫什么名字", "北极星是谁", "帮助", "help"}:
            return True
        return any(w in text for w in ["你能做什么", "你会什么", "有什么功能", "介绍一下你", "你的功能"])

    def _is_agent_capability_request(self, user_input: str) -> bool:
        text = user_input.strip()
        capability_words = ["企业微信", "通知", "提醒", "语音", "打印", "后台", "网页", "手机", "按钮"]
        self_words = ["你", "北极星", "机器人", "智能体", "系统"]
        ask_words = ["会", "支持", "能不能", "可以", "能否", "是否", "有没有"]
        if "企业微信" in text and any(w in text for w in ask_words + ["通知", "提醒"]):
            return True
        return (
            any(w in text for w in capability_words)
            and any(w in text for w in self_words)
            and any(w in text for w in ask_words)
        )

    def _is_bag_upload_request(self, user_input: str) -> bool:
        text = user_input.strip()
        if not text:
            return False
        start_words = ["开始上传泡袋", "上传泡袋", "新增泡袋", "新建泡袋", "创建泡袋"]
        return any(w in text for w in start_words) and not any(w in text for w in ["烫金", "下单", "开单"])

    def _extract_bag_upload_params(self, user_input: str) -> dict:
        result = {"intent": "bag_upload"}
        if "宽版" in user_input:
            result["bag_type"] = "宽版"
        elif any(w in user_input for w in ["红茶", "金骏眉", "小种"]):
            result["bag_type"] = "红茶"
        elif any(w in user_input for w in ["岩茶", "肉桂", "水仙", "大红袍"]):
            result["bag_type"] = "岩茶"
        return result

    def _extract_contextual_sales_cancel(self, user_input: str, session: SessionManager, history: list[dict]) -> dict | None:
        """After a successful order, understand short cancel-like utterances as a request to undo that sales order."""
        text = user_input.strip()
        if not text:
            return None
        last_order = session.get_meta("last_order") or {}
        if last_order.get("type") != "sales" or not last_order.get("id"):
            return None

        cancel_words = ["算了", "取消了", "取消", "不要了", "撤销", "作废", "删掉", "删除", "不下了", "不开了"]
        context_words = ["刚才", "刚刚", "上一单", "这个单", "这单", "订单", "销售单", "开单"]
        if not any(w in text for w in cancel_words):
            return None

        last_assistant = ""
        for msg in reversed(history or []):
            if msg.get("role") == "assistant":
                last_assistant = msg.get("content", "")
                break
        just_opened_order = "开单成功" in last_assistant and "销售单号" in last_assistant
        explicit_context = any(w in text for w in context_words)
        if not (just_opened_order or explicit_context):
            return None

        return {
            "intent": "sales_manage",
            "action": "delete",
            "target": "single",
            "sales_ids": [str(last_order["id"])],
        }

    def _is_customer_manage_request(self, user_input: str) -> bool:
        text = user_input.strip()
        create_words = ["创建", "新建", "新增", "添加", "建立"]
        return any(w in text for w in create_words) and ("客户" in text or "客户档案" in text)

    def _is_print_request(self, user_input: str) -> bool:
        text = user_input.strip()
        if any(w in text for w in ["打印", "打单", "打印任务"]) and re.search(r"\d+", text):
            return True
        return any(w in text for w in ["打印", "打单", "打印任务"]) and any(
            w in text for w in ["销售单", "订单", "单子", "单号", "最新", "最近", "最后", "客户"]
        )

    def _extract_print_params(self, user_input: str) -> dict:
        result = {"intent": "print"}
        sid = re.search(r"(?:销售单|订单|单号)\D*(\d+)", user_input)
        if not sid and any(w in user_input for w in ["打印", "打单", "打印任务"]):
            sid = re.search(r"\d+", user_input)
        if sid:
            result["sales_id"] = int(sid.group(1) if sid.lastindex else sid.group(0))
            return result
        count_match = re.search(r"(?:最近|近|最后|最新)\s*(\d+|一|二|两|三|四|五|六|七|八|九|十)?\s*(?:个|条|单|张)?", user_input)
        if count_match:
            result["count"] = self._parse_count(count_match.group(1) or "一")
        cleaned = user_input
        for word in [
            "帮我", "帮", "请", "打印一下", "打印", "打单", "打印任务", "最新一个", "最新一单",
            "最近一个", "最近一单", "最近一次", "最新", "最近", "最后", "客户", "的", "销售单", "订单", "单子",
        ]:
            cleaned = cleaned.replace(word, " ")
        cleaned = re.sub(r"\d+\s*(?:个|条|单|张)?", " ", cleaned)
        parts = [p for p in re.split(r"[\s，,]+", cleaned.strip()) if p]
        if parts:
            result["customer"] = parts[0]
        return result

    def _extract_customer_manage_params(self, user_input: str) -> dict:
        text = user_input.strip()
        result = {"intent": "customer_manage", "action": "create"}
        name = text
        name = re.sub(r"(?:帮我|给我|请|麻烦|把|将)", " ", name)
        name = re.sub(r"(?:创建|新建|新增|添加|建立)\s*(?:一个)?\s*(?:客户|客户档案)?", " ", name)
        name = re.sub(r"(?:客户|客户名|名称)[:：]\s*", " ", name)
        name = re.sub(r"(?:创建吧|创建一下|确认创建|建吧)", " ", name)
        name = re.sub(r"[吧啊呀]+$", "", name.strip())
        name = re.sub(r"\s+", "", name).strip("，,。")
        if name:
            result["customer"] = name
        phone = re.search(r"1[3-9]\d{9}", text)
        if phone:
            result["contacts_tel"] = phone.group(0)
        contact = re.search(r"(?:联系人|老板|对接人)[:：]?\s*([\u4e00-\u9fa5A-Za-z]{2,6})", text)
        if contact:
            result["contacts_name"] = contact.group(1)
        return result

    def _is_series_manage_request(self, user_input: str) -> bool:
        text = user_input.strip()
        rule_words = ["1件起", "一件起", "件起订", "非1件起", "非一件起", "按件"]
        action_words = ["加", "加入", "添加", "设为", "设置", "改成", "取消", "移出", "去掉", "删除", "查看", "列出", "查询"]
        return any(w in text for w in rule_words) and any(w in text for w in action_words + ["系列", "规则"])

    def _extract_series_manage_params(self, user_input: str) -> dict:
        action = self._detect_series_action(user_input)
        series = self._extract_series_names(user_input)
        result = {"intent": "series_manage", "action": action}
        if series:
            result["series"] = series
        return result

    def _detect_series_action(self, user_input: str) -> str:
        text = user_input.strip()
        if any(w in text for w in ["查看", "看看", "列出", "查询", "有哪些"]):
            return "query"
        non_one_words = ["非1件起", "非一件起", "不是1件起", "不是一件起", "不用1件起", "不用一件起"]
        remove_words = ["取消", "移出", "去掉", "删除", "删掉", "不算"]
        if any(w in text for w in non_one_words):
            if any(w in text for w in remove_words) and "非" in text:
                return "remove_non_one_piece"
            return "set_non_one_piece"
        if any(w in text for w in remove_words) and any(w in text for w in ["1件起", "一件起", "件起订", "按件"]):
            return "set_non_one_piece"
        return "set_one_piece"

    def _extract_series_names(self, user_input: str) -> list[str]:
        text = user_input.strip()
        cleanup_words = [
            "以后", "以后和他说", "记住", "规则", "系列", "礼盒", "把", "将", "给",
            "查看", "看看", "列出", "查询", "有哪些",
            "加入到", "加到", "加进", "加入", "添加", "新增", "加", "设为", "设置为",
            "设置成", "改成", "变成", "归为", "算作", "作为", "取消", "移出", "去掉",
            "删除", "删掉", "不算", "不是", "不用", "非1件起", "非一件起", "1件起订",
            "一件起订", "1件起", "一件起", "件起订", "按件", "的",
        ]
        for word in cleanup_words:
            text = text.replace(word, " ")
        text = re.sub(r"[，,、/;；\n]+", " ", text)
        names = []
        for part in [p.strip() for p in text.split() if p.strip()]:
            if part in {"为", "到", "成", "和", "或", "与", "非", "起", "订"}:
                continue
            part = re.sub(r"^[：:]+|[：:]+$", "", part)
            if not part or re.search(r"\d", part):
                continue
            if part not in names:
                names.append(part)
        return names

    def _extract_workflow_order_params(self, user_input: str) -> dict:
        import re
        result = {"intent": "workflow", "action": "create"}

        customer_match = re.search(r'客户[:：]\s*([^\s，,]+)', user_input)
        if customer_match:
            result["customer"] = customer_match.group(1).strip()

        product_match = re.search(r'(?:商品|产品|货品)\s*([^\s，,]+)', user_input)
        if product_match:
            result["goods_name"] = product_match.group(1).strip()

        qty_match = re.search(r'(\d+)\s*(张|套|个|件|捆|斤)?', user_input)
        if qty_match:
            result["quantity"] = int(qty_match.group(1))
            result["unit"] = qty_match.group(2) or ""

        colors = ["红色", "黄色", "橙色", "蓝色", "绿色", "橄榄绿", "咖色", "深咖色", "古铜色", "黑色", "白色", "紫色", "粉色"]
        for color in colors:
            if color in user_input:
                result["color"] = color
                break

        if "丝印" in user_input or "印刷" in user_input:
            result["is_screen_print"] = True
            result["remark"] = "丝印"

        return result

    def _extract_workflow_query_params(self, user_input: str) -> dict:
        result = {"intent": "workflow", "action": "query"}

        oid = re.search(r'(?:工作流订单|工作流单|设计稿订单|单号)\D*(\d+)', user_input)
        if oid:
            result["order_id"] = int(oid.group(1))

        count_match = re.search(r'(?:最近|近|最后)\s*(\d+|一|二|两|三|四|五|六|七|八|九|十)\s*(?:个|条|单)?', user_input)
        if count_match:
            result["count"] = self._parse_count(count_match.group(1))
        elif "最近" in user_input:
            result["count"] = 1

        cleaned = user_input
        for word in ["帮我", "帮看看", "查看", "看看", "看下", "查询", "查一下", "查下", "查", "最近", "最后", "工作流订单", "工作流单", "设计稿订单", "的"]:
            cleaned = cleaned.replace(word, " ")
        cleaned = re.sub(r'\d+\s*(?:个|条|单)?', " ", cleaned)
        parts = [p for p in re.split(r'[\s，,]+', cleaned.strip()) if p and p not in {"一个", "一条", "一单", "列表", "详情"}]
        if parts:
            result["keyword"] = parts[0]
        return result

    def _extract_workflow_delete_params(self, user_input: str) -> dict:
        ids = re.findall(r'\d+', user_input)
        result = {"intent": "workflow", "action": "delete"}
        if ids:
            result["workflow_ids"] = ids
            if len(ids) == 1:
                result["order_id"] = ids[0]
        return result

    def _is_sales_query_request(self, user_input: str) -> bool:
        if self._is_sales_modify_request(user_input):
            return False
        query_words = ["最近一次", "下单了什么", "买了什么", "订了什么", "订单内容", "订单详情", "销售单详情", "查销售单", "查询", "查下"]
        if any(k in user_input for k in query_words) and ("订单" in user_input or "销售单" in user_input or "下单" in user_input):
            return True
        return bool(re.search(r'(?:最近|近|最后)\s*(\d+|一|二|两|三|四|五|六|七|八|九|十)\s*(?:个|条|单)', user_input))

    def _is_sales_modify_request(self, user_input: str) -> bool:
        return any(w in user_input for w in ["修改", "更改", "改一下", "改销售单", "调整销售单"]) and (
            "销售单" in user_input or "订单" in user_input or "单号" in user_input
        )

    def _extract_sales_modify_params(self, user_input: str) -> dict:
        result = {"intent": "sales_manage", "action": "modify"}
        sid = re.search(r'(?:销售单|订单|单号)?\D*(\d+)', user_input)
        if sid:
            result["sales_id"] = int(sid.group(1))
        return result

    def _extract_sales_query_params(self, user_input: str) -> dict:
        import re
        result = {"intent": "sales_query"}

        sid = re.search(r'(?:销售单|订单|单号)\D*(\d+)', user_input)
        if sid:
            result["sales_id"] = int(sid.group(1))

        count_match = re.search(r'(?:最近|近|最后)\s*(\d+|一|二|两|三|四|五|六|七|八|九|十)\s*(?:个|条|单)?', user_input)
        if count_match:
            result["count"] = self._parse_count(count_match.group(1))

        cleaned = user_input
        for word in ["帮我", "帮看看", "帮", "看看", "查一下", "查下", "查", "最近一次", "最近", "客户"]:
            cleaned = cleaned.replace(word, " ")
        cleaned = re.sub(r'\d+\s*(?:个|条|单)', " ", cleaned)
        customer = ""
        m = re.search(r'([^\s，,]+?)(?:下单|买了|订了|订单|销售单)', cleaned)
        if m:
            customer = m.group(1).strip()
        if not customer:
            parts = [p for p in re.split(r'[\s，,]+', cleaned.strip()) if p and p not in {"下单", "订单", "销售单", "买了", "什么", "了什么", "东西", "内容", "详情"}]
            if parts:
                customer = parts[0]
        if customer and customer not in {"下单", "订单", "销售单", "买了", "什么", "了什么"}:
            result["customer"] = customer
        return result

    def _parse_count(self, value: str) -> int:
        if value.isdigit():
            return max(1, min(int(value), 10))
        mapping = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
        return mapping.get(value, 1)

    def _is_sales_delete_request(self, user_input: str) -> bool:
        return ("删" in user_input or "删除" in user_input or "作废" in user_input) and ("单" in user_input or "订单" in user_input)

    def _extract_sales_delete_params(self, user_input: str) -> dict:
        import re
        result = {"intent": "sales_manage", "action": "delete"}
        ids = re.findall(r'\d+', user_input)
        if ids:
            result.update({"target": "multiple" if len(ids) > 1 else "single", "sales_ids": [int(i) for i in ids]})
            return result
        if any(w in user_input for w in ["这个", "这单", "这个单", "这订单", "这个订单", "刚才", "上一单"]):
            result["target"] = "single"
            result["sales_ids"] = []
            return result
        m = re.search(r'删除\s*([^\s，,]+)\s*的.*单', user_input)
        if m:
            result.update({"target": "customer_all", "customer": m.group(1)})
            return result
        result["target"] = "unknown"
        return result

    def _is_inventory_request(self, user_input: str) -> bool:
        words = ["库存", "有货", "有库存", "还有", "还剩", "够不够", "够吗", "查一下", "查下"]
        return any(w in user_input for w in words) and not any(w in user_input for w in ["下单", "开单", "进货", "调拨", "调货"])

    def _is_transfer_request(self, user_input: str) -> bool:
        return any(w in user_input for w in ["调货", "调拨", "调仓", "仓库调"])

    def _extract_transfer_params(self, user_input: str) -> dict:
        result = {"intent": "transfer"}
        text = user_input.strip()

        def normalize_warehouse(value: str) -> str:
            if not value:
                return ""
            if "自己" in value or "店里" in value or "本店" in value:
                return "自己店里"
            if "百鑫" in value:
                return "百鑫"
            return value

        warehouse = r"(自己店里|自己|店里|本店|百鑫仓库|百鑫)"
        direction_patterns = [
            rf"从\s*{warehouse}\s*(?:仓库)?\s*(?:调货|调拨|调|转)?\s*(?:到|至|进|入|给)\s*{warehouse}",
            rf"{warehouse}\s*(?:仓库)?\s*(?:到|至|调到|转到|调入|进|入|给)\s*{warehouse}",
        ]
        for pattern in direction_patterns:
            m = re.search(pattern, text)
            if m:
                result["from"] = normalize_warehouse(m.group(1))
                result["to"] = normalize_warehouse(m.group(2))
                text = (text[:m.start()] + " " + text[m.end():]).strip()
                break

        if "from" not in result:
            from_match = re.search(rf"从\s*{warehouse}", text)
            to_match = re.search(rf"(?:到|至|调到|转到|调入|进|入|给)\s*{warehouse}", text)
            if from_match:
                result["from"] = normalize_warehouse(from_match.group(1))
                text = (text[:from_match.start()] + " " + text[from_match.end():]).strip()
            if to_match:
                result["to"] = normalize_warehouse(to_match.group(1))
                text = (text[:to_match.start()] + " " + text[to_match.end():]).strip()

        for word in ["帮我", "请", "调货", "调拨", "调仓", "仓库", "商品", "产品"]:
            text = text.replace(word, " ")
        text = re.sub(r"[，,;；\n]+", " ", text)
        text = re.sub(r"\s+", " ", text).strip()

        products = []
        for match in re.finditer(r"(.+?)\s*(\d+)\s*(套|张|个|件|捆|斤)", text):
            raw_name = match.group(1).strip()
            product = self._build_transfer_product(raw_name, match.group(2), match.group(3))
            if product:
                products.append(product)

        if not products:
            for match in re.finditer(r"(\d+)\s*(套|张|个|件|捆|斤)\s*(.+)", text):
                raw_name = match.group(3).strip()
                product = self._build_transfer_product(raw_name, match.group(1), match.group(2))
                if product:
                    products.append(product)

        if products:
            result["products"] = products
        return result

    def _build_transfer_product(self, raw_name: str, quantity: str, unit: str) -> dict | None:
        raw_name = re.sub(r"^(?:商品|产品|礼盒|盒子)\s*", "", raw_name or "").strip()
        raw_name = raw_name.strip(" ：:，,。")
        if not raw_name:
            return None
        color = self._extract_color_from_text(raw_name)
        if color:
            raw_name = raw_name.replace(color, "").strip()
        name = self._normalize_inventory_query_keyword(raw_name)
        if not name:
            return None
        return {
            "name": name,
            "quantity": int(quantity),
            "unit": unit,
            "color": color,
        }

    def _is_stocktaking_request(self, user_input: str) -> bool:
        return any(w in user_input for w in ["盘点", "盘一下", "库存同步", "同步库存", "校准库存"])

    def _extract_stocktaking_params(self, user_input: str) -> dict:
        result = {"intent": "stocktaking"}
        result["warehouse"] = "自己店里" if ("自己" in user_input or "店里" in user_input) else "百鑫"
        clear_to_zero = any(word in user_input for word in ["清零", "归零", "清为0", "清为零", "设为0", "设置为0"])

        text = user_input
        for word in [
            "库存同步", "同步库存", "校准库存", "盘一下", "盘点", "库存", "设为", "设置为",
            "设置", "改成", "调整为", "百鑫仓库", "百鑫", "自己店里", "自己", "店里", "仓库",
            "清零", "归零", "清为0", "清为零",
        ]:
            text = text.replace(word, " ")
        text = re.sub(r"[，,;；\n]+", " ", text)

        products = []
        for match in re.finditer(r"(.+?)\s*(\d+)\s*(套|张|个|件|捆|斤)", text):
            raw_name = match.group(1).strip()
            raw_name = re.sub(r"^(?:商品|产品|礼盒|盒子)\s*", "", raw_name).strip()
            if not raw_name:
                continue
            color = self._extract_color_from_text(raw_name)
            if color:
                raw_name = raw_name.replace(color, "").strip()
            name = self._normalize_inventory_query_keyword(raw_name)
            if not name:
                continue
            products.append({
                "name": name,
                "quantity": int(match.group(2)),
                "unit": match.group(3),
                "color": color,
            })
        if not products and clear_to_zero:
            raw_name = re.sub(r"\b0\b|零", " ", text).strip()
            raw_name = re.sub(r"^(?:商品|产品|礼盒|盒子)\s*", "", raw_name).strip()
            color = self._extract_color_from_text(raw_name)
            if color:
                raw_name = raw_name.replace(color, "").strip()
            name = self._normalize_inventory_query_keyword(raw_name)
            if name:
                products.append({
                    "name": name,
                    "quantity": 0,
                    "unit": "套",
                    "color": color,
                })
        if products:
            result["products"] = products
        return result

    def _extract_color_from_text(self, text: str) -> str:
        return extract_known_color(text)

    def _extract_inventory_params(self, user_input: str) -> dict:
        result = {"intent": "inventory"}
        text = user_input
        color = self._extract_color_from_text(text)
        if color:
            result["color"] = color
            text = text.replace(color, "")
        cleanup_words = ["帮我", "帮看看", "看看", "查询", "查一下", "查下", "查", "库存", "有货", "有库存", "有什么", "哪些", "礼盒", "盒子", "的", "吗", "嘛", "呢"]
        for word in cleanup_words:
            text = text.replace(word, "")
        text = self._normalize_inventory_query_keyword(text)
        if text:
            result["product_name"] = text
        return result

    def _normalize_inventory_query_keyword(self, text: str) -> str:
        return normalize_product_name(text.strip(), colors=known_colors(), specs=PRODUCT_SPECS)

    def _is_order_request(self, user_input: str) -> bool:
        if self._is_transfer_request(user_input):
            return False
        has_unit = any(unit in user_input for unit in ["套", "张", "个", "件", "捆", "斤"])
        if not has_unit:
            return False
        if any(w in user_input for w in ["下单", "开单", "订货"]):
            return True
        if re.search(r"^[\u4e00-\u9fa5A-Za-z0-9（）()【】\-]{2,20}要\d+(?:\.\d+)?\s*(?:套|张|个|件|捆|斤).+", user_input.strip()):
            return True
        return bool(re.search(r"^[^\s，,]{2,20}\s+.+\d+(?:\.\d+)?\s*(?:套|张|个|件|捆|斤)", user_input.strip()))

    def _extract_order_params_fast(self, user_input: str) -> dict | None:
        import re
        customer = ""
        command_words = ("开单", "下单", "销售单", "帮我开单", "帮我下单")
        text = user_input.strip()
        command_pattern = r"^(?:帮我开单|帮我下单|开单|下单|销售单)\s*"
        command_match = re.match(command_pattern, text)
        text_without_command = re.sub(command_pattern, "", text, count=1).strip()
        m = re.search(r'(?<![\u4e00-\u9fa5A-Za-z0-9])客户[:：]?\s*([^\s，,]+)', text_without_command)
        if m:
            customer = m.group(1).strip()
        else:
            if command_match:
                m = re.search(r'^([^\s，,]{2,20})\s+.+\d+(?:\.\d+)?\s*(?:套|张|个|件|捆|斤)', text_without_command)
                if m:
                    customer = m.group(1).strip()
            else:
                m = re.search(r'^([^\s，,]+).*?(?:下单|开单)', text)
                if m:
                    customer = m.group(1).strip()
                else:
                    m = re.search(r'^([^\s，,]{2,20})\s+.+\d+(?:\.\d+)?\s*(?:套|张|个|件|捆|斤)', text)
                    if m:
                        customer = m.group(1).strip()
        if customer in command_words or customer in {"客户", "客户名字", "客户名", "客户名称", "名字", "姓名", "名称"}:
            customer = ""

        colors = ["红色", "黄色", "橙色", "蓝色", "绿色", "橄榄绿", "咖色", "深咖色", "古铜色", "黑色", "白色", "紫色", "粉色"]
        products = []
        compact = re.sub(r"\s+", "", text_without_command or text)
        compact_match = re.match(
            r"^([\u4e00-\u9fa5A-Za-z0-9（）()【】\-]{2,20})要(\d+(?:\.\d+)?)(套|张|个|件|捆|斤)(.+)$",
            compact,
        )
        if compact_match and not customer:
            customer = compact_match.group(1).strip()
            raw_name = compact_match.group(4).strip()
            color = ""
            for c in colors:
                if c in raw_name:
                    color = c
                    raw_name = raw_name.replace(c, "")
                    break
            products.append({
                "name": raw_name.replace("商品", "").replace("产品", "").strip(),
                "qty": int(float(compact_match.group(2))),
                "unit": compact_match.group(3),
                "color": color,
                "_qty_text": compact_match.group(2),
            })
        if not products:
            cleaned = re.sub(r'(?<![\u4e00-\u9fa5A-Za-z0-9])客户[:：]?\s*[^\s，,]+', '', text_without_command or text)
            for match in re.finditer(r'([\u4e00-\u9fa5A-Za-z0-9【】]+?)\s*(\d+)\s*(套|张|个|件|捆|斤)', cleaned):
                name = match.group(1).strip()
                if name in {"客户", "商品", "产品", "下单", "开单"}:
                    continue
                color = ""
                for c in colors:
                    if c in name or c in user_input[match.end(): match.end() + 6]:
                        color = c
                        name = name.replace(c, "")
                        break
                products.append({"name": name.replace("商品", "").replace("产品", "").strip(), "qty": int(match.group(2)), "unit": match.group(3), "color": color, "_qty_text": match.group(2)})
        if customer or products:
            return {"intent": "order", "customer": customer, "products": products}
        return None

    def _validate_params(self, intent: str, params: dict, user_input: str) -> dict | None:
        """
        验证参数完整性。
        返回 None = 参数OK，可以执行
        返回 dict = 需要追问用户（包含 question 和 state）
        """
        if intent == "order":
            if not params.get("customer"):
                params["customer"] = "散客"
                params["customer_defaulted"] = True
            products = params.get("products", [])
            if not products:
                return {"question": "请问要下什么商品？例如：标签4张 岩味半斤红色1套", "state": {"partial_params": params}}
            for p in products:
                if not p.get("name"):
                    return {"question": "商品信息不完整，请告诉我商品名和数量，例如：标签4张", "state": {"partial_params": params}}

        elif intent == "inventory":
            if not params.get("product_name"):
                return {"question": "请问要查哪个商品的库存？例如：查下半斤库存", "state": {"partial_params": params}}

        elif intent == "stocktaking":
            if not params.get("products"):
                return {"question": "请问要盘点什么商品？例如：盘点 岩味半斤红色 设为20套", "state": {"partial_params": params}}

        elif intent == "purchase":
            if not params.get("products"):
                return {"question": "请问要进货什么商品？例如：进货 标签100张", "state": {"partial_params": params}}

        elif intent == "series_manage":
            if params.get("action") != "query" and not params.get("series"):
                return {"question": "请问要调整哪个系列？例如：把青云加到1件起系列", "state": {"partial_params": params}}

        elif intent == "transfer":
            for key in ("from", "to"):
                if params.get(key):
                    params[key] = "自己店里" if any(w in str(params[key]) for w in ["自己", "店里", "本店"]) else "百鑫"
            if not params.get("from") or not params.get("to"):
                return {"question": "请问从哪个仓库调到哪个仓库？例如：从自己店里调10套到百鑫", "state": {"partial_params": params}}
            if params["from"] == params["to"]:
                return {"question": "调出和调入仓库不能相同，请重新指定", "state": {"partial_params": params}}
            if not params.get("products"):
                return {"question": "请问要调拨什么商品？", "state": {"partial_params": params}}
            for p in params.get("products", []):
                if not p.get("name"):
                    return {"question": "商品信息不完整，请告诉我商品名和数量，例如：岩彩一两橙色8套", "state": {"partial_params": params}}

        elif intent == "sales_manage":
            if params.get("action") == "modify":
                return None
            if params.get("target") == "unknown" or not params.get("target"):
                return {"question": "请问要删除哪个销售单？例如：删除销售单142 或 删除测试客户的所有销售单", "state": {"partial_params": params}}

        elif intent == "sales_query":
            if not (params.get("customer") or params.get("sales_id")):
                if not params.get("count"):
                    return {"question": "请问要查哪个客户或哪个销售单号？", "state": {"partial_params": params}}

        elif intent == "print":
            if not (params.get("customer") or params.get("sales_id")):
                return {"question": "请问要打印哪个客户的最新销售单，或哪个销售单号？", "state": {"partial_params": params}}

        elif intent == "customer_manage":
            if not (params.get("customer") or params.get("name")):
                return {"question": "请告诉我要创建的客户名称。", "state": {"partial_params": params}}

        elif intent == "workflow":
            if params.get("action") == "query":
                return None
            if params.get("action") == "delete":
                if params.get("workflow_ids") or params.get("order_id") or params.get("ids"):
                    return None
                return {
                    "question": "请告诉我要删除哪个工作流订单号，例如：删除工作流订单139",
                    "state": {"partial_params": params},
                }
            if not params.get("customer"):
                return {"question": "请问工作流订单是哪个客户？", "state": {"partial_params": params}}
            if not (params.get("goods_name") or params.get("product_name") or params.get("products")):
                return {"question": "请问工作流订单是什么商品？", "state": {"partial_params": params}}
            if not (params.get("quantity") or params.get("qty")):
                return {"question": "请问工作流订单数量是多少？", "state": {"partial_params": params}}

        return None  # 参数OK

    def _extract_answer_params(self, intent: str, user_input: str, partial: dict) -> dict:
        """从用户回答中提取参数（追问合并阶段，不重新分类意图）"""
        new_params = {}
        text = user_input.strip()
        import re

        if intent == "order":
            if not partial.get("customer"):
                new_params["customer"] = text
            elif not partial.get("products"):
                import re
                products = []
                for m in re.finditer(r'([\u4e00-\u9fa5]+)\s*(\d+)\s*(套|张|个|件|捆|斤)', text):
                    products.append({
                        "name": m.group(1),
                        "qty": int(m.group(2)),
                        "unit": m.group(3),
                        "color": ""
                    })
                if products:
                    new_params["products"] = products

        elif intent == "inventory":
            if not partial.get("product_name"):
                colors = ["红色", "黄色", "橙色", "蓝色", "绿色", "橄榄绿", "咖色", "深咖色", "古铜色", "黑色", "白色", "紫色", "粉色"]
                product_name = text
                color = ""
                for c in colors:
                    if c in text:
                        color = c
                        product_name = text.replace(c, "").strip()
                        break
                new_params["product_name"] = product_name
                if color:
                    new_params["color"] = color

        elif intent == "workflow":
            import re
            if partial.get("action") == "delete":
                ids = re.findall(r'\d+', text)
                if ids:
                    new_params["workflow_ids"] = ids
                    if len(ids) == 1:
                        new_params["order_id"] = ids[0]
            elif not partial.get("customer"):
                new_params["customer"] = text
            elif not (partial.get("goods_name") or partial.get("product_name") or partial.get("products")):
                new_params["goods_name"] = text
            elif not (partial.get("quantity") or partial.get("qty")):
                m = re.search(r'\d+', text)
                if m:
                    new_params["quantity"] = int(m.group(0))

        elif intent == "sales_query":
            import re
            count_match = re.search(r'(?:最近|近|最后)\s*(\d+|一|二|两|三|四|五|六|七|八|九|十)\s*(?:个|条|单)?', text)
            if count_match:
                new_params["count"] = self._parse_count(count_match.group(1))
            sid = re.search(r'\d+', text)
            if sid and "count" not in new_params:
                new_params["sales_id"] = int(sid.group(0))
            else:
                new_params["customer"] = text

        elif intent == "customer_manage":
            if not (partial.get("customer") or partial.get("name")):
                cleaned = self._extract_customer_manage_params(text).get("customer") or text
                new_params["customer"] = cleaned.strip()
            phone = re.search(r"1[3-9]\d{9}", text)
            if phone:
                new_params["contacts_tel"] = phone.group(0)
            contact = re.search(r"(?:联系人|老板|对接人)[:：]?\s*([\u4e00-\u9fa5A-Za-z]{2,6})", text)
            if contact:
                new_params["contacts_name"] = contact.group(1)

        elif intent == "print":
            parsed = self._extract_print_params(text)
            for key in ("customer", "sales_id", "count"):
                if parsed.get(key):
                    new_params[key] = parsed[key]
            if not new_params and text:
                new_params["customer"] = text

        elif intent in ("stocktaking", "purchase"):
            if not partial.get("products"):
                import re
                products = []
                for m in re.finditer(r'([\u4e00-\u9fa5]+)\s*(\d+)\s*(套|张|个|件|捆|斤)', text):
                    products.append({
                        "name": m.group(1),
                        "quantity": int(m.group(2)),
                        "unit": m.group(3)
                    })
                if products:
                    new_params["products"] = products

        elif intent == "transfer":
            parsed = self._extract_transfer_params(text)
            for key in ("from", "to", "products"):
                if parsed.get(key) and not partial.get(key):
                    new_params[key] = parsed[key]
            if partial.get("products") and parsed.get("products"):
                new_params["products"] = parsed["products"]

        elif intent == "series_manage":
            series = self._extract_series_names(text)
            if series:
                new_params["series"] = series
            if not partial.get("action"):
                new_params["action"] = self._detect_series_action(text)

        return new_params

    def _is_new_request(self, user_input: str, state: dict) -> bool:
        """判断用户输入是否为新请求（而非对 pending skill 的回复）"""
        text = user_input.strip()

        # 简短肯定词（<=6字）→ 不是新请求，是确认
        confirm_words = ["确认", "是", "对", "好的", "删", "删除", "yes", "ok", "取消", "不删"]
        if len(text) <= 6 and any(w in text for w in confirm_words):
            return False

        # 长输入（>6字）且包含明确新指令词 → 新请求
        new_request_words = ["删除", "所有", "全部", "最后", "几个", "批量", "查询", "下单", "库存", "进货", "调拨", "调货", "盘点", "客户"]
        if len(text) > 6 and any(w in text for w in new_request_words):
            return True

        # 包含数字且长度>5 → 可能是新的操作
        if len(text) > 5 and re.search(r'\d{2,}', text):
            nums = re.findall(r'\d+', text)
            state_ids = state.get("sales_ids", [])
            if nums and not any(n in state_ids for n in nums):
                return True

        return False

    def _is_cancel_request(self, user_input: str) -> bool:
        text = user_input.strip()
        return text in {"取消", "不用了", "没事了", "算了", "停止", "先不弄了"} or any(
            w in text for w in ["取消当前", "不用查了", "不用下了", "不用创建了", "不查了", "先不查", "换个事"]
        )

    def _route_cancel_to_pending(self, intent: str | None, state: dict | None, user_input: str) -> bool:
        """Some prompts use the UI cancel button as a negative choice, not as global stop."""
        text = user_input.strip()
        return (
            intent == "order"
            and (state or {}).get("pending_action") == "confirm_self_ship"
            and text in {"取消", "不用", "不用了", "不要", "否", "不"}
        )

    def _decide_pending_action(self, user_input: str, intent: str, state: dict, history: list[dict]) -> str:
        """Decide whether the current message answers the pending question or starts a new task."""
        text = user_input.strip()
        if self._route_cancel_to_pending(intent, state, text):
            return "answer_pending"
        if self._is_cancel_request(text):
            return "cancel"
        if (
            intent == "order"
            and state.get("pending_action") == "confirm_self_ship"
            and any(w in text for w in ["进货", "入库", "补货", "先进货", "直接进货"])
        ):
            return "answer_pending"

        fast = self._fast_extract(text)
        if fast and fast.get("intent") and fast.get("intent") != intent:
            return "new_request"
        if intent == "workflow" and fast and fast.get("intent") == "workflow":
            old_action = state.get("partial_params", {}).get("action") or state.get("action")
            new_action = fast.get("action")
            if old_action and new_action and old_action != new_action:
                return "new_request"

        if self._looks_like_explicit_new_topic(text):
            return "new_request"
        if self._looks_like_pending_answer(text, intent, state):
            return "answer_pending"

        return self._llm_decide_pending_action(text, intent, state, history)

    def _looks_like_explicit_new_topic(self, text: str) -> bool:
        if any(w in text for w in ["你好", "谢谢", "你是谁", "能做什么", "帮助", "功能"]):
            return True
        new_topic_words = [
            "查库存", "库存", "有货", "下单", "开单", "创建工作流", "工作流订单",
            "删除", "作废", "进货", "入库", "调拨", "调货", "盘点", "查询销售单", "查订单",
        ]
        return any(w in text for w in new_topic_words)

    def _looks_like_pending_answer(self, text: str, intent: str, state: dict) -> bool:
        partial = state.get("partial_params", {})
        if intent == "bag_upload":
            return bool(text)
        if len(text) <= 8 and text in {"是", "对", "确认", "好的", "可以", "行", "不", "不要", "不删"}:
            return True
        if intent == "sales_query":
            return bool(re.fullmatch(r'[\u4e00-\u9fa5A-Za-z0-9（）()【】\-]+', text)) and not any(
                w in text for w in ["库存", "下单", "删除", "进货", "调拨", "盘点", "工作流"]
            )
        if intent == "workflow":
            if not partial.get("customer"):
                return bool(re.fullmatch(r'[\u4e00-\u9fa5A-Za-z0-9（）()【】\-]+', text))
            if not (partial.get("goods_name") or partial.get("product_name") or partial.get("products")):
                return "查询" not in text and "查" not in text
            if not (partial.get("quantity") or partial.get("qty")):
                return bool(re.search(r'\d+', text))
        if intent == "customer_manage":
            if not (partial.get("customer") or partial.get("name")):
                return bool(re.search(r'[\u4e00-\u9fa5A-Za-z0-9]', text))
            return len(text) <= 20 and not any(w in text for w in ["库存", "下单", "开单", "删除", "进货", "调拨", "盘点", "工作流"])
        if intent == "print":
            return bool(re.search(r'[\u4e00-\u9fa5A-Za-z0-9]', text)) and not any(
                w in text for w in ["库存", "下单", "开单", "删除", "进货", "调拨", "盘点", "工作流"]
            )
        if intent == "order":
            if not partial.get("customer"):
                return bool(re.fullmatch(r'[\u4e00-\u9fa5A-Za-z0-9（）()【】\-]+', text))
            if not partial.get("products"):
                return bool(re.search(r'\d+\s*(套|张|个|件|捆|斤)', text))
        if intent == "transfer":
            if not (partial.get("from") and partial.get("to")):
                return any(w in text for w in ["自己", "店里", "本店", "百鑫", "到", "从"])
            if not partial.get("products"):
                return bool(re.search(r'\d+\s*(套|张|个|件|捆|斤)', text))
        return False

    def _llm_decide_pending_action(self, text: str, intent: str, state: dict, history: list[dict]) -> str:
        try:
            from src.core.llm import llm_json
            prompt = """你是肆计包装-北极星订单管理机器人的上下文守门员。
判断用户当前这句话是在回答上一轮追问，还是已经换成了新请求，或者取消当前操作。
只返回JSON：{"action":"answer_pending/new_request/cancel"}。

判断原则：
- 如果用户明确说取消、不用了、没事了、算了，返回 cancel。
- 如果用户在提供上一轮缺少的信息，如客户名、商品名、数量、确认词，返回 answer_pending。
- 如果用户开始问库存、下单、删除、查询别的订单、闲聊、问功能，返回 new_request。
- 不要为了完成旧流程硬把新话题当成参数。"""
            result = llm_json(prompt, f"pending_intent={intent}\npending_state={state}\n当前用户：{text}", history)
            action = result.get("action", "")
            if action in {"answer_pending", "new_request", "cancel"}:
                return action
        except Exception as e:
            logger.warning(f"[SkillEngine] pending 上下文判断失败: {e}")
        return "answer_pending"

    def _handle_result(self, session: SessionManager, intent: str, user_input: str, result: dict) -> str:
        """处理 workflow 返回结果"""
        if result.get("status") == "ask":
            # 需要问用户 → 保存状态
            session.save_pending(result.get("intent") or intent, result["state"])
            session.save_turn(user_input, result["question"])
            return result["question"]
        else:
            # 流程完成 → 清除状态，保存历史
            session.clear_pending()
            reply = result.get("reply", "处理完成。")
            session.save_turn(user_input, reply)
            return reply
