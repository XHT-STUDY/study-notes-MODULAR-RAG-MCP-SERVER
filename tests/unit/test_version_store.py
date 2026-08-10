"""Tests for the Phase 4 DocumentVersionStore (version ledger + snapshots)."""

from pathlib import Path

import pytest

from src.ingestion.versioning import DocumentVersionStore


@pytest.fixture()
def version_store(tmp_path: Path):
    db = str(tmp_path / "ingestion_history.db")
    vs = DocumentVersionStore(db, versions_root=str(tmp_path / "versions"))
    return vs


class TestRecordAndQuery:
    def test_record_success_creates_active_version(self, version_store):
        row = version_store.record_success("/docs/a.pdf", "default", "hash1")
        assert row["status"] == "success"
        assert row["is_active"] == 1
        assert row["version_no"] == 1
        active = version_store.get_active("/docs/a.pdf", "default")
        assert active is not None
        assert active["file_hash"] == "hash1"

    def test_record_success_supersedes_previous(self, version_store):
        version_store.record_success("/docs/a.pdf", "default", "hash1")
        version_store.record_success("/docs/a.pdf", "default", "hash2")

        active = version_store.get_active("/docs/a.pdf", "default")
        assert active["file_hash"] == "hash2"
        versions = version_store.list_versions("/docs/a.pdf", "default")
        assert len(versions) == 2
        # hash1 row is superseded (inactive), hash2 is active
        by_hash = {v["file_hash"]: v for v in versions}
        assert by_hash["hash1"]["is_active"] == 0
        assert by_hash["hash2"]["is_active"] == 1

    def test_version_no_increments_per_path(self, version_store):
        version_store.record_success("/a.pdf", "default", "h1")
        version_store.record_success("/a.pdf", "default", "h2")
        version_store.record_success("/b.pdf", "default", "h3")
        a_versions = version_store.list_versions("/a.pdf", "default")
        b_versions = version_store.list_versions("/b.pdf", "default")
        assert [v["version_no"] for v in a_versions] == [2, 1]
        assert [v["version_no"] for v in b_versions] == [1]

    def test_record_failure_is_inactive(self, version_store):
        version_store.record_failure("/docs/a.pdf", "default", "hashX", "boom")
        assert version_store.get_active("/docs/a.pdf", "default") is None
        versions = version_store.list_versions("/docs/a.pdf", "default")
        assert len(versions) == 1
        assert versions[0]["status"] == "failed"
        assert versions[0]["is_active"] == 0

    def test_get_version(self, version_store):
        version_store.record_success("/docs/a.pdf", "default", "h1")
        version_store.record_success("/docs/a.pdf", "default", "h2")
        v1 = version_store.get_version("/docs/a.pdf", "default", 1)
        assert v1["file_hash"] == "h1"
        assert version_store.get_version("/docs/a.pdf", "default", 99) is None

    def test_supersede_marks_all_inactive(self, version_store):
        version_store.record_success("/docs/a.pdf", "default", "h1")
        version_store.record_success("/docs/a.pdf", "default", "h2")
        count = version_store.supersede("/docs/a.pdf", "default")
        assert count == 1  # only the active row flips
        assert version_store.get_active("/docs/a.pdf", "default") is None

    def test_active_and_superseded_file_hashes(self, version_store):
        version_store.record_success("/a.pdf", "default", "h1")
        version_store.record_success("/a.pdf", "default", "h2")  # supersedes h1
        version_store.record_success("/b.pdf", "default", "h3")
        assert version_store.active_file_hashes("default") == {"h2", "h3"}
        assert version_store.superseded_file_hashes("default") == {"h1"}


class TestSnapshots:
    def test_save_snapshot_copies_file(self, tmp_path, version_store):
        src = tmp_path / "original.pdf"
        src.write_bytes(b"%PDF-1.4 hello")
        snap = version_store.save_snapshot("/docs/a.pdf", "default", "hash1", str(src))
        assert Path(snap).exists()
        assert Path(snap).read_bytes() == b"%PDF-1.4 hello"
        assert "hash1" in snap

    def test_save_snapshot_idempotent(self, tmp_path, version_store):
        src = tmp_path / "original.pdf"
        src.write_bytes(b"data")
        snap1 = version_store.save_snapshot("/docs/a.pdf", "default", "hash1", str(src))
        snap2 = version_store.save_snapshot("/docs/a.pdf", "default", "hash1", str(src))
        assert snap1 == snap2

    def test_versions_isolated_by_file_hash(self, tmp_path, version_store):
        src = tmp_path / "original.pdf"
        src.write_bytes(b"data")
        snap1 = version_store.save_snapshot("/docs/a.pdf", "default", "hash1", str(src))
        snap2 = version_store.save_snapshot("/docs/a.pdf", "default", "hash2", str(src))
        assert Path(snap1).parent != Path(snap2).parent
