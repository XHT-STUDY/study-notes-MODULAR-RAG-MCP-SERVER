"""Retrieval reflection for the Agentic RAG layer (Phase 6).

After a retrieval pass the reflector decides whether the evidence is
sufficient.  If not, it rewrites the query by splicing ``expanded_terms`` back
into the original text and the loop re-searches — bounded by
``max_retrieval_rounds``.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.core.types import RetrievalResult


@dataclass
class ReflectionDecision:
    """Verdict of one reflection pass."""

    needs_retrieval: bool
    reason: str = ""
    rewritten_query: str | None = None


class RetrievalReflector:
    """Rule-based evidence sufficiency check + query rewrite.

    Args:
        enabled: When False every evaluation returns ``needs_retrieval=False``.
        min_results: Re-seek when fewer results than this came back.
        coverage_threshold: Re-seek when the top score is below this (0..1).
        max_retrieval_rounds: Hard cap on re-seeks per query.
    """

    def __init__(
        self,
        enabled: bool = True,
        min_results: int = 1,
        coverage_threshold: float = 0.0,
        max_retrieval_rounds: int = 2,
    ) -> None:
        self._enabled = enabled
        self._min_results = min_results
        self._coverage_threshold = coverage_threshold
        self._max_retrieval_rounds = max_retrieval_rounds

    @property
    def max_retrieval_rounds(self) -> int:
        return self._max_retrieval_rounds

    def evaluate(
        self,
        results: list[RetrievalResult],
        rounds_used: int,
    ) -> ReflectionDecision:
        """Decide whether another retrieval pass is warranted."""
        if not self._enabled:
            return ReflectionDecision(
                needs_retrieval=False, reason="反射已禁用"
            )
        if rounds_used >= self._max_retrieval_rounds:
            return ReflectionDecision(
                needs_retrieval=False,
                reason=f"已达重检轮数上限 {self._max_retrieval_rounds}",
            )
        if len(results) < self._min_results:
            return ReflectionDecision(
                needs_retrieval=True,
                reason=f"结果数 {len(results)} 小于 {self._min_results}",
            )
        top_score = results[0].score if results else 0.0
        if top_score < self._coverage_threshold:
            return ReflectionDecision(
                needs_retrieval=True,
                reason=f"最高分 {top_score:.3f} 低于阈值 {self._coverage_threshold}",
            )
        return ReflectionDecision(needs_retrieval=False, reason="证据充分")

    def rewrite(self, query: str, expanded_terms: list[str]) -> str:
        """Splice expanded terms into the original query for a re-seek."""
        if not expanded_terms:
            return query
        return f"{query}（{'，'.join(expanded_terms)}）"
