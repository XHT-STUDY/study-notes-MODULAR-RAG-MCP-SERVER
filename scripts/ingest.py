#!/usr/bin/env python
"""Ingestion script for the Modular RAG MCP Server.

Ingests PDF files into the knowledge hub and prints a stage-by-stage
pipeline report for every file: integrity check, document loading,
chunking, LLM transforms (refine / enrich / caption), encoding and
storage — each with its outputs and elapsed time.

The report builder lives in ``src/ingestion/pipeline_report.py`` and is
shared with the Streamlit dashboard's ingestion manager.

Usage:
    # Ingest one PDF with the default pipeline report
    python scripts/ingest.py --path documents/report.pdf --collection contracts

    # Process all PDFs in a directory recursively
    python scripts/ingest.py --path documents/ --collection technical_docs

    # Force re-processing (ignore previous ingestion)
    python scripts/ingest.py --path documents/report.pdf --collection contracts --force

    # List files that would be processed
    python scripts/ingest.py --path documents/ --dry-run

    # Show the INFO run logs that are suppressed by default
    python scripts/ingest.py --path documents/ --verbose

Exit codes:
    0 - Success (all files processed)
    1 - Partial failure (some files failed)
    2 - Complete failure (all files failed or configuration error)
"""

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import List

# Ensure project root is on sys.path
_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent
sys.path.insert(0, str(_REPO_ROOT))

# Set UTF-8 encoding for Windows console
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from src.core.settings import load_settings, Settings
from src.core.trace import TraceContext, TraceCollector
from src.ingestion.pipeline import IngestionPipeline, PipelineResult
from src.ingestion.pipeline_report import build_file_report
from src.observability.logger import get_logger

logger = get_logger(__name__)

_LINE = "=" * 68


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Ingest documents into the Modular RAG knowledge hub.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--path", "-p",
        required=True,
        help="Path to file or directory to ingest. "
             "If directory, processes all PDF files recursively."
    )

    parser.add_argument(
        "--collection", "-c",
        default="default",
        help="Collection name for organizing documents (default: 'default')"
    )

    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Force re-processing even if file was previously ingested"
    )

    parser.add_argument(
        "--config",
        default=str(_REPO_ROOT / "config" / "settings.yaml"),
        help="Path to configuration file (default: config/settings.yaml)"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show INFO run logs (suppressed by default so the pipeline "
             "report stays readable)"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List files that would be processed without actually processing"
    )

    return parser.parse_args()


def discover_files(path: str, extensions: List[str] = None) -> List[Path]:
    """Discover files to process from path.

    Args:
        path: File or directory path
        extensions: List of file extensions to include (default: ['.pdf'])

    Returns:
        List of file paths to process
    """
    if extensions is None:
        extensions = ['.pdf']

    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"Path does not exist: {path}")

    if path.is_file():
        if path.suffix.lower() in extensions:
            return [path]
        else:
            raise ValueError(f"Unsupported file type: {path.suffix}. Supported: {extensions}")

    # Directory: recursively find all matching files
    files = []
    for ext in extensions:
        files.extend(path.rglob(f"*{ext}"))
        files.extend(path.rglob(f"*{ext.upper()}"))

    # Remove duplicates and sort
    files = sorted(set(files))

    return files


def print_summary(results: List[PipelineResult], verbose: bool = False) -> None:
    """Print processing summary.

    Args:
        results: List of pipeline results
        verbose: Whether to print detailed information
    """
    total = len(results)
    successful = sum(1 for r in results if r.success)
    failed = total - successful

    total_chunks = sum(r.chunk_count for r in results if r.success)
    total_images = sum(r.image_count for r in results if r.success)

    print("\n" + "=" * 60)
    print("INGESTION SUMMARY")
    print("=" * 60)
    print(f"Total files processed: {total}")
    print(f"  [OK] Successful: {successful}")
    print(f"  [FAIL] Failed: {failed}")
    print(f"\nTotal chunks generated: {total_chunks}")
    print(f"Total images processed: {total_images}")

    if verbose and failed > 0:
        print("\nFailed files:")
        for r in results:
            if not r.success:
                print(f"  [FAIL] {r.file_path}: {r.error}")

    if verbose and successful > 0:
        print("\nSuccessful files:")
        for r in results:
            if r.success:
                skipped = r.stages.get("integrity", {}).get("skipped", False)
                status = "[SKIP] skipped" if skipped else f"[OK] {r.chunk_count} chunks"
                print(f"  {status}: {r.file_path}")

    print("=" * 60)


