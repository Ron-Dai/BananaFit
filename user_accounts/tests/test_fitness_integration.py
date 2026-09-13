import pytest

from sexybanana_accounts import (
    AccountDatabase,
    AccountService,
    build_fitness_service,
    create_app,
)
from sexybanana_accounts.errors import AccountError
from sexybanana_intake import DeepSeekProvider, FakeProvider


DEEPSEEK_ENVIRONMENT = (
    "DEEPSEEK_API_KEY",
    "DEEPSEEK_MODEL",
    "DEEPSEEK_BASE_URL",
    "DEEPSEEK_TIMEOUT_SECONDS",
    "DEEPSEEK_MAX_RETRIES",
    "DEEPSEEK_MAX_TOKENS",
    "DEEPSEEK_TEMPERATURE",
)


def clear_deepseek_environment(monkeypatch):
    for name in DEEPSEEK_ENVIRONMENT:
        monkeypatch.delenv(name, raising=False)


def test_default_builder_injects_live_deepseek_without_network(monkeypatch, settings):
    clear_deepseek_environment(monkeypatch)

    fitness = build_fitness_service(settings)

    assert isinstance(fitness.provider, DeepSeekProvider)
    assert fitness.provider.config.model == "deepseek/deepseek-chat"
    assert fitness.provider.config.base_url == "https://openrouter.ai/api/v1"
    assert fitness.provider.config.api_key.get_secret_value().startswith("sk-or-v1-")
    assert fitness.store.path == settings.database_path


def test_environment_overrides_bundled_development_provider(monkeypatch, settings):
    clear_deepseek_environment(monkeypatch)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-override-key")
    monkeypatch.setenv("DEEPSEEK_MODEL", "test-model")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://provider.example/api/v1")

    fitness = build_fitness_service(settings)

    assert fitness.provider.config.api_key.get_secret_value() == "test-override-key"
    assert fitness.provider.config.model == "test-model"
    assert fitness.provider.config.base_url == "https://provider.example/api/v1"


def test_fake_provider_remains_an_explicit_offline_option(settings):
    offline = settings.model_copy(update={"fitness_provider": "fake"})

    fitness = build_fitness_service(offline)

    assert isinstance(fitness.provider, FakeProvider)


def test_app_factory_uses_builder_when_no_service_is_injected(monkeypatch, settings, database):
    clear_deepseek_environment(monkeypatch)

    app = create_app(settings, database=database)

    assert isinstance(app.state.account_service.fitness_service.provider, DeepSeekProvider)


def test_real_intake_validation_becomes_safe_account_error(settings):
    offline = settings.model_copy(update={"fitness_provider": "fake"})
    fitness = build_fitness_service(offline)
    accounts = AccountService(offline, AccountDatabase(offline.database_path), fitness)
    user = accounts.register("consent@example.com", "ConsentRules123")

    with pytest.raises(AccountError) as error:
        accounts.create_fitness_session_for_user(
            user.id,
            consent={"external_ai": True, "sensitive_sections": ["not_a_real_section"]},
        )

    assert error.value.code == "invalid_consent"
    assert error.value.status_code == 422
