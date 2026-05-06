"""
飞书消息发送脚本
通过飞书机器人 API 发送消息
"""
import sys
import json
import argparse

try:
    import requests
except ImportError:
    requests = None


def send_feishu_message(
    webhook_url: str,
    msg_type: str = "text",
    content: dict = None,
) -> dict:
    """
    通过飞书 Webhook 发送消息

    Args:
        webhook_url: 飞书机器人 Webhook URL
        msg_type: 消息类型 (text/image/post/card)
        content: 消息内容

    Returns:
        {"code": 0, "msg": "success"} 或 {"error": "..."}
    """
    if requests is None:
        return {"error": "requests 库未安装"}

    try:
        payload = {"msg_type": msg_type, "content": content or {}}
        response = requests.post(webhook_url, json=payload, timeout=10)
        return response.json()
    except Exception as e:
        return {"error": str(e)}


def main():
    parser = argparse.ArgumentParser(description="飞书消息发送")
    parser.add_argument("--webhook", required=True, help="飞书 Webhook URL")
    parser.add_argument("--text", required=True, help="消息内容")
    args = parser.parse_args()

    result = send_feishu_message(
        webhook_url=args.webhook,
        msg_type="text",
        content={"text": args.text},
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
