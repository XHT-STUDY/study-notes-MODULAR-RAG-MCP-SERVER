"""
Modular RAG MCP Server - Main Entry Point (thin launcher).

``python main.py`` starts the real stdio MCP server implemented in
``src.mcp_server.server``.  This module only adds a fail-fast
configuration check before delegating; all logging goes to stderr so
stdout stays reserved for the JSON-RPC protocol.
"""

from __future__ import annotations

import sys
from pathlib import Path

from src.core.settings import SettingsError, load_settings


def main() -> int:
    """
    Validate configuration, then start the stdio MCP server.

    Returns:
        int: Exit code (0 for success, non-zero for failure)
    """
    # Fail fast on a missing/invalid config — better than a server that
    # starts but cannot serve tool calls. Errors go to stderr only.
    try:
        load_settings(Path("config/settings.yaml"))
    except SettingsError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1

    # Lazy import so that config failures never pull in heavy MCP deps.
    from src.mcp_server.server import main as run_mcp_server

    return run_mcp_server()


if __name__ == "__main__":
    sys.exit(main())
