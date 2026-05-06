"""
sjagent 主入口
统一启动入口，支持多种渠道
"""
import argparse
import sys
import threading

# Windows 终端 GBK 编码兼容：输出 UTF-8；pythonw 后台启动时 stdout/stderr 可能为空。
if sys.stdout and sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr and sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
from dotenv import load_dotenv
load_dotenv()
from src.core.agent import Agent
from src.core.config import get_config
from src.utils import get_logger, setup_logger

logger = get_logger("sjagent.main")


def start_feishu(port: int = 5000):
    """启动飞书渠道"""
    from src.channels.feishu.bot import FeishuBot
    from src.channels.feishu.handler import init_handler, run_server

    config = get_config()
    app_id = config.get_with_env("feishu.app_id", "")
    app_secret = config.get_with_env("feishu.app_secret", "")

    if not app_id or not app_secret:
        logger.warning("飞书配置缺失，跳过飞书渠道启动")
        return

    bot = FeishuBot(app_id=app_id, app_secret=app_secret)
    init_handler(bot)

    logger.info(f"启动飞书渠道: port={port}")
    run_server(port=port)


def start_http_api(port: int = 8080):
    """启动 HTTP API 渠道"""
    from src.channels.http_api import init_api, run_api_server

    agent = Agent()
    init_api(agent)

    logger.info(f"启动 HTTP API 渠道: port={port}")
    run_api_server(port=port)


def run_console():
    """控制台交互模式"""
    agent = Agent()
    logger.info("sjagent 启动成功（控制台模式）")
    print("=" * 50)
    print("肆计包装-北极星订单管理机器人")
    print("输入 exit 退出")
    print("=" * 50)

    while True:
        try:
            user_input = input("\n用户> ").strip()
            if user_input.lower() in ("exit", "quit", "q"):
                print("再见！")
                break
            if not user_input:
                continue

            response = agent.run(user_input)
            print(f"\n智能体> {response}")
        except KeyboardInterrupt:
            print("\n再见！")
            break
        except Exception as e:
            print(f"\n异常: {e}")


def run_single(user_input: str) -> str:
    """单次执行模式"""
    agent = Agent()
    return agent.run(user_input)


def main():
    parser = argparse.ArgumentParser(description="sjagent - 肆计包装-北极星订单管理机器人")
    parser.add_argument("--mode", choices=["console", "feishu", "http", "all"], default="console",
                        help="运行模式：console=控制台, feishu=飞书渠道, http=HTTP API, all=全部")
    parser.add_argument("--feishu-port", type=int, default=5000, help="飞书渠道端口")
    parser.add_argument("--http-port", type=int, default=8080, help="HTTP API 端口")
    parser.add_argument("--message", type=str, help="单次执行模式，直接传入消息")

    args = parser.parse_args()

    # 初始化日志
    setup_logger()

    # 单次执行模式
    if args.message:
        result = run_single(args.message)
        print(result)
        return

    # 控制台模式
    if args.mode == "console":
        run_console()
        return

    # 多渠道模式
    threads = []
    if args.mode in ("feishu", "all"):
        t = threading.Thread(target=start_feishu, args=(args.feishu_port,), daemon=True)
        t.start()
        threads.append(t)

    if args.mode in ("http", "all"):
        t = threading.Thread(target=start_http_api, args=(args.http_port,), daemon=True)
        t.start()
        threads.append(t)

    if threads:
        logger.info("所有渠道已启动，按 Ctrl+C 退出")
        try:
            for t in threads:
                t.join()
        except KeyboardInterrupt:
            logger.info("收到退出信号")
    else:
        run_console()


if __name__ == "__main__":
    main()
