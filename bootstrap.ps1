#!/usr/bin/env pwsh
# One-command bootstrap for the Modular RAG MCP Server.
# Thin wrapper -> python scripts/bootstrap.py
# Usage: .\bootstrap.ps1 [-seed] [-full] [-venv <path>] [-verbose]
$ErrorActionPreference = "Stop"
python "$PSScriptRoot\scripts\bootstrap.py" @args
exit $LASTEXITCODE
