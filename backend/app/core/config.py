"""App settings, read from environment variables (see .env.example)."""
from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PLACEHOLDER_SECRETS = {"change-me-in-env", "generate-a-long-random-string", ""}
MIN_SECRET_LENGTH = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Sahara (PROTOTYPE)"
    environment: str = "local"
    database_url: str = "postgresql+psycopg://sahara:sahara@localhost:5432/sahara"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: list[str] = ["http://localhost:5173"]

    jwt_secret: str = ""  # required: the app refuses to start without a strong secret
    jwt_access_minutes: int = 30
    bcrypt_rounds: int = 12  # tests lower this for speed; never below 12 in production

    typesafe_api_key: str | None = None
    typesafe_base_url: str = "https://api.typesafe.ai"
    # Pinned on purpose: thresholds are fitted to this exact model version.
    jev_model: str = "jev-1.14.0"
    jev_timeout_seconds: float = 2.0
    # Only admins of this department may reset the demo or inject mock-service faults.
    platform_admin_tenant: str = "pension"

    @model_validator(mode="after")
    def _refuse_weak_jwt_secret(self) -> "Settings":
        if self.jwt_secret in PLACEHOLDER_SECRETS or len(self.jwt_secret) < MIN_SECRET_LENGTH:
            raise ValueError("JWT_SECRET must be set to a random string of at least 32 characters")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
