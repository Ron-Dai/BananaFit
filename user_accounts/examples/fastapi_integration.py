"""Illustrative future host integration; this file does not edit the existing server."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sexybanana_accounts import (
    AccountDatabase,
    AccountService,
    AccountSettings,
    build_fitness_service,
    create_router,
    install_exception_handlers,
)
settings = AccountSettings()
fitness_service = build_fitness_service(settings)
account_service = AccountService(
    settings,
    AccountDatabase(settings.database_path),
    fitness_service,
)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
)
install_exception_handlers(app)
app.include_router(create_router(account_service))
