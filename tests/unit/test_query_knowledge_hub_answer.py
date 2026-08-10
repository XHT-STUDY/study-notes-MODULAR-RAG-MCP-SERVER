"""Unit tests for answer generation integration in QueryKnowledgeHubTool."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.core.response.response_builder import MCPToolResponse
from src.core.settings import AnswerGeneratorSettings
from src.core.trace import TraceCollector
from src.core.types import RetrievalResult
from src.libs.answer_generator import Answer
from src.mcp_server.tools.query_knowledge_hub import QueryKnowledgeHubTool


def _chunks() -> list[RetrievalResult]:
    return [
        RetrievalResult(
            chunk_id="c1", score=0.9,
            text="Azure OpenAI 是微软提供的云服务。",
            metadata={"source_path": "a.pdf"},
        )
    ]


def _disable_trace_collect(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep unit tests from appending to logs/traces.jsonl."""
    monkeypatch.setattr(TraceCollector, "collect", lambda self, trace: None)


@pytest.mark.unit
class TestQueryKnowledgeHubAnswer:
    """Tests for wiring the answer generator into query_knowledge_hub."""

    @pytest.mark.asyncio
    async def test_execute_attaches_answer(self, monkeypatch: pytest.MonkeyPatch) -> None:
        generator = Mock()
        generator.generate.return_value = Answer(content="测试答案 [1]", confidence=0.9)
        tool = QueryKnowledgeHubTool(answer_generator=generator)
        results = _chunks()
        monkeypatch.setattr(tool, "_ensure_initialized", lambda c: None)
        monkeypatch.setattr(tool, "_perform_search", lambda q, k, t: results)
        _disable_trace_collect(monkeypatch)

        response = await tool.execute(query="问题", top_k=3)

        generator.generate.assert_called_once()
        assert response.answer == "测试答案 [1]"
        assert response.confidence == 0.9
        assert "## 回答" in response.content
        assert "测试答案" in response.content

    @pytest.mark.asyncio
    async def test_execute_disabled_skips_generation(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        tool = QueryKnowledgeHubTool(
            settings=SimpleNamespace(
                answer_generator=AnswerGeneratorSettings(
                    enabled=False, provider="extractive"
                )
            )
        )
        monkeypatch.setattr(tool, "_ensure_initialized", lambda c: None)
        monkeypatch.setattr(tool, "_perform_search", lambda q, k, t: _chunks())
        _disable_trace_collect(monkeypatch)

        response = await tool.execute(query="问题", top_k=3)

        assert response.answer is None
        assert response.confidence is None
        assert "## 回答" not in response.content

    @pytest.mark.asyncio
    async def test_empty_results_skips_generation(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        generator = Mock()
        tool = QueryKnowledgeHubTool(answer_generator=generator)
        monkeypatch.setattr(tool, "_ensure_initialized", lambda c: None)
        monkeypatch.setattr(tool, "_perform_search", lambda q, k, t: [])
        _disable_trace_collect(monkeypatch)

        response = await tool.execute(query="问题", top_k=3)

        generator.generate.assert_not_called()
        assert response.is_empty is True
        assert response.answer is None

    def test_get_answer_generator_disabled_returns_none(self) -> None:
        tool = QueryKnowledgeHubTool(
            settings=SimpleNamespace(
                answer_generator=AnswerGeneratorSettings(
                    enabled=False, provider="extractive"
                )
            )
        )
        assert tool._get_answer_generator() is None

    def test_attach_answer_prepends_content(self) -> None:
        tool = QueryKnowledgeHubTool()
        response = MCPToolResponse(content="## 检索结果\n内容")
        answer = Answer(content="答案 [1]", confidence=0.8)

        tool._attach_answer(response, answer)

        assert response.content.startswith("## 回答")
        assert "## 检索结果" in response.content
        assert response.answer == "答案 [1]"
        assert response.confidence == 0.8

    def test_attach_answer_refusal_marks_metadata(self) -> None:
        tool = QueryKnowledgeHubTool()
        response = MCPToolResponse(content="x")
        answer = Answer(content="答案", confidence=0.2, refusal_reason="low_confidence")

        tool._attach_answer(response, answer)

        assert response.metadata["answer_refused"] is True
        assert "error" not in response.metadata
        assert response.refusal_reason == "low_confidence"

    def test_attach_answer_empty_content_is_noop(self) -> None:
        tool = QueryKnowledgeHubTool()
        response = MCPToolResponse(content="x")
        answer = Answer(content="", confidence=0.0)

        tool._attach_answer(response, answer)

        assert response.content == "x"
        assert response.answer is None
