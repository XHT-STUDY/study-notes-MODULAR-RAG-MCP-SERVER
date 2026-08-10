"""Shared chunk-ID helpers for the ingestion storage layer.

Phase 4 centralizes the chunk-id prefix derivation so every store (Chroma,
BM25, ``DocumentManager``, orphan GC) agrees on how a document's source path
maps to the prefix that groups its chunks.

Chunk ID format (see :class:`~src.ingestion.storage.vector_upserter.VectorUpserter`):

    {source_path_hash}_{chunk_index:04d}_{content_hash}

Where:

- ``source_path_hash`` = first 8 chars of ``SHA256(source_path)`` — this
  prefix is derived from the **path**, not the content, so re-ingesting a
  changed file still maps to the same document grouping.
- ``content_hash``     = first 8 chars of ``SHA256(chunk.text)``.
"""

import hashlib


def chunk_id_prefix(source_path: str) -> str:
    """Return the stable chunk-id prefix for a source path.

    This is the value shared by every chunk of a document.  Because it hashes
    the *path* (not the content), a content change keeps the same prefix, which
    is what makes cross-store deletion / GC by prefix reliable.
    """
    return hashlib.sha256(source_path.encode("utf-8")).hexdigest()[:8]
