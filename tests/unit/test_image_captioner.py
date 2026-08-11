"""Tests for ImageCaptioner prompt loading (Phase 5: versioned prompts)."""

from __future__ import annotations

import textwrap
from pathlib import Path

from src.core.prompts import PROMPTS_DIR, PromptRegistry
from src.core.settings import load_settings
from src.ingestion.transform.image_captioner import ImageCaptioner

FALLBACK = "Describe this image in detail for indexing purposes."


def _write_yaml(path: Path, content: str) -> None:
    path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")


def _minimal_config(extra: str = "") -> str:
    """A minimal settings.yaml with vision disabled (no LLMFactory call)."""
    base = """
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
    vision_llm:
      enabled: false
      provider: qwen
      model: qwen-vl-max
      max_image_size: 1024
    """
    return base + extra


def test_captioner_loads_real_prompt_body(tmp_path: Path) -> None:
    """Constructing with a real Settings loads the migrated prompts file body."""
    settings_path = tmp_path / "settings.yaml"
    _write_yaml(settings_path, _minimal_config())
    settings = load_settings(settings_path)

    captioner = ImageCaptioner(settings)

    expected = PromptRegistry().load("image_captioning").body.strip()
    assert captioner.prompt == expected
    assert captioner.prompt
    # Frontmatter lines must never leak into the prompt.
    assert not any(
        line.startswith(("name:", "version:", "checksum:", "description:"))
        for line in captioner.prompt.splitlines()
    )


def test_captioner_custom_prompt_path(tmp_path: Path) -> None:
    """An injected prompt_path takes precedence over the default."""
    settings_path = tmp_path / "settings.yaml"
    _write_yaml(settings_path, _minimal_config())
    settings = load_settings(settings_path)

    custom = tmp_path / "custom_caption.md"
    custom.write_text("Custom caption instruction.", encoding="utf-8")

    captioner = ImageCaptioner(settings, prompt_path=str(custom))
    assert captioner.prompt == "Custom caption instruction."


def test_captioner_missing_prompt_falls_back(tmp_path: Path) -> None:
    """A missing prompt_path must fall back to the hardcoded string, not crash."""
    settings_path = tmp_path / "settings.yaml"
    _write_yaml(settings_path, _minimal_config())
    settings = load_settings(settings_path)

    captioner = ImageCaptioner(settings, prompt_path=str(tmp_path / "nope.md"))
    assert captioner.prompt == FALLBACK


def test_captioner_prompt_path_relative_to_prompts_dir(tmp_path: Path) -> None:
    """Custom names under prompts/ are resolved relative to the prompts dir."""
    settings_path = tmp_path / "settings.yaml"
    _write_yaml(
        settings_path,
        _minimal_config(
            "\n    prompts:\n      image_captioning: caption_v2\n"
        ),
    )
    settings = load_settings(settings_path)

    # The resolved default points at a file that doesn't exist → fallback.
    captioner = ImageCaptioner(settings)
    assert captioner.prompt == FALLBACK
    # And it resolved to the *custom* name, not the role default.
    assert captioner._prompt_path == str(PROMPTS_DIR / "caption_v2.md")
