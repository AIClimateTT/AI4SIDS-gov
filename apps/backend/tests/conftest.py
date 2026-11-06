import os

# Force an isolated local sqlite DB for the test session, regardless of what
# DATABASE_URL is set to in .env (e.g. a real Postgres used for manual/
# docker-compose runs). This must run before any `app.config`/`app.db`
# import, since pydantic-settings caches Settings() on first access and env
# vars take precedence over .env file values.
os.environ.setdefault("DATABASE_URL", "sqlite:///./dev.db")


import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user
from app.auth.models import User


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "real_auth: run the real login checks instead of a signed-in admin"
    )


@pytest.fixture(autouse=True)
def _signed_in_admin(request, monkeypatch):
    """API tests exercise their own subject, so each client is an admin unless
    the test asks for the real login checks with @pytest.mark.real_auth."""
    if request.node.get_closest_marker("real_auth"):
        return
    admin = User(
        user_id=uuid.uuid4(),
        email="admin@example.com",
        role="admin",
        first_name="Test",
        is_active=True,
    )
    original_init = TestClient.__init__

    def init(self, app, *args, **kwargs):
        if isinstance(app, FastAPI):
            app.dependency_overrides.setdefault(get_current_user, lambda: admin)
        original_init(self, app, *args, **kwargs)

    monkeypatch.setattr(TestClient, "__init__", init)
