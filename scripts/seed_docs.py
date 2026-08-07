#!/usr/bin/env python
"""Idempotent sample-document seeding for the Modular RAG MCP Server.

Ingests the sample PDFs under ``tests/fixtures/sample_documents/`` into a
Chroma/BM25 collection so a fresh clone has queryable data. Files already
present in the ingestion history (for the target collection) are skipped, so
re-running is safe. Pass ``--clean`` to delete each sample document across all
stores before re-ingesting (full rebuild).

Usage:
    python scripts/seed_docs.py                       # ingest missing samples
    python scripts/seed_docs.py --clean               # delete then re-ingest
    python scripts/seed_docs.py --collection tech     # different collection
    python scripts/seed_docs.py --config config/settings.yaml.example

Notes:
    - Only ``.pdf`` files are ingested: the current ``PdfLoader`` accepts PDFs
      only.  ``.txt``/``.md``/images in the sample dir are reported as skipped.
    - Ingestion requires a working embedding provider (set ``EMBEDDING_API_KEY``
      or use a local Ollama provider).  Retrieval-only features need no keys.

Exit codes:
    0 - all files ingested or skipped, none failed
    1 - some files failed (partial failure)
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
from src.ingestion.pipeline import PipelineResult, run_pipeline  # noqa: E402

DEFAULT_SAMPLE_DIR = _REPO_ROOT / "tests" / "fixtures" / "sample_documents"
DEFAULT_COLLECTION = "default"


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Seed the knowledge hub with sample documents (idempotent).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--collection", "-c",
        default=DEFAULT_COLLECTION,
        help=f"Collection name (default: '{DEFAULT_COLLECTION}')",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Delete each sample document from all stores before re-ingesting",
    )
    parser.add_argument(
        "--sample-dir",
        default=str(DEFAULT_SAMPLE_DIR),
        help="Directory containing sample documents (default: tests/fixtures/sample_documents)",
    )
    parser.add_argument(
        "--config",
        default=str(_REPO_ROOT / "config" / "settings.yaml"),
        help="Path to configuration file (default: config/settings.yaml)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print per-file pipeline details",
    )
    return parser.parse_args()


def discover_sample_pdfs(sample_dir: Path) -> list[Path]:
    """Return sorted absolute paths of ``.pdf`` files under *sample_dir*."""
    if not sample_dir.exists():
        raise FileNotFoundError(f"Sample directory does not exist: {sample_dir}")
    pdfs = sorted(p for p in sample_dir.iterdir() if p.is_file() and p.suffix.lower() == ".pdf")
    return [p.resolve() for p in pdfs]


def list_ingested_paths(collection: str) -> set[str]:
    """Return the set of source paths already ingested for *collection*.

    Reads the ingestion-history table directly — the same table
    ``DocumentManager.list_documents`` is built on — without opening a second
    Chroma client while the pipeline writes.
    """
    from src.libs.loader.file_integrity import SQLiteIntegrityChecker

    checker = SQLiteIntegrityChecker(db_path=str(resolve_path("data/db/ingestion_history.db")))
    try:
        records = checker.list_processed(collection)
        return {str(rec["file_path"]) for rec in records}
    finally:
        checker.close()


def delete_sample_document(source_path: str, collection: str) -> None:
    """Delete one document across all stores via ``DocumentManager``."""
    from src.core.settings import load_settings as _ls
    from src.ingestion.document_manager import DocumentManager
    from src.ingestion.storage.bm25_indexer import BM25Indexer
    from src.ingestion.storage.image_storage import ImageStorage
    from src.libs.loader.file_integrity import SQLiteIntegrityChecker
    from src.libs.vector_store.vector_store_factory import VectorStoreFactory

    settings = _ls()
    chroma = VectorStoreFactory.create(settings, collection_name=collection)
    bm25 = BM25Indexer(index_dir=str(resolve_path(f"data/db/bm25/{collection}")))
    images = ImageStorage(
        db_path=str(resolve_path("data/db/image_index.db")),
        images_root=str(resolve_path("data/images")),
    )
    integrity = SQLiteIntegrityChecker(db_path=str(resolve_path("data/db/ingestion_history.db")))
    manager = DocumentManager(chroma, bm25, images, integrity)
    result = manager.delete_document(source_path, collection=collection)
    integrity.close()
    images.close()
    if not result.success:
        raise RuntimeError(f"delete incomplete: {result.errors}")


def print_summary(results: list[PipelineResult], skipped: list[Path], failed: list[PipelineResult]) -> None:
    """Print the seed summary."""
    print("\n" + "=" * 60)
    print("SEED SUMMARY")
    print("=" * 60)
    print(f"Ingested:   {len([r for r in results if r.success])}")
    print(f"Skipped:    {len(skipped)}")
    print(f"Failed:     {len(failed)}")
    print("=" * 60)


def main() -> int:
    """Entry point. Returns 0 when nothing failed."""
    args = parse_args()

    print(f"[*] Seeding sample documents -> collection '{args.collection}'")
    print(f"    sample-dir: {args.sample_dir}")
    print(f"    config:     {args.config}")

    # Load config first (fail fast on config errors).
    try:
        load_settings(args.config)
    except Exception as exc:
        print(f"[FAIL] Configuration error: {exc}")
        return 2

    # Discover sample PDFs.
    try:
        pdfs = discover_sample_pdfs(Path(args.sample_dir))
    except FileNotFoundError as exc:
        print(f"[FAIL] {exc}")
        return 2
    if not pdfs:
        print(f"[WARN] No PDF files found under {args.sample_dir}")
        return 0

    print(f"[INFO] Found {len(pdfs)} sample PDF(s):")
    for p in pdfs:
        print(f"       - {p.name}")

    # Existing documents in this collection (idempotency).
    ingested_paths: set[str] = set()
    if not args.clean:
        ingested_paths = list_ingested_paths(args.collection)
        print(f"[INFO] Already-ingested in '{args.collection}': {len(ingested_paths)} document(s)")

    results: list[PipelineResult] = []
    skipped: list[Path] = []
    failed: list[PipelineResult] = []

    for pdf in pdfs:
        source = str(pdf)
        print(f"\n--- {pdf.name} ---")

        if args.clean:
            print("  [clean] deleting from all stores...")
            try:
                delete_sample_document(source, args.collection)
                print("  [clean] deleted")
            except Exception as exc:
                print(f"  [clean] delete failed (continuing): {exc}")

        if not args.clean and source in ingested_paths:
            print("  [SKIP] already ingested")
            skipped.append(pdf)
            continue

        try:
            result = run_pipeline(
                source,
                settings_path=args.config,
                collection=args.collection,
                force=args.clean,
            )
            results.append(result)
            if result.success:
                was_skipped = bool(result.stages.get("integrity", {}).get("skipped", False))
                if was_skipped:
                    print("  [SKIP] integrity hash says already processed")
                    skipped.append(pdf)
                else:
                    print(f"  [OK] {result.chunk_count} chunks, {result.image_count} images")
            else:
                print(f"  [FAIL] {result.error}")
                failed.append(result)
        except Exception as exc:
            print(f"  [FAIL] {exc}")
            failed.append(PipelineResult(success=False, file_path=source, error=str(exc)))

    print_summary(results, skipped, failed)

    if failed:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
