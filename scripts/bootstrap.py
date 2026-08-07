#!/usr/bin/env python
"""One-command bootstrap for the Modular RAG MCP Server.

Brings a fresh clone to a runnable state with a single command:

    uv check → create Python 3.12 venv → ``uv sync --locked`` (strict lock)
    → generate ``config/settings.yaml`` from the example if missing
    → environment self-check → (optional) seed sample docs → (optional) smoke query

This module is intentionally **stdlib-only**: it runs under whatever Python is
invoked (system / existing venv) and manages the project venv itself.

venv path policy (does not disturb an existing environment):
    - ``.venv`` does not exist        → create ``.venv`` (Python 3.12)
    - ``.venv`` exists and is 3.12    → reuse it
    - ``.venv`` exists but not 3.12   → create ``.venv-3.12``, leave ``.venv`` alone

Usage:
    python scripts/bootstrap.py                # env only (venv + sync + self-check)
    python scripts/bootstrap.py --seed         # + ingest sample docs
    python scripts/bootstrap.py --full         # + ingest + smoke query (needs API keys)
    python scripts/bootstrap.py --venv .venv   # explicit venv path
    python scripts/bootstrap.py --verbose

Exit codes:
    0 - all requested steps succeeded and self-check passed
    1 - at least one step failed
    2 - uv is missing (or invalid arguments)
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TARGET_PYTHON = "3.12"

# Set UTF-8 encoding for Windows console
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def _log(step: str, message: str) -> None:
    print(f"  [{step}] {message}")


def _venv_bin_dir(venv: Path) -> Path:
    return venv / ("Scripts" if os.name == "nt" else "bin")


def venv_python(venv: Path) -> Path:
    """Return the venv's Python executable path."""
    return _venv_bin_dir(venv) / ("python.exe" if os.name == "nt" else "python")


def venv_version(venv: Path) -> str | None:
    """Read the Python version from ``pyvenv.cfg`` (e.g. ``3.12.13``).

    CPython venvs write ``version = 3.12.4``; uv-created venvs write
    ``version_info = 3.12.4`` instead, so both keys are checked.
    """
    cfg = venv / "pyvenv.cfg"
    if not cfg.exists():
        return None
    try:
        for line in cfg.read_text(encoding="utf-8").splitlines():
            if "=" in line:
                key, _, value = line.partition("=")
                if key.strip() in ("version", "version_info"):
                    return value.strip().split()[0]
    except OSError:
        return None
    return None


def resolve_venv_target(requested: str | None, repo_root: Path) -> Path:
    """Decide the venv path per the policy in the module docstring."""
    if requested:
        return Path(requested).resolve()
    default = repo_root / ".venv"
    if default.exists():
        version = venv_version(default)
        if version is None or not version.startswith("3.12"):
            return repo_root / ".venv-3.12"
    return default


def run(cmd: list[str], cwd: Path, env: dict | None = None, verbose: bool = False) -> int:
    """Run a subprocess, forwarding output, and return its exit code."""
    if verbose:
        print(f"  [cmd] {' '.join(cmd)}")
    proc = subprocess.run(cmd, cwd=str(cwd), env=env, text=True)
    return proc.returncode


def check_uv() -> str | None:
    """Return the path to ``uv`` or None with install guidance printed."""
    uv = shutil.which("uv")
    if uv:
        return uv
    print("\n[FAIL] `uv` not found on PATH.")
    print("       Install it (https://docs.astral.sh/uv/):")
    print("         Windows (PowerShell):  powershell -ExecutionPolicy ByPass -c \"irm https://astral.sh/uv/install.ps1 | iex\"")
    print("         macOS / Linux:         curl -LsSf https://astral.sh/uv/install.sh | sh")
    print("       Then re-run this bootstrap.")
    return None


def ensure_venv(uv: str, target: Path, verbose: bool) -> bool:
    """Create (or reuse) the 3.12 venv. Returns True on success."""
    version = venv_version(target)
    if target.exists() and version and version.startswith("3.12"):
        _log("venv", f"reuse existing {TARGET_PYTHON} venv at {target} (version {version})")
        return True

    if target.exists():
        _log("venv", f"existing venv at {target} is {version or 'unreadable'} — recreating as {TARGET_PYTHON}")
        cmd = [uv, "venv", str(target), "--python", TARGET_PYTHON, "--clear"]
    else:
        _log("venv", f"creating {TARGET_PYTHON} venv at {target}")
        cmd = [uv, "venv", str(target), "--python", TARGET_PYTHON]

    return run(cmd, cwd=REPO_ROOT, verbose=verbose) == 0


