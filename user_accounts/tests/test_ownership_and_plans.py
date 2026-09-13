import pytest

from conftest import csrf, register, sample_plan
from sexybanana_accounts.errors import AccountError


def _service(app):
    return app.state.account_service


def _new_user(service, email):
    return service.register(email, "securepass123")


def test_session_and_plan_are_associated_with_server_user(app):
    service = _service(app)
    user = _new_user(service, "owner@example.com")
    session = service.create_fitness_session_for_user(user.id)
    result = service.generate_plan_for_user(user.id, session.session_id)
    assert result.plan["session_id"] == session.session_id
    current = service.get_current_plan_for_user(user.id)
    assert current.status == "available"
    assert current.plan.fitness_session_id == session.session_id
    assert current.plan.summary.duration_days == 14
    assert current.plan.summary.training_days == 4
    assert current.plan.summary.next_session_title == "Wall push-up"
    assert "Chest" in current.plan.summary.target_muscle_groups


def test_user_cannot_access_another_users_session_or_plan(app):
    service = _service(app)
    owner = _new_user(service, "owner@example.com")
    attacker = _new_user(service, "attacker@example.com")
    session = service.create_fitness_session_for_user(owner.id)
    service.generate_plan_for_user(owner.id, session.session_id)
    record_id = service.get_current_plan_for_user(owner.id).plan.id
    with pytest.raises(AccountError) as session_error:
        service.generate_plan_for_user(attacker.id, session.session_id)
    assert session_error.value.code == "not_found"
    with pytest.raises(AccountError) as plan_error:
        service.get_plan_for_user(attacker.id, record_id)
    assert plan_error.value.code == "not_found"
    assert service.list_plans_for_user(attacker.id) == []


def test_plan_save_is_idempotent(app):
    service = _service(app)
    user = _new_user(service, "owner@example.com")
    session = service.create_fitness_session_for_user(user.id)
    plan = sample_plan(session.session_id)
    session.plans.append(plan)
    first = service.save_plan_for_user(user.id, session.session_id, plan)
    second = service.save_plan_for_user(user.id, session.session_id, plan)
    assert first == second
    assert len(service.list_plans_for_user(user.id)) == 1


def test_missing_and_stale_plan_states(app):
    service = _service(app)
    user = _new_user(service, "owner@example.com")
    assert service.get_current_plan_for_user(user.id).model_dump() == {
        "status": "none",
        "plan": None,
    }
    session = service.create_fitness_session_for_user(user.id)
    plan = sample_plan(session.session_id, stale=True)
    session.plans.append(plan)
    service.save_plan_for_user(user.id, session.session_id, plan)
    assert service.get_current_plan_for_user(user.id).status == "stale"


def test_invalid_plan_is_rejected(app):
    service = _service(app)
    user = _new_user(service, "owner@example.com")
    session = service.create_fitness_session_for_user(user.id)
    with pytest.raises(AccountError) as error:
        service.save_plan_for_user(user.id, session.session_id, {"plan_id": "plan_bad"})
    assert error.value.code == "invalid_request"


def test_url_plan_id_manipulation_returns_same_404(client, app):
    service = _service(app)
    owner = _new_user(service, "owner@example.com")
    owner_session = service.create_fitness_session_for_user(owner.id)
    service.generate_plan_for_user(owner.id, owner_session.session_id)
    owner_plan_id = service.get_current_plan_for_user(owner.id).plan.id
    assert register(client, "attacker@example.com").status_code == 201
    foreign = client.get(f"/api/plans/{owner_plan_id}")
    missing = client.get("/api/plans/userplan_does_not_exist")
    assert foreign.status_code == missing.status_code == 404
    assert foreign.json() == missing.json()


def test_url_intake_session_manipulation_returns_404(client, app):
    service = _service(app)
    owner = _new_user(service, "owner@example.com")
    owner_session = service.create_fitness_session_for_user(owner.id)
    assert register(client, "attacker@example.com").status_code == 201
    response = client.get(f"/api/intake/sessions/{owner_session.session_id}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_protected_api_and_current_plan_contract(client, app):
    assert client.get("/api/plans/current").status_code == 401
    assert register(client).status_code == 201
    service = _service(app)
    user_id = client.get("/api/auth/me").json()["user"]["id"]
    session = service.create_fitness_session_for_user(user_id)
    service.generate_plan_for_user(user_id, session.session_id)
    response = client.get("/api/plans/current")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "available"
    assert body["plan"]["summary"]["duration_days"] == 14
    assert "password_hash" not in response.text
    assert "constraints" not in body["plan"]


def test_api_create_session_ignores_client_identity(client, app):
    assert register(client).status_code == 201
    authenticated_id = client.get("/api/auth/me").json()["user"]["id"]
    token = csrf(client)
    response = client.post(
        "/api/intake/sessions?user_id=user_someone_else",
        headers={"X-CSRF-Token": token},
    )
    assert response.status_code == 201
    session_id = response.json()["session_id"]
    assert app.state.account_service.database.owns_fitness_session(authenticated_id, session_id)


def test_api_creates_session_with_explicit_external_ai_consent(client, app):
    assert register(client).status_code == 201
    authenticated_id = client.get("/api/auth/me").json()["user"]["id"]
    token = csrf(client)
    response = client.post(
        "/api/intake/sessions",
        headers={"X-CSRF-Token": token},
        json={
            "consent": {
                "external_ai": True,
                "sensitive_sections": [],
                "attachments": False,
                "purpose": "Fitness intake and fourteen-day planning",
            }
        },
    )
    assert response.status_code == 201
    session_id = response.json()["session_id"]
    assert app.state.account_service.database.owns_fitness_session(
        authenticated_id, session_id
    )
    assert app.state.account_service.fitness_service.get_session(
        session_id
    ).consent.external_ai is True


def test_consent_update_requires_session_ownership(client, app):
    service = _service(app)
    owner = _new_user(service, "owner@example.com")
    session = service.create_fitness_session_for_user(owner.id)
    assert register(client, "attacker@example.com").status_code == 201
    token = csrf(client)
    body = {
        "consent": {
            "external_ai": True,
            "sensitive_sections": [],
            "attachments": False,
            "purpose": "Fitness intake and fourteen-day planning",
        },
        "expected_version": 0,
    }
    foreign = client.post(
        f"/api/intake/sessions/{session.session_id}/consent",
        headers={"X-CSRF-Token": token},
        json=body,
    )
    missing = client.post(
        "/api/intake/sessions/session_missing/consent",
        headers={"X-CSRF-Token": token},
        json=body,
    )
    assert foreign.status_code == missing.status_code == 404
    assert foreign.json() == missing.json()


def test_delete_user_data_removes_sessions_and_owned_records(app, fitness):
    service = _service(app)
    user = _new_user(service, "owner@example.com")
    session = service.create_fitness_session_for_user(user.id)
    service.generate_plan_for_user(user.id, session.session_id)
    service.delete_user_data(user.id)
    assert service.database.user_by_id(user.id) is None
    assert session.session_id not in fitness.sessions
    assert service.database.fitness_sessions_for_user(user.id) == []
