import os

# Force an isolated local sqlite DB for the test session, regardless of what
# DATABASE_URL is set to in .env (e.g. a real Postgres used for manual/
# docker-compose runs). This must run before any `app.config`/`app.db`
# import, since pydantic-settings caches Settings() on first access and env
# vars take precedence over .env file values.
os.environ.setdefault("DATABASE_URL", "sqlite:///./dev.db")
