"""SQLite persistence for accounts, server sessions, ownership, and plans."""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .errors import AccountError, ERROR_MESSAGES
from .models import StoredUser


MIGRATIONS: tuple[tuple[int, str], ...] = (
    (
        1,
        """
        CREATE TABLE IF NOT EXISTS account_schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email_normalized TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            is_active INTEGER NOT NULL CHECK (is_active IN (0, 1))
        );
        CREATE TABLE IF NOT EXISTS auth_sessions (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            token_hash TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            revoked_at TEXT
        );
        CREATE TABLE IF NOT EXISTS fitness_session_owners (
            fitness_session_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at TEXT NOT NULL,
            UNIQUE (fitness_session_id, user_id)
        );
        CREATE TABLE IF NOT EXISTS workout_plans (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            fitness_session_id TEXT NOT NULL,
            fitness_plan_id TEXT NOT NULL UNIQUE,
            source_profile_version INTEGER NOT NULL CHECK (source_profile_version >= 0),
            status TEXT NOT NULL CHECK (status IN ('available', 'stale')),
            plan_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (fitness_session_id, user_id)
                REFERENCES fitness_session_owners(fitness_session_id, user_id)
                ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_auth_sessions_user ON auth_sessions(user_id);
        CREATE INDEX IF NOT EXISTS idx_plans_user_created ON workout_plans(user_id, created_at DESC);
        """,
    ),
)


