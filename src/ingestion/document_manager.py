"""Cross-store document lifecycle management.

This module provides a single entry-point for listing, inspecting, deleting,
rolling back, and garbage-collecting documents across all storage backends
(ChromaDB, BM25, ImageStorage, FileIntegrityChecker, and the Phase 4 version
ledger).

Design Principles:
- Coordinated: one call cascades into all relevant stores.
- Transactional: ``delete_document`` captures a snapshot first and restores it
  if any store fails (no partial deletes).
- Fail-safe: partial failures are reported but do not abort remaining stores.
- Read-only safe: list / stats / detail methods never mutate data.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.ingestion.storage.chunk_ids import chunk_id_prefix
from src.ingestion.storage.orphan_gc import OrphanGC
from src.ingestion.versioning import DocumentVersionStore

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result data-classes
# ---------------------------------------------------------------------------

@dataclass
class DocumentInfo:
    """Summary information about an ingested document."""

    source_path: str
    source_hash: str
    collection: Optional[str] = None
    chunk_count: int = 0
    image_count: int = 0
    processed_at: Optional[str] = None


@dataclass
class DocumentDetail(DocumentInfo):
    """Extended document info including chunk IDs and image IDs."""

    chunk_ids: List[str] = field(default_factory=list)
    image_ids: List[str] = field(default_factory=list)


@dataclass
class DeleteResult:
    """Outcome of a delete_document operation."""

    success: bool
    chunks_deleted: int = 0
    bm25_removed: bool = False
    images_deleted: int = 0
    integrity_removed: bool = False
    rolled_back: bool = False
    errors: List[str] = field(default_factory=list)


@dataclass
class RollbackResult:
    """Outcome of a rollback_document operation."""

    success: bool
    version_no: int | None = None
    file_hash: str | None = None
    message: str = ""
    details: dict[str, Any] | None = None


@dataclass
class CollectionStats:
    """Aggregate statistics for a collection."""

    collection: Optional[str] = None
    document_count: int = 0
    chunk_count: int = 0
    image_count: int = 0


# ---------------------------------------------------------------------------
# DocumentManager
# ---------------------------------------------------------------------------

class DocumentManager:
    """Coordinate document lifecycle across all storage backends.

    Args:
        chroma_store: ChromaStore instance (vector store).
        bm25_indexer: BM25Indexer instance (sparse index).
        image_storage: ImageStorage instance (image files + SQLite index).
        file_integrity: SQLiteIntegrityChecker instance (ingestion history).
        version_store: Optional DocumentVersionStore.  When omitted it is
            lazily created from ``file_integrity.db_path`` on first need
            (rollback / gc / list_versions).
    """

    def __init__(
        self,
        chroma_store: Any,
        bm25_indexer: Any,
        image_storage: Any,
        file_integrity: Any,
        version_store: DocumentVersionStore | None = None,
    ) -> None:
        self.chroma = chroma_store
        self.bm25 = bm25_indexer
        self.images = image_storage
        self.integrity = file_integrity
        self.version_store = version_store

    def _ensure_version_store(self) -> DocumentVersionStore | None:
        """Lazily create the version ledger from the integrity DB path.

        The ``isinstance(db_path, str)`` guard keeps MagicMock-based tests from
        spuriously constructing a real ledger (MagicMock auto-creates any
        attribute, so ``getattr(..., None)`` would not return ``None``).
        """
        if self.version_store is None:
            db_path = getattr(self.integrity, "db_path", None)
            if isinstance(db_path, str):
                try:
                    self.version_store = DocumentVersionStore(db_path=db_path)
                except Exception as e:
                    logger.warning(f"Version store unavailable: {e}")
        return self.version_store

    # ------------------------------------------------------------------
    # list_documents
    # ------------------------------------------------------------------

    def list_documents(
        self, collection: Optional[str] = None
    ) -> List[DocumentInfo]:
        """Return a list of ingested documents.

        Combines information from the integrity checker (source_path,
        hash, processed_at) with counts from ChromaDB and ImageStorage.

        Args:
            collection: Optional collection filter.

        Returns:
            List of ``DocumentInfo`` objects.
        """
        records = self.integrity.list_processed(collection)

        docs: List[DocumentInfo] = []
        for rec in records:
            source_hash = rec["file_hash"]
            source_path = rec["file_path"]
            coll = rec.get("collection")

            # Count chunks in Chroma
            chunk_count = self._count_chunks(source_hash)

            # Count images
            image_count = self._count_images(source_hash)

            docs.append(
                DocumentInfo(
                    source_path=source_path,
                    source_hash=source_hash,
                    collection=coll,
                    chunk_count=chunk_count,
                    image_count=image_count,
                    processed_at=rec.get("processed_at"),
                )
            )

        return docs

    # ------------------------------------------------------------------
    # get_document_detail
    # ------------------------------------------------------------------

    def get_document_detail(self, doc_id: str) -> Optional[DocumentDetail]:
        """Get detailed information about a single document.

        *doc_id* is matched against the ``source_hash`` stored in the
        integrity checker.

        Args:
            doc_id: The document's source_hash.

        Returns:
            ``DocumentDetail`` with chunk/image IDs, or *None* if not found.
        """
        # Look up integrity record
        all_records = self.integrity.list_processed()
        record = None
        for rec in all_records:
            if rec["file_hash"] == doc_id:
                record = rec
                break

        if record is None:
            return None

        source_hash = record["file_hash"]

        # Collect chunk IDs from Chroma
        chunk_ids = self._get_chunk_ids(source_hash)

        # Collect image IDs
        image_ids = self._get_image_ids(source_hash)

        return DocumentDetail(
            source_path=record["file_path"],
            source_hash=source_hash,
            collection=record.get("collection"),
            chunk_count=len(chunk_ids),
            image_count=len(image_ids),
            processed_at=record.get("processed_at"),
            chunk_ids=chunk_ids,
            image_ids=image_ids,
        )

    # ------------------------------------------------------------------
    # delete_document (transactional)
    # ------------------------------------------------------------------

    def delete_document(
        self,
        source_path: str,
        collection: str = "default",
        source_hash: Optional[str] = None,
    ) -> DeleteResult:
        """Delete a document from all storage backends, transactionally.

        Coordinates deletion across ChromaDB, BM25, ImageStorage, FileIntegrity,
        and (best-effort) the version ledger.  Before deleting, a snapshot of
        every affected record is captured; if any store fails, the already
        deleted stores are restored from that snapshot and ``DeleteResult`` is
        marked ``rolled_back=True``.

        The document is identified by the (source_path, source_hash) pair —
        Chroma chunks are removed only where *both* match, so a byte-identical
        document at another path is never deleted.  BM25 postings are keyed by
        the chunk-id **prefix** derived from *source_path*, so *source_path*
        must match the path used at ingestion (for rollback, the logical
        source path).

        Args:
            source_path: Original filesystem path of the document.
            collection: Collection the document belongs to.
            source_hash: Pre-computed SHA-256 hash.  When provided the
                method will not attempt to read the source file.

        Returns:
            ``DeleteResult`` summarising what was cleaned.
        """
        result = DeleteResult(success=True)

        # Normalise the path the same way the storage layers do (the loader
        # resolves to absolute), so the BM25 prefix and history lookups agree
        # with the chunks actually stored.
        source_path = str(Path(source_path).resolve())

        # Resolve hash – prefer caller-supplied, then file, then DB lookup
        if source_hash is None:
            try:
                source_hash = self.integrity.compute_sha256(source_path)
            except Exception as e:
                source_hash = self._hash_from_path(source_path)
                if source_hash is None:
                    result.success = False
                    result.errors.append(f"Cannot identify document: {e}")
                    return result

        prefix = chunk_id_prefix(source_path)

        # ── Phase 1: capture snapshot (read-only) ──
        captured = self._capture_delete_snapshot(source_path, collection, source_hash, prefix)
        if captured is None:
            result.success = False
            result.errors.append(
                "Failed to capture delete snapshot; aborted to avoid partial delete"
            )
            return result

        executed: list[str] = []

        # 1. ChromaDB – delete chunks matching this (path, hash) pair only.
        #    Scoping by source_path too keeps a byte-identical document at
        #    another path from being deleted (a document is a (path, hash)
        #    pair; see GC active_prefixes).
        try:
            count = self.chroma.delete_by_metadata(
                {"$and": [{"source_path": source_path}, {"doc_hash": source_hash}]}
            )
            result.chunks_deleted = count
            executed.append("chroma")
        except Exception as e:
            result.errors.append(f"ChromaDB delete failed: {e}")

        # 2. BM25 – remove postings sharing this document's chunk-id prefix
        try:
            result.bm25_removed = self.bm25.remove_document(prefix, collection)
            executed.append("bm25")
        except Exception as e:
            result.errors.append(f"BM25 remove failed: {e}")

        # 3. ImageStorage – delete images by doc_hash
        try:
            deleted_imgs = 0
            for img in captured["images"]:
                if self.images.delete_image(img["image_id"]):
                    deleted_imgs += 1
            result.images_deleted = deleted_imgs
            executed.append("images")
        except Exception as e:
            result.errors.append(f"ImageStorage delete failed: {e}")

        # 4. FileIntegrity – remove the ingestion record
        try:
            result.integrity_removed = self.integrity.remove_record(source_hash)
            executed.append("integrity")
        except Exception as e:
            result.errors.append(f"FileIntegrity remove failed: {e}")

        # ── Phase 2: rollback on any failure ──
        if result.errors:
            result.success = False
            self._rollback_delete(captured, executed, collection, source_path, result)
            return result

        # ── Phase 3: best-effort ledger cleanup on full success ──
        vs = self._ensure_version_store()
        if vs is not None:
            try:
                vs.supersede(source_path, collection)
            except Exception as e:
                logger.warning(
                    f"Version ledger supersede failed after delete of {source_path}: {e}"
                )

        return result

    # ------------------------------------------------------------------
    # rollback_document
    # ------------------------------------------------------------------

    def rollback_document(
        self,
        source_path: str,
        collection: str = "default",
        version_no: int | None = None,
    ) -> RollbackResult:
        """Roll a document back to a previous version (snapshot + re-ingest).

        Deletes the currently active version's index data transactionally,
        then re-ingests the target version's content snapshot under the
        original *source_path* (so chunk IDs stay identical).  The re-ingest
        records a *new* active ledger row — a full audit trail.

        Args:
            source_path: Logical/identity path of the document.
            collection: Collection name.
            version_no: Target version to restore.  When ``None``, the most
                recent successful non-active version is used.

        Returns:
            ``RollbackResult`` with the restored version number and hash.
        """
        vs = self._ensure_version_store()
        if vs is None:
            return RollbackResult(success=False, message="Version store unavailable")

        # Normalise the path to the resolved form the ledger stores (matching
        # the chunk-id prefix), so lookups work regardless of input style.
        source_path = str(Path(source_path).resolve())

        active = vs.get_active(source_path, collection)
        target: dict[str, Any] | None

        if version_no is None:
            versions = vs.list_versions(source_path, collection)
            candidates = [
                v for v in versions if not v["is_active"] and v["status"] == "success"
            ]
            if not candidates:
                return RollbackResult(
                    success=False, message="No prior successful version to roll back to"
                )
            target = candidates[0]
        else:
            target = vs.get_version(source_path, collection, version_no)

        if target is None:
            return RollbackResult(
                success=False, message=f"Version {version_no} not found"
            )
        if target["status"] != "success":
            return RollbackResult(
                success=False,
                version_no=target["version_no"],
                message="Target version did not ingest successfully",
            )
        if active is not None and active["id"] == target["id"]:
            return RollbackResult(
                success=False,
                version_no=target["version_no"],
                file_hash=target["file_hash"],
                message="Target version is already active",
            )

        snapshot = target.get("snapshot_path")
        if not snapshot or not Path(snapshot).exists():
            return RollbackResult(
                success=False,
                version_no=target["version_no"],
                file_hash=target["file_hash"],
                message="Content snapshot missing; cannot roll back",
            )

        # Delete the current active version's data (transactional).
        if active is not None:
            del_result = self.delete_document(
                source_path, collection, source_hash=active["file_hash"]
            )
            if not del_result.success:
                return RollbackResult(
                    success=False,
                    version_no=target["version_no"],
                    file_hash=target["file_hash"],
                    message=f"Failed to remove current version: {del_result.errors}",
                )

        # Re-ingest the snapshot under the original logical path.
        from src.ingestion.pipeline import run_pipeline

        result = run_pipeline(
            snapshot, collection=collection, force=True, logical_source_path=source_path
        )
        if not result.success:
            return RollbackResult(
                success=False,
                version_no=target["version_no"],
                file_hash=target["file_hash"],
                message=f"Re-ingestion failed: {result.error}",
            )

        return RollbackResult(
            success=True,
            version_no=target["version_no"],
            file_hash=target["file_hash"],
            message="Rollback successful",
        )

    # ------------------------------------------------------------------
    # list_versions / gc
    # ------------------------------------------------------------------

    def list_versions(
        self, source_path: str, collection: str = "default"
    ) -> list[dict[str, Any]]:
        """Return the version ledger rows for a document, newest first."""
        vs = self._ensure_version_store()
        if vs is None:
            return []
        return vs.list_versions(source_path, collection)

    def gc(self, collection: str = "default", dry_run: bool = False):
        """Run orphan GC across the collection's storage backends."""
        gc = OrphanGC(
            self.chroma, self.bm25, self.images, self.integrity,
            self._ensure_version_store(),
        )
        return gc.run(collection, dry_run=dry_run)

    # ------------------------------------------------------------------
    # get_collection_stats
    # ------------------------------------------------------------------

    def get_collection_stats(
        self, collection: Optional[str] = None
    ) -> CollectionStats:
        """Return aggregate statistics for a collection.

        Args:
            collection: Collection name.  When *None*, stats span
                all collections.

        Returns:
            ``CollectionStats`` dataclass.
        """
        docs = self.list_documents(collection)
        chunk_total = sum(d.chunk_count for d in docs)
        image_total = sum(d.image_count for d in docs)

        return CollectionStats(
            collection=collection,
            document_count=len(docs),
            chunk_count=chunk_total,
            image_count=image_total,
        )

    # ------------------------------------------------------------------
    # Transaction helpers
    # ------------------------------------------------------------------

    def _capture_delete_snapshot(
        self,
        source_path: str,
        collection: str,
        source_hash: str,
        prefix: str,
    ) -> dict[str, Any] | None:
        """Capture everything needed to restore a document after deletion.

        Returns:
            Dict with ``chroma`` / ``bm25`` / ``images`` / ``integrity``
            snapshots, or ``None`` if capture fails (caller aborts the delete).
        """
        try:
            # Capture the same (path, hash) scope the delete will remove, so a
            # shared content hash at another path is never captured or restored.
            chroma_records = self.chroma.get_by_metadata(
                {"$and": [{"source_path": source_path}, {"doc_hash": source_hash}]},
                include_embeddings=True,
            )
            bm25_stats = self.bm25.get_document_stats(prefix, collection)
            images = self.images.list_images(doc_hash=source_hash)
            # Read image bytes now so rollback can restore files even after
            # delete_image() removed them from disk.
            for img in images:
                try:
                    img_path = Path(img["file_path"])
                    if img_path.exists():
                        img["_bytes"] = img_path.read_bytes()
                        img["_extension"] = img_path.suffix.lstrip(".") or "png"
                    else:
                        img["_bytes"] = None
                except Exception:
                    img["_bytes"] = None
            integrity = self.integrity.get_record(source_hash)
        except Exception as e:
            logger.warning(f"delete_document capture failed for {source_path}: {e}")
            return None

        return {
            "chroma": chroma_records or [],
            "bm25": bm25_stats or [],
            "images": images or [],
            "integrity": integrity,
        }

    def _rollback_delete(
        self,
        captured: dict[str, Any],
        executed: list[str],
        collection: str,
        source_path: str,
        result: DeleteResult,
    ) -> None:
        """Restore already-deleted stores when a later store failed."""
        restored: list[str] = []

        # 1. Chroma
        if "chroma" in executed and result.chunks_deleted > 0:
            records = [
                {"id": r["id"], "vector": r["embedding"], "metadata": r["metadata"]}
                for r in captured["chroma"]
                if r.get("embedding") is not None
            ]
            if records:
                try:
                    self.chroma.upsert(records)
                    restored.append("chroma")
                except Exception as e:
                    result.errors.append(f"ChromaDB restore failed: {e}")

        # 2. BM25
        if "bm25" in executed and result.bm25_removed:
            try:
                if captured["bm25"]:
                    self.bm25.add_documents(captured["bm25"], collection=collection)
                restored.append("bm25")
            except Exception as e:
                result.errors.append(f"BM25 restore failed: {e}")

        # 3. Images
        if "images" in executed and result.images_deleted > 0:
            for img in captured["images"]:
                try:
                    if img.get("_bytes") is not None:
                        self.images.save_image(
                            image_id=img["image_id"],
                            image_data=img["_bytes"],
                            collection=img.get("collection"),
                            doc_hash=img.get("doc_hash"),
                            page_num=img.get("page_num"),
                            extension=img.get("_extension", "png"),
                        )
                    else:
                        # Best-effort: the file may still exist if the delete
                        # never reached it.
                        self.images.register_image(
                            image_id=img["image_id"],
                            file_path=img["file_path"],
                            collection=img.get("collection"),
                            doc_hash=img.get("doc_hash"),
                            page_num=img.get("page_num"),
                        )
                except Exception as e:
                    result.errors.append(
                        f"Image restore failed for {img.get('image_id')}: {e}"
                    )
            restored.append("images")

        # 4. Integrity
        if "integrity" in executed and result.integrity_removed:
            rec = captured["integrity"]
            if rec:
                try:
                    self.integrity.mark_success(
                        rec["file_hash"], rec["file_path"], rec.get("collection")
                    )
                    restored.append("integrity")
                except Exception as e:
                    result.errors.append(f"FileIntegrity restore failed: {e}")

        result.rolled_back = bool(restored)
        logger.warning(
            f"delete_document rolled back {len(restored)} store(s) for {source_path}: "
            f"{result.errors}"
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _count_chunks(self, source_hash: str) -> int:
        """Count chunks in Chroma that belong to *source_hash*."""
        try:
            results = self.chroma.collection.get(
                where={"doc_hash": source_hash}, include=[]
            )
            return len(results.get("ids", []))
        except Exception:
            return 0

    def _get_chunk_ids(self, source_hash: str) -> List[str]:
        """Return chunk IDs from Chroma matching *source_hash*."""
        try:
            results = self.chroma.collection.get(
                where={"doc_hash": source_hash}, include=[]
            )
            ids = results.get("ids", [])
            return list(ids) if ids else []
        except Exception:
            return []

    def _count_images(self, source_hash: str) -> int:
        """Count images belonging to *source_hash*."""
        try:
            return len(self.images.list_images(doc_hash=source_hash))
        except Exception:
            return 0

    def _get_image_ids(self, source_hash: str) -> List[str]:
        """Return image IDs belonging to *source_hash*."""
        try:
            imgs = self.images.list_images(doc_hash=source_hash)
            return [img["image_id"] for img in imgs]
        except Exception:
            return []

    def _hash_from_path(self, source_path: str) -> Optional[str]:
        """Try to find a source_hash from integrity records by path."""
        try:
            query = str(Path(source_path).resolve())
            for rec in self.integrity.list_processed():
                if rec["file_path"] == query:
                    return str(rec["file_hash"])
        except Exception:
            pass
        return None
