"""Orphan garbage collection across the ingestion storage layer (Phase 4).

Removes data whose content hash is no longer *active* — the "update loop"
leaves stale chunks in Chroma, stale BM25 postings, stale image rows, and
stale history records whenever a document is re-ingested under new content.

Definition of *active*:

    active = ingestion-history success hashes − version-ledger superseded hashes

Because documents ingested before Phase 4 have no version-ledger rows at all,
they are never marked superseded and therefore stay active — GC is safe
against pre-existing data.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from src.ingestion.storage.chunk_ids import chunk_id_prefix
from src.ingestion.versioning import DocumentVersionStore

logger = logging.getLogger(__name__)


@dataclass
class GcResult:
    """Outcome of an OrphanGC run."""

    collection: str = "default"
    dry_run: bool = False
    active_documents: int = 0
    chroma_deleted: int = 0
    bm25_removed: int = 0
    images_deleted: int = 0
    history_removed: int = 0
    errors: list[str] = field(default_factory=list)


class OrphanGC:
    """Coordinate orphan cleanup across Chroma, BM25, ImageStorage, and history.

    Args:
        chroma: ChromaStore instance (vector store).
        bm25: BM25Indexer instance (sparse index).
        images: ImageStorage instance.
        integrity: SQLiteIntegrityChecker instance (ingestion history).
        version_store: Optional DocumentVersionStore; when ``None`` every
            history-success hash is treated as active (no supersede info).
    """

    def __init__(
        self,
        chroma: Any,
        bm25: Any,
        images: Any,
        integrity: Any,
        version_store: DocumentVersionStore | None = None,
    ) -> None:
        self.chroma = chroma
        self.bm25 = bm25
        self.images = images
        self.integrity = integrity
        self.version_store = version_store

    # ------------------------------------------------------------------
    # Active-set computation
    # ------------------------------------------------------------------

    def active_hashes(self, collection: str) -> set[str]:
        """Return content hashes that currently count as active."""
        history_success = {
            rec["file_hash"] for rec in self.integrity.list_processed(collection)
        }
        superseded: set[str] = set()
        if self.version_store is not None:
            try:
                superseded = self.version_store.superseded_file_hashes(collection)
            except Exception as e:
                logger.warning(
                    f"Version ledger read failed ({e}); GC treats all history as active"
                )
        return history_success - superseded

    def active_prefixes(self, collection: str, active: set[str]) -> set[str]:
        """Return chunk-id prefixes for active documents.

        A document is a (path, hash) pair, and the same content hash can be
        active under several paths (a file ingested at two locations, or two
        byte-identical documents).  Prefixes therefore come from *every* active
        ledger row's ``source_path``, not one row per hash.  Hashes with no
        ledger row (pre-Phase-4 data) fall back to the history ``file_path``.
        """
        prefixes: set[str] = set()
        if self.version_store is not None:
            try:
                for src in self.version_store.active_source_paths(collection):
                    prefixes.add(chunk_id_prefix(src))
            except Exception as e:
                logger.warning(f"Active-path read failed ({e}); using history paths")
        for h in active:
            rec = self.integrity.get_record(h)
            if rec and rec.get("file_path"):
                prefixes.add(chunk_id_prefix(rec["file_path"]))
        return prefixes

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def run(self, collection: str = "default", dry_run: bool = False) -> GcResult:
        """Remove (or count, in dry-run) all orphaned data in a collection."""
        result = GcResult(collection=collection, dry_run=dry_run)
        active = self.active_hashes(collection)
        prefixes = self.active_prefixes(collection, active)
        result.active_documents = len(prefixes)

        # 1. Chroma – records whose doc_hash is missing or not active
        try:
            all_records = self.chroma.get_by_metadata(None, include_embeddings=False)
            orphan_ids = [
                r["id"]
                for r in all_records
                if r.get("metadata", {}).get("doc_hash") not in active
            ]
            if orphan_ids and not dry_run:
                self.chroma.delete(orphan_ids)
            result.chroma_deleted = len(orphan_ids)
        except Exception as e:
            result.errors.append(f"Chroma GC failed: {e}")

        # 2. BM25 – postings whose prefix is not active
        try:
            result.bm25_removed = self.bm25.prune(prefixes, collection, dry_run=dry_run)
        except Exception as e:
            result.errors.append(f"BM25 GC failed: {e}")

        # 3. Images – rows whose doc_hash is not active
        try:
            images = self.images.list_images(collection=collection)
            orphan_images = [
                img for img in images if img.get("doc_hash") not in active
            ]
            if orphan_images and not dry_run:
                for img in orphan_images:
                    self.images.delete_image(img["image_id"])
            result.images_deleted = len(orphan_images)
        except Exception as e:
            result.errors.append(f"Image GC failed: {e}")

        # 4. History – success rows whose hash is not active
        try:
            history = self.integrity.list_processed(collection)
            orphan_hashes = [
                rec["file_hash"] for rec in history if rec["file_hash"] not in active
            ]
            if orphan_hashes and not dry_run:
                for h in orphan_hashes:
                    self.integrity.remove_record(h)
            result.history_removed = len(orphan_hashes)
        except Exception as e:
            result.errors.append(f"History GC failed: {e}")

        return result
