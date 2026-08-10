"""Unit tests for RagasEvaluator.

Tests verify:
- Initialization with valid/invalid metrics
- ImportError handling when ragas is not installed
- Input validation (missing answer, empty query, etc.)
- Metric extraction from settings
- Text extraction from various chunk formats

Note: Actual Ragas evaluation (LLM calls) is mocked to keep unit tests fast
and deterministic.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch, PropertyMock
from typing import Any, Dict

import pytest


class TestRagasEvaluatorInit:
    """Tests for RagasEvaluator initialisation."""

    def test_init_default_metrics(self) -> None:
        from src.observability.evaluation.ragas_evaluator import RagasEvaluator

        evaluator = RagasEvaluator()
        assert set(evaluator._metric_names) == {
            "answer_correctness",
            "answer_relevancy",
            "context_precision",
            "faithfulness",
        }

    def test_init_custom_metrics(self) -> None:
        from src.observability.evaluation.ragas_evaluator import RagasEvaluator

        evaluator = RagasEvaluator(metrics=["faithfulness"])
        assert evaluator._metric_names == ["faithfulness"]

    def test_init_unsupported_metric_raises(self) -> None:
        from src.observability.evaluation.ragas_evaluator import RagasEvaluator

        with pytest.raises(ValueError, match="Unsupported ragas metrics"):
            RagasEvaluator(metrics=["hit_rate"])

    def test_init_reads_metrics_from_settings(self) -> None:
        from src.observability.evaluation.ragas_evaluator import RagasEvaluator

        settings = MagicMock()
        settings.evaluation.metrics = ["faithfulness", "answer_relevancy", "hit_rate"]

        evaluator = RagasEvaluator(settings=settings)
        # hit_rate is not a ragas metric, should be filtered out
        assert "hit_rate" not in evaluator._metric_names
        assert "faithfulness" in evaluator._metric_names
        assert "answer_relevancy" in evaluator._metric_names

    def test_init_no_settings_defaults_to_all(self) -> None:
        from src.observability.evaluation.ragas_evaluator import RagasEvaluator

        evaluator = RagasEvaluator(settings=None, metrics=None)
        assert len(evaluator._metric_names) == 4


class TestRagasImportCheck:
    """Tests for ragas import validation."""

    def test_import_error_when_ragas_missing(self) -> None:
        from src.observability.evaluation.ragas_evaluator import _import_ragas

        with patch.dict("sys.modules", {"ragas": None}):
            with pytest.raises(ImportError, match="ragas"):
                _import_ragas()


class TestRagasEvaluatorValidation:
    """Tests for input validation in evaluate()."""

    def test_empty_query_raises(self) -> None:
        from src.observability.evaluation.ragas_evaluator import RagasEvaluator

        evaluator = RagasEvaluator(metrics=["faithfulness"])
        with pytest.raises(ValueError, match="Query cannot be empty"):
            evaluator.evaluate("  ", [{"text": "ctx"}], generated_answer="ans")

    def test_empty_chunks_raises(self) -> None:
        from src.observability.evaluation.ragas_evaluator import RagasEvaluator

        evaluator = RagasEvaluator(metrics=["faithfulness"])
        with pytest.raises(ValueError, match="retrieved_chunks cannot be empty"):
            evaluator.evaluate("query", [], generated_answer="ans")

    def test_missing_generated_answer_raises(self) -> None:
        from src.observability.evaluation.ragas_evaluator import RagasEvaluator

        evaluator = RagasEvaluator(metrics=["faithfulness"])
        with pytest.raises(ValueError, match="generated_answer"):
            evaluator.evaluate("query", [{"text": "ctx"}], generated_answer=None)

    def test_empty_generated_answer_raises(self) -> None:
        from src.observability.evaluation.ragas_evaluator import RagasEvaluator

        evaluator = RagasEvaluator(metrics=["faithfulness"])
        with pytest.raises(ValueError, match="generated_answer"):
            evaluator.evaluate("query", [{"text": "ctx"}], generated_answer="   ")


class TestRagasEvaluatorTextExtraction:
    """Tests for _extract_texts helper."""

    def test_extract_from_dicts(self) -> None:
        from src.observability.evaluation.ragas_evaluator import RagasEvaluator

        evaluator = RagasEvaluator(metrics=["faithfulness"])
        result = evaluator._extract_texts([
            {"text": "chunk1"},
            {"content": "chunk2"},
            {"page_content": "chunk3"},
        ])
        assert result == ["chunk1", "chunk2", "chunk3"]

    def test_extract_from_strings(self) -> None:
        from src.observability.evaluation.ragas_evaluator import RagasEvaluator

        evaluator = RagasEvaluator(metrics=["faithfulness"])
        result = evaluator._extract_texts(["chunk1", "chunk2"])
        assert result == ["chunk1", "chunk2"]

    def test_extract_from_objects(self) -> None:
        from src.observability.evaluation.ragas_evaluator import RagasEvaluator

        evaluator = RagasEvaluator(metrics=["faithfulness"])

        class Chunk:
            def __init__(self, text: str) -> None:
                self.text = text

        result = evaluator._extract_texts([Chunk("hello"), Chunk("world")])
        assert result == ["hello", "world"]


class TestRagasEvaluatorEvaluate:
    """Tests for evaluate() with mocked Ragas backend."""

    def _make_mock_ragas_result(self, scores: Dict[str, float]) -> MagicMock:
        """Create a mock ragas evaluation result."""
        import pandas as pd

        df = pd.DataFrame([scores])
        mock_result = MagicMock()
        mock_result.to_pandas.return_value = df
        return mock_result

    def test_evaluate_returns_metrics_dict(self) -> None:
        from src.observability.evaluation.ragas_evaluator import RagasEvaluator

        evaluator = RagasEvaluator(metrics=["faithfulness", "context_precision"])

        expected = {"faithfulness": 0.92, "context_precision": 0.85}
        evaluator._run_ragas = MagicMock(return_value=expected)  # type: ignore[method-assign]

        result = evaluator.evaluate(
            query="What is RAG?",
            retrieved_chunks=["RAG is retrieval augmented generation."],
            generated_answer="RAG stands for Retrieval Augmented Generation.",
        )

        assert result == expected

    def test_evaluate_with_mocked_run_ragas(self) -> None:
        from src.observability.evaluation.ragas_evaluator import RagasEvaluator

        evaluator = RagasEvaluator(metrics=["faithfulness", "answer_relevancy"])

        expected_scores = {"faithfulness": 0.95, "answer_relevancy": 0.88}
        evaluator._run_ragas = MagicMock(return_value=expected_scores)  # type: ignore[method-assign]

        result = evaluator.evaluate(
            query="What is RAG?",
            retrieved_chunks=[{"text": "RAG is Retrieval Augmented Generation"}],
            generated_answer="RAG stands for Retrieval Augmented Generation.",
        )

        assert result == expected_scores
        evaluator._run_ragas.assert_called_once()

    def test_evaluate_runtime_error_on_ragas_failure(self) -> None:
        from src.observability.evaluation.ragas_evaluator import RagasEvaluator

        evaluator = RagasEvaluator(metrics=["faithfulness"])
        evaluator._run_ragas = MagicMock(  # type: ignore[method-assign]
            side_effect=Exception("LLM call failed"),
        )

        with pytest.raises(RuntimeError, match="Ragas evaluation failed"):
            evaluator.evaluate(
                query="test",
                retrieved_chunks=[{"text": "ctx"}],
                generated_answer="answer",
            )

    def test_ground_truth_is_ignored(self) -> None:
        """Ragas should work fine even when ground_truth is provided."""
        from src.observability.evaluation.ragas_evaluator import RagasEvaluator

        evaluator = RagasEvaluator(metrics=["faithfulness"])
        evaluator._run_ragas = MagicMock(return_value={"faithfulness": 0.9})  # type: ignore[method-assign]

        result = evaluator.evaluate(
            query="test",
            retrieved_chunks=[{"text": "ctx"}],
            generated_answer="answer",
            ground_truth=["chunk_001"],  # should be ignored
        )

        assert "faithfulness" in result


class TestRagasEvaluatorFactory:
    """Tests for factory integration."""

    def test_factory_creates_ragas_evaluator(self) -> None:
        from src.libs.evaluator.evaluator_factory import EvaluatorFactory
        from src.observability.evaluation.ragas_evaluator import RagasEvaluator

        settings = MagicMock()
        settings.evaluation.enabled = True
        settings.evaluation.provider = "ragas"
        settings.evaluation.metrics = ["faithfulness"]

        evaluator = EvaluatorFactory.create(settings)
        assert isinstance(evaluator, RagasEvaluator)

    def test_factory_lists_ragas(self) -> None:
        from src.libs.evaluator.evaluator_factory import EvaluatorFactory

        providers = EvaluatorFactory.list_providers()
        assert "custom" in providers
        # ragas may be in _PROVIDERS after first create or in _LAZY_PROVIDERS


class TestRagasEvaluatorBuildWrappers:
    """Phase 3: non-Azure providers use an OpenAI-compatible client."""

    def _qwen_settings(self) -> MagicMock:
        """Real LLM/Embedding dataclasses under a MagicMock Settings shell.

        MagicMock can't reliably represent ``api_key=None`` (its __getattr__
        creates child mocks), so the credential fields use real frozen dataclasses.
        """
        from src.core.settings import EmbeddingSettings, LLMSettings

        settings = MagicMock()
        settings.llm = LLMSettings(
            provider="qwen", model="qwen-turbo", temperature=0.0, max_tokens=4096,
            api_key="sk-qwen", base_url="http://localhost:11434/v1",
        )
        settings.embedding = EmbeddingSettings(
            provider="qwen", model="text-embedding-v3", dimensions=1024,
            api_key="sk-qwen", base_url="http://localhost:11434/v1",
        )
        return settings

    def test_qwen_uses_openai_compatible_client_with_base_url(self) -> None:
        from src.observability.evaluation.ragas_evaluator import RagasEvaluator

        evaluator = RagasEvaluator(settings=self._qwen_settings(), metrics=["faithfulness"])

        with patch("openai.AsyncOpenAI") as mock_client, \
             patch("openai.AsyncAzureOpenAI") as mock_azure, \
             patch("ragas.llms.llm_factory") as mock_llm_factory, \
             patch("ragas.embeddings.OpenAIEmbeddings") as mock_emb:
            llm, embeddings = evaluator._build_wrappers()

        mock_azure.assert_not_called()
        assert mock_client.call_args.kwargs["base_url"] == "http://localhost:11434/v1"
        assert mock_client.call_args.kwargs["api_key"] == "sk-qwen"
        mock_llm_factory.assert_called_once()
        mock_emb.assert_called_once_with(model="text-embedding-v3", client=mock_client.return_value)
        assert llm is mock_llm_factory.return_value
        assert embeddings is mock_emb.return_value

    def test_ollama_without_api_key_still_builds(self) -> None:
        from src.core.settings import EmbeddingSettings, LLMSettings
        from src.observability.evaluation.ragas_evaluator import RagasEvaluator

        settings = MagicMock()
        settings.llm = LLMSettings(
            provider="ollama", model="qwen-turbo", temperature=0.0, max_tokens=4096,
            api_key=None, base_url="http://localhost:11434/v1",
        )
        settings.embedding = EmbeddingSettings(
            provider="qwen", model="text-embedding-v3", dimensions=1024,
            api_key=None, base_url="http://localhost:11434/v1",
        )
        evaluator = RagasEvaluator(settings=settings, metrics=["faithfulness"])

        with patch("openai.AsyncOpenAI") as mock_client, \
             patch("openai.AsyncAzureOpenAI"), \
             patch("ragas.llms.llm_factory"), \
             patch("ragas.embeddings.OpenAIEmbeddings"):
            evaluator._build_wrappers()

        # api_key=None is constructible for a local OpenAI-compatible gateway
        assert mock_client.call_args.kwargs.get("api_key") is None
        assert mock_client.call_args.kwargs["base_url"] == "http://localhost:11434/v1"


class TestRagasEvaluatorReference:
    """Phase 3: ground_truth → reference-answer extraction."""

    def _make(self):
        from src.observability.evaluation.ragas_evaluator import RagasEvaluator

        return RagasEvaluator(metrics=["faithfulness"])

    def test_str_is_itself(self) -> None:
        assert self._make()._extract_reference("answer text") == "answer text"

    def test_dict_reference_key(self) -> None:
        assert self._make()._extract_reference({"reference": "ans"}) == "ans"

    def test_dict_reference_answer_key(self) -> None:
        assert self._make()._extract_reference({"reference_answer": "ans2"}) == "ans2"

    def test_dict_without_reference_returns_none(self) -> None:
        assert self._make()._extract_reference({"ids": ["c1"]}) is None

    def test_none_returns_none(self) -> None:
        assert self._make()._extract_reference(None) is None

    def test_single_element_list(self) -> None:
        assert self._make()._extract_reference(["ans"]) == "ans"

    def test_multi_element_list_returns_none(self) -> None:
        assert self._make()._extract_reference(["a", "b"]) is None


class TestRagasEvaluatorAnswerCorrectness:
    """Phase 3: answer_correctness uses reference; skips gracefully without it."""

    def _evaluator(self):
        from src.observability.evaluation.ragas_evaluator import RagasEvaluator

        evaluator = RagasEvaluator(metrics=["answer_correctness"])
        evaluator._build_wrappers = MagicMock(return_value=(MagicMock(), MagicMock()))
        return evaluator

    def test_scores_with_reference(self, monkeypatch) -> None:
        captured: dict[str, Any] = {}

        class FakeAnswerCorrectness:
            def __init__(self, llm: Any, embeddings: Any) -> None:
                captured["llm"] = llm
                captured["embeddings"] = embeddings

            def score(self, user_input: str, response: str, reference: str) -> MagicMock:
                captured["call"] = (user_input, response, reference)
                return MagicMock(value=0.85)

        monkeypatch.setattr(
            "ragas.metrics.collections.AnswerCorrectness", FakeAnswerCorrectness
        )

        result = self._evaluator()._run_ragas("q", ["ctx1"], "answer", reference="ref ans")

        assert result["answer_correctness"] == pytest.approx(0.85)
        assert captured["call"] == ("q", "answer", "ref ans")

    def test_skipped_when_no_reference(self, monkeypatch) -> None:
        evaluator = self._evaluator()
        with patch("ragas.metrics.collections.AnswerCorrectness") as mock_ac:
            result = evaluator._run_ragas("q", ["ctx1"], "answer", reference=None)

        assert result == {}
        mock_ac.assert_not_called()
