"""Tests for the versioned prompt-template registry (Phase 5)."""

from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import Mock

import pytest

from src.core.prompts import (
    DEFAULT_ROLES,
    PROMPTS_DIR,
    PromptError,
    PromptRegistry,
    PromptsSettings,
    get_prompt_text,
    resolve_prompt_path,
    sha256_text,
    split_frontmatter,
)


def _write(path: Path, content: str) -> None:
    """Write *content* verbatim (no trailing-newline normalization) so the
    checksum the test computes matches the on-disk body bytes."""
    path.write_text(textwrap.dedent(content), encoding="utf-8")


def _template(name: str, body: str, checksum: str | None = None) -> str:
    """Build a frontmattered template; a None checksum omits the field."""
    checksum_line = f"checksum: {checksum}\n" if checksum else ""
    return (
        f"---\n"
        f"name: {name}\n"
        f"version: 1\n"
        f"description: test template\n"
        f"{checksum_line}"
        f"updated_at: 2026-08-10\n"
        f"---\n"
        f"{body}"
    )


# ── frontmatter parsing ────────────────────────────────────────────────────


def test_split_frontmatter_parses_metadata_and_body() -> None:
    raw = _template("rerank", "Hello {text}")
    metadata, body = split_frontmatter(raw)

    assert metadata is not None
    assert metadata["name"] == "rerank"
    assert metadata["version"] == "1"
    assert metadata["description"] == "test template"
    assert body == "Hello {text}"


def test_split_frontmatter_plain_text_is_whole_body() -> None:
    """No leading ``---`` → (None, whole file) — keeps temp-file tests green."""
    raw = "Just a plain prompt.\nNo frontmatter here.\n"
    metadata, body = split_frontmatter(raw)

    assert metadata is None
    assert body == raw


def test_parse_yaml_lines_strips_quotes_and_comments() -> None:
    raw = (
        "---\n"
        'name: "chunk_refinement"   # quoted + trailing comment\n'
        "version: 1\n"
        "# a full-line comment\n"
        "---\n"
        "body"
    )
    metadata, body = split_frontmatter(raw)

    assert metadata["name"] == "chunk_refinement"
    assert metadata["version"] == "1"
    assert body == "body"


# ── sha256 ─────────────────────────────────────────────────────────────────


def test_sha256_text_returns_64_hex() -> None:
    digest = sha256_text("abc")
    assert len(digest) == 64
    assert all(c in "0123456789abcdef" for c in digest)


# ── loading real templates ─────────────────────────────────────────────────


def test_canonical_prompt_files_exist() -> None:
    for role in DEFAULT_ROLES:
        assert (PROMPTS_DIR / f"{role}.md").is_file(), f"missing {role}.md"


def test_real_template_body_keeps_placeholder_and_no_frontmatter() -> None:
    """The migrated bodies must still contain their placeholders and the body
    must not leak `name:` / `checksum:` frontmatter lines."""
    registry = PromptRegistry()
    chunk = registry.load("chunk_refinement")
    meta = registry.load("metadata_enrichment")

    assert "{text}" in chunk.body
    assert "{chunk_text}" in meta.body
    assert not any(line.startswith(("name:", "checksum:")) for line in chunk.body.splitlines())
    assert chunk.checksum is not None and len(chunk.checksum) == 64


def test_load_missing_file_raises(tmp_path: Path) -> None:
    registry = PromptRegistry(tmp_path)
    with pytest.raises(FileNotFoundError):
        registry.load("does_not_exist")


# ── checksum verification ──────────────────────────────────────────────────


def test_load_checksum_match_no_warning(caplog: pytest.LogCaptureFixture) -> None:
    registry = PromptRegistry()
    tmpl = registry.load("rerank")

    with caplog.at_level("WARNING"):
        loaded = registry.load("rerank", strict=True)
    assert loaded.body == tmpl.body  # deterministic: same file each time
    assert "checksum mismatch" not in caplog.text


def test_load_checksum_mismatch_warns_but_returns_body(caplog: pytest.LogCaptureFixture, tmp_path: Path) -> None:
    path = tmp_path / "rerank.md"
    _write(path, _template("rerank", "New body {text}", checksum="0" * 64))

    registry = PromptRegistry(tmp_path)
    with caplog.at_level("WARNING"):
        tmpl = registry.load("rerank")

    assert tmpl.body == "New body {text}"
    assert "checksum mismatch" in caplog.text


def test_load_checksum_mismatch_strict_raises(tmp_path: Path) -> None:
    path = tmp_path / "rerank.md"
    _write(path, _template("rerank", "New body {text}", checksum="0" * 64))

    registry = PromptRegistry(tmp_path)
    with pytest.raises(PromptError, match="checksum mismatch"):
        registry.load("rerank", strict=True)


def test_load_plain_text_file_skips_checksum(tmp_path: Path) -> None:
    """A no-frontmatter temp file loads silently even with strict=True."""
    path = tmp_path / "rerank.md"
    path.write_text("plain body without frontmatter", encoding="utf-8")

    registry = PromptRegistry(tmp_path)
    tmpl = registry.load("rerank", strict=True)

    assert tmpl.body == "plain body without frontmatter"
    assert tmpl.checksum is None
    assert tmpl.metadata == {}


# ── caching ────────────────────────────────────────────────────────────────


def test_get_prompt_text_caches_by_path(tmp_path: Path) -> None:
    path = tmp_path / "rerank.md"
    _write(path, _template("rerank", "Body {text}", checksum=sha256_text("Body {text}")))

    registry = PromptRegistry(tmp_path)
    first = registry.get_prompt_text("rerank", path=path)
    second = registry.get_prompt_text("rerank", path=path)

    assert first == second == "Body {text}"


