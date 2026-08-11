"""Tests for the Phase 6 agent loop (RetrievalEngine + 循环基座 + 三策略).

All components are injected; ``load_settings`` is neutralised so the tests
never depend on the presence of ``config/settings.yaml`` (gitignored in CI).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.core.agent import agent_runner
from src.core.agent.agent_runner import (
    PlanAndExecuteAgent,
    ReActAgent,
    RetrievalEngineResult,
    SelfAskAgent,
)
from src.core.agent.base_tool import FunctionTool, ToolResult
from src.core.agent.query_router import NullRouter
from src.core.agent.reflection import RetrievalReflector
from src.core.agent.tool_registry import ToolRegistry
from src.core.trace import TraceContext
from src.core.types import RetrievalResult
from src.libs.llm.base_llm import BaseLLM, ChatResponse, Message, format_tool_call

QKH = "query_knowledge_hub"


@pytest.fixture(autouse=True)
def _no_settings_load(monkeypatch: pytest.MonkeyPatch) -> None:
    """Neutralise ``load_settings`` so no test touches the real config file."""

    monkeypatch.setattr(
        agent_runner, "load_settings", lambda: SimpleNamespace(agent=None)
    )


class StubLLM(BaseLLM):
    """Canned-response LLM; records every injected message list."""

    def __init__(self, responses: list[str], *, fill: str | None = None, raise_error: bool = False) -> None:
        self.responses = list(responses)
        self.fill = fill
        self.raise_error = raise_error
        self.calls: list[list[Message]] = []

    def chat(self, messages: list[Message], trace=None, **kwargs) -> ChatResponse:
        self.calls.append(list(messages))
        if self.raise_error:
            raise RuntimeError("stub llm failure")
        if self.responses:
            content = self.responses.pop(0)
        elif self.fill is not None:
            content = self.fill
        else:
            raise AssertionError("StubLLM 响应耗尽")
        return ChatResponse(content=content, model="stub")


class FakeEngine:
    """Async retrieval engine recording every search call."""

    def __init__(self, results: list[RetrievalResult], content: str = "检索到的内容") -> None:
        self.results = results
        self.content = content
        self.call_count = 0
        self.search_calls: list[dict] = []

    async def search(self, query, top_k=None, collection=None, trace=None):
        self.call_count += 1
        self.search_calls.append(
            {"query": query, "top_k": top_k, "collection": collection}
        )
        return RetrievalEngineResult(
            results=list(self.results),
            content=self.content,
            query=query,
            collection=collection or "default",
        )


class FakeMemory:
    """In-memory conversation memory recording adds."""

    def __init__(self, history: list[dict[str, str]] | None = None) -> None:
        self.history = history or []
        self.adds: list[tuple[str, str, str]] = []

    def recent(self, session_id: str, window_size: int = 10) -> list[dict[str, str]]:
        return self.history

    def add(self, session_id: str, role: str, content: str) -> None:
        self.adds.append((session_id, role, content))

    def clear(self, session_id: str) -> None:
        pass


def _result() -> RetrievalResult:
    return RetrievalResult(
        chunk_id="c1",
        score=0.9,
        text="RAG 是检索增强生成",
        metadata={"source_path": "doc.pdf"},
    )


def _qkh_tool() -> FunctionTool:
    async def _intercept(arguments: dict) -> ToolResult:
        return ToolResult(content="不应被调用（循环拦截检索工具）")

    return FunctionTool(
        name=QKH,
        description="检索知识库",
        input_schema={},
        func=_intercept,
    )


def _registry(allowed: tuple[str, ...] = (QKH,)) -> ToolRegistry:
    return ToolRegistry(tools=[_qkh_tool()], allowed=list(allowed))


def _agent(
    cls=ReActAgent,
    *,
    engine=None,
    stub=None,
    registry=None,
    memory=None,
    reflector=None,
    max_iterations: int = 5,
    direct_retriever=None,
) -> ReActAgent:
    return cls(
        llm=stub,
        registry=registry or _registry(),
        retrieval_engine=engine,
        memory=memory if memory is not None else FakeMemory(),
        router=NullRouter(),
        reflector=reflector,
        max_iterations=max_iterations,
        direct_retriever=direct_retriever,
    )


class TestReActFullLoop:
    @pytest.mark.asyncio
    async def test_full_loop_tool_then_final(self) -> None:
        engine = FakeEngine([_result()])
        stub = StubLLM(
            [
                format_tool_call(QKH, {"query": "RAG 是什么"}),
                "RAG 是检索增强生成 [1]",
            ]
        )
        agent = _agent(ReActAgent, engine=engine, stub=stub)
        result = await agent.run("RAG 是什么")

        assert result.strategy == "react"
        assert result.content == "RAG 是检索增强生成 [1]"
        assert result.refusal_reason is None
        assert result.is_empty is False
        assert engine.call_count == 1
        assert len(result.citations) == 1
        assert result.citations[0].index == 1
        assert result.citations[0].chunk_id == "c1"
        assert result.confidence == 0.9

    @pytest.mark.asyncio
    async def test_message_roundtrip(self) -> None:
        engine = FakeEngine([_result()])
        stub = StubLLM(
            [
                format_tool_call(QKH, {"query": "RAG 是什么"}),
                "最终答案",
            ]
        )
        agent = _agent(ReActAgent, engine=engine, stub=stub)
        await agent.run("RAG 是什么")

        assert len(stub.calls) >= 2
        last = stub.calls[-1]
        assert last[-2].role == "assistant"
        assert last[-2].tool_calls == [{"name": QKH, "arguments": {"query": "RAG 是什么"}}]
        assert last[-1].role == "tool"
        assert last[-1].tool_call_id == "t1"
        assert last[-1].content == engine.content

    @pytest.mark.asyncio
    async def test_whitelist_rejection_feeds_back(self) -> None:
        engine = FakeEngine([_result()])
        stub = StubLLM(
            [
                format_tool_call(QKH, {"query": "RAG 是什么"}),
                "最终答案",
            ]
        )
        agent = _agent(
            ReActAgent,
            engine=engine,
            stub=stub,
            registry=_registry(allowed=("list_collections",)),
        )
        result = await agent.run("RAG 是什么")

        assert result.content == "最终答案"
        assert engine.call_count == 0
        assert any(s["kind"] == "not_allowed" for s in result.intermediate_steps)
        assert "不在白名单" in stub.calls[1][-1].content

    @pytest.mark.asyncio
    async def test_max_iterations_exhausted(self) -> None:
        engine = FakeEngine([_result()])
        stub = StubLLM([], fill=format_tool_call(QKH, {"query": "RAG 是什么"}))
        agent = _agent(ReActAgent, engine=engine, stub=stub, max_iterations=2)
        result = await agent.run("RAG 是什么")

        assert result.refusal_reason == "agent_max_iterations_exceeded"
        assert result.content == engine.content
        assert result.is_empty is False
        assert engine.call_count == 2


class TestDegradation:
    @pytest.mark.asyncio
    async def test_llm_unavailable_degrades_to_direct(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def _raise(*args, **kwargs):
            raise RuntimeError("no llm")

        monkeypatch.setattr(agent_runner.LLMFactory, "create", staticmethod(_raise))
        agent = _agent(
            ReActAgent,
            direct_retriever=lambda q: SimpleNamespace(content=f"直通: {q}"),
        )
        result = await agent.run("RAG 是什么")

        assert result.content == "直通: RAG 是什么"
        assert result.refusal_reason == "llm_unavailable"
        assert result.is_empty is False

    @pytest.mark.asyncio
    async def test_llm_unavailable_no_retriever_refuses(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def _raise(*args, **kwargs):
            raise RuntimeError("no llm")

        monkeypatch.setattr(agent_runner.LLMFactory, "create", staticmethod(_raise))
        agent = _agent(ReActAgent)
        result = await agent.run("问题")

        assert result.is_empty is True
        assert result.refusal_reason == "llm_unavailable"

    @pytest.mark.asyncio
    async def test_llm_error_degrades(self) -> None:
        engine = FakeEngine([_result()])
        stub = StubLLM([], raise_error=True)
        agent = _agent(
            ReActAgent,
            engine=engine,
            stub=stub,
            direct_retriever=lambda q: SimpleNamespace(content="直通"),
        )
        result = await agent.run("问题")

        assert result.refusal_reason == "llm_error"
        assert result.content == "直通"


class TestReflection:
    @pytest.mark.asyncio
    async def test_reseek_on_insufficient_results(self) -> None:
        engine = FakeEngine([_result()])
        stub = StubLLM(
            [
                format_tool_call(QKH, {"query": "RAG 是什么"}),
                "最终答案",
            ]
        )
        reflector = RetrievalReflector(
            min_results=2, coverage_threshold=0.0, max_retrieval_rounds=2
        )
        agent = _agent(ReActAgent, engine=engine, stub=stub, reflector=reflector)
        result = await agent.run("RAG 是什么")

        assert engine.call_count == 3  # 初始 + 2 次重检
        reflections = [s for s in result.intermediate_steps if s["kind"] == "reflection"]
        assert len(reflections) == 2
        assert [r["round"] for r in reflections] == [1, 2]
        # 重检用的是改写后的查询（expanded_terms 拼接）
        assert engine.search_calls[1]["query"] != engine.search_calls[0]["query"]


class TestMemory:
    @pytest.mark.asyncio
    async def test_history_injected_and_result_recorded(self) -> None:
        engine = FakeEngine([_result()])
        memory = FakeMemory(
            history=[
                {"role": "user", "content": "历史问题"},
                {"role": "assistant", "content": "历史答案"},
            ]
        )
        stub = StubLLM(
            [
                format_tool_call(QKH, {"query": "RAG 是什么"}),
                "最终答案",
            ]
        )
        agent = _agent(ReActAgent, engine=engine, stub=stub, memory=memory)
        await agent.run("RAG 是什么")

        # 历史消息位于查询之前（第 0 条是 system）
        assert stub.calls[0][1].content == "历史问题"
        assert stub.calls[0][2].content == "历史答案"
        assert stub.calls[0][3].content == "RAG 是什么"
        # session_id 无 trace 时默认 "default"
        assert ("default", "user", "RAG 是什么") in memory.adds
        assert ("default", "assistant", "最终答案") in memory.adds


class TestStrategies:
    @pytest.mark.asyncio
    async def test_plan_and_execute_planning_and_prefix_strip(self) -> None:
        engine = FakeEngine([_result()])
        stub = StubLLM(
            [
                "先检索 RAG 概念",
                format_tool_call(QKH, {"query": "RAG 是什么"}),
                "Final Answer: 答案是检索增强生成",
            ]
        )
        agent = _agent(PlanAndExecuteAgent, engine=engine, stub=stub)
        result = await agent.run("RAG 是什么")

        assert result.strategy == "plan_and_execute"
        assert result.content == "答案是检索增强生成"
        # 规划消息在首次循环调用中已追加
        assert stub.calls[1][-1].role == "assistant"
        assert stub.calls[1][-1].content == "计划: 先检索 RAG 概念"

    @pytest.mark.asyncio
    async def test_self_ask_prefix_strip(self) -> None:
        engine = FakeEngine([_result()])
        stub = StubLLM(["Final Answer: 自问自答答案"])
        agent = _agent(SelfAskAgent, engine=engine, stub=stub)
        result = await agent.run("问题")

        assert result.strategy == "self_ask"
        assert result.content == "自问自答答案"
        assert engine.call_count == 0  # 直接回答，未触发检索


class TestTrace:
    @pytest.mark.asyncio
    async def test_records_agent_stages(self) -> None:
        engine = FakeEngine([_result()])
        memory = FakeMemory()
        stub = StubLLM(
            [
                format_tool_call(QKH, {"query": "RAG 是什么"}),
                "最终答案",
            ]
        )
        agent = _agent(ReActAgent, engine=engine, stub=stub, memory=memory)
        trace = TraceContext(trace_type="agent")
        trace.metadata["session_id"] = "s1"
        await agent.run("RAG 是什么", trace)

        data = trace.to_dict()
        assert data["trace_type"] == "agent"
        stage_names = [s["stage"] for s in data["stages"]]
        assert "agent_tool_call" in stage_names
        assert "agent_final" in stage_names
        # session_id 来自 trace.metadata
        assert ("s1", "user", "RAG 是什么") in memory.adds
        assert ("s1", "assistant", "最终答案") in memory.adds
