"""统一异常定义"""


class AgentError(Exception):
    """智能体基础异常"""
    pass


class APIError(AgentError):
    """API 请求异常"""

    def __init__(self, message: str, code: int = -1, response: dict = None):
        super().__init__(message)
        self.code = code
        self.response = response or {}


class DBError(AgentError):
    """数据库异常"""
    pass


class ConfigError(AgentError):
    """配置异常"""
    pass


class ToolError(AgentError):
    """工具执行异常"""
    pass
