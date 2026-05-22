"""Agent 主入口 - Skill 固定流程架构"""
import asyncio
from src.core.config import get_config
from src.utils import get_logger

logger = get_logger("sjagent.agent")

_tools_registered = False


class Agent:
    """
    门店智能体主入口（Skill 固定流程）

    意图分类（正则）→ 固定流程执行 → LLM 只负责理解自然语言
    """

    def __init__(self):
        global _tools_registered
        if not _tools_registered:
            from src.core.tools import register_all_tools
            register_all_tools()
            _tools_registered = True

        from src.core.skill_engine import SkillEngine

        self.config = get_config()
        self.engine = SkillEngine()
        logger.info("Agent 初始化完成，工具已注册")

    def run(self, user_input: str, user_id: str = "default", session_id: str = "default") -> str:
        """
        运行智能体（Skill 固定流程）

        Args:
            user_input: 用户自然语言输入
            user_id: 用户标识
            session_id: 会话ID

        Returns:
            Agent 最终输出字符串
        """
        logger.info(f"[{session_id}] 用户输入: {user_input[:100]}...")

        try:
            output = self.engine.run(user_input, session_id)

            logger.info(f"[{session_id}] Agent输出: {output[:100]}...")
            return output
        except Exception as e:
            logger.error(f"[{session_id}] Agent执行异常: {e}")
            return f"处理异常：{str(e)}"

    async def arun(self, user_input: str, user_id: str = "default", session_id: str = "default") -> str:
        """异步运行（不阻塞事件循环）"""
        return await asyncio.to_thread(self.run, user_input, user_id, session_id)
