"""泡袋新品上传流程。

当前只实现前置测试阶段：收集模板、商品名、图片，并按 ERP 的 SJ 自动编号规则生成预览，
不真正创建/上传商品。
"""
from __future__ import annotations

import re
from pathlib import Path

from src.skills.base import BaseWorkflow
from src.utils import get_logger

logger = get_logger("sjagent.skills.bag_upload")


BAG_TYPES = {
    "岩茶": {"suffix": "长泡袋", "template": "岩茶泡袋模板"},
    "红茶": {"suffix": "短泡袋", "template": "红茶泡袋模板"},
    "宽版": {"suffix": "宽版泡袋", "template": "宽版泡袋模板"},
}

BAG_CATEGORIES = [
    ("肉桂", 7, "肉桂泡袋"),
    ("水仙", 6, "水仙泡袋"),
    ("大红袍", 5, "大红袍泡袋"),
    ("金骏眉", 12, "红茶泡袋"),
    ("小种", 12, "红茶泡袋"),
    ("红茶", 12, "红茶泡袋"),
]


class BagUploadWorkflow(BaseWorkflow):
    """上传泡袋新品的分步流程。"""

    def execute(self, user_input: str, params: dict = None) -> dict:
        params = params or {}
        bag_type = self._normalize_bag_type(params.get("bag_type") or user_input)
        if bag_type:
            return self._ask_name(bag_type)
        return self._ask(
            "开始上传泡袋。这个泡袋是岩茶、红茶，还是宽版？",
            {"pending_action": "collect_bag_type"},
        )

    def resume(self, user_input: str, state: dict) -> dict:
        action = state.get("pending_action")

        if action == "collect_bag_type":
            bag_type = self._normalize_bag_type(user_input)
            if not bag_type:
                return self._ask(
                    "我需要先确定模板：这个泡袋是岩茶、红茶，还是宽版？",
                    {"pending_action": "collect_bag_type"},
                )
            return self._ask_name(bag_type)

        if action == "collect_bag_name":
            name = self._clean_product_name(user_input)
            if not name:
                return self._ask(
                    "这个新品泡袋叫什么名字？例如：虎啸岩肉桂。",
                    state,
                )
            next_state = {**state, "product_name": name}
            category = self._classify_category(name, state.get("bag_type"))
            if not category:
                next_state["pending_action"] = "collect_bag_category"
                return self._ask(
                    f"“{name}”我还不能确定分类，请告诉我是肉桂泡袋、水仙泡袋、大红袍泡袋、红茶泡袋，还是宽版泡袋？",
                    next_state,
                )
            next_state.update(category)
            return self._ask_image(next_state)

        if action == "collect_bag_category":
            category = self._category_from_text(user_input)
            if not category:
                return self._ask(
                    "分类还没识别到，请直接说：肉桂泡袋、水仙泡袋、大红袍泡袋、红茶泡袋，或宽版泡袋。",
                    state,
                )
            next_state = {**state, **category}
            return self._ask_image(next_state)

        if action == "collect_bag_image":
            image = self._extract_image_path(user_input)
            if not image:
                return self._ask(
                    "请把泡袋 PNG 图片发给我。当前先做本地流程测试，不会上传商品。",
                    state,
                )
            draft = self._build_draft({**state, "image_path": image})
            return self._ask(
                self._draft_text(draft),
                {**draft, "pending_action": "confirm_bag_product_draft"},
            )

        if action == "confirm_bag_product_draft":
            if self._is_confirm(user_input):
                return self._reply(self._test_done_text(state))
            if self._is_cancel(user_input):
                return self._reply("已取消泡袋新品上传流程。")
            return self._ask(
                "现在还是测试模式。确认这个泡袋新品资料没问题吗？回复“确认”结束前置测试，回复“取消”放弃。",
                state,
            )

        return self._reply("泡袋上传流程状态已失效，请重新说“开始上传泡袋”。")

    def _ask_name(self, bag_type: str) -> dict:
        return self._ask(
            f"已选择{bag_type}模板。这个新品泡袋叫什么名字？",
            {"pending_action": "collect_bag_name", "bag_type": bag_type},
        )

    def _ask_image(self, state: dict) -> dict:
        name = state.get("product_name") or ""
        category = state.get("category_name") or ""
        return self._ask(
            f"已识别：{name}，分类：{category}。请上传这个泡袋的 PNG 图片。",
            {**state, "pending_action": "collect_bag_image"},
        )

    def _build_draft(self, state: dict) -> dict:
        bag_type = state.get("bag_type") or "岩茶"
        meta = BAG_TYPES.get(bag_type, BAG_TYPES["岩茶"])
        name = state.get("product_name") or ""
        code = self._next_sj_code()
        title = f"【{code}】{name}-{meta['suffix']}"
        return {
            **state,
            "coding_preview": code,
            "title": title,
            "template_name": meta["template"],
            "suffix": meta["suffix"],
            "upload_enabled": False,
        }

    def _draft_text(self, draft: dict) -> str:
        image_name = Path(draft.get("image_path") or "").name or "已收到图片"
        return (
            "泡袋新品前置资料已收齐，当前是本地测试模式，暂不上传产品。\n\n"
            f"模板：{draft.get('template_name')}\n"
            f"商品名：{draft.get('product_name')}\n"
            f"分类：{draft.get('category_name')}（ID {draft.get('category_id')}）\n"
            f"预计编号：{draft.get('coding_preview')}（正式创建时仍由 ERP 自动生成）\n"
            f"预计标题：{draft.get('title')}\n"
            f"图片：{image_name}\n\n"
            "确认后本轮只结束前置测试，不会写入 ERP。"
        )

    def _test_done_text(self, state: dict) -> str:
        return (
            "泡袋新品前置流程测试完成。\n"
            f"商品：{state.get('title') or state.get('product_name')}\n"
            f"分类：{state.get('category_name')}\n"
            f"编号预览：{state.get('coding_preview')}\n"
            "目前没有上传产品；下一步可以接生成主图/详情图和 ERP 新建商品。"
        )

    def _normalize_bag_type(self, text: str) -> str:
        text = str(text or "")
        if "宽版" in text or "宽泡袋" in text:
            return "宽版"
        if "红茶" in text or "金骏眉" in text or "小种" in text:
            return "红茶"
        if "岩茶" in text or "肉桂" in text or "水仙" in text or "大红袍" in text:
            return "岩茶"
        return ""

    def _clean_product_name(self, text: str) -> str:
        cleaned = str(text or "").strip()
        for word in ["商品名", "名字", "名称", "叫", "是", "泡袋", "新品"]:
            cleaned = cleaned.replace(word, " ")
        cleaned = re.sub(r"\s+", "", cleaned)
        cleaned = re.sub(r"^[：:，,。.\s]+|[：:，,。.\s]+$", "", cleaned)
        return cleaned[:80]

    def _classify_category(self, name: str, bag_type: str = "") -> dict | None:
        if bag_type == "宽版":
            return {"category_id": 21, "category_name": "宽版泡袋"}
        for key, cid, cname in BAG_CATEGORIES:
            if key in name:
                return {"category_id": cid, "category_name": cname}
        if bag_type == "红茶":
            return {"category_id": 12, "category_name": "红茶泡袋"}
        return None

    def _category_from_text(self, text: str) -> dict | None:
        text = str(text or "")
        mapping = {
            "肉桂": (7, "肉桂泡袋"),
            "水仙": (6, "水仙泡袋"),
            "大红袍": (5, "大红袍泡袋"),
            "红茶": (12, "红茶泡袋"),
            "宽版": (21, "宽版泡袋"),
        }
        for key, (cid, cname) in mapping.items():
            if key in text:
                return {"category_id": cid, "category_name": cname}
        return None

    def _extract_image_path(self, text: str) -> str:
        text = str(text or "").strip()
        match = re.search(r"(?:图片|image|path)[:：]?\s*(.+)$", text, re.I)
        if match:
            text = match.group(1).strip()
        for part in re.split(r"\s+", text):
            if re.search(r"\.(png|jpg|jpeg|webp|bmp)$", part, re.I) or part.startswith("/api/images/file/"):
                return part
        return text if Path(text).suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".bmp"} else ""

    def _next_sj_code(self) -> str:
        try:
            from src.engine.db_client import get_db_client

            db = get_db_client()
            number = 506
            while number < 99999:
                code = f"SJ{number:04d}"
                exists = 0
                for table in ("sxo_plugins_erp_product", "sxo_plugins_erp_product_base", "sxo_goods_spec_base"):
                    rows = db.query(f"SELECT COUNT(*) AS c FROM `{table}` WHERE coding=%s", (code,))
                    exists += int((rows[0] if rows else {}).get("c") or 0)
                if not exists:
                    return code
                number += 1
        except Exception as e:
            logger.warning(f"获取 SJ 编号预览失败，使用占位编号: {e}")
        return "SJ_AUTO"

    def _is_confirm(self, text: str) -> bool:
        return str(text or "").strip() in {"确认", "确定", "可以", "继续", "好", "没问题", "是"}

    def _is_cancel(self, text: str) -> bool:
        return any(word in str(text or "") for word in ["取消", "算了", "不要", "不用"])
