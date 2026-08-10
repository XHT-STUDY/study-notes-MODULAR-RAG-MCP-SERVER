"""Unit tests for LLMAnswerGenerator with a mocked LLM."""

from unittest.mock import Mock

import pytest

from src.core.types import RetrievalResult
from src.libs.answer_generator import LLMAnswerGenerator
from src.libs.llm.base_llm import ChatResponse, Message


def _chunks() -> list[RetrievalResult]:
    return [
        RetrievalResult(
            chunk_id="c1", score=0.9,
            text="Azure OpenAI 是微软提供的云服务。",
            metadata={"source_path": "a.pdf"},
        ),
        RetrievalResult(
            chunk_id="c2", score=0.7,
            text="配置需要 API 密钥。",
            metadata={"source_path": "b.pdf"},
        ),
    ]


@pytest.mark.unit
class TestLLMAnswerGenerator:
    """Tests for the LLM answer generator with grounding and fallback."""

    def test_generate_parses_chat_response(self) -> None:
        llm = Mock()
        llm.chat.return_value = ChatResponse(content="答案内容 [1]", model="mock")
        generator = LLMAnswerGenerator(llm=llm)
        answer = generator.generate("问题", _chunks())

        assert answer.content == "答案内容 [1]"
        assert answer.confidence == 0.9
        assert answer.refusal_reason is None

        # Prompt must contain system + user messages with numbered materials.
        messages = llm.chat.call_args.args[0]
        assert len(messages) == 2
        assert isinstance(messages[0], Message)
        assert messages[0].role == "system"
        assert messages[1].role == "user"
        assert "[1]" in messages[1].content
        assert "Azure OpenAI" in messages[1].content

    def test_generate_accepts_plain_str_response(self) -> None:
        llm = Mock()
        llm.chat.return_value = "字符串答案 [1]"
        generator = LLMAnswerGenerator(llm=llm)
        answer = generator.generate("问题", _chunks())

        assert "字符串答案" in answer.content

    def test_out_of_range_citations_stripped(self) -> None:
        llm = Mock()
        llm.chat.return_value = ChatResponse(
            content="引用越界 [99] 合法 [1]", model="mock"
        )
        generator = LLMAnswerGenerator(llm=llm)
        answer = generator.generate("问题", _chunks())

        assert "[99]" not in answer.content
        assert "[1]" in answer.content

    def test_zero_index_citation_stripped(self) -> None:
        llm = Mock()
        llm.chat.return_value = ChatResponse(content="编号 [0] 无效 [2] 有效", model="mock")
        generator = LLMAnswerGenerator(llm=llm)
        answer = generator.generate("问题", _chunks())

        assert "[0]" not in answer.content
        assert "[2]" in answer.content

    def test_no_valid_citations_falls_back_to_extractive(self) -> None:
        llm = Mock()
        llm.chat.return_value = ChatResponse(content="完全没有引用标记", model="mock")
        generator = LLMAnswerGenerator(llm=llm)
        answer = generator.generate("问题", _chunks())

        # Degraded to extractive: extractive phrasing + [1] marker present.
        assert "针对「问题」" in answer.content
        assert "[1]" in answer.content

    def test_llm_raise_falls_back_to_extractive(self) -> None:
        llm = Mock()
        llm.chat.side_effect = RuntimeError("API down")
        generator = LLMAnswerGenerator(llm=llm)
        answer = generator.generate("问题", _chunks())

        assert "针对「问题」" in answer.content

    def test_llm_factory_failure_falls_back_silently(self) -> None:
        generator = LLMAnswerGenerator()
        # LLMFactory.create would fail on settings without an llm section;
        # _get_llm must swallow the error and fall back to extractive.
        answer = generator.generate("问题", _chunks())

        assert "针对「问题」" in answer.content

    def test_no_chunks_returns_refusal_without_calling_llm(self) -> None:
        llm = Mock()
        generator = LLMAnswerGenerator(llm=llm)
        answer = generator.generate("问题", [])

        assert answer.refusal_reason == "no_retrieval_results"
        assert answer.confidence == 0.0
        llm.chat.assert_not_called()

    def test_low_confidence_attaches_notice(self) -> None:
        chunks = [
            RetrievalResult(
                chunk_id="c1", score=0.2, text="内容甲。",
                metadata={"source_path": "a.pdf"},
            )
        ]
        llm = Mock()
        llm.chat.return_value = ChatResponse(content="答案 [1]", model="mock")
        generator = LLMAnswerGenerator(llm=llm, confidence_threshold=0.5)
        answer = generator.generate("问题", chunks)

        assert answer.refusal_reason == "low_confidence"
        assert "置信度较低" in answer.content
