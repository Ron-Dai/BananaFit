"""Application-facing APIs that compose accounts, plans, workouts, and camera state."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Request

from sexybanana_accounts.csrf import validate_csrf
from sexybanana_accounts.errors import ERROR_MESSAGES, AccountError

from .exercise_bridge import present_block


def _load_dataset(path: Path) -> dict[str, dict]:
    with path.open(encoding="utf-8") as handle:
        return {item["id"]: item for item in json.load(handle)}


def create_controller_router(account_service, metrics_store, workout_store, root: Path) -> APIRouter:
    router = APIRouter()
    dataset = _load_dataset(root / "frontend" / "public" / "data" / "exercises.json")

    def principal(request: Request):
        return account_service.authenticate(
            request.cookies.get(account_service.settings.cookie_name)
        )

    def current(user_id: str):
        result = account_service.get_current_plan_for_user(user_id)
        if result.plan is None:
            return result, None, None
        plan = result.plan
        try:
            zone = ZoneInfo(plan.timezone or "UTC")
        except ZoneInfoNotFoundError:
            zone = ZoneInfo("UTC")
        today_iso = datetime.now(zone).date().isoformat()
        day = next((item for item in plan.days if item.get("date") == today_iso), None)
        return result, plan, day

    @router.get("/api/app/bootstrap")
    def bootstrap(request: Request) -> dict:
        actor = principal(request)
        result, plan, day = current(actor.user.id)
        return {
            "authenticated": True,
            "user": actor.user.model_dump(),
            "plan_status": result.status,
            "today": _today(plan, day, dataset) if plan else None,
        }

    @router.get("/api/app/today")
    def today(request: Request) -> dict:
        actor = principal(request)
        result, plan, day = current(actor.user.id)
        if plan is None:
            return {"status": result.status, "plan": None, "day": None}
        return {"status": result.status, "plan_id": plan.id, "day": _today(plan, day, dataset)}

    @router.get("/api/app/calendar")
    def calendar(request: Request) -> dict:
        actor = principal(request)
        result, plan, _day = current(actor.user.id)
        if plan is None:
            return {"status": result.status, "start_date": None, "end_date": None, "days": []}
        try:
            zone = ZoneInfo(plan.timezone or "UTC")
        except ZoneInfoNotFoundError:
            zone = ZoneInfo("UTC")
        today_iso = datetime.now(zone).date().isoformat()
        return {
            "status": result.status,
            "start_date": plan.start_date,
            "end_date": plan.end_date,
            "days": [
                {
                    "day": item.get("day"),
                    "date": item.get("date"),
                    "kind": item.get("kind"),
                    "completed": bool(item.get("completed")),
                    "today": item.get("date") == today_iso,
                }
                for item in plan.days
            ],
        }

    @router.get("/api/app/personal")
    def personal(request: Request) -> dict:
        actor = principal(request)
        result, plan, day = current(actor.user.id)
        if plan is None or day is None:
            return {"status": result.status, "workout": None, "exercises": []}
        return {
            "status": result.status,
            "workout": {"plan_id": plan.id, "day": day.get("day"), "date": day.get("date")},
            "exercises": [present_block(block, dataset) for block in day.get("blocks", [])],
        }

    @router.post("/api/workouts/today/start")
    def start_today(request: Request) -> dict:
        validate_csrf(request, account_service.settings)
        actor = principal(request)
        _result, plan, day = current(actor.user.id)
        if plan is None or day is None or day.get("kind") != "training":
            raise AccountError("plan_unavailable", ERROR_MESSAGES["plan_unavailable"], 409)
        workout = workout_store.start(actor.user.id, plan.id, day)
        return {
            "workout": workout,
            "launch_url": f"/?page=exercises&tab=personal&workout={workout['id']}",
        }

    @router.get("/api/workouts/{workout_id}")
    def workout(workout_id: str, request: Request) -> dict:
        actor = principal(request)
        record = workout_store.for_user(actor.user.id, workout_id)
        if record is None:
            raise AccountError("not_found", ERROR_MESSAGES["not_found"], 404)
        return {"workout": record}

    @router.get("/api/coach/metrics")
    def coach_metrics() -> dict:
        return metrics_store.snapshot()

    return router


def _today(plan, day: dict | None, dataset: dict[str, dict]) -> dict | None:
    if day is None:
        return None
    exercises = [present_block(block, dataset) for block in day.get("blocks", [])]
    completed = 1 if day.get("completed") else 0
    return {
        "plan_id": plan.id,
        "plan_day": day.get("day"),
        "date": day.get("date"),
        "kind": day.get("kind"),
        "objective": day.get("objective") or plan.objective,
        "total_minutes": day.get("total_minutes") or 0,
        "completed": bool(day.get("completed")),
        "completed_count": completed * len(exercises),
        "exercise_count": len(exercises),
        "exercises": exercises,
    }
