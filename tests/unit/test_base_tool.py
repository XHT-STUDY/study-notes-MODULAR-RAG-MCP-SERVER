"""Tests for the Phase 6 tool abstraction (BaseTool / FunctionTool)."""

from __future__ import annotations

import pytest

from src.core.agent.base_tool import BaseTool, FunctionTool, ToolResult

SCHEMA = {
    "type": "object",
    "properties": {"query": {"type": "string"}},
}


class TestToolResult:
    def test_defaults(self) -> None:
        result = ToolResult(content="ok")
        assert result.content == "ok"
        assert result.is_error is False
        assert result.metadata is None


class TestFunctionTool:
    def test_properties(self) -> None:
        tool = FunctionTool(
            name="query_knowledge_hub",
            description="检索知识库",
            input_schema=SCHEMA,
            func=lambda args: ToolResult(content="ok"),
        )
        assert tool.name == "query_knowledge_hub"
        assert tool.description == "检索知识库"
        assert tool.input_schema == SCHEMA
        assert isinstance(tool, BaseTool)

    @pytest.mark.asyncio
    async def test_call_async_callable(self) -> None:
        async def _handler(arguments: dict) -> ToolResult:
            return ToolResult(content=f"got {arguments['query']}")

        tool = FunctionTool("x", "d", SCHEMA, _handler)
        result = await tool.call({"query": "你好"})
        assert result.content == "got 你好"
        assert result.is_error is False

    @pytest.mark.asyncio
    async def test_call_sync_callable(self) -> None:
        tool = FunctionTool(
            "x", "d", SCHEMA, lambda args: ToolResult(content="sync ok")
        )
        result = await tool.call({})
        assert result.content == "sync ok"


class TestBaseToolAbstract:
    def test_cannot_instantiate(self) -> None:
        with pytest.raises(TypeError):
            BaseTool()  # type: ignore[abstract]
