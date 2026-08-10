#!/usr/bin/env python
"""Orphan garbage collection for the Modular RAG MCP Server (Phase 4).

Removes data whose content hash is no longer active across Chroma, BM25,
ImageStorage, and the ingestion-history table.  Use ``--dry-run`` to print
what would be removed without touching anything.

An "active" document is one present as a success row in the ingestion history
and not superseded in the version ledger.  Pre-Phase-4 data has no ledger rows
and is therefore always considered active — GC never touches legacy data.

Usage:
    python scripts/gc.py                              # GC default collection
    python scripts/gc.py --collection tech            # another collection
    python scripts/gc.py --dry-run                    # count without deleting
    python scripts/gc.py --config config/settings.yaml.example

Exit codes:
    0 - GC completed (dry-run: would-remove counts reported)
    1 - GC completed but one or more stores reported errors
    2 - configuration / discovery error
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure project root is on sys.path
_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent
sys.path.insert(0, str(_REPO_ROOT))

# Set UTF-8 encoding for Windows console
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from src.core.settings import load_settings, resolve_path  # noqa: E402  (sys.path above)

DEFAULT_COLLECTION = "default"


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Remove orphaned ingestion data (Phase 4 GC).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--collection", "-c",
        default=DEFAULT_COLLECTION,
        help=f"Collection name (default: '{DEFAULT_COLLECTION}')",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be removed without deleting anything",
    )
    parser.add_argument(
        "--config",
        default=str(_REPO_ROOT / "config" / "settings.yaml"),
        help="Path to configuration file (default: config/settings.yaml)",
    )
    return parser.parse_args()


def build_manager(collection: str):
    """Wire all four stores + version ledger into a ``DocumentManager``."""
    from src.ingestion.document_manager import DocumentManager
    from src.ingestion.storage.bm25_indexer import BM25Indexer
    from src.ingestion.storage.image_storage import ImageStorage
    from src.ingestion.versioning import DocumentVersionStore
    from src.libs.loader.file_integrity import SQLiteIntegrityChecker
    from src.libs.vector_store.vector_store_factory import VectorStoreFactory

    settings = load_settings()
    chroma = VectorStoreFactory.create(settings, collection_name=collection)
    bm25 = BM25Indexer(index_dir=str(resolve_path(f"data/db/bm25/{collection}")))
    images = ImageStorage(
        db_path=str(resolve_path("data/db/image_index.db")),
        images_root=str(resolve_path("data/images")),
    )
    integrity = SQLiteIntegrityChecker(
        db_path=str(resolve_path("data/db/ingestion_history.db"))
    )
    version_store = DocumentVersionStore(db_path=str(integrity.db_path))
    manager = DocumentManager(chroma, bm25, images, integrity, version_store=version_store)
    return manager, integrity, images


def main() -> int:
    """Entry point."""
    args = parse_args()
    load_settings(args.config)

    try:
        manager, integrity, images = build_manager(args.collection)
    except Exception as e:
        print(f"[gc] configuration error: {e}", file=sys.stderr)
        return 2

    try:
        result = manager.gc(collection=args.collection, dry_run=args.dry_run)
    finally:
        integrity.close()
        images.close()

    verb = "would remove" if args.dry_run else "removed"
    print("=" * 60)
    print(f"Orphan GC ({args.collection}) {'[dry-run]' if args.dry_run else ''}")
    print(f"  Active documents : {result.active_documents}")
    print(f"  Chroma chunks {verb} : {result.chroma_deleted}")
    print(f"  BM25 postings {verb} : {result.bm25_removed}")
    print(f"  Images {verb}       : {result.images_deleted}")
    print(f"  History rows {verb} : {result.history_removed}")
    if result.errors:
        print("Errors:")
        for err in result.errors:
            print(f"  - {err}")
    print("=" * 60)

    return 1 if result.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
