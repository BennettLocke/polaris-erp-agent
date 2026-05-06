"""
统一工具调用器
封装工具调用，包含参数校验、异常捕获、日志记录
"""
from typing import Any, Optional, Callable
from src.core.tools.registry import ToolRegistry
from src.engine.exceptions import ToolError
from src.utils import get_logger

logger = get_logger("sjagent.tools.caller")


class ToolCaller:
    """
    统一工具调用器
    所有工具调用通过此类执行，包含完整的日志和异常处理
    """

    def __init__(self):
        self.tools = ToolRegistry

    def call(self, tool_name: str, **kwargs) -> Any:
        """
        调用工具

        Args:
            tool_name: 工具名称
            **kwargs: 工具参数

        Returns:
            工具执行结果

        Raises:
            ToolError: 工具不存在或执行失败
        """
        tool_func = self.tools.get(tool_name)
        if not tool_func:
            raise ToolError(f"工具不存在: {tool_name}")

        logger.info(f"工具调用: {tool_name}, 参数: {kwargs}")

        try:
            result = tool_func(**kwargs)
            logger.debug(f"工具返回: {str(result)[:200]}")
            return result
        except TypeError as e:
            # 参数错误
            logger.error(f"工具参数错误: {tool_name}, {e}")
            raise ToolError(f"参数错误: {e}") from e
        except Exception as e:
            logger.error(f"工具执行异常: {tool_name}, {e}")
            raise ToolError(f"执行失败: {e}") from e

    def call_with_fallback(
        self,
        tool_name: str,
        fallback: Any = None,
        **kwargs,
    ) -> Any:
        """
        调用工具，失败时返回 fallback 值
        """
        try:
            return self.call(tool_name, **kwargs)
        except ToolError as e:
            logger.warning(f"工具调用失败，使用fallback: {e}")
            return fallback

    def list_tools(self) -> list[str]:
        """列出所有可用工具"""
        return self.tools.list_tools()


# 全局工具调用器
_tool_caller: Optional[ToolCaller] = None


def get_tool_caller() -> ToolCaller:
    """获取工具调用器单例"""
    global _tool_caller
    if _tool_caller is None:
        _tool_caller = ToolCaller()
    return _tool_caller
