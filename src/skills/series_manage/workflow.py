"""1件起订/非1件起订系列规则管理。"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from src.core.config import get_config
from src.skills.base import BaseWorkflow
from src.utils import get_logger

logger = get_logger("sjagent.skills.series_manage")


ONE_PATH = ("business_rules", "unit_conversion", "one_piece_series")
NON_ONE_PATH = ("business_rules", "unit_conversion", "non_one_piece_series")


class SeriesManageWorkflow(BaseWorkflow):
    """管理礼盒系列的进货换算规则。"""

    def execute(self, user_input: str, params: dict = None) -> dict:
        params = params or {}
        action = params.get("action") or self._detect_action(user_input)
        series = params.get("series") or self._extract_series(user_input)

        if action == "query":
            return self._reply(self._format_current_rules())

        if not series:
            return self._ask(
                "请告诉我要调整哪个系列，例如：把青云加到1件起系列，或把星禾设为非1件起。",
                {"pending_action": "collect_series_rule", "series_partial": {"action": action}},
            )

        state = {"pending_action": "confirm_series_rule", "action": action, "series": series}
        return self._ask(self._format_confirm_question(action, series), state)

    def resume(self, user_input: str, state: dict) -> dict:
        action = state.get("pending_action")
        if action == "collect_series_rule":
            partial = state.get("series_partial", {})
            series = self._extract_series(user_input)
            rule_action = partial.get("action") or self._detect_action(user_input)
            if not series:
                return self._ask("请直接回复系列名，例如：青云。", state)
            return self.execute(user_input, {"action": rule_action, "series": series})

        if action == "confirm_series_rule":
            if not self._is_confirmation(user_input):
                return self._reply("已取消规则修改。")
            try:
                return self._reply(self._apply_rule(state.get("action"), state.get("series") or []))
            except Exception as e:
                logger.error(f"系列规则修改失败: {e}")
                return self._reply(f"规则修改失败：{str(e)}")

        return self._reply("规则管理状态已失效，请重新发起。")

    def _detect_action(self, text: str) -> str:
        value = text or ""
        if any(w in value for w in ["查看", "看看", "列出", "查询", "有哪些"]):
            return "query"
        non_one_words = ["非1件起", "非一件起", "不是1件起", "不是一件起", "不用1件起", "不用一件起"]
        remove_words = ["取消", "移出", "去掉", "删除", "删掉", "不算"]
        if any(w in value for w in non_one_words):
            if any(w in value for w in remove_words) and "非" in value:
                return "remove_non_one_piece"
            return "set_non_one_piece"
        if any(w in value for w in remove_words) and any(w in value for w in ["1件起", "一件起", "件起订", "按件"]):
            return "set_non_one_piece"
        return "set_one_piece"

    def _extract_series(self, text: str) -> list[str]:
        value = str(text or "")
        cleanup_words = [
            "以后", "以后和他说", "记住", "规则", "系列", "礼盒", "把", "将", "给",
            "查看", "看看", "列出", "查询", "有哪些",
            "加入到", "加到", "加进", "加入", "添加", "新增", "加", "设为", "设置为",
            "设置成", "改成", "变成", "归为", "算作", "作为", "取消", "移出", "去掉",
            "删除", "删掉", "不算", "不是", "不用", "非1件起", "非一件起", "1件起订",
            "一件起订", "1件起", "一件起", "件起订", "按件", "的",
        ]
        for word in cleanup_words:
            value = value.replace(word, " ")
        value = re.sub(r"[，,、/;；\n]+", " ", value)
        parts = [p.strip() for p in value.split() if p.strip()]
        stop_words = {"为", "到", "成", "和", "或", "与", "非", "起", "订"}
        series = []
        for part in parts:
            if part in stop_words:
                continue
            part = re.sub(r"^[：:]+|[：:]+$", "", part)
            if not part or re.search(r"\d", part):
                continue
            if part not in series:
                series.append(part)
        return series

    def _format_confirm_question(self, action: str, series: list[str]) -> str:
        names = "、".join(series)
        if action == "set_one_piece":
            return f"确认把「{names}」加入1件起订系列吗？确认后会从非1件起订系列里移除。"
        if action == "remove_non_one_piece":
            return f"确认把「{names}」从非1件起订系列里移除吗？"
        return f"确认把「{names}」设为非1件起订系列吗？确认后会从1件起订系列里移除。"

    def _apply_rule(self, action: str, series: list[str]) -> str:
        data = self._load_config()
        one_piece = self._get_list(data, ONE_PATH)
        non_one = self._get_list(data, NON_ONE_PATH)

        if action == "set_one_piece":
            for name in series:
                one_piece = self._append_unique(one_piece, name)
                non_one = [item for item in non_one if item != name]
            change = f"已加入1件起订系列：{'、'.join(series)}。"
        elif action == "remove_non_one_piece":
            for name in series:
                non_one = [item for item in non_one if item != name]
            change = f"已从非1件起订系列移除：{'、'.join(series)}。"
        else:
            for name in series:
                non_one = self._append_unique(non_one, name)
                one_piece = [item for item in one_piece if item != name]
            change = f"已设为非1件起订系列：{'、'.join(series)}。"

        self._set_list(data, ONE_PATH, one_piece)
        self._set_list(data, NON_ONE_PATH, non_one)
        self._save_lists_preserving_comments(one_piece, non_one)
        get_config().reload()

        return f"{change}\n当前1件起订：{'、'.join(one_piece) or '无'}\n当前非1件起订：{'、'.join(non_one) or '无'}"

    def _format_current_rules(self) -> str:
        data = self._load_config()
        one_piece = self._get_list(data, ONE_PATH)
        non_one = self._get_list(data, NON_ONE_PATH)
        return f"当前1件起订：{'、'.join(one_piece) or '无'}\n当前非1件起订：{'、'.join(non_one) or '无'}"

    def _load_config(self) -> dict:
        with open(self._config_path(), encoding="utf-8") as f:
            return yaml.safe_load(f)

    def _config_path(self) -> Path:
        return Path(__file__).resolve().parents[3] / "config.yaml"

    def _get_list(self, data: dict, path: tuple[str, ...]) -> list[str]:
        current = data
        for key in path:
            current = current.setdefault(key, {})
        return list(current or [])

    def _set_list(self, data: dict, path: tuple[str, ...], value: list[str]) -> None:
        current = data
        for key in path[:-1]:
            current = current.setdefault(key, {})
        current[path[-1]] = value

    def _append_unique(self, values: list[str], name: str) -> list[str]:
        return values if name in values else values + [name]

    def _save_lists_preserving_comments(self, one_piece: list[str], non_one: list[str]) -> None:
        path = self._config_path()
        text = path.read_text(encoding="utf-8")
        text = self._replace_yaml_list(text, "one_piece_series", one_piece)
        text = self._replace_yaml_list(text, "non_one_piece_series", non_one)
        path.write_text(text, encoding="utf-8")

    def _replace_yaml_list(self, text: str, key: str, values: list[str]) -> str:
        pattern = rf"(?m)^(\s{{4}}{re.escape(key)}:\n)(?:\s{{6}}- .*\n)*"
        replacement = rf"\1" + "".join(f"      - {value}\n" for value in values)
        new_text, count = re.subn(pattern, replacement, text, count=1)
        if count != 1:
            raise ValueError(f"没有找到配置项 {key}")
        return new_text

    def _is_confirmation(self, text: str) -> bool:
        value = str(text or "").strip().lower()
        if len(value) > 8:
            return False
        return any(w in value for w in ["确认", "是", "对", "好的", "可以", "执行", "ok", "yes", "y"])
