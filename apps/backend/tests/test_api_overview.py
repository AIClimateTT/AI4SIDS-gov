from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import create_app
from app.core.registry import reset_registry
from app.db import Base, engine as db_engine
from app.modules.survey123.ingest import ingest_csv

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "sample_small.csv"
SITREP_FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "sample_sitrep_small.csv"
DEV_DB_PATH = Path(__file__).parent.parent / "dev.db"


@pytest.fixture(autouse=True)
def _clean_registry():
    reset_registry()
    db_engine.dispose()
    if DEV_DB_PATH.exists():
        DEV_DB_PATH.unlink()
    yield
    reset_registry()
    db_engine.dispose()
    if DEV_DB_PATH.exists():
        DEV_DB_PATH.unlink()


def make_client() -> TestClient:
    # Import models so metadata includes incidents + reports tables.
    import app.core.report_models  # noqa: F401
    import app.modules.survey123.models  # noqa: F401

    Base.metadata.create_all(db_engine)
    app = create_app()
    return TestClient(app)


def test_get_overview_returns_counts():
    client = make_client()

    from sqlalchemy.orm import sessionmaker

    Session = sessionmaker(bind=db_engine)
    session = Session()
    ingest_csv(FIXTURE_PATH, session, salt="test-salt")
    session.close()

    response = client.get("/overview")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["incident_count_survey123"] == 30
    assert body["incident_count_sitreps"] == 0
    assert body["report_count"] == 0
    assert body["needs_review_count"] == 0
    assert body["recent_reports"] == []
