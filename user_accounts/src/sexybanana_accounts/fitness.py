"""Construct the existing fitness-intake service for the account boundary."""

from __future__ import annotations

from .configuration import AccountSettings


def _deepseek_config():
    from sexybanana_intake import DeepSeekConfig

    return DeepSeekConfig.from_env()


def build_fitness_service(settings: AccountSettings):
    """Build the existing intake engine with durable shared storage and a selected provider."""

    from sexybanana_intake import (
        DeepSeekProvider,
        FakeProvider,
        FitnessIntakeService,
        SQLiteStore,
    )

    if settings.fitness_provider == "fake":
        provider = FakeProvider()
    else:
        provider = DeepSeekProvider(_deepseek_config())
    return FitnessIntakeService(
        provider=provider,
        store=SQLiteStore(settings.database_path),
    )
