import os
from concurrent.futures import ThreadPoolExecutor
import pytest
from pydantic import ValidationError

from sexybanana_accounts import AccountDatabase, AccountSettings
from sexybanana_accounts.errors import AccountError
from sexybanana_accounts.models import StoredUser


def test_migrations_are_idempotent(settings):
    first = AccountDatabase(settings.database_path)
    first.migrate()
    second = AccountDatabase(settings.database_path)
    with second.read() as connection:
        versions = connection.execute(
            "SELECT version FROM account_schema_migrations ORDER BY version"
        ).fetchall()
        foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()[0]
    assert [row[0] for row in versions] == [1]
    assert foreign_keys == 1


def test_database_file_is_owner_only(settings):
    AccountDatabase(settings.database_path)
    assert os.stat(settings.database_path).st_mode & 0o077 == 0


def test_foreign_keys_reject_unknown_users(database):
    with pytest.raises(AccountError) as error:
        database.add_fitness_owner("session_unknown", "user_unknown", "2026-09-13T00:00:00+00:00")
    assert error.value.code == "not_found"


def test_configuration_rejects_unsafe_redirect():
    with pytest.raises(ValidationError):
        AccountSettings(app_url="javascript:alert(1)")
    with pytest.raises(ValidationError):
        AccountSettings(app_url="https://person:secret@example.com/")
    with pytest.raises(ValidationError):
        AccountSettings(questionnaire_url="//attacker.example/intake")
    with pytest.raises(ValidationError):
        AccountSettings(questionnaire_url="javascript:alert(1)")
    with pytest.raises(ValidationError):
        AccountSettings(questionnaire_url="/\\attacker.example/intake")
    with pytest.raises(ValidationError):
        AccountSettings(questionnaire_url="/intake#unexpected")

    assert AccountSettings(questionnaire_url="/intake").questionnaire_url == "/intake"


def test_origin_list_is_explicit_and_deduplicated():
    settings = AccountSettings(allowed_origins="http://localhost:5173/, http://localhost:5173")
    assert settings.origin_list == ["http://localhost:5173"]


def test_from_env_uses_component_prefix(monkeypatch, tmp_path):
    database_path = tmp_path / "from-env.db"
    monkeypatch.setenv("SEXYBANANA_DATABASE_PATH", str(database_path))
    monkeypatch.setenv("SEXYBANANA_AUTH_PORT", "9100")

    settings = AccountSettings.from_env()

    assert settings.database_path == database_path
    assert settings.auth_port == 9100


def test_concurrent_duplicate_user_insert_has_one_winner(database):
    def insert(index):
        user = StoredUser(
            id=f"user_{index}",
            email_normalized="same@example.com",
            password_hash="$argon2id$synthetic",
            created_at="2026-09-13T00:00:00+00:00",
            updated_at="2026-09-13T00:00:00+00:00",
            is_active=True,
        )
        try:
            database.insert_user(user)
            return "created"
        except AccountError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(insert, [1, 2]))
    assert sorted(outcomes) == ["account_exists", "created"]
