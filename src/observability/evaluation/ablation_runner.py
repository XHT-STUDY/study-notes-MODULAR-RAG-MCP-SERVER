"""Ablation runner: compare retrieval strategy variants on the same golden set.

Runs one evaluation per variant — dense-only, sparse-only, hybrid, and
hybrid+rerank — reusing a single set of retrievers/fusion so differences are
attributable to the retrieval strategy, not to component drift.

Design notes:
- ``HybridSearchConfig._extract_config`` hardcodes ``enable_dense`` /
  ``enable_sparse`` to True, so variants cannot be toggled from YAML.  Each
  variant therefore constructs its own ``HybridSearch`` with an explicit
  ``config=`` (the ``create_hybrid_search()`` factory does not accept one).
- Output is a single dict with a per-variant breakdown plus a metric×variant
  comparison matrix, rather than N separate run files.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from dataclasses import replace
from typing import Any

from src.core.query_engine.hybrid_search import HybridSearch
from src.observability.evaluation.eval_runner import EvalReport, EvalRunner

ABLATION_VARIANTS = ["dense", "sparse", "hybrid", "hybrid_rerank"]


def run_ablations(
    settings: Any,
    build_search: Callable[[], Any],
    evaluator: Any,
    test_set_path: str,
    top_k: int = 10,
    collection: str | None = None,
    reranker: Any = None,
) -> dict[str, EvalReport]:
    """Run one evaluation per retrieval variant on the same golden set.

    Args:
        settings: Application settings (forwarded to EvalRunner).
        build_search: Zero-argument callable returning the base ``HybridSearch``
            (the default hybrid configuration).  The caller owns the
            retriever/query_processor/fusion assembly so every variant shares
            the same components.
        evaluator: BaseEvaluator instance scored for every variant.
        test_set_path: Path to the golden test set JSON.
        top_k: Number of chunks to retrieve per query.
        collection: Optional collection name filter.
        reranker: Optional CoreReranker used only by the ``hybrid_rerank``
            variant (when ``is_enabled``).

    Returns:
        Mapping of variant name -> EvalReport.
    """
    base_search = build_search()
    base_config = base_search.config

    variants: dict[str, EvalReport] = {}
    for name in ABLATION_VARIANTS:
        if name == "dense":
            search = _variant_search(
                base_search,
                config=replace(base_config, enable_dense=True, enable_sparse=False),
            )
        elif name == "sparse":
            search = _variant_search(
                base_search,
                config=replace(base_config, enable_dense=False, enable_sparse=True),
            )
        else:  # "hybrid" / "hybrid_rerank"
            search = base_search

        variant_reranker = reranker if name == "hybrid_rerank" else None
        runner = EvalRunner(
            settings=settings,
            hybrid_search=search,
            evaluator=evaluator,
            reranker=variant_reranker,
        )
        report = runner.run(
            test_set_path=test_set_path,
            top_k=top_k,
            collection=collection,
        )
        report.variant = name
        variants[name] = report

    return variants


def _variant_search(base: HybridSearch, config: Any) -> HybridSearch:
    """Build a HybridSearch that shares base components but overrides config."""
    return HybridSearch(
        settings=None,
        query_processor=base.query_processor,
        dense_retriever=base.dense_retriever,
        sparse_retriever=base.sparse_retriever,
        fusion=base.fusion,
        config=config,
    )


def ablation_to_dict(variants: dict[str, EvalReport]) -> dict[str, Any]:
    """Combine per-variant reports into a single ablation dict.

    Returns:
        ``{run_id, generated_at, variants: {name: report_dict},
        comparison: {metric: {variant: value}}}`` — ``comparison`` is the
        metric×variant matrix used for the HTML comparison table.
    """
    ordered = [name for name in ABLATION_VARIANTS if name in variants]

    comparison: dict[str, dict[str, float]] = {}
    for name in ordered:
        report = variants[name]
        for metric, value in report.aggregate_metrics.items():
            comparison.setdefault(metric, {})[name] = round(value, 4)

    return {
        "run_id": uuid.uuid4().hex[:8],
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "variants": {name: variants[name].to_dict() for name in ordered},
        "comparison": comparison,
    }
