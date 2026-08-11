"""MCP Tool: agent_query

Agentic RAG query (Phase 6). When ``agent.enabled=false`` (the default) the
tool short-circuits to :func:`query_knowledge_hub_handler` — byte-identical to
the plain retrieval tool, so it is always usable and existing callers see zero
behaviour change. When enabled, it runs the configured agent strategy
(react / plan_and_execute / self_ask) with the shared loop, tool whitelist,
conversation memory, router and retrieval reflection.

The ``ToolDefinition`` → callable adaptation lives here (this file), keeping
``src/core/agent`` free of the MCP SDK: :func:`AgentQueryTool._invoke` wraps
``protocol_handler.execute_tool`` into a :class:`FunctionTool`.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from mcp import types

from src.core.agent import AgentFactory
from src.core.agent.base_agent import AgentResult
from src.core.agent.base_tool import FunctionTool, ToolResult
from src.core.agent.tool_registry import ToolRegistry
from src.core.response.response_builder import MCPToolResponse
from src.core.settings import Settings, load_settings
from src.core.trace import TraceCollector, TraceContext
from src.mcp_server.tools.query_knowledge_hub import (
    get_tool_instance,
    query_knowledge_hub_handler,
)

if TYPE_CHECKING:
    from src.mcp_server.protocol_handler import ProtocolHandler

logger = logging.getLogger(__name__)


# Tool metadata
TOOL_NAME = "agent_query"
TOOL_DESCRIPTION = """Agentic RAG query: runs an agent loop (tool calls + retrieval + optional
memory / reflection) to answer the query. When the agent is disabled this
degrades to plain hybrid retrieval, identical to query_knowledge_hub.

Parameters:
- query: Your search question or keywords
- top_k: Maximum number of results (default: 5)
- collection: Limit search to a specific document collection
- session_id: Optional conversation id for memory continuity
"""

TOOL_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "The search query or question.",
        },
        "top_k": {
            "type": "integer",
            "description": "Maximum number of results.",
            "default": 5,
            "minimum": 1,
            "maximum": 20,
        },
        "collection": {
            "type": "string",
            "description": "Optional collection name to limit the search scope.",
        },
        "session_id": {
            "type": "string",
            "description": "Optional conversation id for memory continuity.",
        },
    },
    "required": ["query"],
}


def _calltoolresult_to_text(result: types.CallToolResult) -> str:
    """Flatten a CallToolResult's content blocks into plain text."""
    parts: list[str] = []
    for block in result.content:
        text = getattr(block, "text", None)
        if text:
            parts.append(str(text))
    return "\n".join(parts)


def _agent_result_to_mcp(result: AgentResult) -> MCPToolResponse:
    """Assemble an AgentResult into an MCPToolResponse (None fields omitted)."""
    metadata: dict[str, Any] = {
        "strategy": result.strategy,
        "intermediate_steps": result.intermediate_steps,
    }
    kwargs: dict[str, Any] = {
        "content": result.content,
        "citations": list(result.citations),
        "metadata": metadata,
        "is_empty": result.is_empty,
    }
    if result.answer is not None:
        kwargs["answer"] = result.answer
    if result.confidence is not None:
        kwargs["confidence"] = result.confidence
    if result.refusal_reason is not None:
        kwargs["refusal_reason"] = result.refusal_reason
        metadata["refusal_reason"] = result.refusal_reason
    return MCPToolResponse(**kwargs)


def _mcp_response(response: MCPToolResponse) -> types.CallToolResult:
    """Mirror query_knowledge_hub's CallToolResult mapping."""
    return types.CallToolResult(
        content=response.to_mcp_content(),
        isError=response.is_empty and "error" in response.metadata,
    )


def _error_result(message: str) -> types.CallToolResult:
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=message)],
        isError=True,
    )


