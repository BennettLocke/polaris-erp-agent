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
from src.core.customer_name import has_customer_name_craft_noise, normalize_customer_name
from src.core.product_matcher import ProductMatcher
from src.core.product_name import PRODUCT_SPECS, normalize_product_name
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
        self.product_matcher = ProductMatcher(self.caller, colors=self._colors())

    def execute(self, user_input: str, params: dict = None) -> dict:
        """
        B1: 提取参数（优先用 LLM 预提取的，否则 fallback）
        B2-B5: 固定流程执行
        """
        user_input = self._normalize_order_input(user_input)
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
        inline_products = self._extract_inline_products(user_input)
        if len(inline_products) > len(params.get("products", []) or []):
            params["products"] = inline_products
        params["products"] = self._enrich_order_products(params.get("products", []), user_input)
        customer_defaulted = bool(params.get("customer_defaulted")) or not bool(str(params.get("customer") or "").strip())
        customer_name = normalize_customer_name(params.get("customer") or "散客") or "散客"
        products = params.get("products", [])
        warehouse_hint = params.get("warehouse") or self._extract_warehouse_hint(user_input)
        skip_inventory = bool(params.get("skip_inventory")) or self._skip_inventory_check(user_input)
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
                        "customer_defaulted": customer_defaulted,
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
        if skip_inventory:
            warehouse_id = self._warehouse_id_from_hint(warehouse_hint)
            for p in resolved_products:
                p["warehouse_id"] = warehouse_id
            inventory_result = {"status": "ok", "warehouse_id": warehouse_id, "skip_inventory": True}
        else:
            inventory_result = self._inventory_decision(resolved_products, warehouse_hint)

        if inventory_result["status"] == "ask":
            # 需要问用户确认仓库/进货等关键动作
            state = {
                "customer_id": customer_id,
                "customer_name": customer_name,
                "customer_defaulted": customer_defaulted,
                "products": resolved_products,
                "warehouse_hint": warehouse_hint,
                "pending_action": inventory_result.get("pending_action", "choose_warehouse"),
                "pending_warehouse": inventory_result.get("pending_warehouse"),
            }
            return self._ask(inventory_result["question"], state)

        # ---- B5: 开单 ----
        logger.info("[OrderFlow] B5: 开单")
        warehouse_id = inventory_result.get("warehouse_id", 2)
        return self._confirm_create_order(
            customer_id,
            customer_name,
            resolved_products,
            warehouse_id,
            inventory_result["status"] == "auto_purchase",
            skip_inventory=inventory_result.get("skip_inventory", False),
            customer_defaulted=customer_defaulted,
        )

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

        if pending_action == "confirm_create_order":
            if any(word in user_input for word in ["修改", "改成", "改为", "换成"]):
                qty_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:张|套|件|个|份|盒)?", user_input)
                if qty_match and products:
                    qty = max(1, int(float(qty_match.group(1))))
                    products[0]["qty"] = qty
                    products[0]["quantity"] = qty
                    state["products"] = products
                return self._ask("已更新确认信息，请在确认弹窗里继续核对；确认后我再执行开单。", state)
            if not self._is_yes(user_input):
                if self._is_stop_order(user_input) or any(word in user_input for word in ["取消", "不要", "否", "不"]):
                    return self._reply("已取消本次开单，没有创建销售单。")
                return self._ask("还没有执行开单。请在确认弹窗核对后点确认，或回复「取消」停止。", state)
            if state.get("auto_purchase"):
                purchase_result = self._execute_purchase(products, int(state.get("warehouse_id") or 2))
                if purchase_result.get("error"):
                    return self._reply(f"进货失败：{purchase_result['error']}")
            elif not state.get("skip_inventory"):
                shortage = self._purchase_confirmation_for_shortage(customer_id, customer_name, products, int(state.get("warehouse_id") or 2))
                if shortage:
                    return shortage
            return self._create_order(
                customer_id,
                customer_name,
                products,
                state.get("warehouse_id", 2),
            )

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
                    return self._confirm_create_order(customer_id, customer_name, products, 2, auto_purchase=True)
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
                    return self._confirm_create_order(customer_id, customer_name, products, 2, auto_purchase=True)
                return self._ask(
                    "还有商品百鑫和自己店里都无货，需要先进货到百鑫仓库。请回复「确认」进货并继续开单，或回复「取消」停止。",
                    {
                        "customer_id": customer_id,
                        "customer_name": customer_name,
                        "products": products,
                        "pending_action": "confirm_purchase",
                    },
                )
            return self._confirm_create_order(customer_id, customer_name, products, 1)

        if pending_action == "confirm_purchase":
            if not self._is_yes(user_input):
                return self._reply("已取消进货，本次订单未开单。")
            warehouse_id = int(state.get("warehouse_id") or 2)
            purchase_result = self._execute_purchase(products, warehouse_id)
            if purchase_result.get("error"):
                return self._reply(f"进货失败：{purchase_result['error']}")
            if state.get("return_to_order"):
                warehouse_id = int((products[0] or {}).get("warehouse_id") or warehouse_id) if products else warehouse_id
                return self._create_order(customer_id, customer_name, products, warehouse_id)
            return self._reply("进货成功。")

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
                return self._confirm_create_order(customer_id, customer_name, products, 2, auto_purchase=True)
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
        return self._confirm_create_order(customer_id, customer_name, products, warehouse_id)

    # ---- 内部方法 ----

    def _normalize_order_input(self, text: str) -> str:
        value = str(text or "").strip()
        # Common speech/typing style: "开单测试客户 喜物..." should be read as
        # "开单 测试客户 喜物...", otherwise the first command can leak into
        # the customer/product boundary.
        value = re.sub(r"^(开单|下单|销售单|帮我开单|帮我下单)(?=\S)", r"\1 ", value)
        return re.sub(r"\s+", " ", value).strip()

    def _extract_inline_products(self, text: str) -> list[dict]:
        products = []
        value = self._normalize_order_input(text)
        for match in re.finditer(r"([^\s，,、]+?)\s*(\d+(?:\.\d+)?)\s*(套|张|件|个|盒|份)", value):
            raw_name = match.group(1).strip()
            if not raw_name or raw_name in {"开单", "下单", "销售单", "客户", "商品"}:
                continue
            colors = self._extract_colors_in_text(raw_name)
            qty = int(float(match.group(2)))
            unit = match.group(3)
            if "各" in raw_name and len(colors) >= 2:
                name = raw_name.replace("各", "")
                for color in colors:
                    name = name.replace(color, "")
                name = name.strip()
                for color in colors:
                    products.append({"name": name, "color": color, "qty": qty, "quantity": qty, "unit": unit})
                continue
            color = colors[0] if colors else ""
            name = raw_name.replace(color, "").strip() if color else raw_name
            products.append({"name": name, "color": color or "", "qty": qty, "quantity": qty, "unit": unit})
        return products

    def _extract_warehouse_hint(self, text: str) -> str | None:
        value = str(text or "")
        if any(word in value for word in ("自己店里", "自己仓", "店里仓", "门店", "店里", "自己")):
            return "自己店里"
        if any(word in value for word in ("百鑫仓库", "百鑫仓", "百鑫")):
            return "百鑫仓库"
        return None

    def _warehouse_id_from_hint(self, warehouse_hint: str | None) -> int:
        return 1 if warehouse_hint and ("自己" in warehouse_hint or "店里" in warehouse_hint) else 2

    def _skip_inventory_check(self, text: str) -> bool:
        value = str(text or "")
        return any(word in value for word in ("不用查库存", "不查库存", "免库存", "直接开单", "直接开"))

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
        return self._confirm_create_order(
            customer_id,
            customer_name,
            resolved_products,
            inventory_result.get("warehouse_id", 2),
            inventory_result["status"] == "auto_purchase",
        )

    def _search_customer(self, name: str) -> int | None:
        """B2: 搜索客户，返回 customer_id"""
        name = normalize_customer_name(name)
        if not name:
            return None
        try:
            results = self.caller.call("customer_query", keyword=name)
            exact_rows = []
            fuzzy_rows = []
            for row in results or []:
                row_name = str(row.get("name") or row.get("customer_name") or row.get("company_name") or "").strip()
                if row_name == name:
                    exact_rows.append(row)
                elif name in row_name and not has_customer_name_craft_noise(row_name):
                    fuzzy_rows.append(row)
            picked = exact_rows or (fuzzy_rows[:1] if len(fuzzy_rows) == 1 else [])
            if picked:
                cid = picked[0].get("id")
                logger.info(f"[OrderFlow] 客户找到: {name} → id={cid}, name={picked[0].get('name')}")
                return int(cid) if cid else None
            if results:
                logger.info(f"[OrderFlow] 客户模糊结果未采用: keyword={name}, rows={len(results)}")
        except Exception as e:
            logger.warning(f"[OrderFlow] 客户查询失败: {e}")
        return None

    def _create_customer(self, name: str) -> int | None:
        name = normalize_customer_name(name)
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
        color = self._normalize_color(product.get("color", ""))
        qty = product.get("qty") or product.get("quantity") or 1
        unit = product.get("unit", "套")
        price_override = self._parse_price(product.get("price") or product.get("unit_price"))

        keyword = self._normalize_product_name(name)
        match = self.product_matcher.match(
            keyword,
            color=color,
            use_inventory=True,
            allow_product_fallback=True,
            product_limit=100,
            inventory_limit=80,
            allow_llm=True,
        )
        results = match.candidates
        target = match.product
        logger.info(f"[OrderFlow] 商品匹配 '{keyword}', color={color} → {match.reason}, 候选={len(results)}")

        if target is None and color and self._is_non_gift(keyword):
            no_color_match = self.product_matcher.match(
                keyword,
                color="",
                use_inventory=True,
                allow_product_fallback=True,
                product_limit=100,
                inventory_limit=80,
                allow_llm=True,
            )
            if no_color_match.product is not None:
                target = no_color_match.product
                results = no_color_match.candidates
                color = ""
        if target is None:
            logger.warning(f"[OrderFlow] 商品未唯一确认: name={name}, color={color}, reason={match.reason}, results={len(results)}")
            return None

        product_id = target.get("id") or target.get("product_id")
        if product_id and ("产品名称" in target or not target.get("price")):
            detail = self._product_detail(product_id)
            if detail:
                target = {**target, **detail}
        if product_id:
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
        base_rows = target.get("base") if isinstance(target.get("base"), list) else []
        if base_rows:
            selected_base = None
            for base in base_rows:
                try:
                    if unit_id and int(base.get("unit_id") or 0) == int(unit_id):
                        selected_base = base
                        break
                except (TypeError, ValueError):
                    continue
            selected_base = selected_base or base_rows[0]
            base_unit_id = selected_base.get("unit_id")
            if base_unit_id:
                unit_id = base_unit_id
            unit = selected_base.get("unit_name") or unit
            if price_override is None and selected_base.get("price") not in (None, ""):
                price = selected_base.get("price")
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
            p["color"] = self._normalize_color(p.get("color", ""))
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
        return normalize_product_name(name, colors=self._colors(), specs=PRODUCT_SPECS)

    def _search_product_candidates(self, keyword: str, color: str = "") -> list[dict]:
        field_candidates = self._field_product_candidates(keyword, color)
        if field_candidates:
            return field_candidates

        for kw in self._product_keywords(keyword):
            candidates = []
            seen = set()
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
            if candidates:
                return candidates

        if not color:
            return []

        candidates = []
        seen = set()
        for kw in self._product_keywords(keyword):
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
            if candidates:
                return candidates
        return candidates

    def _field_product_candidates(self, keyword: str, color: str = "") -> list[dict]:
        terms = self._product_terms(keyword)
        if len(terms) < 2:
            return []

        brand = self._normalize_product_name(terms[0]).replace(" ", "")
        spec = self._normalize_product_name(terms[-1]).replace(" ", "")
        spec_aliases = [spec]

        title_expr = "REPLACE(REPLACE(REPLACE(title, '【', ''), '】', ''), ' ', '')"
        spec_filters = " OR ".join([f"{title_expr} LIKE %s" for _ in spec_aliases])
        sql = f"""
        SELECT id, title, spec, simple_desc, price
        FROM sxo_plugins_erp_product
        WHERE {title_expr} LIKE %s
          AND ({spec_filters})
        """
        params: list = [f"%{brand}%"] + [f"%{item}%" for item in spec_aliases]

        normalized_color = self._normalize_color(color)
        if normalized_color:
            sql += " AND (spec = %s OR spec LIKE %s)"
            params.extend([normalized_color, f"%{normalized_color}%"])
        sql += " ORDER BY id DESC LIMIT 30"

        try:
            rows = self.caller.call("db_query", sql=sql, params=tuple(params))
        except Exception as e:
            logger.warning(f"[OrderFlow] 字段商品匹配失败: {e}")
            return []
        rows = [row for row in rows or [] if isinstance(row, dict) and not row.get("error")]
        logger.info(f"[OrderFlow] 字段商品匹配: brand={brand}, spec={spec}, color={normalized_color}, 结果={len(rows)}条")
        return rows

    def _product_keywords(self, name: str) -> list[str]:
        specs = PRODUCT_SPECS
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
        specs = PRODUCT_SPECS
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
        match = self.product_matcher.match(keyword, color=color, use_inventory=True, allow_llm=False)
        if match.candidates:
            return match.candidates
        compact = keyword.replace(" ", "")
        for fallback in [compact[:2]]:
            if len(fallback) < 2 or fallback == keyword:
                continue
            match = self.product_matcher.match(fallback, color=color, use_inventory=True, allow_llm=False)
            if match.candidates:
                return match.candidates
        return []

    def _product_detail(self, product_id) -> dict | None:
        try:
            from src.engine.api_client import ERPSystemClient
            result = ERPSystemClient().product_detail(int(product_id))
            data = result.get("data") if isinstance(result, dict) else None
            if isinstance(data, dict) and isinstance(data.get("data"), dict):
                data = data["data"]
            if isinstance(data, dict) and data:
                return data
        except Exception as e:
            logger.warning(f"[OrderFlow] 商品API详情查询失败: {e}")
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


    def _normalize_color(self, color: str) -> str:
        value = str(color or "").strip()
        aliases = {
            "深咖色": "咖色",
            "深咖": "咖色",
            "咖啡色": "咖色",
            "棕咖色": "咖色",
        }
        return aliases.get(value, value)

    def _extract_color(self, text: str) -> str:
        for color in self._colors():
            if color in str(text or ""):
                return self._normalize_color(color)
        return ""

    def _extract_colors_in_text(self, text: str) -> list[str]:
        value = str(text or "")
        matches = [(value.find(color), color) for color in self._colors() if color in value]
        colors = [self._normalize_color(color) for _, color in sorted(matches, key=lambda item: item[0]) if _ >= 0]
        return list(dict.fromkeys(colors))

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
            normalized_color = self._normalize_color(color)
            color_matches = [
                r for r in candidates
                if normalized_color in str(r.get("spec", ""))
                or self._normalize_color(str(r.get("spec", ""))) == normalized_color
            ]
            if not color_matches:
                return None
            candidates = color_matches

        terms = self._product_terms(keyword)
        brand_terms = terms[:-1] if len(terms) > 1 else []
        if brand_terms:
            brand_matches = [
                r for r in candidates
                if self._candidate_has_terms(r, brand_terms)
            ]
            if not brand_matches:
                return None
            candidates = brand_matches

        term_matches = [
            r for r in candidates
            if self._candidate_has_terms(r, terms)
        ]
        if len(term_matches) == 1:
            return term_matches[0]
        if term_matches:
            candidates = term_matches
        elif len(terms) > 1:
            return None

        exact = [
            r for r in candidates
            if keyword and self._normalize_product_name(keyword).replace(" ", "") in self._candidate_title_text(r)
        ]
        if len(exact) == 1:
            return exact[0]
        if len(candidates) == 1:
            return candidates[0]
        return None

    def _candidate_title_text(self, row: dict) -> str:
        return self.product_matcher.candidate_title(row)

    def _candidate_has_terms(self, row: dict, terms: list[str]) -> bool:
        return self.product_matcher.candidate_has_terms(row, terms)

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
        except Exception as e:
            logger.warning(f"[OrderFlow] 历史价查询失败: {product.get('name', '')}: {e}")

        if product["price"] > 0:
            logger.info(f"[OrderFlow] 零售价: {product['name']} = {product['price']}")
            return

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
        # 如果用户已指定仓库，确认卡里预选该仓库，最终仍由用户确认。
        if warehouse_hint and warehouse_hint not in ("不指定", "未指定", "无", "null", ""):
            wid = 1 if "自己" in warehouse_hint or "店里" in warehouse_hint else 2
            for p in products:
                p["warehouse_id"] = wid
                p.pop("pending_self_ship", None)
                p.pop("pending_warehouse_choice", None)
            return {"status": "ok", "warehouse_id": wid}

        # 检查是否所有商品都是非礼盒类
        all_non_gift = all(self._is_non_gift(p["name"]) for p in products)
        logger.info(f"[OrderFlow] all_non_gift={all_non_gift}, products={[p['name'] for p in products]}")
        if all_non_gift:
            # 非礼盒类全部从百鑫发货
            for p in products:
                p["warehouse_id"] = 2
            return {"status": "ok", "warehouse_id": 2}

        # 有礼盒类商品 → 默认百鑫仓库，确认卡里可人工改为自己店里。
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
                p["warehouse_id"] = 2
            elif baixin_qty > 0:
                p["warehouse_id"] = 2
            elif self_qty > 0:
                p["warehouse_id"] = 2
                p["need_purchase"] = True
            else:
                # 都无货 → 需要进货
                p["warehouse_id"] = 2
                p["need_purchase"] = True

        need_purchase = [p for p in products if p.get("need_purchase")]
        if need_purchase:
            return {"status": "ok", "warehouse_id": 2}

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
        warehouse_id = need_purchase[0].get("warehouse_id", 2) if need_purchase else 2
        lines = [f"将先给{customer_name or '客户'}的订单进货到{self._warehouse_name(warehouse_id)}，再继续开销售单。请确认执行："]
        for p in need_purchase:
            lines.append(self._format_purchase_plan_line(p))
        lines.append("回复「确认」执行进货并开单，回复「取消」停止。")
        return "\n".join(lines)

    def _warehouse_name(self, warehouse_id: int) -> str:
        return "自己店里" if int(warehouse_id or 2) == 1 else "百鑫仓库"

    def _warehouse_stock(self, inventory: dict, warehouse_id: int) -> int:
        return int(inventory.get(self._warehouse_name(warehouse_id), 0) or 0)

    def _purchase_confirmation_for_shortage(
        self,
        customer_id: int,
        customer_name: str,
        products: list[dict],
        warehouse_id: int,
    ) -> dict | None:
        warehouse_id = int(warehouse_id or 2)
        shortage_products = []
        for p in products:
            product_warehouse_id = int(p.get("warehouse_id") or warehouse_id or 2)
            p["warehouse_id"] = product_warehouse_id
            if self._is_non_gift(p.get("name", "")):
                p.pop("need_purchase", None)
                p.pop("purchase_warehouse_id", None)
                p.pop("shortage_qty", None)
                continue
            inventory = self._query_inventory(p["product_id"])
            p["inventory"] = inventory
            selected_stock = self._warehouse_stock(inventory, product_warehouse_id)
            try:
                qty = int(float(p.get("qty") or 1))
            except (TypeError, ValueError):
                qty = 1
            if selected_stock < qty:
                p["need_purchase"] = True
                p["purchase_warehouse_id"] = int(p.get("purchase_warehouse_id") or product_warehouse_id)
                p["shortage_qty"] = max(1, qty - selected_stock)
                shortage_products.append(p)
            else:
                p.pop("need_purchase", None)
                p.pop("purchase_warehouse_id", None)
                p.pop("shortage_qty", None)

        if not shortage_products:
            return None

        lines = ["部分商品库存不足，需要先进货再开销售单。请确认进货信息："]
        for p in shortage_products:
            lines.append(self._format_purchase_plan_line(p))
        lines.append("确认后会先进货到所选仓库，再继续开销售单；取消则不执行。")
        return self._ask(
            "\n".join(lines),
            {
                "pending_action": "confirm_purchase",
                "customer_id": customer_id,
                "customer_name": customer_name,
                "products": products,
                "warehouse_id": warehouse_id,
                "purchase_warehouse_id": int(shortage_products[0].get("purchase_warehouse_id") or warehouse_id or 2),
                "return_to_order": True,
            },
        )

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
        shortage_qty = int(product.get("shortage_qty") or order_qty or 1)
        purchase_qty = plan["purchase_qty"]
        purchase_unit = plan["purchase_unit"]
        if purchase_unit == "件" and plan.get("per_piece"):
            return f"- {desc}：订单{order_qty}{order_unit}，缺口{shortage_qty}{order_unit}，进货{purchase_qty}件（{plan['per_piece']}套/件）"
        return f"- {desc}：订单{order_qty}{order_unit}，缺口{shortage_qty}{order_unit}，进货{purchase_qty}{purchase_unit}"

    def _annotate_purchase_plan(self, product: dict) -> dict:
        order_qty = int(product.get("qty") or 1)
        order_unit = product.get("unit") or "套"
        shortage_qty = int(product.get("shortage_qty") or order_qty or 1)
        per_piece = self._parse_sets_per_case(product.get("simple_desc", "")) or 0
        product_name = f"{product.get('name', '')} {product.get('title', '')}".strip()

        should_use_piece = order_unit == "套" and per_piece > 1 and is_one_piece_order(product_name)
        if should_use_piece:
            computed_purchase_qty = calculate_purchase_quantity(shortage_qty, per_piece, product_name)
            purchase_qty = computed_purchase_qty
            purchase_unit = "件"
        else:
            computed_purchase_qty = shortage_qty
            purchase_qty = shortage_qty
            purchase_unit = order_unit

        try:
            edited_purchase_qty = int(float(product.get("purchase_qty") or 0))
        except (TypeError, ValueError):
            edited_purchase_qty = 0
        if edited_purchase_qty > 0:
            if should_use_piece and per_piece > 1 and edited_purchase_qty > computed_purchase_qty and edited_purchase_qty >= shortage_qty:
                purchase_qty = calculate_purchase_quantity(edited_purchase_qty, per_piece, product_name)
            else:
                purchase_qty = edited_purchase_qty

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
        no_words = ("取消", "不要", "否", "不", "no", "n")
        if any(w in value for w in no_words):
            return False
        yes_words = ("确认", "同意", "可以", "是", "好", "好的", "继续", "执行", "创建", "开单", "yes", "y", "ok")
        return any(w in value for w in yes_words)

    def _execute_purchase(self, products: list[dict], warehouse_id: int = 2) -> dict:
        """Purchase all products marked as need_purchase into the selected warehouse."""
        warehouse_id = int(warehouse_id or 2)
        purchase_groups: dict[int, list[dict]] = {}
        for p in products:
            if not p.get("need_purchase"):
                continue
            target_warehouse_id = int(p.get("purchase_warehouse_id") or p.get("warehouse_id") or warehouse_id or 2)
            plan = self._annotate_purchase_plan(p)
            purchase_groups.setdefault(target_warehouse_id, []).append(self._purchase_payload_item(p, plan))
            p["warehouse_id"] = target_warehouse_id
            p["purchase_warehouse_id"] = target_warehouse_id
            p.pop("need_purchase", None)

        if not purchase_groups:
            return {"ok": True}

        try:
            results = []
            for target_warehouse_id, purchase_products in purchase_groups.items():
                result = self.caller.call(
                    "other_enter_add",
                    warehouse_id=target_warehouse_id,
                    products=purchase_products,
                    note=f"送至{self._warehouse_name(target_warehouse_id)}",
                )
                results.append(result)
                if isinstance(result, dict) and result.get("error"):
                    return {"error": result["error"]}
        except Exception as e:
            return {"error": str(e)}
        return {"ok": True, "result": results}

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

    def _confirm_create_order(
        self,
        customer_id: int,
        customer_name: str,
        products: list[dict],
        warehouse_id: int,
        auto_purchase: bool = False,
        skip_inventory: bool = False,
        customer_defaulted: bool = False,
    ) -> dict:
        """Always pause before mutating ERP state."""
        warehouse_id = int(warehouse_id or 2)
        for p in products:
            p["warehouse_id"] = int(p.get("warehouse_id") or warehouse_id or 2)
        lines = ["请确认是否执行开单：", f"客户：{customer_name}"]
        if customer_defaulted:
            lines.append("提醒：这次没有识别到客户，已默认按散客处理；确认前可以改客户。")
        lines.append("动作：先进货入库，再创建销售单" if auto_purchase else "动作：创建销售单")
        lines.append("商品：")
        for p in products:
            wh = "自己店里" if int(p.get("warehouse_id") or warehouse_id or 2) == 1 else "百鑫仓库"
            color = f" {p.get('color')}" if p.get("color") else ""
            price = p.get("price", 0)
            lines.append(f"- {p.get('name', p.get('title', '商品'))}{color} {p.get('qty', 1)}{p.get('unit', '套')}，{wh}，单价 {price}")
        lines.append("确认后才会真正写入进销存。")
        return self._ask(
            "\n".join(lines),
            {
                "pending_action": "confirm_create_order",
                "customer_id": customer_id,
                "customer_name": customer_name,
                "products": products,
                "warehouse_id": warehouse_id,
                "auto_purchase": auto_purchase,
                "skip_inventory": skip_inventory,
                "customer_defaulted": customer_defaulted,
            },
        )

    def _create_order(self, customer_id: int, customer_name: str, products: list[dict], warehouse_id: int) -> dict:
        """B5: 开销售单"""
        warehouse_id = int(warehouse_id or 2)
        for p in products:
            p["warehouse_id"] = int(p.get("warehouse_id") or warehouse_id or 2)
            detail = self._product_detail(p.get("product_id")) if p.get("product_id") else None
            base_rows = detail.get("base") if isinstance(detail, dict) and isinstance(detail.get("base"), list) else []
            if not base_rows:
                continue
            current_unit_id = p.get("unit_id")
            selected_base = None
            for base in base_rows:
                try:
                    if current_unit_id and int(base.get("unit_id") or 0) == int(current_unit_id):
                        selected_base = base
                        break
                except (TypeError, ValueError):
                    continue
            selected_base = selected_base or base_rows[0]
            if selected_base.get("unit_id"):
                p["unit_id"] = int(selected_base["unit_id"])
            if selected_base.get("unit_name"):
                p["unit"] = selected_base["unit_name"]
            if not p.get("price") and selected_base.get("price") not in (None, ""):
                p["price"] = float(selected_base["price"])
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
                # 构建回复
                lines = [f"开单成功！销售单号：{sales_no}", ""]
                lines.append(f"客户：{customer_name}")
                lines.append("商品：")
                total = 0
                order_items = []
                for p in products:
                    price = p.get("price", 0)
                    qty = p.get("qty", 1)
                    subtotal = price * qty
                    total += subtotal
                    wh = "自己店里" if p.get("warehouse_id", warehouse_id) == 1 else "百鑫仓库"
                    order_items.append({
                        "name": p.get("name", ""),
                        "color": p.get("color", ""),
                        "qty": qty,
                        "unit": p.get("unit", "套"),
                        "price": price,
                        "subtotal": subtotal,
                        "warehouse": wh,
                    })
                    lines.append(f"  {p['name']}{(' ' + p['color']) if p.get('color') else ''}: {qty}{p.get('unit','套')} × {price}元 = {subtotal}元（{wh}发货）")
                lines.append(f"\n合计：{total}元")
                from src.core.session import SessionManager, get_current_session_id
                if sales_no:
                    SessionManager(get_current_session_id()).set_meta("last_order", {
                        "type": "sales",
                        "id": str(sales_no),
                        "customer": customer_name,
                        "products": order_items,
                        "total": total,
                    })
                return self._reply("\n".join(lines))
            else:
                msg = data.get("msg") or data.get("error") or "未知错误"
                return self._reply(f"开单失败：{msg}")

        except Exception as e:
            logger.error(f"[OrderFlow] 开单异常: {e}")
            return self._reply(f"开单失败：{str(e)}")
