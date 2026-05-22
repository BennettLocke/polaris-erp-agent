#!/usr/bin/env python3
"""Local sales-order print agent for sjagent.

Polls sjagent's native print queue, renders printable HTML to PDF, sends it to
the configured Windows printer, then marks the queue item as printed.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path


BASE_URL = os.environ.get("SJAGENT_PRINT_BASE_URL", "http://127.0.0.1:8081").rstrip("/")
PRINT_TOKEN = os.environ.get("SJAGENT_PRINT_AGENT_TOKEN", "").strip()
CHECK_INTERVAL = max(1, int(os.environ.get("SJAGENT_PRINT_CHECK_INTERVAL", "3") or 3))
PRINTER_NAME = os.environ.get("SJAGENT_PRINTER_NAME", "Kyocera TASKalfa 1800").strip()
CHROMIUM_PATH = os.environ.get(
    "CHROMIUM_PATH",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
).strip()

SCRIPT_DIR = Path(__file__).resolve().parent
NODE_SCRIPT = SCRIPT_DIR / "local_print_render_pdf.js"
PDF_DIR = SCRIPT_DIR / "pdf_output"
LOG_DIR = SCRIPT_DIR / "logs"
SUMATRA_PATH = SCRIPT_DIR / "SumatraPDF" / "SumatraPDF-3.5.2-64.exe"


def _setup_logging() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / f"sjagent_print_{datetime.now().strftime('%Y%m%d')}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    return logging.getLogger("sjagent_print")


logger = _setup_logging()


def _absolute_url(path_or_url: str) -> str:
    value = str(path_or_url or "").strip()
    if value.startswith(("http://", "https://")):
        return value
    if not value.startswith("/"):
        value = f"/{value}"
    return f"{BASE_URL}{value}"


def _headers() -> dict[str, str]:
    headers = {"Accept": "application/json"}
    if PRINT_TOKEN:
        headers["X-SJ-Print-Token"] = PRINT_TOKEN
    return headers


def _request_json(method: str, path_or_url: str, payload: dict | None = None) -> dict | None:
    url = _absolute_url(path_or_url)
    data = None
    headers = _headers()
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    try:
        req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8")
        return json.loads(body or "{}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        logger.error("请求失败: %s %s -> HTTP %s %s", method, url, exc.code, body[:300])
    except Exception as exc:
        logger.error("请求失败: %s %s -> %s", method, url, exc)
    return None


def fetch_print_tasks() -> list[dict]:
    result = _request_json("GET", "/api/print-agent/sales/tasks?page_size=20")
    if not isinstance(result, dict) or result.get("code") not in (0, "0", None):
        return []
    data = result.get("data") if isinstance(result.get("data"), dict) else {}
    rows = data.get("list") if isinstance(data, dict) else []
    return rows if isinstance(rows, list) else []


def mark_done(task: dict) -> bool:
    task_id = int(task.get("task_id") or task.get("id") or 0)
    result = _request_json("POST", task.get("done_url") or f"/api/print-agent/sales/tasks/{task_id}/done", {"task_id": task_id})
    return isinstance(result, dict) and result.get("code") in (0, "0")


def mark_failed(task: dict, reason: str) -> None:
    task_id = int(task.get("task_id") or task.get("id") or 0)
    _request_json(
        "POST",
        f"/api/print-agent/sales/tasks/{task_id}/fail",
        {"reason": str(reason or "打印失败")[:200]},
    )


def render_pdf(task: dict) -> Path | None:
    if not NODE_SCRIPT.exists():
        logger.error("未找到渲染脚本: %s", NODE_SCRIPT)
        return None
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    task_id = int(task.get("task_id") or task.get("id") or 0)
    sales_id = str(task.get("sales_id") or task.get("document_id") or task_id)
    html_path = task.get("html_url") or f"/api/print-agent/sales/tasks/{task_id}/html"
    html_url = _absolute_url(html_path)
    separator = "&" if "?" in html_url else "?"
    html_url = f"{html_url}{separator}auto=0"
    pdf_path = PDF_DIR / f"sjagent_sales_{sales_id}_{int(time.time())}.pdf"

    env = os.environ.copy()
    env["SJAGENT_PRINT_AGENT_TOKEN"] = PRINT_TOKEN
    if CHROMIUM_PATH:
        env["CHROMIUM_PATH"] = CHROMIUM_PATH

    try:
        result = subprocess.run(
            ["node", str(NODE_SCRIPT), html_url, str(pdf_path)],
            cwd=str(SCRIPT_DIR),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=90,
            env=env,
        )
    except subprocess.TimeoutExpired:
        logger.error("PDF 渲染超时: task_id=%s", task_id)
        return None
    except Exception as exc:
        logger.error("PDF 渲染异常: task_id=%s, error=%s", task_id, exc)
        return None

    if result.returncode != 0 or not pdf_path.exists():
        logger.error("PDF 渲染失败: stdout=%s stderr=%s", result.stdout[-800:], result.stderr[-800:])
        return None
    logger.info("PDF 已生成: %s (%.1f KB)", pdf_path, pdf_path.stat().st_size / 1024)
    return pdf_path


def print_pdf(pdf_path: Path) -> bool:
    if sys.platform != "win32":
        return print_pdf_linux(pdf_path)
    return print_pdf_windows(pdf_path)


def pdf_orientation(pdf_path: Path) -> str:
    """Return landscape/portrait from the first PDF MediaBox."""
    try:
        data = pdf_path.read_bytes()[:200_000].decode("latin1", errors="ignore")
        match = re.search(
            r"/MediaBox\s*\[\s*([\d.\-]+)\s+([\d.\-]+)\s+([\d.\-]+)\s+([\d.\-]+)\s*\]",
            data,
        )
        if not match:
            return "portrait"
        x0, y0, x1, y1 = [float(item) for item in match.groups()]
        return "landscape" if (x1 - x0) > (y1 - y0) else "portrait"
    except Exception as exc:
        logger.warning("读取 PDF 方向失败: %s", exc)
        return "portrait"


def print_pdf_windows(pdf_path: Path) -> bool:
    printer = PRINTER_NAME
    orientation = pdf_orientation(pdf_path)
    if SUMATRA_PATH.exists():
        cmd = [str(SUMATRA_PATH), "-silent", "-exit-when-done", "-print-settings", orientation]
        if printer:
            cmd.extend(["-print-to", printer])
        else:
            cmd.append("-print-to-default")
        cmd.append(str(pdf_path))
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
            if result.returncode == 0:
                logger.info("已发送到打印机: %s (%s)", printer or "系统默认", orientation)
                return True
            logger.error("SumatraPDF 打印失败: code=%s stdout=%s stderr=%s", result.returncode, result.stdout, result.stderr)
        except Exception as exc:
            logger.error("SumatraPDF 打印异常: %s", exc)

    try:
        import win32api  # type: ignore

        code = win32api.ShellExecute(0, "print", str(pdf_path), "", ".", 0)
        if code > 32:
            logger.info("已发送到打印机: %s", printer or "系统默认")
            time.sleep(3)
            return True
        logger.error("ShellExecute 打印失败: code=%s", code)
    except Exception as exc:
        logger.error("ShellExecute 打印异常: %s", exc)
    return False


def print_pdf_linux(pdf_path: Path) -> bool:
    cmd = ["lp"]
    if PRINTER_NAME:
        cmd += ["-d", PRINTER_NAME]
    cmd.append(str(pdf_path))
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except FileNotFoundError:
        logger.error("打印失败: 未找到 lp 命令")
        return False
    if result.returncode == 0:
        logger.info("已发送到打印机: %s", result.stdout.strip())
        return True
    logger.error("打印失败: %s", result.stderr.strip())
    return False


def process_task(task: dict) -> None:
    task_id = int(task.get("task_id") or task.get("id") or 0)
    logger.info(
        "[任务] #%s 销售单:%s 客户:%s",
        task_id,
        task.get("sales_no") or task.get("sales_id") or "-",
        task.get("customer_name") or "-",
    )
    pdf_path = render_pdf(task)
    if not pdf_path:
        mark_failed(task, "PDF 渲染失败")
        return
    if not print_pdf(pdf_path):
        mark_failed(task, "本地打印失败")
        return
    if mark_done(task):
        logger.info("任务 #%s 完成", task_id)
    else:
        logger.warning("任务 #%s 已打印，但标记完成失败", task_id)


def main() -> None:
    logger.info("=== sjagent 本地自动打印启动 ===")
    logger.info("API: %s", BASE_URL)
    logger.info("Node脚本: %s", NODE_SCRIPT)
    logger.info("检查间隔: %s秒", CHECK_INTERVAL)
    logger.info("打印机: %s", PRINTER_NAME or "系统默认")

    while True:
        try:
            for task in fetch_print_tasks():
                process_task(task)
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("已停止")
            break
        except Exception as exc:
            logger.error("轮询异常: %s", exc)
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