class AgentQueryTool:
    """MCP Tool for agentic RAG queries.

    Lazy settings; the protocol handler is passed in on each execute so the
    tool whitelist always reflects the tools actually registered.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        direct_tool: Any = None,
    ) -> None:
        self._settings = settings
        self._direct_tool = direct_tool

    @property
    def settings(self) -> Settings:
        if self._settings is None:
            self._settings = load_settings()
        return self._settings

    def _agent_settings(self):
        return getattr(self.settings, "agent", None)

    def _agent_enabled(self) -> bool:
        ag = self._agent_settings()
        return bool(ag is not None and ag.enabled)

    def _build_registry(self, protocol_handler: Any) -> ToolRegistry:
        """Wrap whitelisted protocol tools into a ToolRegistry.

        ``agent_query`` itself is excluded to prevent recursion.
        """
        ag = self._agent_settings()
        allowed = list(ag.tools) if ag is not None and ag.tools else []
        registry = ToolRegistry(tools=[], allowed=allowed)
        for name in allowed:
            if name == TOOL_NAME:  # 防递归
                continue
            definition = protocol_handler.tools.get(name)
            if definition is None:
                continue
            registry.register(
                FunctionTool(
                    name=name,
                    description=definition.description,
                    input_schema=definition.input_schema,
                    func=self._invoke(protocol_handler, name),
                )
            )
        return registry

    @staticmethod
    def _invoke(protocol_handler: Any, name: str):
        async def _call(arguments: dict[str, Any]) -> ToolResult:
            result = await protocol_handler.execute_tool(name, arguments or {})
            return ToolResult(
                content=_calltoolresult_to_text(result),
                is_error=bool(result.isError),
            )

        return _call

    def _direct_retriever(self, query: str, top_k: int, collection: str | None) -> Any:
        """Passthrough used when the agent degrades (no LLM / disabled loop)."""
        tool = self._direct_tool or get_tool_instance()
        return tool.execute(query=query, top_k=top_k, collection=collection)

    async def execute(
        self,
        query: str,
        top_k: int = 5,
        collection: str | None = None,
        session_id: str | None = None,
        protocol_handler: Any = None,
    ) -> types.CallToolResult:
        """Run the agent (or the passthrough retrieval when disabled)."""
        if not query or not query.strip():
            return _error_result("参数错误: 查询不能为空")

        # 禁用（默认）→ 直通检索：与 query_knowledge_hub 字节级等价，永远可用。
        if not self._agent_enabled():
            return await query_knowledge_hub_handler(
                query=query, top_k=top_k, collection=collection
            )

        trace = TraceContext(trace_type="agent")
        trace.metadata["query"] = query[:200]
        trace.metadata["top_k"] = top_k
        trace.metadata["collection"] = collection or "default"
        trace.metadata["session_id"] = session_id or "default"
        trace.metadata["source"] = "mcp"

        try:
            if protocol_handler is None:
                raise RuntimeError(
                    "protocol_handler is required when agent is enabled"
                )
            registry = self._build_registry(protocol_handler)

            def direct(q: str) -> Any:
                return self._direct_retriever(q, top_k, collection)

            agent = AgentFactory.create(
                self.settings,
                registry=registry,
                direct_retriever=direct,
            )
            result = await agent.run(query, trace)
            response = _agent_result_to_mcp(result)
            trace.metadata["strategy"] = result.strategy
            TraceCollector().collect(trace)
            return _mcp_response(response)
        except Exception as exc:
            logger.exception("agent_query failed: %s", exc)
            TraceCollector().collect(trace)
            return _error_result("内部错误: agent 执行失败")


def register_tool(protocol_handler: ProtocolHandler) -> None:
    """Register the agent_query tool with the protocol handler."""
    tool = AgentQueryTool()

    async def handler(
        query: str,
        top_k: int = 5,
        collection: str | None = None,
        session_id: str | None = None,
    ) -> types.CallToolResult:
        return await tool.execute(
            query=query,
            top_k=top_k,
            collection=collection,
            session_id=session_id,
            protocol_handler=protocol_handler,
        )

    protocol_handler.register_tool(
        name=TOOL_NAME,
        description=TOOL_DESCRIPTION,
        input_schema=TOOL_INPUT_SCHEMA,
        handler=handler,
    )
    logger.info("Registered MCP tool: %s", TOOL_NAME)
