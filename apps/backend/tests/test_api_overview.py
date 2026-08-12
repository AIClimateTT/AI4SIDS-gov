from datetime import datetime
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
CORP = "diego_martin_regional_corporati"


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


def test_get_overview_counts_sitrep_incidents():
    # test_get_overview_returns_counts only ever proves incident_count_sitreps
    # is 0, which a hardcoded zero would satisfy just as well. Seed real
    # SitrepIncident rows via ingest_submission (the actual write path, not a
    # bare model construction) so the overview endpoint's sitreps branch is
    # genuinely exercised end to end.
    client = make_client()

    from sqlalchemy.orm import sessionmaker

    from app.modules.sitreps.ingest import ingest_submission

    Session = sessionmaker(bind=db_engine)
    session = Session()
    ingest_submission(
        session,
        corporation=CORP,
        as_at=datetime(2023, 6, 30, 16, 0),
        incidents_path=Path(__file__).parent.parent
        / "fixtures"
        / "sample_submission_incidents.csv",
    )
    session.close()

    response = client.get("/overview")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["incident_count_sitreps"] == 3
