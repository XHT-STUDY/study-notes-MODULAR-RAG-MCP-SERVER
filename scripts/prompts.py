#!/usr/bin/env python
"""Prompt-template checksum maintenance and verification.

Prompt templates live in ``prompts/*.md`` with YAML frontmatter carrying a
``checksum`` field.  This script is the single maintenance entry point:

    python scripts/prompts.py --verify
        Strictly verify every template's checksum (exit 0 = all good,
        exit 1 = at least one mismatch / missing canonical file).

    python scripts/prompts.py --update-checksums
        Rewrite each frontmattered ``*.md`` so its ``checksum`` matches its
        body.  Run this after editing a prompt body, then commit — the git
        diff shows the real body change plus the one-line checksum update.

Exit codes:
    0 - OK (or, for --update-checksums, ran successfully)
    1 - --verify found errors
    2 - invalid CLI usage
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure project root is on sys.path
_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent
sys.path.insert(0, str(_REPO_ROOT))


def _configure_windows_utf8() -> None:
    """Set UTF-8 encoding for Windows console (only when run as a CLI).

    Guarded behind ``__name__ == "__main__"`` so importing ``main`` for tests
    leaves ``sys.stdout``/``sys.stderr`` untouched (capsys capture intact).
    """
    if sys.platform == "win32":
        import io

        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from src.core.prompts import PROMPTS_DIR, PromptRegistry  # noqa: E402  (sys.path above)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="prompts.py",
        description="Prompt-template checksum verify / update.",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="strictly verify every template checksum (exit 1 on error)",
    )
    parser.add_argument(
        "--update-checksums",
        action="store_true",
        help="rewrite each frontmattered template's checksum to match its body",
    )
    return parser


def main(argv: list[str] | None = None, registry: PromptRegistry | None = None) -> int:
    """Run the CLI.  *registry* is injectable for tests."""
    args = _build_parser().parse_args(argv)
    if args.verify and args.update_checksums:
        print("error: --verify and --update-checksums are mutually exclusive", file=sys.stderr)
        return 2
    if not args.verify and not args.update_checksums:
        _build_parser().print_help(sys.stderr)
        return 2

    reg = registry or PromptRegistry()

    if args.verify:
        errors = reg.verify_all()
        if errors:
            for error in errors:
                print(f"[FAIL] {error}", file=sys.stderr)
            print(f"FAIL: {len(errors)} problem(s) in {PROMPTS_DIR}", file=sys.stderr)
            return 1
        print(f"OK: verified {len(list(PROMPTS_DIR.glob('*.md')))} prompt(s) in {PROMPTS_DIR}")
        return 0

    changed = reg.update_checksums()
    if changed:
        for path in changed:
            try:
                display = path.relative_to(_REPO_ROOT)
            except ValueError:
                display = path  # registry pointed at a non-repo dir (tests)
            print(f"updated {display}")
    print(f"OK: updated checksum(s) for {len(changed)} prompt(s)")
    return 0


if __name__ == "__main__":
    _configure_windows_utf8()
    raise SystemExit(main())
