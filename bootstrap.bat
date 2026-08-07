@echo off
REM One-command bootstrap for the Modular RAG MCP Server.
REM Thin wrapper -> python scripts/bootstrap.py
REM Usage: .\bootstrap.bat [--seed|--full] [--venv <path>] [--verbose]
setlocal
python "%~dp0scripts\bootstrap.py" %*
exit /b %errorlevel%
