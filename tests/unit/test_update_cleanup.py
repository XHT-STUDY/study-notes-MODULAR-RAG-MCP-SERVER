"""Tests for the Phase 4 update cleanup (pipeline._cleanup_old_version).

The same content hash can legitimately live at several paths (a file ingested
twice, or two byte-identical documents).  Regression test for the over-deletion
found in e2e: cleanup must be scoped to the updated path, and the
doc_hash-keyed stores (images / history) must only be touched once the old hash
is *fully superseded* (no active ledger row anywhere).
"""

from unittest.mock import MagicMock

from src.ingestion.pipeline import IngestionPipeline


def _fake_pipeline(*, has_version_store: bool = True, active_hashes: set | None = None):
    class FP:
        collection = "test"

    fp = FP()
    fp.vector_upserter = MagicMock()
    fp.vector_upserter.vector_store = MagicMock()
    fp.image_storage = MagicMock()
    fp.image_storage.list_images.return_value = [{"image_id": "img0"}]
    fp.image_storage.delete_image.return_value = True
    fp.integrity_checker = MagicMock()
    fp.integrity_checker.remove_record.return_value = True

    if has_version_store:
        fp.version_store = MagicMock()
        fp.version_store.active_file_hashes.return_value = active_hashes or set()
    return fp


class TestUpdateCleanupScoping:
    def test_chroma_delete_is_scoped_to_path_and_hash(self):
        fp = _fake_pipeline(active_hashes={"oldhash"})
        IngestionPipeline._cleanup_old_version(fp, "/docs/a.pdf", "oldhash", "test")
        fp.vector_upserter.vector_store.delete_by_metadata.assert_called_once_with(
            {"$and": [{"source_path": "/docs/a.pdf"}, {"doc_hash": "oldhash"}]}
        )

    def test_images_and_history_kept_when_hash_still_active_elsewhere(self):
        fp = _fake_pipeline(active_hashes={"oldhash"})
        IngestionPipeline._cleanup_old_version(fp, "/docs/a.pdf", "oldhash", "test")
        fp.image_storage.list_images.assert_not_called()
        fp.image_storage.delete_image.assert_not_called()
        fp.integrity_checker.remove_record.assert_not_called()

    def test_images_and_history_cleaned_when_fully_superseded(self):
        fp = _fake_pipeline(active_hashes=set())
        IngestionPipeline._cleanup_old_version(fp, "/docs/a.pdf", "oldhash", "test")
        fp.image_storage.list_images.assert_called_once_with(doc_hash="oldhash")
        fp.image_storage.delete_image.assert_called_once_with("img0")
        fp.integrity_checker.remove_record.assert_called_once_with("oldhash")

    def test_conservative_when_ledger_unavailable(self):
        fp = _fake_pipeline(has_version_store=False)
        IngestionPipeline._cleanup_old_version(fp, "/docs/a.pdf", "oldhash", "test")
        # Chroma still scoped-clean; images/history untouched without ledger proof
        fp.vector_upserter.vector_store.delete_by_metadata.assert_called_once()
        fp.image_storage.list_images.assert_not_called()
        fp.integrity_checker.remove_record.assert_not_called()

    def test_chroma_failure_is_best_effort(self):
        fp = _fake_pipeline(active_hashes=set())
        fp.vector_upserter.vector_store.delete_by_metadata.side_effect = RuntimeError("boom")
        IngestionPipeline._cleanup_old_version(fp, "/docs/a.pdf", "oldhash", "test")
        # Chroma failed but images/history still cleaned; no exception escapes
        fp.image_storage.list_images.assert_called_once_with(doc_hash="oldhash")
