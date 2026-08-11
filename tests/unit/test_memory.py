"""Tests for the Phase 6 conversation memory (None / SQLite / factory)."""

from __future__ import annotations

from pathlib import Path

from src.core.agent.memory import (
    MemoryFactory,
    NoneMemory,
    SQLiteMemory,
)
from src.core.settings import MemorySettings


class TestNoneMemory:
    def test_noop_recent(self) -> None:
        memory = NoneMemory()
        memory.add("s1", "user", "hi")
        assert memory.recent("s1") == []
        memory.clear("s1")  # should not raise


class TestSQLiteMemory:
    def _memory(self, tmp_path: Path) -> SQLiteMemory:
        return SQLiteMemory(str(tmp_path / "agent_memory.db"))

    def test_add_and_recent_chronological(self, tmp_path: Path) -> None:
        memory = self._memory(tmp_path)
        memory.add("s1", "user", "q1")
        memory.add("s1", "assistant", "a1")
        memory.add("s1", "user", "q2")
        recent = memory.recent("s1")
        assert [m["role"] for m in recent] == ["user", "assistant", "user"]
        assert recent[0]["content"] == "q1"
        assert recent[-1]["content"] == "q2"

    def test_window_size_limits(self, tmp_path: Path) -> None:
        memory = self._memory(tmp_path)
        for i in range(10):
            memory.add("s1", "user", f"msg-{i}")
        recent = memory.recent("s1", window_size=3)
        assert len(recent) == 3
        assert recent[-1]["content"] == "msg-9"

    def test_session_isolation(self, tmp_path: Path) -> None:
        memory = self._memory(tmp_path)
        memory.add("s1", "user", "a")
        memory.add("s2", "user", "b")
        assert [m["content"] for m in memory.recent("s1")] == ["a"]
        assert [m["content"] for m in memory.recent("s2")] == ["b"]

    def test_clear(self, tmp_path: Path) -> None:
        memory = self._memory(tmp_path)
        memory.add("s1", "user", "a")
        memory.clear("s1")
        assert memory.recent("s1") == []

    def test_persists_across_instances(self, tmp_path: Path) -> None:
        db = str(tmp_path / "agent_memory.db")
        first = SQLiteMemory(db)
        first.add("s1", "user", "a")
        del first  # close nothing held — each call opens/closes its own conn
        second = SQLiteMemory(db)
        assert [m["content"] for m in second.recent("s1")] == ["a"]


class TestMemoryFactory:
    def test_disabled_returns_none_memory(self) -> None:
        assert isinstance(
            MemoryFactory.create(MemorySettings(enabled=False)), NoneMemory
        )

    def test_none_settings_returns_none_memory(self) -> None:
        assert isinstance(MemoryFactory.create(None), NoneMemory)

    def test_sqlite_backend(self, tmp_path: Path) -> None:
        memory = MemoryFactory.create(
            MemorySettings(enabled=True, backend="sqlite"),
            db_path=str(tmp_path / "m.db"),
        )
        assert isinstance(memory, SQLiteMemory)

    def test_none_backend_returns_none_memory(self) -> None:
        assert isinstance(
            MemoryFactory.create(MemorySettings(enabled=True, backend="none")),
            NoneMemory,
        )
