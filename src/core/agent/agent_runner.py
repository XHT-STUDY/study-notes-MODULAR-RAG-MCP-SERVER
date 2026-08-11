"""Agent loop and retrieval engine for the Agentic RAG layer (Phase 6).

:class:`RetrievalEngine` mirrors the ``QueryKnowledgeHubTool`` component
assembly but stays inside ``src/core/agent`` (no MCP SDK).  :class:`_BaseLoopAgent`
is the shared ReAct-style loop; the three strategies (react / plan_and_execute /
self_ask) differ only in system prompt, an optional planning step, and final
answer prefix handling.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
from dataclasses import dataclass
from typing import Any

from src.core.agent.base_agent import AgentResult, BaseAgent
from src.core.agent.memory import ConversationMemory, MemoryFactory
from src.core.agent.query_router import (
    NullRouter,
    QueryRouter,
    RouterFactory,
)
from src.core.agent.query_understanding import (
    QueryUnderstanding,
    RuleQueryUnderstanding,
)
from src.core.agent.reflection import RetrievalReflector
from src.core.agent.tool_registry import ToolRegistry
from src.core.response.citation_generator import Citation, CitationGenerator
from src.core.response.response_builder import ResponseBuilder
from src.core.settings import Settings, load_settings
from src.core.types import ProcessedQuery, RetrievalResult
from src.libs.answer_generator.base_answer_generator import sanitize_citation_markers
from src.libs.llm.base_llm import (
    BaseLLM,
    Message,
    format_tool_call,
    parse_tool_call,
)
from src.libs.llm.llm_factory import LLMFactory

logger = logging.getLogger(__name__)

#: The retrieval tool the loop handles natively (intercepted before the registry).
RETRIEVAL_TOOL = "query_knowledge_hub"

_REACT_SYSTEM_PROMPT = (
    "你是智能检索代理。你会获得检索知识库的工具。"
    '每次要么调用一个工具（只输出一行 <tool_call name="工具名">{{"参数": 值}}</tool_call>），'
    "要么在资料已足够时直接输出最终答案。"
    "回答必须基于检索到的资料，并用 [1][2] 等标注引用来源。"
)

_PLAN_SYSTEM_PROMPT = (
    "你是智能检索代理。先输出一句「计划」说明你的检索方案，然后逐步调用工具检索，"
    '最后输出以 "Final Answer:" 开头的最终答案。'
    "回答必须基于检索到的资料，并用 [1][2] 等标注引用来源。"
)

_SELF_ASK_SYSTEM_PROMPT = (
    "你是智能检索代理。若问题复杂，先自问子问题并依次检索，"
    '最后输出以 "Final Answer:" 开头的最终答案。'
    "回答必须基于检索到的资料，并用 [1][2] 等标注引用来源。"
)

_FORMAT_ERROR_MSG = (
    "格式错误: {detail}。请重新输出 <tool_call name=\"工具名\">{{\"参数\": 值}}</tool_call> "
    "或直接给出最终答案。"
)


def _strip_final_prefix(text: str) -> str:
    """Strip a leading ``Final Answer:`` / ``答案:`` style prefix."""
    text = text.strip()
    for prefix in ("Final Answer:", "Final Answer：", "Final:", "答案:", "Answer:"):
        if text.startswith(prefix):
            return text[len(prefix) :].strip()
    return text


def _top_score(results: list[RetrievalResult]) -> float:
    """Top chunk score rounded to 4 decimals (or 0.0 when empty/invalid)."""
    if not results:
        return 0.0
    try:
        return round(float(results[0].score), 4)
    except (TypeError, ValueError):
        return 0.0


def _citations_from(results: list[RetrievalResult]) -> list[Citation]:
    """Build 1-based citations matching the response builder's ``[n]`` markers."""
    return CitationGenerator().generate(results) if results else []


def _route_tool_args(tool_name: str, query: str) -> dict[str, Any] | None:
    """Best-effort router pre-execution args; ``None`` when not derivable."""
    if tool_name == "list_collections":
        return {}
    return None


@dataclass
class RetrievalEngineResult:
    """Result of one retrieval-engine search."""

    results: list[RetrievalResult]
    content: str
    query: str = ""
    collection: str = ""


