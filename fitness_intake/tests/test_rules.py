"""All twelve required YAML behavior cases, plus branch and readiness boundaries."""

import pytest

from sexybanana_intake import Answer, FitnessIntakeService
from sexybanana_intake.metrics import paired_metrics
from sexybanana_intake.models import MeasurementMetadata
from sexybanana_intake.rules import EMERGENCY_FIELDS, branch_targets


def measurement(value, construct="grip_strength", method="dynamometer", day="2026-09-12"):
    return Answer(
        status="answered",
        value=value,
        unit="kg",
        source_type="supervised_measurement",
        validation="user_confirmed",
        measurement_metadata=MeasurementMetadata(
            original_value=value,
            original_unit="kg",
            method=method,
            observed_at=day,
            date_precision="day",
            device={"model": "fictional"},
            setting="seated, elbow at 90 degrees",
            reference={"construct": construct},
        ),
    )


def paired(a, left, right, construct="grip_strength"):
    return {
        "left": left,
        "right": right,
        "construct": a(construct),
        "region_task": a("hand grip"),
        "protocol": a("same protocol"),
    }


def test_case_01_bodyfat_unmeasured_continues(ready):
    service, sid = ready
    assert (
        service.get_session(sid).responses["body_composition"]["body_fat_percent"].status
        == "not_measured"
    )
    assert service.generate_plan(sid).status == "ready"


def test_case_02_bodyfat_does_not_replace_declined_screen(ready):
    service, sid = ready
    service.update_answer(
        sid, "immediate_screen.current_chest_discomfort", Answer(status="declined")
    )
    result = service.generate_plan(sid)
    assert result.plan is None and result.status == "needs_more_info"


def test_case_03_incomparable_constructs(a):
    results = paired_metrics(
        paired(a, measurement(30, "lean_soft_tissue"), measurement(25, "skeletal_muscle"))
    )
    assert all(x["value"] is None for x in results)


def test_case_04_grip_difference_descriptive(a):
    results = paired_metrics(paired(a, measurement(30), measurement(25)))
    assert [x["value"] for x in results[:2]] == [-5, 5]
    assert results[2]["value"] == pytest.approx(16.6666666667)
    assert "not a diagnosis" in results[2]["interpretation"]


@pytest.mark.parametrize(
    "left,right",
    [(measurement(0), measurement(0)), (measurement(30), Answer(status="not_measured"))],
)
def test_case_05_zero_or_missing(a, left, right):
    assert paired_metrics(paired(a, left, right))[2]["value"] is None


def test_case_06_old_surgery_not_emergency(ready, a):
    service, sid = ready
    service.update_answer(sid, "injury_history.ever_injury_or_surgery", a(True))
    service.submit_answers(
        sid,
        {
            "injury_history.injuries": a(
                [
                    {
                        "event_name": a("Old surgery"),
                        "onset_date": a("2009"),
                        "current_function": a("Normal daily function without symptoms"),
                        "trajectory": a("resolved"),
                    }
                ]
            )
        },
    )
    result = service.generate_plan(sid)
    assert result.plan is not None
    assert not any(f.severity == "emergency" for f in result.readiness.flags)


@pytest.mark.parametrize("field", EMERGENCY_FIELDS)
def test_cases_07_08_acute_warning_interrupts(ready, a, field):
    service, sid = ready
    calls = service.provider.calls
    service.update_answer(sid, "immediate_screen." + field, a(True))
    result = service.generate_plan(sid)
    assert result.status == "emergency" and result.plan is None
    assert service.provider.calls == calls
    assert service.get_next_questions(sid) == []
    assert "911" not in str(result.model_dump())


def test_case_09_pem_no_fixed_progression(ready, a):
    service, sid = ready
    service.update_answer(sid, "nutrition_recovery.delayed_exacerbation", a(True))
    result = service.generate_plan(sid)
    assert result.status == "needs_review" and result.plan is None
    assert any(f.rule_id == "R07" for f in result.readiness.flags)


def test_case_10_medication_no_age_only_hr_zones(ready, a):
    service, sid = ready
    service.update_answer(
        sid,
        "medication_and_exposure.medications",
        a(
            [
                {
                    "name": a("Fictional prescribed heart-rate-affecting medication"),
                    "exercise_instructions": a(
                        "Existing advice: use perceived effort, no heart-rate prescription"
                    ),
                }
            ]
        ),
    )
    result = service.generate_plan(sid)
    assert any(f.rule_id == "R08" for f in result.readiness.flags)
    assert result.plan is not None
    assert all("heart_rate" not in b for d in result.plan["days"] for b in d["blocks"])


