"""Standalone app factory and host-integration helpers."""

from __future__ import annotations

import sqlite3

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .configuration import AccountSettings
from .database import AccountDatabase
from .errors import AccountError, ERROR_MESSAGES
from .fitness import build_fitness_service
from .router import create_router
from .service import AccountService, FitnessService


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AccountError)
    async def account_error(_request: Request, exc: AccountError) -> JSONResponse:
        return JSONResponse(
            {"error": {"code": exc.code, "message": exc.message}},
            status_code=exc.status_code,
        )

    @app.exception_handler(RequestValidationError)
    async def request_error(_request: Request, _exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            {"error": {"code": "invalid_request", "message": ERROR_MESSAGES["invalid_request"]}},
            status_code=422,
        )

    @app.exception_handler(sqlite3.DatabaseError)
    async def database_error(_request: Request, _exc: sqlite3.DatabaseError) -> JSONResponse:
        return JSONResponse(
            {
                "error": {
                    "code": "database_failure",
                    "message": ERROR_MESSAGES["database_failure"],
                }
            },
            status_code=500,
        )


def create_app(
    settings: AccountSettings | None = None,
    *,
    fitness_service: FitnessService | None = None,
    database: AccountDatabase | None = None,
) -> FastAPI:
    """Build the standalone development app without starting a process or network call."""
    settings = settings or AccountSettings()
    if fitness_service is None:
        try:
            fitness_service = build_fitness_service(settings)
        except ImportError:
            fitness_service = None
    database = database or AccountDatabase(settings.database_path)
    service = AccountService(settings, database, fitness_service)
    app = FastAPI(title="SexyBanana Accounts", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-CSRF-Token"],
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["X-Frame-Options"] = "DENY"
        if request.url.path in {"/login", "/register"} or request.url.path.startswith("/api/auth"):
            response.headers["Cache-Control"] = "no-store"
        return response

    install_exception_handlers(app)
    app.include_router(create_router(service))
    app.state.account_service = service
    app.state.account_settings = settings
    return app
