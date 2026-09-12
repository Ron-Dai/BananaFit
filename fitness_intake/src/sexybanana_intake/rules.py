"""Explicit B01-B12 and R01-R13 logic; these are not validated medical triage rules."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from .catalog import CATALOG, equipment_from_text, excluded_activities, weekday_availability
from .models import Answer, Flag, Readiness, Session
from .specification import Specification

EMERGENCY_FIELDS = [
    "current_chest_discomfort",
    "severe_rest_dyspnea",
    "current_fainting_or_confusion",
    "sudden_focal_neurology",
    "new_saddle_sensation_change",
    "new_bladder_bowel_control_change",
    "new_bilateral_leg_neurology",
]
SCREEN_FIELDS = EMERGENCY_FIELDS + ["major_trauma_or_rapid_pain", "current_fever_or_acute_illness"]
CORE_PATHS = [
    *("immediate_screen." + key for key in SCREEN_FIELDS),
    "medical_history.professional_restrictions",
    "medical_history.conditions",
    "medical_history.symptoms",
    "injury_history.ever_injury_or_surgery",
    "injury_history.current_pain_regions",
    "function.movement_limits",
    "profile.age",
    "nutrition_recovery.delayed_exacerbation",
    "nutrition_recovery.orthostatic_intolerance",
    "medication_and_exposure.medications",
    "goals_and_constraints.goals",
    "goals_and_constraints.days_per_week",
    "goals_and_constraints.session_duration",
    "goals_and_constraints.time_preferences",
    "goals_and_constraints.equipment",
    "goals_and_constraints.preferences",
    "activity_history.current_activities",
    "activity_history.training_history",
    "activity_history.exercise_adverse_history",
    "reports_and_update.unmentioned_factors",
]
SYSTEM_PATHS = {
    "profile.participant_id",
    "immediate_screen.screen_time",
    "reports_and_update.reviewed_at",
}


def usable(answer: Answer) -> bool:
    """Only current valid answers can support decisions; missingness is never negative."""
    return answer.status == "answered" and answer.validation not in {"invalid", "inconsistent"}


def get(session: Session, path: str) -> Answer:
    """Read a top-level or matrix answer, returning a nonpersistent unknown placeholder."""
    parts = path.split(".")
    answer = session.responses[parts[0]][parts[1]]
    if len(parts) == 3:
        return (
            answer.value.get(parts[2], Answer())
            if usable(answer) and isinstance(answer.value, dict)
            else Answer()
        )
    return answer


def value(session: Session, path: str, default: Any = None) -> Any:
    """Read an answer value only when its status and verification permit use."""
    answer = get(session, path)
    return answer.value if usable(answer) else default


def records(session: Session, path: str) -> list[dict]:
    """Return known repeated records without treating an unknown field as an empty answer."""
    return value(session, path, [])


def rv(record: dict, key: str, default: Any = None) -> Any:
    """Read a record child without inferring meaning from missing values."""
    answer = record.get(key)
    return answer.value if isinstance(answer, Answer) and usable(answer) else default


def branch_targets(session: Session) -> dict[str, list[str]]:
    """Resolve B01-B12 into follow-up targets; never create unreported diagnoses."""
    positive_conditions = any(
        usable(a) and a.value is True
        for a in value(session, "medical_history.condition_screen", {}).values()
    )
    symptoms = bool(records(session, "medical_history.symptoms")) or any(
        usable(a) and a.value is True
        for a in value(session, "medical_history.symptom_screen", {}).values()
    )
    injury = (
        value(session, "injury_history.ever_injury_or_surgery") is True
        or bool(records(session, "medical_history.hospitalization_events"))
        or bool(records(session, "injury_history.injuries"))
    )
    difference = value(session, "asymmetry.noticed_difference") is True or bool(
        records(session, "asymmetry.paired_observations")
    )
    difficult = any(
        usable(a) and a.value not in ("none", "unknown")
        for a in value(session, "function.activities", {}).values()
    )
    cardio = (
        any(value(session, "immediate_screen." + key) is True for key in SCREEN_FIELDS[:3])
        or value(session, "nutrition_recovery.orthostatic_intolerance") is True
        or any(
            value(session, "medical_history.symptom_screen." + key) is True
            for key in ["chest_discomfort", "breathlessness", "palpitations", "faintness"]
        )
    )
    definitions = {
        "B01": (positive_conditions, ["medical_history.conditions"]),
        "B02": (injury, ["injury_history.injuries", "injury_history.persistent_impairments"]),
        "B03": (
            symptoms
            or difference
            or bool(value(session, "injury_history.current_pain_regions", [])),
            ["medical_history.symptoms"],
        ),
        "B04": (difference, ["asymmetry.differences", "asymmetry.paired_observations"]),
        "B05": (
            any(
                records(session, p)
                for p in [
                    "medication_and_exposure.medications",
                    "medication_and_exposure.supplements",
                    "injury_history.implants_and_aids",
                ]
            ),
            ["medication_and_exposure.recent_changes", "injury_history.implants_and_aids"],
        ),
        "B06": (
            cardio,
            [
                "medical_history.professional_restrictions",
                "medical_history.symptoms",
                "cardiovascular.resting_heart_rate",
            ],
        ),
        "B07": (
            value(session, "nutrition_recovery.delayed_exacerbation") is True,
            ["nutrition_recovery.delayed_exacerbation_details"],
        ),
        "B08": (difficult, ["function.movement_limits", "function.assistance_required"]),
        "B09": (
            value(session, "reproductive_and_hormonal.relevance") is True
            or any(
                value(session, p)
                for p in [
                    "reproductive_and_hormonal.pregnancy_status",
                    "reproductive_and_hormonal.postpartum_details",
                    "nutrition_recovery.possible_underfueling",
                ]
            ),
            [
                "reproductive_and_hormonal.pregnancy_status",
                "reproductive_and_hormonal.pregnancy_complications",
                "nutrition_recovery.possible_underfueling",
            ],
        ),
        "B10": (
            bool(records(session, "reports_and_update.reports")),
            ["reports_and_update.reports"],
        ),
        "B11": (any(get(session, p).status in {"unknown", "declined"} for p in CORE_PATHS), []),
        "B12": (session.needs_update, ["reports_and_update.changes_since_last"]),
    }
    return {rule: targets for rule, (triggered, targets) in definitions.items() if triggered}


def evaluate(session: Session, spec: Specification, screen_max_age_hours: float = 24) -> Readiness:
    """Evaluate current facts deterministically; unknown or unsupported scopes remain explicit."""
    flags: list[Flag] = []
    missing: list[dict] = []
    states = {f"R{i:02}": "indeterminate" for i in range(1, 14)}
    all_answers = list(spec.walk(session))
    by_id = {a.answer_id: a for _, _, a in all_answers}

    def add(rule: str, severity: str, description: str, paths: list[str], next_step: str):
        ids = [get(session, p).answer_id for p in paths]
        flags.append(
            Flag(
                rule_id=rule,
                severity=severity,
                description=description,
                answer_ids=ids,
                evidence=paths,
                next_step=next_step,
            )
        )
        states[rule] = "triggered"

    def need(path: str, reason: str, decision: str = "Initial training scope"):
        answer = get(session, path)
        missing.append(
            {
                "field_path": path,
                "reason": reason,
                "status": answer.status,
                "affected_decision": decision,
                "voluntary": True,
            }
        )

    for path in CORE_PATHS:
        if not usable(get(session, path)):
            need(path, "This decision-relevant answer is unavailable or invalid.")
    emergency = [
        "immediate_screen." + key
        for key in EMERGENCY_FIELDS
        if value(session, "immediate_screen." + key) is True
    ]
    # Structured symptom records supplement, but never override, immediate screening.
    for record in records(session, "medical_history.symptoms"):
        regions = rv(record, "region", [])
        sudden = rv(record, "onset_type") == "sudden"
        current = rv(record, "current") is True
        text = str(rv(record, "name", "")).lower()
        focal = rv(record, "side") in {"left", "right"} and any(
            x in text for x in ["weakness", "numbness", "speech", "vision"]
        )
        onset = str(rv(record, "onset_date", ""))
        historical = False
        try:
            historical = (
                int(onset[:4]) < date.today().year - 1
                and rv(record, "trend") in {"stable", "resolved"}
                and rv(record, "current") is False
            )
        except ValueError:
            pass
        if (sudden and focal and not historical) or (
            current
            and not historical
            and ("chest" in regions or "chest" in text)
            and any(x in text for x in ["pain", "pressure", "tightness"])
        ):
            emergency.append("medical_history.symptoms")
    if emergency:
        add(
            "R01",
            "emergency",
            "Current or recent acute warning information was reported; no new exercise or testing recommendations can be issued.",
            emergency,
            "Stop new exercise and seek local emergency or emergency-department assessment immediately. Do not wait to finish this intake.",
        )
    elif all(usable(get(session, "immediate_screen." + key)) for key in EMERGENCY_FIELDS):
        states["R01"] = "not_triggered"

    urgent = [
        "immediate_screen." + k
        for k in ["major_trauma_or_rapid_pain", "current_fever_or_acute_illness"]
        if value(session, "immediate_screen." + k) is True
    ]
    symptoms = records(session, "medical_history.symptoms")
    concerning_symptoms = any(
        rv(r, "trend") == "worsening"
        or rv(r, "current") is True
        or (
            "exercise" in rv(r, "contexts", [])
            and any(k in str(rv(r, "name", "")).lower() for k in ["chest", "faint"])
        )
        for r in symptoms
    )
    positive_symptoms = any(
        usable(a) and a.value is True
        for a in value(session, "medical_history.symptom_screen", {}).values()
    )
    if urgent or concerning_symptoms:
        add(
            "R02",
            "prompt_professional_review",
            "A current illness, concerning symptom, or recent trauma needs assessment before dependent load decisions.",
            urgent or ["medical_history.symptoms"],
            "Clarify current status and obtain appropriate professional assessment; escalate acute warning symptoms immediately.",
        )
    elif positive_symptoms:
        add(
            "R02",
            "clarification_needed",
            "A symptom-screen item is positive and needs its timing and current relevance clarified.",
            ["medical_history.symptom_screen"],
            "Add a symptom record with current status, onset, triggers, and existing assessment.",
        )
    else:
        states["R02"] = (
            "not_triggered" if usable(get(session, "medical_history.symptoms")) else "indeterminate"
        )

    conditions = records(session, "medical_history.conditions")
    positive_conditions = any(
        usable(a) and a.value is True
        for a in value(session, "medical_history.condition_screen", {}).values()
    )
    if conditions or positive_conditions or records(session, "medical_history.prior_screening"):
        stable = bool(conditions) and all(
            rv(r, "current_control") in {"stable_as_reported", "resolved"}
            and rv(r, "exercise_effect") is not None
            for r in conditions
        )
        add(
            "R03",
            "monitoring_note" if stable and not positive_symptoms else "clarification_needed",
            "Existing conditions or screening results require context; their labels do not establish a blanket exercise prohibition.",
            ["medical_history.conditions", "medical_history.prior_screening"],
            "Confirm current control, symptoms, habitual activity, intended intensity, and original screening follow-up.",
        )
    else:
        states["R03"] = (
            "not_triggered"
            if usable(get(session, "medical_history.conditions"))
            else "indeterminate"
        )

    valid_constraints = [
        c
        for c in session.constraints
        if c.source_answer_ids and all(i in by_id and usable(by_id[i]) for i in c.source_answer_ids)
    ]
    covered = {i for c in valid_constraints for i in c.source_answer_ids}
    restrictions = records(session, "medical_history.professional_restrictions")
    if restrictions:
        unresolved = [r for r in restrictions if r["original_instruction"].answer_id not in covered]
        add(
            "R04",
            "prompt_professional_review" if unresolved else "adaptation_needed",
            "Professional wording is preserved; an explicit reviewed activity scope is required for machine validation.",
            ["medical_history.professional_restrictions"],
            "Have the host record a reviewed interpretation tied to the original instruction. Expiry alone does not remove a restriction.",
        )
    else:
        states["R04"] = (
            "not_triggered"
            if usable(get(session, "medical_history.professional_restrictions"))
            else "indeterminate"
        )
    if (
        value(session, "asymmetry.noticed_difference") is True
        or records(session, "asymmetry.differences")
        or records(session, "asymmetry.paired_observations")
    ):
        add(
            "R05",
            "monitoring_note",
            "Left-right observations require comparable constructs, methods, conditions, and uncertainty; no automatic weaker-side extra volume.",
            ["asymmetry.paired_observations", "asymmetry.differences"],
            "Describe differences without diagnosing a cause or applying universal percentage cutoffs.",
        )
    worsening = value(session, "asymmetry.progressive_wasting_or_weakness") is True or any(
        rv(r, "trend") == "worsening"
        for r in records(session, "injury_history.persistent_impairments")
    )
    if worsening:
        add(
            "R06",
            "prompt_professional_review",
            "Progressive weakness, thinning, or functional decline needs assessment.",
            ["asymmetry.progressive_wasting_or_weakness", "injury_history.persistent_impairments"],
            "Clarify onset and associated symptoms with a professional; acute focal changes follow R01.",
        )
    if value(session, "nutrition_recovery.delayed_exacerbation") is True:
        professional = any(
            c.professional_scope
            and get(session, "nutrition_recovery.delayed_exacerbation").answer_id
            in c.source_answer_ids
            for c in valid_constraints
        )
        add(
            "R07",
            "adaptation_needed" if professional else "prompt_professional_review",
            "Delayed whole-body worsening was reported. No automatic progression or maximal testing is permitted.",
            ["nutrition_recovery.delayed_exacerbation"],
            "Discuss triggers and recovery with an appropriate professional and follow the existing individualized management plan.",
        )
    elif value(session, "nutrition_recovery.delayed_exacerbation") is False:
        states["R07"] = "not_triggered"

    medications = records(session, "medication_and_exposure.medications")
    special = []
    age = value(session, "profile.age")
    if age is not None and age < 18:
        special.append("profile.age")
    for path in [
        "reproductive_and_hormonal.pregnancy_status",
        "reproductive_and_hormonal.postpartum_details",
        "reproductive_and_hormonal.pregnancy_complications",
    ]:
        raw = value(session, path)
        if raw and str(raw).lower().strip() not in {"no", "none", "not pregnant", "not applicable"}:
            special.append(path)
    if (
        medications
        or special
        or value(session, "nutrition_recovery.orthostatic_intolerance") is True
    ):
        reviewed_special = all(
            any(
                c.professional_scope and get(session, p).answer_id in c.source_answer_ids
                for c in valid_constraints
            )
            for p in special
        )
        severity = (
            "prompt_professional_review" if special and not reviewed_special else "monitoring_note"
        )
        if value(session, "nutrition_recovery.orthostatic_intolerance") is True:
            severity = "prompt_professional_review"
        add(
            "R08",
            severity,
            "Medication or physiological context changes planning assumptions. Age-only heart-rate targets and medication changes are not supported.",
            ["medication_and_exposure.medications", *special],
            "Use an applicable professional scope for special populations; verify actual medication instructions without changing treatment.",
        )
        for record in medications:
            if rv(record, "name") is None or rv(record, "exercise_instructions") is None:
                need(
                    "medication_and_exposure.medications",
                    "Medication name and existing exercise instructions need clarification.",
                )

    measurements = [(p, a) for p, f, a in all_answers if f.type == "measurement" and usable(a)]
    if measurements:
        add(
            "R09",
            "monitoring_note",
            "Measurement constructs and device estimates remain distinct; normal-looking values do not negate symptoms.",
            list(dict.fromkeys(".".join(p.split(".")[:2]) for p, _ in measurements)),
            "Check dates, units, methods, and quality before interpretation or comparison.",
        )
    issues = [
        (p, a)
        for p, _, a in all_answers
        if a.status == "invalid" or a.issues or a.validation == "inconsistent"
    ]
    for p, a in issues:
        missing.append(
            {
                "field_path": p,
                "reason": "; ".join(a.issues) or "Invalid or inconsistent evidence",
                "status": a.status,
                "affected_decision": "Dependent calculations and recommendations",
                "voluntary": True,
            }
        )
    # A paired blood pressure record does not become valid merely because each number parsed.
    for r in records(session, "cardiovascular.blood_pressure"):
        systolic, diastolic = rv(r, "systolic"), rv(r, "diastolic")
        if (systolic is None) != (diastolic is None) or (
            systolic is not None and diastolic is not None and diastolic >= systolic
        ):
            issues.append(
                ("cardiovascular.blood_pressure", get(session, "cardiovascular.blood_pressure"))
            )
            need(
                "cardiovascular.blood_pressure",
                "Confirm paired same-occasion readings and original report; relationship is incomplete or inconsistent.",
                "Blood-pressure interpretation",
            )
    if issues:
        add(
            "R10",
            "clarification_needed",
            "Some input or measurement metadata requires verification; raw evidence is retained.",
            list(dict.fromkeys(".".join(p.split(".")[:2]) for p, _ in issues)),
            "Correct the specific field or verify its source. Measurement checks must not delay emergency action.",
        )
    for record in records(session, "laboratory_reports.blood_tests"):
        wording = str(rv(record, "report_interpretation", "")).lower()
        if "critical" in wording and not any(
            term in wording for term in ["not critical", "no critical"]
        ):
            add(
                "R10",
                "prompt_professional_review",
                "The supplied report describes a critical result; no numeric threshold was inferred by this component.",
                ["laboratory_reports.blood_tests"],
                "Follow the report's professional instructions promptly; current emergency symptoms still follow R01.",
            )
    if session.broken_references:
        add(
            "R10",
            "monitoring_note",
            "Some linked evidence was withdrawn or replaced; broken-link reasons remain recorded.",
            ["reports_and_update.user_corrections"],
            "Do not use withdrawn reference targets as current evidence.",
        )

    impairments = records(session, "injury_history.persistent_impairments")
    if (
        impairments
        or records(session, "injury_history.implants_and_aids")
        or records(session, "function.movement_limits")
    ):
        add(
            "R11",
            "adaptation_needed",
            "Functional differences require activity-specific adaptation; a diagnostic label alone does not determine ability.",
            ["injury_history.persistent_impairments", "function.movement_limits"],
            "Use demonstrated daily function, assistance, and reviewed professional restrictions to select compatible activities.",
        )
    if session.needs_update:
        add(
            "R12",
            "monitoring_note",
            "Answers changed; dependent summaries, constraints, and plans need reevaluation.",
            ["reports_and_update.user_corrections", "reports_and_update.changes_since_last"],
            "Rebuild current results while preserving previously issued and executed plans.",
        )

    if value(session, "injury_history.ever_injury_or_surgery") is True:
        injuries = records(session, "injury_history.injuries")
        if not injuries or any(
            rv(r, "current_function") is None or rv(r, "trajectory") is None for r in injuries
        ):
            need(
                "injury_history.injuries",
                "Clarify each event's current function and trajectory; elapsed time alone does not establish recovery.",
            )
    elif value(session, "injury_history.ever_injury_or_surgery") is False and records(
        session, "injury_history.injuries"
    ):
        need(
            "injury_history.ever_injury_or_surgery",
            "The negative injury-history answer conflicts with supplied injury records.",
        )
        add(
            "R10",
            "clarification_needed",
            "Injury-history answers conflict; neither is silently discarded.",
            ["injury_history.ever_injury_or_surgery", "injury_history.injuries"],
            "Correct the conflicting answer before planning.",
        )
    if symptoms and any(rv(r, "current") is None or rv(r, "onset_type") is None for r in symptoms):
        need("medical_history.symptoms", "Clarify current status and onset for each symptom.")
    for path in [
        "activity_history.exercise_adverse_history",
        "goals_and_constraints.preferences",
        "goals_and_constraints.time_preferences",
        "reports_and_update.unmentioned_factors",
    ]:
        text = value(session, path)
        if (
            text
            and path.endswith("exercise_adverse_history")
            and str(text).lower().strip() not in {"none", "no", "no adverse reactions"}
            and not symptoms
        ):
            need(
                "medical_history.symptoms",
                "Describe reported exercise reactions before making dependent decisions.",
            )
        if (
            text
            and path.endswith("unmentioned_factors")
            and str(text).lower().strip() not in {"none", "no", "nothing else", "no other factors"}
            and get(session, path).answer_id not in covered
        ):
            need(
                path,
                "Clarify the additional reported factor and record a reviewed planning scope; it cannot be ignored.",
            )

    # Freshness is a configurable product policy, not a medical-validity guarantee.
    for key in SCREEN_FIELDS:
        answer = get(session, "immediate_screen." + key)
        if usable(answer):
            try:
                stamp = datetime.fromisoformat(answer.answered_at or "")
                age_hours = (datetime.now(timezone.utc) - stamp).total_seconds() / 3600
                if age_hours < 0 or age_hours > screen_max_age_hours:
                    raise ValueError
            except (ValueError, TypeError):
                need(
                    "immediate_screen." + key,
                    "Current symptom confirmation is stale or lacks a valid timezone.",
                )

    equipment = equipment_from_text(str(value(session, "goals_and_constraints.equipment", "")))
    if (
        usable(get(session, "goals_and_constraints.time_preferences"))
        and weekday_availability(str(value(session, "goals_and_constraints.time_preferences", "")))
        is None
    ):
        need(
            "goals_and_constraints.time_preferences",
            "List available weekday names positively, or say 'any day'; the current schedule wording is ambiguous.",
        )
    allowed = []
    for exercise_id, activity in CATALOG.items():
        functional = all(
            value(session, "function.activities." + task) == "none"
            for task in activity["functions"]
        )
        if set(activity["equipment"]) <= equipment and functional:
            allowed.append(exercise_id)
    # Unstructured current pain/movement limits need reviewed scope rather than guesswork.
    for path in [
        "injury_history.current_pain_regions",
        "function.movement_limits",
        "injury_history.persistent_impairments",
    ]:
        if value(session, path) and get(session, path).answer_id not in covered:
            allowed = []
            need(
                path,
                "Record an explicit reviewed activity scope for current pain or functional limitations.",
                "Selection of unaffected activities",
            )
    professional_scopes = [c for c in valid_constraints if c.professional_scope]
    if professional_scopes and all(
        not value(session, p) or get(session, p).answer_id in covered
        for p in [
            "injury_history.current_pain_regions",
            "function.movement_limits",
            "injury_history.persistent_impairments",
        ]
    ):
        allowed = [
            key
            for key in CATALOG
            if set(CATALOG[key]["equipment"]) <= equipment
            and key in professional_scopes[0].allowed_exercise_ids
        ]
    for constraint in valid_constraints:
        # Multiple scopes always intersect. A later scope cannot undo an earlier exclusion.
        allowed = [key for key in allowed if key in constraint.allowed_exercise_ids]
    excluded = excluded_activities(str(value(session, "goals_and_constraints.preferences", "")))
    allowed = [key for key in allowed if key not in excluded]
    if not allowed and not any(flag.severity == "emergency" for flag in flags):
        need(
            "function.activities",
            "No activity yet has a sufficiently established functional and equipment scope.",
            "Activity selection",
        )
    for p in session.pending:
        need(
            ".".join(p.split(".")[:2]),
            "A model extraction or clarification is pending user confirmation.",
        )
    minutes = float(value(session, "goals_and_constraints.session_duration", 0))
    days = int(value(session, "goals_and_constraints.days_per_week", 0))
    max_rpe = 4.0
    for constraint in valid_constraints:
        max_rpe = min(max_rpe, constraint.max_rpe)
        if constraint.max_session_minutes is not None:
            minutes = min(minutes, constraint.max_session_minutes)
        if constraint.max_days_per_week is not None:
            days = min(days, constraint.max_days_per_week)
    if days == 0 or minutes < 5:
        need(
            "goals_and_constraints.session_duration",
            "A training plan requires available training days and at least five minutes per session; adjust availability voluntarily.",
        )
    blocking_flags = [f for f in flags if f.severity in {"emergency", "prompt_professional_review"}]
    if any(f.severity == "emergency" for f in blocking_flags):
        status = "emergency"
    elif blocking_flags:
        status = "needs_review"
    elif any(
        f.rule_id in {"R02", "R03"} and f.severity == "clarification_needed" for f in flags
    ) or any(
        m["affected_decision"] != "Dependent calculations and recommendations"
        and m["affected_decision"] != "Blood-pressure interpretation"
        for m in missing
    ):
        status = "needs_more_info"
    else:
        status = (
            "limited"
            if conditions
            or valid_constraints
            or any(f.severity == "adaptation_needed" for f in flags)
            else "ready"
        )
    if missing:
        states["R13"] = "triggered"
        add(
            "R13",
            "clarification_needed" if status == "needs_more_info" else "monitoring_note",
            "Information sufficiency is assessed per decision; unmeasured optional body composition does not block all planning.",
            ["goals_and_constraints.goals"],
            "Review the listed affected decisions; supplying missing health information remains voluntary.",
        )
    else:
        states["R13"] = "not_triggered"
    scope = "A conservative introductory fitness plan using only the established activity scope; no maximal loading, diagnosis, or medical clearance."
    if status not in {"ready", "limited"}:
        scope = "No new training plan is available until the specified issues are resolved. Existing factual information can still be discussed."
    return Readiness(
        status=status,
        flags=flags,
        missing=missing,
        allowed_exercise_ids=allowed,
        planning_scope=scope,
        max_rpe=max_rpe,
        max_minutes=minutes,
        max_days=days,
        rule_states=states,
    )
