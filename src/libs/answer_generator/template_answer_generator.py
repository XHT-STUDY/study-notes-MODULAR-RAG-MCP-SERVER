"""Template answer generator for baselines and tests.

Produces a deterministic, fixed-format answer from the top chunks with a
fixed confidence of 0.5. Useful as a baseline for comparing generator
quality and for unit tests that need reproducible output.
"""

from __future__ import annotations

from typing import Any

from src.core.types import RetrievalResult
from src.libs.answer_generator.base_answer_generator import (
    Answer,
    BaseAnswerGenerator,
)


class TemplateAnswerGenerator(BaseAnswerGenerator):
    """Generates a fixed-template answer listing the top chunk snippets.

    Args:
        settings: Application settings (unused by this provider).
        confidence_threshold: Confidence below this triggers the low-confidence
            notice (template always scores 0.5, so only relevant if the
            threshold is above 0.5).
        max_chunks: Max number of top chunks included in the answer.
        citation_generator: Optional CitationGenerator override (testing).
        header: Markdown heading used as the answer title.
        snippet_max_length: Max characters per included chunk snippet.
    """

    def __init__(
        self,
        settings: Any = None,
        confidence_threshold: float = 0.5,
        max_chunks: int = 3,
        citation_generator: Any | None = None,
        header: str = "## 回答",
        snippet_max_length: int = 300,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            settings=settings,
            confidence_threshold=confidence_threshold,
            max_chunks=max_chunks,
            citation_generator=citation_generator,
        )
        self.header = header
        self.snippet_max_length = snippet_max_length

    def generate(
        self,
        query: str,
        chunks: list[RetrievalResult],
        trace: Any | None = None,
    ) -> Answer:
        """Generate a fixed-template answer from the top chunks."""
        self.validate_query(query)
        if not chunks:
            return self._refusal_no_results(query)

        citations = self._build_citations(chunks)
        top = self._top_n(chunks)
        top_citations = citations[: len(top)]

        lines: list[str] = [
            self.header,
            f"针对「{query}」，根据以下资料概述：",
            "",
        ]
        for chunk, citation in zip(top, top_citations):
            marker = self._citation_generator.format_citation_marker(citation.index)
            snippet = " ".join((chunk.text or "").split())[: self.snippet_max_length]
            lines.append(f"- {snippet} {marker}")

        return Answer(
            content="\n".join(lines),
            citations=citations,
            confidence=0.5,
        )
