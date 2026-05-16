"""Cached voice prompts for the Orange Pi desktop robot."""
from __future__ import annotations

import random
import subprocess
from dataclasses import dataclass
from pathlib import Path

from src.core.config import get_config
from src.services.mimo_tts import synthesize
from src.utils import get_logger

logger = get_logger("sjagent.services.voice_prompts")


@dataclass(frozen=True)
class VoicePrompt:
    key: str
    text: str
    context: str = "你是桌面机器人小星，请用自然中文普通话回复。"


PROMPT_GROUPS: dict[str, list[VoicePrompt]] = {
    "wake": [
        VoicePrompt("wake_zaine", "在呢。", "用户刚刚喊了小星。"),
        VoicePrompt("wake_wozai", "我在。", "用户刚刚喊了小星。"),
        VoicePrompt("wake_en_wozai", "嗯，我在。", "用户刚刚喊了小星。"),
        VoicePrompt("wake_lailai", "来了。", "用户刚刚喊了小星。"),
        VoicePrompt("wake_tingzhe", "我听着呢。", "用户刚刚喊了小星。"),
        VoicePrompt("wake_xiaoxing", "小星在。", "用户刚刚喊了小星。"),
    ],
    "processing": [
        VoicePrompt("processing_favorite", "收到啦，正在给你处理。", "用户给小星发送了一条中文语音指令。"),
        VoicePrompt("processing_ok", "好的，我来处理。", "用户给小星发送了一条中文语音指令。"),
    ],
    "slow_8s": [
        VoicePrompt("slow_8s_chazhao", "还在查，稍等一下。", "小星正在处理查询任务，时间稍微有点久。"),
        VoicePrompt("slow_8s_chuli", "我还在处理，稍等。", "小星正在处理查询任务，时间稍微有点久。"),
    ],
    "slow_25s": [
        VoicePrompt("slow_25s_jixu", "这个稍微慢一点，我继续看。", "小星正在等待业务系统返回结果。"),
        VoicePrompt("slow_25s_xitong", "系统响应有点慢，我继续处理。", "小星正在等待业务系统返回结果。"),
    ],
    "failed": [
        VoicePrompt("failed_retry", "刚才没处理成功，你再说一遍。", "小星处理语音指令失败，需要用户重试。"),
        VoicePrompt("failed_again", "这个我没处理好，再试一次。", "小星处理语音指令失败，需要用户重试。"),
    ],
}


def voice_output_dir() -> Path:
    cfg = get_config().tts_config
    return Path(cfg.get("output_dir") or "./data/generated/voice") / "prompts"


def prompt_path(prompt: VoicePrompt) -> Path:
    return voice_output_dir() / f"{prompt.key}.wav"


def get_prompts(group: str) -> list[VoicePrompt]:
    prompts = PROMPT_GROUPS.get(group)
    if not prompts:
        raise KeyError(f"Unknown voice prompt group: {group}")
    return prompts


def pick_prompt(group: str) -> VoicePrompt:
    return random.choice(get_prompts(group))


def ensure_prompt(prompt: VoicePrompt, *, force: bool = False) -> Path:
    path = prompt_path(prompt)
    if path.exists() and path.stat().st_size > 0 and not force:
        return path
    return synthesize(prompt.text, path, context=prompt.context)


def ensure_group(group: str, *, force: bool = False) -> list[Path]:
    return [ensure_prompt(prompt, force=force) for prompt in get_prompts(group)]


def ensure_all_prompts(*, force: bool = False) -> list[Path]:
    paths: list[Path] = []
    for group in PROMPT_GROUPS:
        paths.extend(ensure_group(group, force=force))
    return paths


def play_file(path: str | Path, *, device: str = "") -> None:
    args = ["aplay"]
    if device:
        args.extend(["-D", device])
    args.append(str(path))
    subprocess.run(args, check=True)


def play_prompt(group: str, *, device: str = "", force: bool = False) -> Path:
    prompt = pick_prompt(group)
    path = ensure_prompt(prompt, force=force)
    logger.info(f"Play voice prompt: group={group}, key={prompt.key}, text={prompt.text}")
    play_file(path, device=device)
    return path


def should_play_processing(elapsed_seconds: float, expected_slow: bool = False) -> bool:
    """Avoid colliding with fast result speech.

    The voice loop should call this after command execution has been running for
    a moment. Fast results can be spoken directly without an extra processing
    prompt.
    """
    return expected_slow or elapsed_seconds >= 3.0
