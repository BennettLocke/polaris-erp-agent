"""
脚本调用工具
通过统一入口调用外部 Python 脚本
"""
import subprocess
import json
import sys
from pathlib import Path
from src.core.config import get_config
from src.core.tools.registry import tool
from src.utils import get_logger

logger = get_logger("sjagent.tools.script")


@tool("script_call", "调用外部Python脚本")
def script_call(script_name: str, args: list = None, kwargs: dict = None) -> dict:
    """
    调用外部 Python 脚本

    Args:
        script_name: 脚本文件名（相对于 scripts/ 目录）
        args: 位置参数列表
        kwargs: 关键字参数字典

    Returns:
        脚本返回的 JSON 结果（字典）
    """
    config = get_config()
    scripts_dir = Path(config.scripts_path).resolve()
    script_path = (scripts_dir / script_name).resolve()

    # 路径遍历保护：确保脚本路径在 scripts 目录内
    if not str(script_path).startswith(str(scripts_dir)):
        logger.error(f"非法脚本路径: {script_name}（路径遍历攻击）")
        return {"error": f"非法脚本路径: {script_name}"}

    if not script_path.exists():
        logger.error(f"脚本不存在: {script_path}")
        return {"error": f"脚本不存在: {script_name}"}

    cmd = [sys.executable, str(script_path)]

    # 添加位置参数
    if args:
        for arg in args:
            cmd.append(str(arg))

    # 添加关键字参数
    if kwargs:
        for k, v in kwargs.items():
            if isinstance(v, bool):
                if v:
                    cmd.append(f"--{k}")
            else:
                cmd.append(f"--{k}")
                cmd.append(str(v))

    try:
        logger.info(f"执行脚本: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode == 0:
            output = result.stdout.strip()
            try:
                return json.loads(output)
            except json.JSONDecodeError:
                for line in reversed(output.splitlines()):
                    line = line.strip()
                    if line.startswith("{") and line.endswith("}"):
                        try:
                            return json.loads(line)
                        except json.JSONDecodeError:
                            continue
                return {"raw": output}
        else:
            logger.error(f"脚本执行失败: {result.stderr}")
            return {"error": result.stderr or f"脚本返回码: {result.returncode}"}

    except subprocess.TimeoutExpired:
        logger.error(f"脚本执行超时: {script_name}")
        return {"error": "脚本执行超时"}
    except Exception as e:
        logger.error(f"脚本执行异常: {e}")
        return {"error": str(e)}


@tool("oss_upload", "上传图片到OSS")
def oss_upload(local_path: str) -> dict:
    """
    上传本地图片到 OSS

    Returns:
        {"url": "https://...", "path": "order/xxx.jpg"}
    """
    return script_call("oss_uploader.py", args=[local_path])


@tool("run_print_task", "执行打印任务")
def run_print_task(sales_id: int) -> dict:
    """执行打印任务脚本"""
    return script_call("print_task.py", args=[str(sales_id)])
