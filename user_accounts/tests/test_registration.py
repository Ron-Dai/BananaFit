from conftest import csrf, register


def test_registration_creates_account_hash_and_session(client, database, settings):
    response = register(client, " Person@Example.COM ")
    assert response.status_code == 201
    assert response.json()["redirect_url"] == "http://localhost:5173/"
    assert response.json()["user"]["email"] == "person@example.com"
    assert settings.cookie_name in response.cookies
    stored = database.user_by_email("person@example.com")
    assert stored is not None
    assert stored.password_hash != "securepass123"
    assert stored.password_hash.startswith("$argon2id$")


def test_duplicate_registration_is_rejected(client):
    assert register(client).status_code == 201
    client.cookies.clear()
    response = register(client)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "account_exists"


def test_invalid_email_is_rejected(client):
    token = csrf(client)
    response = client.post(
        "/api/auth/register",
        headers={"X-CSRF-Token": token},
        json={
            "email": "not-an-email",
            "password": "securepass123",
            "password_confirmation": "securepass123",
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_email"


def test_weak_and_mismatched_passwords_have_stable_errors(client):
    token = csrf(client)
    weak = client.post(
        "/api/auth/register",
        headers={"X-CSRF-Token": token},
        json={"email": "a@example.com", "password": "onlylettersxx", "password_confirmation": "onlylettersxx"},
    )
    assert weak.json()["error"]["code"] == "weak_password"
    mismatch = client.post(
        "/api/auth/register",
        headers={"X-CSRF-Token": token},
        json={"email": "a@example.com", "password": "securepass123", "password_confirmation": "different1234"},
    )
    assert mismatch.json()["error"]["code"] == "password_mismatch"


def test_client_cannot_submit_user_id_during_registration(client):
    token = csrf(client)
    response = client.post(
        "/api/auth/register",
        headers={"X-CSRF-Token": token},
        json={
            "email": "a@example.com",
            "password": "securepass123",
            "password_confirmation": "securepass123",
            "user_id": "user_someone_else",
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"
