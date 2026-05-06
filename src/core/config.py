"""全局配置加载器 - 从 config.yaml 读取所有配置"""
import os
import yaml
from pathlib import Path
from typing import Any, Optional
from functools import lru_cache


class Config:
    """全局配置单例"""

    _instance: Optional["Config"] = None
    _data: dict = {}

    def __new__(cls) -> "Config":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load()
        return cls._instance

    def _load(self) -> None:
        """加载 config.yaml"""
        config_path = Path(__file__).parent.parent.parent / "config.yaml"
        if not config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_path}")

        with open(config_path, encoding="utf-8") as f:
            self._data = yaml.safe_load(f)

    def reload(self) -> None:
        """重新加载 config.yaml，供运行时规则变更后刷新内存配置。"""
        self._load()

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置，支持点号分隔的路径，如 config.get('erp.api_key')
        """
        keys = key.split(".")
        value = self._data
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
            if value is None:
                return default
        return value

    def get_with_env(self, key: str, default: Any = None) -> Any:
        """
        获取配置，并将 ${ENV_VAR} 形式的占位符替换为环境变量
        """
        value = self.get(key, default)
        if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
            env_var = value[2:-1]
            return os.environ.get(env_var, default)
        return value

    @property
    def erp_api_base(self) -> str:
        return self.get("erp.api_base")

    @property
    def erp_api_key(self) -> str:
        return self.get_with_env("erp.api_key")

    @property
    def warehouse_self(self) -> int:
        return int(self.get("erp.warehouse.self", 1))

    @property
    def warehouse_baixin(self) -> int:
        return int(self.get("erp.warehouse.baixin", 2))

    @property
    def qiwu_tea_id(self) -> int:
        return int(self.get("erp.customer.qiwu_tea_id", 1))

    @property
    def db_config(self) -> dict:
        return {
            "host": self.get_with_env("database.host"),
            "port": int(self.get_with_env("database.port", 3306)),
            "name": self.get_with_env("database.name"),
            "user": self.get_with_env("database.user"),
            "password": self.get_with_env("database.password"),
            "charset": self.get("database.charset", "utf8mb4"),
        }

    @property
    def oss_config(self) -> dict:
        return {
            "access_key_id": self.get_with_env("oss.access_key_id"),
            "access_key_secret": self.get_with_env("oss.access_key_secret"),
            "bucket": self.get("oss.bucket"),
            "endpoint": self.get("oss.endpoint"),
            "domain": self.get("oss.domain"),
            "upload_path": self.get("oss.upload_path"),
        }

    @property
    def knowledge_base_path(self) -> str:
        return self.get("knowledge_base.path", "./src/knowledge/sjbzwiki")

    @property
    def knowledge_preload(self) -> bool:
        return self.get("knowledge_base.preload", True)

    @property
    def llm_provider(self) -> str:
        return self.get("llm.provider", "anthropic")

    @property
    def llm_base_url(self) -> str:
        return self.get("llm.base_url", "")

    @property
    def llm_model(self) -> str:
        return self.get("llm.model", "mimo-v2.5-pro")

    @property
    def llm_api_key(self) -> str:
        return self.get_with_env("llm.api_key", "")

    @property
    def llm_max_tokens(self) -> int:
        return int(self.get("llm.max_tokens", 4096))

    @property
    def logging_level(self) -> str:
        return self.get("logging.level", "INFO")

    @property
    def logging_file(self) -> str:
        return self.get("logging.file", "./logs/sjagent.log")

    @property
    def scripts_path(self) -> str:
        return self.get("scripts.path", "./scripts")

    @property
    def max_history_turns(self) -> int:
        return int(self.get("history.max_turns", 10))


@lru_cache(maxsize=1)
def get_config() -> Config:
    """获取配置单例（带缓存）"""
    return Config()
