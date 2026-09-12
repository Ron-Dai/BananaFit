"""Candidate schedules, deterministic plan validation, and English rendering."""

from __future__ import annotations

import copy
import html
from datetime import date, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import ValidationError

from .catalog import CATALOG, equipment_from_text, weekday_availability
from .errors import IntakeError
from .models import CandidatePlan, Readiness, Session, identifier, now
from .rules import get, value


def training_days(
    session: Session, readiness: Readiness, start_date: str | None = None
) -> list[int]:
    """Select a feasible repeated weekly schedule from explicit weekday availability."""
    available = weekday_availability(
        str(value(session, "goals_and_constraints.time_preferences", ""))
    )
    if available is None:
        raise IntakeError("invalid_calendar", "Clarify available weekdays before scheduling.")
    count = min(readiness.max_days, len(available), 4)
    selected = {available[(i * len(available)) // count] for i in range(count)} if count else set()
    offset = date.fromisoformat(start_date).weekday() if start_date else 0
    return [day for day in range(1, 15) if (offset + day - 1) % 7 in selected]


def plan_contract(
    session: Session, readiness: Readiness, start_date: str | None, timezone: str | None
) -> dict:
    """Build the model's bounded schedule contract; reject ambiguous calendar input."""
    try:
        if start_date:
            date.fromisoformat(start_date)
        if timezone:
            ZoneInfo(timezone)
    except (ValueError, ZoneInfoNotFoundError):
        raise IntakeError(
            "invalid_calendar", "Use an ISO start date and a valid IANA timezone."
        ) from None
    return {
        "schema": CandidatePlan.model_json_schema(),
        "allowed_exercise_ids": readiness.allowed_exercise_ids,
        "training_days": training_days(session, readiness, start_date),
        "max_minutes": readiness.max_minutes,
        "max_rpe": readiness.max_rpe,
        "max_days_per_week": readiness.max_days,
        "catalog": {key: CATALOG[key] for key in readiness.allowed_exercise_ids},
        "week_two_rule": "No automatic increase in activity minutes or peak RPE before feedback.",
    }


def validate_candidate(
    raw: dict, session: Session, readiness: Readiness, contract: dict
) -> CandidatePlan:
    """Reject invalid shapes, impossible schedules, unsupported activities, or excess loads."""
    try:
        candidate = CandidatePlan.model_validate(raw)
    except ValidationError:
        raise IntakeError(
            "invalid_plan", "The candidate does not match the strict fourteen-day plan schema."
        ) from None
    if [day.day for day in candidate.days] != list(range(1, 15)):
        raise IntakeError(
            "invalid_plan",
            "Plan days must be ordered 1 through 14 without omissions or duplicates.",
        )
    training = [day.day for day in candidate.days if day.kind == "training"]
    if training != contract["training_days"]:
        raise IntakeError("invalid_plan", "The training schedule does not match available days.")
    equipment = equipment_from_text(str(value(session, "goals_and_constraints.equipment", "")))
    minutes = [0.0, 0.0]
    peak = [0.0, 0.0]
    for day in candidate.days:
        fixed = {item["day"]: item for item in contract.get("fixed_past_days", [])}
        if day.day in fixed:
            if day.model_dump() != fixed[day.day]:
                raise IntakeError("invalid_plan", "Executed history cannot be changed.")
            for block in day.blocks:
                minutes[(day.day - 1) // 7] += block.active_minutes
                peak[(day.day - 1) // 7] = max(peak[(day.day - 1) // 7], block.rpe)
            continue
        if day.kind != "training":
            if day.blocks or day.preparation_minutes != 0:
                raise IntakeError(
                    "invalid_plan",
                    "Rest and recovery days cannot conceal extra prescribed exercise.",
                )
            continue
        phases = [block.phase for block in day.blocks]
        if not phases or phases[0] != "warmup" or phases[-1] != "cooldown" or "main" not in phases:
            raise IntakeError(
                "invalid_plan", "Training days require warm-up, main work, and cool-down."
            )
        order = {"warmup": 0, "main": 1, "cooldown": 2}
        if phases != sorted(phases, key=order.get):
            raise IntakeError("invalid_plan", "Exercise phases are out of order.")
        total = day.preparation_minutes
        for block in day.blocks:
            if block.exercise_id not in readiness.allowed_exercise_ids:
                raise IntakeError(
                    "invalid_plan", "A candidate activity is outside the established scope."
                )
            activity = CATALOG[block.exercise_id]
            if not set(activity["equipment"]) <= equipment or block.rpe > readiness.max_rpe:
                raise IntakeError(
                    "invalid_plan", "The candidate exceeds equipment or intensity constraints."
                )
            if block.phase != "main" and block.rpe > min(2.0, readiness.max_rpe):
                raise IntakeError(
                    "invalid_plan", "Warm-up and cool-down must remain at easy effort."
                )
            if activity["category"] == "strength" and block.phase == "main":
                if (
                    block.sets is None
                    or block.repetitions is None
                    or block.active_minutes * 60 < block.sets * block.repetitions * 2
                    or block.active_minutes * 60 > block.sets * block.repetitions * 8
                ):
                    raise IntakeError(
                        "invalid_plan",
                        "Strength blocks need sets, repetitions, and enough active time.",
                    )
            total += block.active_minutes + block.rest_minutes
            minutes[(day.day - 1) // 7] += block.active_minutes
            peak[(day.day - 1) // 7] = max(peak[(day.day - 1) // 7], block.rpe)
        if total > readiness.max_minutes + 1e-8 or total <= 0:
            raise IntakeError(
                "invalid_plan",
                "Session duration exceeds the available total including preparation and rest.",
            )
    if minutes[1] > minutes[0] + 1e-8 or peak[1] > peak[0] + 1e-8:
        raise IntakeError(
            "invalid_plan", "Week 2 must not progress automatically without feedback."
        )
    return candidate


def normalize_strength_timing(raw: dict, max_minutes: float | None = None) -> dict:
    """Normalize model timing arithmetic without adding exercise or intensity."""
    candidate = copy.deepcopy(raw)
    days = candidate.get("days") if isinstance(candidate, dict) else None
    if not isinstance(days, list):
        return candidate
    for day in days:
        if not isinstance(day, dict) or not isinstance(day.get("blocks"), list):
            continue
        for block in day["blocks"]:
            if not isinstance(block, dict) or block.get("phase") != "main":
                continue
            activity = CATALOG.get(block.get("exercise_id"))
            sets = block.get("sets")
            repetitions = block.get("repetitions")
            active = block.get("active_minutes")
            rest = block.get("rest_minutes", 0.0)
            if (
                not activity
                or activity["category"] != "strength"
                or type(sets) is not int
                or type(repetitions) is not int
                or sets <= 0
                or repetitions <= 0
                or type(active) not in (int, float)
                or type(rest) not in (int, float)
                or active <= sets * repetitions * 8 / 60
            ):
                continue
            repetition_time = sets * repetitions * 4 / 60
            block["active_minutes"] = repetition_time
            block["rest_minutes"] = rest + active - repetition_time
        if max_minutes is None or day.get("kind") != "training":
            continue
        preparation = day.get("preparation_minutes", 0.0)
        if type(preparation) not in (int, float):
            continue
        numeric_blocks = [
            block
            for block in day["blocks"]
            if isinstance(block, dict)
            and type(block.get("active_minutes")) in (int, float)
            and type(block.get("rest_minutes", 0.0)) in (int, float)
        ]
        if len(numeric_blocks) != len(day["blocks"]):
            continue
        total = preparation + sum(
            block["active_minutes"] + block.get("rest_minutes", 0.0)
            for block in numeric_blocks
        )
        excess = max(0.0, total - max_minutes)
        # Models commonly include all between-set recovery in a strength block's
        # duration. Shorten that proposed recovery first while preserving the work.
        for block in numeric_blocks:
            if excess <= 1e-8:
                break
            rest = block.get("rest_minutes", 0.0)
            reduction = min(rest, excess)
            block["rest_minutes"] = rest - reduction
            excess -= reduction
    return candidate


def finalize(
    candidate: CandidatePlan,
    session: Session,
    readiness: Readiness,
    provider: str,
    start_date: str | None,
    timezone: str | None,
) -> dict:
    """Attach provenance and trusted instructions to a validated candidate."""
    basis_paths = [
        "goals_and_constraints.goals",
        "goals_and_constraints.session_duration",
        "goals_and_constraints.days_per_week",
        "goals_and_constraints.equipment",
        "medical_history.professional_restrictions",
        "function.activities",
    ]
    goals = value(session, "goals_and_constraints.goals", [])
    plan = {
        "plan_id": identifier("plan"),
        "version": len(session.plans) + 1,
        "session_id": session.session_id,
        "profile_version": session.profile_version,
        "spec_version": session.spec_version,
        "generated_at": now(),
        "provider": provider,
        "prompt_version": "1.0",
        "start_date": start_date,
        "timezone": timezone,
        "day_one_weekday": date.fromisoformat(start_date).strftime("%A")
        if start_date
        else "Monday (relative schedule anchor; no calendar date assumed)",
        "duration_days": 14,
        "scope": readiness.planning_scope,
        "goals": goals,
        "basis_answer_ids": [get(session, p).answer_id for p in basis_paths],
        "constraints": [c.model_dump() for c in session.constraints],
        "uncertainties": readiness.missing,
        "stale": False,
        "days": [],
        "reassessment": [
            "New symptoms, injury, medication changes, or changed functional ability require a fresh assessment before continuing.",
            "For new acute warning symptoms, stop new exercise and seek local emergency assessment.",
            "Stop or reduce activity if discomfort, unusual fatigue, dizziness, or delayed whole-body worsening occurs; record it and request reassessment.",
        ],
        "week_two_condition": "Use Week 2 only if Week 1 remained comfortable without new symptoms or delayed worsening. Otherwise pause and submit feedback. There is no automatic progression.",
        "review_days": [7, 14],
        "feedback_questions": [
            "What was completed?",
            "Was effort comfortable or too hard?",
            "Any symptoms during, immediately after, or the next day?",
            "Any changes in medication, restrictions, equipment, or available time?",
        ],
    }
    for day in candidate.days:
        item = day.model_dump()
        item["date"] = (
            (date.fromisoformat(start_date) + timedelta(days=day.day - 1)).isoformat()
            if start_date
            else None
        )
        item["total_minutes"] = round(
            day.preparation_minutes + sum(b.active_minutes + b.rest_minutes for b in day.blocks), 4
        )
        item["objective"] = (
            "Practice tolerated movement and observe recovery."
            if day.kind == "training"
            else "Rest and observe recovery; no additional exercise target."
        )
        item["conditional"] = day.day > 7
        for block in item["blocks"]:
            activity = CATALOG[block["exercise_id"]]
            block.update(
                {
                    "name": activity["name"],
                    "instructions": activity["instructions"],
                    "equipment": activity["equipment"],
                    "intensity_scale": "RPE 0-10",
                    "load_guidance": "No specific external load is prescribed. Use only a familiar, comfortable load where applicable.",
                    "alternatives": [
                        x
                        for x in readiness.allowed_exercise_ids
                        if x != block["exercise_id"]
                        and CATALOG[x]["category"] == activity["category"]
                    ],
                    "adaptation": "Use only the already established comfortable range and reviewed scope; request reassessment if an adaptation is unclear.",
                }
            )
        plan["days"].append(item)
    return plan


def render_plan_markdown(plan: dict) -> str:
    """Render a validated plan without regenerating advice or executing embedded HTML."""

    def safe(text: object) -> str:
        return html.escape(str(text)).replace("\n", " ").replace("|", "\\|")

    lines = [
        "# Two-week fitness plan",
        "",
        f"Plan: `{plan['plan_id']}` · Version {plan['version']} · Provider: {safe(plan['provider'])}",
        "",
        safe(plan["scope"]),
        "",
        "Goals: " + ", ".join(safe(x) for x in plan["goals"]),
        "",
        safe(plan["week_two_condition"]),
        "",
        f"Schedule anchor: {safe(plan['day_one_weekday'])}",
    ]
    if plan["provider"] == "offline_fake":
        lines[2:2] = ["**Fictional offline demonstration. No external AI model was called.**", ""]
    if plan.get("stale"):
        lines += ["", "**This plan is outdated and must be reassessed before further use.**"]
    for day in plan["days"]:
        lines += [
            "",
            f"## Day {day['day']} — {day['kind'].title()}"
            + (f" ({day['date']})" if day["date"] else ""),
            "",
            f"{safe(day['objective'])} Total: {day['total_minutes']:g} minutes, including preparation and rest.",
        ]
        if day["blocks"]:
            lines += [
                "",
                "| Phase | Activity | Active min | Rest min | Sets × reps | RPE (0–10) |",
                "| --- | --- | ---: | ---: | --- | ---: |",
            ]
            for b in day["blocks"]:
                dose = f"{b['sets']} × {b['repetitions']}" if b["sets"] else "Time-based"
                lines.append(
                    f"| {b['phase']} | {safe(b['name'])} | {b['active_minutes']:g} | {b['rest_minutes']:g} | {dose} | {b['rpe']:g} |"
                )
            lines += [
                "",
                *[
                    f"- {safe(b['name'])}: {safe(b['instructions'])}"
                    for b in day["blocks"]
                    if b["phase"] == "main"
                ],
            ]
        if day["day"] in [7, 14]:
            lines += ["", "Review: " + " ".join(plan["feedback_questions"])]
    lines += ["", "## Stop and reassess", "", *["- " + safe(x) for x in plan["reassessment"]]]
    return "\n".join(lines) + "\n"
