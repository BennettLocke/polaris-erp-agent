"""
文字下单固定流程（流程 B）

步骤：
B1. 接收资料 → LLM 提取参数
B2. 查询信息（客户 + 商品）
B3. 查价格
B4. 库存决策
B5. 开销售单
"""
import json
import re
from src.skills.base import BaseWorkflow
from src.core.tools.caller import get_tool_caller
from src.core.config import get_config
from src.utils import get_logger
from scripts.common.unit_converter import calculate_purchase_quantity, is_one_piece_order

logger = get_logger("sjagent.skills.order_flow")

# 不查库存的类别（非礼盒类，直接从百鑫发货）
NON_CHECK_CATEGORIES = ["泡袋", "包茶", "内衬", "PVC", "标签", "纸箱", "烫金泡袋", "提袋UV", "提袋丝印", "烫膜"]

# 单位映射
UNIT_MAP = {"套": 1, "捆": 2, "个": 3, "斤": 4, "张": 5, "件": 1}


class OrderFlowWorkflow(BaseWorkflow):
    """文字下单固定流程"""

    def __init__(self):
        self.caller = get_tool_caller()
        self.config = get_config()

    def execute(self, user_input: str, params: dict = None) -> dict:
        """
        B1: 提取参数（优先用 LLM 预提取的，否则 fallback）
        B2-B5: 固定流程执行
        """
        # 优先使用 LLM 预提取的参数
        if params and params.get("products"):
            # 从统一 LLM 结果中提取订单参数
            logger.info(f"[OrderFlow] B1: 使用预提取参数")
        elif params and not params.get("products"):
            return self._reply("没有识别到商品信息，请重新描述，例如：测试客户 下单 标签4张 岩味半斤红色1套")
        else:
            from src.core.llm import llm_extract_order_params
            logger.info(f"[OrderFlow] B1: LLM 提取参数 - {user_input[:50]}")
            params = llm_extract_order_params(user_input)

        params = params or {}
        params["products"] = self._enrich_order_products(params.get("products", []), user_input)
        customer_name = params.get("customer")
        products = params.get("products", [])
        warehouse_hint = params.get("warehouse")
        logger.info(f"[OrderFlow] 提取结果: customer={customer_name}, products={len(products)}个, warehouse={warehouse_hint}")

        if not products:
            return self._reply("没有识别到商品信息，请重新描述，例如：测试客户 下单 标签4张 岩味半斤红色1套")

        # ---- B2: 查询客户 ----
        logger.info("[OrderFlow] B2: 查询客户")
        customer_id = self._search_customer(customer_name)
        if customer_id is None:
            logger.info(f"[OrderFlow] 客户不存在，自动创建: {customer_name}")
            customer_id = self._create_customer(customer_name)
            if customer_id is None:
                return self._reply(f"客户「{customer_name}」不存在，自动创建也失败了。请到后台确认客户名称后再开单。")

        # ---- B2: 查询商品 ----
        logger.info("[OrderFlow] B2: 查询商品")
        resolved_products = []
        for index, p in enumerate(products):
            resolved = self._search_product(p)
            if resolved is None:
                return self._ask(
                    self._format_product_clarification_question(p),
                    {
                        "customer_id": customer_id,
                        "customer_name": customer_name,
                        "products": products,
                        "product_index": index,
                        "warehouse_hint": warehouse_hint,
                        "pending_action": "confirm_product_name",
                    },
                )
            resolved_products.append(resolved)

        # ---- B3: 查价格 ----
        logger.info("[OrderFlow] B3: 查价格")
        for p in resolved_products:
            self._fill_price(customer_id, p)

        # ---- B4: 库存决策 ----
        logger.info("[OrderFlow] B4: 库存决策")
        inventory_result = self._inventory_decision(resolved_products, warehouse_hint)

        if inventory_result["status"] == "ask":
            # 需要问用户确认仓库/进货等关键动作
            state = {
                "customer_id": customer_id,
                "customer_name": customer_name,
                "products": resolved_products,
                "warehouse_hint": warehouse_hint,
                "pending_action": inventory_result.get("pending_action", "choose_warehouse"),
                "pending_warehouse": inventory_result.get("pending_warehouse"),
            }
            return self._ask(inventory_result["question"], state)

        if inventory_result["status"] == "auto_purchase":
            purchase_result = self._execute_purchase(resolved_products)
            if purchase_result.get("error"):
                return self._reply(f"进货失败：{purchase_result['error']}")

        # ---- B5: 开单 ----
        logger.info("[OrderFlow] B5: 开单")
        warehouse_id = inventory_result.get("warehouse_id", 2)
        return self._create_order(customer_id, customer_name, resolved_products, warehouse_id)

    def resume(self, user_input: str, state: dict) -> dict:
        """Resume a paused order flow after a user confirmation."""
        from src.core.llm import llm_extract_warehouse

        if state.get("pending_action") == "customer_missing":
            customer_name = state.get("customer_name", "")
            products = state.get("products", [])
            warehouse_hint = state.get("warehouse_hint")
            text = user_input.strip()
            if self._is_stop_order(text):
                return self._reply("已取消本次开单。")
            if self._wants_create_customer(text):
                customer_id = self._create_customer(customer_name)
                if not customer_id:
                    return self._reply(f"客户「{customer_name}」创建失败，请到后台确认后再开单。")
                return self._continue_after_product_resolution(customer_id, customer_name, products, warehouse_hint)

            corrected_name = text
            customer_id = self._search_customer(corrected_name)
            if customer_id is None:
                return self._ask(
                    f"客户「{corrected_name}」也没有找到。回复「创建客户」创建「{customer_name}」，或回复正确客户名。",
                    {
                        "customer_name": customer_name,
                        "products": products,
                        "warehouse_hint": warehouse_hint,
                        "pending_action": "customer_missing",
                    },
                )
            return self._continue_after_product_resolution(customer_id, corrected_name, products, warehouse_hint)

        if state.get("pending_action") == "confirm_image_sales":
            if not self._is_yes(user_input):
                return self._reply("已创建工作流订单，未继续开销售单。")
            params = state.get("order_params") or {}
            if not params.get("products"):
                return self._reply("图片识别结果里没有可开单的商品，请重新上传或补充商品信息。")
            return self.execute("图片识别结果确认开单", params=params)

        customer_id = state["customer_id"]
        customer_name = state.get("customer_name", "")
        products = state["products"]
        pending_action = state.get("pending_action", "choose_warehouse")

        if pending_action == "confirm_product_name":
            index = state.get("product_index", 0)
            if self._is_yes(user_input):
                products = self._enrich_order_products(products)
            elif 0 <= index < len(products):
                corrected = user_input.strip()
                corrected_color = self._extract_color(corrected)
                if corrected_color and corrected_color == corrected:
                    products[index]["color"] = corrected_color
                else:
                    products[index]["name"] = corrected
                products = self._enrich_order_products(products)
            return self._continue_after_product_resolution(
                customer_id=customer_id,
                customer_name=customer_name,
                products=products,
                warehouse_hint=state.get("warehouse_hint"),
            )

        if pending_action == "confirm_self_ship":
            if self._is_stop_order(user_input):
                return self._reply("已取消本次开单。")
            if self._wants_purchase(user_input) or not self._is_yes(user_input):
                for p in products:
                    if p.get("pending_self_ship"):
                        p["warehouse_id"] = 2
                        p["need_purchase"] = True
                        p.pop("pending_self_ship", None)
                if not self._need_purchase_confirmation(products):
                    purchase_result = self._execute_purchase(products)
                    if purchase_result.get("error"):
                        return self._reply(f"进货失败：{purchase_result['error']}")
                    return self._create_order(customer_id, customer_name, products, 2)
                return self._ask(
                    self._format_purchase_confirm_question(products, customer_name),
                    {
                        "customer_id": customer_id,
                        "customer_name": customer_name,
                        "products": products,
                        "pending_action": "confirm_purchase",
                    },
                )
            for p in products:
                if p.get("pending_self_ship"):
                    p["warehouse_id"] = 1
                    p.pop("pending_self_ship", None)
            if any(p.get("need_purchase") for p in products):
                if not self._need_purchase_confirmation(products):
                    purchase_result = self._execute_purchase(products)
                    if purchase_result.get("error"):
                        return self._reply(f"进货失败：{purchase_result['error']}")
                    return self._create_order(customer_id, customer_name, products, 2)
                return self._ask(
                    "还有商品百鑫和自己店里都无货，需要先进货到百鑫仓库。请回复「确认」进货并继续开单，或回复「取消」停止。",
                    {
                        "customer_id": customer_id,
                        "customer_name": customer_name,
                        "products": products,
                        "pending_action": "confirm_purchase",
                    },
                )
            return self._create_order(customer_id, customer_name, products, 1)

        if pending_action == "confirm_purchase":
            if not self._is_yes(user_input):
                return self._reply("已取消进货，本次订单未开单。")
            purchase_result = self._execute_purchase(products)
            if purchase_result.get("error"):
                return self._reply(f"进货失败：{purchase_result['error']}")
            return self._create_order(customer_id, customer_name, products, 2)

        warehouse = llm_extract_warehouse(user_input)
        warehouse_id = warehouse["warehouse_id"]
        if warehouse_id == 1:
            for p in products:
                p["pending_self_ship"] = True
            return self._ask(
                "你选择从自己店里发货。请确认是否使用自己店里的库存发货？",
                {
                    "customer_id": customer_id,
                    "customer_name": customer_name,
                    "products": products,
                    "pending_action": "confirm_self_ship",
                },
            )

        for p in products:
            if p.get("pending_warehouse_choice"):
                p["warehouse_id"] = 2
                p.pop("pending_warehouse_choice", None)
        if any(p.get("need_purchase") for p in products):
            if not self._need_purchase_confirmation(products):
                purchase_result = self._execute_purchase(products)
                if purchase_result.get("error"):
                    return self._reply(f"进货失败：{purchase_result['error']}")
                return self._create_order(customer_id, customer_name, products, 2)
            return self._ask(
                "还有商品百鑫和自己店里都无货，需要先进货到百鑫仓库。请回复「确认」进货并继续开单，或回复「取消」停止。",
                {
                    "customer_id": customer_id,
                    "customer_name": customer_name,
                    "products": products,
                    "pending_action": "confirm_purchase",
                },
            )
        logger.info(f"[OrderFlow] resume warehouse={warehouse['warehouse_name']}(id={warehouse_id})")
        return self._create_order(customer_id, customer_name, products, warehouse_id)

    # ---- 内部方法 ----

    def _continue_after_product_resolution(
        self,
        customer_id: int,
        customer_name: str,
        products: list[dict],
        warehouse_hint: str | None,
    ) -> dict:
        """Continue order flow after the user corrected a product name."""
        products = self._enrich_order_products(products)
        resolved_products = []
        for index, p in enumerate(products):
            resolved = self._search_product(p)
            if resolved is None:
                return self._ask(
                    self._format_product_clarification_question(p, retry=True),
                    {
                        "customer_id": customer_id,
                        "customer_name": customer_name,
                        "products": products,
                        "product_index": index,
                        "warehouse_hint": warehouse_hint,
                        "pending_action": "confirm_product_name",
                    },
                )
            resolved_products.append(resolved)

        for p in resolved_products:
            self._fill_price(customer_id, p)

        inventory_result = self._inventory_decision(resolved_products, warehouse_hint)
        if inventory_result["status"] == "ask":
            return self._ask(
                inventory_result["question"],
                {
                    "customer_id": customer_id,
                    "customer_name": customer_name,
                    "products": resolved_products,
                    "warehouse_hint": warehouse_hint,
                    "pending_action": inventory_result.get("pending_action", "choose_warehouse"),
                    "pending_warehouse": inventory_result.get("pending_warehouse"),
                },
            )
        if inventory_result["status"] == "auto_purchase":
            purchase_result = self._execute_purchase(resolved_products)
            if purchase_result.get("error"):
                return self._reply(f"进货失败：{purchase_result['error']}")
        return self._create_order(customer_id, customer_name, resolved_products, inventory_result.get("warehouse_id", 2))

    def _search_customer(self, name: str) -> int | None:
        """B2: 搜索客户，返回 customer_id"""
        if not name:
            return None
        try:
            results = self.caller.call("customer_query", keyword=name)
            if results:
                cid = results[0].get("id")
                logger.info(f"[OrderFlow] 客户找到: {name} → id={cid}")
                return int(cid) if cid else None
        except Exception as e:
            logger.warning(f"[OrderFlow] 客户查询失败: {e}")
        return None

    def _create_customer(self, name: str) -> int | None:
        if not name:
            return None
        try:
            result = self.caller.call("customer_create", name=name, contacts_name="", contacts_tel="")
            if isinstance(result, dict) and result.get("error"):
                logger.warning(f"[OrderFlow] 客户创建失败: {result['error']}")
                return None
        except Exception as e:
            logger.warning(f"[OrderFlow] 客户创建异常: {e}")
            return None
        return self._search_customer(name)

    def _search_product(self, product: dict) -> dict | None:
        """B2: 搜索商品，返回解析后的商品信息"""
        name = product["name"]
        color = product.get("color", "")
        qty = product.get("qty") or product.get("quantity") or 1
        unit = product.get("unit", "套")
        price_override = self._parse_price(product.get("price") or product.get("unit_price"))

        keyword = self._normalize_product_name(name)
        results = self._search_product_candidates(keyword, color)
        logger.info(f"[OrderFlow] 搜索 '{keyword}', color={color} → {len(results)} 条候选")

        target = self._select_confirmed_product(results, keyword, color)
        if target is None:
            llm_keywords = self._llm_product_keywords(name, color)
            for llm_keyword in llm_keywords:
                if llm_keyword == keyword:
                    continue
                llm_results = self._search_product_candidates(llm_keyword, color)
                target = self._select_confirmed_product(llm_results, llm_keyword, color)
                if target is not None:
                    keyword = llm_keyword
                    results = llm_results
                    break
            if target is None:
                logger.warning(f"[OrderFlow] 商品未唯一确认: name={name}, color={color}, results={len(results)}")
                return None

        product_id = target.get("id") or target.get("product_id")
        if product_id and ("产品名称" in target or not target.get("price")):
            detail = self._product_detail(product_id)
            if detail:
                target = {**target, **detail}
        product_title = target.get("title", name)
        spec = target.get("spec", "")
        simple_desc = target.get("simple_desc", "")
        price = price_override if price_override is not None else target.get("price", 0)
        if not product_id:
            logger.warning(f"[OrderFlow] product_id 未确认: product_id={product_id}")
            return None

        # 如果单位是"件"，需要查 simple_desc 换算
        if unit == "件":
            sets_per_case = self._parse_sets_per_case(simple_desc)
            if not sets_per_case:
                logger.warning(f"[OrderFlow] 件套换算失败: product={product_title}, simple_desc={simple_desc}")
                return None
            qty = qty * sets_per_case
            unit = "套"
            logger.info(f"[OrderFlow] 件套换算: {product['name']} {product.get('qty',1)}件 × {sets_per_case}套/件 = {qty}套")

        unit_id = self._lookup_unit_id(unit)
        if not unit_id:
            logger.warning(f"[OrderFlow] unit_id 未确认: unit={unit}")
            return None

        resolved = {
            "product_id": int(product_id) if product_id else 0,
            "name": product_title,
            "spec": spec,
            "color": color or spec,
            "qty": qty,
            "unit": unit,
            "unit_id": int(unit_id),
            "price": float(price) if price else 0,
            "price_overridden": price_override is not None,
            "simple_desc": simple_desc,
        }
        logger.info(f"[OrderFlow] 商品解析: {resolved['name']} {spec} → id={product_id}, qty={qty}, unit={unit}")
        return resolved

    def _enrich_order_products(self, products: list[dict], user_input: str = "") -> list[dict]:
        enriched = []
        text_color = self._extract_color(user_input)
        for product in products or []:
            p = dict(product)
            if "qty" not in p and "quantity" in p:
                p["qty"] = p.get("quantity")
            if "quantity" not in p and "qty" in p:
                p["quantity"] = p.get("qty")
            p["qty"] = int(p.get("qty") or p.get("quantity") or 1)
            p["quantity"] = int(p.get("quantity") or p["qty"])
            p.setdefault("unit", "套")
            if text_color and not p.get("color"):
                p["color"] = text_color
            p.setdefault("color", "")
            if p.get("name") and p.get("color"):
                p["name"] = str(p["name"]).replace(str(p["color"]), "").strip()
            p["name"] = self._normalize_product_name(p.get("name", ""))
            if p.get("price") is None:
                parsed_price = self._extract_price_override(user_input)
                if parsed_price is not None:
                    p["price"] = parsed_price
            enriched.append(p)
        return enriched

    def _parse_price(self, value) -> float | None:
        if value in (None, ""):
            return None
        try:
            price = float(value)
        except (TypeError, ValueError):
            return None
        return price if price > 0 else None

    def _extract_price_override(self, text: str) -> float | None:
        match = re.search(r"(?:价格|单价|改价)\s*(?:改|改成|设为|设置为|按)?\s*(\d+(?:\.\d+)?)\s*元?", str(text or ""))
        if not match:
            return None
        return self._parse_price(match.group(1))

    def _parse_sets_per_case(self, simple_desc: str) -> int | None:
        """从 simple_desc 中解析每件套数，如 '规格：20套/件' → 20"""
        import re
        if not simple_desc:
            return None
        patterns = [
            r'(\d+)\s*套\s*/\s*件',
            r'(\d+)\s*个\s*/\s*件',
            r'(\d+)\s*张\s*/\s*件',
            r'(\d+)\s*套\s*[/／]?\s*1?\s*件',
            r'1\s*件\s*(\d+)\s*套',
            r'每\s*件\s*(\d+)\s*套',
        ]
        for pattern in patterns:
            m = re.search(pattern, simple_desc)
            if m:
                return int(m.group(1))
        return None

    def _normalize_product_name(self, name: str) -> str:
        """Normalize common OCR/order aliases before DB lookup."""
        normalized = re.sub(r'【[^】]+】', '', name or '').strip()
        for color in self._colors():
            normalized = normalized.replace(color, "")
        normalized = re.sub(r"(?:3\s*两|2\s*两|(?<!二)三两|二两)", "二三两", normalized)
        normalized = re.sub(r"(?:2\s*大盒|两\s*大盒|二\s*大盒)", "两大盒", normalized)
        normalized = re.sub(r"(?:2\s*泡(?:盒|装小盒)?|二\s*泡(?:盒|装小盒)?|两\s*泡(?:盒|装小盒)?)", "两泡装小盒", normalized)
        normalized = re.sub(r"(?:0\.5\s*斤|半\s*斤)", "半斤", normalized)
        normalized = re.sub(r"(?:1\s*两|一\s*两)", "一两", normalized)
        replacements = [
            ("2小盒", "二小盒"),
            ("3小盒", "三小盒"),
            ("6小盒", "六小盒"),
            ("10小盒", "十小盒"),
        ]
        for raw, new in replacements:
            normalized = normalized.replace(raw, new)
        specs = ["五格短半斤", "短半斤", "二三两", "两大盒", "两泡装小盒", "三小盒", "六小盒", "十小盒", "长半斤", "半斤", "一两"]
        for spec in specs:
            normalized = re.sub(rf"(?<!^)(?<!\s)({re.escape(spec)})", r" \1", normalized)
        return re.sub(r"\s+", " ", normalized).strip()

    def _search_product_candidates(self, keyword: str, color: str = "") -> list[dict]:
        candidates = []
        seen = set()
        for kw in self._product_keywords(keyword):
            try:
                rows = self.caller.call("product_search", keyword=kw)
            except Exception as e:
                logger.warning(f"[OrderFlow] 商品搜索失败: {e}")
                rows = []
            for row in rows or []:
                key = (row.get("id"), row.get("spec"))
                if key in seen:
                    continue
                seen.add(key)
                candidates.append(row)

            if color:
                try:
                    inventory_rows = self.caller.call("inventory_search", keyword=kw, color=color, only_in_stock=False, limit=60)
                except Exception:
                    inventory_rows = []
                for row in inventory_rows or []:
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
        return candidates

    def _product_keywords(self, name: str) -> list[str]:
        specs = ["五格短半斤", "短半斤", "二三两", "两大盒", "两泡装小盒", "三小盒", "六小盒", "十小盒", "长半斤", "半斤", "一两"]
        normalized = self._normalize_product_name(name)
        keywords = [normalized]
        for spec in specs:
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

    def _product_terms(self, keyword: str) -> list[str]:
        specs = ["五格短半斤", "短半斤", "二三两", "两大盒", "两泡装小盒", "三小盒", "六小盒", "十小盒", "长半斤", "半斤", "一两"]
        normalized = self._normalize_product_name(keyword)
        for spec in specs:
            if spec in normalized:
                brand = normalized.replace(spec, "").strip()
                return [term for term in (brand, spec) if term]
        return [normalized] if normalized else []

    def _format_product_clarification_question(self, product: dict, retry: bool = False) -> str:
        desc = self._product_desc(product)
        prefix = "仍然没有唯一匹配到" if retry else "没有唯一匹配到"
        lines = [f"商品「{desc}」{prefix}数据库商品，请补充更准确的商品名称、规格或颜色。"]
        candidates = self._preview_product_candidates(product)
        if candidates:
            lines.append("")
            lines.append("我找到一些可能相关的商品：")
            for idx, row in enumerate(candidates[:8], 1):
                title = row.get("title") or row.get("产品名称") or ""
                spec = row.get("spec") or row.get("【颜色】") or ""
                lines.append(f"{idx}. {title}{(' ' + spec) if spec else ''}")
            specs = [str(row.get("spec") or row.get("【颜色】") or "").strip() for row in candidates]
            specs = [spec for spec in dict.fromkeys(specs) if spec]
            if len(specs) >= 2:
                lines.append(f"请直接回复颜色：{' / '.join(specs[:8])}。")
            else:
                lines.append("请直接回复要用哪一个，例如：茶客两泡装小盒红色。")
        else:
            lines.append("我不会自动改用相似商品，避免把一个商品错开成另一个商品。")
        return "\n".join(lines)

    def _preview_product_candidates(self, product: dict) -> list[dict]:
        name = product.get("name", "")
        color = product.get("color", "")
        keyword = self._normalize_product_name(name)
        candidates = self._search_product_candidates(keyword, color)
        if candidates:
            return candidates
        compact = keyword.replace(" ", "")
        for fallback in [compact[:2]]:
            if len(fallback) < 2 or fallback == keyword:
                continue
            candidates = self._search_product_candidates(fallback, color)
            if candidates:
                return candidates
        return []

    def _product_detail(self, product_id) -> dict | None:
        try:
            return self.caller.call("product_info", product_id=int(product_id))
        except Exception as e:
            logger.warning(f"[OrderFlow] 商品详情查询失败: {e}")
            return None

    def _llm_product_keywords(self, name: str, color: str = "") -> list[str]:
        try:
            from src.core.llm import llm_json
            result = llm_json(
                """你是商品搜索关键词纠错器。把用户/OCR商品名转成适合数据库搜索的礼盒关键词，返回JSON：
{"keywords":["品牌 规格", "品牌", "规格"]}
规则：
- 3两/三两/2两/二两 都归一为 二三两
- 2泡盒/二泡盒/两泡盒 都归一为 两泡装小盒
- 3小盒/三小盒 归一为 三小盒，6小盒为 六小盒，10小盒为 十小盒
- 去掉颜色、数量、工艺词，只保留品牌和规格
- 不要编造品牌，只输出可能的搜索关键词""",
                f"商品名：{name}\n颜色：{color}",
            )
            keywords = result.get("keywords") or []
            return [self._normalize_product_name(str(item)) for item in keywords if str(item).strip()]
        except Exception as e:
            logger.warning(f"[OrderFlow] LLM 商品关键词纠错失败: {e}")
            return []

    def _colors(self) -> list[str]:
        return ["香槟金", "橄榄绿", "深咖色", "古铜色", "红色", "黄色", "金色", "橙色", "蓝色", "绿色", "咖色", "黑色", "白色", "银色", "灰色", "紫色", "粉色"]

    def _extract_color(self, text: str) -> str:
        for color in self._colors():
            if color in str(text or ""):
                return color
        return ""

    def _lookup_unit_id(self, unit_name: str) -> int | None:
        """Look up unit_id from ERP unit table instead of hardcoding it."""
        aliases = {
            "套": ("套",),
            "个": ("个",),
            "张": ("张",),
            "件": ("件",),
            "捆": ("捆",),
            "斤": ("斤",),
        }
        expected_names = aliases.get(unit_name, (unit_name,))
        try:
            units = self.caller.call("get_unit_list")
        except Exception as e:
            logger.warning(f"[OrderFlow] 单位表查询失败: {e}")
            return None
        for row in units:
            name = str(row.get("name", ""))
            if name in expected_names:
                return int(row.get("id"))
        return None

    def _select_confirmed_product(self, results: list[dict], keyword: str, color: str) -> dict | None:
        """Return one DB-confirmed product, or None when matching is ambiguous."""
        if not results:
            return None

        candidates = results
        if color:
            color_matches = [r for r in candidates if color in str(r.get("spec", ""))]
            if not color_matches:
                return None
            candidates = color_matches

        terms = self._product_terms(keyword)
        term_matches = [
            r for r in candidates
            if all(term in re.sub(r"[【】]", "", str(r.get("title", ""))) for term in terms)
        ]
        if len(term_matches) == 1:
            return term_matches[0]
        if term_matches:
            candidates = term_matches

        exact = [
            r for r in candidates
            if keyword and keyword in str(r.get("title", ""))
        ]
        if len(exact) == 1:
            return exact[0]
        if len(candidates) == 1:
            return candidates[0]
        return None

    def _product_desc(self, product: dict) -> str:
        return (
            f"{product.get('name', '')}"
            f"{(' ' + product.get('color', '')) if product.get('color') else ''}"
            f" {product.get('qty') or product.get('quantity') or ''}{product.get('unit', '套')}"
        ).strip()

    def _fill_price(self, customer_id: int, product: dict):
        """B3: 填充价格（优先历史价，其次零售价）"""
        if product.get("price_overridden"):
            logger.info(f"[OrderFlow] 用户指定价格: {product['name']} = {product['price']}")
            return
        if product["price"] > 0:
            return  # 已有价格

        # 查历史成交价
        try:
            history = self.caller.call("sales_history_price",
                customer_id=customer_id,
                product_id=product["product_id"],
            )
            if history and isinstance(history, (int, float)) and history > 0:
                product["price"] = float(history)
                logger.info(f"[OrderFlow] 历史价: {product['name']} = {history}")
                return
        except Exception:
            pass

        # 用零售价（search_product 已返回 price）
        # 如果还是 0，用 0（开单时 API 会用默认价）
        logger.info(f"[OrderFlow] 价格: {product['name']} = {product['price']}（零售价）")

    def _inventory_decision(self, products: list[dict], warehouse_hint: str | None) -> dict:
        """
        B4: 库存决策

        返回:
            {"status": "ok", "warehouse_id": 2}  → 不需要问用户
            {"status": "ask", "question": "...", "pending_warehouse": [...]}  → 需要问用户
        """
        # 如果用户已指定仓库，百鑫可直接走；自己店里必须二次确认。
        if warehouse_hint and warehouse_hint not in ("不指定", "未指定", "无", "null", ""):
            wid = 1 if "自己" in warehouse_hint or "店里" in warehouse_hint else 2
            for p in products:
                if wid == 1:
                    p["pending_self_ship"] = True
                else:
                    p["warehouse_id"] = wid
            if wid == 1:
                return {
                    "status": "ask",
                    "question": "你指定从自己店里发货。请确认是否使用自己店里的库存发货？",
                    "pending_action": "confirm_self_ship",
                }
            return {"status": "ok", "warehouse_id": wid}

        # 检查是否所有商品都是非礼盒类
        all_non_gift = all(self._is_non_gift(p["name"]) for p in products)
        logger.info(f"[OrderFlow] all_non_gift={all_non_gift}, products={[p['name'] for p in products]}")
        if all_non_gift:
            # 非礼盒类全部从百鑫发货
            for p in products:
                p["warehouse_id"] = 2
            return {"status": "ok", "warehouse_id": 2}

        # 有礼盒类商品 → 需要查库存
        need_warehouse_ask = []
        for p in products:
            is_non = self._is_non_gift(p["name"])
            logger.info(f"[OrderFlow] 库存判断: {p['name']} → 非礼盒={is_non}")
            if is_non:
                p["warehouse_id"] = 2
                continue

            # 查库存
            inventory = self._query_inventory(p["product_id"])
            baixin_qty = inventory.get("百鑫仓库", 0)
            self_qty = inventory.get("自己店里", 0)

            p["inventory"] = inventory
            logger.info(f"[OrderFlow] 库存: {p['name']} → 百鑫={baixin_qty}, 自己={self_qty}")

            if baixin_qty > 0 and self_qty > 0:
                # 两个仓库都有货 → 需要问用户
                p["pending_warehouse_choice"] = True
                need_warehouse_ask.append(p)
            elif baixin_qty > 0:
                p["warehouse_id"] = 2
            elif self_qty > 0:
                p["pending_self_ship"] = True
                need_warehouse_ask.append(p)  # 只有自己店里有，需要确认
            else:
                # 都无货 → 需要进货
                p["warehouse_id"] = 2
                p["need_purchase"] = True

        if need_warehouse_ask:
            # 构建问题
            names = "、".join([p["name"] + (f" {p['color']}" if p.get("color") else "") for p in need_warehouse_ask])
            inv_text = "\n".join([
                f"- {p['name']}{(' ' + p['color']) if p.get('color') else ''}: 自己店里{p['inventory'].get('自己店里', 0)}套, 百鑫{p['inventory'].get('百鑫仓库', 0)}套"
                for p in need_warehouse_ask
            ])
            if all(p.get("pending_self_ship") for p in need_warehouse_ask):
                question = f"以下商品百鑫无货，但自己店里有货。请确认是否从自己店里调货/发货：\n{inv_text}\n\n回复「确认」从自己店里发货，回复「取消」则改为先进货到百鑫仓库。"
                return {"status": "ask", "question": question, "pending_action": "confirm_self_ship"}
            question = f"以下商品需要选择发货仓库：\n{inv_text}\n\n请回复「自己店里」或「百鑫」。如果选择自己店里，我会再让你确认一次。"
            return {"status": "ask", "question": question, "pending_action": "choose_warehouse", "pending_warehouse": need_warehouse_ask}

        need_purchase = [p for p in products if p.get("need_purchase")]
        if need_purchase:
            if not self._need_purchase_confirmation(products):
                return {
                    "status": "auto_purchase",
                    "warehouse_id": 2,
                }
            return {
                "status": "ask",
                "question": self._format_purchase_confirm_question(products),
                "pending_action": "confirm_purchase",
            }

        return {"status": "ok", "warehouse_id": 2}

    def _wants_purchase(self, text: str) -> bool:
        value = (text or "").strip()
        return any(w in value for w in ["进货", "入库", "补货", "先进货", "直接进货"])

    def _wants_create_customer(self, text: str) -> bool:
        value = (text or "").strip()
        return any(w in value for w in ["创建", "新建", "新增", "添加", "建立", "建客户", "创建客户"])

    def _is_stop_order(self, text: str) -> bool:
        value = (text or "").strip()
        return any(w in value for w in ["停止", "取消当前", "整单取消", "不下了", "不用下了", "不开了", "先不弄了"])

    def _format_purchase_confirm_question(self, products: list[dict], customer_name: str = "") -> str:
        need_purchase = [p for p in products if p.get("need_purchase")]
        lines = [f"将先给{customer_name or '客户'}的订单进货到百鑫仓库，再继续开销售单。请确认执行："]
        for p in need_purchase:
            lines.append(self._format_purchase_plan_line(p))
        lines.append("回复「确认」执行进货并开单，回复「取消」停止。")
        return "\n".join(lines)

    def _need_purchase_confirmation(self, products: list[dict]) -> bool:
        """Only one-piece-order purchases require an explicit confirmation in order flow."""
        need_purchase = [p for p in products if p.get("need_purchase")]
        if not need_purchase:
            return False
        return any(self._purchase_requires_confirmation(p) for p in need_purchase)

    def _purchase_requires_confirmation(self, product: dict) -> bool:
        plan = self._annotate_purchase_plan(product)
        return plan.get("purchase_unit") == "件" and bool(plan.get("per_piece"))

    def _format_purchase_plan_line(self, product: dict) -> str:
        plan = self._annotate_purchase_plan(product)
        desc = f"{product.get('name', '商品')}{(' ' + product.get('color', '')) if product.get('color') else ''}"
        order_qty = product.get("qty", 1)
        order_unit = product.get("unit", "套")
        purchase_qty = plan["purchase_qty"]
        purchase_unit = plan["purchase_unit"]
        if purchase_unit == "件" and plan.get("per_piece"):
            return f"- {desc}：订单{order_qty}{order_unit}，进货{purchase_qty}件（{plan['per_piece']}套/件）"
        return f"- {desc}：订单{order_qty}{order_unit}，进货{purchase_qty}{purchase_unit}"

    def _annotate_purchase_plan(self, product: dict) -> dict:
        order_qty = int(product.get("qty") or 1)
        order_unit = product.get("unit") or "套"
        per_piece = self._parse_sets_per_case(product.get("simple_desc", "")) or 0
        product_name = f"{product.get('name', '')} {product.get('title', '')}".strip()

        should_use_piece = order_unit == "套" and per_piece > 1 and is_one_piece_order(product_name)
        if should_use_piece:
            purchase_qty = calculate_purchase_quantity(order_qty, per_piece, product_name)
            purchase_unit = "件"
        else:
            purchase_qty = order_qty
            purchase_unit = order_unit

        product["purchase_qty"] = int(purchase_qty)
        product["purchase_unit"] = purchase_unit
        product["purchase_per_piece"] = per_piece
        return {"purchase_qty": int(purchase_qty), "purchase_unit": purchase_unit, "per_piece": per_piece}

    def _is_non_gift(self, product_name: str) -> bool:
        """判断是否非礼盒类（不需要查库存）"""
        return any(cat in product_name for cat in NON_CHECK_CATEGORIES)

    def _is_yes(self, text: str) -> bool:
        """Conservative confirmation parser for irreversible inventory/order actions."""
        value = (text or "").strip().lower()
        yes_words = ("确认", "同意", "可以", "是", "好", "好的", "继续", "yes", "y", "ok")
        no_words = ("取消", "不要", "否", "不", "no", "n")
        if any(w in value for w in no_words):
            return False
        return any(w in value for w in yes_words)

    def _execute_purchase(self, products: list[dict]) -> dict:
        """Purchase all products marked as need_purchase into Baixin warehouse."""
        purchase_products = []
        for p in products:
            if not p.get("need_purchase"):
                continue
            plan = self._annotate_purchase_plan(p)
            purchase_products.append(self._purchase_payload_item(p, plan))
            p["warehouse_id"] = 2
            p.pop("need_purchase", None)

        if not purchase_products:
            return {"ok": True}

        try:
            result = self.caller.call(
                "other_enter_add",
                warehouse_id=2,
                products=purchase_products,
                note="送至百鑫",
            )
        except Exception as e:
            return {"error": str(e)}
        if isinstance(result, dict) and result.get("error"):
            return {"error": result["error"]}
        return {"ok": True, "result": result}

    def _purchase_payload_item(self, product: dict, plan: dict) -> dict:
        """ERP has no 件 unit, so 1件起 purchases are entered as equivalent 套."""
        unit_id = product.get("unit_id")
        buy_number = plan["purchase_qty"]
        if plan.get("purchase_unit") == "件" and plan.get("per_piece"):
            unit_id = self._lookup_unit_id("套") or product.get("unit_id")
            buy_number = int(plan["purchase_qty"]) * int(plan["per_piece"])
        return {
            "product_id": product["product_id"],
            "unit_id": unit_id,
            "buy_number": buy_number,
        }

    def _validate_before_sales(self, products: list[dict]) -> str | None:
        """Hard gate before SalesAdd. Return an error message when blocked."""
        for p in products:
            if not p.get("product_id"):
                return f"商品「{p.get('name', '')}」缺少 product_id，禁止开单。"
            if not p.get("unit_id"):
                return f"商品「{p.get('name', '')}」缺少 unit_id，禁止开单。"
            if p.get("unit") == "件":
                return f"商品「{p.get('name', '')}」仍是件单位，未完成件套换算，禁止开单。"
            if p.get("qty", 0) <= 0:
                return f"商品「{p.get('name', '')}」数量无效，禁止开单。"
            if p.get("price", 0) <= 0:
                return f"商品「{p.get('name', '')}」价格未确认，禁止开单。"
            if p.get("need_purchase"):
                return f"商品「{p.get('name', '')}」还未完成进货，禁止开单。"
            if p.get("pending_self_ship"):
                return f"商品「{p.get('name', '')}」使用自己店里库存但未确认，禁止开单。"
            if not p.get("warehouse_id"):
                return f"商品「{p.get('name', '')}」缺少发货仓库，禁止开单。"
        return None

    def _query_inventory(self, product_id: int) -> dict:
        """查库存，返回 {仓库名: 数量}"""
        try:
            results = self.caller.call("inventory_query_by_id", product_id=product_id)
            inventory = {}
            for inv in results:
                warehouse = inv.get("【仓库】", "")
                qty = inv.get("库存数量", 0)
                inventory[warehouse] = int(qty) if qty else 0
            return inventory
        except Exception as e:
            logger.warning(f"[OrderFlow] 库存查询失败: {e}")
            return {}

    def _create_order(self, customer_id: int, customer_name: str, products: list[dict], warehouse_id: int) -> dict:
        """B5: 开销售单"""
        blocked = self._validate_before_sales(products)
        if blocked:
            return self._reply(f"[BLOCKED: Missing Critical Info]\n{blocked}")

        # 构建商品列表
        api_products = []
        for p in products:
            pid = p.get("product_id")
            if not pid:
                continue
            api_products.append({
                "product_id": pid,
                "unit_id": p["unit_id"],
                "buy_number": p.get("qty", 1),
                "price": p.get("price", 0),
                "warehouse_id": p.get("warehouse_id", warehouse_id),
            })

        if not api_products:
            return self._reply("没有有效的商品信息，无法开单。")

        try:
            result = self.caller.call("sales_add",
                customer_id=customer_id,
                warehouse_id=warehouse_id,
                products=api_products,
            )

            # 解析结果
            data = result if isinstance(result, dict) else json.loads(json.dumps(result))
            if data.get("code") == 0:
                sales_no = data.get("data", "")
                from src.core.session import SessionManager, get_current_session_id
                if sales_no:
                    SessionManager(get_current_session_id()).set_meta("last_order", {
                        "type": "sales",
                        "id": str(sales_no),
                        "customer": customer_name,
                    })
                # 构建回复
                lines = [f"开单成功！销售单号：{sales_no}", ""]
                lines.append(f"客户：{customer_name}")
                lines.append("商品：")
                total = 0
                for p in products:
                    price = p.get("price", 0)
                    qty = p.get("qty", 1)
                    subtotal = price * qty
                    total += subtotal
                    wh = "自己店里" if p.get("warehouse_id", warehouse_id) == 1 else "百鑫仓库"
                    lines.append(f"  {p['name']}{(' ' + p['color']) if p.get('color') else ''}: {qty}{p.get('unit','套')} × {price}元 = {subtotal}元（{wh}发货）")
                lines.append(f"\n合计：{total}元")
                return self._reply("\n".join(lines))
            else:
                msg = data.get("msg", "未知错误")
                return self._reply(f"开单失败：{msg}")

        except Exception as e:
            logger.error(f"[OrderFlow] 开单异常: {e}")
            return self._reply(f"开单失败：{str(e)}")
