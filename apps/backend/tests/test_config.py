from app.config import Settings


def test_settings_defaults(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
    monkeypatch.delenv("REPORT_TIMEZONE", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("DEDUP_SALT", raising=False)

    settings = Settings(_env_file=None)

    assert settings.database_url == "sqlite:///./dev.db"
    assert settings.anthropic_api_key is None
    assert settings.anthropic_model == "claude-sonnet-5"
    assert settings.report_timezone == "America/Port_of_Spain"
    assert settings.app_env == "development"
    assert settings.dedup_salt == "dev-salt-change-in-production"


def test_settings_env_override(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@localhost:5432/dmcu")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-123")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DEDUP_SALT", "prod-salt-xyz")

    settings = Settings(_env_file=None)

    assert settings.database_url == "postgresql+psycopg://user:pass@localhost:5432/dmcu"
    assert settings.anthropic_api_key == "sk-test-123"
    assert settings.app_env == "production"
    assert settings.dedup_salt == "prod-salt-xyz"
