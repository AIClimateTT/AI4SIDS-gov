from datetime import datetime
from pathlib import Path

import pytest
from pydantic import EmailStr, TypeAdapter
from typer.testing import CliRunner

from app.auth.models import User
from app.auth.passwords import hash_password, verify_with_timing_protection
from app.cli import app
from app.db import Base, SessionLocal, engine as db_engine
from app.modules.sitreps.models import Event
from app.modules.survey123.normalize import CANONICAL_CORPORATIONS

DEV_DB_PATH = Path(__file__).parent.parent / "dev.db"
runner = CliRunner()


@pytest.fixture(autouse=True)
def _clean_state():
    db_engine.dispose()
    if DEV_DB_PATH.exists():
        DEV_DB_PATH.unlink()
    Base.metadata.create_all(db_engine)
    session = SessionLocal()
    session.add(
        Event(
            corporation="arima_borough_corporation",
            title="Old event",
            hazard_type="wind",
            started_at=datetime(2023, 6, 27),
            created_at=datetime(2023, 6, 27),
        )
    )
    session.add(User(email="old@example.com", role="dmu", password_hash=hash_password("secret123")))
    session.commit()
    session.close()
    yield
    db_engine.dispose()
    if DEV_DB_PATH.exists():
        DEV_DB_PATH.unlink()


def test_db_reset_clears_existing_data():
    result = runner.invoke(app, ["db", "reset", "--yes"])
    assert result.exit_code == 0, result.output
    session = SessionLocal()
    assert session.query(Event).count() == 0
    assert session.query(User).filter(User.email == "old@example.com").count() == 0
    session.close()


def test_db_reset_seeds_the_admin():
    runner.invoke(app, ["db", "reset", "--yes"])
    session = SessionLocal()
    admin = session.query(User).filter(User.role == "admin").one()
    assert admin.email == "admin@mail.com"
    assert admin.is_active
    assert admin.corporation is None
    assert verify_with_timing_protection("Password123!", admin.password_hash)
    session.close()


def test_db_reset_seeds_one_account_per_corporation():
    runner.invoke(app, ["db", "reset", "--yes"])
    session = SessionLocal()
    corps = session.query(User).filter(User.role == "corp").all()
    assert {user.corporation for user in corps} == CANONICAL_CORPORATIONS
    assert len(corps) == 14
    for user in corps:
        TypeAdapter(EmailStr).validate_python(user.email)
        assert user.is_active
    assert session.query(User).count() == 15
    session.close()


def test_db_reset_can_run_twice():
    runner.invoke(app, ["db", "reset", "--yes"])
    result = runner.invoke(app, ["db", "reset", "--yes"])
    assert result.exit_code == 0, result.output
    session = SessionLocal()
    assert session.query(User).count() == 15
    session.close()


def test_db_reset_declined_changes_nothing():
    result = runner.invoke(app, ["db", "reset"], input="n\n")
    assert result.exit_code != 0
    session = SessionLocal()
    assert session.query(Event).count() == 1
    assert session.query(User).one().email == "old@example.com"
    session.close()
