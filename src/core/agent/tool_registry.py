"""Tool registry for the Agentic RAG layer (Phase 6).

Holds the tools the agent may invoke and enforces the ``agent.tools``
whitelist: tools outside the whitelist are hidden from the model's
descriptions and rejected with an error :class:`ToolResult` when called.
"""

from __future__ import annotations

from typing import Any

from src.core.agent.base_tool import BaseTool, ToolResult


class ToolRegistry:
    """Named registry of tools with an optional invocation whitelist.

    When ``allowed`` is ``None`` every registered tool is available; otherwise
    both :meth:`describe` and :meth:`call` are restricted to it. An unknown
    name or a tool outside the whitelist yields an error :class:`ToolResult`
    instead of raising, so the loop can feed the message back to the model.
    """

    def __init__(
        self,
        tools: list[BaseTool] | None = None,
        allowed: list[str] | None = None,
    ) -> None:
        self._tools: dict[str, BaseTool] = {}
        self._allowed: set[str] | None = set(allowed) if allowed else None
        for tool in tools or []:
            self.register(tool)

    def register(self, tool: BaseTool) -> None:
        """Register (or replace) a tool by name."""
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool | None:
        """Return the registered tool, or ``None`` when unknown."""
        return self._tools.get(name)

    def is_allowed(self, name: str) -> bool:
        """True when the tool is registered and inside the whitelist."""
        if self._allowed is None:
            return name in self._tools
        return name in self._allowed and name in self._tools

    def describe(self) -> list[dict[str, Any]]:
        """Tool descriptions the model may see — whitelisted tools only.

        Shape matches what :func:`build_tools_system_prompt` expects:
        ``[{"name", "description", "input_schema"}]``.
        """
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_schema,
            }
            for tool in self._tools.values()
            if self.is_allowed(tool.name)
        ]

    async def call(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        """Invoke a tool by name, returning an error result on any failure."""
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(content=f"未知工具: {name}", is_error=True)
        if self._allowed is not None and name not in self._allowed:
            return ToolResult(
                content=f"工具 {name} 不在白名单中，不能调用。", is_error=True
            )
        try:
            return await tool.call(arguments or {})
        except Exception as exc:  # surfaced to the model as text, not fatal
            return ToolResult(
                content=f"工具 {name} 执行失败: {exc}", is_error=True
            )
