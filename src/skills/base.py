"""Workflow 基类 - 所有 skill 流程的统一接口"""
from abc import ABC, abstractmethod
from src.utils import get_logger

logger = get_logger("sjagent.skills.base")


class BaseWorkflow(ABC):
    """
    Skill 流程基类。

    每个 skill 必须实现 execute()，可选实现 resume()。

    execute() 返回格式：
        {"reply": "..."}  → 流程结束，直接回复用户
        {"status": "ask", "question": "...", "state": {...}}  → 需要问用户，暂停流程

    resume() 返回格式：
        {"reply": "..."}  → 流程结束
        {"status": "ask", ...}  → 继续问用户
    """

    @abstractmethod
    def execute(self, user_input: str, params: dict = None) -> dict:
        """执行流程（params 为 LLM 预提取的参数，可直接使用）"""
        raise NotImplementedError

    def resume(self, user_input: str, state: dict) -> dict:
        """恢复执行（用户回答了上一步的问题后调用）"""
        # 默认实现：不支持暂停/恢复
        return {"reply": "抱歉，该功能不支持继续操作，请重新开始。"}

    def _ask(self, question: str, state: dict) -> dict:
        """快捷方法：返回需要问用户的结果"""
        return {"status": "ask", "question": question, "state": state}

    def _reply(self, text: str) -> dict:
        """快捷方法：返回流程完成的结果"""
        return {"reply": text}
