"""Double-submit CSRF tokens plus trusted-origin validation."""

import hmac
import secrets

from fastapi import Request

from .configuration import AccountSettings
from .errors import AccountError, ERROR_MESSAGES


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def validate_csrf(request: Request, settings: AccountSettings) -> None:
    cookie_name = f"{settings.cookie_name}_csrf"
    cookie = request.cookies.get(cookie_name)
    header = request.headers.get("X-CSRF-Token")
    origin = request.headers.get("Origin")
    if origin and origin.rstrip("/") not in settings.origin_list:
        raise AccountError("csrf_failed", ERROR_MESSAGES["csrf_failed"], 403)
    if (
        not cookie
        or not header
        or len(cookie) > 512
        or len(header) > 512
        or not hmac.compare_digest(cookie, header)
    ):
        raise AccountError("csrf_failed", ERROR_MESSAGES["csrf_failed"], 403)
