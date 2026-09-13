"""FastAPI pages and APIs for accounts and user-owned workout plans."""

from __future__ import annotations

import json
from importlib.resources import files
from typing import Any

from fastapi import APIRouter, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import ValidationError

from .configuration import AccountSettings
from .csrf import new_csrf_token, validate_csrf
from .errors import AccountError, ERROR_MESSAGES
from .models import (
    CreateIntakeSessionRequest,
    GeneratePlanRequest,
    LoginRequest,
    RegisterRequest,
    SessionPrincipal,
    UpdateConsentRequest,
)
from .service import AccountService


def _resource_text(directory: str, filename: str) -> str:
    return files("sexybanana_accounts").joinpath(directory, filename).read_text(encoding="utf-8")


async def _json_object(request: Request) -> dict[str, Any]:
    try:
        body = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise AccountError("invalid_request", ERROR_MESSAGES["invalid_request"], 400) from None
    if not isinstance(body, dict):
        raise AccountError("invalid_request", ERROR_MESSAGES["invalid_request"], 400)
    return body


async def _optional_json_object(request: Request) -> dict[str, Any]:
    if not await request.body():
        return {}
    return await _json_object(request)


def _register_request(body: dict[str, Any]) -> RegisterRequest:
    try:
        return RegisterRequest.model_validate(body)
    except ValidationError as exc:
        locations = {tuple(item["loc"]) for item in exc.errors()}
        messages = " ".join(item["msg"].lower() for item in exc.errors())
        if ("email",) in locations:
            code = "invalid_email"
        elif "confirmation" in messages or "match" in messages:
            code = "password_mismatch"
        elif any(loc and loc[0] == "password" for loc in locations):
            code = "weak_password"
        else:
            code = "invalid_request"
        raise AccountError(code, ERROR_MESSAGES[code], 422) from None


def _login_request(body: dict[str, Any]) -> LoginRequest:
    try:
        return LoginRequest.model_validate(body)
    except ValidationError:
        raise AccountError("invalid_credentials", ERROR_MESSAGES["invalid_credentials"], 401) from None


def _principal(request: Request, service: AccountService) -> SessionPrincipal:
    return service.authenticate(request.cookies.get(service.settings.cookie_name))


