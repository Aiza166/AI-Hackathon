"""App settings, read from environment variables (see .env.example)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Sahara (PROTOTYPE)"
    environment: str = "local"
    database_url: str = "postgresql+psycopg://sahara:sahara@localhost:5432/sahara"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: list[str] = ["http://localhost:5173"]

    jwt_secret: str = "change-me-in-env"
    jwt_access_minutes: int = 30
    bcrypt_rounds: int = 12  # tests lower this for speed; never below 12 in production

    typesafe_api_key: str | None = None
    typesafe_base_url: str = "https://api.typesafe.ai"
    # Pinned on purpose: thresholds are fitted to this exact model version.
    jev_model: str = "jev-1.14.0"
    jev_timeout_seconds: float = 2.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
