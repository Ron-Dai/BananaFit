"""Validated environment configuration with safe local defaults."""

from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AccountSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SEXYBANANA_", extra="ignore")

    database_path: Path = Path("data/sexybanana.db")
    app_url: str = "http://localhost:5173/"
    questionnaire_url: str = "/intake"
    allowed_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:8001,http://127.0.0.1:8001"
    )
    cookie_name: str = "sexybanana_session"
    cookie_secure: bool = False
    session_lifetime_seconds: int = Field(default=43200, ge=300, le=2592000)
    auth_host: str = "127.0.0.1"
    auth_port: int = Field(default=8001, ge=1, le=65535)
    fitness_provider: Literal["deepseek", "fake"] = "deepseek"

    @classmethod
    def from_env(cls) -> "AccountSettings":
        """Load account settings from ``SEXYBANANA_*`` environment variables."""

        return cls()

    @field_validator("app_url")
    @classmethod
    def safe_app_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Application URL must be an absolute HTTP(S) URL.")
        if parsed.username or parsed.password or parsed.fragment:
            raise ValueError("Application URL must not contain credentials or a fragment.")
        return value

    @field_validator("questionnaire_url")
    @classmethod
    def safe_questionnaire_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if (
            value.startswith("/")
            and not value.startswith("//")
            and "\\" not in value
            and not parsed.query
            and not parsed.fragment
        ):
            return value
        return cls.safe_app_url(value)

    @field_validator("cookie_name")
    @classmethod
    def valid_cookie_name(cls, value: str) -> str:
        if not value or not value.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Cookie name contains unsupported characters.")
        return value

    @property
    def origin_list(self) -> list[str]:
        values = [item.strip().rstrip("/") for item in self.allowed_origins.split(",")]
        return list(dict.fromkeys(item for item in values if item))