def _set_session_cookie(response: Response, settings: AccountSettings, token: str) -> None:
    response.set_cookie(
        settings.cookie_name,
        token,
        max_age=settings.session_lifetime_seconds,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


def create_router(service: AccountService) -> APIRouter:
    """Create an inert router; the caller explicitly mounts it on a FastAPI app."""
    router = APIRouter()
    settings = service.settings

    @router.get("/login", response_class=HTMLResponse, include_in_schema=False)
    def login_page() -> HTMLResponse:
        return HTMLResponse(_resource_text("templates", "login.html"))

    @router.get("/register", response_class=HTMLResponse, include_in_schema=False)
    def register_page() -> HTMLResponse:
        return HTMLResponse(_resource_text("templates", "register.html"))

    @router.get("/auth-static/auth.css", include_in_schema=False)
    def auth_css() -> Response:
        return Response(_resource_text("static", "auth.css"), media_type="text/css")

    @router.get("/auth-static/auth.js", include_in_schema=False)
    def auth_js() -> Response:
        return Response(_resource_text("static", "auth.js"), media_type="text/javascript")

    @router.get("/api/auth/csrf")
    def csrf_token() -> JSONResponse:
        token = new_csrf_token()
        response = JSONResponse({"csrf_token": token})
        response.set_cookie(
            f"{settings.cookie_name}_csrf",
            token,
            max_age=3600,
            httponly=False,
            secure=settings.cookie_secure,
            samesite="lax",
            path="/",
        )
        return response

    @router.post("/api/auth/register", status_code=201)
    async def register(request: Request) -> JSONResponse:
        validate_csrf(request, settings)
        submitted = _register_request(await _json_object(request))
        user = service.register(str(submitted.email), submitted.password)
        _, token, expires_at = service.login(str(submitted.email), submitted.password)
        response = JSONResponse(
            {
                "authenticated": True,
                "user": user.model_dump(),
                "expires_at": expires_at,
                "redirect_url": settings.app_url,
            },
            status_code=201,
        )
        _set_session_cookie(response, settings, token)
        return response

    @router.post("/api/auth/login")
    async def login(request: Request) -> JSONResponse:
        validate_csrf(request, settings)
        submitted = _login_request(await _json_object(request))
        user, token, expires_at = service.login(str(submitted.email), submitted.password)
        response = JSONResponse(
            {
                "authenticated": True,
                "user": user.model_dump(),
                "expires_at": expires_at,
                "redirect_url": settings.app_url,
            }
        )
        _set_session_cookie(response, settings, token)
        return response

    @router.post("/api/auth/logout")
    def logout(request: Request) -> JSONResponse:
        validate_csrf(request, settings)
        service.logout(request.cookies.get(settings.cookie_name))
        response = JSONResponse({"authenticated": False})
        response.delete_cookie(settings.cookie_name, path="/")
        return response

    @router.get("/api/auth/me")
    def me(request: Request) -> dict:
        principal = _principal(request, service)
        return {"authenticated": True, "user": principal.user.model_dump()}

    @router.post("/api/intake/sessions", status_code=201)
    async def create_intake_session(request: Request) -> dict:
        validate_csrf(request, settings)
        principal = _principal(request, service)
        try:
            submitted = CreateIntakeSessionRequest.model_validate(
                await _optional_json_object(request)
            )
        except ValidationError:
            raise AccountError(
                "invalid_request", ERROR_MESSAGES["invalid_request"], 422
            ) from None
        session = service.create_fitness_session_for_user(
            principal.user.id,
            consent=submitted.consent.model_dump(),
        )
        return {"session_id": session.session_id, "version": session.version}

    @router.post("/api/intake/sessions/{fitness_session_id}/consent")
    async def update_intake_consent(fitness_session_id: str, request: Request) -> dict:
        validate_csrf(request, settings)
        principal = _principal(request, service)
        try:
            submitted = UpdateConsentRequest.model_validate(await _json_object(request))
        except ValidationError:
            raise AccountError(
                "invalid_request", ERROR_MESSAGES["invalid_request"], 422
            ) from None
        session = service.update_fitness_consent_for_user(
            principal.user.id,
            fitness_session_id,
            submitted.consent.model_dump(),
            expected_version=submitted.expected_version,
        )
        return {
            "session_id": session.session_id,
            "version": session.version,
            "consent": session.consent.model_dump(),
        }

    @router.post("/api/intake/sessions/{fitness_session_id}/generate-plan")
    async def generate_plan(fitness_session_id: str, request: Request) -> dict:
        validate_csrf(request, settings)
        principal = _principal(request, service)
        try:
            submitted = GeneratePlanRequest.model_validate(await _json_object(request))
        except ValidationError:
            raise AccountError(
                "invalid_request", ERROR_MESSAGES["invalid_request"], 422
            ) from None
        result = service.generate_plan_for_user(
            principal.user.id,
            fitness_session_id,
            start_date=submitted.start_date,
            timezone=submitted.timezone,
            expected_version=submitted.expected_version,
        )
        current = service.get_current_plan_for_user(principal.user.id)
        return {
            "status": result.status,
            "readiness": result.readiness.model_dump(),
            "current_plan": current.model_dump(),
        }

    @router.get("/api/intake/sessions/{fitness_session_id}")
    def get_intake_session(fitness_session_id: str, request: Request) -> dict:
        principal = _principal(request, service)
        session = service.get_fitness_session_for_user(
            principal.user.id, fitness_session_id
        )
        if hasattr(session, "model_dump"):
            return session.model_dump()
        return {
            "session_id": session.session_id,
            "version": session.version,
            "profile_version": session.profile_version,
        }

    @router.get("/api/plans")
    def list_plans(request: Request) -> dict:
        principal = _principal(request, service)
        plans = service.list_plans_for_user(principal.user.id)
        return {"plans": [plan.model_dump() for plan in plans]}

    @router.get("/api/plans/current")
    def current_plan(request: Request) -> dict:
        principal = _principal(request, service)
        return service.get_current_plan_for_user(principal.user.id).model_dump()

    @router.get("/api/plans/{plan_id}")
    def get_plan(plan_id: str, request: Request) -> dict:
        principal = _principal(request, service)
        return service.get_plan_for_user(principal.user.id, plan_id).model_dump()

    return router