class RetrievalEngine:
    """Self-contained hybrid retrieval, mirroring QueryKnowledgeHubTool.

    All blocking work (embedding API, ChromaDB, BM25, rerank) runs inside
    ``asyncio.to_thread`` so the stdio transport never stalls.  Components can
    be injected for tests; otherwise they are lazily built from settings.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        default_top_k: int = 5,
        max_top_k: int = 20,
        default_collection: str = "default",
        enable_rerank: bool = True,
        embedding_client: Any = None,
        reranker: Any = None,
        response_builder: ResponseBuilder | None = None,
    ) -> None:
        self._settings = settings
        self._default_top_k = default_top_k
        self._max_top_k = max_top_k
        self._default_collection = default_collection
        self._enable_rerank = enable_rerank
        self._embedding_client = embedding_client
        self._reranker = reranker
        self._response_builder = response_builder or ResponseBuilder()
        self._hybrid_search: Any = None
        self._current_collection: str | None = None

    @property
    def settings(self) -> Settings:
        if self._settings is None:
            self._settings = load_settings()
        return self._settings

    async def search(
        self,
        query: str,
        top_k: int | None = None,
        collection: str | None = None,
        trace: Any = None,
    ) -> RetrievalEngineResult:
        """Run hybrid search + optional rerank and build the markdown response."""
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")
        effective_top_k = min(top_k or self._default_top_k, self._max_top_k)
        effective_collection = collection or self._default_collection

        await asyncio.to_thread(self._ensure_initialized, effective_collection)
        results = await asyncio.to_thread(
            self._perform_search, query, effective_top_k, trace
        )
        if self._enable_rerank and results:
            results = await asyncio.to_thread(
                self._apply_rerank, query, results, effective_top_k, trace
            )
        response = self._response_builder.build(
            results=results, query=query, collection=effective_collection
        )
        return RetrievalEngineResult(
            results=results,
            content=response.content,
            query=query,
            collection=effective_collection,
        )

    def _ensure_initialized(self, collection: str) -> None:
        """Build vector store + retrievers + hybrid search for a collection."""
        from src.core.query_engine.dense_retriever import create_dense_retriever
        from src.core.query_engine.hybrid_search import create_hybrid_search
        from src.core.query_engine.query_processor import QueryProcessor
        from src.core.query_engine.reranker import create_core_reranker
        from src.core.query_engine.sparse_retriever import create_sparse_retriever
        from src.ingestion.storage.bm25_indexer import BM25Indexer
        from src.libs.embedding.embedding_factory import EmbeddingFactory
        from src.libs.vector_store.vector_store_factory import VectorStoreFactory

        if self._embedding_client is None:
            self._embedding_client = EmbeddingFactory.create(self.settings)
        if self._reranker is None:
            self._reranker = create_core_reranker(settings=self.settings)

        if collection == self._current_collection and self._hybrid_search is not None:
            return
        vector_store = VectorStoreFactory.create(
            self.settings, collection_name=collection
        )
        dense_retriever = create_dense_retriever(
            settings=self.settings,
            embedding_client=self._embedding_client,
            vector_store=vector_store,
        )
        bm25_indexer = BM25Indexer(index_dir=str(_bm25_dir(collection)))
        sparse_retriever = create_sparse_retriever(
            settings=self.settings,
            bm25_indexer=bm25_indexer,
            vector_store=vector_store,
        )
        sparse_retriever.default_collection = collection
        self._hybrid_search = create_hybrid_search(
            settings=self.settings,
            query_processor=QueryProcessor(),
            dense_retriever=dense_retriever,
            sparse_retriever=sparse_retriever,
        )
        self._current_collection = collection

    def _perform_search(
        self, query: str, top_k: int, trace: Any = None
    ) -> list[RetrievalResult]:
        if self._hybrid_search is None:
            raise RuntimeError("HybridSearch not initialized")
        initial_top_k = top_k * 2 if self._enable_rerank else top_k
        try:
            results = self._hybrid_search.search(
                query=query,
                top_k=initial_top_k,
                filters=None,
                trace=trace,
                return_details=False,
            )
            return results if isinstance(results, list) else results.results
        except Exception as exc:  # surfaced as empty results, not fatal
            logger.warning("Hybrid search failed: %s", exc)
            return []

    def _apply_rerank(
        self, query: str, results: list[RetrievalResult], top_k: int, trace: Any = None
    ) -> list[RetrievalResult]:
        if self._reranker is None or not getattr(self._reranker, "is_enabled", True):
            return results[:top_k]
        try:
            rerank_result = self._reranker.rerank(
                query=query, results=results, top_k=top_k, trace=trace
            )
            return rerank_result.results if hasattr(rerank_result, "results") else results[:top_k]
        except Exception as exc:  # keep original order on failure
            logger.warning("Rerank failed, using original order: %s", exc)
            return results[:top_k]


def _bm25_dir(collection: str) -> str:
    """Absolute BM25 index directory for a collection."""
    from src.core.settings import resolve_path

    return str(resolve_path(f"data/db/bm25/{collection}"))


class _BaseLoopAgent(BaseAgent):
    """Shared ReAct-style loop used by all three strategies.

    Strategy-specific behaviour hooks:
    - ``_pre_loop``: optional planning step that consumes an iteration.
    - ``_parse_final``: final-answer prefix handling.
    """

    def __init__(
        self,
        strategy: str,
        settings: Settings | None = None,
        *,
        llm: BaseLLM | None = None,
        registry: ToolRegistry | None = None,
        retrieval_engine: RetrievalEngine | None = None,
        memory: ConversationMemory | None = None,
        router: QueryRouter | None = None,
        reflector: RetrievalReflector | None = None,
        query_understanding: QueryUnderstanding | None = None,
        direct_retriever: Any = None,
        max_iterations: int = 5,
    ) -> None:
        self.strategy = strategy
        self._settings = settings
        self._llm = llm
        self._registry = registry
        self._retrieval_engine = retrieval_engine
        self._memory = memory
        self._router = router
        self._reflector = reflector
        self._query_understanding = query_understanding
        self._direct_retriever = direct_retriever
        self._max_iterations = max_iterations

    # ---- lazy component building -----------------------------------------

    @property
    def settings(self) -> Settings:
        if self._settings is None:
            self._settings = load_settings()
        return self._settings

    def _agent_settings(self):
        return getattr(self.settings, "agent", None)

    def _get_llm(self) -> BaseLLM | None:
        if self._llm is None:
            try:
                self._llm = LLMFactory.create(self.settings)
            except Exception as exc:  # e.g. missing key → passthrough degradation
                logger.warning("LLM unavailable for agent: %s", exc)
                self._llm = None
        return self._llm

    def _get_registry(self) -> ToolRegistry:
        if self._registry is None:
            self._registry = ToolRegistry([])
        return self._registry

    def _get_retrieval_engine(self) -> RetrievalEngine:
        if self._retrieval_engine is None:
            self._retrieval_engine = RetrievalEngine(self.settings)
        return self._retrieval_engine

    def _get_memory(self) -> ConversationMemory:
        if self._memory is None:
            ag = self._agent_settings()
            self._memory = MemoryFactory.create(ag.memory if ag else None)
        return self._memory

    def _get_router(self, llm: BaseLLM) -> QueryRouter:
        if self._router is None:
            ag = self._agent_settings()
            self._router = RouterFactory.create(ag.router if ag else None, llm=llm)
        return self._router

    def _get_reflector(self) -> RetrievalReflector:
        if self._reflector is None:
            ag = self._agent_settings()
            if ag is not None and ag.reflection is not None and ag.reflection.enabled:
                self._reflector = RetrievalReflector(
                    enabled=True,
                    max_retrieval_rounds=ag.reflection.max_retrieval_rounds,
                )
            else:
                self._reflector = RetrievalReflector(enabled=False)
        return self._reflector

    def _get_query_understanding(self) -> QueryUnderstanding:
        if self._query_understanding is None:
            self._query_understanding = RuleQueryUnderstanding()
        return self._query_understanding

    def _memory_window(self) -> int:
        ag = self._agent_settings()
        if ag is not None and ag.memory is not None:
            return ag.memory.window_size
        return 10

    # ---- strategy hooks ---------------------------------------------------

    def _system_prompt(self) -> str:
        return {
            "react": _REACT_SYSTEM_PROMPT,
            "plan_and_execute": _PLAN_SYSTEM_PROMPT,
            "self_ask": _SELF_ASK_SYSTEM_PROMPT,
        }.get(self.strategy, _REACT_SYSTEM_PROMPT)

    async def _pre_loop(
        self,
        query: str,
        messages: list[Message],
        llm: BaseLLM,
        tool_descs: list[dict[str, Any]],
        trace: Any,
    ) -> bool:
        """Optional planning step; returns True when it consumed an iteration."""
        return False

    def _parse_final(self, content: str) -> str:
        return content

    # ---- run ---------------------------------------------------------------

    async def run(self, query: str, trace: Any = None) -> AgentResult:
        if not query or not query.strip():
            return AgentResult(
                strategy=self.strategy, content="", refusal_reason="empty_query", is_empty=True
            )
        llm = self._get_llm()
        if llm is None:
            return await self._degrade(query, trace, "llm_unavailable")

        registry = self._get_registry()
        engine = self._get_retrieval_engine()
        memory = self._get_memory()
        reflector = self._get_reflector()
        router = self._get_router(llm)
        understanding = self._get_query_understanding()

        session_id = (
            (trace.metadata or {}).get("session_id", "default") if trace else "default"
        )
        pq = understanding.understand(query, trace)
        tool_descs = registry.describe()

        messages: list[Message] = [Message(role="system", content=self._system_prompt())]
        for msg in memory.recent(session_id, self._memory_window()):
            messages.append(Message(role=msg["role"], content=msg["content"]))
        messages.append(Message(role="user", content=query))

        steps: list[dict[str, Any]] = []
        iterations = 0

        # Router pre-step: a tool-routed query is executed once upfront.
        if not isinstance(router, NullRouter):
            route = await router.route(query, trace)
            if trace is not None:
                trace.record_stage(
                    "agent_router",
                    {"target": route.target, "tool_name": route.tool_name, "reason": route.reason},
                )
            args = _route_tool_args(route.tool_name or "", query)
            if route.target == "tool" and args is not None and registry.is_allowed(route.tool_name or ""):
                pre_result = await registry.call(route.tool_name or "", args)
                messages.append(
                    Message(role="assistant", content=format_tool_call(route.tool_name or "", args))
                )
                messages.append(
                    Message(role="tool", content=pre_result.content, tool_call_id="t0")
                )
                steps.append({"kind": "route_pre_exec", "tool": route.tool_name})

        # Planning step (plan_and_execute only).
        if await self._pre_loop(query, messages, llm, tool_descs, trace):
            iterations += 1

        final_content = ""
        final_results: list[RetrievalResult] = []
        last_search: RetrievalEngineResult | None = None

        while iterations < self._max_iterations:
            iterations += 1
            try:
                response = await asyncio.to_thread(
                    llm.chat_with_tools, messages, tool_descs, trace
                )
            except Exception as exc:
                logger.warning("Agent LLM call failed: %s", exc)
                return await self._degrade(query, trace, "llm_error", detail=str(exc))

            content = (response.content or "").strip()
            if not content:
                continue

            tool_call, err = parse_tool_call(content)
            if tool_call is None:
                if err is not None:
                    messages.append(Message(role="assistant", content=content))
                    messages.append(
                        Message(
                            role="tool",
                            content=_FORMAT_ERROR_MSG.format(detail=err),
                            tool_call_id=f"t{iterations}",
                        )
                    )
                    continue
                final_content = self._parse_final(content)
                break

            if not registry.is_allowed(tool_call.name):
                messages.append(Message(role="assistant", content=content))
                messages.append(
                    Message(
                        role="tool",
                        content=f"工具 {tool_call.name} 不在白名单中，不能调用。",
                        tool_call_id=f"t{iterations}",
                    )
                )
                steps.append({"kind": "not_allowed", "tool": tool_call.name})
                continue

            if tool_call.name == RETRIEVAL_TOOL:
                search_result = await self._search_with_reflection(
                    tool_call.arguments, query, pq, reflector, engine, trace, steps
                )
                tool_text = search_result.content
                last_search = search_result
                final_results = list(search_result.results)
            else:
                tool_result = await registry.call(tool_call.name, tool_call.arguments)
                tool_text = tool_result.content
                steps.append(
                    {
                        "kind": "tool_call",
                        "tool": tool_call.name,
                        "is_error": tool_result.is_error,
                    }
                )

            if trace is not None:
                trace.record_stage(
                    "agent_tool_call",
                    {
                        "tool": tool_call.name,
                        "step": iterations,
                        "is_retrieval": tool_call.name == RETRIEVAL_TOOL,
                    },
                )
            messages.append(
                Message(
                    role="assistant",
                    content=content,
                    tool_calls=[{"name": tool_call.name, "arguments": tool_call.arguments}],
                )
            )
            messages.append(
                Message(role="tool", content=tool_text, tool_call_id=f"t{iterations}")
            )

        if not final_content:
            if last_search is not None:
                final_content = last_search.content
            exhausted_results = final_results or (
                last_search.results if last_search else []
            )
            return AgentResult(
                strategy=self.strategy,
                content=final_content,
                intermediate_steps=steps,
                citations=_citations_from(exhausted_results),
                confidence=_top_score(exhausted_results),
                refusal_reason="agent_max_iterations_exceeded",
                is_empty=not final_content,
            )

        memory.add(session_id, "user", query)
        memory.add(session_id, "assistant", final_content)

        valid_indices = set(range(1, len(final_results) + 1))
        final_content = sanitize_citation_markers(final_content, valid_indices)
        if trace is not None:
            trace.record_stage(
                "agent_final",
                {"strategy": self.strategy, "iterations": iterations, "len": len(final_content)},
            )
        return AgentResult(
            strategy=self.strategy,
            content=final_content,
            intermediate_steps=steps,
            citations=_citations_from(final_results),
            confidence=_top_score(final_results),
        )

    # ---- helpers -----------------------------------------------------------

    async def _search_with_reflection(
        self,
        arguments: dict[str, Any],
        original_query: str,
        pq: ProcessedQuery,
        reflector: RetrievalReflector,
        engine: RetrievalEngine,
        trace: Any,
        steps: list[dict[str, Any]],
    ) -> RetrievalEngineResult:
        query = arguments.get("query") or original_query
        top_k = arguments.get("top_k")
        collection = arguments.get("collection")
        result = await engine.search(
            query, top_k=top_k, collection=collection, trace=trace
        )
        rounds_used = 0
        decision = reflector.evaluate(result.results, rounds_used)
        while decision.needs_retrieval:
            rounds_used += 1
            rewritten = reflector.rewrite(original_query, pq.expanded_terms)
            steps.append(
                {
                    "kind": "reflection",
                    "round": rounds_used,
                    "reason": decision.reason,
                    "rewritten_query": rewritten,
                }
            )
            if trace is not None:
                trace.record_stage(
                    "agent_reflection",
                    {
                        "round": rounds_used,
                        "reason": decision.reason,
                        "rewritten_query": rewritten,
                    },
                )
            result = await engine.search(
                rewritten, top_k=top_k, collection=collection, trace=trace
            )
            decision = reflector.evaluate(result.results, rounds_used)
        return result

    async def _degrade(
        self, query: str, trace: Any, reason: str, detail: str = ""
    ) -> AgentResult:
        """Passthrough to the direct retriever when the LLM is unavailable."""
        if self._direct_retriever is not None:
            result = self._direct_retriever(query)
            if inspect.isawaitable(result):
                result = await result
            content = getattr(result, "content", str(result)) or ""
            return AgentResult(
                strategy=self.strategy,
                content=content,
                refusal_reason=reason,
                is_empty=not content,
            )
        return AgentResult(
            strategy=self.strategy,
            content="",
            refusal_reason=reason,
            is_empty=True,
        )


class ReActAgent(_BaseLoopAgent):
    """Full ReAct loop (default strategy): thought → tool → final answer."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__("react", *args, **kwargs)


class PlanAndExecuteAgent(_BaseLoopAgent):
    """Plan first (one planning LLM call), then execute the loop."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__("plan_and_execute", *args, **kwargs)

    async def _pre_loop(
        self,
        query: str,
        messages: list[Message],
        llm: BaseLLM,
        tool_descs: list[dict[str, Any]],
        trace: Any,
    ) -> bool:
        try:
            response = await asyncio.to_thread(
                llm.chat_with_tools, list(messages), tool_descs, trace
            )
        except Exception:
            return False
        plan_text = (response.content or "").strip()
        if not plan_text:
            return False
        messages.append(Message(role="assistant", content=f"计划: {plan_text}"))
        return True

    def _parse_final(self, content: str) -> str:
        return _strip_final_prefix(content)


class SelfAskAgent(_BaseLoopAgent):
    """Self-ask strategy: sub-question decomposition, prefix-stripped final."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__("self_ask", *args, **kwargs)

    def _parse_final(self, content: str) -> str:
        return _strip_final_prefix(content)
