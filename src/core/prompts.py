"""Versioned prompt-template registry (Phase 5).

Prompt templates live as Markdown files in ``prompts/`` at the repo root,
each carrying a YAML frontmatter block with ``name`` / ``version`` /
``description`` / ``checksum`` / ``updated_at`` metadata.  The ``checksum``
is a SHA-256 of the template *body* (the bytes after the closing frontmatter
delimiter) and is maintained by ``scripts/prompts.py --update-checksums`` —
never hand-edited.

Loading is best-effort: a checksum mismatch logs a warning and still returns
the body (so a stale checksum never blocks ingestion).  ``strict=True`` turns
that into a ``PromptError``, which is what ``--verify`` uses to hard-fail.
Files without a leading frontmatter block (e.g. plain-text temp files injected
in tests) are treated as whole-file bodies and skipped silently.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.core.settings import REPO_ROOT, PromptsSettings
from src.observability.logger import get_logger

logger = get_logger(__name__)

# Root directory holding the versioned prompt templates.
PROMPTS_DIR: Path = REPO_ROOT / "prompts"

# The canonical roles the system understands.  ``--verify`` asserts each of
# these files exists, so a renamed/deleted template is caught.
DEFAULT_ROLES: tuple[str, ...] = (
    "chunk_refinement",
    "metadata_enrichment",
    "image_captioning",
    "rerank",
)

# Only a *leading* ``---`` block counts as frontmatter; a plain-text file with
# no opening delimiter is treated as whole-file body (keeps temp-file tests
# green).
_FRONTMATTER_RE = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*\r?\n", re.DOTALL)
_CHECKSUM_LINE_RE = re.compile(r"(?m)^checksum\s*:\s*.*$")


class PromptError(ValueError):
    """Raised when a prompt template fails strict validation."""


@dataclass(frozen=True)
class PromptTemplate:
    """A loaded prompt template with its frontmatter metadata."""

    name: str
    path: Path
    body: str
    checksum: str | None
    metadata: Mapping[str, Any]


def sha256_text(text: str) -> str:
    """SHA-256 hex digest of *text* as UTF-8 bytes."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def split_frontmatter(raw: str) -> tuple[dict[str, Any] | None, str]:
    """Split *raw* into ``(metadata, body)``.

    Returns ``(None, raw)`` when there is no leading frontmatter block, so the
    whole file is treated as the body.
    """
    match = _FRONTMATTER_RE.match(raw)
    if match is None:
        return None, raw
    meta_block = match.group(1)
    body = raw[match.end():]
    metadata = _parse_yaml_lines(meta_block)
    return metadata, body


def _parse_yaml_lines(block: str) -> dict[str, Any]:
    """Parse a small ``key: value`` frontmatter block without importing yaml.

    Values are strings (kept as-is); quoted values have their quotes stripped.
    Comments (``#``) are trimmed.  This intentionally supports only the simple
    scalar format our prompt files use.
    """
    parsed: dict[str, Any] = {}
    for line in block.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in stripped:
            continue
        key, _, value = stripped.partition(":")
        key = key.strip()
        value = value.strip()
        # Drop trailing inline comments.
        if " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        parsed[key] = value
    return parsed


def _set_checksum(raw: str, new_hash: str) -> str:
    """Return *raw* with only its ``checksum:`` field updated.

    If no ``checksum:`` field exists, one is inserted just before the closing
    frontmatter delimiter.  Files without frontmatter are returned unchanged.
    """
    match = _FRONTMATTER_RE.match(raw)
    if match is None:
        return raw
    frontmatter = match.group(0)
    if _CHECKSUM_LINE_RE.search(frontmatter):
        updated = _CHECKSUM_LINE_RE.sub(f"checksum: {new_hash}", frontmatter, count=1)
    else:
        closing_start = frontmatter.rstrip("\r\n").rfind("\n---") + 1
        updated = frontmatter[:closing_start] + f"checksum: {new_hash}\n" + frontmatter[closing_start:]
    return raw.replace(frontmatter, updated, 1)


