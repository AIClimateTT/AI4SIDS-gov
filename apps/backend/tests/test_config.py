from app.config import Settings


def test_settings_defaults(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    monkeypatch.delenv("REPORT_TIMEZONE", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("DEDUP_SALT", raising=False)

    settings = Settings(_env_file=None)

    assert settings.database_url == "sqlite:///./dev.db"
    assert settings.llm_provider == "ollama"
    assert settings.ollama_base_url == "http://localhost:11434"
    assert settings.ollama_model == "gemma3:4b"
    assert settings.report_timezone == "America/Port_of_Spain"
    assert settings.app_env == "development"
    assert settings.dedup_salt == "dev-salt-change-in-production"


def test_settings_env_override(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@localhost:5432/dmcu")
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama-host:11434")
    monkeypatch.setenv("OLLAMA_MODEL", "gpt-oss:20b")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DEDUP_SALT", "prod-salt-xyz")

    settings = Settings(_env_file=None)

    assert settings.database_url == "postgresql+psycopg://user:pass@localhost:5432/dmcu"
    assert settings.llm_provider == "fake"
    assert settings.ollama_base_url == "http://ollama-host:11434"
    assert settings.ollama_model == "gpt-oss:20b"
    assert settings.app_env == "production"
    assert settings.dedup_salt == "prod-salt-xyz"
