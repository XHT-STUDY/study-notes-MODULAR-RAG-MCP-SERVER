#!/usr/bin/env python
"""Verify the golden test set against a live collection.

For each query in the golden test set, runs HybridSearch and reports the
actual retrieved source basenames alongside the expected sources — a sanity
check that the golden set is answerable from the indexed documents.

Optional ``--refresh-ids`` writes the machine-local retrieved chunk ids into
``tests/fixtures/golden_test_set.local.json`` (gitignored).  The committed
``golden_test_set.json`` intentionally leaves ``expected_chunk_ids`` empty
because chunk ids embed an absolute-path hash + LLM-refined-text hash and are
not portable across machines.

Usage:
    python scripts/verify_golden_set.py [--collection eval_default] [--top-k 10]
    python scripts/verify_golden_set.py --refresh-ids eval_default
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Set UTF-8 encoding for Windows console (GBK cannot encode emoji log markers)
if sys.platform == "win32":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_GOLDEN_SET = PROJECT_ROOT / "tests" / "fixtures" / "golden_test_set.json"
LOCAL_GOLDEN_SET = PROJECT_ROOT / "tests" / "fixtures" / "golden_test_set.local.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify the golden test set.")
    parser.add_argument(
        "--test-set", default=str(DEFAULT_GOLDEN_SET), help="Golden test set path."
    )
    parser.add_argument("--collection", default="default", help="Collection to search.")
    parser.add_argument("--top-k", type=int, default=10, help="Chunks per query.")
    parser.add_argument(
        "--refresh-ids",
        nargs="?",
        const="default",
        metavar="COLLECTION",
        help="Write machine-local retrieved chunk ids into "
        "tests/fixtures/golden_test_set.local.json.",
    )
    return parser.parse_args()


def _create_hybrid_search(settings, collection: str):
    from src.core.query_engine.query_processor import QueryProcessor
    from src.core.query_engine.hybrid_search import create_hybrid_search
    from src.core.query_engine.dense_retriever import create_dense_retriever
    from src.core.query_engine.sparse_retriever import create_sparse_retriever
    from src.ingestion.storage.bm25_indexer import BM25Indexer
    from src.libs.embedding.embedding_factory import EmbeddingFactory
    from src.libs.vector_store.vector_store_factory import VectorStoreFactory

    vector_store = VectorStoreFactory.create(settings, collection_name=collection)
    embedding_client = EmbeddingFactory.create(settings)
    dense_retriever = create_dense_retriever(
        settings=settings, embedding_client=embedding_client, vector_store=vector_store,
    )
    bm25_indexer = BM25Indexer(index_dir=f"data/db/bm25/{collection}")
    sparse_retriever = create_sparse_retriever(
        settings=settings, bm25_indexer=bm25_indexer, vector_store=vector_store,
    )
    sparse_retriever.default_collection = collection
    query_processor = QueryProcessor()
    return create_hybrid_search(
        settings=settings,
        query_processor=query_processor,
        dense_retriever=dense_retriever,
        sparse_retriever=sparse_retriever,
    )


def main() -> int:
    args = parse_args()

    from src.core.settings import load_settings
    from src.observability.evaluation.eval_runner import load_test_set

    settings = load_settings()
    test_cases = load_test_set(args.test_set)

    print(f"✅ Loaded {len(test_cases)} test cases from {args.test_set}")
    print(f"✅ Searching collection: {args.collection} (top-k={args.top_k})\n")

    hybrid = _create_hybrid_search(settings, args.collection)

    matched_ids: dict[str, list[str]] = {}
    all_ok = True
    for idx, tc in enumerate(test_cases, 1):
        results = hybrid.search(query=tc.query, top_k=args.top_k)
        results = results if isinstance(results, list) else results.results

        actual_sources = []
        chunk_ids = []
        for r in results:
            src = (r.metadata or {}).get("source_path", "")
            from pathlib import Path as _Path
            if src:
                actual_sources.append(_Path(src).name)
            chunk_ids.append(r.chunk_id)

        expected = set(tc.expected_sources or [])
        hit = bool(expected) and bool(set(actual_sources) & expected)
        all_ok = all_ok and hit
        matched_ids[tc.query] = chunk_ids

        status = "✅" if hit else ("⚠️" if expected else "⚪")
        print(f"[{idx}] {tc.query}")
        print(f"    expected_sources: {sorted(expected) or '(empty)'}")
        print(f"    retrieved_sources: {sorted(set(actual_sources))}")
        print(f"    {status} source-level hit: {'YES' if hit else 'NO'}")
        print()

    if args.refresh_ids is not None:
        _write_local_golden(args, matched_ids)
        return 0

    print("=" * 50)
    print("ALL_GOOD" if all_ok else "MISMATCH")
    return 0 if all_ok else 1


def _write_local_golden(args, matched_ids: dict[str, list[str]]) -> None:
    """Write golden_test_set.local.json with this machine's actual chunk ids."""
    from src.observability.evaluation.eval_runner import load_test_set

    with open(args.test_set, "r", encoding="utf-8") as f:
        data = json.load(f)

    refreshed = False
    for tc in data.get("test_cases", []):
        query = tc.get("query", "")
        ids = matched_ids.get(query)
        if ids:
            tc["expected_chunk_ids"] = ids
            refreshed = True

    LOCAL_GOLDEN_SET.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    if refreshed:
        print(f"📝 Wrote machine-local golden set: {LOCAL_GOLDEN_SET}")
        print("    (gitignored; use --test-set tests/fixtures/golden_test_set.local.json "
              "to evaluate with chunk-level metrics)")
    else:
        print("⚠️  No retrieval results found; local golden set may be empty.")


if __name__ == "__main__":
    sys.exit(main())
