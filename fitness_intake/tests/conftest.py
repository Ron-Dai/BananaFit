"""Fictional isolated fixtures; tests never send network requests."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "examples"))
from common import answered, fictional_answers  # noqa: E402
from sexybanana_intake import FakeProvider, FitnessIntakeService  # noqa: E402


@pytest.fixture
def ready():
    service = FitnessIntakeService(provider=FakeProvider())
    session = service.create_session()
    service.submit_answers(session.session_id, fictional_answers())
    return service, session.session_id


@pytest.fixture
def a():
    return answered
