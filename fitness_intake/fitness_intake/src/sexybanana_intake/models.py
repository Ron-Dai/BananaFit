"""Public data contracts; domain-specific field validation lives in specification.py."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

Status = Literal[
    "answered", "not_asked", "unknown", "not_measured", "declined", "not_applicable", "invalid"
]
ReadinessStatus = Literal["ready", "limited", "needs_more_info", "needs_review", "emergency"]


def now() -> str:
    """Return an aware UTC timestamp, never a fabricated observation timestamp."""
    return datetime.now(timezone.utc).isoformat()


def identifier(kind: str) -> str:
    """Generate a typed UUID identifier."""
    return f"{kind}_{uuid4().hex}"


class Model(BaseModel):
    """Reject undocumented fields and implicit type coercion at public boundaries."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class MeasurementMetadata(Model):
    observed_at: str = "unknown"
    date_precision: Literal["day", "month", "year", "approximate", "unknown"] = "unknown"
    original_value: Any = None
    original_unit: str = "unknown"
    method: str = "unknown"
    device: dict[str, Any] = Field(
        default_factory=lambda: {
            "manufacturer": "unknown",
            "model": "unknown",
            "software_version": "unknown",
            "algorithm_version": "unknown",
            "calibration_date": "unknown",
        }
    )
    setting: str | dict[str, Any] = "unknown"
    quality: Literal["unknown", "acceptable_per_documented_protocol", "limited", "invalid"] = (
        "unknown"
    )
    assessor: str = "unknown"
    preparation: dict[str, Any] = Field(default_factory=dict)
    protocol: str | dict[str, Any] = "unknown"
    context: dict[str, Any] = Field(default_factory=dict)
    estimate: dict[str, Any] = Field(default_factory=dict)
    quality_reason: str = ""
    reference: dict[str, Any] = Field(default_factory=dict)


class Answer(Model):
    answer_id: str = Field(default_factory=lambda: identifier("answer"))
    status: Status = "not_asked"
    value: Any = None
    unit: str | None = None
    original_text: str | None = None
    answered_at: str | None = None
    observed_at: str | None = None
    date_precision: Literal["day", "month", "year", "approximate", "unknown"] = "unknown"
    source_type: Literal[
        "self_report",
        "clinician_report",
        "supervised_measurement",
        "home_measurement",
        "wearable",
        "derived",
        "other",
        "unknown",
    ] = "unknown"
    source_detail: str = ""
    note: str = ""
    report_refs: list[str] = Field(default_factory=list)
    related_record_ids: list[str] = Field(default_factory=list)
    history: list[dict[str, Any]] = Field(default_factory=list)
    validation: Literal[
        "unchecked", "user_confirmed", "source_checked", "inconsistent", "invalid"
    ] = "unchecked"
    measurement_metadata: MeasurementMetadata | None = None
    other_text: str = ""
    attachment_refs: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_status(self) -> Answer:
        """Enforce missingness without converting unknown into a negative answer."""
        if self.status != "answered" and self.value is not None:
            raise ValueError("Only answered responses may contain a value.")
        if self.status == "answered" and self.value is None:
            raise ValueError("An answered response must contain a value.")
        return self


class Consent(Model):
    external_ai: bool = False
    sensitive_sections: list[str] = Field(default_factory=list)
    attachments: bool = False
    purpose: str = "Fitness intake and fourteen-day planning"
    recorded_at: str = Field(default_factory=now)


class Constraint(Model):
    """Host-reviewed interpretation; not a medical clearance or an LLM output."""

    source_answer_ids: list[str]
    reviewed_by: str
    allowed_exercise_ids: list[str]
    max_rpe: float = Field(default=4.0, ge=0, le=6)
    max_session_minutes: float | None = Field(default=None, gt=0)
    max_days_per_week: int | None = Field(default=None, ge=0, le=7)
    professional_scope: bool = False
    note: str = ""


