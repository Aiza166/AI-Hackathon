"""App settings, read from environment variables (see .env.example)."""
from functools import lru_cache

from pydantic import field_validator, model_validator
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

    # Azure AI services. All optional: without them the app falls back (Tesseract OCR,
    # browser speech) and keeps working. Never log these values.
    azure_speech_key: str | None = None
    azure_speech_region: str | None = None
    azure_docintel_endpoint: str | None = None
    azure_docintel_key: str | None = None
    azure_timeout_seconds: float = 20.0
    jev_image_timeout_seconds: float = 8.0
    tts_cache_dir: str | None = None  # disk cache for synthesised audio; memory-only when unset

    # Production hardening. ENVIRONMENT=production turns these on.
    # Judge-console shortcuts (demo reset, mock faults, skipping the payout hold) need this
    # token in the X-Demo-Console-Token header in production; unset means they are disabled.
    demo_console_token: str | None = None
    allow_docs: bool = False  # production only: expose /docs and /openapi.json
    # Proxies whose X-Forwarded-For we believe (comma-separated IPs or CIDRs). Same value as
    # uvicorn's --forwarded-allow-ips in start.sh.
    forwarded_allow_ips: str = "127.0.0.1"
    # Rate-limit storage. Unset: Redis (REDIS_URL) in production, process memory elsewhere.
    ratelimit_storage_uri: str | None = None
    max_body_bytes: int = 10 * 1024 * 1024

    @property
    def is_production(self) -> bool:
        return self.environment.strip().lower() in ("production", "prod")

    @field_validator("database_url")
    @classmethod
    def _use_psycopg_driver(cls, url: str) -> str:
        """Hosts like Railway give postgres:// or postgresql:// URLs; SQLAlchemy needs the driver named."""
        for prefix in ("postgres://", "postgresql://"):
            if url.startswith(prefix):
                return "postgresql+psycopg://" + url[len(prefix):]
        return url

    @field_validator("azure_speech_key", "azure_speech_region", "azure_docintel_endpoint", "azure_docintel_key", "typesafe_api_key",
                     "demo_console_token", "ratelimit_storage_uri")
    @classmethod
    def _blank_is_unset(cls, value: str | None) -> str | None:
        """An empty placeholder in .env means "not configured"."""
        if value is None:
            return None
        return value.strip() or None

    @property
    def speech_configured(self) -> bool:
        return bool(self.azure_speech_key and self.azure_speech_region)

    @property
    def docintel_configured(self) -> bool:
        return bool(self.azure_docintel_endpoint and self.azure_docintel_key)

    @model_validator(mode="after")
    def _refuse_weak_jwt_secret(self) -> "Settings":
        if self.jwt_secret in PLACEHOLDER_SECRETS or len(self.jwt_secret) < MIN_SECRET_LENGTH:
            raise ValueError("JWT_SECRET must be set to a random string of at least 32 characters")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
