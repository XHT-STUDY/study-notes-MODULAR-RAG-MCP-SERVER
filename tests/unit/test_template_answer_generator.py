"""Unit tests for TemplateAnswerGenerator."""

import pytest

from src.core.types import RetrievalResult
from src.libs.answer_generator import TemplateAnswerGenerator


@pytest.mark.unit
class TestTemplateAnswerGenerator:
    """Tests for the fixed-template baseline answer generator."""

    def test_generate_fixed_template(self) -> None:
        chunks = [
            RetrievalResult(
                chunk_id="c1", score=0.9, text="内容甲。",
                metadata={"source_path": "a.pdf"},
            ),
            RetrievalResult(
                chunk_id="c2", score=0.8, text="内容乙。",
                metadata={"source_path": "b.pdf"},
            ),
        ]
        generator = TemplateAnswerGenerator()
        answer = generator.generate("问题", chunks)

        assert answer.confidence == 0.5
        assert "## 回答" in answer.content
        assert "[1]" in answer.content
        assert "内容甲" in answer.content
        assert len(answer.citations) == 2

    def test_generate_no_results_refusal(self) -> None:
        generator = TemplateAnswerGenerator()
        answer = generator.generate("问题", [])

        assert answer.refusal_reason == "no_retrieval_results"
        assert answer.confidence == 0.0
