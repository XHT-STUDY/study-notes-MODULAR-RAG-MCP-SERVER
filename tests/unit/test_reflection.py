"""Tests for the Phase 6 retrieval reflector (sufficiency check + rewrite)."""

from __future__ import annotations

from src.core.agent.reflection import RetrievalReflector
from src.core.types import RetrievalResult


def _result(score: float) -> RetrievalResult:
    return RetrievalResult(chunk_id="c1", score=score, text="t", metadata={})


class TestEvaluate:
    def test_sufficient_results_no_reseek(self) -> None:
        reflector = RetrievalReflector(min_results=1, coverage_threshold=0.0)
        decision = reflector.evaluate([_result(0.9)], rounds_used=0)
        assert decision.needs_retrieval is False
        assert decision.reason == "证据充分"

    def test_few_results_needs_reseek(self) -> None:
        reflector = RetrievalReflector(min_results=3, coverage_threshold=0.0)
        decision = reflector.evaluate([_result(0.9)], rounds_used=0)
        assert decision.needs_retrieval is True
        assert "小于" in decision.reason

    def test_low_coverage_needs_reseek(self) -> None:
        reflector = RetrievalReflector(min_results=1, coverage_threshold=0.5)
        decision = reflector.evaluate([_result(0.2)], rounds_used=0)
        assert decision.needs_retrieval is True
        assert "低于阈值" in decision.reason

    def test_max_rounds_stops_reseeking(self) -> None:
        reflector = RetrievalReflector(
            min_results=3, coverage_threshold=0.0, max_retrieval_rounds=2
        )
        decision = reflector.evaluate([_result(0.9)], rounds_used=2)
        assert decision.needs_retrieval is False
        assert "上限" in decision.reason

    def test_disabled_never_reseeks(self) -> None:
        reflector = RetrievalReflector(
            enabled=False, min_results=10, coverage_threshold=0.99
        )
        decision = reflector.evaluate([], rounds_used=0)
        assert decision.needs_retrieval is False

    def test_empty_results_needs_reseek(self) -> None:
        reflector = RetrievalReflector(min_results=1, coverage_threshold=0.0)
        assert reflector.evaluate([], rounds_used=0).needs_retrieval is True


class TestRewrite:
    def test_splices_expanded_terms(self) -> None:
        reflector = RetrievalReflector()
        rewritten = reflector.rewrite("RAG 是什么", ["检索增强生成", "llm"])
        assert rewritten == "RAG 是什么（检索增强生成，llm）"

    def test_no_terms_returns_query_unchanged(self) -> None:
        reflector = RetrievalReflector()
        assert reflector.rewrite("RAG 是什么", []) == "RAG 是什么"

    def test_max_retrieval_rounds_property(self) -> None:
        reflector = RetrievalReflector(max_retrieval_rounds=3)
        assert reflector.max_retrieval_rounds == 3
