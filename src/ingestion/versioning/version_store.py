"""Document version tracking with content snapshots (Phase 4).

This module provides the ledger that records *when* a document was ingested and
*which* content hash is currently active, plus the content-snapshot store that
powers rollback.

Design Principles:
- Same DB, one truth: the ledger lives in the same SQLite file as the
  ingestion history (``data/db/ingestion_history.db``) so versioning and the
  integrity checker never drift apart.
- Audit semantics: ``record_success`` marks the new hash active and supersedes
  any other active row for the same ``(source_path, collection)``.  Rollback
  re-ingests an old snapshot and records a *new* row (same ``file_hash``,
  fresh ``version_no``) — the same content can legitimately appear multiple
  times in the ledger.
- Best-effort snapshots: writing a snapshot never blocks ingestion; a missing
  snapshot only makes rollback impossible for that version.
"""

from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.core.settings import resolve_path


class DocumentVersionStore:
    """Track per-document ingestion versions and content snapshots.

    Args:
        db_path: Path to the SQLite ledger (typically the same file used by
            :class:`~src.libs.loader.file_integrity.SQLiteIntegrityChecker`).
        versions_root: Root directory for content snapshots.  Snapshots are
            written under ``{versions_root}/{collection}/{file_hash}/``.
    """

    def __init__(self, db_path: str, versions_root: str | None = None) -> None:
        self.db_path = db_path
        self.versions_root = (
            Path(resolve_path(versions_root))
            if versions_root
            else Path(resolve_path("data/versions"))
        )
        self.versions_root.mkdir(parents=True, exist_ok=True)
        self._ensure_database()

    # ------------------------------------------------------------------
    # Schema / connection helpers
    # ------------------------------------------------------------------

    def _ensure_database(self) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS document_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_path TEXT NOT NULL,
                    collection TEXT NOT NULL,
                    file_hash TEXT NOT NULL,
                    version_no INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    is_active INTEGER DEFAULT 0,
                    snapshot_path TEXT,
                    error_msg TEXT,
                    processed_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_dv_path
                ON document_versions(source_path, collection)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_dv_hash_active
                ON document_versions(file_hash, is_active)
                """
            )
            conn.commit()
        finally:
            conn.close()

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _next_version_no(self, source_path: str, collection: str) -> int:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT COALESCE(MAX(version_no), 0) FROM document_versions "
                "WHERE source_path = ? AND collection = ?",
                (source_path, collection),
            )
            return int(cursor.fetchone()[0]) + 1
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record_success(
        self,
        source_path: str,
        collection: str,
        file_hash: str,
        snapshot_path: str | None = None,
    ) -> dict[str, Any]:
        """Record a successful ingestion and make it the active version.

        Any other active row for the same ``(source_path, collection)`` is
        superseded (``is_active = 0``).

        Returns:
            The newly inserted ledger row.
        """
        now = self._now()
        version_no = self._next_version_no(source_path, collection)

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute(
                "UPDATE document_versions SET is_active = 0, updated_at = ? "
                "WHERE source_path = ? AND collection = ? AND is_active = 1",
                (now, source_path, collection),
            )
            cursor = conn.execute(
                """
                INSERT INTO document_versions
                    (source_path, collection, file_hash, version_no, status,
                     is_active, snapshot_path, error_msg, processed_at, updated_at)
                VALUES (?, ?, ?, ?, 'success', 1, ?, NULL, ?, ?)
                """,
                (source_path, collection, file_hash, version_no, snapshot_path, now, now),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM document_versions WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
            return dict(row)
        finally:
            conn.close()

    def record_failure(
        self,
        source_path: str,
        collection: str,
        file_hash: str,
        error_msg: str,
    ) -> dict[str, Any]:
        """Record a failed ingestion (non-active, no supersede)."""
        now = self._now()
        version_no = self._next_version_no(source_path, collection)

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute(
                """
                INSERT INTO document_versions
                    (source_path, collection, file_hash, version_no, status,
                     is_active, snapshot_path, error_msg, processed_at, updated_at)
                VALUES (?, ?, ?, ?, 'failed', 0, NULL, ?, ?, ?)
                """,
                (source_path, collection, file_hash, version_no, error_msg, now, now),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM document_versions WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
            return dict(row)
        finally:
            conn.close()

    def supersede(self, source_path: str, collection: str) -> int:
        """Mark every active version of a document as superseded.

        Returns:
            Number of rows updated.
        """
        now = self._now()
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "UPDATE document_versions SET is_active = 0, updated_at = ? "
                "WHERE source_path = ? AND collection = ? AND is_active = 1",
                (now, source_path, collection),
            )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------

    def list_versions(
        self, source_path: str, collection: str = "default"
    ) -> list[dict[str, Any]]:
        """Return all ledger rows for a document, newest first."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute(
                "SELECT * FROM document_versions "
                "WHERE source_path = ? AND collection = ? "
                "ORDER BY version_no DESC",
                (source_path, collection),
            )
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_active(
        self, source_path: str, collection: str = "default"
    ) -> dict[str, Any] | None:
        """Return the currently active version row, or ``None``."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute(
                "SELECT * FROM document_versions "
                "WHERE source_path = ? AND collection = ? AND is_active = 1 "
                "ORDER BY version_no DESC LIMIT 1",
                (source_path, collection),
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_version(
        self, source_path: str, collection: str, version_no: int
    ) -> dict[str, Any] | None:
        """Return a specific version row, or ``None``."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute(
                "SELECT * FROM document_versions "
                "WHERE source_path = ? AND collection = ? AND version_no = ?",
                (source_path, collection, version_no),
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_active_by_hash(
        self, file_hash: str, collection: str = "default"
    ) -> dict[str, Any] | None:
        """Return the active ledger row for a specific content hash.

        Used by orphan GC to recover a document's source path (and thus its
        chunk-id prefix) from the ledger rather than from disk.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute(
                "SELECT * FROM document_versions "
                "WHERE file_hash = ? AND collection = ? AND is_active = 1 "
                "ORDER BY version_no DESC LIMIT 1",
                (file_hash, collection),
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def active_file_hashes(self, collection: str = "default") -> set[str]:
        """Return hashes that currently have an active ledger row."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT DISTINCT file_hash FROM document_versions "
                "WHERE collection = ? AND is_active = 1",
                (collection,),
            )
            return {row[0] for row in cursor.fetchall()}
        finally:
            conn.close()

    def active_source_paths(self, collection: str = "default") -> set[str]:
        """Return the source path of *every* active ledger row.

        Unlike :meth:`get_active_by_hash` (which returns one row per hash),
        this returns all active paths — the same content hash can legitimately
        be active under several paths (a file ingested at two locations), and
        each path's chunk-id prefix must be preserved by orphan GC.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT DISTINCT source_path FROM document_versions "
                "WHERE collection = ? AND is_active = 1",
                (collection,),
            )
            return {row[0] for row in cursor.fetchall()}
        finally:
            conn.close()

    def superseded_file_hashes(self, collection: str = "default") -> set[str]:
        """Return hashes that appear in the ledger but have NO active row."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                """
                SELECT DISTINCT file_hash FROM document_versions
                WHERE collection = ?
                EXCEPT
                SELECT DISTINCT file_hash FROM document_versions
                WHERE collection = ? AND is_active = 1
                """,
                (collection, collection),
            )
            return {row[0] for row in cursor.fetchall()}
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Content snapshots
    # ------------------------------------------------------------------

    def save_snapshot(
        self,
        source_path: str,
        collection: str,
        file_hash: str,
        src_path: str,
    ) -> str:
        """Copy *src_path* into the version store and return the snapshot path.

        The destination is content-addressed: ``{versions_root}/{collection}/
        {file_hash}/{original_basename}``.  Re-saving the same content is a
        no-op (the existing snapshot is returned).

        Raises:
            OSError: If the source file cannot be read or the copy fails.
        """
        dest_dir = self.versions_root / collection / file_hash
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / Path(src_path).name

        if dest_path.exists():
            return str(dest_path)

        shutil.copy2(src_path, dest_path)
        return str(dest_path)
