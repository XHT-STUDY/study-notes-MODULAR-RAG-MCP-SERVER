"""Conversation memory for the Agentic RAG layer (Phase 6).

Three implementations: :class:`NoneMemory` (no-op, default), :class:`SQLiteMemory`
(windowed recent turns persisted in WAL mode, mirroring ``SQLiteIntegrityChecker``),
and a :class:`MemoryFactory` that selects between them from ``agent.memory``.
"""

from __future__ import annotations

import sqlite3
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path

from src.core.settings import REPO_ROOT, MemorySettings

#: Default persistence location for SQLite conversation memory.
DEFAULT_MEMORY_DB: str = str(REPO_ROOT / "data" / "db" / "agent_memory.db")


class ConversationMemory(ABC):
    """Abstract session-scoped conversation memory."""

    @abstractmethod
    def add(self, session_id: str, role: str, content: str) -> None:
        """Record one message for a session."""

    @abstractmethod
    def recent(self, session_id: str, window_size: int = 10) -> list[dict[str, str]]:
        """Return the most recent ``window_size`` messages for a session.

        Each dict has keys ``role`` and ``content``.
        """

    @abstractmethod
    def clear(self, session_id: str) -> None:
        """Drop all recorded messages for a session."""


class NoneMemory(ConversationMemory):
    """No-op memory used when ``agent.memory.enabled=false`` (or backend ``none``)."""

    def add(self, session_id: str, role: str, content: str) -> None:
        pass

    def recent(self, session_id: str, window_size: int = 10) -> list[dict[str, str]]:
        return []

    def clear(self, session_id: str) -> None:
        pass


class SQLiteMemory(ConversationMemory):
    """Windowed conversation memory backed by SQLite (WAL mode).

    Each call opens and closes its own connection, mirroring
    ``SQLiteIntegrityChecker`` for safe multi-thread use.
    """

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._ensure_database()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_database(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = self._connect()
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS conversation_memory (
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_conversation_session "
                "ON conversation_memory(session_id, created_at)"
            )
            conn.commit()
        finally:
            conn.close()

    def add(self, session_id: str, role: str, content: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO conversation_memory (session_id, role, content, created_at) "
                "VALUES (?, ?, ?, ?)",
                (session_id, role, content, now),
            )
            conn.commit()
        finally:
            conn.close()

    def recent(self, session_id: str, window_size: int = 10) -> list[dict[str, str]]:
        conn = self._connect()
        try:
            cursor = conn.execute(
                "SELECT role, content FROM conversation_memory "
                "WHERE session_id = ? ORDER BY created_at DESC LIMIT ?",
                (session_id, max(window_size, 1)),
            )
            rows = [dict(row) for row in cursor.fetchall()]
            rows.reverse()  # back to chronological order
            return rows
        finally:
            conn.close()

    def clear(self, session_id: str) -> None:
        conn = self._connect()
        try:
            conn.execute(
                "DELETE FROM conversation_memory WHERE session_id = ?",
                (session_id,),
            )
            conn.commit()
        finally:
            conn.close()


class MemoryFactory:
    """Builds a memory backend from ``agent.memory`` settings."""

    @staticmethod
    def create(
        settings: MemorySettings | None,
        db_path: str = DEFAULT_MEMORY_DB,
    ) -> ConversationMemory:
        if settings is None or not settings.enabled:
            return NoneMemory()
        backend = (settings.backend or "none").lower()
        if backend == "sqlite":
            return SQLiteMemory(db_path)
        return NoneMemory()
