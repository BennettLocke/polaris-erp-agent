"""外部脚本调用节点"""
import subprocess
from pathlib import Path
from src.core.state import AgentState
from src.core.config import get_config
from src.utils import get_logger

logger = get_logger("sjagent.nodes.script")


def script_execute_node(state: AgentState) -> AgentState:
    """
    外部脚本调用节点
    调用 scripts/ 目录下的独立 Python 脚本
    """
    state["node_name"] = "script_execute"

    config = get_config()
    scripts_path = Path(config.scripts_path)

    # 判断需要调用的脚本
    intent = state.get("intent")
    sales_results = state.get("sales_results", [])

    # 如果有销售单结果 → 可能需要自动打印
    if sales_results and intent == "image_order":
        # 齐唯茶叶(customer_id=1)开单后自动打印
        customer_id = state.get("customer_info", {}).get("customer_id")
        if customer_id == config.qiwu_tea_id:
            for sale in sales_results:
                sales_id = sale.get("data") or sale.get("sales_id")
                if sales_id:
                    run_print_script(scripts_path, sales_id)

    return state


def run_print_script(scripts_path: Path, sales_id: str) -> None:
    """执行打印脚本"""
    script = scripts_path / "print_task.py"
    if not script.exists():
        logger.warning(f"打印脚本不存在: {script}")
        return

    try:
        result = subprocess.run(
            ["python", str(script), str(sales_id)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            logger.info(f"打印任务创建成功: sales_id={sales_id}")
        else:
            logger.error(f"打印脚本失败: {result.stderr}")
    except Exception as e:
        logger.error(f"打印脚本异常: {e}")