def main() -> int:
    """Main entry point for the ingestion script.

    Returns:
        Exit code (0=success, 1=partial failure, 2=complete failure)
    """
    args = parse_args()

    # Keep the console readable: silence INFO run logs unless --verbose.
    if args.verbose:
        logging.getLogger().setLevel(logging.INFO)
    else:
        logging.getLogger().setLevel(logging.WARNING)
        logging.getLogger("jieba").setLevel(logging.ERROR)

    print("[*] Modular RAG Ingestion Script")
    print(_LINE)

    # Load configuration
    try:
        config_path = Path(args.config)
        if not config_path.exists():
            print(f"[FAIL] Configuration file not found: {config_path}")
            return 2

        settings = load_settings(str(config_path))
        print(f"[OK] Configuration loaded from: {config_path}")
    except Exception as e:
        print(f"[FAIL] Failed to load configuration: {e}")
        return 2

    # Discover files
    try:
        files = discover_files(args.path)
        print(f"[INFO] Found {len(files)} file(s) to process")

        if len(files) == 0:
            print("[WARN] No files found to process")
            return 0

        for f in files:
            print(f"   - {f}")
    except FileNotFoundError as e:
        print(f"[FAIL] {e}")
        return 2
    except ValueError as e:
        print(f"[FAIL] {e}")
        return 2

    # Dry run mode
    if args.dry_run:
        print("\n[INFO] Dry run mode - no files were processed")
        return 0

    # Initialize pipeline
    print(f"\n[INFO] Initializing pipeline...")
    print(f"   Collection: {args.collection}")
    print(f"   Force: {args.force}")

    try:
        pipeline = IngestionPipeline(
            settings=settings,
            collection=args.collection,
            force=args.force
        )
    except Exception as e:
        print(f"[FAIL] Failed to initialize pipeline: {e}")
        logger.exception("Pipeline initialization failed")
        return 2

    # Process files
    print(f"\n[INFO] Processing files...")
    results: List[PipelineResult] = []
    run_start = time.monotonic()

    collector = TraceCollector()

    for i, file_path in enumerate(files, 1):
        try:
            trace = TraceContext(trace_type="ingestion")
            trace.metadata["source_path"] = str(file_path)
            result = pipeline.run(str(file_path), trace=trace)
            trace.finish()
            collector.collect(trace)
            results.append(result)

            title = f"[{i}/{len(files)}] 摄取报告 · {file_path.name}"
            print()
            print(build_file_report(result, trace, settings, args.collection, title=title))

        except Exception as e:
            logger.exception(f"Unexpected error processing {file_path}")
            results.append(PipelineResult(
                success=False,
                file_path=str(file_path),
                error=str(e)
            ))
            print(f"\n [{i}/{len(files)}] 摄取失败 · {file_path.name}")
            print(f" [FAIL] Error: {e}")

    # Print summary
    print_summary(results, args.verbose)
    print(f"\n[SUMMARY] 批次总耗时 {(time.monotonic() - run_start):.1f} s")

    # Determine exit code
    successful = sum(1 for r in results if r.success)
    if successful == len(results):
        return 0  # All successful
    elif successful > 0:
        return 1  # Partial failure
    else:
        return 2  # Complete failure


if __name__ == "__main__":
    sys.exit(main())
