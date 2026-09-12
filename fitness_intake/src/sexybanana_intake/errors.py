"""Stable, redacted errors for application integrations."""


class IntakeError(Exception):
    """Expose a code and safe message without retaining provider payloads or health data."""

    def __init__(self, code: str, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable

    def to_dict(self) -> dict:
        """Return a JSON-compatible error envelope."""
        return {"code": self.code, "message": self.message, "retryable": self.retryable}