def sync_locked(uv: str, target: Path, verbose: bool) -> bool:
    """Strictly sync dependencies into *target* from ``uv.lock``.

    ``--extra dev`` pulls in the ``[project.optional-dependencies] dev`` extras
    (pytest / ruff / mypy / openai) so the bootstrapped env can run the test
    suite, not just the runtime.
    """
    _log("sync", f"uv sync --locked (incl. dev extras) into {target}")
    env = dict(os.environ)
    env["VIRTUAL_ENV"] = str(target)
    bin_dir = _venv_bin_dir(target)
    env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
    return run([uv, "sync", "--active", "--locked", "--extra", "dev"], cwd=REPO_ROOT, env=env, verbose=verbose) == 0


def ensure_settings(verbose: bool) -> bool:
    """Generate ``config/settings.yaml`` from the example if missing."""
    settings_path = REPO_ROOT / "config" / "settings.yaml"
    example_path = REPO_ROOT / "config" / "settings.yaml.example"
    if settings_path.exists():
        _log("config", "config/settings.yaml already exists (not overwriting)")
        return True
    if not example_path.exists():
        _log("config", f"neither settings.yaml nor example found at {REPO_ROOT / 'config'}")
        return False
    shutil.copyfile(example_path, settings_path)
    _log("config", f"generated config/settings.yaml from {example_path.name} (fill in API keys via env)")
    return True


def run_step(py: Path, script: str, args: list[str], verbose: bool) -> int:
    """Run one project script under the venv Python."""
    cmd = [str(py), str(REPO_ROOT / "scripts" / script)] + args
    if verbose:
        print(f"  [cmd] {' '.join(cmd)}")
    proc = subprocess.run(cmd, cwd=str(REPO_ROOT), text=True)
    return proc.returncode


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="One-command bootstrap for the Modular RAG MCP Server.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--seed", action="store_true", help="After self-check, ingest sample documents")
    parser.add_argument(
        "--full",
        action="store_true",
        help="= --seed + a smoke query (retrieval chain; requires embedding keys)",
    )
    parser.add_argument("--venv", default=None, help="Explicit venv path (default: .venv or .venv-3.12)")
    parser.add_argument("--config", default=None, help="Path to settings YAML passed to project scripts")
    parser.add_argument("--sample-dir", default=None, help="Sample-doc directory for --seed/--full")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print subprocess commands")
    return parser.parse_args()


def main() -> int:
    """Entry point. Returns 0 when all requested steps succeeded."""
    args = parse_args()

    print("=" * 60)
    print("Modular RAG MCP Server — Bootstrap")
    print("=" * 60)

    # 1. uv present?
    uv = check_uv()
    if uv is None:
        return 2

    # 2. Decide venv path.
    target = resolve_venv_target(args.venv, REPO_ROOT)
    _log("venv", f"target venv: {target}")

    # 3. Create/reuse the 3.12 venv.
    if not ensure_venv(uv, target, args.verbose):
        print("\n[FAIL] Could not create the 3.12 virtual environment.")
        return 1

    # 4. Strict sync from uv.lock.
    if not sync_locked(uv, target, args.verbose):
        print("\n[FAIL] `uv sync --locked` failed. Check the output above.")
        print("        Hint: delete the venv and retry, or run `uv lock` to regenerate uv.lock.")
        return 1

    py = venv_python(target)
    if not py.exists():
        print(f"[FAIL] venv Python not found at {py}")
        return 1

    # 5. Ensure a settings file exists.
    if not ensure_settings(args.verbose):
        print("\n[FAIL] No settings template available to generate config/settings.yaml.")
        return 1

    # 6. Self-check.
    print("\n--- Environment self-check ---")
    self_check_args = ["--config", args.config] if args.config else []
    self_check_exit = run_step(py, "self_check.py", self_check_args, args.verbose)
    if self_check_exit != 0:
        print("\n[FAIL] Self-check reported blocking failures. Fix them before seeding.")
        return 1

    # 7. Optional seed.
    if args.seed or args.full:
        print("\n--- Seeding sample documents ---")
        seed_args: list[str] = []
        if args.config:
            seed_args += ["--config", args.config]
        if args.sample_dir:
            seed_args += ["--sample-dir", args.sample_dir]
        seed_exit = run_step(py, "seed_docs.py", seed_args, args.verbose)
        if seed_exit != 0:
            print("\n[FAIL] Seeding failed (usually missing embedding API keys).")
            return 1

    # 8. Optional smoke query.
    if args.full:
        print("\n--- Smoke query (hybrid retrieval) ---")
        query_args = ["--query", "什么是混合检索", "--top-k", "5"]
        if args.config:
            query_args += ["--config", args.config]
        query_exit = run_step(py, "query.py", query_args, args.verbose)
        if query_exit != 0:
            print("\n[FAIL] Smoke query failed.")
            return 1

    print("\n" + "=" * 60)
    print("BOOTSTRAP COMPLETE")
    print(f"  venv:            {target}")
    print(f"  python:          {py}")
    print("  next steps:")
    print("    - dashboard:   python scripts/start_dashboard.py --port 8501")
    print("    - ingest:      python scripts/ingest.py --path <pdf> --collection <name>")
    print("    - query:       python scripts/query.py -q \"问题\"")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
