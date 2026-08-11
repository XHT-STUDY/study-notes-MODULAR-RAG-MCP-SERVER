"""Tool abstraction for the Agentic RAG layer (Phase 6).

The agent loop calls tools through :class:`BaseTool`. :class:`FunctionTool`
wraps an injected async callable, keeping ``src/core/agent`` independent of
the MCP SDK: the ``ToolDefinition`` → callable adaptation lives only in
``src/mcp_server/tools/agent_query.py``.
"""

from __future__ import annotations

import inspect
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolResult:
    """Text result of a tool call, fed back to the model as a ``tool`` message.

    Attributes:
        content: The tool's textual output.
        is_error: When True the content describes a failure the model should
            correct (e.g. tool outside the whitelist, unknown tool, exception).
        metadata: Optional structured data (e.g. citation count) for tracing.
    """

    content: str
    is_error: bool = False
    metadata: dict[str, Any] | None = field(default=None)


class BaseTool(ABC):
    """Abstract tool contract for the agent loop."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool name (matches the JSON-RPC tool name)."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Short human-readable description for the model."""

    @property
    @abstractmethod
    def input_schema(self) -> dict[str, Any]:
        """JSON-schema ``properties`` map describing the arguments."""

    @abstractmethod
    async def call(self, arguments: dict[str, Any]) -> ToolResult:
        """Invoke the tool with parsed keyword arguments.

        Implementations should return a :class:`ToolResult` rather than raise;
        the registry additionally converts exceptions to error results so the
        loop never crashes on a failing tool.
        """


_AsyncCallable = Callable[
    [dict[str, Any]], ToolResult | Awaitable[ToolResult]
]


class FunctionTool(BaseTool):
    """Wrap an injected async callable into a :class:`BaseTool`.

    Args:
        name: Tool name.
        description: Tool description.
        input_schema: JSON-schema ``properties`` map.
        func: Callable receiving the parsed ``arguments`` dict and returning a
            :class:`ToolResult` (or an awaitable of one).
    """

    def __init__(
        self,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        func: _AsyncCallable,
    ) -> None:
        self._name = name
        self._description = description
        self._input_schema = input_schema
        self._func = func

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def input_schema(self) -> dict[str, Any]:
        return self._input_schema

    async def call(self, arguments: dict[str, Any]) -> ToolResult:
        result = self._func(arguments)
        if inspect.isawaitable(result):
            result = await result
        return result
