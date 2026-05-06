"""日志系统 - 基于 loguru"""
import sys
import logging
from pathlib import Path
from loguru import logger
from src.core.config import get_config


def setup_logger() -> "logger":
    """初始化日志系统"""
    config = get_config()

    # 移除默认 handler
    logger.remove()

    # 控制台输出
    logger.add(
        sys.stdout,
        level=config.logging_level,
        format=config.get("logging.format", "{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {name} | {message}"),
        colorize=True,
    )

    # 文件输出
    log_file = Path(config.logging_file)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    logger.add(
        str(log_file),
        level=config.logging_level,
        format=config.get("logging.format", "{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {name} | {message}"),
        rotation=config.get("logging.max_bytes", 10485760),
        retention=config.get("logging.backup_count", 5),
        compression="zip",
        encoding="utf-8",
    )

    return logger


# 全局 logger 实例（懒加载）
_loguru_logger: "logger | None" = None


def get_logger(name: str = "sjagent") -> "logger":
    """获取日志实例"""
    global _loguru_logger
    if _loguru_logger is None:
        _loguru_logger = setup_logger()
    return logger.bind(name=name)


class LoggerMixin:
    """混入类，给其他类自动加上 logger 属性"""

    @property
    def logger(self):
        name = f"{self.__class__.__module__}.{self.__class__.__name__}"
        return get_logger(name)
