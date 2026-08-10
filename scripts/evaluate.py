#!/usr/bin/env python
"""Evaluation script for Modular RAG MCP Server.

Runs batch evaluation against a golden test set and outputs a metrics report.
Phase 3 adds: JSON + HTML report files under ``reports/`` and an ``--ablate``
mode comparing dense / sparse / hybrid / hybrid+rerank strategies.

Usage:
    # Run with default settings (custom evaluator)
    python scripts/evaluate.py

    # Specify a custom golden test set
    python scripts/evaluate.py --test-set path/to/golden.json

    # Use a specific collection
    python scripts/evaluate.py --collection technical_docs

    # JSON output
    python scripts/evaluate.py --json

    # Compare retrieval strategies (dense / sparse / hybrid / hybrid+rerank)
    python scripts/evaluate.py --ablate

Exit codes:
    0 - Success
    1 - Evaluation failure
    2 - Configuration error
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Set UTF-8 encoding for Windows console
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Run RAG evaluation against a golden test set."
    )
    parser.add_argument(
        "--test-set",
        default="tests/fixtures/golden_test_set.json",
        help="Path to golden test set JSON file (default: tests/fixtures/golden_test_set.json)",
    )
    parser.add_argument(
        "--collection",
        default=None,
        help="Collection name to search within.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=10,
        help="Number of chunks to retrieve per query (default: 10).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON instead of formatted text.",
    )
    parser.add_argument(
        "--no-search",
        action="store_true",
        help="Skip retrieval (evaluate with mock chunks for testing).",
    )
    parser.add_argument(
        "--report-dir",
        default="reports",
        help="Directory for eval_*.json / eval_*.html files (default: reports).",
    )
    parser.add_argument(
        "--ablate",
        action="store_true",
        help="Run ablation comparison: dense / sparse / hybrid / hybrid+rerank.",
    )
    return parser.parse_args()


def _create_reranker(settings):
    """Create the CoreReranker if enabled, else None."""
    try:
        from src.core.query_engine.reranker import create_core_reranker
        reranker = create_core_reranker(settings=settings)
        return reranker if reranker.is_enabled else None
    except Exception as exc:
        print(f"⚠️  Reranker unavailable (proceeding without): {exc}")
        return None


def _create_hybrid_search(settings, collection: str):
    """Assemble the base HybridSearch for a collection.

    Returns the HybridSearch instance, or None on failure.  The assembly is
    reused verbatim by the ablation runner so every variant shares the same
    retriever/fusion components.
    """
    try:
        from src.core.query_engine.dense_retriever import create_dense_retriever
        from src.core.query_engine.hybrid_search import create_hybrid_search
        from src.core.query_engine.query_processor import QueryProcessor
        from src.core.query_engine.sparse_retriever import create_sparse_retriever
        from src.ingestion.storage.bm25_indexer import BM25Indexer
        from src.libs.embedding.embedding_factory import EmbeddingFactory
        from src.libs.vector_store.vector_store_factory import VectorStoreFactory

        vector_store = VectorStoreFactory.create(
            settings, collection_name=collection,
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
        sparse_retriever.default_collection = collection

        query_processor = QueryProcessor()
        return create_hybrid_search(
            settings=settings,
            query_processor=query_processor,
            dense_retriever=dense_retriever,
            sparse_retriever=sparse_retriever,
        )
    except Exception as exc:
        print(f"⚠️  Failed to initialize search (running without retrieval): {exc}")
        return None


def _write_report_files(report_dict: dict, report_dir: Path) -> None:
    """Persist an evaluation report as JSON + HTML."""
    from src.observability.evaluation.report_html import render_report_html

    report_dir.mkdir(parents=True, exist_ok=True)
    run_id = report_dict.get("run_id", "run")

    json_path = report_dir / f"eval_{run_id}.json"
    json_path.write_text(
        json.dumps(report_dict, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    html_path = report_dir / f"eval_{run_id}.html"
    html_path.write_text(render_report_html(report_dict), encoding="utf-8")

    print(f"📄 Report written: {json_path}")
    print(f"🖥️  HTML written:  {html_path}")


def _run_single(args, settings, evaluator, hybrid_search) -> dict:
    """Run a single evaluation pass and return the report dict."""
    from src.observability.evaluation.eval_runner import EvalRunner

    runner = EvalRunner(
        settings=settings,
        hybrid_search=hybrid_search,
        evaluator=evaluator,
    )
    report = runner.run(
        test_set_path=args.test_set,
        top_k=args.top_k,
        collection=args.collection,
    )
    return report.to_dict()


def _run_ablate(args, settings, evaluator, hybrid_search) -> dict:
    """Run the ablation comparison and return the combined ablation dict."""
    from src.observability.evaluation.ablation_runner import (
        ablation_to_dict,
        run_ablations,
    )

    reranker = _create_reranker(settings)
    variants = run_ablations(
        settings=settings,
        build_search=lambda: hybrid_search,
        evaluator=evaluator,
        test_set_path=args.test_set,
        top_k=args.top_k,
        collection=args.collection,
        reranker=reranker,
    )
    return ablation_to_dict(variants)


def main() -> int:
    """Main entry point."""
    args = parse_args()

    try:
        from src.core.settings import load_settings
        from src.libs.evaluator.evaluator_factory import EvaluatorFactory

        settings = load_settings()
    except Exception as exc:
        print(f"❌ Configuration error: {exc}", file=sys.stderr)
        return 2

    # Create evaluator from config
    try:
        evaluator = EvaluatorFactory.create(settings)
        evaluator_name = type(evaluator).__name__
    except Exception as exc:
        print(f"❌ Failed to create evaluator: {exc}", file=sys.stderr)
        return 2

    # Create HybridSearch (unless --no-search)
    hybrid_search = None
    collection = args.collection or "default"
    if not args.no_search:
        hybrid_search = _create_hybrid_search(settings, collection)
        if hybrid_search is not None:
            print(f"✅ HybridSearch initialized for collection: {collection}")

    if args.ablate:
        if hybrid_search is None:
            print("❌ Ablation requires retrieval; cannot build HybridSearch.", file=sys.stderr)
            return 1
        print(f"\n🔍 Running ablation with {evaluator_name}...")
        print(f"📄 Test set: {args.test_set}")
        print(f"🔢 Top-K: {args.top_k}\n")
        try:
            ablation_dict = _run_ablate(args, settings, evaluator, hybrid_search)
        except Exception as exc:
            print(f"❌ Ablation failed: {exc}", file=sys.stderr)
            return 1

        if args.json:
            print(json.dumps(ablation_dict, indent=2, ensure_ascii=False))
        else:
            _print_ablation(ablation_dict)

        _write_ablation_files(ablation_dict, Path(args.report_dir))
        return 0

    # Single run
    try:
        print(f"\n🔍 Running evaluation with {evaluator_name}...")
        print(f"📄 Test set: {args.test_set}")
        print(f"🔢 Top-K: {args.top_k}\n")

        report_dict = _run_single(args, settings, evaluator, hybrid_search)
    except Exception as exc:
        print(f"❌ Evaluation failed: {exc}", file=sys.stderr)
        return 1

    # Output results
    if args.json:
        print(json.dumps(report_dict, indent=2, ensure_ascii=False))
    else:
        _print_report(report_dict)

    _write_report_files(report_dict, Path(args.report_dir))

    return 0


def _write_ablation_files(ablation_dict: dict, report_dir: Path) -> None:
    """Persist an ablation dict as JSON + HTML."""
    from src.observability.evaluation.report_html import render_ablation_html

    report_dir.mkdir(parents=True, exist_ok=True)
    run_id = ablation_dict.get("run_id", "ablate")

    json_path = report_dir / f"eval_{run_id}_ablate.json"
    json_path.write_text(
        json.dumps(ablation_dict, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    html_path = report_dir / f"eval_{run_id}_ablate.html"
    html_path.write_text(render_ablation_html(ablation_dict), encoding="utf-8")

    print(f"📄 Ablation report written: {json_path}")
    print(f"🖥️  Ablation HTML written:  {html_path}")


def _print_report(report: dict) -> None:
    """Print formatted evaluation report."""
    print("=" * 60)
    print("  EVALUATION REPORT")
    print("=" * 60)
    print(f"  Run ID:    {report.get('run_id', '—')}")
    print(f"  Timestamp: {report.get('timestamp', '—')}")
    print(f"  Evaluator: {report.get('evaluator_name', '—')}")
    print(f"  Test Set:  {report.get('test_set_path', '—')}")
    print(f"  Collection:{report.get('collection', '—')}")
    print(f"  Queries:   {report.get('query_count', 0)}")
    print(f"  Time:      {report.get('total_elapsed_ms', 0):.0f} ms")
    print()

    # Aggregate metrics
    print("─" * 60)
    print("  AGGREGATE METRICS")
    print("─" * 60)
    agg = report.get("aggregate_metrics", {})
    if agg:
        for metric, value in sorted(agg.items()):
            bar = "█" * int(value * 20) + "░" * (20 - int(value * 20))
            print(f"  {metric:<25s} {bar} {value:.4f}")
    else:
        print("  (no metrics computed)")
    print()

    # Per-query details
    print("─" * 60)
    print("  PER-QUERY RESULTS")
    print("─" * 60)
    for i, qr in enumerate(report.get("query_results", []), 1):
        print(f"\n  [{i}] {qr.get('query', '—')}")
        print(f"      Retrieved: {len(qr.get('retrieved_chunk_ids', []))} chunks")
        metrics = qr.get("metrics", {})
        if metrics:
            for metric, value in sorted(metrics.items()):
                print(f"      {metric}: {value:.4f}")
        else:
            print("      (no metrics)")
        print(f"      Time: {qr.get('elapsed_ms', 0):.0f} ms")

    print()
    print("=" * 60)


def _print_ablation(ablation: dict) -> None:
    """Print the ablation comparison matrix."""
    print("=" * 60)
    print("  ABLATION REPORT")
    print("=" * 60)
    print(f"  Run ID: {ablation.get('run_id', '—')}")
    print()

    variants = list(ablation.get("variants", {}).keys())
    comparison = ablation.get("comparison", {})
    if not comparison or not variants:
        print("  (no comparison data)")
        return

    # Header
    print(f"  {'metric':<20s}" + "".join(f"{v:>16s}" for v in variants))
    print("  " + "-" * (20 + 16 * len(variants)))
    for metric, values in sorted(comparison.items()):
        row = f"  {metric:<20s}"
        for v in variants:
            row += f"{values.get(v, 0.0):>16.4f}"
        print(row)
    print()
    print("=" * 60)


if __name__ == "__main__":
    sys.exit(main())
