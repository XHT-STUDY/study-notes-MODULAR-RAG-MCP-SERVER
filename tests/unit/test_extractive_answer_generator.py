"""Unit tests for ExtractiveAnswerGenerator."""


import pytest

from src.core.types import RetrievalResult
from src.libs.answer_generator import ExtractiveAnswerGenerator


@pytest.fixture
def chunks() -> list[RetrievalResult]:
    return [
        RetrievalResult(
            chunk_id="c1",
            score=0.9,
            text="混合检索结合了稠密向量和稀疏关键词检索，并通过 RRF 融合。",
            metadata={"source_path": "a.pdf"},
        ),
        RetrievalResult(
            chunk_id="c2",
            score=0.6,
            text="RRF 融合对多个检索结果进行加权合并。",
            metadata={"source_path": "b.pdf"},
        ),
    ]


@pytest.mark.unit
class TestExtractiveAnswerGenerator:
    """Tests for the offline extractive answer generator."""

    def test_generate_with_results_has_citations(self, chunks: list[RetrievalResult]) -> None:
        generator = ExtractiveAnswerGenerator()
        answer = generator.generate("什么是混合检索", chunks)

        assert "针对「什么是混合检索」" in answer.content
        assert "[1]" in answer.content
        assert "[2]" in answer.content
        assert answer.confidence == 0.9
        assert answer.refusal_reason is None
        assert len(answer.citations) == 2
        assert answer.citations[0].chunk_id == "c1"
        assert answer.citations[1].index == 2

    def test_generate_no_results_returns_refusal(self) -> None:
        generator = ExtractiveAnswerGenerator()
        answer = generator.generate("问题", [])

        assert answer.refusal_reason == "no_retrieval_results"
        assert answer.confidence == 0.0
        assert "无法回答" in answer.content
        assert answer.citations == []

    def test_low_confidence_attaches_notice(self) -> None:
        chunks = [
            RetrievalResult(
                chunk_id="c1", score=0.3, text="内容甲。",
                metadata={"source_path": "a.pdf"},
            )
        ]
        generator = ExtractiveAnswerGenerator(confidence_threshold=0.5)
        answer = generator.generate("问题", chunks)

        assert answer.refusal_reason == "low_confidence"
        assert "置信度较低" in answer.content

    def test_high_confidence_no_notice(self, chunks: list[RetrievalResult]) -> None:
        generator = ExtractiveAnswerGenerator(confidence_threshold=0.5)
        answer = generator.generate("问题", chunks)

        assert answer.refusal_reason is None
        assert "置信度较低" not in answer.content

    def test_zero_threshold_disables_notice(self, chunks: list[RetrievalResult]) -> None:
        generator = ExtractiveAnswerGenerator(confidence_threshold=0.0)
        answer = generator.generate("问题", chunks)

        assert answer.refusal_reason is None
        assert "置信度较低" not in answer.content

    def test_max_chunks_limits_answer_content(self, chunks: list[RetrievalResult]) -> None:
        generator = ExtractiveAnswerGenerator(max_chunks=1)
        answer = generator.generate("问题", chunks)

        # Citations always cover all chunks; only the top chunk's content is used.
        assert len(answer.citations) == 2
        assert "[2]" not in answer.content

    def test_validate_query_rejects_empty(self) -> None:
        generator = ExtractiveAnswerGenerator()
        with pytest.raises(ValueError, match="cannot be empty"):
            generator.generate("   ", [])

    def test_fallback_truncates_when_no_keyword_hit(self) -> None:
        chunks = [
            RetrievalResult(
                chunk_id="c1", score=0.8,
                text="完全无关的一段长文本内容，用于验证无关键词命中时的兜底路径。",
                metadata={"source_path": "a.pdf"},
            )
        ]
        generator = ExtractiveAnswerGenerator(snippet_max_length=20)
        answer = generator.generate("xyz-nowhere", chunks)

        assert "[1]" in answer.content
        assert "..." in answer.content
