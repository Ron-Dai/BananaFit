"""Reject invalid candidate schedules and preserve executed history on revision."""

import copy

import pytest

from sexybanana_intake import FakeProvider, Feedback, IntakeError
from sexybanana_intake.planning import normalize_strength_timing, plan_contract, validate_candidate


def test_exact_fourteen_days_with_rest(ready):
    service, sid = ready
    result = service.generate_plan(sid, start_date="2026-09-14", timezone="America/New_York")
    plan = result.plan
    assert [d["day"] for d in plan["days"]] == list(range(1, 15))
    assert plan["days"][-1]["date"] == "2026-09-27"
    assert sum(d["kind"] == "training" for d in plan["days"]) == 6
    assert all(d["total_minutes"] <= 20 for d in plan["days"])
    assert all(d["conditional"] for d in plan["days"][7:])
    assert "RPE (0–10)" in service.render_plan_markdown(plan)


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "duplicate",
        "equipment",
        "rpe",
        "duration",
        "extra_field",
        "rest_exercise",
        "progression",
    ],
)
def test_candidate_rejection(ready, mutation):
    service, sid = ready
    session = service.get_session(sid)
    readiness = service.evaluate_readiness(sid)
    contract = plan_contract(session, readiness, None, None)
    raw = FakeProvider().generate("plan", {}, contract)
    if mutation == "missing":
        raw["days"].pop()
    elif mutation == "duplicate":
        raw["days"][1]["day"] = 1
    elif mutation == "equipment":
        raw["days"][0]["blocks"][1]["exercise_id"] = "stationary_cycle"
    elif mutation == "rpe":
        raw["days"][0]["blocks"][1]["rpe"] = 6
    elif mutation == "duration":
        raw["days"][0]["preparation_minutes"] = 20
    elif mutation == "extra_field":
        raw["days"][0]["diagnosis"] = "perfectly healthy"
    elif mutation == "rest_exercise":
        raw["days"][1]["blocks"] = copy.deepcopy(raw["days"][0]["blocks"])
    elif mutation == "progression":
        raw["days"][7]["blocks"][1]["rpe"] = 4
    with pytest.raises(IntakeError):
        validate_candidate(raw, session, readiness, contract)


def test_feedback_revision_keeps_completed_days(ready):
    service, sid = ready
    original = service.generate_plan(sid).plan
    service.submit_feedback(
        sid, Feedback(plan_id=original["plan_id"], day=7, completed=True, tolerance="too_hard")
    )
    result = service.revise_plan(sid, original["plan_id"], completed_through=7)
    assert result.plan["days"][:7] == original["days"][:7]
    assert result.plan["supersedes_plan_id"] == original["plan_id"]
    assert all(b["rpe"] <= 3 for d in result.plan["days"][7:] for b in d["blocks"])
    assert len(service.get_session(sid).plans) == 2


def test_strength_total_duration_is_split_into_active_work_and_rest(ready):
    service, sid = ready
    session = service.get_session(sid)
    readiness = service.evaluate_readiness(sid)
    contract = plan_contract(session, readiness, None, None)
    raw = FakeProvider().generate("plan", {}, contract)
    block = raw["days"][0]["blocks"][1]
    block.update(
        exercise_id="sit_to_stand",
        active_minutes=5.0,
        rest_minutes=0.0,
        sets=2,
        repetitions=5,
    )
    normalized = normalize_strength_timing(raw, readiness.max_minutes)
    repaired = normalized["days"][0]["blocks"][1]
    assert repaired["active_minutes"] == pytest.approx(2 * 5 * 4 / 60)
    assert repaired["active_minutes"] + repaired["rest_minutes"] == pytest.approx(5.0)


def test_feedback_symptoms_block_replanning(ready):
    service, sid = ready
    plan = service.generate_plan(sid).plan
    turn = service.submit_feedback(
        sid,
        Feedback(
            plan_id=plan["plan_id"],
            day=1,
            completed=False,
            tolerance="symptoms",
            notes="Unusual dizziness",
        ),
    )
    assert turn.status == "needs_more_info"
    assert service.revise_plan(sid, plan["plan_id"], completed_through=1).plan is None


@pytest.mark.parametrize("calendar", [{"start_date": "2026-02-30"}, {"timezone": "Unknown/City"}])
def test_invalid_calendar(ready, calendar):
    service, sid = ready
    with pytest.raises(IntakeError) as error:
        service.generate_plan(sid, **calendar)
    assert error.value.code == "invalid_calendar"
