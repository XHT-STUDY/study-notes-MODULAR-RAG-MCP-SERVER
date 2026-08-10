"""Unit tests for the ablation runner (ablation_runner.py)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from src.core.query_engine.hybrid_search import HybridSearch, HybridSearchConfig
from src.observability.evaluation.ablation_runner import (
    ABLATION_VARIANTS,
    ablation_to_dict,
    run_ablations,
)
from src.observability.evaluation.eval_runner import EvalReport


def _make_base_search() -> HybridSearch:
    """Real HybridSearch with stub components — exercises real config plumbing."""
    return HybridSearch(
        config=HybridSearchConfig(),
        query_processor=MagicMock(),
        dense_retriever=MagicMock(),
        sparse_retriever=MagicMock(),
        fusion=MagicMock(),
    )


class _RecordingEvalRunner:
    """Stands in for EvalRunner to capture per-variant constructor kwargs."""

    def __init__(self, captured: list[dict[str, Any]], **kwargs: Any) -> None:
        captured.append(kwargs)

    def run(self, test_set_path: str, top_k: int = 10, collection: Any = None) -> EvalReport:
        return EvalReport()


class TestRunAblations:
    def test_build_search_called_once_and_all_variants_produced(
        self, tmp_path, monkeypatch
    ) -> None:
        base = _make_base_search()
        build = MagicMock(return_value=base)
        captured: list[dict[str, Any]] = []
        monkeypatch.setattr(
            "src.observability.evaluation.ablation_runner.EvalRunner",
            lambda **kwargs: _RecordingEvalRunner(captured, **kwargs),
        )

        variants = run_ablations(
            settings=None,
            build_search=build,
            evaluator=MagicMock(),
            test_set_path=str(tmp_path / "g.json"),
            top_k=5,
            collection="eval",
            reranker=MagicMock(),
        )

        build.assert_called_once()
        assert set(variants) == set(ABLATION_VARIANTS)

    def test_variant_configs_and_reranker_injection(self, tmp_path, monkeypatch) -> None:
        base = _make_base_search()
        reranker = MagicMock()
        reranker.is_enabled = True
        captured: list[dict[str, Any]] = []
        monkeypatch.setattr(
            "src.observability.evaluation.ablation_runner.EvalRunner",
            lambda **kwargs: _RecordingEvalRunner(captured, **kwargs),
        )

        run_ablations(
            settings=None,
            build_search=lambda: base,
            evaluator=MagicMock(),
            test_set_path=str(tmp_path / "g.json"),
            top_k=5,
            collection="eval",
            reranker=reranker,
        )

        # dense: only dense enabled, no reranker
        dense = captured[0]["hybrid_search"]
        assert dense.config.enable_dense is True
        assert dense.config.enable_sparse is False
        assert captured[0]["reranker"] is None

        # sparse: only sparse enabled, no reranker
        sparse = captured[1]["hybrid_search"]
        assert sparse.config.enable_dense is False
        assert sparse.config.enable_sparse is True
        assert captured[1]["reranker"] is None

        # hybrid: both enabled, reuses base search
        assert captured[2]["hybrid_search"] is base
        assert captured[2]["reranker"] is None

        # hybrid_rerank: both enabled + reranker injected
        assert captured[3]["hybrid_search"] is base
        assert captured[3]["reranker"] is reranker

    def test_variant_set_on_each_report(self, tmp_path, monkeypatch) -> None:
        captured: list[dict[str, Any]] = []
        monkeypatch.setattr(
            "src.observability.evaluation.ablation_runner.EvalRunner",
            lambda **kwargs: _RecordingEvalRunner(captured, **kwargs),
        )

        variants = run_ablations(
            settings=None,
            build_search=_make_base_search,
            evaluator=MagicMock(),
            test_set_path=str(tmp_path / "g.json"),
        )

        assert variants["dense"].variant == "dense"
        assert variants["sparse"].variant == "sparse"
        assert variants["hybrid"].variant == "hybrid"
        assert variants["hybrid_rerank"].variant == "hybrid_rerank"


class TestAblationToDict:
    def test_comparison_matrix(self) -> None:
        reports = {
            "dense": EvalReport(variant="dense", aggregate_metrics={"hit_rate": 0.5, "mrr": 0.25}),
            "sparse": EvalReport(variant="sparse", aggregate_metrics={"hit_rate": 0.4}),
            "hybrid": EvalReport(variant="hybrid", aggregate_metrics={"hit_rate": 0.9, "mrr": 0.8}),
            "hybrid_rerank": EvalReport(
                variant="hybrid_rerank", aggregate_metrics={"hit_rate": 0.95, "mrr": 0.85}
            ),
        }

        d = ablation_to_dict(reports)

        assert d["run_id"]
        assert d["generated_at"]
        assert set(d["variants"]) == set(ABLATION_VARIANTS)
        assert d["comparison"]["hit_rate"] == {
            "dense": 0.5,
            "sparse": 0.4,
            "hybrid": 0.9,
            "hybrid_rerank": 0.95,
        }
        assert d["comparison"]["mrr"]["hybrid_rerank"] == 0.85

    def test_missing_variants_excluded(self) -> None:
        reports = {"dense": EvalReport(variant="dense", aggregate_metrics={"hit_rate": 0.5})}

        d = ablation_to_dict(reports)

        assert set(d["variants"]) == {"dense"}
        assert d["comparison"] == {"hit_rate": {"dense": 0.5}}
