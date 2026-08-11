"""Tests for the Phase E MCP server entry point (main.py + console script)."""

from __future__ import annotations

from pathlib import Path

import pytest
import tomllib

import main as main_mod
from src.core.settings import SettingsError

PROJECT_ROOT = Path(__file__).parents[2]


def _pyproject_scripts() -> dict[str, str]:
    """Return the ``[project.scripts]`` table from pyproject.toml."""
    with (PROJECT_ROOT / "pyproject.toml").open("rb") as fh:
        data = tomllib.load(fh)
    return data["project"]["scripts"]


class TestConsoleScript:
    def test_mcp_server_points_to_real_server(self) -> None:
        """The installed ``mcp-server`` command must start the real server.

        ``main.py`` sits at the repo root, outside the ``src/`` package, so
        ``main:main`` is not importable after ``pip install``; the console
        script has to target the packaged module.
        """
        scripts = _pyproject_scripts()
        assert scripts["mcp-server"] == "src.mcp_server.server:main"


class TestMainDelegation:
    def test_main_delegates_to_real_server(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``python main.py`` forwards to src.mcp_server.server.main()."""
        import src.mcp_server.server as server_mod

        called: list[str] = []

        def fake_load_settings(settings_path) -> object:
            return object()

        def fake_server_main() -> int:
            called.append("server")
            return 42

        monkeypatch.setattr(main_mod, "load_settings", fake_load_settings)
        monkeypatch.setattr(server_mod, "main", fake_server_main)

        assert main_mod.main() == 42
        assert called == ["server"]

    def test_main_fails_fast_on_config_error(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Missing/invalid config exits 1 with the error on stderr only."""

        def raise_settings_error(settings_path) -> object:
            raise SettingsError("bad config")

        monkeypatch.setattr(main_mod, "load_settings", raise_settings_error)

        assert main_mod.main() == 1
        captured = capsys.readouterr()
        assert "Configuration error" in captured.err
        assert captured.out == ""  # 错误只走 stderr，绝不污染 stdout

    def test_main_no_stdout_pollution_on_success(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """On the success path stdout stays empty (JSON-RPC channel)."""
        import src.mcp_server.server as server_mod

        def fake_load_settings(settings_path) -> object:
            return object()

        def fake_server_main() -> int:
            return 0

        monkeypatch.setattr(main_mod, "load_settings", fake_load_settings)
        monkeypatch.setattr(server_mod, "main", fake_server_main)

        assert main_mod.main() == 0
        captured = capsys.readouterr()
        assert captured.out == ""


class TestServerModule:
    def test_real_server_exposes_main(self) -> None:
        """The packaged entry module provides the documented callables."""
        import src.mcp_server.server as server_mod

        assert callable(server_mod.main)
        assert callable(server_mod.run_stdio_server)
