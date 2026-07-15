from sqlalchemy import text

from app.db import make_engine


def test_make_engine_connects_and_executes():
    engine = make_engine("sqlite:///:memory:")

    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        assert result.scalar() == 1


def test_make_engine_returns_engine_for_postgres_url_without_connecting():
    engine = make_engine("postgresql+psycopg://user:pass@localhost:5432/dmcu")

    assert engine.url.drivername == "postgresql+psycopg"
