import sys
from pathlib import Path

from fastapi.testclient import TestClient

from conftest import csrf, register
from sexybanana_accounts import AccountDatabase, build_fitness_service, create_app

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "fitness_intake" / "examples"))
from common import fictional_answers  # noqa: E402


def questionnaire_client(settings):
    offline = settings.model_copy(update={"fitness_provider": "fake"})
    database = AccountDatabase(offline.database_path)
    fitness = build_fitness_service(offline)
    return TestClient(
        create_app(offline, fitness_service=fitness, database=database),
        base_url="http://testserver",
    )


def test_questionnaire_page_is_public_and_matches_approved_shell(client):
    page = client.get("/intake")
    assert page.status_code == 200
    assert "Fitness Intake" in page.text
    assert "Sign in to save progress" in page.text
    assert "Let’s check that training is appropriate today" in page.text
    assert "<aside" not in page.text

    stylesheet = client.get("/auth-static/intake.css")
    script = client.get("/auth-static/intake.js")
    assert stylesheet.status_code == 200
    assert "#ed7048" in stylesheet.text
    assert script.status_code == 200
    assert "/api/intake/current" in script.text


def test_questionnaire_data_api_requires_login(client):
    assert client.get("/api/intake/current").status_code == 401
    assert client.get("/api/intake/sessions/not-real/questionnaire").status_code == 401


def test_answer_submission_is_saved_and_returns_next_questions(settings):
    with questionnaire_client(settings) as client:
        assert register(client).status_code == 201
        assert client.get("/api/intake/current").json() == {
            "status": "none",
            "session": None,
        }

        token = csrf(client)
        created = client.post(
            "/api/intake/sessions",
            headers={"X-CSRF-Token": token, "Origin": "http://testserver"},
            json={},
        )
        assert created.status_code == 201
        session_id = created.json()["session_id"]

        state = client.get(f"/api/intake/sessions/{session_id}/questionnaire")
        assert state.status_code == 200
        before = state.json()
        assert before["stage"] == {"number": 2, "total": 6, "label": "Safety"}
        assert len(before["questions"]) == 3

        answers = {
            question["field_path"]: {
                "status": "answered",
                "value": False,
                "source_type": "self_report",
            }
            for question in before["questions"]
        }
        token = csrf(client)
        submitted = client.post(
            f"/api/intake/sessions/{session_id}/answers",
            headers={"X-CSRF-Token": token, "Origin": "http://testserver"},
            json={
                "answers": answers,
                "expected_version": before["version"],
                "request_id": "questionnaire-test-1",
            },
        )
        assert submitted.status_code == 200
        after = submitted.json()
        assert after["version"] > before["version"]
        assert {question["field_path"] for question in after["questions"]}.isdisjoint(
            answers
        )

        stored = client.get(f"/api/intake/sessions/{session_id}").json()
        for path in answers:
            section, field = path.split(".")
            assert stored["responses"][section][field]["value"] is False

        current = client.get("/api/intake/current").json()
        assert current["status"] == "available"
        assert current["session"]["session_id"] == session_id


def test_another_user_cannot_read_or_answer_an_owned_questionnaire(settings):
    with questionnaire_client(settings) as owner:
        assert register(owner, "owner@example.com").status_code == 201
        token = csrf(owner)
        created = owner.post(
            "/api/intake/sessions",
            headers={"X-CSRF-Token": token},
            json={},
        )
        session_id = created.json()["session_id"]

        with questionnaire_client(settings) as stranger:
            assert register(stranger, "stranger@example.com").status_code == 201
            assert (
                stranger.get(f"/api/intake/sessions/{session_id}/questionnaire").status_code
                == 404
            )
            token = csrf(stranger)
            response = stranger.post(
                f"/api/intake/sessions/{session_id}/answers",
                headers={"X-CSRF-Token": token},
                json={
                    "answers": {
                        "immediate_screen.current_chest_discomfort": {
                            "status": "answered",
                            "value": False,
                        }
                    },
                    "request_id": "stranger-test-1",
                },
            )
            assert response.status_code == 404


def test_login_redirects_to_app_after_a_plan_is_saved(client, settings):
    assert register(client).status_code == 201
    token = csrf(client)
    created = client.post(
        "/api/intake/sessions",
        headers={"X-CSRF-Token": token},
        json={},
    )
    session_id = created.json()["session_id"]
    token = csrf(client)
    generated = client.post(
        f"/api/intake/sessions/{session_id}/generate-plan",
        headers={"X-CSRF-Token": token},
        json={},
    )
    assert generated.status_code == 200
    assert generated.json()["current_plan"]["status"] == "available"

    token = csrf(client)
    assert client.post("/api/auth/logout", headers={"X-CSRF-Token": token}).status_code == 200
    token = csrf(client)
    logged_in = client.post(
        "/api/auth/login",
        headers={"X-CSRF-Token": token},
        json={"email": "person@example.com", "password": "securepass123"},
    )
    assert logged_in.status_code == 200
    assert logged_in.json()["redirect_url"] == settings.app_url


def test_completed_questionnaire_generates_and_saves_owned_fourteen_day_plan(settings):
    with questionnaire_client(settings) as client:
        assert register(client, "planner@example.com").status_code == 201
        token = csrf(client)
        created = client.post(
            "/api/intake/sessions",
            headers={"X-CSRF-Token": token},
            json={},
        )
        session_id = created.json()["session_id"]
        version = created.json()["version"]

        answer_items = []
        for path, answer in fictional_answers().items():
            envelope = {
                "status": answer.status,
                "source_type": "self_report",
            }
            if answer.status == "answered":
                envelope["value"] = answer.value
            if answer.unit:
                envelope["unit"] = answer.unit
            answer_items.append((path, envelope))

        for offset in range(0, len(answer_items), 3):
            token = csrf(client)
            response = client.post(
                f"/api/intake/sessions/{session_id}/answers",
                headers={"X-CSRF-Token": token},
                json={
                    "answers": dict(answer_items[offset : offset + 3]),
                    "expected_version": version,
                    "request_id": f"full-intake-{offset:03d}",
                },
            )
            assert response.status_code == 200, response.text
            version = response.json()["version"]

        token = csrf(client)
        consent = client.post(
            f"/api/intake/sessions/{session_id}/consent",
            headers={"X-CSRF-Token": token},
            json={
                "consent": {
                    "external_ai": True,
                    "sensitive_sections": [],
                    "attachments": False,
                    "purpose": "Fitness intake and fourteen-day planning",
                },
                "expected_version": version,
            },
        )
        assert consent.status_code == 200

        token = csrf(client)
        generated = client.post(
            f"/api/intake/sessions/{session_id}/generate-plan",
            headers={"X-CSRF-Token": token},
            json={"expected_version": consent.json()["version"]},
        )
        assert generated.status_code == 200, generated.text
        result = generated.json()
        assert result["status"] == "ready"
        assert result["current_plan"]["status"] == "available"
        assert result["redirect_url"] == settings.app_url
        assert len(result["current_plan"]["plan"]["days"]) == 14
        assert result["current_plan"]["plan"]["fitness_session_id"] == session_id

        listed = client.get("/api/plans").json()["plans"]
        assert len(listed) == 1
        assert listed[0]["fitness_session_id"] == session_id
