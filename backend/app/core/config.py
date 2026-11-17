
from functools import lru_cache
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "AI Agent Verification System"
    APP_ENV: str = "development"
    DEBUG: bool = False

    API_V1_PREFIX: str = "/api/v1"
    FRONTEND_URL: str = "http://localhost:3000"
    CORS_ALLOWED_ORIGINS: str | None = None
    TRUSTED_HOSTS: str = "localhost,127.0.0.1,testserver"
    TRUST_PROXY_HEADERS: bool = False
    ENFORCE_HTTPS: bool = False
    RATE_LIMIT_REQUESTS: int = Field(default=120, ge=1)
    RATE_LIMIT_WINDOW_SECONDS: int = Field(default=60, ge=1)
    RATE_LIMIT_MAX_CLIENTS: int = Field(default=10_000, ge=1)

    SUPABASE_URL: str | None = None
    SUPABASE_PUBLISHABLE_KEY: str | None = None
    SUPABASE_SECRET_KEY: str | None = None
    DATABASE_URL: str | None = None
    supabase_url: str | None = None
    supabase_service_role_key: str | None = None
    supabase_storage_bucket: str = "agent-kyc-documents"

    # These server-only values are deliberately absent from the frontend.
    DIDIT_ENABLED: bool = False
    DIDIT_API_KEY: SecretStr | None = None
    DIDIT_WORKFLOW_ID: str | None = None
    DIDIT_WEBHOOK_SECRET: SecretStr | None = None
    DIDIT_WEBHOOK_PREVIOUS_SECRET: SecretStr | None = None
    DIDIT_RETURN_URL: str | None = None
    DIDIT_ENVIRONMENT: Literal["sandbox", "production"] = "sandbox"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.lower() == "production"

    @property
    def cors_allowed_origins(self) -> list[str]:
        """Return explicit browser origins; wildcard CORS is never allowed."""

        raw_origins = self.CORS_ALLOWED_ORIGINS or self.FRONTEND_URL

        # Local development commonly alternates between localhost and the
        # loopback address. They are distinct browser origins, so allow both
        # only when the default local frontend URL is in use. Production still
        # requires explicit HTTPS origins below.
        if (
            not self.is_production
            and self.CORS_ALLOWED_ORIGINS is None
            and self.FRONTEND_URL == "http://localhost:3000"
        ):
            raw_origins = "http://localhost:3000,http://127.0.0.1:3000"

        origins = [
            origin.strip().rstrip("/")
            for origin in raw_origins.split(",")
            if origin.strip()
        ]
        if not origins or "*" in origins:
            raise ValueError("CORS_ALLOWED_ORIGINS must contain explicit origins")
        for origin in origins:
            parsed = urlparse(origin)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.path not in {"", "/"}
                or parsed.params
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError(
                    "CORS_ALLOWED_ORIGINS entries must be browser origins"
                )
        return origins

    @property
    def trusted_hosts(self) -> list[str]:
        hosts = [
            host.strip()
            for host in self.TRUSTED_HOSTS.split(",")
            if host.strip()
        ]
        if not hosts or "*" in hosts:
            raise ValueError("TRUSTED_HOSTS must contain explicit host names")
        return hosts

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        """Reject configurations that would weaken a production deployment."""

        # Evaluate these properties for every environment so malformed comma
        # separated values fail during startup rather than at the first request.
        _ = self.cors_allowed_origins
        _ = self.trusted_hosts

        if not self.is_production:
            return self

        if self.DEBUG:
            raise ValueError("DEBUG must be false in production")
        if not self.ENFORCE_HTTPS:
            raise ValueError("ENFORCE_HTTPS must be true in production")
        if not self.FRONTEND_URL.startswith("https://"):
            raise ValueError("FRONTEND_URL must use HTTPS in production")
        if any(
            not origin.startswith("https://")
            for origin in self.cors_allowed_origins
        ):
            raise ValueError(
                "CORS_ALLOWED_ORIGINS entries must use HTTPS in production"
            )
        if self.SUPABASE_URL and not self.SUPABASE_URL.startswith("https://"):
            raise ValueError("SUPABASE_URL must use HTTPS in production")
        if self.DIDIT_ENABLED:
            if self.DIDIT_ENVIRONMENT != "production":
                raise ValueError(
                    "DIDIT_ENVIRONMENT must be production when Didit is enabled"
                )
            if (
                not self.DIDIT_RETURN_URL
                or not self.DIDIT_RETURN_URL.startswith("https://")
            ):
                raise ValueError(
                    "DIDIT_RETURN_URL must use HTTPS when Didit is enabled"
                )

        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