class PromptRegistry:
    """Loads and validates prompt templates from a directory.

    Cache key is the resolved file path, so distinct prompts (or a custom path
    override) never collide.
    """

    def __init__(self, prompts_dir: Path | None = None) -> None:
        self.prompts_dir: Path = Path(prompts_dir) if prompts_dir else PROMPTS_DIR
        self._cache: dict[str, str] = {}

    def load(
        self,
        name: str,
        *,
        path: Path | None = None,
        strict: bool = False,
    ) -> PromptTemplate:
        """Load *name* (or the file at *path*) as a :class:`PromptTemplate`.

        Raises:
            FileNotFoundError: The template file does not exist.
            PromptError: *strict* is true and the declared checksum mismatches.
        """
        file_path = Path(path) if path else self.prompts_dir / f"{name}.md"
        if not file_path.is_file():
            raise FileNotFoundError(f"Prompt file not found: {file_path}")
        raw = file_path.read_text(encoding="utf-8")
        metadata, body = split_frontmatter(raw)
        declared = metadata.get("checksum") if metadata else None
        if isinstance(declared, str) and declared:
            computed = sha256_text(body)
            if computed != declared:
                message = (
                    f"checksum mismatch for {file_path.name}: "
                    f"declared {declared}, computed {computed} "
                    "(run `python scripts/prompts.py --update-checksums`)"
                )
                if strict:
                    raise PromptError(message)
                logger.warning(message)
        return PromptTemplate(
            name=name,
            path=file_path,
            body=body,
            checksum=declared if isinstance(declared, str) else None,
            metadata=dict(metadata) if metadata else {},
        )

    def get_prompt_text(
        self,
        name: str,
        *,
        path: Path | None = None,
        strict: bool = False,
    ) -> str:
        """Return the body of a prompt template (cached by file path)."""
        file_path = Path(path) if path else self.prompts_dir / f"{name}.md"
        key = str(file_path)
        if key in self._cache:
            return self._cache[key]
        body = self.load(name, path=file_path, strict=strict).body
        self._cache[key] = body
        return body

    def verify_all(self, prompts_dir: Path | None = None) -> list[str]:
        """Strictly verify every template; returns a list of errors (empty = OK).

        Asserts each canonical role file exists, then validates checksums with
        ``strict=True`` for every ``*.md`` in the directory.
        """
        directory = Path(prompts_dir) if prompts_dir else self.prompts_dir
        errors: list[str] = []
        for role in DEFAULT_ROLES:
            path = directory / f"{role}.md"
            if not path.is_file():
                errors.append(f"missing canonical prompt: {_rel(path)}")
        for path in sorted(directory.glob("*.md")):
            try:
                self.load(path.stem, path=path, strict=True)
            except (PromptError, FileNotFoundError) as exc:
                errors.append(f"{_rel(path)}: {exc}")
        return errors

    def update_checksums(self, prompts_dir: Path | None = None) -> list[Path]:
        """Rewrite each frontmattered ``*.md`` so its ``checksum`` matches its body.

        Files without frontmatter are skipped.  Returns the list of files that
        were actually changed.
        """
        directory = Path(prompts_dir) if prompts_dir else self.prompts_dir
        changed: list[Path] = []
        for path in sorted(directory.glob("*.md")):
            raw = path.read_text(encoding="utf-8")
            metadata, body = split_frontmatter(raw)
            if metadata is None:
                continue
            new_hash = sha256_text(body)
            updated = _set_checksum(raw, new_hash)
            if updated != raw:
                path.write_text(updated, encoding="utf-8")
                changed.append(path)
        return changed


def resolve_prompt_path(
    role: str,
    prompts_cfg: PromptsSettings | None = None,
) -> Path:
    """Resolve *role* to its prompt file path.

    Uses ``prompts_cfg.resolve(role)`` when a real :class:`PromptsSettings` is
    given; otherwise (or when the config is a test Mock) falls back to the role
    name as the default file stem.
    """
    if isinstance(prompts_cfg, PromptsSettings):
        name = prompts_cfg.resolve(role)
    else:
        name = role
    return PROMPTS_DIR / f"{name}.md"


def _rel(path: Path) -> str:
    """Repo-root-relative path for readable messages."""
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


# Module-level singleton so consumers (ingestion transforms, reranker) can load
# prompts without constructing a registry.
_registry = PromptRegistry()


def get_prompt_text(
    name: str,
    *,
    path: Path | None = None,
    strict: bool = False,
) -> str:
    """Module-level shortcut for :meth:`PromptRegistry.get_prompt_text`."""
    return _registry.get_prompt_text(name, path=path, strict=strict)
