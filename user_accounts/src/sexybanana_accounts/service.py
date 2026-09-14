"""Authentication and ownership service independent of HTTP presentation."""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

from .configuration import AccountSettings
from .database import AccountDatabase
from .errors import AccountError, ERROR_MESSAGES
from .models import (
    CurrentPlanResponse,
    PublicPlan,
    PublicUser,
    SessionPrincipal,
    StoredUser,
    new_id,
    utc_now,
)
from .passwords import Passwords


class FitnessService(Protocol):
    def create_session(self, **kwargs): ...
    def get_session(self, session_id: str): ...
    def delete_session(self, session_id: str) -> None: ...
    def update_consent(self, session_id: str, consent, **kwargs): ...
    def get_next_questions(self, session_id: str, **kwargs): ...
    def submit_answers(self, session_id: str, answers, **kwargs): ...
    def evaluate_readiness(self, session_id: str): ...
    def list_sections(self, session_id: str): ...
    def generate_plan(self, session_id: str, **kwargs): ...


MUSCLE_GROUPS = {
    "walk": ["Lower body"],
    "sit_to_stand": ["Quadriceps", "Glutes"],
    "wall_pushup": ["Chest", "Shoulders", "Triceps"],
    "stationary_cycle": ["Lower body"],
    "seated_march": ["Hip flexors", "Core"],
    "band_row": ["Back", "Biceps"],
    "curl": ["Biceps"],
}


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class AccountService:
    """Own account state and gate every fitness resource by authenticated user."""

    def __init__(
        self,
        settings: AccountSettings,
        database: AccountDatabase,
        fitness_service: FitnessService | None = None,
        passwords: Passwords | None = None,
    ):
        self.settings = settings
        self.database = database
        self.fitness_service = fitness_service
        self.passwords = passwords or Passwords()

    @staticmethod
    def normalize_email(email: str) -> str:
        return email.strip().casefold()

    @staticmethod
    def public_user(user: StoredUser) -> PublicUser:
        return PublicUser(id=user.id, email=user.email_normalized, created_at=user.created_at)

    def register(self, email: str, password: str) -> PublicUser:
        timestamp = utc_now()
        user = StoredUser(
            id=new_id("user"),
            email_normalized=self.normalize_email(email),
            password_hash=self.passwords.hash(password),
            created_at=timestamp,
            updated_at=timestamp,
            is_active=True,
        )
        self.database.insert_user(user)
        return self.public_user(user)

    def login(self, email: str, password: str) -> tuple[PublicUser, str, str]:
        user = self.database.user_by_email(self.normalize_email(email))
        valid_password = self.passwords.verify_or_dummy(
            user.password_hash if user is not None else None, password
        )
        if user is None or not valid_password:
            raise AccountError("invalid_credentials", ERROR_MESSAGES["invalid_credentials"], 401)
        if not user.is_active:
            raise AccountError("account_disabled", ERROR_MESSAGES["account_disabled"], 403)
        if self.passwords.needs_rehash(user.password_hash):
            self.database.update_password_hash(user.id, self.passwords.hash(password), utc_now())
        raw_token = secrets.token_urlsafe(32)
        created = datetime.now(timezone.utc)
        expires = created + timedelta(seconds=self.settings.session_lifetime_seconds)
        self.database.insert_auth_session(
            new_id("auth"),
            user.id,
            token_digest(raw_token),
            created.isoformat(),
            expires.isoformat(),
        )
        return self.public_user(user), raw_token, expires.isoformat()

    def authenticate(self, raw_token: str | None) -> SessionPrincipal:
        if not raw_token or len(raw_token) > 512:
            raise AccountError(
                "authentication_required", ERROR_MESSAGES["authentication_required"], 401
            )
        digest = token_digest(raw_token)
        row = self.database.session_with_user(digest)
        if row is None or row["revoked_at"] is not None:
            raise AccountError(
                "authentication_required", ERROR_MESSAGES["authentication_required"], 401
            )
        try:
            expires = datetime.fromisoformat(row["expires_at"])
        except ValueError:
            self.database.delete_session(digest)
            raise AccountError("session_expired", ERROR_MESSAGES["session_expired"], 401) from None
        if expires <= datetime.now(timezone.utc):
            self.database.delete_session(digest)
            raise AccountError("session_expired", ERROR_MESSAGES["session_expired"], 401)
        if not bool(row["is_active"]):
            raise AccountError("account_disabled", ERROR_MESSAGES["account_disabled"], 403)
        return SessionPrincipal(
            user=PublicUser(
                id=row["id"], email=row["email_normalized"], created_at=row["created_at"]
            ),
            session_id=row["session_id"],
            expires_at=row["expires_at"],
        )

    def logout(self, raw_token: str | None) -> None:
        if raw_token and len(raw_token) <= 512:
            self.database.revoke_session(token_digest(raw_token), utc_now())

    def _require_fitness(self) -> FitnessService:
        if self.fitness_service is None:
            raise AccountError("plan_unavailable", ERROR_MESSAGES["plan_unavailable"], 503)
        return self.fitness_service

    def create_fitness_session_for_user(self, user_id: str, **kwargs):
        fitness = self._require_fitness()
        try:
            session = fitness.create_session(**kwargs)
        except AccountError:
            raise
        except Exception as exc:
            code = getattr(exc, "code", "invalid_request")
            raise AccountError(
                code,
                str(exc) or ERROR_MESSAGES["invalid_request"],
                422,
            ) from None
        try:
            self.database.add_fitness_owner(session.session_id, user_id, utc_now())
        except Exception:
            fitness.delete_session(session.session_id)
            raise
        return session

    def claim_fitness_session_for_user(self, user_id: str, fitness_session_id: str) -> None:
        fitness = self._require_fitness()
        try:
            fitness.get_session(fitness_session_id)
        except Exception:
            raise AccountError("not_found", ERROR_MESSAGES["not_found"], 404) from None
        self.database.add_fitness_owner(fitness_session_id, user_id, utc_now())

    def assert_fitness_session_owner(self, user_id: str, fitness_session_id: str) -> None:
        if not self.database.owns_fitness_session(user_id, fitness_session_id):
            raise AccountError("not_found", ERROR_MESSAGES["not_found"], 404)

    def get_fitness_session_for_user(self, user_id: str, fitness_session_id: str):
        self.assert_fitness_session_owner(user_id, fitness_session_id)
        fitness = self._require_fitness()
        try:
            return fitness.get_session(fitness_session_id)
        except Exception:
            raise AccountError("not_found", ERROR_MESSAGES["not_found"], 404) from None

    @staticmethod
    def _fitness_error(exc: Exception, *, default_status: int = 422) -> AccountError:
        code = getattr(exc, "code", "invalid_request")
        status = 409 if code in {"version_conflict", "idempotency_conflict"} else default_status
        return AccountError(code, str(exc) or ERROR_MESSAGES["invalid_request"], status)

    def latest_fitness_session_for_user(self, user_id: str) -> str | None:
        return self.database.latest_fitness_session_for_user(user_id)

    def questionnaire_state_for_user(
        self, user_id: str, fitness_session_id: str
    ) -> dict[str, Any]:
        self.assert_fitness_session_owner(user_id, fitness_session_id)
        fitness = self._require_fitness()
        try:
            questions = fitness.get_next_questions(fitness_session_id, limit=3)
            session = fitness.get_session(fitness_session_id)
            readiness = fitness.evaluate_readiness(fitness_session_id)
            sections = fitness.list_sections(fitness_session_id)
        except Exception as exc:
            raise self._fitness_error(exc) from None
        answered = sum(item.get("answered", 0) for item in sections)
        missing = len(getattr(readiness, "missing", []))
        denominator = max(answered + missing, 1)
        progress = 100 if not questions and readiness.status in {"ready", "limited"} else int(
            min(95, answered * 100 / denominator)
        )
        stage = self._questionnaire_stage(questions, readiness.status)
        return {
            "session_id": session.session_id,
            "version": session.version,
            "profile_version": session.profile_version,
            "stage": stage,
            "progress_percent": progress,
            "questions": [question.model_dump() for question in questions],
            "question_schemas": self._question_schemas(fitness, session, questions),
            "readiness": readiness.model_dump(),
            "sections": sections,
        }

    @staticmethod
    def _questionnaire_stage(questions, readiness_status: str) -> dict[str, Any]:
        if not questions and readiness_status in {"ready", "limited", "emergency"}:
            return {"number": 6, "total": 6, "label": "Review"}
        paths = [question.field_path for question in questions]
        prefixes = {path.split(".", 1)[0] for path in paths}
        if prefixes & {"immediate_screen"}:
            number, label = 2, "Safety"
        elif prefixes & {
            "profile",
            "medical_history",
            "injury_history",
            "function",
            "asymmetry",
            "body_composition",
            "cardiovascular",
            "respiratory",
            "medication_and_exposure",
            "laboratory_reports",
            "reproductive_and_hormonal",
        }:
            number, label = 3, "About You"
        elif prefixes & {"goals_and_constraints"}:
            number, label = 4, "Goals"
        else:
            number, label = 5, "Lifestyle"
        return {"number": number, "total": 6, "label": label}

    @staticmethod
    def _question_schemas(fitness, session, questions) -> dict[str, Any]:
        schemas: dict[str, Any] = {}
        spec = getattr(fitness, "spec", None)
        if spec is None:
            return schemas
        for question in questions:
            try:
                _, _, field = spec.locate(session, question.field_path)
            except Exception:
                continue
            if not field.type.startswith("record:"):
                continue
            record_name = field.type.split(":", 1)[1]
            fields = []
            for name, child in spec.records.get(record_name, {}).items():
                kind, _, enum_name = child.type.partition(":")
                if kind in {"refs", "record", "measurements"}:
                    continue
                options = {}
                if kind in {"enum", "multi"}:
                    options = {
                        key: key.replace("_", " ").capitalize()
                        for key in spec.enums.get(enum_name, [])
                    }
                fields.append(
                    {
                        "name": name,
                        "label": name.replace("_", " ").capitalize(),
                        "type": child.type,
                        "unit": child.unit,
                        "options": options,
                    }
                )
            schemas[question.field_path] = {"record_name": record_name, "fields": fields}
        return schemas

    def submit_questionnaire_answers_for_user(
        self,
        user_id: str,
        fitness_session_id: str,
        answers: dict[str, Any],
        *,
        expected_version: int | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        self.assert_fitness_session_owner(user_id, fitness_session_id)
        fitness = self._require_fitness()
        try:
            fitness.submit_answers(
                fitness_session_id,
                answers,
                expected_version=expected_version,
                request_id=request_id,
            )
        except Exception as exc:
            raise self._fitness_error(exc) from None
        return self.questionnaire_state_for_user(user_id, fitness_session_id)

    def update_fitness_consent_for_user(
        self,
        user_id: str,
        fitness_session_id: str,
        consent: dict[str, Any],
        *,
        expected_version: int | None = None,
    ):
        self.assert_fitness_session_owner(user_id, fitness_session_id)
        fitness = self._require_fitness()
        try:
            return fitness.update_consent(
                fitness_session_id,
                consent,
                expected_version=expected_version,
            )
        except Exception as exc:
            code = getattr(exc, "code", "invalid_request")
            status = 409 if code == "version_conflict" else 422
            raise AccountError(code, str(exc) or ERROR_MESSAGES["invalid_request"], status) from None

    @staticmethod
    def _validate_plan(fitness_session_id: str, plan: dict[str, Any]) -> None:
        if (
            not isinstance(plan, dict)
            or not isinstance(plan.get("plan_id"), str)
            or plan.get("session_id") != fitness_session_id
            or type(plan.get("profile_version")) is not int
            or plan["profile_version"] < 0
            or not isinstance(plan.get("days"), list)
            or len(plan["days"]) != 14
            or [day.get("day") for day in plan["days"] if isinstance(day, dict)]
            != list(range(1, 15))
        ):
            raise AccountError("invalid_request", ERROR_MESSAGES["invalid_request"], 400)

    def save_plan_for_user(
        self, user_id: str, fitness_session_id: str, plan: dict[str, Any]
    ) -> str:
        self.assert_fitness_session_owner(user_id, fitness_session_id)
        self._validate_plan(fitness_session_id, plan)
        existing = self.database.plan_by_fitness_id(user_id, plan["plan_id"])
        if existing is not None:
            return existing["id"]
        record_id = new_id("userplan")
        timestamp = utc_now()
        self.database.insert_plan(
            record_id=record_id,
            user_id=user_id,
            fitness_session_id=fitness_session_id,
            fitness_plan_id=plan["plan_id"],
            profile_version=plan["profile_version"],
            status="stale" if plan.get("stale") else "available",
            plan=plan,
            created_at=timestamp,
        )
        if not plan.get("stale"):
            self.database.mark_other_plans_stale(user_id, record_id)
        return record_id

    def generate_plan_for_user(self, user_id: str, fitness_session_id: str, **kwargs):
        self.assert_fitness_session_owner(user_id, fitness_session_id)
        fitness = self._require_fitness()
        try:
            result = fitness.generate_plan(fitness_session_id, **kwargs)
        except AccountError:
            raise
        except Exception as exc:
            code = getattr(exc, "code", "invalid_request")
            status = 409 if code == "version_conflict" else 400
            raise AccountError(code, str(exc) or ERROR_MESSAGES["invalid_request"], status) from None
        if result.plan is not None:
            self.save_plan_for_user(user_id, fitness_session_id, result.plan)
        return result

    def _fresh_plan_and_feedback(self, row) -> tuple[dict[str, Any], set[int]]:
        plan = json.loads(row["plan_json"])
        completed: set[int] = set()
        if self.fitness_service is None:
            return plan, completed
        try:
            session = self.fitness_service.get_session(row["fitness_session_id"])
        except Exception:
            return plan, completed
        current = next(
            (item for item in session.plans if item.get("plan_id") == row["fitness_plan_id"]),
            None,
        )
        if current is not None:
            plan = current
        completed = {
            item["day"]
            for item in session.feedback
            if item.get("plan_id") == row["fitness_plan_id"] and item.get("completed") is True
        }
        return plan, completed

    @staticmethod
    def _public_plan(row, plan: dict[str, Any], completed: set[int]) -> PublicPlan:
        safe_days: list[dict[str, Any]] = []
        muscle_groups: set[str] = set()
        for day in plan.get("days", []):
            blocks = []
            for block in day.get("blocks", []):
                exercise_id = block.get("exercise_id")
                muscle_groups.update(MUSCLE_GROUPS.get(exercise_id, []))
                blocks.append(
                    {
                        key: block.get(key)
                        for key in (
                            "exercise_id",
                            "name",
                            "phase",
                            "active_minutes",
                            "rest_minutes",
                            "sets",
                            "repetitions",
                            "rpe",
                            "rest_seconds_between_sets",
                            "tempo_seconds_per_rep",
                            "completion_rule",
                            "load_type",
                            "coaching_cues",
                            "equipment",
                            "instructions",
                        )
                    }
                )
            safe_days.append(
                {
                    "day": day.get("day"),
                    "date": day.get("date"),
                    "kind": day.get("kind"),
                    "objective": day.get("objective"),
                    "total_minutes": day.get("total_minutes", 0),
                    "completed": day.get("day") in completed,
                    "blocks": blocks,
                }
            )
        training = [day for day in safe_days if day["kind"] == "training"]
        next_day = next((day for day in training if not day["completed"]), None)
        start = plan.get("start_date")
        end = None
        if isinstance(start, str):
            try:
                end = (datetime.fromisoformat(start).date() + timedelta(days=13)).isoformat()
            except ValueError:
                end = None
        goals = plan.get("goals") if isinstance(plan.get("goals"), list) else []
        objective = ", ".join(str(goal).replace("_", " ").title() for goal in goals)
        if not objective:
            objective = "Two-week fitness plan"
        next_title = None
        if next_day:
            main = next((b for b in next_day["blocks"] if b["phase"] == "main"), None)
            next_title = main.get("name") if main else f"Training day {next_day['day']}"
        return PublicPlan(
            id=row["id"],
            fitness_plan_id=row["fitness_plan_id"],
            fitness_session_id=row["fitness_session_id"],
            source_profile_version=row["source_profile_version"],
            stale=bool(plan.get("stale")) or row["status"] == "stale",
            start_date=start,
            end_date=end,
            timezone=plan.get("timezone"),
            objective=objective,
            summary={
                "duration_days": len(safe_days),
                "training_days": len(training),
                "rest_days": len(safe_days) - len(training),
                "completed_days": len(completed),
                "next_training_day": next_day["day"] if next_day else None,
                "next_session_title": next_title,
                "next_session_minutes": next_day["total_minutes"] if next_day else None,
                "target_muscle_groups": sorted(muscle_groups),
            },
            days=safe_days,
            generated_at=plan.get("generated_at", row["created_at"]),
        )

    def get_plan_for_user(self, user_id: str, record_id: str) -> PublicPlan:
        row = self.database.plan_for_user(user_id, record_id)
        if row is None:
            raise AccountError("not_found", ERROR_MESSAGES["not_found"], 404)
        plan, completed = self._fresh_plan_and_feedback(row)
        return self._public_plan(row, plan, completed)

    def get_current_plan_for_user(self, user_id: str) -> CurrentPlanResponse:
        row = self.database.latest_plan_for_user(user_id)
        if row is None:
            return CurrentPlanResponse(status="none", plan=None)
        plan, completed = self._fresh_plan_and_feedback(row)
        public = self._public_plan(row, plan, completed)
        if public.stale:
            status = "stale"
        elif public.end_date and datetime.now(timezone.utc).date() > datetime.fromisoformat(
            public.end_date
        ).date():
            status = "expired"
        else:
            status = "available"
        return CurrentPlanResponse(status=status, plan=public)

    def list_plans_for_user(self, user_id: str) -> list[PublicPlan]:
        result = []
        for row in self.database.plans_for_user(user_id):
            plan, completed = self._fresh_plan_and_feedback(row)
            result.append(self._public_plan(row, plan, completed))
        return result

    def delete_user_data(self, user_id: str) -> None:
        """Delete component-owned fitness sessions, then cascade account-owned records."""
        fitness_session_ids = self.database.fitness_sessions_for_user(user_id)
        if self.fitness_service is not None:
            for session_id in fitness_session_ids:
                self.fitness_service.delete_session(session_id)
        self.database.delete_user(user_id)
