"""Small durable workout-session store built on the existing SQLite database."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class WorkoutStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._migrate()

    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=10000")
        return connection

    def _migrate(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS workout_runtime_sessions (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    workout_plan_id TEXT NOT NULL REFERENCES workout_plans(id) ON DELETE CASCADE,
                    plan_day INTEGER NOT NULL CHECK(plan_day BETWEEN 1 AND 14),
                    scheduled_date TEXT,
                    status TEXT NOT NULL CHECK(status IN ('in_progress','completed','cancelled')),
                    current_block INTEGER NOT NULL DEFAULT 0,
                    current_set INTEGER NOT NULL DEFAULT 1,
                    valid_repetitions INTEGER NOT NULL DEFAULT 0,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    UNIQUE(user_id, workout_plan_id, plan_day)
                );
                CREATE INDEX IF NOT EXISTS idx_runtime_user_date
                    ON workout_runtime_sessions(user_id, scheduled_date);
                CREATE TABLE IF NOT EXISTS workout_set_results (
                    id TEXT PRIMARY KEY,
                    workout_session_id TEXT NOT NULL
                        REFERENCES workout_runtime_sessions(id) ON DELETE CASCADE,
                    block_index INTEGER NOT NULL,
                    set_number INTEGER NOT NULL,
                    valid_repetitions INTEGER NOT NULL DEFAULT 0,
                    rejected_repetitions INTEGER NOT NULL DEFAULT 0,
                    load_kg REAL,
                    form_score INTEGER,
                    completed_at TEXT NOT NULL,
                    UNIQUE(workout_session_id, block_index, set_number)
                );
                """
            )

    def start(self, user_id: str, plan_id: str, day: dict) -> dict:
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT * FROM workout_runtime_sessions "
                "WHERE user_id=? AND workout_plan_id=? AND plan_day=?",
                (user_id, plan_id, day["day"]),
            ).fetchone()
            if existing is None:
                record_id = f"workout_{uuid4().hex}"
                connection.execute(
                    "INSERT INTO workout_runtime_sessions "
                    "(id,user_id,workout_plan_id,plan_day,scheduled_date,status,started_at) "
                    "VALUES (?,?,?,?,?,'in_progress',?)",
                    (record_id, user_id, plan_id, day["day"], day.get("date"), utc_now()),
                )
                existing = connection.execute(
                    "SELECT * FROM workout_runtime_sessions WHERE id=?", (record_id,)
                ).fetchone()
        return dict(existing)

    def for_user(self, user_id: str, workout_id: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM workout_runtime_sessions WHERE id=? AND user_id=?",
                (workout_id, user_id),
            ).fetchone()
        return dict(row) if row else None
