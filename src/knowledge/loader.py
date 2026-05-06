"""知识库加载器 - 将 sjbzwiki 文档常驻加载到内存"""
from __future__ import annotations
import re
from pathlib import Path
from typing import Optional
from src.core.config import get_config
from src.utils import get_logger

logger = get_logger("sjagent.knowledge.loader")

# 知识库缓存（全局常驻）
_knowledge_cache: dict[str, dict] = {}


class KnowledgeLoader:
    """
    知识库加载器
    从 sjbzwiki 目录加载所有文档，建立索引
    支持：全文索引、片段检索、全文匹配
    """

    def __init__(self):
        self.config = get_config()
        self.base_path = Path(self.config.knowledge_base_path)

    def load(self, force: bool = False) -> dict[str, dict]:
        """
        加载全部知识库文档到内存
        返回: {文件名: {"title": ..., "content": ..., "path": ...}}
        """
        global _knowledge_cache

        if _knowledge_cache and not force:
            logger.info(f"知识库已缓存，共 {len(_knowledge_cache)} 个文档")
            return _knowledge_cache

        docs = {}

        # 遍历 raw 目录下的所有 .md 文件
        raw_dir = self.base_path / "raw"
        if not raw_dir.exists():
            logger.warning(f"知识库目录不存在: {raw_dir}")
            return docs

        for md_file in raw_dir.rglob("*.md"):
            try:
                with open(md_file, encoding="utf-8") as f:
                    content = f.read()

                # 解析标题
                title = self._extract_title(content) or md_file.stem

                # 按 ## 拆分章节
                sections = self._split_sections(content)

                doc_key = str(md_file.relative_to(raw_dir))
                docs[doc_key] = {
                    "title": title,
                    "content": content,
                    "sections": sections,
                    "path": str(md_file),
                }
                logger.debug(f"加载知识库文档: {doc_key}")
            except Exception as e:
                logger.error(f"加载知识库文档失败 {md_file}: {e}")

        # 额外加载 wiki 目录下的 entities 和 concepts
        wiki_dir = self.base_path / "wiki"
        if wiki_dir.exists():
            for subdir in ["entities", "concepts"]:
                sub_path = wiki_dir / subdir
                if sub_path.exists():
                    for md_file in sub_path.rglob("*.md"):
                        try:
                            with open(md_file, encoding="utf-8") as f:
                                content = f.read()
                            title = self._extract_title(content) or md_file.stem
                            doc_key = f"wiki/{subdir}/{md_file.stem}"
                            docs[doc_key] = {
                                "title": title,
                                "content": content,
                                "sections": self._split_sections(content),
                                "path": str(md_file),
                            }
                        except Exception as e:
                            logger.error(f"加载文档失败 {md_file}: {e}")

        _knowledge_cache = docs
        logger.info(f"知识库加载完成，共 {len(docs)} 个文档")

        # 打印摘要
        for key, doc in docs.items():
            logger.debug(f"  - {key}: {doc['title']}")

        return docs

    def _extract_title(self, content: str) -> str | None:
        """从 markdown 内容中提取标题"""
        match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        return match.group(1).strip() if match else None

    def _split_sections(self, content: str) -> list[dict]:
        """
        按 ## 二级标题拆分章节
        返回: [{"title": ..., "content": ...}, ...]
        """
        sections = []
        parts = re.split(r"(?=^##\s)", content, flags=re.MULTILINE)

        for part in parts:
            part = part.strip()
            if not part:
                continue

            match = re.search(r"^##\s+(.+)$", part, re.MULTILINE)
            if match:
                title = match.group(1).strip()
                body = part[len(match.group(0)) :].strip()
                sections.append({"title": title, "content": body})
            elif re.match(r"^#\s+", part):
                # 一级标题（文件开头部分）
                lines = part.split("\n", 1)
                sections.append({"title": lines[0].lstrip("# ").strip(), "content": lines[1] if len(lines) > 1 else ""})

        return sections

    def get_doc(self, key: str) -> dict | None:
        """获取单个文档"""
        return _knowledge_cache.get(key)

    def search(self, keyword: str, top_k: int = 5) -> list[dict]:
        """
        全文搜索
        支持中文分词：先按标点分，再对长文本做滑窗提取关键词
        """
        keyword_lower = keyword.lower()
        results = []

        # 提取关键词列表
        keywords = []
        parts = re.split(r'[\s,，。、！？?]+', keyword_lower)
        for part in parts:
            if len(part) >= 2:
                keywords.append(part)

        # 对中文做滑窗分词
        if len(keyword_lower) > 4:
            cleaned = re.sub(r'[是什么的在有吗呢吧了么这那请问下查看看能和与或]', '', keyword_lower)
            cleaned = re.sub(r'[\s,，。、！？?]+', '', cleaned)
            for wlen in (4, 3, 2):
                for i in range(len(cleaned) - wlen + 1):
                    kw = cleaned[i:i+wlen]
                    if kw not in keywords:
                        keywords.append(kw)

        if not keywords:
            keywords = [keyword_lower]

        for doc_key, doc in _knowledge_cache.items():
            content = doc["content"].lower()

            # 对每个关键词计分，长关键词权重更高
            score = sum(content.count(kw) * len(kw) for kw in keywords)

            if score > 0:
                # 提取匹配片段
                matches = []
                # 用最短的有意义关键词定位
                search_kw = min((kw for kw in keywords if content.count(kw) > 0), key=len, default=keyword_lower)
                start = 0
                while len(matches) < 3:
                    pos = content.find(search_kw, start)
                    if pos == -1:
                        break
                    snippet_start = max(0, pos - 100)
                    snippet_end = min(len(content), pos + 100)
                    snippet = doc["content"][snippet_start:snippet_end]
                    matches.append(snippet)
                    start = pos + len(search_kw)

                results.append({
                    "doc_key": doc_key,
                    "title": doc["title"],
                    "score": score,
                    "matches": matches,
                    "source": doc["path"],
                })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]
