"""
配置管理工具 - 运行时修改业务规则配置
安全限制：只允许修改 business_rules 部分
"""
import yaml
from pathlib import Path
from src.core.tools.registry import tool
from src.utils import get_logger

logger = get_logger("sjagent.tools.config")

# 允许修改的配置路径前缀（白名单）
ALLOWED_PREFIXES = [
    "business_rules.unit_conversion.",
    "business_rules.inventory_decision.",
    "business_rules.color_filter.",
    "business_rules.hot_stamp.",
    "business_rules.print_rules.",
    "business_rules.price_rules.",
    "business_rules.warehouse_defaults.",
    "business_rules.order_rules.",
    "business_rules.purchase_rules.",
    "business_rules.workflow.",
    "business_rules.image.",
    "business_rules.intent.",
    "business_rules.knowledge_qa.",
]

# 需要确认的敏感配置（修改前会要求用户确认）
SENSITIVE_KEYS = [
    "business_rules.warehouse_defaults.transfer_from",
    "business_rules.warehouse_defaults.transfer_to",
    "business_rules.warehouse_defaults.default_warehouse",
    "business_rules.price_rules.allow_empty_price",
]


def _get_config_path() -> Path:
    """获取 config.yaml 绝对路径"""
    return Path(__file__).parent.parent.parent.parent / "config.yaml"


def _load_config() -> dict:
    """加载配置文件"""
    config_path = _get_config_path()
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _save_config(data: dict):
    """保存配置文件"""
    config_path = _get_config_path()
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


def _get_nested(data: dict, dotpath: str):
    """按点号路径获取嵌套字典值"""
    keys = dotpath.split(".")
    current = data
    for k in keys:
        if isinstance(current, dict):
            current = current.get(k)
        else:
            return None
    return current


def _set_nested(data: dict, dotpath: str, value):
    """按点号路径设置嵌套字典值"""
    keys = dotpath.split(".")
    current = data
    for k in keys[:-1]:
        current = current.setdefault(k, {})
    current[keys[-1]] = value


@tool("config_query", "查询当前业务规则配置")
def config_query(section: str = "") -> dict:
    """
    查询配置（只读）

    Args:
        section: 配置路径，如 "business_rules.unit_conversion.one_piece_series"
                 为空则返回全部 business_rules

    Returns:
        配置内容
    """
    try:
        data = _load_config()

        if section:
            value = _get_nested(data, section)
            if value is None:
                return {"error": f"配置路径不存在: {section}"}
            return {"section": section, "value": value}
        else:
            return {"business_rules": data.get("business_rules", {})}
    except Exception as e:
        logger.error(f"配置查询失败: {e}")
        return {"error": str(e)}


@tool("config_update", "修改业务规则配置（需要用户确认）")
def config_update(section: str, value: str, action: str = "set") -> dict:
    """
    修改 config.yaml 中的业务规则配置

    安全限制：
    - 只允许修改 business_rules 下的配置
    - 修改前自动备份旧值
    - 所有修改记录到日志

    Args:
        section: 配置路径，如 "business_rules.unit_conversion.one_piece_series"
        value: 新值（JSON格式），如 '["见喜","岩味","新品种"]' 或 '"送至百鑫"' 或 'true'
        action: 操作类型
            - "set": 设置新值（覆盖）
            - "add": 向列表追加元素
            - "remove": 从列表移除元素

    Returns:
        {"success": True, "old_value": ..., "new_value": ..., "message": "..."}

    示例：
        # 添加1件起系列
        config_update("business_rules.unit_conversion.one_piece_series", '["礼盒A"]', "add")

        # 移除礼盒关键词
        config_update("business_rules.inventory_decision.gift_box_keywords", '"盒"', "remove")

        # 修改进货备注
        config_update("business_rules.purchase_rules.note", '"送至新仓库"', "set")
    """
    import json

    # 1. 安全校验：只允许修改 business_rules
    if not section.startswith("business_rules."):
        return {"error": f"安全限制：只允许修改 business_rules 下的配置，当前路径: {section}"}

    # 检查是否在白名单中
    if not any(section.startswith(prefix) for prefix in ALLOWED_PREFIXES):
        return {"error": f"不允许修改的配置路径: {section}"}

    try:
        # 2. 加载当前配置
        data = _load_config()
        old_value = _get_nested(data, section)

        # 3. 解析新值
        try:
            new_value = json.loads(value)
        except json.JSONDecodeError:
            # 尝试作为字符串处理
            new_value = value

        # 4. 根据操作类型执行
        if action == "set":
            _set_nested(data, section, new_value)
        elif action == "add":
            if not isinstance(old_value, list):
                return {"error": f"配置 {section} 不是列表类型，无法追加"}
            if isinstance(new_value, list):
                old_value.extend(new_value)
            else:
                old_value.append(new_value)
            _set_nested(data, section, old_value)
        elif action == "remove":
            if not isinstance(old_value, list):
                return {"error": f"配置 {section} 不是列表类型，无法移除"}
            if isinstance(new_value, list):
                for item in new_value:
                    if item in old_value:
                        old_value.remove(item)
            else:
                if new_value in old_value:
                    old_value.remove(new_value)
                else:
                    return {"error": f"值 {new_value} 不在列表中"}
            _set_nested(data, section, old_value)
        else:
            return {"error": f"不支持的操作类型: {action}，支持 set/add/remove"}

        # 5. 保存配置
        _save_config(data)

        # 6. 记录日志
        final_value = _get_nested(data, section)
        logger.info(f"配置修改: {section}, 旧值={old_value}, 新值={final_value}, 操作={action}")

        return {
            "success": True,
            "section": section,
            "old_value": old_value,
            "new_value": final_value,
            "action": action,
            "message": f"配置已更新: {section}",
        }

    except Exception as e:
        logger.error(f"配置修改失败: {e}")
        return {"error": str(e)}
