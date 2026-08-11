"""Tests for the Phase 6 query understanding (expanded_terms population)."""

from __future__ import annotations

from src.core.agent.query_understanding import RuleQueryUnderstanding


class TestRuleQueryUnderstanding:
    def test_expands_matched_term(self) -> None:
        pq = RuleQueryUnderstanding().understand("如何使用 RAG 检索")
        assert "检索增强生成" in pq.expanded_terms
        assert "retrieval augmented generation" in pq.expanded_terms

    def test_preserves_original_query(self) -> None:
        query = "LLM 与 MCP 的关系"
        pq = RuleQueryUnderstanding().understand(query)
        assert pq.original_query == query

    def test_keywords_list_matched_terms(self) -> None:
        pq = RuleQueryUnderstanding().understand("BM25 检索")
        assert "bm25" in pq.keywords

    def test_filters_stay_empty(self) -> None:
        pq = RuleQueryUnderstanding().understand("RAG 是什么")
        assert pq.filters == {}

    def test_no_match_leaves_expanded_empty(self) -> None:
        pq = RuleQueryUnderstanding().understand("完全无关的普通问题")
        assert pq.expanded_terms == []

    def test_empty_query_is_safe(self) -> None:
        pq = RuleQueryUnderstanding().understand("   ")
        assert pq.original_query == ""
        assert pq.expanded_terms == []

    def test_dedupes_aliases(self) -> None:
        pq = RuleQueryUnderstanding().understand("RAG 和 vector 检索")
        assert len(pq.expanded_terms) == len(set(pq.expanded_terms))
