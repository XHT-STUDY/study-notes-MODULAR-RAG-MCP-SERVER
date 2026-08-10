"""Tests for Phase 4 transactional delete, the BM25 prefix fix, and update
convergence.

Covers:
- delete_document passes the *path-prefix* (not the content hash) to BM25
  (the pre-Phase-4 orphan root cause),
- capture -> execute -> rollback restores already-deleted stores when a later
  store fails,
- a successful delete never triggers rollback,
- re-ingesting a changed document under the same path drops the old BM25
  postings (add_documents remove-before-rebuild by prefix).
"""

from pathlib import Path

from src.ingestion.document_manager import DocumentManager
from src.ingestion.storage.bm25_indexer import BM25Indexer
from src.ingestion.storage.chunk_ids import chunk_id_prefix


def _make_manager(tmp_path: Path) -> DocumentManager:
    """DocumentManager over mocks with capture methods configured sanely."""
    from unittest.mock import MagicMock

    chroma = MagicMock()
    bm25 = MagicMock()
    images = MagicMock()
    integrity = MagicMock()

    integrity.compute_sha256.return_value = "abc123"
    chroma.get_by_metadata.return_value = []
    bm25.get_document_stats.return_value = []
    images.list_images.return_value = []
    integrity.get_record.return_value = None

    chroma.delete_by_metadata.return_value = 0
    bm25.remove_document.return_value = True
    images.delete_image.return_value = True
    integrity.remove_record.return_value = True

    return DocumentManager(chroma, bm25, images, integrity)


class TestBm25PrefixFix:
    def test_delete_passes_path_prefix_not_content_hash(self, tmp_path: Path):
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"hello world")

        mgr = _make_manager(tmp_path)
        mgr.delete_document(str(test_file), "default")

        # Content hash "abc123" (64-char shape in production) would never match
        # stored chunk ids; the path prefix must be used instead.
        mgr.bm25.remove_document.assert_called_once_with(
            chunk_id_prefix(str(test_file)), "default"
        )

    def test_reingest_same_path_drops_old_postings(self, tmp_path: Path):
        indexer = BM25Indexer(index_dir=str(tmp_path))
        prefix = chunk_id_prefix("doc.pdf")
        indexer.build(
            [
                {
                    "chunk_id": f"{prefix}_0000_aaaaaaaa",
                    "term_frequencies": {"oldcontent": 2},
                    "doc_length": 2,
                }
            ],
            collection="default",
        )

        # New version of the same document, same path prefix, new content.
        indexer.add_documents(
            [
                {
                    "chunk_id": f"{prefix}_0000_bbbbbbbb",
                    "term_frequencies": {"newcontent": 1},
                    "doc_length": 1,
                }
            ],
            collection="default",
            doc_id=prefix,
        )

        assert indexer.query(["oldcontent"], top_k=10) == []
        assert len(indexer.query(["newcontent"], top_k=10)) == 1

    def test_remove_with_content_hash_removes_nothing(self, tmp_path: Path):
        """The pre-Phase-4 orphan: a content hash is never a path-prefix."""
        indexer = BM25Indexer(index_dir=str(tmp_path))
        prefix = chunk_id_prefix("doc.pdf")
        indexer.build(
            [
                {
                    "chunk_id": f"{prefix}_0000_aaaaaaaa",
                    "term_frequencies": {"x": 1},
                    "doc_length": 1,
                }
            ],
            collection="default",
        )
        removed = indexer.remove_document("a" * 64, "default")
        assert removed is False
        assert len(indexer.query(["x"], top_k=10)) == 1


