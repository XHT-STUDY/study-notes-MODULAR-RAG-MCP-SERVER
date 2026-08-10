"""Tests for the Phase 4 OrphanGC."""

from unittest.mock import MagicMock

from src.ingestion.storage.chunk_ids import chunk_id_prefix
from src.ingestion.storage.orphan_gc import OrphanGC


def _make_gc(
    chroma=None,
    bm25=None,
    images=None,
    integrity=None,
    version_store=None,
):
    return OrphanGC(
        chroma or MagicMock(),
        bm25 or MagicMock(),
        images or MagicMock(),
        integrity or MagicMock(),
        version_store,
    )


class TestActiveSets:
    def test_active_hashes_excludes_superseded(self):
        integrity = MagicMock()
        integrity.list_processed.return_value = [
            {"file_hash": "h1"},
            {"file_hash": "h2"},
            {"file_hash": "h3"},
        ]
        version_store = MagicMock()
        version_store.superseded_file_hashes.return_value = {"h2"}

        gc = _make_gc(integrity=integrity, version_store=version_store)
        assert gc.active_hashes("default") == {"h1", "h3"}

    def test_active_hashes_without_ledger_treats_all_as_active(self):
        integrity = MagicMock()
        integrity.list_processed.return_value = [
            {"file_hash": "h1"},
            {"file_hash": "h2"},
        ]
        gc = _make_gc(integrity=integrity)  # no version_store
        assert gc.active_hashes("default") == {"h1", "h2"}

    def test_active_prefixes_uses_ledger_source_path(self):
        integrity = MagicMock()
        integrity.list_processed.return_value = [{"file_hash": "h1"}]
        integrity.get_record.return_value = None
        version_store = MagicMock()
        version_store.superseded_file_hashes.return_value = set()
        version_store.active_source_paths.return_value = {"/docs/a.pdf"}

        gc = _make_gc(integrity=integrity, version_store=version_store)
        assert gc.active_prefixes("default", {"h1"}) == {chunk_id_prefix("/docs/a.pdf")}

    def test_active_prefixes_includes_all_paths_for_shared_hash(self):
        """One content hash active under two paths keeps both prefixes."""
        integrity = MagicMock()
        integrity.list_processed.return_value = [{"file_hash": "h1"}]
        integrity.get_record.return_value = None
        version_store = MagicMock()
        version_store.active_source_paths.return_value = {"/docs/a.pdf", "/docs/b.pdf"}

        gc = _make_gc(integrity=integrity, version_store=version_store)
        assert gc.active_prefixes("default", {"h1"}) == {
            chunk_id_prefix("/docs/a.pdf"),
            chunk_id_prefix("/docs/b.pdf"),
        }

    def test_active_prefixes_falls_back_to_history(self):
        integrity = MagicMock()
        integrity.list_processed.return_value = [{"file_hash": "h1"}]
        integrity.get_record.return_value = {"file_path": "/docs/a.pdf"}
        version_store = MagicMock()
        version_store.active_source_paths.return_value = set()

        gc = _make_gc(integrity=integrity, version_store=version_store)
        assert gc.active_prefixes("default", {"h1"}) == {chunk_id_prefix("/docs/a.pdf")}


class TestRun:
    def test_run_deletes_orphans_across_stores(self):
        integrity = MagicMock()
        integrity.list_processed.return_value = [{"file_hash": "h1"}]
        integrity.get_record.return_value = {"file_path": "/docs/a.pdf"}
        version_store = MagicMock()
        version_store.superseded_file_hashes.return_value = set()
        version_store.get_active_by_hash.return_value = None  # fall back to history

        chroma = MagicMock()
        chroma.get_by_metadata.return_value = [
            {"id": "keep_c0", "metadata": {"doc_hash": "h1"}},
            {"id": "orphan_c0", "metadata": {"doc_hash": "stale_hash"}},
            {"id": "missing_c0", "metadata": {}},  # no doc_hash -> orphan
        ]
        bm25 = MagicMock()
        bm25.prune.return_value = 3
        images = MagicMock()
        images.list_images.return_value = [
            {"image_id": "keep_i", "doc_hash": "h1"},
            {"image_id": "orphan_i", "doc_hash": "stale_hash"},
        ]

        gc = OrphanGC(chroma, bm25, images, integrity, version_store)
        result = gc.run("default")

        # Chroma: two orphans deleted, active kept
        assert result.chroma_deleted == 2
        chroma.delete.assert_called_once_with(["orphan_c0", "missing_c0"])
        # BM25 prune keeps only the active prefix
        bm25.prune.assert_called_once_with(
            {chunk_id_prefix("/docs/a.pdf")}, "default", dry_run=False
        )
        # Images: one orphan removed
        assert result.images_deleted == 1
        images.delete_image.assert_called_once_with("orphan_i")
        # History: only h1 is active -> nothing to remove
        assert result.history_removed == 0
        assert result.active_documents == 1
        assert result.errors == []

    def test_run_dry_run_does_not_mutate(self):
        integrity = MagicMock()
        integrity.list_processed.return_value = [{"file_hash": "h1"}]
        integrity.get_record.return_value = {"file_path": "/docs/a.pdf"}

        chroma = MagicMock()
        chroma.get_by_metadata.return_value = [
            {"id": "orphan_c0", "metadata": {"doc_hash": "stale_hash"}},
        ]
        bm25 = MagicMock()
        bm25.prune.return_value = 1
        images = MagicMock()
        images.list_images.return_value = [
            {"image_id": "orphan_i", "doc_hash": "stale_hash"},
        ]

        gc = OrphanGC(chroma, bm25, images, integrity, None)
        result = gc.run("default", dry_run=True)

        assert result.chroma_deleted == 1
        assert result.images_deleted == 1
        chroma.delete.assert_not_called()
        images.delete_image.assert_not_called()
        bm25.prune.assert_called_once_with(
            {chunk_id_prefix("/docs/a.pdf")}, "default", dry_run=True
        )

    def test_run_isolated_failures(self):
        integrity = MagicMock()
        integrity.list_processed.return_value = [{"file_hash": "h1"}]
        integrity.get_record.return_value = {"file_path": "/docs/a.pdf"}

        chroma = MagicMock()
        chroma.get_by_metadata.side_effect = RuntimeError("chroma down")
        bm25 = MagicMock()
        bm25.prune.return_value = 0
        images = MagicMock()
        images.list_images.return_value = []

        gc = OrphanGC(chroma, bm25, images, integrity, None)
        result = gc.run("default")

        assert result.errors  # chroma failure recorded
        # Other stores still ran
        assert result.bm25_removed == 0
        assert result.images_deleted == 0
