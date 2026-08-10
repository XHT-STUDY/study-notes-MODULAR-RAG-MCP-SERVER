"""Tests for the Phase 4 shared chunk-id prefix helper.

The chunk-id prefix must be:
- stable (same path -> same prefix, across calls and processes),
- path-derived, NOT content-derived (a content change keeps the prefix, which
  is what makes cross-store deletion and orphan GC by prefix reliable).
"""

from src.ingestion.storage.chunk_ids import chunk_id_prefix


class TestChunkIdPrefix:
    def test_returns_8_hex_chars(self) -> None:
        assert len(chunk_id_prefix("docs/a.pdf")) == 8
        assert all(c in "0123456789abcdef" for c in chunk_id_prefix("docs/a.pdf"))

    def test_stable_across_calls(self) -> None:
        assert chunk_id_prefix("docs/a.pdf") == chunk_id_prefix("docs/a.pdf")

    def test_path_derived_not_content_derived(self) -> None:
        # Same path, different (hypothetical) content -> same prefix.
        assert chunk_id_prefix("docs/a.pdf") == chunk_id_prefix("docs/a.pdf")
        # Different path -> different prefix (high confidence, 32-bit space).
        assert chunk_id_prefix("docs/a.pdf") != chunk_id_prefix("docs/b.pdf")

    def test_differs_from_content_hash(self) -> None:
        # The prefix must NOT be the content hash of the file.
        path = "docs/a.pdf"
        content_hash = __import__("hashlib").sha256(b"some content").hexdigest()[:8]
        assert chunk_id_prefix(path) != content_hash

    def test_unicode_path(self) -> None:
        prefix = chunk_id_prefix("知识库/混合检索.pdf")
        assert len(prefix) == 8
        assert prefix == chunk_id_prefix("知识库/混合检索.pdf")
