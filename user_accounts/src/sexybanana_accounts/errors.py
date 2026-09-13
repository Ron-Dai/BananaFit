"""Stable public errors without database or identity disclosure."""


class AccountError(Exception):
    """Error with a machine-readable code, safe message, and HTTP status."""

    def __init__(self, code: str, message: str, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


ERROR_MESSAGES = {
    "invalid_request": "The request is invalid.",
    "invalid_email": "Enter a valid email address.",
    "weak_password": "The password does not meet the documented requirements.",
    "password_mismatch": "The password confirmation does not match.",
    "account_exists": "An account with this email already exists.",
    "invalid_credentials": "The email or password is incorrect.",
    "account_disabled": "This account is unavailable.",
    "authentication_required": "Sign in to continue.",
    "session_expired": "Your session has expired. Sign in again.",
    "csrf_failed": "The security token is missing or invalid.",
    "not_found": "The requested resource was not found.",
    "version_conflict": "The data changed. Reload and try again.",
    "plan_unavailable": "A workout plan is not available yet.",
    "plan_stale": "The workout plan requires reassessment.",
    "database_failure": "The request could not be completed.",
}
