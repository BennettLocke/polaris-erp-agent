"""
工具注册中心 - 统一注册所有业务工具
"""
from src.core.tools.registry import ToolRegistry, tool

# 导入所有工具模块（触发 @tool 装饰器注册）
from src.core.tools import erp_tools
from src.core.tools import order_tools
from src.core.tools import db_tools
from src.core.tools import script_tools
from src.core.tools import config_tools


def register_all_tools():
    """验证所有工具已通过 @tool 装饰器注册"""
    logger = __import__("src.utils", fromlist=["get_logger"]).get_logger("sjagent.tools")
    tool_count = len(ToolRegistry.list_tools())
    if tool_count == 0:
        logger.warning("没有工具被注册，请检查 @tool 装饰器")
    else:
        logger.info(f"工具注册完成，共 {tool_count} 个工具")


def list_all_tools():
    """列出所有已注册工具"""
    return ToolRegistry.list_tools()
