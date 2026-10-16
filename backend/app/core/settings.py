"""Runtime settings, read from the environment (and backend/.env when it exists)."""

from functools import lru_cache
from typing import Literal, Self

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_SESSION_SECRET = "dev-only-session-secret"


class Settings(BaseSettings):
    # Errors leave out the input: it holds DATABASE_URL, password included, and lands in deploy logs.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

    app_env: Literal["dev", "test", "prod"] = "dev"
    database_url: str = "postgresql+psycopg://jagalink:jagalink@localhost:5432/jagalink"
    frontend_origin: str = "http://localhost:5173"
    session_secret: str = DEV_SESSION_SECRET

    @field_validator("database_url")
    @classmethod
    def use_psycopg_driver(cls, url: str) -> str:
        """Railway hands out postgresql:// URLs; SQLAlchemy needs the psycopg driver named."""
        for scheme in ("postgres://", "postgresql://"):
            if url.startswith(scheme):
                return "postgresql+psycopg://" + url.removeprefix(scheme)
        return url

    @field_validator("frontend_origin")
    @classmethod
    def strip_trailing_slash(cls, origin: str) -> str:
        return origin.rstrip("/")

    @model_validator(mode="after")
    def require_real_secret_in_prod(self) -> Self:
        if self.app_env == "prod" and (
            self.session_secret == DEV_SESSION_SECRET or len(self.session_secret) < 32
        ):
            raise ValueError("SESSION_SECRET must be a random string of 32+ characters in prod")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