class Session(Model):
    session_id: str = Field(default_factory=lambda: identifier("session"))
    participant_id: str = Field(default_factory=lambda: identifier("participant"))
    spec_id: str
    spec_version: str
    format_version: str = "1.0"
    version: int = 0
    profile_version: int = 0
    created_at: str = Field(default_factory=now)
    updated_at: str = Field(default_factory=now)
    language: Literal["en"] = "en"
    consent: Consent = Field(default_factory=Consent)
    responses: dict[str, dict[str, Answer]]
    audit_history: list[dict[str, Any]] = Field(default_factory=list)
    derived_results: list[dict[str, Any]] = Field(default_factory=list)
    constraints: list[Constraint] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)
    pending: dict[str, dict[str, Any]] = Field(default_factory=dict)
    requests: dict[str, str] = Field(default_factory=dict)
    broken_references: dict[str, str] = Field(default_factory=dict)
    plans: list[dict[str, Any]] = Field(default_factory=list)
    feedback: list[dict[str, Any]] = Field(default_factory=list)
    summary: dict[str, Any] | None = None
    needs_update: bool = False


class Question(Model):
    question_id: str
    field_path: str
    text: str
    answer_type: str
    unit: str | None = None
    options: dict[str, str] = Field(default_factory=dict)
    allowed_statuses: list[str] = Field(
        default_factory=lambda: [
            "answered",
            "unknown",
            "not_measured",
            "declined",
            "not_applicable",
        ]
    )
    reason: str = "Optional information relevant to your training."


class Flag(Model):
    rule_id: str
    description: str
    severity: Literal[
        "emergency",
        "prompt_professional_review",
        "clarification_needed",
        "adaptation_needed",
        "monitoring_note",
    ]
    answer_ids: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    next_step: str
    resolved: bool = False


class Readiness(Model):
    status: ReadinessStatus
    flags: list[Flag]
    missing: list[dict[str, Any]]
    allowed_exercise_ids: list[str]
    planning_scope: str
    max_rpe: float = 4.0
    max_minutes: float = 0.0
    max_days: int = 0
    rule_states: dict[str, Literal["triggered", "not_triggered", "indeterminate"]] = Field(
        default_factory=dict
    )


class ExerciseBlock(Model):
    exercise_id: str
    phase: Literal["warmup", "main", "cooldown"]
    active_minutes: float = Field(gt=0, le=120)
    rest_minutes: float = Field(default=0.0, ge=0, le=30)
    sets: int | None = Field(default=None, ge=1, le=5)
    repetitions: int | None = Field(default=None, ge=1, le=30)
    rpe: float = Field(ge=0, le=6)
    rest_seconds_between_sets: int | None = Field(default=None, ge=0, le=600)
    tempo_seconds_per_rep: float | None = Field(default=None, ge=2, le=8)
    completion_rule: Literal["repetitions", "duration"] | None = None
    load_type: Literal[
        "bodyweight", "none", "resistance_band", "familiar_comfortable"
    ] | None = None
    coaching_cues: list[str] = Field(default_factory=list, max_length=4)


class PlanDay(Model):
    day: int = Field(ge=1, le=14)
    kind: Literal["training", "rest", "recovery"]
    preparation_minutes: float = Field(default=0.0, ge=0, le=30)
    title: str | None = Field(default=None, min_length=1, max_length=80)
    focus: list[str] = Field(default_factory=list, max_length=4)
    blocks: list[ExerciseBlock] = Field(default_factory=list)


class CandidatePlan(Model):
    days: list[PlanDay] = Field(min_length=14, max_length=14)


class PlanResult(Model):
    status: ReadinessStatus
    readiness: Readiness
    plan: dict[str, Any] | None = None


class TurnResult(Model):
    session_id: str
    version: int
    status: ReadinessStatus
    questions: list[Question] = Field(default_factory=list)
    pending: dict[str, dict[str, Any]] = Field(default_factory=dict)
    flags: list[Flag] = Field(default_factory=list)
    message: str = ""


class Feedback(Model):
    plan_id: str
    day: int = Field(ge=1, le=14)
    completed: bool
    tolerance: Literal["comfortable", "too_hard", "symptoms", "unknown"]
    notes: str = ""
    recorded_at: str = Field(default_factory=now)
    answer_updates: dict[str, Any] = Field(default_factory=dict)
