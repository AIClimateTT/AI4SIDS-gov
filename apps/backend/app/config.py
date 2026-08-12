from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./dev.db"
    llm_provider: Literal["fake", "ollama"] = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "gemma3:4b"
    # Ollama defaults this to 2048. Fact tables already reach ~2,000 tokens and
    # grow as corporations report, and overflow yields an empty narrative rather
    # than an error, so it is set explicitly.
    ollama_num_ctx: int = 8192
    report_timezone: str = "America/Port_of_Spain"
    app_env: str = "development"
    dedup_salt: str = "dev-salt-change-in-production"
    survey123_transport: Literal["inprocess", "mcp"] = "inprocess"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
