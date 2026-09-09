from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./dev.db"
    secret_key: str = "dev-only-change-me-use-a-long-random-value-in-production"
    access_token_expire_minutes: int = 720
    refresh_token_expire_days: int = 30
    app_name: str = "DMCU"
    app_url: str = "http://localhost:3000"
    from_email: str = "DMCU <noreply@example.com>"
    resend_api_key: str | None = None
    mailpit_url: str = "http://localhost:8025"
    email_logo_url: str = "https://example.com/logo.png"
    support_email: str = "support@example.com"
    brand_color: str = "#111827"
    otp_length: int = 6
    otp_ttl_minutes: int = 10
    llm_provider: Literal["fake", "ollama", "nim"] = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "gemma3:4b"
    ollama_chat_model: str = "gemma3:4b"
    # Ollama defaults this to 2048. Fact tables already reach ~2,000 tokens and
    # grow as corporations report, and overflow yields an empty narrative rather
    # than an error, so it is set explicitly.
    ollama_num_ctx: int = 8192
    nim_base_url: str = "http://localhost:8000"
    nim_api_key: str = "none"
    nim_model: str = "openai/gpt-oss-20b"
    nim_chat_model: str = "openai/gpt-oss-20b"
    job_backend: Literal["eager", "procrastinate"] | None = None
    report_timezone: str = "America/Port_of_Spain"
    app_env: str = "development"
    dedup_salt: str = "dev-salt-change-in-production"
    survey123_transport: Literal["inprocess", "mcp"] = "inprocess"

    @field_validator("secret_key")
    @classmethod
    def secret_key_must_not_be_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("SECRET_KEY must not be empty")
        return value


def validate_runtime_settings(values: Settings | None = None) -> None:
    """Refuse to boot staging/prod without a Resend key."""
    current = values or settings
    if current.app_env.lower() in ("production", "staging") and not current.resend_api_key:
        raise RuntimeError("RESEND_API_KEY is required in staging/production")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
