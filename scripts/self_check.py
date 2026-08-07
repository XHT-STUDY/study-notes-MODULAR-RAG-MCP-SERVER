#!/usr/bin/env python
"""Environment self-check for the Modular RAG MCP Server.

Validates that the runtime environment is ready to run the full system:
Python version, config loading, key packages, data-directory writability,
Chroma connectivity, SQLite schema, BM25 index writability, trace logging,
and (non-blocking) API-key readiness.

Usage:
    python scripts/self_check.py                 # human-readable, exit 0/1
    python scripts/self_check.py --json          # JSON output (CI-friendly)
    python scripts/self_check.py --config path   # check a specific config

Exit codes:
    0 - all blocking checks passed (WARN / HINT allowed)
    1 - at least one blocking check failed
"""

from __future__ import annotations

import argparse
import importlib
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

# Ensure project root is on sys.path
_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent
sys.path.insert(0, str(_REPO_ROOT))

# Set UTF-8 encoding for Windows console
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from src.core.settings import Settings, load_settings, resolve_path  # noqa: E402  (sys.path above)

# Packages that must be importable for the system to run.
REQUIRED_PACKAGES: list[str] = ["mcp", "chromadb", "streamlit", "yaml", "markitdown", "jieba"]

# Blocking statuses; WARN / HINT never fail the check.
_BLOCKING = {"OK", "FAIL"}
_STATUS_ORDER = ["OK", "WARN", "HINT", "FAIL"]


class CheckResult:
    """One self-check line."""

    def __init__(self, name: str, status: str, detail: str, blocking: bool) -> None:
        self.name = name
        self.status = status
        self.detail = detail
        self.blocking = blocking

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "detail": self.detail,
            "blocking": self.blocking,
        }


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------


def check_python_version() -> tuple[str, str]:
    """Check Python >= 3.12."""
    ok = sys.version_info >= (3, 12)
    detail = f"{sys.version.split()[0]} (py{'.'.join(map(str, sys.version_info[:3]))})"
    return ("OK" if ok else "FAIL"), detail


def check_config(config_path: str | None) -> tuple[str, str]:
    """Try to load settings, falling back to the example template."""
    candidates: list[Path] = []
    if config_path:
        candidates.append(Path(config_path))
    candidates.append(_REPO_ROOT / "config" / "settings.yaml")
    candidates.append(_REPO_ROOT / "config" / "settings.yaml.example")

    last_error: str | None = None
    loaded: Settings | None = None
    used: Path | None = None
    for cand in candidates:
        if not cand.exists():
            continue
        try:
            loaded = load_settings(str(cand))
            used = cand
            break
        except Exception as exc:  # SettingsError, yaml.YAMLError, ...
            last_error = f"{cand.name}: {exc}"

    if loaded is None:
        return "FAIL", f"no config loadable — {last_error or 'no candidates'}"
    assert used is not None  # loaded implies a candidate was used
    label = used.name
    if used == _REPO_ROOT / "config" / "settings.yaml.example":
        label += " (example template)"
    return "OK", label


def check_packages() -> tuple[str, str]:
    """Check all required third-party packages import cleanly."""
    missing: list[str] = []
    for pkg in REQUIRED_PACKAGES:
        try:
            importlib.import_module(pkg)
        except Exception:
            missing.append(pkg)
    if missing:
        return "FAIL", f"missing: {', '.join(missing)}"
    return "OK", ", ".join(REQUIRED_PACKAGES)


def check_data_dirs() -> tuple[str, str]:
    """Check data directories are creatable and writable."""
    dirs = [
        _REPO_ROOT / "data",
        _REPO_ROOT / "data" / "db",
        _REPO_ROOT / "data" / "db" / "chroma",
        _REPO_ROOT / "data" / "db" / "bm25",
        _REPO_ROOT / "data" / "images",
    ]
    try:
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)
            probe = d / ".self_check_probe"
            probe.write_text("probe", encoding="utf-8")
            probe.unlink()
        return "OK", f"writable: {', '.join(str(p.relative_to(_REPO_ROOT)) for p in dirs)}"
    except Exception as exc:
        return "FAIL", str(exc)


def check_chroma(settings: Settings) -> tuple[str, str]:
    """Check ChromaDB can connect and create a collection."""
    try:
        import chromadb
        from chromadb.config import Settings as ChromaSettings

        persist_dir = resolve_path(settings.vector_store.persist_directory)
        persist_dir.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(
            path=str(persist_dir),
            settings=ChromaSettings(anonymized_telemetry=False, allow_reset=True),
        )
        coll = client.get_or_create_collection("self_check_probe")
        coll_name = coll.name
        try:
            client.delete_collection("self_check_probe")
        except Exception:
            pass
        return "OK", f"PersistentClient@{persist_dir} collection={coll_name}"
    except Exception as exc:
        return "FAIL", str(exc)


def check_sqlite() -> tuple[str, str]:
    """Check the ingestion-history SQLite DB opens and schema can be created."""
    try:
        db_path = resolve_path("data/db/ingestion_history.db")
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path))
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                "CREATE TABLE IF NOT EXISTS ingestion_history ("
                " file_hash TEXT PRIMARY KEY,"
                " file_path TEXT NOT NULL,"
                " status TEXT NOT NULL,"
                " collection TEXT,"
                " error_msg TEXT,"
                " processed_at TEXT NOT NULL,"
                " updated_at TEXT NOT NULL)"
            )
            conn.commit()
        finally:
            conn.close()
        return "OK", f"sqlite@{db_path}"
    except Exception as exc:
        return "FAIL", str(exc)


