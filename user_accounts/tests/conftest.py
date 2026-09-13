from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from sexybanana_accounts import AccountDatabase, AccountSettings, create_app


def sample_plan(session_id: str, *, stale: bool = False) -> dict:
    days = []
    for day in range(1, 15):
        training = day in {1, 4, 8, 11}
        blocks = []
        if training:
            blocks = [
                {
                    "exercise_id": "walk",
                    "name": "Comfortable level walking",
                    "phase": "warmup",
                    "active_minutes": 2.0,
                    "rest_minutes": 0.0,
                    "sets": None,
                    "repetitions": None,
                    "rpe": 1.0,
                    "equipment": [],
                    "instructions": "Use a comfortable pace.",
                },
                {
                    "exercise_id": "wall_pushup",
                    "name": "Wall push-up",
                    "phase": "main",
                    "active_minutes": 4.0,
                    "rest_minutes": 2.0,
                    "sets": 2,
                    "repetitions": 8,
                    "rpe": 3.0,
                    "equipment": ["wall"],
                    "instructions": "Use a stable wall.",
                },
                {
                    "exercise_id": "walk",
                    "name": "Comfortable level walking",
                    "phase": "cooldown",
                    "active_minutes": 2.0,
                    "rest_minutes": 0.0,
                    "sets": None,
                    "repetitions": None,
                    "rpe": 1.0,
                    "equipment": [],
                    "instructions": "Slow down gradually.",
                },
            ]
        days.append(
            {
                "day": day,
                "date": f"2026-09-{13 + day:02d}",
                "kind": "training" if training else "rest",
                "objective": "Practice tolerated movement." if training else "Rest.",
                "total_minutes": 10.0 if training else 0.0,
                "blocks": blocks,
            }
        )
    return {
        "plan_id": "plan_" + session_id.split("_", 1)[-1],
        "session_id": session_id,
        "profile_version": 2,
        "generated_at": "2026-09-13T12:00:00+00:00",
        "start_date": "2026-09-14",
        "goals": ["health", "strength"],
        "stale": stale,
        "days": days,
    }


class StubFitnessService:
    def __init__(self):
        self.sessions = {}
        self.counter = 0

    def create_session(self, **_kwargs):
        self.counter += 1
        session = SimpleNamespace(
            session_id=f"session_{self.counter}",
            version=0,
            profile_version=2,
            plans=[],
            feedback=[],
            consent=SimpleNamespace(
                external_ai=bool(_kwargs.get("consent", {}).get("external_ai", False)),
                sensitive_sections=list(
                    _kwargs.get("consent", {}).get("sensitive_sections", [])
                ),
                attachments=bool(_kwargs.get("consent", {}).get("attachments", False)),
                purpose=_kwargs.get("consent", {}).get(
                    "purpose", "Fitness intake and fourteen-day planning"
                ),
                model_dump=lambda: {
                    "external_ai": bool(_kwargs.get("consent", {}).get("external_ai", False)),
                    "sensitive_sections": list(
                        _kwargs.get("consent", {}).get("sensitive_sections", [])
                    ),
                    "attachments": bool(
                        _kwargs.get("consent", {}).get("attachments", False)
                    ),
                    "purpose": _kwargs.get("consent", {}).get(
                        "purpose", "Fitness intake and fourteen-day planning"
                    ),
                },
            ),
        )
        self.sessions[session.session_id] = session
        return session

    def get_session(self, session_id: str):
        if session_id not in self.sessions:
            raise KeyError(session_id)
        return self.sessions[session_id]

    def delete_session(self, session_id: str):
        self.sessions.pop(session_id, None)

    def update_consent(self, session_id: str, consent, *, expected_version=None):
        session = self.get_session(session_id)
        if expected_version is not None and expected_version != session.version:
            error = RuntimeError("Session changed; reload before updating consent.")
            error.code = "version_conflict"
            raise error
        session.version += 1
        session.consent = SimpleNamespace(
            **consent,
            model_dump=lambda: dict(consent),
        )
        return session

    def generate_plan(self, session_id: str, **_kwargs):
        session = self.get_session(session_id)
        plan = sample_plan(session_id)
        session.plans.append(deepcopy(plan))

        class Readiness:
            def model_dump(self):
                return {"status": "ready", "flags": [], "missing": []}

        return SimpleNamespace(status="ready", readiness=Readiness(), plan=plan)


@pytest.fixture
def settings(tmp_path: Path) -> AccountSettings:
    return AccountSettings(
        database_path=tmp_path / "accounts.db",
        app_url="http://localhost:5173/",
        allowed_origins="http://testserver,http://localhost:5173",
        session_lifetime_seconds=3600,
    )


@pytest.fixture
def fitness() -> StubFitnessService:
    return StubFitnessService()


@pytest.fixture
def database(settings: AccountSettings) -> AccountDatabase:
    return AccountDatabase(settings.database_path)


@pytest.fixture
def app(settings, fitness, database):
    return create_app(settings, fitness_service=fitness, database=database)


@pytest.fixture
def client(app):
    with TestClient(app, base_url="http://testserver") as value:
        yield value


def csrf(client: TestClient) -> str:
    response = client.get("/api/auth/csrf")
    assert response.status_code == 200
    return response.json()["csrf_token"]


def register(client: TestClient, email="person@example.com", password="securepass123"):
    token = csrf(client)
    return client.post(
        "/api/auth/register",
        headers={"X-CSRF-Token": token, "Origin": "http://testserver"},
        json={"email": email, "password": password, "password_confirmation": password},
    )
