"""知识库检索器 - 基于关键词+段落匹配"""
import re
from typing import Optional
from src.knowledge.loader import KnowledgeLoader
from src.utils import get_logger

logger = get_logger("sjagent.knowledge.retriever")


class KnowledgeRetriever:
    """
    知识库检索器
    支持：关键词检索、段落匹配、全文索引
    检索结果用于注入 LLM 上下文
    """

    def __init__(self):
        self.loader = KnowledgeLoader()
        self._is_loaded = False
        self._docs = {}

    def load(self) -> None:
        """加载知识库到内存"""
        if self._is_loaded:
            return
        self._docs = self.loader.load()
        self._is_loaded = True
        logger.info("知识库检索器就绪")

    def retrieve(self, query: str, top_k: int = 5) -> list[dict]:
        """
        检索与 query 相关的知识片段

        Args:
            query: 用户查询（自然语言）
            top_k: 返回最多 top_k 条

        Returns:
            [{"title": ..., "content": ..., "source": ...}, ...]
        """
        if not self._is_loaded:
            self.load()

        # 1. 关键词搜索
        search_results = self.loader.search(query, top_k=top_k)

        # 2. 精确匹配（知识库中直接查找包含关键词的章节）
        section_matches = self._search_sections(query, top_k=top_k)

        # 3. 合并去重
        combined = {}
        for r in search_results:
            key = r["doc_key"]
            combined[key] = {
                "title": r["title"],
                "content": "\n---\n".join(r["matches"]),
                "source": r["source"],
                "score": r["score"],
            }

        for r in section_matches:
            key = r["doc_key"]
            if key in combined:
                combined[key]["content"] = r["content"][:500]  # 限制长度
            else:
                combined[key] = r

        results = list(combined.values())[:top_k]
        logger.info(f"知识库检索: query='{query}', 返回 {len(results)} 条")
        return results

    def _search_sections(self, query: str, top_k: int = 5) -> list[dict]:
        """在章节级别精确匹配"""
        results = []
        query_lower = query.lower()

        # 提取关键词：先按标点分，再对中文做简单分词
        keywords = []

        # 1. 按标点和空格分割
        parts = re.split(r'[\s,，。、！？?]+', query_lower)
        for part in parts:
            if len(part) >= 2:
                keywords.append(part)

        # 2. 对中文长文本做滑窗分词（去掉常见虚词后）
        if len(query_lower) > 4:
            # 去掉常见虚词/停用词
            cleaned = re.sub(r'[是什么的在有吗呢吧了么这那请问下查看看能和与或]', '', query_lower)
            cleaned = re.sub(r'[\s,，。、！？?]+', '', cleaned)
            # 2-4字滑窗
            for wlen in (4, 3, 2):
                for i in range(len(cleaned) - wlen + 1):
                    kw = cleaned[i:i+wlen]
                    if kw not in keywords:
                        keywords.append(kw)

        if not keywords:
            keywords = [query_lower]

        for doc_key, doc in self._docs.items():
            for section in doc.get("sections", []):
                section_text = section["content"].lower()
                score = 0
                for kw in keywords:
                    score += section_text.count(kw) * len(kw)  # 长关键词权重更高

                if score > 0:
                    results.append({
                        "doc_key": doc_key,
                        "title": section["title"],
                        "content": section["content"][:500],
                        "source": doc["path"],
                        "score": score,
                    })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]
