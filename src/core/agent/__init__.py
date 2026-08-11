"""Agentic RAG layer (Phase 6).

The agent package provides the ReAct-style agent loop across three strategies
(``react`` / ``plan_and_execute`` / ``self_ask``), the tool abstraction +
whitelist registry, query understanding / routing, conversation memory and
retrieval reflection.

Layering: this package depends only on ``src.core`` + ``src.libs`` — it never
imports ``src.mcp_server.*`` or the MCP SDK.  The ``ToolDefinition`` → callable
adaptation lives in ``src/mcp_server/tools/agent_query.py``.
"""

from __future__ import annotations

from typing import Any

from src.core.agent.agent_runner import (
    PlanAndExecuteAgent,
    ReActAgent,
    RetrievalEngine,
    RetrievalEngineResult,
    SelfAskAgent,
)
from src.core.agent.base_agent import AgentResult, BaseAgent, NoneAgent
from src.core.agent.base_tool import BaseTool, FunctionTool, ToolResult
from src.core.agent.memory import (
    ConversationMemory,
    MemoryFactory,
    NoneMemory,
    SQLiteMemory,
)
from src.core.agent.query_router import (
    LLMRouter,
    NullRouter,
    QueryRouter,
    RouteResult,
    RouterFactory,
    RuleRouter,
)
from src.core.agent.query_understanding import (
    QueryUnderstanding,
    RuleQueryUnderstanding,
)
from src.core.agent.reflection import ReflectionDecision, RetrievalReflector
from src.core.agent.tool_registry import ToolRegistry


class AgentFactory:
    """Builds an agent from settings, mirroring ``AnswerGeneratorFactory``.

    Three strategies are registered: ``react`` (full loop, default),
    ``plan_and_execute`` and ``self_ask`` (lighter variants sharing the same
    loop base).  When ``agent.enabled=false`` (or no agent block) the factory
    returns :class:`NoneAgent` — the passthrough that delegates to the injected
    ``direct_retriever`` when one is provided.
    """

    _PROVIDERS: dict[str, type[BaseAgent]] = {
        "react": ReActAgent,
        "plan_and_execute": PlanAndExecuteAgent,
        "self_ask": SelfAskAgent,
    }

    #: Reserved to mirror ``EvaluatorFactory`` / ``AnswerGeneratorFactory``.
    _LAZY_PROVIDERS: dict[str, Any] = {}

    @classmethod
    def register_provider(cls, name: str, provider_class: type[BaseAgent]) -> None:
        """Register (or replace) an agent strategy implementation."""
        if not issubclass(provider_class, BaseAgent):
            raise ValueError(
                f"Provider class {provider_class.__name__} must inherit from BaseAgent"
            )
        cls._PROVIDERS[name.lower()] = provider_class

    @classmethod
    def create(
        cls,
        settings: Any,
        **override_kwargs: Any,
    ) -> BaseAgent:
        """Create an agent based on configuration.

        Args:
            settings: Full ``Settings`` (with ``.agent``) or a bare
                ``AgentSettings`` object.
            **override_kwargs: Component overrides forwarded to the strategy
                (llm / registry / retrieval_engine / memory / router /
                reflector / query_understanding / direct_retriever / ...).

        Returns:
            A configured :class:`BaseAgent`.

        Raises:
            ValueError: If the strategy is unsupported.
            RuntimeError: If the strategy fails to instantiate.
        """
        if settings is None:
            return NoneAgent(
                strategy="react",
                direct_retriever=override_kwargs.get("direct_retriever"),
            )
        ag_settings = cls._extract_agent_settings(settings)
        if ag_settings is None or not ag_settings.enabled:
            strategy = (
                getattr(ag_settings, "strategy", "react")
                if ag_settings is not None
                else "react"
            )
            return NoneAgent(
                strategy=strategy,
                direct_retriever=override_kwargs.get("direct_retriever"),
            )
        provider_name = ag_settings.strategy.lower()
        provider_class = cls._PROVIDERS.get(provider_name)
        if provider_class is None:
            available = ", ".join(sorted(cls._PROVIDERS.keys())) or "none"
            raise ValueError(
                f"Unsupported agent strategy: '{provider_name}'. "
                f"Available strategies: {available}."
            )
        try:
            return provider_class(settings=settings, **override_kwargs)
        except Exception as exc:
            raise RuntimeError(
                f"Failed to instantiate agent strategy '{provider_name}': {exc}"
            ) from exc

    @staticmethod
    def _extract_agent_settings(settings: Any):
        """Accept full ``Settings`` or a bare ``AgentSettings``."""
        if hasattr(settings, "agent"):
            return settings.agent
        if hasattr(settings, "strategy") and hasattr(settings, "enabled"):
            return settings
        raise AttributeError("settings has no 'agent' attribute")

    @classmethod
    def list_providers(cls) -> list[str]:
        """List all registered strategy names (sorted)."""
        return sorted(cls._PROVIDERS.keys())


__all__ = [
    "AgentFactory",
    "AgentResult",
    "BaseAgent",
    "NoneAgent",
    "ReActAgent",
    "PlanAndExecuteAgent",
    "SelfAskAgent",
    "RetrievalEngine",
    "RetrievalEngineResult",
    "BaseTool",
    "FunctionTool",
    "ToolResult",
    "ToolRegistry",
    "QueryRouter",
    "RouteResult",
    "NullRouter",
    "RuleRouter",
    "LLMRouter",
    "RouterFactory",
    "QueryUnderstanding",
    "RuleQueryUnderstanding",
    "ConversationMemory",
    "NoneMemory",
    "SQLiteMemory",
    "MemoryFactory",
    "RetrievalReflector",
    "ReflectionDecision",
]
