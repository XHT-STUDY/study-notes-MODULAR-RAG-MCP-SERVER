#!/usr/bin/env bash
# One-command bootstrap for the Modular RAG MCP Server.
# Thin wrapper -> python scripts/bootstrap.py
# Usage: ./bootstrap.sh [--seed|--full] [--venv <path>] [--verbose]
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python "$SCRIPT_DIR/scripts/bootstrap.py" "$@"
