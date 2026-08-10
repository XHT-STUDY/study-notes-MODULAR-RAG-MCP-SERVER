"""Regression tests for ChromaStore.get_by_metadata (Phase 4).

chromadb 1.x returns ``embeddings`` from ``collection.get()`` as a numpy
2-D array.  ``get_by_metadata`` must tolerate that — the pre-fix code tested
``if embeddings and ...`` which calls ``bool(ndarray)`` and raises
"truth value of an array with more than one element is ambiguous" whenever
more than one record is returned.  The Phase 4 transactional-delete capture
path was the first caller to hit ``where`` + embeddings together.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pytest

from src.libs.vector_store.chroma_store import ChromaStore


def _make_store(get_return: dict) -> ChromaStore:
    """Build a ChromaStore without real ChromaDB by skipping __init__."""
    store = object.__new__(ChromaStore)
    store.collection = MagicMock()
    store.collection.get.return_value = get_return
    return store


class TestGetByMetadataNumpyEmbeddings:
    def test_multiple_records_with_numpy_embeddings(self) -> None:
        """The failure mode: >1 record, embeddings returned as ndarray."""
        store = _make_store(
            {
                "ids": ["c0", "c1"],
                "documents": ["text0", "text1"],
                "metadatas": [{"doc_hash": "h"}, {"doc_hash": "h"}],
                "embeddings": np.array([[0.1, 0.2], [0.3, 0.4]]),
            }
        )
        records = store.get_by_metadata(
            {"doc_hash": "h"}, include_embeddings=True
        )
        assert len(records) == 2
        # Embeddings are converted to plain lists (JSON-safe for restore)
        assert records[0]["embedding"] == [0.1, 0.2]
        assert records[1]["embedding"] == [0.3, 0.4]

    def test_single_record_embeddings(self) -> None:
        store = _make_store(
            {
                "ids": ["c0"],
                "documents": ["text0"],
                "metadatas": [{"doc_hash": "h"}],
                "embeddings": np.array([[0.5, 0.6]]),
            }
        )
        records = store.get_by_metadata({"doc_hash": "h"}, include_embeddings=True)
        assert records[0]["embedding"] == [0.5, 0.6]

    def test_embeddings_omitted_when_not_requested(self) -> None:
        store = _make_store(
            {
                "ids": ["c0"],
                "documents": ["text0"],
                "metadatas": [{"doc_hash": "h"}],
            }
        )
        records = store.get_by_metadata({"doc_hash": "h"}, include_embeddings=False)
        assert "embedding" not in records[0]

    def test_no_where_clause_scans_whole_collection(self) -> None:
        store = _make_store(
            {
                "ids": ["c0"],
                "documents": ["text0"],
                "metadatas": [{"doc_hash": "h"}],
                "embeddings": np.array([[0.1, 0.2]]),
            }
        )
        records = store.get_by_metadata(None, include_embeddings=True)
        assert len(records) == 1
        store.collection.get.assert_called_once_with(
            where=None, include=["metadatas", "documents", "embeddings"]
        )

    def test_empty_result(self) -> None:
        store = _make_store({"ids": [], "documents": [], "metadatas": []})
        assert store.get_by_metadata({"doc_hash": "nope"}, include_embeddings=True) == []

    def test_raises_runtime_error_on_collection_failure(self) -> None:
        store = _make_store({})
        store.collection.get.side_effect = RuntimeError("chroma down")
        with pytest.raises(RuntimeError, match="Failed to get records"):
            store.get_by_metadata({"doc_hash": "h"}, include_embeddings=True)
