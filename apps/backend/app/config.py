from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./dev.db"
    llm_provider: Literal["fake", "ollama"] = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "gemma3:4b"
    report_timezone: str = "America/Port_of_Spain"
    app_env: str = "development"
    dedup_salt: str = "dev-salt-change-in-production"
    survey123_transport: Literal["inprocess", "mcp"] = "inprocess"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
