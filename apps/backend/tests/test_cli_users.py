from pathlib import Path

import pytest
from typer.testing import CliRunner

from app.auth.models import User
from app.auth.passwords import verify_with_timing_protection
from app.db import Base, SessionLocal, engine as db_engine
from cli import app

DEV_DB_PATH = Path(__file__).parent.parent / "dev.db"
runner = CliRunner()


@pytest.fixture(autouse=True)
def _clean_state():
    db_engine.dispose()
    if DEV_DB_PATH.exists():
        DEV_DB_PATH.unlink()
    Base.metadata.create_all(db_engine)
    yield
    db_engine.dispose()
    if DEV_DB_PATH.exists():
        DEV_DB_PATH.unlink()


def test_users_create_requires_role():
    result = runner.invoke(app, ["users", "create", "ada@example.com", "--password", "secret123"])
    assert result.exit_code != 0


def test_users_create_admin_with_password():
    result = runner.invoke(
        app,
        [
            "users",
            "create",
            "ada@example.com",
            "--role",
            "admin",
            "--password",
            "secret123",
        ],
    )
    assert result.exit_code == 0
    session = SessionLocal()
    user = session.query(User).one()
    assert user.email == "ada@example.com"
    assert user.role == "admin"
    assert verify_with_timing_protection("secret123", user.password_hash)
    session.close()


def test_users_set_password_updates_hash():
    runner.invoke(
        app,
        [
            "users",
            "create",
            "ada@example.com",
            "--role",
            "dmu",
            "--password",
            "secret123",
        ],
    )
    result = runner.invoke(
        app,
        ["users", "set-password", "ada@example.com", "--password", "newsecret"],
    )
    assert result.exit_code == 0
    session = SessionLocal()
    user = session.query(User).one()
    assert verify_with_timing_protection("newsecret", user.password_hash)
    session.close()
