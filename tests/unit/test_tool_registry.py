"""Tests for the Phase 6 ToolRegistry whitelist and error handling."""

from __future__ import annotations

import pytest

from src.core.agent.base_tool import FunctionTool, ToolResult
from src.core.agent.tool_registry import ToolRegistry


def _tool(name: str) -> FunctionTool:
    return FunctionTool(
        name=name,
        description=f"{name} 的描述",
        input_schema={"type": "object", "properties": {}},
        func=lambda args, n=name: ToolResult(content=f"{n} ok"),
    )


class TestRegistryBasics:
    def test_register_and_get(self) -> None:
        registry = ToolRegistry([_tool("a"), _tool("b")])
        assert registry.get("a") is not None
        assert registry.get("b") is not None
        assert registry.get("c") is None

    def test_describe_shape(self) -> None:
        registry = ToolRegistry([_tool("query_knowledge_hub")])
        described = registry.describe()
        assert described == [
            {
                "name": "query_knowledge_hub",
                "description": "query_knowledge_hub 的描述",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                },
            }
        ]

    def test_no_allowed_means_all_available(self) -> None:
        registry = ToolRegistry([_tool("a"), _tool("b")])
        assert registry.is_allowed("a") is True
        assert registry.is_allowed("b") is True


class TestWhitelist:
    def test_allowed_subset_describes_only_allowed(self) -> None:
        registry = ToolRegistry(
            [_tool("query_knowledge_hub"), _tool("list_collections")],
            allowed=["query_knowledge_hub"],
        )
        names = [t["name"] for t in registry.describe()]
        assert names == ["query_knowledge_hub"]

    def test_allowed_subset_blocks_others(self) -> None:
        registry = ToolRegistry(
            [_tool("query_knowledge_hub"), _tool("list_collections")],
            allowed=["query_knowledge_hub"],
        )
        assert registry.is_allowed("query_knowledge_hub") is True
        assert registry.is_allowed("list_collections") is False

    @pytest.mark.asyncio
    async def test_call_outside_whitelist_returns_error(self) -> None:
        registry = ToolRegistry(
            [_tool("a"), _tool("b")], allowed=["a"]
        )
        result = await registry.call("b", {})
        assert result.is_error is True
        assert "不在白名单中" in result.content


class TestCallErrors:
    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error(self) -> None:
        registry = ToolRegistry([])
        result = await registry.call("does_not_exist", {})
        assert result.is_error is True
        assert "未知工具" in result.content

    @pytest.mark.asyncio
    async def test_tool_exception_converted_to_error(self) -> None:
        def _boom(arguments: dict) -> ToolResult:
            raise RuntimeError("boom")

        registry = ToolRegistry([FunctionTool("a", "d", {}, _boom)])
        result = await registry.call("a", {})
        assert result.is_error is True
        assert "执行失败" in result.content
        assert "boom" in result.content

    @pytest.mark.asyncio
    async def test_allowed_call_succeeds(self) -> None:
        registry = ToolRegistry([_tool("a")], allowed=["a"])
        result = await registry.call("a", {})
        assert result.is_error is False
        assert result.content == "a ok"
