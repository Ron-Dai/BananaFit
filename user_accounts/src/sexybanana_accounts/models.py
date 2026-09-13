"""Strict request, persistence, and public-response models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class RegisterRequest(StrictModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=256)
    password_confirmation: str = Field(min_length=1, max_length=256)

    @field_validator("password")
    @classmethod
    def password_quality(cls, value: str) -> str:
        if value.strip() != value or not any(c.isalpha() for c in value) or not any(
            c.isdigit() for c in value
        ):
            raise ValueError("Password must include letters and numbers and have no edge spaces.")
        return value

    @model_validator(mode="after")
    def matching_passwords(self):
        if self.password != self.password_confirmation:
            raise ValueError("Password confirmation does not match.")
        return self


class LoginRequest(StrictModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class ConsentRequest(StrictModel):
    external_ai: bool = False
    sensitive_sections: list[str] = Field(default_factory=list, max_length=32)
    attachments: bool = False
    purpose: str = Field(
        default="Fitness intake and fourteen-day planning",
        min_length=1,
        max_length=200,
    )


class CreateIntakeSessionRequest(StrictModel):
    consent: ConsentRequest = Field(default_factory=ConsentRequest)


class UpdateConsentRequest(StrictModel):
    consent: ConsentRequest
    expected_version: int | None = Field(default=None, ge=0)


class AnswerInput(StrictModel):
    status: Literal["answered", "unknown", "not_measured", "declined", "not_applicable"]
    value: Any = None
    unit: str | None = Field(default=None, max_length=40)
    source_type: Literal["self_report"] = "self_report"
    note: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def status_matches_value(self):
        if self.status == "answered" and self.value is None:
            raise ValueError("An answered value is required.")
        if self.status != "answered" and self.value is not None:
            raise ValueError("Missingness statuses cannot include a value.")
        return self


class SubmitAnswersRequest(StrictModel):
    answers: dict[str, AnswerInput] = Field(min_length=1, max_length=3)
    expected_version: int | None = Field(default=None, ge=0)
    request_id: str | None = Field(default=None, min_length=8, max_length=128)

    @field_validator("answers")
    @classmethod
    def safe_answer_paths(cls, value: dict[str, AnswerInput]):
        for path in value:
            if (
                len(path) > 160
                or path.startswith(".")
                or path.endswith(".")
                or any(not part.replace("_", "").isalnum() for part in path.split("."))
            ):
                raise ValueError("An answer field path is invalid.")
        return value


class GeneratePlanRequest(StrictModel):
    start_date: str | None = None
    timezone: str | None = None
    expected_version: int | None = Field(default=None, ge=0)


class PublicUser(StrictModel):
    id: str
    email: str
    created_at: str


class StoredUser(StrictModel):
    id: str
    email_normalized: str
    password_hash: str
    created_at: str
    updated_at: str
    is_active: bool


class SessionPrincipal(StrictModel):
    user: PublicUser
    session_id: str
    expires_at: str


class PlanSummary(StrictModel):
    duration_days: int
    training_days: int
    rest_days: int
    completed_days: int
    next_training_day: int | None
    next_session_title: str | None
    next_session_minutes: float | None
    target_muscle_groups: list[str]


class PublicPlan(StrictModel):
    id: str
    fitness_plan_id: str
    fitness_session_id: str
    source_profile_version: int
    stale: bool
    start_date: str | None
    end_date: str | None
    objective: str
    summary: PlanSummary
    days: list[dict[str, Any]]
    generated_at: str


class CurrentPlanResponse(StrictModel):
    status: Literal["available", "none", "stale"]
    plan: PublicPlan | None
