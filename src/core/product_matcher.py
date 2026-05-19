"""Central product matching for ERP product operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.core.colors import extract_color_from_text, known_colors, normalize_color
from src.core.product_name import PRODUCT_SPECS, normalize_product_name, product_keywords, product_terms
from src.utils import get_logger

logger = get_logger("sjagent.product_matcher")


DEFAULT_COLORS = known_colors()


@dataclass
class ProductMatch:
    product: dict | None = None
    candidates: list[dict] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    reason: str = ""

    @property
    def is_unique(self) -> bool:
        return self.product is not None


class ProductMatcher:
    """Find one safe ERP product match, or return candidates for confirmation."""

    def __init__(self, caller, colors: list[str] | None = None):
        self.caller = caller
        self.colors = list(dict.fromkeys([*(colors or []), *DEFAULT_COLORS]))

    def match(
        self,
        name: str,
        *,
        color: str = "",
        warehouse_name: str = "",
        min_stock: int | None = None,
        use_inventory: bool = True,
        product_limit: int = 100,
        inventory_limit: int = 100,
        allow_product_fallback: bool = True,
        allow_llm: bool = True,
    ) -> ProductMatch:
        detected_color = color or self.extract_color(name)
        normalized_name = self.normalize_name(name)
        normalized_color = self.normalize_color(detected_color)
        keywords = self.keywords(normalized_name)
        terms = self.terms(normalized_name)
        if not normalized_name:
            return ProductMatch(keywords=keywords, reason="empty_name")

        rows = self._collect_candidates(
            keywords,
            color=normalized_color,
            use_inventory=use_inventory,
            allow_product_fallback=allow_product_fallback,
            product_limit=product_limit,
            inventory_limit=inventory_limit,
        )
        candidates = self._rank_candidates(
            rows,
            terms=terms,
            query=normalized_name,
            color=normalized_color,
            warehouse_name=warehouse_name,
            min_stock=min_stock,
        )
        logger.info(
            f"商品匹配: name={name} normalized={normalized_name} color={normalized_color} "
            f"warehouse={warehouse_name} min_stock={min_stock} rows={len(rows)} candidates={len(candidates)}"
        )

        if len(candidates) == 1:
            return ProductMatch(product=candidates[0], candidates=candidates, keywords=keywords, reason="unique")

        exact = self._exact_candidates(candidates, normalized_name, terms)
        if len(exact) == 1:
            return ProductMatch(product=exact[0], candidates=candidates, keywords=keywords, reason="exact")

        if allow_llm and len(terms) >= 2 and 1 < len(candidates) <= 8:
            picked = self._llm_pick_candidate(normalized_name, normalized_color, candidates)
            if picked:
                return ProductMatch(product=picked, candidates=candidates, keywords=keywords, reason="llm_pick")

        return ProductMatch(product=None, candidates=candidates, keywords=keywords, reason="ambiguous" if candidates else "not_found")

    def normalize_name(self, name: str) -> str:
        return normalize_product_name(name, colors=self.colors, specs=PRODUCT_SPECS)

    def normalize_color(self, color: str) -> str:
        return normalize_color(color)

    def extract_color(self, text: str) -> str:
        return extract_color_from_text(text)

    def keywords(self, name: str) -> list[str]:
        return product_keywords(name, specs=PRODUCT_SPECS)

    def terms(self, name: str) -> list[str]:
        return product_terms(name, specs=PRODUCT_SPECS)

    def candidate_title(self, row: dict) -> str:
        title = str(row.get("title") or row.get("产品名称") or "")
        return self.normalize_name(title).replace(" ", "")

    def candidate_has_terms(self, row: dict, terms: list[str]) -> bool:
        title = self.candidate_title(row)
        compact_terms = [self.normalize_name(term).replace(" ", "") for term in terms if str(term).strip()]
        return all(term in title for term in compact_terms)

    def _collect_candidates(
        self,
        keywords: list[str],
        *,
        color: str,
        use_inventory: bool,
        allow_product_fallback: bool,
        product_limit: int,
        inventory_limit: int,
    ) -> list[dict]:
        rows: list[dict] = []
        seen = set()

        def add(row: dict, source: str):
            normalized = self._normalize_candidate(row, source)
            product_id = normalized.get("id") or normalized.get("product_id")
            key = (
                product_id,
                normalized.get("spec") or normalized.get("【颜色】"),
                normalized.get("【仓库】") if source == "inventory" else "",
                source,
            )
            if not product_id or key in seen:
                return
            seen.add(key)
            rows.append(normalized)

        for keyword in keywords:
            if allow_product_fallback:
                try:
                    product_rows = self.caller.call("product_search", keyword=keyword) or []
                except Exception as e:
                    logger.warning(f"商品搜索失败: keyword={keyword} error={e}")
                    product_rows = []
                for row in product_rows[:product_limit]:
                    if isinstance(row, dict):
                        add(row, "product")

            if use_inventory:
                try:
                    inventory_rows = self.caller.call(
                        "inventory_search",
                        keyword=keyword,
                        color=color,
                        only_in_stock=False,
                        limit=inventory_limit,
                    ) or []
                except Exception as e:
                    logger.warning(f"库存反查商品失败: keyword={keyword} error={e}")
                    inventory_rows = []
                for row in inventory_rows:
                    if isinstance(row, dict):
                        add(row, "inventory")

        return rows

    def _normalize_candidate(self, row: dict, source: str) -> dict:
        product_id = row.get("id") or row.get("product_id")
        title = row.get("title") or row.get("产品名称") or row.get("name") or ""
        spec = row.get("spec") or row.get("【颜色】") or row.get("color") or ""
        candidate = dict(row)
        candidate.update(
            {
                "id": product_id,
                "product_id": product_id,
                "title": title,
                "产品名称": title,
                "spec": spec,
                "【颜色】": spec,
                "simple_desc": row.get("simple_desc") or "",
                "price": row.get("price") or 0,
                "_match_source": source,
            }
        )
        return candidate

    def _rank_candidates(
        self,
        rows: list[dict],
        *,
        terms: list[str],
        query: str,
        color: str,
        warehouse_name: str,
        min_stock: int | None,
    ) -> list[dict]:
        ranked: list[dict] = []
        for row in rows:
            score = self._score_candidate(
                row,
                terms=terms,
                query=query,
                color=color,
                warehouse_name=warehouse_name,
                min_stock=min_stock,
            )
            if score is None:
                continue
            key = (row.get("id"), row.get("spec") or row.get("【颜色】"))
            if min_stock is not None:
                key = (*key, row.get("【仓库】") or "")
            previous_index = next((idx for idx, item in enumerate(ranked) if item.get("_match_key") == key), None)
            candidate = dict(row)
            candidate["_match_score"] = score
            candidate["_match_key"] = key
            if previous_index is None:
                ranked.append(candidate)
            elif score > ranked[previous_index].get("_match_score", 0):
                ranked[previous_index] = candidate

        ranked.sort(key=lambda item: item.get("_match_score", 0), reverse=True)
        for item in ranked:
            item.pop("_match_key", None)
        return ranked

    def _score_candidate(
        self,
        row: dict,
        *,
        terms: list[str],
        query: str,
        color: str,
        warehouse_name: str,
        min_stock: int | None,
    ) -> int | None:
        title = self.candidate_title(row)
        compact_terms = [self.normalize_name(term).replace(" ", "") for term in terms if str(term).strip()]
        if compact_terms and not all(term in title for term in compact_terms):
            return None

        spec = self.normalize_color(str(row.get("spec") or row.get("【颜色】") or ""))
        if color:
            if color not in spec and spec not in color:
                return None

        warehouse = str(row.get("【仓库】") or row.get("warehouse") or "")
        if warehouse_name and warehouse and warehouse_name not in warehouse:
            return None

        if min_stock is not None:
            if not warehouse:
                return None
            try:
                stock = int(row.get("库存数量", 0) or 0)
            except (TypeError, ValueError):
                return None
            if stock < min_stock:
                return None
        else:
            stock = row.get("库存数量", "")

        query_compact = self.normalize_name(query).replace(" ", "")
        score = 0
        if query_compact and query_compact in title:
            score += 40
        score += len(compact_terms) * 30
        if color:
            score += 25
        if warehouse_name and warehouse:
            score += 15
        if row.get("_match_source") == "inventory":
            score += 5
        if stock not in ("", None):
            score += 1
        return score

    def _exact_candidates(self, candidates: list[dict], query: str, terms: list[str]) -> list[dict]:
        query_compact = self.normalize_name(query).replace(" ", "")
        if not query_compact:
            return []
        exact = [row for row in candidates if query_compact == self.candidate_title(row)]
        if exact:
            return exact
        if len(terms) >= 2:
            return [row for row in candidates if self.candidate_has_terms(row, terms)]
        return []

    def _llm_pick_candidate(self, name: str, color: str, candidates: list[dict]) -> dict | None:
        try:
            from src.core.llm import llm_json

            rows = [
                {
                    "product_id": row.get("id"),
                    "title": row.get("title"),
                    "spec": row.get("spec"),
                    "warehouse": row.get("【仓库】", ""),
                }
                for row in candidates
            ]
            result = llm_json(
                """你是 ERP 商品候选判断器，只能从候选列表里选择。
返回 JSON：{"product_id": 数字或null, "confidence": 0到1, "reason": "简短原因"}
规则：
- 用户商品名的品牌和规格必须都能对应候选商品。
- 颜色不一致不能选。
- 如果缺少规格、候选仍然歧义、或需要猜测，product_id 返回 null。
- 禁止编造商品，只能返回候选里的 product_id。""",
                f"用户商品：{name}\n颜色：{color}\n候选：{rows}",
            )
        except Exception as e:
            logger.warning(f"LLM 商品候选判断失败: {e}")
            return None

        try:
            product_id = int(result.get("product_id") or 0)
            confidence = float(result.get("confidence") or 0)
        except (TypeError, ValueError):
            return None
        if not product_id or confidence < 0.78:
            return None
        matches = [row for row in candidates if int(row.get("id") or 0) == product_id]
        return matches[0] if len(matches) == 1 else None
