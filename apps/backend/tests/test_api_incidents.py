from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.registry import reset_registry
from app.db import Base, SessionLocal, engine as db_engine
from app import create_app
from app.modules.sitreps.models import SitrepIncident
from app.modules.sitreps.store import create_event, create_submission

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "sample_small.csv"
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
    import app.modules.sitreps.models  # noqa: F401
    import app.modules.survey123.models  # noqa: F401

    Base.metadata.create_all(db_engine)
    app = create_app()
    return TestClient(app)


def _seed_sitrep() -> None:
    session = SessionLocal()
    try:
        event = create_event(
            session,
            corporation=CORP,
            title="River rise",
            hazard_type="flood",
            started_at=datetime(2024, 7, 1),
        )
        submission = create_submission(
            session,
            corporation=CORP,
            as_at=datetime(2024, 7, 2),
            event_id=event.id,
        )
        session.add(
            SitrepIncident(
                submission_id=submission.id,
                corporation=CORP,
                event_id=event.id,
                row_id="1",
                community="Diego Martin",
                incident_type="flood",
                incident_summary="River over bank",
                event_date=datetime(2024, 7, 1),
                injuries_occurred=False,
                deaths_occurred=False,
                follow_up_flags={},
                ingested_at=datetime(2024, 7, 2, tzinfo=timezone.utc),
            )
        )
        session.commit()
    finally:
        session.close()


def test_get_incidents_lists_survey123_and_sitrep_rows():
    client = make_client()
    with open(FIXTURE_PATH, "rb") as handle:
        ingested = client.post(
            "/ingest/survey123",
            files={"file": ("sample_small.csv", handle, "text/csv")},
        )
    assert ingested.status_code == 200, ingested.text
    _seed_sitrep()

    response = client.get("/incidents", params={"page": 1, "page_size": 100})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 31
    sources = {item["source"] for item in body["items"]}
    assert sources == {"survey123", "sitreps"}
    sitrep = next(item for item in body["items"] if item["source"] == "sitreps")
    assert sitrep["incident_summary"] == "River over bank"
    assert sitrep["validation_status"] is None
    assert sitrep["id"].startswith("sitreps:")


def test_get_incidents_filters_by_source_and_search():
    client = make_client()
    with open(FIXTURE_PATH, "rb") as handle:
        client.post(
            "/ingest/survey123",
            files={"file": ("sample_small.csv", handle, "text/csv")},
        )
    _seed_sitrep()

    sitreps = client.get("/incidents", params={"source": "sitreps"})
    assert sitreps.status_code == 200
    assert sitreps.json()["total"] == 1

    field = client.get("/incidents", params={"source": "survey123", "page_size": 100})
    assert field.json()["total"] == 30
    assert all(item["source"] == "survey123" for item in field.json()["items"])

    found = client.get("/incidents", params={"q": "river over"})
    assert found.json()["total"] == 1
    assert found.json()["items"][0]["source"] == "sitreps"


def test_get_incidents_rejects_an_unknown_source():
    client = make_client()
    response = client.get("/incidents", params={"source": "rainfall"})
    assert response.status_code == 400
    assert "source" in response.json()["detail"]
