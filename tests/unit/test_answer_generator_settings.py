"""Unit tests for AnswerGeneratorSettings parsing."""

import textwrap
from pathlib import Path

import pytest

from src.core.settings import load_settings

# Minimal valid config (all required sections) without an answer_generator block.
_MINIMAL = """
llm: {provider: openai, model: gpt-4o-mini, temperature: 0.0, max_tokens: 1024}
embedding: {provider: openai, model: text-embedding-3-small, dimensions: 1536}
vector_store: {provider: chroma, persist_directory: ./data/db/chroma, collection_name: knowledge_hub}
retrieval: {dense_top_k: 20, sparse_top_k: 20, fusion_top_k: 10, rrf_k: 60}
rerank: {enabled: false, provider: none, model: none, top_k: 5}
evaluation: {enabled: false, provider: custom, metrics: [hit_rate]}
observability: {log_level: INFO, trace_enabled: true, trace_file: ./logs/traces.jsonl, structured_logging: true}
"""


def _write(path: Path, content: str) -> None:
    path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")


@pytest.mark.unit
class TestAnswerGeneratorSettings:
    """Tests for the optional answer_generator settings block."""

    def test_absent_block_defaults_none(self, tmp_path: Path) -> None:
        path = tmp_path / "settings.yaml"
        _write(path, _MINIMAL)

        settings = load_settings(path)

        assert settings.answer_generator is None

    def test_parse_full_block(self, tmp_path: Path) -> None:
        path = tmp_path / "settings.yaml"
        _write(
            path,
            _MINIMAL
            + """
answer_generator:
  enabled: true
  provider: extractive
  temperature: 0.1
  max_tokens: 512
  confidence_threshold: 0.3
  max_chunks: 5
""",
        )

        ag = load_settings(path).answer_generator

        assert ag is not None
        assert ag.enabled is True
        assert ag.provider == "extractive"
        assert ag.temperature == 0.1
        assert ag.max_tokens == 512
        assert ag.confidence_threshold == 0.3
        assert ag.max_chunks == 5

    def test_partial_block_uses_defaults(self, tmp_path: Path) -> None:
        path = tmp_path / "settings.yaml"
        _write(
            path,
            _MINIMAL
            + """
answer_generator:
  enabled: true
  provider: llm
""",
        )

        ag = load_settings(path).answer_generator

        assert ag is not None
        assert ag.provider == "llm"
        assert ag.model == ""
        assert ag.temperature == 0.0
        assert ag.max_tokens == 1024
        assert ag.confidence_threshold == 0.5
        assert ag.max_chunks == 3

    def test_example_template_parses_answer_generator(self) -> None:
        example = Path(__file__).parents[2] / "config" / "settings.yaml.example"
        ag = load_settings(str(example)).answer_generator

        assert ag is not None
        assert ag.enabled is True
        assert ag.provider == "extractive"