def check_bm25() -> tuple[str, str]:
    """Check the BM25 index directory is writable (JSON round-trip)."""
    try:
        bm25_dir = resolve_path("data/db/bm25")
        bm25_dir.mkdir(parents=True, exist_ok=True)
        probe = bm25_dir / ".self_check_probe.json"
        with probe.open("w", encoding="utf-8") as handle:
            json.dump({"ok": True}, handle)
        with probe.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        probe.unlink()
        if not data.get("ok"):
            raise RuntimeError("round-trip mismatch")
        return "OK", f"bm25@{bm25_dir}"
    except Exception as exc:
        return "FAIL", str(exc)


def check_traces() -> tuple[str, str]:
    """Check trace log file is appendable (WARNING only — non-blocking)."""
    try:
        traces_file = resolve_path("logs/traces.jsonl")
        traces_file.parent.mkdir(parents=True, exist_ok=True)
        with traces_file.open("a", encoding="utf-8") as handle:
            handle.write('{"self_check": true}\n')
        return "OK", f"appendable@{traces_file}"
    except Exception as exc:
        return "WARN", f"cannot write traces: {exc}"


def check_api_keys(settings: Settings) -> tuple[str, str]:
    """Report API-key readiness as a HINT (never blocking)."""
    missing: list[str] = []
    if not settings.llm.api_key:
        missing.append("LLM_API_KEY")
    if not settings.embedding.api_key:
        missing.append("EMBEDDING_API_KEY")
    if missing:
        return "HINT", "set " + ", ".join(missing) + " to enable LLM/embedding features"
    return "OK", "keys present via env or settings.yaml"


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def run_self_check(config_path: str | None = None) -> list[CheckResult]:
    """Run all checks and return the ordered result list."""
    # Config is needed by several later checks.
    config_status, config_detail = check_config(config_path)
    settings: Settings | None = None
    if config_status == "OK":
        try:
            settings = load_settings(config_path or str(_REPO_ROOT / "config" / "settings.yaml"))
        except Exception:
            try:
                settings = load_settings(str(_REPO_ROOT / "config" / "settings.yaml.example"))
            except Exception:
                settings = None

    checks: list[CheckResult] = [
        CheckResult("Python version", *check_python_version(), blocking=True),
        CheckResult("Config loadable", config_status, config_detail, blocking=True),
        CheckResult("Key packages", *check_packages(), blocking=True),
        CheckResult("Data dirs writable", *check_data_dirs(), blocking=True),
    ]

    if settings is not None:
        checks.append(CheckResult("Chroma connectable", *check_chroma(settings), blocking=True))
        checks.append(CheckResult("SQLite creatable", *check_sqlite(), blocking=True))
        checks.append(CheckResult("BM25 index writable", *check_bm25(), blocking=True))
        checks.append(CheckResult("Trace log writable", *check_traces(), blocking=False))
        checks.append(CheckResult("API keys ready", *check_api_keys(settings), blocking=False))
    else:
        # Without settings, storage checks can't run — report as FAIL.
        checks.append(CheckResult("Chroma connectable", "FAIL", "no config loaded", blocking=True))
        checks.append(CheckResult("SQLite creatable", "FAIL", "no config loaded", blocking=True))
        checks.append(CheckResult("BM25 index writable", "FAIL", "no config loaded", blocking=True))
        checks.append(CheckResult("Trace log writable", "WARN", "no config loaded", blocking=False))
        checks.append(CheckResult("API keys ready", "HINT", "no config loaded", blocking=False))

    return checks


def format_report(checks: list[CheckResult]) -> str:
    """Render the human-readable report."""
    lines = ["", "Environment Self-Check", "=" * 60]
    for i, check in enumerate(checks, 1):
        lines.append(f"[{i}/{len(checks)}] {check.name:<22} [{check.status:>4}] {check.detail}")
    lines.append("=" * 60)
    counts = {status: sum(1 for c in checks if c.status == status) for status in _STATUS_ORDER}
    lines.append(
        f"Summary: {counts['OK']} OK, {counts['WARN']} WARN, "
        f"{counts['HINT']} HINT, {counts['FAIL']} FAIL"
    )
    failed = [c for c in checks if c.status == "FAIL" and c.blocking]
    lines.append("Result: " + ("PASS" if not failed else f"FAIL — {len(failed)} blocking check(s)"))
    return "\n".join(lines)


def main() -> int:
    """CLI entry point. Returns 0 when no blocking check failed."""
    parser = argparse.ArgumentParser(
        description="Run the Modular RAG environment self-check.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of human-readable report")
    parser.add_argument(
        "--config",
        default=None,
        help="Path to settings YAML (default: config/settings.yaml, then example)",
    )
    args = parser.parse_args()

    checks = run_self_check(args.config)
    failed = [c for c in checks if c.status == "FAIL" and c.blocking]

    if args.json:
        payload = {
            "passed": not failed,
            "exit_code": 0 if not failed else 1,
            "python_version": sys.version.split()[0],
            "checks": [c.to_dict() for c in checks],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(format_report(checks))

    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
