"""Unit tests for HTML report rendering (report_html.py)."""

from __future__ import annotations

from typing import Any

from src.observability.evaluation.report_html import (
    render_ablation_html,
    render_report_html,
)


def _sample_report() -> dict[str, Any]:
    return {
        "run_id": "abc12345",
        "timestamp": "2026-08-10 12:00:00",
        "evaluator_name": "CustomEvaluator",
        "test_set_path": "tests/fixtures/golden_test_set.json",
        "collection": "eval_default",
        "variant": "hybrid",
        "query_count": 1,
        "total_elapsed_ms": 123.4,
        "aggregate_metrics": {"hit_rate": 1.0, "source_hit_rate": 1.0, "mrr": 0.5},
        "query_results": [
            {
                "query": "What is RAG?",
                "retrieved_chunk_ids": ["c1", "c2"],
                "generated_answer": "RAG is Retrieval Augmented Generation.",
                "metrics": {"hit_rate": 1.0},
                "elapsed_ms": 12.3,
            }
        ],
        "config_snapshot": {
            "collection": "eval_default",
            "top_k": 10,
            "retrieval": {"dense_top_k": 20},
        },
    }


class TestRenderReportHtml:
    def test_contains_header_and_metadata(self) -> None:
        html = render_report_html(_sample_report())
        assert html.startswith("<!doctype html>")
        assert "Evaluation Report" in html
        assert "abc12345" in html
        assert "2026-08-10 12:00:00" in html
        assert "CustomEvaluator" in html

    def test_contains_aggregate_and_source_metrics(self) -> None:
        html = render_report_html(_sample_report())
        assert "source_hit_rate" in html
        assert "hit_rate" in html
        assert "1.0000" in html

    def test_contains_query_details(self) -> None:
        html = render_report_html(_sample_report())
        assert "What is RAG?" in html
        assert "c1" in html
        assert "RAG is Retrieval Augmented Generation." in html

    def test_contains_config_snapshot(self) -> None:
        html = render_report_html(_sample_report())
        assert "Config Snapshot" in html
        assert "dense_top_k" in html

    def test_escapes_user_text(self) -> None:
        report = _sample_report()
        report["query_results"][0]["query"] = "<script>alert(1)</script>"
        html = render_report_html(report)
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_handles_minimal_report(self) -> None:
        html = render_report_html({"evaluator_name": "None", "query_results": []})
        assert "(no metrics)" in html


class TestRenderAblationHtml:
    def _sample_ablation(self) -> dict[str, Any]:
        return {
            "run_id": "x1",
            "generated_at": "2026-08-10",
            "variants": {
                "dense": {"aggregate_metrics": {"hit_rate": 0.5}},
                "sparse": {"aggregate_metrics": {"hit_rate": 0.4}},
                "hybrid": {"aggregate_metrics": {"hit_rate": 0.9}},
                "hybrid_rerank": {"aggregate_metrics": {"hit_rate": 0.95}},
            },
            "comparison": {
                "hit_rate": {
                    "dense": 0.5,
                    "sparse": 0.4,
                    "hybrid": 0.9,
                    "hybrid_rerank": 0.95,
                }
            },
        }

    def test_contains_all_variants(self) -> None:
        html = render_ablation_html(self._sample_ablation())
        assert "Ablation Report" in html
        for variant in ("dense", "sparse", "hybrid", "hybrid_rerank"):
            assert variant in html

    def test_contains_comparison_matrix(self) -> None:
        html = render_ablation_html(self._sample_ablation())
        assert "Metric × Variant Comparison" in html
        assert "0.9500" in html

    def test_empty_comparison_graceful(self) -> None:
        html = render_ablation_html(
            {"run_id": "x", "generated_at": "t", "variants": {}, "comparison": {}}
        )
        assert "(no comparison data)" in html
