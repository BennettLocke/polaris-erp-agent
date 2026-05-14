"""Helpers for writing reviewed learning notes into the shared wiki."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re

from src.core.config import get_config
from src.utils import get_logger

logger = get_logger("sjagent.knowledge.wiki_inbox")

DENY_PATTERNS = [
    r"password\s*[:=]",
    r"api[_ -]?key\s*[:=]",
    r"secret\s*[:=]",
    r"token\s*[:=]",
    r"私钥",
    r"密钥",
    r"口令",
]


def wiki_root() -> Path:
    configured = Path(get_config().knowledge_base_path).expanduser()
    if not configured.is_absolute():
        configured = get_config().project_root / configured
    return configured.resolve(strict=False)


def is_safe_note(text: str) -> bool:
    value = str(text or "")
    return bool(value.strip()) and not any(re.search(pattern, value, re.IGNORECASE) for pattern in DENY_PATTERNS)


def record_wiki_inbox(
    title: str,
    body: str,
    category: str = "learning",
    source: str = "sjagent",
    wiki_base: Path | None = None,
) -> Path | None:
    """Append a note to wiki/inbox/YYYY-MM-DD.md for human review."""
    if not is_safe_note(title) or not is_safe_note(body):
        logger.warning("跳过知识库 inbox 写入：内容为空或疑似敏感")
        return None

    base = wiki_base or wiki_root()
    inbox_dir = base / "wiki" / "inbox"
    inbox_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    path = inbox_dir / f"{now:%Y-%m-%d}.md"
    if not path.exists():
        path.write_text(
            "---\n"
            f"title: 知识库待确认 {now:%Y-%m-%d}\n"
            "type: synthesis\n"
            "tags: [inbox, 待确认, 智能体学习]\n"
            "sources: [sjagent]\n"
            f"created: {now:%Y-%m-%d}\n"
            f"updated: {now:%Y-%m-%d}\n"
            "---\n\n"
            f"# 知识库待确认 {now:%Y-%m-%d}\n",
            encoding="utf-8",
        )

    with path.open("a", encoding="utf-8") as f:
        f.write(
            "\n"
            f"## {title}\n\n"
            f"- 时间：{now:%Y-%m-%d %H:%M:%S}\n"
            f"- 分类：{category}\n"
            f"- 来源：{source}\n\n"
            f"{body.strip()}\n"
        )
    logger.info(f"已写入知识库 inbox: {path}")
    return path


def sync_series_rules_page(
    one_piece: list[str],
    non_one_piece: list[str],
    source: str = "sjagent series_manage",
    wiki_base: Path | None = None,
) -> Path | None:
    """Write current one-piece/non-one-piece rules into the formal wiki page."""
    base = wiki_base or wiki_root()
    page = base / "wiki" / "concepts" / "件套换算.md"
    if not page.exists():
        logger.warning(f"件套换算页面不存在，跳过同步: {page}")
        return None

    now = datetime.now()
    text = page.read_text(encoding="utf-8")
    block = (
        "<!-- AUTO:series-rules:start -->\n"
        "## 智能体维护的起订规则\n\n"
        f"> 更新时间：{now:%Y-%m-%d %H:%M:%S}；来源：{source}\n\n"
        "### 1件起订系列\n\n"
        + "\n".join(f"- {name}" for name in one_piece)
        + "\n\n### 非1件起订系列\n\n"
        + "\n".join(f"- {name}" for name in non_one_piece)
        + "\n<!-- AUTO:series-rules:end -->\n"
    )
    pattern = r"<!-- AUTO:series-rules:start -->.*?<!-- AUTO:series-rules:end -->\n?"
    if re.search(pattern, text, flags=re.S):
        new_text = re.sub(pattern, block, text, flags=re.S)
    else:
        new_text = text.rstrip() + "\n\n" + block
    page.write_text(new_text, encoding="utf-8")
    logger.info(f"已同步系列规则到 wiki: {page}")
    return page
