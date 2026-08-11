"""Query router for the Agentic RAG layer (Phase 6).

Decides whether a query goes straight to retrieval (``direct_rag``), needs
multiple retrieval hops (``multi_hop``) or should be answered by a dedicated
tool (``tool``).  The rule router is offline; the LLM router classifies with a
prompt and falls back to direct retrieval on any error.
"""

from __future__ import annotations

import asyncio
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Literal

from src.core.settings import RouterSettings
from src.libs.llm.base_llm import BaseLLM, Message

#: Tool name targeted when the query is about listing collections.
_LIST_TOOL = "list_collections"
#: Tool name targeted when the query asks for a document summary.
_SUMMARY_TOOL = "get_document_summary"

#: Keyword → tool routing rules, checked in order (regex, case-insensitive).
_TOOL_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"集合|collection|列表|库列表", re.IGNORECASE), _LIST_TOOL),
    (re.compile(r"总结|摘要|概要|summary", re.IGNORECASE), _SUMMARY_TOOL),
]

#: Keywords hinting that multiple retrieval hops would help.
_MULTI_HOP_RE = re.compile(r"对比|比较|区别|差异|compare|versus|vs\.?", re.IGNORECASE)

_ROUTER_SYSTEM_PROMPT = (
    "你是查询路由器。判断用户查询应如何处理，只回复一个词，不要输出其他内容：\n"
    f"- 查询涉及列举集合/库列表 → tool:{_LIST_TOOL}\n"
    f"- 查询请求总结某个文档 → tool:{_SUMMARY_TOOL}\n"
    "- 查询需要多轮检索或对比多个资料 → multi_hop\n"
    "- 否则 → direct_rag"
)


@dataclass
class RouteResult:
    """Where the agent should direct this query."""

    target: Literal["direct_rag", "multi_hop", "tool"] = "direct_rag"
    tool_name: str | None = None
    reason: str = ""

    @property
    def is_direct(self) -> bool:
        return self.target == "direct_rag"


class QueryRouter(ABC):
    """Abstract query router."""

    @abstractmethod
    async def route(self, query: str, trace: Any = None) -> RouteResult:
        """Classify a query into a :class:`RouteResult`."""


class NullRouter(QueryRouter):
    """Router used when routing is disabled — always direct retrieval."""

    async def route(self, query: str, trace: Any = None) -> RouteResult:
        return RouteResult(target="direct_rag", reason="路由未启用")


class RuleRouter(QueryRouter):
    """Offline keyword/regex routing (no LLM cost)."""

    async def route(self, query: str, trace: Any = None) -> RouteResult:
        for pattern, tool_name in _TOOL_RULES:
            if pattern.search(query):
                return RouteResult(
                    target="tool",
                    tool_name=tool_name,
                    reason=f"命中工具规则: {pattern.pattern}",
                )
        if _MULTI_HOP_RE.search(query):
            return RouteResult(target="multi_hop", reason="命中多跳规则")
        return RouteResult(target="direct_rag", reason="默认直通检索")


class LLMRouter(QueryRouter):
    """Prompt-based classification; degrades to direct retrieval on any error."""

    def __init__(self, llm: BaseLLM) -> None:
        self._llm = llm

    async def route(self, query: str, trace: Any = None) -> RouteResult:
        messages = [
            Message(role="system", content=_ROUTER_SYSTEM_PROMPT),
            Message(role="user", content=query),
        ]
        try:
            # The LLM call is blocking — run it off the event loop so the
            # stdio transport never stalls (same reason as the agent loop).
            response = await asyncio.to_thread(
                self._llm.chat, messages, trace=trace
            )
        except Exception:
            return RouteResult(target="direct_rag", reason="LLM 路由失败，回退直通")
        return _parse_llm_reply(response.content)


def _parse_llm_reply(reply: str) -> RouteResult:
    text = (reply or "").strip().lower()
    if text.startswith("tool"):
        tool_name = (
            text.split(":", 1)[1].strip() if ":" in text else "query_knowledge_hub"
        )
        return RouteResult(target="tool", tool_name=tool_name, reason="LLM 分类")
    if "multi_hop" in text:
        return RouteResult(target="multi_hop", reason="LLM 分类")
    return RouteResult(target="direct_rag", reason="LLM 分类默认")


class RouterFactory:
    """Builds a router from settings; falls back to the rule router."""

    @staticmethod
    def create(settings: RouterSettings | None, llm: BaseLLM | None = None) -> QueryRouter:
        if settings is None or not settings.enabled:
            return NullRouter()
        provider = (settings.provider or "rule").lower()
        if provider == "llm":
            if llm is not None:
                return LLMRouter(llm)
            return RuleRouter()  # no LLM available → offline fallback
        return RuleRouter()