# ── resolve_prompt_path ────────────────────────────────────────────────────


def test_resolve_prompt_path_default_role_name() -> None:
    assert resolve_prompt_path("chunk_refinement", None) == PROMPTS_DIR / "chunk_refinement.md"


def test_resolve_prompt_path_custom_name() -> None:
    cfg = PromptsSettings(chunk_refinement="my_custom_prompt")
    assert resolve_prompt_path("chunk_refinement", cfg) == PROMPTS_DIR / "my_custom_prompt.md"


def test_resolve_prompt_path_mock_settings_falls_back() -> None:
    """A Mock(spec=Settings).prompts is NOT a PromptsSettings — must not produce
    a `<Mock id=…>.md` path."""
    mock_settings = Mock(spec=("prompts",))
    result = resolve_prompt_path("rerank", getattr(mock_settings, "prompts", None))
    assert result == PROMPTS_DIR / "rerank.md"


# ── verify_all ─────────────────────────────────────────────────────────────


def test_verify_all_clean_dir_returns_empty(tmp_path: Path) -> None:
    for role in DEFAULT_ROLES:
        _write(tmp_path / f"{role}.md", _template(role, "body {text}", checksum=sha256_text("body {text}")))
    assert PromptRegistry(tmp_path).verify_all() == []


def test_verify_all_missing_canonical_reports(tmp_path: Path) -> None:
    _write(tmp_path / "rerank.md", _template("rerank", "body", checksum=sha256_text("body")))
    errors = PromptRegistry(tmp_path).verify_all()
    assert len(errors) == len(DEFAULT_ROLES) - 1
    assert any("missing canonical prompt" in e for e in errors)


def test_verify_all_checksum_mismatch_reports(tmp_path: Path) -> None:
    for role in DEFAULT_ROLES:
        _write(tmp_path / f"{role}.md", _template(role, "body {text}", checksum=sha256_text("body {text}")))
    (tmp_path / "rerank.md").write_text(
        _template("rerank", "tampered body", checksum=sha256_text("body {text}")), encoding="utf-8"
    )
    errors = PromptRegistry(tmp_path).verify_all()
    assert len(errors) == 1
    assert "checksum mismatch" in errors[0]


# ── update_checksums ───────────────────────────────────────────────────────


def test_update_checksums_only_touches_checksum_line(tmp_path: Path) -> None:
    path = tmp_path / "rerank.md"
    _write(path, _template("rerank", "body {text}", checksum="0" * 64))
    registry = PromptRegistry(tmp_path)

    changed = registry.update_checksums()
    assert changed == [path]

    raw = path.read_text(encoding="utf-8")
    assert f"checksum: {sha256_text('body {text}')}" in raw
    # Only the checksum line changed; body and other fields intact.
    assert "name: rerank" in raw
    assert "body {text}" in raw


def test_update_checksums_idempotent(tmp_path: Path) -> None:
    for role in DEFAULT_ROLES:
        _write(tmp_path / f"{role}.md", _template(role, "body {text}"))
    registry = PromptRegistry(tmp_path)

    assert registry.update_checksums()  # first run fills them in
    assert registry.update_checksums() == []  # second run: nothing to change


def test_update_checksums_skips_no_frontmatter(tmp_path: Path) -> None:
    path = tmp_path / "rerank.md"
    path.write_text("plain body", encoding="utf-8")
    registry = PromptRegistry(tmp_path)

    assert registry.update_checksums() == []
    assert path.read_text(encoding="utf-8") == "plain body"


# ── CLI (scripts/prompts.py) ───────────────────────────────────────────────


def _sample_registry(tmp_path: Path) -> PromptRegistry:
    for role in DEFAULT_ROLES:
        _write(tmp_path / f"{role}.md", _template(role, "body {text}", checksum=sha256_text("body {text}")))
    return PromptRegistry(tmp_path)


def test_cli_verify_clean_exit_zero(capsys, tmp_path: Path) -> None:
    from scripts.prompts import main

    rc = main(["--verify"], registry=_sample_registry(tmp_path))
    assert rc == 0
    assert "OK:" in capsys.readouterr().out


def test_cli_verify_error_exit_one(capsys, tmp_path: Path) -> None:
    from scripts.prompts import main

    registry = _sample_registry(tmp_path)
    (tmp_path / "rerank.md").write_text(
        _template("rerank", "tampered", checksum=sha256_text("body {text}")), encoding="utf-8"
    )
    rc = main(["--verify"], registry=registry)
    assert rc == 1
    assert "FAIL:" in capsys.readouterr().err


def test_cli_update_checksums_exit_zero(capsys, tmp_path: Path) -> None:
    from scripts.prompts import main

    rc = main(["--update-checksums"], registry=_sample_registry(tmp_path))
    assert rc == 0
    assert "OK:" in capsys.readouterr().out


def test_cli_no_flags_exit_two(capsys, tmp_path: Path) -> None:
    from scripts.prompts import main

    assert main([], registry=_sample_registry(tmp_path)) == 2


def test_cli_both_flags_exit_two(capsys, tmp_path: Path) -> None:
    from scripts.prompts import main

    assert main(["--verify", "--update-checksums"], registry=_sample_registry(tmp_path)) == 2


# ── module-level shortcut ───────────────────────────────────────────────────


def test_get_prompt_text_shortcut() -> None:
    """The module-level get_prompt_text uses PROMPTS_DIR; verify it returns the
    real migrated rerank body with placeholder intact."""
    body = get_prompt_text("rerank")
    assert "candidate passages" in body
    assert "passage_id" in body
