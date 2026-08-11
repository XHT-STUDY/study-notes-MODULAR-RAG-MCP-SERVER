"""Tests for the Phase 6 query router (rule / LLM / factory)."""

from __future__ import annotations

import pytest

from src.core.agent.query_router import (
    LLMRouter,
    NullRouter,
    RouteResult,
    RouterFactory,
    RuleRouter,
)
from src.core.settings import RouterSettings
from src.libs.llm.base_llm import ChatResponse


class StubLLM:
    """Sync chat stub — asyncio.to_thread treats it as a blocking call."""

    def __init__(self, reply: str, raise_error: bool = False) -> None:
        self._reply = reply
        self._raise_error = raise_error
        self.last_messages = None

    def chat(self, messages, trace=None, **kwargs) -> ChatResponse:
        self.last_messages = messages
        if self._raise_error:
            raise RuntimeError("llm down")
        return ChatResponse(content=self._reply, model="stub")


class TestRuleRouter:
    @pytest.mark.asyncio
    async def test_collection_keyword_routes_to_tool(self) -> None:
        result = await RuleRouter().route("列出所有集合")
        assert result.target == "tool"
        assert result.tool_name == "list_collections"

    @pytest.mark.asyncio
    async def test_summary_keyword_routes_to_tool(self) -> None:
        result = await RuleRouter().route("总结一下这份文档")
        assert result.target == "tool"
        assert result.tool_name == "get_document_summary"

    @pytest.mark.asyncio
    async def test_compare_keyword_routes_to_multi_hop(self) -> None:
        result = await RuleRouter().route("对比 BM25 和向量检索")
        assert result.target == "multi_hop"
        assert result.tool_name is None

    @pytest.mark.asyncio
    async def test_default_routes_to_direct_rag(self) -> None:
        result = await RuleRouter().route("RAG 是什么")
        assert result.target == "direct_rag"


class TestNullRouter:
    @pytest.mark.asyncio
    async def test_always_direct(self) -> None:
        result = await NullRouter().route("随便什么")
        assert result.is_direct is True
        assert result.target == "direct_rag"


class TestLLMRouter:
    @pytest.mark.asyncio
    async def test_tool_classification(self) -> None:
        router = LLMRouter(StubLLM("tool:list_collections"))
        result = await router.route("有哪些集合")
        assert result.target == "tool"
        assert result.tool_name == "list_collections"

    @pytest.mark.asyncio
    async def test_multi_hop_classification(self) -> None:
        router = LLMRouter(StubLLM("multi_hop"))
        result = await router.route("A 与 B 有什么区别")
        assert result.target == "multi_hop"

    @pytest.mark.asyncio
    async def test_direct_classification(self) -> None:
        router = LLMRouter(StubLLM("direct_rag"))
        result = await router.route("RAG 是什么")
        assert result.target == "direct_rag"

    @pytest.mark.asyncio
    async def test_error_falls_back_to_direct(self) -> None:
        router = LLMRouter(StubLLM("anything", raise_error=True))
        result = await router.route("问题")
        assert result.target == "direct_rag"
        assert "回退" in result.reason


class TestRouterFactory:
    def test_disabled_returns_null_router(self) -> None:
        router = RouterFactory.create(RouterSettings(enabled=False))
        assert isinstance(router, NullRouter)

    def test_none_settings_returns_null_router(self) -> None:
        router = RouterFactory.create(None)
        assert isinstance(router, NullRouter)

    def test_rule_provider_returns_rule_router(self) -> None:
        router = RouterFactory.create(RouterSettings(enabled=True, provider="rule"))
        assert isinstance(router, RuleRouter)

    def test_llm_provider_without_llm_falls_back_to_rule(self) -> None:
        router = RouterFactory.create(RouterSettings(enabled=True, provider="llm"))
        assert isinstance(router, RuleRouter)

    def test_llm_provider_with_llm_returns_llm_router(self) -> None:
        router = RouterFactory.create(
            RouterSettings(enabled=True, provider="llm"), llm=StubLLM("direct_rag")
        )
        assert isinstance(router, LLMRouter)


class TestRouteResult:
    def test_defaults(self) -> None:
        result = RouteResult()
        assert result.target == "direct_rag"
        assert result.tool_name is None
        assert result.is_direct is True