class TestTransactionalDelete:
    def test_delete_scopes_chroma_to_path_and_hash(self, tmp_path: Path):
        """A byte-identical document at another path must not be deleted."""
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"data")

        mgr = _make_manager(tmp_path)
        mgr.chroma.delete_by_metadata.return_value = 1

        mgr.delete_document(str(test_file), "default")

        # Chroma removal is scoped to (source_path, doc_hash) — never hash alone,
        # so a shared content hash at a different path keeps its chunks.
        mgr.chroma.delete_by_metadata.assert_called_once_with(
            {"$and": [{"source_path": str(test_file.resolve())}, {"doc_hash": "abc123"}]}
        )
        # The capture step uses the same scope, so restore never re-adds other
        # paths' chunks.
        mgr.chroma.get_by_metadata.assert_called_once_with(
            {"$and": [{"source_path": str(test_file.resolve())}, {"doc_hash": "abc123"}]},
            include_embeddings=True,
        )

    def test_successful_delete_no_rollback(self, tmp_path: Path):
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"data")

        mgr = _make_manager(tmp_path)
        mgr.chroma.get_by_metadata.return_value = [
            {
                "id": "c0",
                "text": "chunk text",
                "metadata": {"doc_hash": "abc123"},
                "embedding": [0.1, 0.2],
            }
        ]
        mgr.bm25.get_document_stats.return_value = [
            {
                "chunk_id": "c0",
                "term_frequencies": {"hello": 1},
                "doc_length": 1,
            }
        ]
        mgr.chroma.delete_by_metadata.return_value = 1

        result = mgr.delete_document(str(test_file), "default")

        assert result.success is True
        assert result.rolled_back is False
        assert result.chunks_deleted == 1
        # No restore calls on success
        mgr.chroma.upsert.assert_not_called()
        mgr.bm25.add_documents.assert_not_called()

    def test_rollback_restores_already_deleted_stores(self, tmp_path: Path):
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"data")

        mgr = _make_manager(tmp_path)
        chroma_records = [
            {
                "id": "c0",
                "text": "chunk text",
                "metadata": {"doc_hash": "abc123"},
                "embedding": [0.1, 0.2],
            }
        ]
        bm25_stats = [
            {"chunk_id": "c0", "term_frequencies": {"hello": 1}, "doc_length": 1}
        ]
        mgr.chroma.get_by_metadata.return_value = chroma_records
        mgr.bm25.get_document_stats.return_value = bm25_stats
        mgr.chroma.delete_by_metadata.return_value = 1
        mgr.images.list_images.return_value = [
            {"image_id": "img0", "file_path": "no-such-file.png"}
        ]
        mgr.images.delete_image.return_value = True
        # FileIntegrity fails -> triggers rollback of chroma + bm25
        mgr.integrity.remove_record.side_effect = RuntimeError("db locked")

        result = mgr.delete_document(str(test_file), "default")

        assert result.success is False
        assert result.rolled_back is True
        assert any("FileIntegrity" in e for e in result.errors)
        # Chroma restored from captured snapshot
        mgr.chroma.upsert.assert_called_once_with(
            [
                {
                    "id": "c0",
                    "vector": [0.1, 0.2],
                    "metadata": {"doc_hash": "abc123"},
                }
            ]
        )
        # BM25 restored from captured stats
        mgr.bm25.add_documents.assert_called_once_with(bm25_stats, collection="default")

    def test_capture_failure_aborts_without_deleting(self, tmp_path: Path):
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"data")

        mgr = _make_manager(tmp_path)
        mgr.chroma.get_by_metadata.side_effect = RuntimeError("chroma down")

        result = mgr.delete_document(str(test_file), "default")

        assert result.success is False
        assert "capture" in result.errors[0].lower()
        # Nothing was deleted
        mgr.chroma.delete_by_metadata.assert_not_called()
        mgr.bm25.remove_document.assert_not_called()

    def test_aborts_when_document_cannot_be_identified(self, tmp_path: Path):
        mgr = _make_manager(tmp_path)
        mgr.integrity.compute_sha256.side_effect = FileNotFoundError("gone")
        mgr.integrity.list_processed.return_value = []

        result = mgr.delete_document("/gone/missing.pdf", "default")

        assert result.success is False
        mgr.chroma.delete_by_metadata.assert_not_called()
