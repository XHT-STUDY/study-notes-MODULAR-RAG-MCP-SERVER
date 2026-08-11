"""Tests for the Phase 6 ``agent`` optional settings block.

Locks: absent block → ``settings.agent is None``; full block parsing with
sub-block defaults; the default tool whitelist; the example template shipping
with ``enabled: false``; the tolerant ``AGENT_ENABLED`` env override (Trap ①)
and the resurrection guard (no ``agent:`` block → env var is a no-op).
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from src.core.settings import (
    _ENV_OVERRIDES,
    MemorySettings,
    ReflectionSettings,
    RouterSettings,
    SettingsError,
    load_settings,
)

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


def _config(agent_block: str | None) -> str:
    """Full valid config with an optional ``agent:`` block appended."""
    base = textwrap.dedent("""
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
    observability:
      log_level: INFO
      trace_enabled: true
      trace_file: ./logs/traces.jsonl
      structured_logging: true
    """)
    if not agent_block:
        return base
    # Dedent the block on its own so a heredoc-styled agent: block lands at
    # column 0 (top-level) rather than nesting under observability.
    return base + "\n" + textwrap.dedent(agent_block)


def _load(tmp_path: Path, config: str):
    settings_path = tmp_path / "settings.yaml"
    _write_yaml(settings_path, config)
    return load_settings(settings_path)


class TestAgentBlock:
    """The optional ``agent:`` block parses or stays None."""

    def test_absent_block_is_none(self, tmp_path: Path) -> None:
        settings = _load(tmp_path, _config(None))
        assert settings.agent is None

    def test_full_block_parses(self, tmp_path: Path) -> None:
        block = """
        agent:
          enabled: true
          strategy: "plan_and_execute"
          max_iterations: 8
          router: { enabled: true, provider: "llm" }
          memory: { enabled: true, backend: "sqlite", window_size: 6 }
          reflection: { enabled: true, max_retrieval_rounds: 3 }
          tools:
            - "query_knowledge_hub"
            - "list_collections"
        """
        settings = _load(tmp_path, _config(block))
        agent = settings.agent
        assert agent is not None
        assert agent.enabled is True
        assert agent.strategy == "plan_and_execute"
        assert agent.max_iterations == 8
        assert agent.router is not None
        assert agent.router.enabled is True
        assert agent.router.provider == "llm"
        assert agent.memory is not None
        assert agent.memory.enabled is True
        assert agent.memory.backend == "sqlite"
        assert agent.memory.window_size == 6
        assert agent.reflection is not None
        assert agent.reflection.enabled is True
        assert agent.reflection.max_retrieval_rounds == 3
        assert agent.tools == ["query_knowledge_hub", "list_collections"]

    def test_subblock_absent_defaults_to_none(self, tmp_path: Path) -> None:
        """Agent block without router/memory/reflection → those stay None."""
        block = """
        agent:
          enabled: true
          strategy: "react"
        """
        settings = _load(tmp_path, _config(block))
        agent = settings.agent
        assert agent is not None
        assert agent.router is None
        assert agent.memory is None
        assert agent.reflection is None

    def test_subblock_field_defaults(self, tmp_path: Path) -> None:
        """A sub-block may omit fields; dataclass defaults apply."""
        block = """
        agent:
          enabled: true
          router: { enabled: true }
          memory: { window_size: 3 }
          reflection: {}
        """
        settings = _load(tmp_path, _config(block))
        agent = settings.agent
        assert agent is not None
        assert agent.router == RouterSettings(enabled=True, provider="rule")
        assert agent.memory == MemorySettings(enabled=False, backend="none", window_size=3)
        assert agent.reflection == ReflectionSettings(enabled=True, max_retrieval_rounds=2)

    def test_tools_default_three(self, tmp_path: Path) -> None:
        block = """
        agent:
          enabled: true
        """
        settings = _load(tmp_path, _config(block))
        assert settings.agent is not None
        assert settings.agent.tools == [
            "query_knowledge_hub",
            "list_collections",
            "get_document_summary",
        ]

    def test_invalid_enabled_value_raises(self, tmp_path: Path) -> None:
        block = """
        agent:
          enabled: "yes"
        """
        with pytest.raises(SettingsError, match="agent.enabled"):
            _load(tmp_path, _config(block))

    def test_example_template_agent_disabled(self, clean_env: None) -> None:
        settings = load_settings(EXAMPLE_SETTINGS)
        assert settings.agent is not None
        assert settings.agent.enabled is False
        assert settings.agent.strategy == "react"
        assert settings.agent.max_iterations == 5


class TestAgentEnvOverride:
    """AGENT_ENABLED flips the block's enabled flag (Trap ①)."""

    def test_env_true_flips_enabled(self, clean_env: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv("AGENT_ENABLED", "true")
        settings = _load(tmp_path, _config("agent:\n  enabled: false\n"))
        assert settings.agent is not None
        assert settings.agent.enabled is True

    def test_env_false_keeps_disabled(self, clean_env: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv("AGENT_ENABLED", "0")
        settings = _load(tmp_path, _config("agent:\n  enabled: true\n"))
        assert settings.agent is not None
        assert settings.agent.enabled is False

    def test_env_no_agent_block_is_noop(self, clean_env: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Resurrection guard: an env var must not create a partial agent block."""
        monkeypatch.setenv("AGENT_ENABLED", "true")
        settings = _load(tmp_path, _config(None))
        assert settings.agent is None

    def test_env_invalid_value_raises(self, clean_env: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv("AGENT_ENABLED", "not-a-bool")
        with pytest.raises(SettingsError, match="agent.enabled"):
            _load(tmp_path, _config("agent:\n  enabled: false\n"))
