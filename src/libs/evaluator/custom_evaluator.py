"""Custom evaluator implementation for lightweight metrics.

This evaluator computes simple, deterministic metrics such as hit rate and MRR.
It is designed for fast regression checks and sanity validation.

Metric set (Phase 3):
- ``hit_rate`` / ``mrr``: exact chunk-id matching against ``expected_chunk_ids``.
- ``source_hit_rate`` / ``source_mrr``: source-level matching against
  ``expected_sources`` (document basenames).  This is the *primary* signal:
  chunk ids embed an absolute-path hash and an LLM-refined-text hash, so they
  are not portable across machines, while source basenames are.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from src.libs.evaluator.base_evaluator import BaseEvaluator


class CustomEvaluator(BaseEvaluator):
    """Custom evaluator for lightweight metrics.

    The evaluator expects retrieved chunks to contain an identifier field.
    Supported id fields: id, chunk_id, document_id, doc_id.

    Metric policy: explicit ``metrics=`` raises ``ValueError`` on unsupported
    names (faithfulness belongs to the ragas backend); metrics derived from
    ``settings.evaluation.metrics`` are silently filtered to the supported set
    so a composite config that mixes backends does not crash.
    """

    SUPPORTED_METRICS = {"hit_rate", "mrr", "source_hit_rate", "source_mrr"}
    _ID_FIELDS = ("id", "chunk_id", "document_id", "doc_id")

    def __init__(
        self,
        settings: Any = None,
        metrics: Sequence[str] | None = None,
        **kwargs: Any,
    ) -> None:
        self.settings = settings
        self.kwargs = kwargs

        explicit = metrics is not None
        if metrics is None:
            metrics = self._metrics_from_settings(settings)

        normalized = [str(metric).strip().lower() for metric in (metrics or [])]
        if not normalized:
            normalized = ["hit_rate", "mrr"]

        if explicit:
            # Explicit metrics: fail fast so misconfigured backends surface.
            unsupported = [m for m in normalized if m not in self.SUPPORTED_METRICS]
            if unsupported:
                raise ValueError(
                    "Unsupported custom metrics: "
                    f"{', '.join(unsupported)}. Supported: {', '.join(sorted(self.SUPPORTED_METRICS))}"
                )
        else:
            # Settings-derived metrics: filter to the supported set so metrics
            # meant for other backends (e.g. faithfulness for ragas) are ignored.
            normalized = [m for m in normalized if m in self.SUPPORTED_METRICS]
            if not normalized:
                normalized = ["hit_rate", "mrr"]

        self.metrics = normalized

    def evaluate(
        self,
        query: str,
        retrieved_chunks: list[Any],
        generated_answer: str | None = None,
        ground_truth: Any | None = None,
        trace: Any | None = None,
        **kwargs: Any,
    ) -> dict[str, float]:
        """Compute requested metrics for the given retrieval results.

        Args:
            query: The user query string.
            retrieved_chunks: Retrieved chunks or records.
            generated_answer: Optional generated answer (unused).
            ground_truth: Ground truth ids or structure.
            trace: Optional TraceContext (unused).
            **kwargs: Additional parameters (unused).

        Returns:
            Dictionary of metric name to float value.
        """
        self.validate_query(query)
        self.validate_retrieved_chunks(retrieved_chunks)

        retrieved_ids = self._extract_ids(retrieved_chunks, label="retrieved_chunks")
        ground_truth_ids = self._extract_ground_truth_ids(ground_truth)

        results: dict[str, float] = {}

        if "hit_rate" in self.metrics:
            results["hit_rate"] = self._compute_hit_rate(retrieved_ids, ground_truth_ids)
        if "mrr" in self.metrics:
            results["mrr"] = self._compute_mrr(retrieved_ids, ground_truth_ids)
        if "source_hit_rate" in self.metrics or "source_mrr" in self.metrics:
            retrieved_sources = self._extract_sources(retrieved_chunks)
            ground_truth_sources = self._extract_ground_truth_sources(ground_truth)
            if "source_hit_rate" in self.metrics:
                results["source_hit_rate"] = self._compute_hit_rate(
                    retrieved_sources, ground_truth_sources
                )
            if "source_mrr" in self.metrics:
                results["source_mrr"] = self._compute_mrr(
                    retrieved_sources, ground_truth_sources
                )

        return results

    def _metrics_from_settings(self, settings: Any) -> list[str]:
        """Extract metrics list from settings if available."""
        if settings is None:
            return []
        metrics = getattr(getattr(settings, "evaluation", None), "metrics", None)
        if metrics is None:
            return []
        return [str(metric) for metric in metrics]

    def _extract_ground_truth_ids(self, ground_truth: Any | None) -> list[str]:
        """Extract ground truth ids from various input shapes."""
        if ground_truth is None:
            return []
        if isinstance(ground_truth, str):
            return [ground_truth]
        if isinstance(ground_truth, dict):
            ids = ground_truth.get("ids")
            if isinstance(ids, list):
                return self._extract_ids(ids, label="ground_truth.ids")
            # A bare dict may carry an id field directly (backward compat).
            if any(field in ground_truth for field in self._ID_FIELDS):
                return self._extract_ids([ground_truth], label="ground_truth")
            # Full ground-truth dict without ids (e.g. {"sources": ...}) → empty.
            return []
        if isinstance(ground_truth, list):
            return self._extract_ids(ground_truth, label="ground_truth")

        raise ValueError(
            f"Unsupported ground_truth type: {type(ground_truth).__name__}. "
            "Expected str, dict, list, or None."
        )

    def _extract_ids(self, items: Iterable[Any], label: str) -> list[str]:
        """Extract ids from a list of items."""
        ids: list[str] = []
        for index, item in enumerate(items):
            if isinstance(item, str):
                ids.append(item)
                continue
            if isinstance(item, dict):
                for field in self._ID_FIELDS:
                    if field in item:
                        ids.append(str(item[field]))
                        break
                else:
                    raise ValueError(
                        f"Missing id field in {label}[{index}]. "
                        f"Expected one of {', '.join(self._ID_FIELDS)}"
                    )
                continue
            if hasattr(item, "id"):
                ids.append(str(getattr(item, "id")))
                continue
            if hasattr(item, "chunk_id"):
                # RetrievalResult exposes .chunk_id (not .id) — this was a real
                # cause of always-empty metrics in the golden evaluation path.
                ids.append(str(getattr(item, "chunk_id")))
                continue

            raise ValueError(
                f"Unable to extract id from {label}[{index}] of type "
                f"{type(item).__name__}"
            )

        return ids

    def _extract_ground_truth_sources(self, ground_truth: Any | None) -> list[str]:
        """Extract ground-truth source names from various input shapes."""
        if ground_truth is None:
            return []
        if isinstance(ground_truth, str):
            return [self._normalize_source(ground_truth)]
        if isinstance(ground_truth, dict):
            sources = ground_truth.get("sources")
            if isinstance(sources, list):
                return [self._normalize_source(s) for s in sources]
            return []
        if isinstance(ground_truth, list):
            return [self._normalize_source(s) for s in ground_truth]
        return []

    def _extract_sources(self, chunks: Iterable[Any]) -> list[str]:
        """Extract source basenames from retrieved chunks.

        Reads ``metadata["source_path"]`` (the key written by
        ``VectorUpserter``) or a top-level ``source_path``, then keeps only the
        basename so matching is portable across machines.
        """
        sources: list[str] = []
        for chunk in chunks:
            source = self._extract_source_path(chunk)
            if source:
                sources.append(self._normalize_source(source))
        return sources

    @staticmethod
    def _extract_source_path(chunk: Any) -> str | None:
        """Return the raw source path of a chunk, if any."""
        if isinstance(chunk, dict):
            metadata = chunk.get("metadata") or {}
            return metadata.get("source_path") or chunk.get("source_path")
        metadata = getattr(chunk, "metadata", None) or {}
        path = metadata.get("source_path")
        if path:
            return str(path)
        return getattr(chunk, "source_path", None)

    @staticmethod
    def _normalize_source(value: Any) -> str:
        """Normalise a source path/name to its basename for portable matching."""
        return Path(str(value)).name

    def _compute_hit_rate(self, retrieved_ids: Sequence[str], ground_truth_ids: Sequence[str]) -> float:
        """Compute hit rate (binary)."""
        if not ground_truth_ids:
            return 0.0
        return 1.0 if any(item in ground_truth_ids for item in retrieved_ids) else 0.0

    def _compute_mrr(self, retrieved_ids: Sequence[str], ground_truth_ids: Sequence[str]) -> float:
        """Compute Mean Reciprocal Rank (MRR)."""
        if not ground_truth_ids:
            return 0.0
        for rank, item in enumerate(retrieved_ids, start=1):
            if item in ground_truth_ids:
                return 1.0 / rank
        return 0.0
