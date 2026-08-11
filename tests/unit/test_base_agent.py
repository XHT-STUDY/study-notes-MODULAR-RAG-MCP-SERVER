"""Tests for the Phase 6 agent base classes (AgentResult / NoneAgent)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.core.agent.base_agent import AgentResult, BaseAgent, NoneAgent
from src.libs.answer_generator.base_answer_generator import Answer


class TestAgentResult:
    def test_defaults(self) -> None:
        result = AgentResult(strategy="react")
        assert result.content == ""
        assert result.answer is None
        assert result.intermediate_steps == []
        assert result.citations == []
        assert result.confidence == 0.0
        assert result.refusal_reason is None
        assert result.is_empty is False

    def test_holds_answer(self) -> None:
        answer = Answer(content="hi", confidence=0.9)
        result = AgentResult(strategy="react", answer=answer, content="hi")
        assert result.answer.content == "hi"
        assert result.answer.confidence == 0.9


class TestBaseAgentAbstract:
    def test_cannot_instantiate(self) -> None:
        with pytest.raises(TypeError):
            BaseAgent()  # type: ignore[abstract]


class TestNoneAgent:
    @pytest.mark.asyncio
    async def test_no_retriever_refuses(self) -> None:
        agent = NoneAgent()
        result = await agent.run("问题")
        assert result.is_empty is True
        assert result.refusal_reason == "agent disabled"
        assert result.content == ""

    @pytest.mark.asyncio
    async def test_is_enabled_false(self) -> None:
        assert NoneAgent().is_enabled is False

    @pytest.mark.asyncio
    async def test_delegates_to_sync_retriever(self) -> None:
        agent = NoneAgent(
            strategy="react",
            direct_retriever=lambda q: SimpleNamespace(content=f"直通: {q}"),
        )
        result = await agent.run("RAG 是什么")
        assert result.content == "直通: RAG 是什么"
        assert result.is_empty is False
        assert result.refusal_reason is None

    @pytest.mark.asyncio
    async def test_delegates_to_async_retriever(self) -> None:
        async def _retriever(q: str) -> SimpleNamespace:
            return SimpleNamespace(content=f"async: {q}", citations=["c1"])

        agent = NoneAgent(direct_retriever=_retriever)
        result = await agent.run("问题")
        assert result.content == "async: 问题"
        assert result.citations == ["c1"]
