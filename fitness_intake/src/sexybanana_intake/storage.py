"""Isolated in-memory and durable SQLite stores with optimistic concurrency."""

from __future__ import annotations

import os
import sqlite3
import threading
from pathlib import Path
from typing import Protocol

from .errors import IntakeError
from .models import Session


class SessionStore(Protocol):
    """Persistence boundary. Hosts enforce identity and access authorization before calls."""

    def create(self, session: Session) -> None: ...
    def load(self, session_id: str) -> Session: ...
    def save(self, session: Session, expected_version: int) -> None: ...
    def delete(self, session_id: str) -> None: ...


class MemoryStore:
    """Copy-on-read in-memory storage for tests and short-lived applications."""

    def __init__(self):
        self._data: dict[str, str] = {}
        self._lock = threading.RLock()

    def create(self, session: Session) -> None:
        """Insert a new session; do not overwrite an existing identifier."""
        with self._lock:
            if session.session_id in self._data:
                raise IntakeError("session_exists", "This session already exists.")
            self._data[session.session_id] = session.model_dump_json()

    def load(self, session_id: str) -> Session:
        """Return an isolated snapshot or a redacted not-found error."""
        with self._lock:
            if session_id not in self._data:
                raise IntakeError("not_found", "Session not found.")
            return Session.model_validate_json(self._data[session_id])

    def save(self, session: Session, expected_version: int) -> None:
        """Commit only when the stored version still matches the caller's snapshot."""
        with self._lock:
            if self.load(session.session_id).version != expected_version:
                raise IntakeError("version_conflict", "Session changed; reload before retrying.")
            self._data[session.session_id] = session.model_dump_json()

    def delete(self, session_id: str) -> None:
        """Remove the session, including history, plans, and cached data."""
        with self._lock:
            self._data.pop(session_id, None)


class SQLiteStore:
    """Local durable storage with parameterized queries and no external health files."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.path.is_symlink():
            raise IntakeError("invalid_storage", "The database path must not be a symbolic link.")
        fd = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
        os.close(fd)
        os.chmod(self.path, 0o600)
        connection = self._connect()
        try:
            with connection:
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, version INTEGER NOT NULL, body TEXT NOT NULL)"
                )
        finally:
            connection.close()

    def _connect(self) -> sqlite3.Connection:
        """Open a short-lived connection with secure deletion and rollback journaling."""
        connection = sqlite3.connect(self.path, timeout=10)
        connection.execute("PRAGMA secure_delete=ON")
        connection.execute("PRAGMA journal_mode=DELETE")
        return connection

    def create(self, session: Session) -> None:
        """Insert a session atomically without replacing existing data."""
        connection = self._connect()
        try:
            with connection:
                connection.execute(
                    "INSERT INTO sessions VALUES (?, ?, ?)",
                    (session.session_id, session.version, session.model_dump_json()),
                )
        except sqlite3.IntegrityError:
            raise IntakeError("session_exists", "This session already exists.") from None
        finally:
            connection.close()

    def load(self, session_id: str) -> Session:
        """Read an isolated snapshot from disk."""
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT body FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
            if row is None:
                raise IntakeError("not_found", "Session not found.")
            return Session.model_validate_json(row[0])
        finally:
            connection.close()

    def save(self, session: Session, expected_version: int) -> None:
        """Atomically compare and replace a session version."""
        connection = self._connect()
        try:
            with connection:
                cursor = connection.execute(
                    "UPDATE sessions SET version = ?, body = ? WHERE id = ? AND version = ?",
                    (
                        session.version,
                        session.model_dump_json(),
                        session.session_id,
                        expected_version,
                    ),
                )
                if cursor.rowcount != 1:
                    raise IntakeError(
                        "version_conflict",
                        "Session changed or was deleted; reload before retrying.",
                    )
        finally:
            connection.close()

    def delete(self, session_id: str) -> None:
        """Delete all session-owned content and compact the database; external backups are host-owned."""
        connection = self._connect()
        try:
            with connection:
                connection.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            connection.execute("VACUUM")
        finally:
            connection.close()
