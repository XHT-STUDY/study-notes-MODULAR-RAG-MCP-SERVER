"""Agent base classes for the Agentic RAG layer (Phase 6).

Defines :class:`AgentResult` (the agent's contract back to the MCP layer),
the :class:`BaseAgent` ABC, and :class:`NoneAgent` — the degraded agent used
when ``agent.enabled=false``.  :class:`NoneAgent` delegates to an injected
direct retriever (the passthrough path) and refuses when none is available.
"""

from __future__ import annotations

import inspect
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from src.core.response.citation_generator import Citation
from src.libs.answer_generator.base_answer_generator import Answer


@dataclass
class AgentResult:
    """Result of one agent run, mirroring the MCP tool response shape.

    Attributes:
        strategy: Which strategy produced this result (react / plan_and_execute /
            self_ask), or the strategy name when degraded.
        content: The final answer text (empty when refused/disabled).
        answer: Optional :class:`Answer` from an answer generator.
        intermediate_steps: Ordered log of the loop's tool calls and decisions.
        citations: Structured citations backing the content.
        confidence: Confidence in [0, 1].
        refusal_reason: Set when the agent refuses (e.g. disabled / LLM down /
            max iterations exceeded).
        is_empty: True for degraded results (disabled / no LLM / refusal).
    """

    strategy: str
    content: str = ""
    answer: Answer | None = None
    intermediate_steps: list[dict[str, Any]] = field(default_factory=list)
    citations: list[Citation] = field(default_factory=list)
    confidence: float = 0.0
    refusal_reason: str | None = None
    is_empty: bool = False


class BaseAgent(ABC):
    """Abstract agent: one ``run`` per user query, optional trace."""

    #: Set to False by degraded implementations (e.g. NoneAgent).
    is_enabled: bool = True

    @abstractmethod
    async def run(self, query: str, trace: Any = None) -> AgentResult:
        """Execute the agent loop and return an :class:`AgentResult`."""


class NoneAgent(BaseAgent):
    """Degraded agent returned when ``agent.enabled=false``.

    Runs the injected ``direct_retriever`` (the passthrough path, byte-identical
    to ``query_knowledge_hub``) when present; otherwise refuses with
    ``agent disabled``.
    """

    is_enabled = False

    def __init__(
        self,
        strategy: str = "react",
        direct_retriever: Callable[..., Any] | None = None,
    ) -> None:
        self.strategy = strategy
        self._direct_retriever = direct_retriever

    async def run(self, query: str, trace: Any = None) -> AgentResult:
        if self._direct_retriever is None:
            return AgentResult(
                strategy=self.strategy,
                content="",
                refusal_reason="agent disabled",
                is_empty=True,
            )
        result = self._direct_retriever(query)
        if inspect.isawaitable(result):
            result = await result
        # The direct retriever is injected from the MCP layer; only the .content
        # (and optional .citations) contract is relied on here.
        content = getattr(result, "content", str(result)) or ""
        citations = getattr(result, "citations", None) or []
        return AgentResult(
            strategy=self.strategy,
            content=content,
            citations=list(citations),
        )
