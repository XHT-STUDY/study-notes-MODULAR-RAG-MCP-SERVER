"""Tests for Phase 4 DocumentManager.rollback_document guard branches.

The happy path (delete active -> re-ingest snapshot) needs a real pipeline and
embedding provider, and is covered by the e2e verification.  Here we exercise
the guard branches with a real version ledger over a temp DB + mock stores.

``source_path`` is normalised (``Path.resolve()``) by ``rollback_document``, so
these tests use real ``tmp_path`` filesystem paths that survive resolution.
"""

from pathlib import Path
from unittest.mock import MagicMock

from src.ingestion.document_manager import DocumentManager
from src.ingestion.versioning import DocumentVersionStore


def _manager(tmp_path: Path) -> DocumentManager:
    db = str(tmp_path / "ingestion_history.db")
    version_store = DocumentVersionStore(db, versions_root=str(tmp_path / "versions"))
    return DocumentManager(
        MagicMock(), MagicMock(), MagicMock(), MagicMock(),
        version_store=version_store,
    )


class TestRollbackDocument:
    def test_rollback_no_prior_version(self, tmp_path: Path):
        src = str(tmp_path / "a.pdf")
        mgr = _manager(tmp_path)
        mgr.version_store.record_success(src, "default", "h1")
        result = mgr.rollback_document(src, "default", version_no=None)
        assert result.success is False
        assert "No prior" in result.message

    def test_rollback_target_already_active(self, tmp_path: Path):
        src = str(tmp_path / "a.pdf")
        mgr = _manager(tmp_path)
        mgr.version_store.record_success(src, "default", "h1")
        result = mgr.rollback_document(src, "default", version_no=1)
        assert result.success is False
        assert "already active" in result.message

    def test_rollback_unknown_version(self, tmp_path: Path):
        src = str(tmp_path / "a.pdf")
        mgr = _manager(tmp_path)
        result = mgr.rollback_document(src, "default", version_no=42)
        assert result.success is False
        assert "not found" in result.message

    def test_rollback_failed_target(self, tmp_path: Path):
        src = str(tmp_path / "a.pdf")
        mgr = _manager(tmp_path)
        mgr.version_store.record_failure(src, "default", "h1", "boom")
        result = mgr.rollback_document(src, "default", version_no=1)
        assert result.success is False
        assert "did not ingest successfully" in result.message

    def test_rollback_missing_snapshot(self, tmp_path: Path):
        src = str(tmp_path / "a.pdf")
        mgr = _manager(tmp_path)
        # v1 ingested without a snapshot, then v2 superseded it
        mgr.version_store.record_success(src, "default", "h1", snapshot_path=None)
        mgr.version_store.record_success(
            src, "default", "h2",
            snapshot_path=str(tmp_path / "versions" / "v2.pdf"),
        )
        result = mgr.rollback_document(src, "default", version_no=1)
        assert result.success is False
        assert "snapshot missing" in result.message.lower()

    def test_rollback_version_store_unavailable(self, tmp_path: Path):
        src = str(tmp_path / "a.pdf")
        mgr = DocumentManager(
            MagicMock(), MagicMock(), MagicMock(), MagicMock()
        )  # no version_store, integrity is a mock without db_path
        result = mgr.rollback_document(src, "default")
        assert result.success is False
        assert "unavailable" in result.message

    def test_list_versions_empty_without_store(self, tmp_path: Path):
        mgr = DocumentManager(MagicMock(), MagicMock(), MagicMock(), MagicMock())
        assert mgr.list_versions(str(tmp_path / "a.pdf"), "default") == []
