"""Tests for settings loading and validation."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from src.core.settings import _ENV_OVERRIDES, SettingsError, load_settings

# Committed, desensitized template — the file new environments copy to settings.yaml.
EXAMPLE_SETTINGS = str(Path(__file__).parents[2] / "config" / "settings.yaml.example")


def _write_yaml(path: Path, content: str) -> None:
    path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove every whitelisted env var so the host environment cannot leak into tests."""
    for key in _ENV_OVERRIDES:
        monkeypatch.delenv(key, raising=False)
    yield


def test_load_settings_success(tmp_path: Path) -> None:
    config = """
    llm:
      provider: openai
      model: gpt-4o-mini
      temperature: 0.0
      max_tokens: 1024
    embedding:
      provider: openai
      model: text-embedding-3-small
      dimensions: 1536
    vector_store:
      provider: chroma
      persist_directory: ./data/db/chroma
      collection_name: knowledge_hub
    retrieval:
      dense_top_k: 20
      sparse_top_k: 20
      fusion_top_k: 10
      rrf_k: 60
    rerank:
      enabled: false
      provider: none
      model: cross-encoder/ms-marco-MiniLM-L-6-v2
      top_k: 5
    evaluation:
      enabled: false
      provider: custom
      metrics:
        - hit_rate
        - mrr
    observability:
      log_level: INFO
      trace_enabled: true
      trace_file: ./logs/traces.jsonl
      structured_logging: true
    ingestion:
      chunk_size: 1000
      chunk_overlap: 200
      splitter: recursive
      batch_size: 100
    """
    settings_path = tmp_path / "settings.yaml"
    _write_yaml(settings_path, config)

    settings = load_settings(settings_path)

    assert settings.llm.provider == "openai"
    assert settings.embedding.dimensions == 1536
    assert settings.vector_store.collection_name == "knowledge_hub"
    assert settings.retrieval.rrf_k == 60
    assert settings.rerank.provider == "none"
    assert settings.evaluation.metrics == ["hit_rate", "mrr"]
    assert settings.observability.log_level == "INFO"
    assert settings.ingestion is not None


def test_missing_required_field_raises_error(tmp_path: Path) -> None:
    config = """
    llm:
      provider: openai
      model: gpt-4o-mini
      temperature: 0.0
      max_tokens: 1024
    embedding:
      model: text-embedding-3-small
      dimensions: 1536
    vector_store:
      provider: chroma
      persist_directory: ./data/db/chroma
      collection_name: knowledge_hub
    retrieval:
      dense_top_k: 20
      sparse_top_k: 20
      fusion_top_k: 10
      rrf_k: 60
    rerank:
      enabled: false
      provider: none
      model: cross-encoder/ms-marco-MiniLM-L-6-v2
      top_k: 5
    evaluation:
      enabled: false
      provider: custom
      metrics:
        - hit_rate
    observability:
      log_level: INFO
      trace_enabled: true
      trace_file: ./logs/traces.jsonl
      structured_logging: true
    """
    settings_path = tmp_path / "settings.yaml"
    _write_yaml(settings_path, config)

    with pytest.raises(SettingsError, match="embedding.provider"):
        load_settings(settings_path)


# ---------------------------------------------------------------------------
# Phase 0: env-var overrides on the example template (env wins over YAML)
# ---------------------------------------------------------------------------


def test_load_example_template_has_no_secrets(clean_env: None) -> None:
    """The committed template must load and ship with blank secret fields."""
    settings = load_settings(EXAMPLE_SETTINGS)

    assert settings.llm.provider == "qwen"
    assert settings.llm.api_key is None
    assert settings.embedding.api_key is None
    assert settings.vision_llm is not None
    assert settings.vision_llm.api_key is None


def test_env_overrides_yaml_api_key(clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    settings = load_settings(EXAMPLE_SETTINGS)
    assert settings.llm.api_key == "sk-test"


def test_env_overrides_base_url(clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EMBEDDING_BASE_URL", "http://localhost:11434/v1")
    settings = load_settings(EXAMPLE_SETTINGS)
    assert settings.embedding.base_url == "http://localhost:11434/v1"


def test_env_overrides_model(clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_MODEL", "gpt-4o")
    settings = load_settings(EXAMPLE_SETTINGS)
    assert settings.llm.model == "gpt-4o"


def test_no_env_keeps_yaml_value(clean_env: None) -> None:
    """With no env vars set, the blank YAML value ('' → None) is preserved."""
    settings = load_settings(EXAMPLE_SETTINGS)
    assert settings.llm.api_key is None


def test_blank_env_ignored(clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty env var must NOT override the YAML value."""
    monkeypatch.setenv("LLM_API_KEY", "")
    settings = load_settings(EXAMPLE_SETTINGS)
    assert settings.llm.api_key is None


# ---------------------------------------------------------------------------
# Dotenv: config/.env is auto-loaded by load_settings (env_file= opt-in in tests)
# ---------------------------------------------------------------------------


def test_dotenv_file_overrides_yaml(clean_env: None, tmp_path: Path) -> None:
    """A .env file passed via env_file= populates the whitelisted settings."""
    env_file = tmp_path / ".env"
    env_file.write_text("LLM_API_KEY=sk-dotenv\n", encoding="utf-8")

    settings = load_settings(EXAMPLE_SETTINGS, env_file=env_file)

    assert settings.llm.api_key == "sk-dotenv"


def test_process_env_wins_over_dotenv(clean_env: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Process env (override=False) beats the .env file value."""
    monkeypatch.setenv("LLM_API_KEY", "sk-proc")
    env_file = tmp_path / ".env"
    env_file.write_text("LLM_API_KEY=sk-dotenv\n", encoding="utf-8")

    settings = load_settings(EXAMPLE_SETTINGS, env_file=env_file)

    assert settings.llm.api_key == "sk-proc"


def test_missing_env_file_is_noop(clean_env: None, tmp_path: Path) -> None:
    """A missing .env path leaves the YAML value untouched."""
    settings = load_settings(EXAMPLE_SETTINGS, env_file=tmp_path / "does_not_exist.env")

    assert settings.llm.api_key is None
