"""DSL, missingness, source preservation, measurements, records, and graph tests."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from sexybanana_intake import Answer, FitnessIntakeService, IntakeError, Specification
from sexybanana_intake.models import identifier
from sexybanana_intake.specification import convert


def test_complete_specification():
    spec = Specification()
    assert len(spec.sections) == 17
    assert sum(map(len, spec.sections.values())) == 161
    assert sum(map(len, spec.records.values())) == 234
    assert len(spec.matrices) == 3


@pytest.mark.parametrize("bad", ["yes", "unknown", "", 0, 1, [], {}])
def test_bool_does_not_coerce(bad):
    spec = Specification()
    answer = spec.normalize(
        spec.definition("immediate_screen.current_chest_discomfort"),
        {"status": "answered", "value": bad},
    )
    assert answer.status == "invalid" and answer.value is None
    assert answer.history[0]["raw_value"] == bad


@pytest.mark.parametrize(
    "status", ["not_asked", "unknown", "not_measured", "declined", "not_applicable", "invalid"]
)
def test_missingness_has_no_value(status):
    with pytest.raises(ValidationError):
        Answer(status=status, value=False)
    assert Answer(status=status).value is None


@pytest.mark.parametrize(
    "original,target,value,expected",
    [
        ("g", "kg", 1000, 1),
        ("m", "cm", 1.8, 180),
        ("mL", "L", 3000, 3),
        ("L/min", "L/s", 120, 2),
        ("%", "ratio", 80, 0.8),
        ("ratio", "%", 0.8, 80),
        ("in", "cm", 1, 2.54),
        ("lb", "kg", 1, 0.45359237),
    ],
)
def test_explicit_conversions(original, target, value, expected):
    assert convert(value, original, target) == pytest.approx(expected)


def test_incompatible_conversion():
    with pytest.raises(ValueError):
        convert(10, "L", "kg")


def test_measurement_preserves_units_and_unknowns():
    spec = Specification()
    result = spec.normalize(
        spec.definition("profile.weight"),
        {"status": "answered", "value": [{"status": "answered", "value": 70000, "unit": "g"}]},
    )
    child = result.value[0]
    assert child.value == 70 and child.unit == "kg"
    assert child.measurement_metadata.original_value == 70000
    assert child.measurement_metadata.original_unit == "g"
    assert child.measurement_metadata.method == "unknown"


@pytest.mark.parametrize(
    "date_value,precision", [("2018", "year"), ("2018-04", "month"), ("2018-04-03", "day")]
)
def test_incomplete_dates_not_fabricated(date_value, precision):
    spec = Specification()
    result = spec.normalize(
        spec.records["injury"]["onset_date"], {"status": "answered", "value": date_value}
    )
    assert result.value == date_value and result.date_precision == precision


@pytest.mark.parametrize(
    "path,bad",
    [
        ("profile.age", -1),
        ("goals_and_constraints.days_per_week", 8),
        ("goals_and_constraints.days_per_week", True),
        ("nutrition_recovery.sleep_hours", 25),
    ],
)
def test_domain_bounds(path, bad):
    spec = Specification()
    assert (
        spec.normalize(spec.definition(path), {"status": "answered", "value": bad}).status
        == "invalid"
    )


def test_real_zero_and_matrix_unknowns(a):
    service = FitnessIntakeService()
    sid = service.create_session().session_id
    service.submit_answers(
        sid,
        {
            "function.falls_last_12_months": a(0),
            "medical_history.condition_screen.diabetes": a(False),
        },
    )
    session = service.get_session(sid)
    assert session.responses["function"]["falls_last_12_months"].value == 0
    matrix = session.responses["medical_history"]["condition_screen"].value
    assert matrix["diabetes"].value is False
    assert matrix["cardiac_disease"].status == "not_asked"


def test_repeated_records_and_stable_child_update(a):
    service = FitnessIntakeService()
    sid = service.create_session().session_id
    service.submit_answers(
        sid,
        {"injury_history.injuries": a([{"event_name": a("Old surgery"), "onset_date": a("2010")}])},
        request_id="event1",
    )
    service.submit_answers(
        sid, {"injury_history.injuries": a([{"event_name": a("Different injury")}])}
    )
    records = service.get_session(sid).responses["injury_history"]["injuries"].value
    path = "injury_history.injuries." + records[0]["record_id"] + ".side"
    service.update_answer(sid, path, a("left"))
    updated = service.get_session(sid).responses["injury_history"]["injuries"].value
    assert len(updated) == 2
    assert updated[0]["side"].value == "left"
    assert updated[0]["onset_date"].value == "2010"
    assert updated[1]["event_name"].value == "Different injury"


def test_duplicate_yaml_rejected(tmp_path):
    source = Path(__file__).parents[1] / "src/sexybanana_intake/resources/fitness_intake_spec.yaml"
    target = tmp_path / "bad.yaml"
    target.write_text(source.read_text() + "\nspec: {}\n")
    with pytest.raises(IntakeError, match="invalid"):
        Specification(target)


def test_unsafe_yaml_rejected(tmp_path):
    target = tmp_path / "bad.yaml"
    target.write_text("!!python/object/apply:os.system ['echo forbidden']")
    with pytest.raises(IntakeError):
        Specification(target)


def test_refs_reject_cross_session_and_wrong_type(a):
    service = FitnessIntakeService()
    first = service.create_session()
    second = service.create_session()
    foreign = second.responses["profile"]["age"].answer_id
    for ref in [foreign, first.responses["profile"]["age"].answer_id, identifier("report")]:
        with pytest.raises(IntakeError) as error:
            service.submit_answers(
                first.session_id, {"injury_history.rehabilitation_documents": a([ref])}
            )
        assert error.value.code == "invalid_reference"


def test_import_duplicates_and_consent(ready):
    service, sid = ready
    exported = json.loads(service.export_session(sid))
    exported["consent"]["external_ai"] = True
    restored = FitnessIntakeService().import_session(exported)
    assert restored.consent.external_ai is False
    assert restored.needs_update is True
    exported["responses"]["profile"]["age"]["answer_id"] = exported["responses"]["profile"][
        "height"
    ]["answer_id"]
    with pytest.raises(IntakeError) as error:
        FitnessIntakeService().import_session(exported)
    assert error.value.code == "invalid_identifier"
