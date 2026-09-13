from datetime import datetime, timedelta, timezone

from conftest import csrf, register


def test_login_me_and_logout(client, settings):
    assert register(client).status_code == 201
    token = csrf(client)
    logout = client.post("/api/auth/logout", headers={"X-CSRF-Token": token})
    assert logout.status_code == 200
    assert client.get("/api/auth/me").status_code == 401
    token = csrf(client)
    login = client.post(
        "/api/auth/login",
        headers={"X-CSRF-Token": token},
        json={"email": "PERSON@example.com", "password": "securepass123"},
    )
    assert login.status_code == 200
    assert login.cookies[settings.cookie_name]
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["email"] == "person@example.com"


def test_invalid_credentials_are_generic(client):
    assert register(client).status_code == 201
    client.cookies.clear()
    for email, password in [
        ("missing@example.com", "securepass123"),
        ("person@example.com", "wrong-password"),
        ("invalid", "wrong-password"),
    ]:
        token = csrf(client)
        response = client.post(
            "/api/auth/login",
            headers={"X-CSRF-Token": token},
            json={"email": email, "password": password},
        )
        assert response.status_code == 401
        assert response.json()["error"] == {
            "code": "invalid_credentials",
            "message": "The email or password is incorrect.",
        }


def test_missing_and_bad_csrf_are_rejected(client):
    response = client.post(
        "/api/auth/register",
        json={"email": "a@example.com", "password": "securepass123", "password_confirmation": "securepass123"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_failed"
    csrf(client)
    response = client.post(
        "/api/auth/register",
        headers={"X-CSRF-Token": "wrong"},
        json={"email": "a@example.com", "password": "securepass123", "password_confirmation": "securepass123"},
    )
    assert response.status_code == 403


def test_untrusted_origin_is_rejected(client):
    token = csrf(client)
    response = client.post(
        "/api/auth/register",
        headers={"X-CSRF-Token": token, "Origin": "https://attacker.example"},
        json={"email": "a@example.com", "password": "securepass123", "password_confirmation": "securepass123"},
    )
    assert response.status_code == 403


def test_expired_session_is_deleted(client, database, settings):
    assert register(client).status_code == 201
    raw = client.cookies.get(settings.cookie_name)
    with database.transaction() as connection:
        connection.execute(
            "UPDATE auth_sessions SET expires_at = ? WHERE token_hash = ?",
            ((datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(), __import__("hashlib").sha256(raw.encode()).hexdigest()),
        )
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "session_expired"


def test_logout_is_idempotent(client):
    token = csrf(client)
    first = client.post("/api/auth/logout", headers={"X-CSRF-Token": token})
    second_token = csrf(client)
    second = client.post("/api/auth/logout", headers={"X-CSRF-Token": second_token})
    assert first.status_code == second.status_code == 200