def test_case_11_normal_measurement_does_not_negate_symptoms(ready, a):
    service, sid = ready
    service.submit_answers(
        sid,
        {
            "cardiovascular.resting_heart_rate": a(
                [{"status": "answered", "value": 60, "unit": "bpm"}]
            )
        },
    )
    service.update_answer(sid, "immediate_screen.current_chest_discomfort", a(True))
    assert service.generate_plan(sid).status == "emergency"


def test_case_12_correction_invalidates_calculations_and_plan(ready, a):
    service, sid = ready
    service.submit_answers(
        sid, {"asymmetry.paired_observations": a([paired(a, measurement(30), measurement(25))])}
    )
    plan = service.generate_plan(sid).plan
    summary = service.build_summary(sid)
    assert summary["asymmetry_summary"]["calculations"][1]["value"] == 5
    record = service.get_session(sid).responses["asymmetry"]["paired_observations"].value[0]
    path = "asymmetry.paired_observations." + record["record_id"] + ".right"
    service.update_answer(sid, path, measurement(28))
    current = service.get_session(sid)
    assert current.summary is None and current.derived_results == []
    assert current.plans[0]["plan_id"] == plan["plan_id"] and current.plans[0]["stale"]
    assert service.build_summary(sid)["asymmetry_summary"]["calculations"][1]["value"] == 2
    assert (
        record["right"].answer_id
        == service.get_session(sid)
        .responses["asymmetry"]["paired_observations"]
        .value[0]["right"]
        .answer_id
    )


def test_source_restriction_cannot_expire_itself(ready, a):
    service, sid = ready
    service.update_answer(
        sid,
        "medical_history.professional_restrictions",
        a(
            [
                {
                    "original_instruction": a("Avoid weight bearing until review"),
                    "expires_or_review": a("2020-01-01"),
                }
            ]
        ),
    )
    assert service.generate_plan(sid).status == "needs_review"


def test_declined_not_repeated_and_modules_accessible(a):
    service = FitnessIntakeService(questions_per_turn=1)
    sid = service.create_session().session_id
    first = service.get_next_questions(sid)[0]
    service.submit_message(sid, "skip")
    assert service.get_next_questions(sid)[0].field_path != first.field_path
    assert len(service.list_sections(sid)) == 17
    assert (
        service.get_next_questions(sid, section="immediate_screen", reopen=True)[0].field_path
        == first.field_path
    )


def test_stale_screening_requires_new_confirmation(ready):
    service, sid = ready
    old = service.get_session(sid).responses["immediate_screen"]["current_chest_discomfort"]
    old.answered_at = "2001-01-01T00:00:00+00:00"
    service.update_answer(sid, "immediate_screen.current_chest_discomfort", old)
    assert service.evaluate_readiness(sid).status == "needs_more_info"


def test_all_branch_handlers_are_executable(ready, a):
    service, sid = ready
    updates = {
        "medical_history.condition_screen.diabetes": a(True),
        "injury_history.ever_injury_or_surgery": a(True),
        "asymmetry.noticed_difference": a(True),
        "nutrition_recovery.delayed_exacerbation": a(True),
        "nutrition_recovery.orthostatic_intolerance": a(True),
        "function.activities.walk": a("assistance"),
        "reproductive_and_hormonal.relevance": a(True),
        "profile.height": Answer(status="declined"),
    }
    for path, answer in updates.items():
        service.update_answer(sid, path, answer)
    service.update_answer(
        sid, "medication_and_exposure.medications", a([{"name": a("Fictional medication")}])
    )
    service.submit_answers(
        sid, {"reports_and_update.reports": a([{"type_title": a("Fictional report")}])}
    )
    # B11 is about critical unknown/refused data.
    service.update_answer(sid, "profile.age", Answer(status="unknown"))
    assert set(branch_targets(service.get_session(sid))) == {f"B{i:02}" for i in range(1, 13)}


def test_explicit_emergency_free_text_works_without_provider():
    service = FitnessIntakeService()
    sid = service.create_session().session_id
    turn = service.submit_message(sid, "I have chest pain now")
    assert turn.status == "emergency"
    assert (
        service.get_session(sid).responses["immediate_screen"]["current_chest_discomfort"].status
        == "not_asked"
    )


def test_minor_does_not_get_adult_template(ready, a):
    service, sid = ready
    service.update_answer(sid, "profile.age", a(15))
    assert service.generate_plan(sid).status == "needs_review"