class AccountDatabase:
    """Short-lived SQLite connections with migrations and foreign-key enforcement."""

    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.path.exists() and self.path.is_symlink():
            raise AccountError("database_failure", ERROR_MESSAGES["database_failure"], 500)
        fd = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
        os.close(fd)
        os.chmod(self.path, 0o600)
        self.migrate()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA secure_delete=ON")
        connection.execute("PRAGMA busy_timeout=10000")
        return connection

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    @contextmanager
    def read(self) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            yield connection
        finally:
            connection.close()

    def migrate(self) -> None:
        with self.transaction() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS account_schema_migrations "
                "(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
            )
            applied = {
                row[0]
                for row in connection.execute(
                    "SELECT version FROM account_schema_migrations"
                ).fetchall()
            }
            for version, script in MIGRATIONS:
                if version in applied:
                    continue
                for statement in script.split(";"):
                    if statement.strip():
                        connection.execute(statement)
                connection.execute(
                    "INSERT INTO account_schema_migrations(version, applied_at) "
                    "VALUES (?, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))",
                    (version,),
                )

    @staticmethod
    def _user(row: sqlite3.Row | None) -> StoredUser | None:
        if row is None:
            return None
        return StoredUser(
            id=row["id"],
            email_normalized=row["email_normalized"],
            password_hash=row["password_hash"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            is_active=bool(row["is_active"]),
        )

    def insert_user(self, user: StoredUser) -> None:
        try:
            with self.transaction() as connection:
                connection.execute(
                    "INSERT INTO users "
                    "(id, email_normalized, password_hash, created_at, updated_at, is_active) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        user.id,
                        user.email_normalized,
                        user.password_hash,
                        user.created_at,
                        user.updated_at,
                        int(user.is_active),
                    ),
                )
        except sqlite3.IntegrityError:
            raise AccountError("account_exists", ERROR_MESSAGES["account_exists"], 409) from None

    def user_by_email(self, email: str) -> StoredUser | None:
        with self.read() as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE email_normalized = ?", (email,)
            ).fetchone()
        return self._user(row)

    def user_by_id(self, user_id: str) -> StoredUser | None:
        with self.read() as connection:
            row = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return self._user(row)

    def update_password_hash(self, user_id: str, password_hash: str, updated_at: str) -> None:
        with self.transaction() as connection:
            connection.execute(
                "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
                (password_hash, updated_at, user_id),
            )

    def insert_auth_session(
        self,
        session_id: str,
        user_id: str,
        token_hash: str,
        created_at: str,
        expires_at: str,
    ) -> None:
        with self.transaction() as connection:
            connection.execute(
                "INSERT INTO auth_sessions "
                "(id, user_id, token_hash, created_at, expires_at, revoked_at) "
                "VALUES (?, ?, ?, ?, ?, NULL)",
                (session_id, user_id, token_hash, created_at, expires_at),
            )

    def session_with_user(self, token_hash: str) -> sqlite3.Row | None:
        with self.read() as connection:
            return connection.execute(
                "SELECT s.id AS session_id, s.expires_at, s.revoked_at, "
                "u.id, u.email_normalized, u.created_at, u.is_active "
                "FROM auth_sessions s JOIN users u ON u.id = s.user_id "
                "WHERE s.token_hash = ?",
                (token_hash,),
            ).fetchone()

    def revoke_session(self, token_hash: str, revoked_at: str) -> None:
        with self.transaction() as connection:
            connection.execute(
                "UPDATE auth_sessions SET revoked_at = COALESCE(revoked_at, ?) "
                "WHERE token_hash = ?",
                (revoked_at, token_hash),
            )

    def delete_session(self, token_hash: str) -> None:
        with self.transaction() as connection:
            connection.execute("DELETE FROM auth_sessions WHERE token_hash = ?", (token_hash,))

    def add_fitness_owner(self, fitness_session_id: str, user_id: str, created_at: str) -> None:
        try:
            with self.transaction() as connection:
                connection.execute(
                    "INSERT INTO fitness_session_owners "
                    "(fitness_session_id, user_id, created_at) VALUES (?, ?, ?)",
                    (fitness_session_id, user_id, created_at),
                )
        except sqlite3.IntegrityError:
            if self.owns_fitness_session(user_id, fitness_session_id):
                return
            raise AccountError("not_found", ERROR_MESSAGES["not_found"], 404) from None

    def owns_fitness_session(self, user_id: str, fitness_session_id: str) -> bool:
        with self.read() as connection:
            row = connection.execute(
                "SELECT 1 FROM fitness_session_owners "
                "WHERE fitness_session_id = ? AND user_id = ?",
                (fitness_session_id, user_id),
            ).fetchone()
        return row is not None

    def fitness_sessions_for_user(self, user_id: str) -> list[str]:
        with self.read() as connection:
            rows = connection.execute(
                "SELECT fitness_session_id FROM fitness_session_owners WHERE user_id = ?",
                (user_id,),
            ).fetchall()
        return [row["fitness_session_id"] for row in rows]

    def latest_fitness_session_for_user(self, user_id: str) -> str | None:
        with self.read() as connection:
            row = connection.execute(
                "SELECT fitness_session_id FROM fitness_session_owners "
                "WHERE user_id = ? ORDER BY created_at DESC, fitness_session_id DESC LIMIT 1",
                (user_id,),
            ).fetchone()
        return row["fitness_session_id"] if row is not None else None

    def delete_user(self, user_id: str) -> None:
        with self.transaction() as connection:
            connection.execute("DELETE FROM users WHERE id = ?", (user_id,))

    def insert_plan(
        self,
        *,
        record_id: str,
        user_id: str,
        fitness_session_id: str,
        fitness_plan_id: str,
        profile_version: int,
        status: str,
        plan: dict,
        created_at: str,
    ) -> None:
        try:
            body = json.dumps(plan, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
            with self.transaction() as connection:
                connection.execute(
                    "INSERT INTO workout_plans "
                    "(id, user_id, fitness_session_id, fitness_plan_id, source_profile_version, "
                    "status, plan_json, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        record_id,
                        user_id,
                        fitness_session_id,
                        fitness_plan_id,
                        profile_version,
                        status,
                        body,
                        created_at,
                        created_at,
                    ),
                )
        except (sqlite3.IntegrityError, TypeError, ValueError):
            existing = self.plan_by_fitness_id(user_id, fitness_plan_id)
            if existing is not None:
                return
            raise AccountError("database_failure", ERROR_MESSAGES["database_failure"], 500) from None

    def plan_by_fitness_id(self, user_id: str, fitness_plan_id: str) -> sqlite3.Row | None:
        with self.read() as connection:
            return connection.execute(
                "SELECT * FROM workout_plans WHERE fitness_plan_id = ? AND user_id = ?",
                (fitness_plan_id, user_id),
            ).fetchone()

    def plan_for_user(self, user_id: str, record_id: str) -> sqlite3.Row | None:
        with self.read() as connection:
            return connection.execute(
                "SELECT * FROM workout_plans WHERE id = ? AND user_id = ?",
                (record_id, user_id),
            ).fetchone()

    def latest_plan_for_user(self, user_id: str) -> sqlite3.Row | None:
        with self.read() as connection:
            return connection.execute(
                "SELECT * FROM workout_plans WHERE user_id = ? "
                "ORDER BY created_at DESC, id DESC LIMIT 1",
                (user_id,),
            ).fetchone()

    def plans_for_user(self, user_id: str) -> list[sqlite3.Row]:
        with self.read() as connection:
            return connection.execute(
                "SELECT * FROM workout_plans WHERE user_id = ? "
                "ORDER BY created_at DESC, id DESC",
                (user_id,),
            ).fetchall()
