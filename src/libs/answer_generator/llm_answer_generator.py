"""LLM answer generator with grounding validation and extractive fallback.

Generates answers via a configured LLM (``LLMFactory``), prompting it to
answer strictly from the provided chunks with ``[n]`` citation markers.
The LLM is created lazily; any failure (no API key, missing config, network
error, out-of-range citations, no valid citations) degrades silently to the
offline extractive generator so the query chain never breaks and answers are
always grounded in the returned chunks.
"""

from __future__ import annotations

import logging
from typing import Any

from src.core.types import RetrievalResult
from src.libs.answer_generator.base_answer_generator import (
    Answer,
    BaseAnswerGenerator,
    extract_citation_indices,
    sanitize_citation_markers,
)
from src.libs.answer_generator.extractive_answer_generator import (
    ExtractiveAnswerGenerator,
)
from src.libs.llm.base_llm import Message
from src.libs.llm.llm_factory import LLMFactory

logger = logging.getLogger(__name__)


class LLMAnswerGenerator(BaseAnswerGenerator):
    """Answers using a configured LLM, grounded on the retrieved chunks.

    Args:
        settings: Application settings (``llm`` section drives provider).
        llm: Optional pre-built LLM instance (injected mock for tests takes
            precedence over ``LLMFactory.create``).
        confidence_threshold: Confidence below this triggers the low-confidence
            notice.
        max_chunks: Max number of top chunks placed in the prompt.
        citation_generator: Optional CitationGenerator override (testing).
        temperature: Override for the LLM temperature (defaults to the LLM's
            own setting when None).
        max_tokens: Override for the LLM max_tokens.
        model: Override for the LLM model (not passed to all providers; the
            provider reads ``settings.llm.model`` by default).
    """

    def __init__(
        self,
        settings: Any = None,
        llm: Any = None,
        confidence_threshold: float = 0.5,
        max_chunks: int = 3,
        citation_generator: Any | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        model: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            settings=settings,
            confidence_threshold=confidence_threshold,
            max_chunks=max_chunks,
            citation_generator=citation_generator,
        )
        self._llm = llm
        self._llm_failure_reason: str | None = None
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.model = model
        self._fallback = ExtractiveAnswerGenerator(
            settings=settings,
            confidence_threshold=confidence_threshold,
            max_chunks=max_chunks,
            citation_generator=citation_generator,
        )

    def _get_llm(self) -> Any:
        """Lazily create the LLM; record and swallow any failure.

        A failed first attempt is cached as ``None`` so we do not retry (and
        re-fail) on every query in a long-lived server process.
        """
        if self._llm is None:
            try:
                self._llm = LLMFactory.create(self.settings)
            except Exception as e:  # no key / missing config / init error
                self._llm_failure_reason = str(e)
                logger.warning("LLM unavailable for answer generation: %s", e)
                self._llm = None
        return self._llm

    def generate(
        self,
        query: str,
        chunks: list[RetrievalResult],
        trace: Any | None = None,
    ) -> Answer:
        """Generate an LLM answer, degrading to extractive on any failure."""
        self.validate_query(query)
        if not chunks:
            return self._refusal_no_results(query)

        citations = self._build_citations(chunks)
        top = self._top_n(chunks)

        llm = self._get_llm()
        if llm is None:
            logger.warning(
                "LLM unavailable (%s); degrading to extractive answer generator",
                self._llm_failure_reason,
            )
            return self._fallback.generate(query, chunks, trace)

        try:
            text = self._call_llm(llm, query, top, trace)
        except Exception as e:
            logger.warning("LLM answer generation failed (%s); degrading to extractive", e)
            return self._fallback.generate(query, chunks, trace)

        # Rule 3 (grounding): strip out-of-range markers, fall back if none valid.
        valid_indices = range(1, len(chunks) + 1)
        refs = extract_citation_indices(text)
        bad = [r for r in refs if r not in set(valid_indices)]
        if bad:
            logger.warning("LLM cited out-of-range indices %s; stripped", bad)
            text = sanitize_citation_markers(text, valid_indices)
        if not extract_citation_indices(text):
            logger.warning("LLM answer had no valid citations; degrading to extractive")
            return self._fallback.generate(query, chunks, trace)

        confidence = self._top_score(chunks)
        notice = self._confidence_notice(confidence)
        if notice:
            text = f"{text}\n\n{notice}"
            return Answer(
                content=text,
                citations=citations,
                confidence=confidence,
                refusal_reason="low_confidence",
            )
        return Answer(content=text, citations=citations, confidence=confidence)

    def _call_llm(self, llm: Any, query: str, top: list[RetrievalResult], trace: Any) -> str:
        """Build the grounding prompt, call the LLM, and normalize to a string."""
        system_prompt = (
            "你是严格基于给定资料回答问题的助手。\n"
            "规则：\n"
            "1) 只能使用下面「资料」中的内容回答；\n"
            "2) 禁止编造，禁止引入资料之外的知识；\n"
            "3) 每个事实点必须用方括号编号标注出处，如 [1][2]；\n"
            "4) 若资料不足以回答，直接说明资料不足，不要猜测。"
        )
        materials = "\n".join(
            f"[{i + 1}] (score={chunk.score:.2f}) {(chunk.text or '').strip()}"
            for i, chunk in enumerate(top)
        )
        user_prompt = (
            f"问题：{query}\n\n资料：\n{materials}\n\n请回答（引用格式 [n]）："
        )
        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_prompt),
        ]

        kwargs: dict = {}
        if self.temperature is not None:
            kwargs["temperature"] = self.temperature
        if self.max_tokens is not None:
            kwargs["max_tokens"] = self.max_tokens

        response = llm.chat(messages, trace=trace, **kwargs)
        # Compatible with both ChatResponse objects and plain strings.
        return response.content if hasattr(response, "content") else str(response)
