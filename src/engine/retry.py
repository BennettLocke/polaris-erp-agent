"""重试机制"""
import time
from functools import wraps
from src.engine.exceptions import APIError
from src.utils import get_logger

logger = get_logger("sjagent.retry")


def retry_on_api_error(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """
    API 请求重试装饰器
    当遇到 APIError 时自动重试

    Args:
        max_retries: 最大重试次数
        delay: 初始延迟（秒）
        backoff: 退避倍数
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            current_delay = delay

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except APIError as e:
                    last_error = e
                    if attempt < max_retries:
                        logger.warning(
                            f"API 调用失败（第{attempt+1}次），{current_delay:.1f}秒后重试: {e}"
                        )
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(f"API 调用最终失败（已重试{max_retries}次）: {e}")

            raise last_error

        return wrapper
    return decorator
