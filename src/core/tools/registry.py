"""工具注册器 - 统一管理所有业务工具"""
from typing import Callable, Any
from src.utils import get_logger

logger = get_logger("sjagent.tools.registry")


class ToolRegistry:
    """
    工具注册中心
    所有业务工具在这里注册，Agent 通过工具名调用
    """

    _tools: dict[str, Callable] = {}

    @classmethod
    def register(cls, name: str, func: Callable, description: str = "") -> None:
        """注册一个工具"""
        cls._tools[name] = func
        logger.info(f"工具注册: {name}")

    @classmethod
    def get(cls, name: str) -> Callable | None:
        """获取工具"""
        return cls._tools.get(name)

    @classmethod
    def list_tools(cls) -> list[str]:
        """列出所有已注册工具"""
        return list(cls._tools.keys())


def tool(name: str, description: str = ""):
    """
    工具装饰器
    用法:
        @tool("inventory_query", "查询库存")
        def inventory_query(product_id: int):
            ...
    """
    def decorator(func: Callable) -> Callable:
        ToolRegistry.register(name, func, description)
        return func
    return decorator
