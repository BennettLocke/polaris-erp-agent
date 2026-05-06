"""会话状态管理 - 支持历史记录 + skill 暂停/恢复"""
import json
from pathlib import Path
from src.utils import get_logger

logger = get_logger("sjagent.session")

HISTORY_DIR = Path(__file__).parent.parent.parent / "data" / "sessions"
CURRENT_SESSION_ID = "default"


def set_current_session_id(session_id: str):
    """记录当前请求的 session_id，供 workflow 写入结构化元数据。"""
    global CURRENT_SESSION_ID
    CURRENT_SESSION_ID = session_id or "default"


def get_current_session_id() -> str:
    """获取当前请求 session_id。"""
    return CURRENT_SESSION_ID


class SessionManager:
    """
    会话管理器。

    数据结构：
    {
        "history": [{"role": "user/assistant", "content": "..."}],
        "pending": {
            "intent": "order",
            "state": {...}  # skill 暂停时保存的状态
        }
    }
    """

    def __init__(self, session_id: str = "default"):
        self.session_id = session_id
        HISTORY_DIR.mkdir(parents=True, exist_ok=True)
        self.file = HISTORY_DIR / f"{session_id}.json"
        self.data = self._load()

    def _load(self) -> dict:
        if self.file.exists():
            try:
                with open(self.file, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                # 兼容旧格式（纯 list）
                if isinstance(raw, list):
                    return {"history": raw, "pending": None}
                return raw
            except Exception:
                pass
        return {"history": [], "pending": None, "meta": {}}

    def _save(self):
        try:
            with open(self.file, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"保存会话失败: {e}")

    # ---- 历史记录 ----

    def get_history(self, max_turns: int = 10) -> list[dict]:
        """获取历史对话"""
        return self.data["history"][-(max_turns * 2):]

    def save_turn(self, user_input: str, assistant_reply: str):
        """保存一轮对话"""
        self.data["history"].append({"role": "user", "content": user_input})
        self.data["history"].append({"role": "assistant", "content": assistant_reply})
        # 裁剪
        if len(self.data["history"]) > 20 * 2:
            self.data["history"] = self.data["history"][-(20 * 2):]
        self._save()

    # ---- Skill 暂停/恢复 ----

    def has_pending(self) -> bool:
        """是否有未完成的 skill"""
        return self.data.get("pending") is not None

    def get_pending_intent(self) -> str | None:
        """获取未完成 skill 的意图"""
        pending = self.data.get("pending")
        return pending["intent"] if pending else None

    def get_state(self) -> dict | None:
        """获取未完成 skill 的状态"""
        pending = self.data.get("pending")
        return pending["state"] if pending else None

    def save_pending(self, intent: str, state: dict):
        """保存待恢复的 skill 状态"""
        self.data["pending"] = {"intent": intent, "state": state}
        self._save()

    def clear_pending(self):
        """清除待恢复状态"""
        self.data["pending"] = None
        self._save()

    # ---- Structured metadata ----

    def get_meta(self, key: str, default=None):
        """获取结构化会话元数据"""
        return self.data.get("meta", {}).get(key, default)

    def set_meta(self, key: str, value):
        """保存结构化会话元数据"""
        self.data.setdefault("meta", {})[key] = value
        self._save()
