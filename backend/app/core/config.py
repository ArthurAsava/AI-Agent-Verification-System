
from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "AI Agent Verification System"
    APP_ENV: str = "development"
    DEBUG: bool = False

    API_V1_PREFIX: str = "/api/v1"
    FRONTEND_URL: str = "http://localhost:3000"

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
