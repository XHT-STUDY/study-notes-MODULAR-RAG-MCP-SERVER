#!/usr/bin/env python
"""Query script for the Modular RAG MCP Server.

Runs one query through the hybrid retrieval pipeline and prints a
stage-by-stage pipeline report. Every stage (query preprocessing, dense
retrieval, BM25 retrieval, RRF fusion, rerank, answer generation) is
listed with its inputs, outputs, elapsed time and intermediate results.

Usage:
    # Full pipeline report (default)
    python scripts/query.py --query "混合检索的原理" --collection default

    # Only the final results, no per-stage detail
    python scripts/query.py --query "RRF 是什么" --quiet

    # Keep the INFO run logs that are suppressed by default
    python scripts/query.py --query "RRF 是什么" --debug

    # Disable reranking / answer generation
    python scripts/query.py --query "RRF 是什么" --no-rerank --no-answer

Exit codes:
    0 - Success
    1 - Query failure
    2 - Configuration error
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import Any

# Ensure project root is on sys.path
_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent
sys.path.insert(0, str(_REPO_ROOT))

# Set UTF-8 encoding for Windows console
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from src.core.query_engine.dense_retriever import create_dense_retriever
from src.core.query_engine.hybrid_search import create_hybrid_search
from src.core.query_engine.query_processor import QueryProcessor
from src.core.query_engine.reranker import create_core_reranker
from src.core.query_engine.sparse_retriever import create_sparse_retriever
from src.core.settings import load_settings
from src.core.trace import TraceCollector, TraceContext
from src.ingestion.storage.bm25_indexer import BM25Indexer
from src.libs.answer_generator import AnswerGeneratorFactory
from src.libs.embedding.embedding_factory import EmbeddingFactory
from src.libs.vector_store.vector_store_factory import VectorStoreFactory
from src.observability.logger import get_logger

logger = get_logger(__name__)

_LINE = "=" * 68
_THIN = "-" * 68
_PREVIEW_WIDTH = 76


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Query documents from the Modular RAG knowledge hub.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--query", "-q",
        required=True,
        help="Query string."
    )

    parser.add_argument(
        "--collection", "-c",
        default="default",
        help="Collection name (default: 'default')"
    )

    parser.add_argument(
        "--top-k",
        type=int,
        default=10,
        help="Max number of results (default: 10)"
    )

    parser.add_argument(
        "--config",
        default=str(_REPO_ROOT / "config" / "settings.yaml"),
        help="Path to configuration file (default: config/settings.yaml)"
    )

    parser.add_argument(
        "--no-rerank",
        action="store_true",
        help="Disable reranking even if enabled in settings"
    )

    parser.add_argument(
        "--no-answer",
        action="store_true",
        help="Skip answer generation (retrieval-only, for baseline comparison)"
    )

    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Only print the final results (skip per-stage details)"
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Keep INFO run logs (suppressed to WARNING by default so the "
             "pipeline report stays readable)"
    )

    # Backwards compatibility: the detailed report is now the default output.
    parser.add_argument(
        "--verbose",
        action="store_true",
        help=argparse.SUPPRESS,
    )

    return parser.parse_args()


def _format_filters(filters: dict[str, Any]) -> str:
    if not filters:
        return "(none)"
    return ", ".join(f"{k}={v}" for k, v in filters.items())


def _short(text: str | None, width: int = _PREVIEW_WIDTH) -> str:
    """One-line text preview."""
    flat = (text or "").replace("\n", " ").strip()
    if len(flat) <= width:
        return flat
    return flat[:width] + "…"


def _source_name(result: Any) -> str:
    """Basename of the source file for a RetrievalResult."""
    metadata = result.metadata or {}
    source = metadata.get("source_path") or metadata.get("source") or "?"
    return Path(str(source)).name


def _stage_ms(trace: TraceContext, stage_name: str) -> float | None:
    """Recorded elapsed_ms for a stage, or None when not recorded."""
    for entry in reversed(trace.stages):
        if entry.get("stage") == stage_name:
            return entry.get("elapsed_ms")
    return None


def _print_ms(trace: TraceContext, stage_name: str, fallback_ms: float | None = None) -> None:
    """Print the '耗时' line for one stage."""
    ms = _stage_ms(trace, stage_name)
    if ms is None:
        ms = fallback_ms
    if ms is not None:
        print(f" 耗时  : {ms:.1f} ms")


def _print_stage_header(index: int, total: int, title: str, status: str = "执行") -> None:
    print(f"\n{_THIN}")
    print(f" [{index}/{total}] {title}   <{status}>")
    print(_THIN)


def _print_io(label: str, lines: list[str]) -> None:
    print(f" {label}:")
    for line in lines:
        print(f"   {line}")


def _print_chunk_rows(results: list[Any], score_label: str, max_rows: int | None = None) -> None:
    """Compact result rows: rank / score / chunk id / source / preview."""
    rows = results[:max_rows] if max_rows else results
    for i, r in enumerate(rows, start=1):
        print(f"   #{i:02d}  {score_label}={r.score:.4f}  {r.chunk_id}  {_source_name(r)}")
        print(f"        └ {_short(r.text)}")
    if max_rows and len(results) > max_rows:
        print(f"   ...（其余 {len(results) - max_rows} 条省略，见最终结果）")


def _print_results(results: list[Any], top_k: int, title: str = "最终检索结果") -> None:
    print("\n" + _LINE)
    print(f"{title} (top_k={top_k}, returned={len(results)})")
    print(_LINE)

    for idx, result in enumerate(results, start=1):
        metadata = result.metadata or {}
        source_path = metadata.get("source_path", "")
        chunk_index = metadata.get("chunk_index", "")
        page_num = metadata.get("page_num", "")
        snippet = (result.text or "").replace("\n", " ")[:200]

        print(f"#{idx:02d}  score={result.score:.4f}  id={result.chunk_id}")
        print(f"     source_path={source_path}")
        if chunk_index != "":
            print(f"     chunk_index={chunk_index}")
        if page_num != "":
            print(f"     page_num={page_num}")
        print(f"     text={snippet}...")

    print(_LINE)


# ---------------------------------------------------------------------------
# Pipeline report
# ---------------------------------------------------------------------------

TOTAL_STAGES = 6


def _print_overview(hybrid_search, reranker, answer_generator, settings, args) -> None:
    """Print the run header with the pipeline overview."""
    cfg = hybrid_search.config
    rrf_k = getattr(getattr(hybrid_search, "fusion", None), "k", "?")
    rerank_status = "跳过" if (args.no_rerank or not reranker.is_enabled) else "执行"
    answer_on = answer_generator is not None and answer_generator.is_enabled
    answer_status = "跳过" if (args.no_answer or not answer_on) else "执行"
    embedding = getattr(getattr(settings, "embedding", None), "model", "?")
    embedding_provider = getattr(getattr(settings, "embedding", None), "provider", "?")

    print(_LINE)
    print("[*] Modular RAG Query — 流水线报告")
    print(_LINE)
    print(f" 查询    : {args.query}")
    print(f" 集合    : {args.collection}    top_k={args.top_k}")
    print(f" 检索配置: dense_top_k={cfg.dense_top_k}  sparse_top_k={cfg.sparse_top_k}  "
          f"fusion_top_k={cfg.fusion_top_k}  rrf_k={rrf_k}")
    print(f" 模型    : embedding={embedding_provider}/{embedding}")
    print(f" 流水线  : ①查询预处理 → ②Dense向量检索 → ③BM25关键词检索 → "
          f"④RRF融合 → ⑤重排[{rerank_status}] → ⑥答案生成[{answer_status}]")
    print(_LINE)


def _stage1_preprocessing(hybrid_result: Any, trace: TraceContext) -> None:
    """Stage 1: query preprocessing — raw query → keywords + filters."""
    _print_stage_header(1, TOTAL_STAGES, "查询预处理 · QueryProcessor")
    pq = hybrid_result.processed_query
    if pq is None:
        _print_io("输出", ["(无 processed_query 信息)"])
        return
    _print_io("输入", [f"query = \"{pq.original_query}\""])
    _print_io("输出", [
        f"keywords = {pq.keywords}",
        f"filters  = {_format_filters(pq.filters)}",
    ])
    _print_ms(trace, "query_processing")


def _stage2_dense(hybrid_result: Any, hybrid_search, trace: TraceContext) -> None:
    """Stage 2: dense retrieval — original query → cosine-ranked chunks."""
    _print_stage_header(2, TOTAL_STAGES, "向量检索 · DenseRetriever (语义)")
    if hybrid_result.dense_error:
        _print_io("状态", [f"[错误] {hybrid_result.dense_error}"])
        print(" [WARN] Dense 失败，已降级为仅 BM25 结果。")
        return
    cfg = hybrid_search.config
    _print_io("输入", [
        f"query(原文) + top_k={cfg.dense_top_k}（score = 向量相似度）",
    ])
    dense = hybrid_result.dense_results or []
    _print_io("输出", [f"{len(dense)} 条结果："])
    print()
    _print_chunk_rows(dense, "sim", max_rows=5)
    _print_ms(trace, "dense_retrieval")


def _stage3_sparse(hybrid_result: Any, hybrid_search, trace: TraceContext) -> None:
    """Stage 3: sparse retrieval — keywords → BM25-ranked chunks."""
    _print_stage_header(3, TOTAL_STAGES, "BM25 检索 · SparseRetriever (关键词)")
    if hybrid_result.sparse_error:
        _print_io("状态", [f"[错误] {hybrid_result.sparse_error}"])
        print(" [WARN] Sparse 失败，已降级为仅 Dense 结果。")
        return
    pq = hybrid_result.processed_query
    cfg = hybrid_search.config
    keywords = pq.keywords if pq else []
    _print_io("输入", [
        f"keywords = {keywords}",
        f"top_k={cfg.sparse_top_k}（score = BM25 词频得分）",
    ])
    sparse = hybrid_result.sparse_results or []
    _print_io("输出", [f"{len(sparse)} 条结果："])
    print()
    _print_chunk_rows(sparse, "bm25", max_rows=5)
    _print_ms(trace, "sparse_retrieval")


def _stage4_fusion(hybrid_result: Any, hybrid_search, trace: TraceContext) -> None:
    """Stage 4: RRF fusion — two ranked lists → fused ranking with contributions."""
    _print_stage_header(4, TOTAL_STAGES, "RRF 融合 · Reciprocal Rank Fusion")
    if hybrid_result.used_fallback:
        _print_io("状态", ["[WARN] 融合被跳过（单路降级），直接使用另一路结果。"])
        return
    dense = hybrid_result.dense_results or []
    sparse = hybrid_result.sparse_results or []
    k = getattr(getattr(hybrid_search, "fusion", None), "k", 60)

    dense_rank = {r.chunk_id: i for i, r in enumerate(dense, start=1)}
    sparse_rank = {r.chunk_id: i for i, r in enumerate(sparse, start=1)}

    _print_io("输入", [
        f"dense {len(dense)} 条 + sparse {len(sparse)} 条",
        f"公式 : score(d) = Σ 1/({k} + rank)",
    ])
    _print_io("输出", [f"{len(hybrid_result.results)} 条融合结果："])
    print()
    for i, r in enumerate(hybrid_result.results, start=1):
        cid = r.chunk_id
        dr = dense_rank.get(cid)
        sr = sparse_rank.get(cid)
        d_part = f"dense#{dr}" if dr else "dense#-"
        s_part = f"sparse#{sr}" if sr else "sparse#-"
        both = "  ← 双路命中" if dr and sr else ("  ← 仅 Dense" if dr else "  ← 仅 BM25")
        print(f"   #{i:02d}  rrf={r.score:.4f}  {d_part} + {s_part}{both}")
        print(f"        └ [{_source_name(r)}] {_short(r.text)}")
    _print_ms(trace, "fusion")


def _stage5_rerank(
    reranker,
    query: str,
    results: list[Any],
    disable_rerank: bool,
    trace: TraceContext,
    quiet: bool,
) -> list[Any]:
    """Stage 5: rerank — fused results → reordered results. Returns new list."""
    skip_reason = None
    if disable_rerank:
        skip_reason = "--no-rerank 由命令行禁用"
    elif not reranker.is_enabled:
        skip_reason = "settings: rerank.enabled=false"

    if skip_reason:
        if not quiet:
            _print_stage_header(5, TOTAL_STAGES, "重排 · Reranker", status="跳过")
            _print_io("原因", [skip_reason])
        return results

    try:
        rerank_result = reranker.rerank(query=query, results=results, top_k=len(results), trace=trace)
        new_results = rerank_result.results
        if not quiet:
            _print_stage_header(5, TOTAL_STAGES, "重排 · Reranker")
            old_pos = {r.chunk_id: i for i, r in enumerate(results, start=1)}
            _print_io("输入", [f"{len(results)} 条融合结果"])
            _print_io("输出", [f"{len(new_results)} 条（括号内为位次变化，= 表示未变）"])
            print()
            for i, r in enumerate(new_results, start=1):
                old = old_pos.get(r.chunk_id)
                if old is None:
                    move = "new"
                elif old == i:
                    move = "="
                elif old > i:
                    move = f"↑{old - i}"
                else:
                    move = f"↓{i - old}"
                print(f"   #{i:02d}  ({move:>3})  score={r.score:.4f}  {r.chunk_id}  {_source_name(r)}")
                print(f"        └ {_short(r.text)}")
            if rerank_result.used_fallback:
                print(f" [WARN] 重排降级: {rerank_result.fallback_reason}")
            _print_ms(trace, "rerank")
        return new_results
    except Exception as e:
        if not quiet:
            print(f" [WARN] 重排失败: {e}，保持原顺序。")
        return results


def _stage6_answer(
    answer_generator,
    query: str,
    results: list[Any],
    disable_answer: bool,
    trace: TraceContext,
    quiet: bool,
) -> None:
    """Stage 6: answer generation — query + top chunks → answer + confidence."""
    skip_reason = None
    if disable_answer:
        skip_reason = "--no-answer 由命令行禁用"
    elif answer_generator is None:
        skip_reason = "答案生成器构建失败（见启动告警）"
    elif not answer_generator.is_enabled:
        skip_reason = "settings: answer_generator.enabled=false"
    elif not results:
        skip_reason = "没有检索结果"

    title = f"答案生成 · {type(answer_generator).__name__ if answer_generator else 'N/A'}"
    if skip_reason:
        if not quiet:
            _print_stage_header(6, TOTAL_STAGES, title, status="跳过")
            _print_io("原因", [skip_reason])
        return

    max_chunks = getattr(answer_generator, "max_chunks", None) or len(results)
    used = results[:max_chunks]
    threshold = getattr(answer_generator, "confidence_threshold", None)

    if not quiet:
        _print_stage_header(6, TOTAL_STAGES, title)
        _print_io("输入", [
            f"query = \"{query}\"",
            f"chunks = 融合结果前 {len(used)} 块: {[r.chunk_id for r in used]}",
        ])

    _t0 = time.monotonic()
    try:
        answer = answer_generator.generate(query=query, chunks=results, trace=trace)
    except Exception as e:
        if not quiet:
            print(f" [WARN] 答案生成失败: {e}")
        return
    gen_ms = (time.monotonic() - _t0) * 1000.0

    if quiet:
        return

    out_lines = []
    if answer.confidence is not None:
        line = f"confidence = {answer.confidence:.4f}"
        if threshold:
            relation = "≥ 达标" if answer.confidence >= threshold else "< 低于阈值 → 拒答标记"
            line += f"  (阈值 {threshold}，{relation})"
        out_lines.append(line)
    if answer.refusal_reason:
        out_lines.append(f"refusal = {answer.refusal_reason}")
    _print_io("输出", out_lines or ["(无结构化输出)"])
    print()
    print(" 答案内容:")
    for line in (answer.content or "").splitlines():
        print(f"   {line}")
    _print_ms(trace, "answer_generation", fallback_ms=gen_ms)


# ---------------------------------------------------------------------------
# Component building / query runner
# ---------------------------------------------------------------------------


def _build_components(settings, collection: str):
    vector_store = VectorStoreFactory.create(
        settings,
        collection_name=collection,
    )

    embedding_client = EmbeddingFactory.create(settings)
    dense_retriever = create_dense_retriever(
        settings=settings,
        embedding_client=embedding_client,
        vector_store=vector_store,
    )

    bm25_indexer = BM25Indexer(index_dir=f"data/db/bm25/{collection}")
    sparse_retriever = create_sparse_retriever(
        settings=settings,
        bm25_indexer=bm25_indexer,
        vector_store=vector_store,
    )
    # Ensure sparse retriever queries the correct collection index
    sparse_retriever.default_collection = collection

    query_processor = QueryProcessor()
    hybrid_search = create_hybrid_search(
        settings=settings,
        query_processor=query_processor,
        dense_retriever=dense_retriever,
        sparse_retriever=sparse_retriever,
    )

    reranker = create_core_reranker(settings=settings)

    return hybrid_search, reranker


def _run_query(
    hybrid_search,
    reranker,
    query: str,
    top_k: int | None,
    use_rerank: bool,
    quiet: bool,
    disable_answer: bool,
    answer_generator=None,
) -> int:
    trace = TraceContext(trace_type="query")
    trace.metadata["query"] = query[:200]
    trace.metadata["top_k"] = top_k

    try:
        hybrid_result = hybrid_search.search(
            query=query,
            top_k=top_k,
            filters=None,
            trace=trace,
            return_details=True,
        )
    except Exception as e:
        print(f"[FAIL] Hybrid search failed: {e}")
        TraceCollector().collect(trace)
        return 1

    results = hybrid_result.results

    if hybrid_result.used_fallback:
        print(f"\n[WARN] HybridSearch 降级: dense_error={hybrid_result.dense_error}, "
              f"sparse_error={hybrid_result.sparse_error}")

    if not results:
        print("\n[INFO] 未找到相关文档，请先运行 ingest.py 摄取数据。")
        trace.finish()
        TraceCollector().collect(trace)
        return 0

    if not quiet:
        _stage1_preprocessing(hybrid_result, trace)
        _stage2_dense(hybrid_result, hybrid_search, trace)
        _stage3_sparse(hybrid_result, hybrid_search, trace)
        _stage4_fusion(hybrid_result, hybrid_search, trace)

    results = _stage5_rerank(
        reranker, query, results, disable_rerank=not use_rerank, trace=trace, quiet=quiet,
    )
    _stage6_answer(
        answer_generator, query, results, disable_answer=disable_answer, trace=trace, quiet=quiet,
    )

    _print_results(results, top_k=len(results))

    trace.finish()
    TraceCollector().collect(trace)

    total_ms = trace.elapsed_ms()
    print(f"\n[SUMMARY] 总耗时 {total_ms:.0f} ms  |  trace_id={trace.trace_id}")
    return 0


def main() -> int:
    args = parse_args()

    # Keep the console readable: silence INFO run logs unless --debug.
    if not args.debug:
        logging.getLogger().setLevel(logging.WARNING)
        logging.getLogger("jieba").setLevel(logging.ERROR)

    # Load configuration
    try:
        config_path = Path(args.config)
        if not config_path.exists():
            print(f"[FAIL] Configuration file not found: {config_path}")
            return 2
        settings = load_settings(str(config_path))
        print(f"[OK] Configuration loaded from: {config_path}")
    except Exception as e:
        print(f"[FAIL] Failed to load configuration: {e}")
        return 2

    try:
        hybrid_search, reranker = _build_components(settings, args.collection)
    except Exception as e:
        print(f"[FAIL] Failed to initialize query components: {e}")
        logger.exception("Query initialization failed")
        return 2

    use_rerank = not args.no_rerank

    # Build the answer generator (NoneAnswerGenerator when disabled). Failures
    # building it (e.g. missing config) degrade to retrieval-only output.
    answer_generator = None
    if not args.no_answer:
        try:
            answer_generator = AnswerGeneratorFactory.create(settings)
        except Exception as e:
            print(f"[WARN] Answer generator unavailable: {e}")

    # Run header with the pipeline overview
    _print_overview(hybrid_search, reranker, answer_generator, settings, args)

    # Single-query mode
    return _run_query(
        hybrid_search=hybrid_search,
        reranker=reranker,
        query=args.query,
        top_k=args.top_k,
        use_rerank=use_rerank,
        quiet=args.quiet,
        disable_answer=args.no_answer,
        answer_generator=answer_generator,
    )


if __name__ == "__main__":
    sys.exit(main())
