"""Extractive answer generator - offline, no API key required.

Builds an answer by extracting the most relevant sentences from the top
retrieved chunks: the query is tokenized into keywords (jieba + shared
stopwords), sentences in each chunk are scored by keyword hits, and the
best sentences are emitted as a bullet list with ``[n]`` citation markers.

This is the default provider because it runs deterministically with zero
external API calls.
"""

from __future__ import annotations

import re
from typing import Any

from src.core.query_engine.query_processor import DEFAULT_STOPWORDS
from src.core.types import RetrievalResult
from src.libs.answer_generator.base_answer_generator import (
    Answer,
    BaseAnswerGenerator,
)

# Sentence delimiters: Chinese/English punctuation plus newlines.
_SENTENCE_SPLIT_RE = re.compile(r"[。！？!?；;\n]+")


class ExtractiveAnswerGenerator(BaseAnswerGenerator):
    """Generates answers by extracting key sentences from retrieved chunks.

    Args:
        settings: Application settings (unused by this provider, kept for the
            uniform ``provider_class(settings=..., **override_kwargs)`` contract).
        confidence_threshold: Confidence below this triggers the low-confidence
            notice.
        max_chunks: Max number of top chunks used to build the answer.
        citation_generator: Optional CitationGenerator override (testing).
        snippet_max_length: Max characters per extracted sentence.
    """

    def __init__(
        self,
        settings: Any = None,
        confidence_threshold: float = 0.5,
        max_chunks: int = 3,
        citation_generator: Any | None = None,
        snippet_max_length: int = 200,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            settings=settings,
            confidence_threshold=confidence_threshold,
            max_chunks=max_chunks,
            citation_generator=citation_generator,
        )
        self.snippet_max_length = snippet_max_length

    def generate(
        self,
        query: str,
        chunks: list[RetrievalResult],
        trace: Any | None = None,
    ) -> Answer:
        """Generate an extractive answer from the top chunks.

        Args:
            query: The user query string.
            chunks: Retrieved chunks to draw the answer from.
            trace: Optional TraceContext (unused by the extractive path).

        Returns:
            An :class:`Answer` with keyword-hit sentences and ``[n]`` markers.
        """
        self.validate_query(query)
        if not chunks:
            return self._refusal_no_results(query)

        citations = self._build_citations(chunks)
        top = self._top_n(chunks)
        top_citations = citations[: len(top)]
        keywords = self._extract_keywords(query)

        points: list[str] = []
        for chunk, citation in zip(top, top_citations):
            best_sentences = self._rank_sentences(chunk.text, keywords, limit=2)
            marker = self._citation_generator.format_citation_marker(citation.index)
            for sentence in best_sentences:
                points.append(f"- {sentence} {marker}")

        # Fallback when no keyword-hitting sentence is found in any chunk.
        if not points:
            for i, chunk in enumerate(top):
                marker = self._citation_generator.format_citation_marker(
                    top_citations[i].index
                )
                points.append(f"- {self._truncate(chunk.text)} {marker}")

        confidence = self._top_score(chunks)
        parts: list[str] = [
            f"针对「{query}」，基于检索到的资料：",
            "",
            *points,
        ]
        notice = self._confidence_notice(confidence)
        if notice:
            parts.extend(["", notice])

        return Answer(
            content="\n".join(parts),
            citations=citations,
            confidence=confidence,
            refusal_reason="low_confidence" if notice else None,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _extract_keywords(self, query: str) -> list[str]:
        """Tokenize the query into keywords using jieba + shared stopwords."""
        try:
            import jieba

            tokens = list(jieba.cut(query))
        except ImportError:  # pragma: no cover - jieba is a project dependency
            tokens = [query]
        stopwords = set(DEFAULT_STOPWORDS)
        keywords = [
            token.strip()
            for token in tokens
            if token.strip() and token.strip() not in stopwords
        ]
        return keywords or [query]

    def _rank_sentences(
        self,
        text: str,
        keywords: list[str],
        limit: int = 2,
    ) -> list[str]:
        """Split ``text`` into sentences and return the top keyword-hitting ones.

        Sentences with zero keyword hits are dropped; the rest are sorted by
        hit count (descending), de-duplicated, and truncated.
        """
        if not text:
            return []
        keyword_set = set(keywords)
        scored: list[tuple] = []
        for sentence in _SENTENCE_SPLIT_RE.split(text):
            sentence = sentence.strip()
            if not sentence:
                continue
            hits = sum(1 for keyword in keyword_set if keyword in sentence)
            if hits > 0:
                scored.append((hits, sentence))

        scored.sort(key=lambda item: -item[0])

        seen = set()
        result: list[str] = []
        for _, sentence in scored:
            cleaned = " ".join(sentence.split())
            if cleaned in seen:
                continue
            seen.add(cleaned)
            result.append(self._truncate(cleaned))
            if len(result) >= limit:
                break
        return result

    def _truncate(self, text: str, length: int | None = None) -> str:
        """Collapse whitespace and truncate to ``snippet_max_length`` chars."""
        max_len = length if length is not None else self.snippet_max_length
        cleaned = " ".join((text or "").split())
        if len(cleaned) <= max_len:
            return cleaned
        return cleaned[:max_len] + "..."
