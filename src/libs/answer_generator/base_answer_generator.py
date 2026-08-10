"""Abstract base class for Answer Generator providers.

This module defines the pluggable interface for answer generation providers,
enabling seamless switching between offline (extractive), LLM-based, and
template backends through configuration-driven instantiation.

Three cross-cutting rules are shared by all generators:
1. No retrieval results -> refusal (no_retrieval_results).
2. Low confidence (< confidence_threshold) -> attach a "资料不足" notice and
   downgrade confidence (low_confidence), without refusing the whole answer.
3. Citations in the answer must be grounded in the returned chunks
   (LLM output is validated and out-of-range markers stripped).
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from src.core.response.citation_generator import Citation, CitationGenerator
from src.core.types import RetrievalResult

_CITATION_PATTERN = re.compile(r"\[(\d+)\]")


def extract_citation_indices(text: str) -> list[int]:
    """Extract all citation indices ``[n]`` from text.

    Args:
        text: Text possibly containing ``[1]``-style citation markers.

    Returns:
        List of integer indices in document order (empty if none).
    """
    if not text:
        return []
    return [int(m) for m in _CITATION_PATTERN.findall(text)]


def sanitize_citation_markers(text: str, valid_indices: Any) -> str:
    """Strip ``[n]`` markers whose index is not in ``valid_indices``.

    Used for grounding validation: an answer may only cite chunks that were
    actually returned.

    Args:
        text: The answer text to sanitize.
        valid_indices: Iterable of valid 1-based citation indices.

    Returns:
        Text with out-of-range markers removed.
    """
    if not text:
        return text
    valid = set(valid_indices)
    return _CITATION_PATTERN.sub(
        lambda m: m.group(0) if int(m.group(1)) in valid else "",
        text,
    )


@dataclass
class Answer:
    """Generated answer with citations, confidence, and optional refusal.

    Attributes:
        content: The generated answer text (empty when refused/disabled).
        citations: Structured citations backing the answer (reuses
            ``src.core.response.Citation``).
        confidence: Relevance confidence in [0, 1].
        refusal_reason: Set when the generator refuses to answer (e.g.
            ``no_retrieval_results`` / ``low_confidence`` / disabled).
    """

    content: str
    citations: list[Citation] = field(default_factory=list)
    confidence: float = 0.0
    refusal_reason: str | None = None


class BaseAnswerGenerator(ABC):
    """Abstract base class for answer generator providers.

    Design Principles Applied:
    - Pluggable: Subclasses can be swapped without changing upstream code.
    - Observable: Accepts optional TraceContext for observability integration.
    - Config-Driven: Instances are created via factory based on settings.
    - Fail-Safe: LLM-based generators degrade to the offline extractive
      generator rather than breaking the query chain.
    """

    #: Set to False by no-op implementations (e.g. NoneAnswerGenerator).
    is_enabled: bool = True

    def __init__(
        self,
        settings: Any = None,
        confidence_threshold: float = 0.5,
        max_chunks: int = 3,
        citation_generator: CitationGenerator | None = None,
    ) -> None:
        """Initialize the answer generator.

        Args:
            settings: Application settings (used by LLM-backed generators).
            confidence_threshold: Confidence below this triggers the
                low-confidence notice (0 disables the notice).
            max_chunks: Max number of top chunks used to build the answer.
            citation_generator: Optional CitationGenerator override (testing).
        """
        self.settings = settings
        self.confidence_threshold = confidence_threshold
        self.max_chunks = max_chunks
        self._citation_generator = citation_generator or CitationGenerator()

    @abstractmethod
    def generate(
        self,
        query: str,
        chunks: list[RetrievalResult],
        trace: Any | None = None,
    ) -> Answer:
        """Generate an answer from the query and retrieved chunks.

        Args:
            query: The user query string.
            chunks: Retrieved chunks (``RetrievalResult`` list) to ground the
                answer on.
            trace: Optional TraceContext for observability.

        Returns:
            An :class:`Answer` with citations and confidence.
        """
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Shared helpers (three cross-cutting rules live here, DRY)
    # ------------------------------------------------------------------

    def validate_query(self, query: str) -> None:
        """Validate the query string.

        Args:
            query: Query string to validate.

        Raises:
            ValueError: If the query is empty or not a string.
        """
        if not isinstance(query, str):
            raise ValueError(f"Query must be a string, got {type(query).__name__}")
        if not query.strip():
            raise ValueError("Query cannot be empty or whitespace-only")

    def _build_citations(self, chunks: list[RetrievalResult]) -> list[Citation]:
        """Build 1-based citations for the given chunks (``[n]`` = position)."""
        return self._citation_generator.generate(chunks)

    def _top_score(self, chunks: list[RetrievalResult]) -> float:
        """Return the top chunk score rounded to 4 decimals (or 0.0)."""
        if not chunks:
            return 0.0
        try:
            return round(float(chunks[0].score), 4)
        except (TypeError, ValueError):
            return 0.0

    def _top_n(self, chunks: list[RetrievalResult]) -> list[RetrievalResult]:
        """Return the first ``max_chunks`` chunks (all when None/negative)."""
        if not self.max_chunks or self.max_chunks < 0:
            return chunks
        return chunks[: self.max_chunks]

    def _refusal_no_results(self, query: str) -> Answer:
        """Rule 1: refuse when there are no retrieval results."""
        content = (
            "未检索到与问题相关的资料，无法回答。\n"
            "请尝试调整关键词或扩大集合范围后重试。"
        )
        return Answer(
            content=content,
            citations=[],
            confidence=0.0,
            refusal_reason="no_retrieval_results",
        )

    def _confidence_notice(self, confidence: float) -> str | None:
        """Rule 2: return a low-confidence notice when below the threshold.

        Returns None when confidence is at/above the threshold or the
        threshold is 0 (explicitly disabled).
        """
        threshold = float(self.confidence_threshold)
        if threshold <= 0:
            return None
        if confidence < threshold:
            return f"> 基于现有资料置信度较低（{confidence:.0%}），建议进一步核实。"
        return None


class NoneAnswerGenerator(BaseAnswerGenerator):
    """No-op answer generator used when answer generation is disabled.

    Mirrors ``NoneEvaluator``: keeps the call site branch-free while
    producing an empty, disabled-marked answer.
    """

    is_enabled = False

    def __init__(self, settings: Any = None, **kwargs: Any) -> None:
        super().__init__(settings=settings, **kwargs)

    def generate(
        self,
        query: str,
        chunks: list[RetrievalResult],
        trace: Any | None = None,
    ) -> Answer:
        self.validate_query(query)
        return Answer(
            content="",
            citations=[],
            confidence=0.0,
            refusal_reason="answer_generator disabled",
        )
