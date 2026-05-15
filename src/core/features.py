"""Runtime feature switches for different sjagent devices."""
from __future__ import annotations

import os


TRUE_VALUES = {"1", "true", "yes", "on", "enable", "enabled"}
FALSE_VALUES = {"0", "false", "no", "off", "disable", "disabled"}
LITE_PROFILES = {"lite", "orangepi", "orangepi_desktop", "desktop_robot"}
LITE_DEFAULT_DISABLED = {
    "bag_upload",
    "asr_hotword_scheduler",
}


def _env_bool(name: str) -> bool | None:
    value = os.environ.get(name)
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    return None


def device_profile() -> str:
    return (
        os.environ.get("SJAGENT_DEVICE_PROFILE")
        or os.environ.get("DEVICE_PROFILE")
        or "full"
    ).strip().lower()


def lite_mode_enabled() -> bool:
    explicit = _env_bool("SJAGENT_LITE_MODE")
    if explicit is not None:
        return explicit
    return device_profile() in LITE_PROFILES


def feature_enabled(feature: str, default: bool = True) -> bool:
    """Return whether a feature should be active in this process.

    Per-feature env vars win first:
    - SJAGENT_ENABLE_<FEATURE>=1/0
    - ENABLE_<FEATURE>=1/0
    - SJAGENT_DISABLE_<FEATURE>=1/0
    """
    key = feature.upper().replace("-", "_")

    for name in (f"SJAGENT_ENABLE_{key}", f"ENABLE_{key}"):
        explicit = _env_bool(name)
        if explicit is not None:
            return explicit

    for name in (f"SJAGENT_DISABLE_{key}", f"DISABLE_{key}"):
        explicit = _env_bool(name)
        if explicit is not None:
            return not explicit

    if lite_mode_enabled() and feature in LITE_DEFAULT_DISABLED:
        return False

    return default


def disabled_feature_reply(feature: str) -> str:
    labels = {
        "bag_upload": "泡袋上传处理",
        "asr_hotword_scheduler": "阿里云 ASR 热词后台同步",
    }
    label = labels.get(feature, feature)
    return (
        f"{label}在这台设备上没有启用。代码仍会跟随 Gitee 更新，"
        "需要使用时把对应功能开关打开即可。"
    )
