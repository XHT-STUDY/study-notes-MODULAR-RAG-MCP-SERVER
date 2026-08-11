"""Query understanding for the Agentic RAG layer (Phase 6).

Fills ``ProcessedQuery.expanded_terms`` — the one slot in the codebase that is
declared but never populated (``src/core/types.py``).  The offline alias table
adds synonyms / abbreviations / bilingual aliases so retrieval recall improves
without any LLM cost.  An LLM-backed expansion can subclass later.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from src.core.types import ProcessedQuery

#: Offline alias table: term → expansion terms (synonyms / abbreviations / bilingual).
_ALIAS_TABLE: dict[str, list[str]] = {
    "rag": ["检索增强生成", "retrieval augmented generation"],
    "llm": ["大语言模型", "大模型", "large language model"],
    "mcp": ["model context protocol", "模型上下文协议"],
    "bm25": ["稀疏检索", "sparse retrieval", "词频检索"],
    "embedding": ["向量化", "嵌入", "vector embedding"],
    "vector": ["向量", "embedding", "嵌入"],
    "rerank": ["重排", "重排序", "re-ranking"],
    "chunk": ["分块", "切块", "chunking"],
    "检索": ["搜索", "query", "查找"],
    "总结": ["摘要", "summary", "summarize"],
}


def _dedupe(items: list[str]) -> list[str]:
    """Dedupe while preserving first-seen order."""
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


class QueryUnderstanding(ABC):
    """Understands a query and expands it for better retrieval recall."""

    @abstractmethod
    def understand(self, query: str, trace: Any = None) -> ProcessedQuery:
        """Return a :class:`ProcessedQuery` with ``expanded_terms`` populated."""


class RuleQueryUnderstanding(QueryUnderstanding):
    """Offline expansion from the alias table (no LLM cost).

    Matching is case-insensitive substring matching; matched terms contribute
    their aliases.  An empty or blank query returns a bare :class:`ProcessedQuery`
    so downstream code never sees ``None``.
    """

    def understand(self, query: str, trace: Any = None) -> ProcessedQuery:
        query = query.strip()
        if not query:
            return ProcessedQuery(original_query="")

        lowered = query.lower()
        expanded: list[str] = []
        for term, aliases in _ALIAS_TABLE.items():
            if term.lower() in lowered:
                expanded.extend(aliases)
        return ProcessedQuery(
            original_query=query,
            keywords=[term for term in _ALIAS_TABLE if term.lower() in lowered],
            expanded_terms=_dedupe(expanded),
        )
