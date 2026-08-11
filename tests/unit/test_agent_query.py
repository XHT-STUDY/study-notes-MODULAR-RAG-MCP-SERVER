"""Tests for the Phase 6 agent_query MCP tool (degradation + assembly)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from mcp import types

from src.core.agent.base_agent import AgentResult
from src.core.response.citation_generator import Citation
from src.core.settings import AgentSettings
from src.mcp_server.protocol_handler import ProtocolHandler
from src.mcp_server.tools import agent_query


def _text_of(result: types.CallToolResult) -> str:
    return "\n".join(getattr(b, "text", "") or "" for b in result.content)


def _disabled_settings() -> SimpleNamespace:
    return SimpleNamespace(agent=AgentSettings(enabled=False))


def _enabled_settings(*, tools: list[str] | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        agent=AgentSettings(
            enabled=True, strategy="react", tools=tools or ["list_collections"]
        )
    )


def _fake_protocol_handler() -> ProtocolHandler:
    """A minimal handler exposing the tools dict (no real backends)."""

    async def _noop(**kwargs):
        return types.CallToolResult(
            content=[types.TextContent(type="text", text="ok")], isError=False
        )

    ph = ProtocolHandler(server_name="test", server_version="1")
    ph.register_tool(
        "list_collections",
        "列出集合",
        {"type": "object", "properties": {}},
        _noop,
    )
    ph.register_tool(
        "query_knowledge_hub",
        "检索知识库",
        {"type": "object", "properties": {}},
        _noop,
    )
    return ph


class StubAgent:
    """Fake agent returning a canned AgentResult."""

    is_enabled = True

    def __init__(self, result: AgentResult) -> None:
        self._result = result

    async def run(self, query: str, trace=None) -> AgentResult:
        return self._result


@pytest.fixture(autouse=True)
def _no_trace_collect(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent writing to logs/traces.jsonl during tests."""

    monkeypatch.setattr(
        agent_query.TraceCollector, "collect", staticmethod(lambda trace: None)
    )


class TestDisabledDegradation:
    @pytest.mark.asyncio
    async def test_disabled_delegates_to_query_knowledge_hub(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict = {}

        async def fake_handler(query, top_k=5, collection=None):
            captured["query"] = query
            captured["top_k"] = top_k
            captured["collection"] = collection
            return types.CallToolResult(
                content=[types.TextContent(type="text", text=f"直通: {query}")],
                isError=False,
            )

        monkeypatch.setattr(agent_query, "query_knowledge_hub_handler", fake_handler)
        tool = agent_query.AgentQueryTool(settings=_disabled_settings())
        result = await tool.execute(query="RAG 是什么", top_k=7, collection="docs")

        assert result.isError is False
        assert captured == {"query": "RAG 是什么", "top_k": 7, "collection": "docs"}
        assert _text_of(result) == "直通: RAG 是什么"

    @pytest.mark.asyncio
    async def test_empty_query_errors(self) -> None:
        tool = agent_query.AgentQueryTool(settings=_disabled_settings())
        result = await tool.execute(query="   ")
        assert result.isError is True
        assert "参数错误" in _text_of(result)


class TestRegistry:
    def test_excludes_agent_query_and_enforces_whitelist(self) -> None:
        tool = agent_query.AgentQueryTool(
            settings=_enabled_settings(
                tools=["agent_query", "query_knowledge_hub", "list_collections"]
            )
        )
        registry = tool._build_registry(_fake_protocol_handler())

        assert registry.get("agent_query") is None  # 防递归
        assert registry.get("query_knowledge_hub") is not None
        assert registry.get("list_collections") is not None
        # 未注册 / 白名单外的工具不可调用
        assert registry.is_allowed("get_document_summary") is False

    def test_call_through_protocol_handler(self) -> None:
        tool = agent_query.AgentQueryTool(settings=_enabled_settings())
        ph = _fake_protocol_handler()
        registry = tool._build_registry(ph)

        async def _run() -> None:
            result = await registry.call("list_collections", {})
            assert result.is_error is False
            assert "ok" in result.content

        import asyncio

        asyncio.run(_run())


class TestEnabledAssembly:
    @pytest.mark.asyncio
    async def test_enabled_assembles_mcp_response(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        citation = Citation(
            index=1,
            chunk_id="c1",
            source="doc.pdf",
            score=0.9,
            text_snippet="片段",
        )
        stub = StubAgent(
            AgentResult(
                strategy="react",
                content="答案 [1]",
                citations=[citation],
                confidence=0.9,
                intermediate_steps=[{"kind": "tool_call", "tool": "query_knowledge_hub"}],
            )
        )
        create_called: dict = {}

        class _FakeFactory:
            @classmethod
            def create(cls, settings, **kwargs):
                create_called["settings"] = settings
                create_called["kwargs"] = kwargs
                return stub

        monkeypatch.setattr(agent_query, "AgentFactory", _FakeFactory)
        tool = agent_query.AgentQueryTool(settings=_enabled_settings())
        result = await tool.execute(
            query="问题", session_id="s1", protocol_handler=_fake_protocol_handler()
        )

        assert result.isError is False
        assert "答案 [1]" in _text_of(result)
        assert "registry" in create_called["kwargs"]
        assert "direct_retriever" in create_called["kwargs"]

    @pytest.mark.asyncio
    async def test_enabled_refusal_is_not_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        stub = StubAgent(
            AgentResult(
                strategy="react",
                content="直通内容",
                refusal_reason="llm_unavailable",
            )
        )

        class _FakeFactory:
            @classmethod
            def create(cls, settings, **kwargs):
                return stub

        monkeypatch.setattr(agent_query, "AgentFactory", _FakeFactory)
        tool = agent_query.AgentQueryTool(settings=_enabled_settings())
        result = await tool.execute(query="问题", protocol_handler=_fake_protocol_handler())

        assert result.isError is False
        assert "直通内容" in _text_of(result)

    @pytest.mark.asyncio
    async def test_enabled_without_protocol_handler_errors(self) -> None:
        tool = agent_query.AgentQueryTool(settings=_enabled_settings())
        result = await tool.execute(query="问题")
        assert result.isError is True
        assert "内部错误" in _text_of(result)


class TestResultMapping:
    def test_agent_result_to_mcp_maps_fields(self) -> None:
        citation = Citation(
            index=1, chunk_id="c1", source="doc.pdf", score=0.9, text_snippet="片段"
        )
        result = AgentResult(
            strategy="react",
            content="答案",
            citations=[citation],
            confidence=0.9,
            intermediate_steps=[{"kind": "tool_call"}],
        )
        response = agent_query._agent_result_to_mcp(result)

        assert response.content == "答案"
        assert response.metadata["strategy"] == "react"
        assert response.metadata["intermediate_steps"] == [{"kind": "tool_call"}]
        assert response.confidence == 0.9
        assert response.citations[0].index == 1
        assert response.is_empty is False
        assert "refusal_reason" not in response.metadata

    def test_agent_result_to_mcp_includes_refusal(self) -> None:
        result = AgentResult(
            strategy="react", content="", refusal_reason="llm_unavailable", is_empty=True
        )
        response = agent_query._agent_result_to_mcp(result)

        assert response.refusal_reason == "llm_unavailable"
        assert response.metadata["refusal_reason"] == "llm_unavailable"
        assert response.is_empty is True
