import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import create_app
from app.core.registry import reset_registry
from app.db import Base, engine

CORP = "diego_martin_regional_corporati"
DEV_DB_PATH = Path(__file__).parent.parent / "dev.db"


# Mirrors the convention already used by tests/test_api_ingest.py and
# tests/test_api_overview.py — a per-test clean DB and registry, so API tests
# do not leak state into each other regardless of ordering.
@pytest.fixture(autouse=True)
def _clean_registry():
    reset_registry()
    engine.dispose()
    if DEV_DB_PATH.exists():
        DEV_DB_PATH.unlink()
    yield
    reset_registry()
    engine.dispose()
    if DEV_DB_PATH.exists():
        DEV_DB_PATH.unlink()


def client() -> TestClient:
    import app.modules.sitreps.models  # noqa: F401
    import app.modules.survey123.models  # noqa: F401

    Base.metadata.create_all(engine)
    return TestClient(create_app())


def test_create_and_list_events():
    c = client()

    created = c.post(
        "/events",
        json={
            "corporation": CORP,
            "title": "Adverse Weather June 2023",
            "hazard_type": "wind",
            "started_at": "2023-06-27T00:00:00",
        },
    )
    assert created.status_code == 201
    event_id = created.json()["id"]

    listed = c.get("/events", params={"corporation": CORP})
    assert listed.status_code == 200
    assert [e["id"] for e in listed.json()] == [event_id]


def test_events_are_scoped_by_corporation():
    c = client()
    c.post(
        "/events",
        json={
            "corporation": "siparia_regional_corporation",
            "title": "Theirs",
            "hazard_type": "flood",
            "started_at": "2023-06-27T00:00:00",
        },
    )

    listed = c.get("/events", params={"corporation": "arima_borough_corporation"})
    assert listed.json() == []


def test_post_submission_with_both_files():
    c = client()
    created = c.post(
        "/events",
        json={
            "corporation": CORP,
            "title": "Adverse Weather June 2023",
            "hazard_type": "wind",
            "started_at": "2023-06-27T00:00:00",
        },
    )
    event_id = created.json()["id"]
    incidents = "Row ID,Incident Type,Date of Event\n1,fallen_tree,2023-06-27\n"
    logs = "Category,Statement,Item,Quantity,Unit,Status\nresource,200 sandbags available,sandbags,200,bags,available\n"

    response = c.post(
        "/submissions",
        data={
            "corporation": CORP,
            "as_at": "2023-06-30T16:00:00",
            "alert_level": "discontinued",
            "present_activity": "Adverse Weather Alert",
            "situation_overview": "Heavy rainfall affected the Borough.",
            "event_id": event_id,
        },
        files={
            "incidents_file": ("incidents.csv", io.BytesIO(incidents.encode()), "text/csv"),
            "logs_file": ("logs.csv", io.BytesIO(logs.encode()), "text/csv"),
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["incidents_inserted"] == 1
    assert body["logs_inserted"] == 1
    assert body["row_errors"] == []
    assert body["pii_columns_dropped"] == ["Name of Person", "Contact Information"]


def test_submission_records_the_uploaded_filename():
    c = client()
    incidents = "Row ID,Incident Type,Date of Event\n1,fallen_tree,2023-06-27\n"
    created = c.post("/events", json={
        "corporation": CORP, "title": "Storm", "hazard_type": "wind",
        "started_at": "2023-06-27T00:00:00"})
    c.post("/submissions",
        data={"corporation": CORP, "as_at": "2023-06-30T16:00:00",
              "event_id": created.json()["id"]},
        files={"incidents_file": ("june-incidents.csv", io.BytesIO(incidents.encode()), "text/csv")})

    from sqlalchemy import select
    from app.db import SessionLocal
    from app.modules.sitreps.models import Submission
    s = SessionLocal()
    stored = s.scalars(select(Submission)).first().source_file
    s.close()

    assert stored == "june-incidents.csv"


def test_post_submission_reports_row_errors_without_failing():
    c = client()
    created = c.post(
        "/events",
        json={
            "corporation": CORP,
            "title": "Adverse Weather June 2023",
            "hazard_type": "wind",
            "started_at": "2023-06-27T00:00:00",
        },
    )
    event_id = created.json()["id"]
    incidents = "Row ID,Incident Type,Date of Event\n,landslide,2023-06-27\n2,fire,2023-06-28\n"

    response = c.post(
        "/submissions",
        data={"corporation": CORP, "as_at": "2023-07-01T09:00:00", "event_id": event_id},
        files={"incidents_file": ("incidents.csv", io.BytesIO(incidents.encode()), "text/csv")},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["incidents_inserted"] == 1
    assert body["row_errors"] == [
        {"file": "incidents", "row_number": 2, "reason": "Row ID is required"}
    ]


def test_post_submission_rejects_an_unknown_corporation():
    c = client()

    response = c.post(
        "/submissions",
        data={"corporation": "not_a_corporation", "as_at": "2023-07-01T09:00:00"},
    )

    assert response.status_code == 400
    assert "corporation" in response.json()["detail"]


def test_post_submission_rejects_an_unknown_alert_level():
    c = client()

    response = c.post(
        "/submissions",
        data={
            "corporation": CORP,
            "as_at": "2023-07-01T09:00:00",
            "alert_level": "chartreuse",
        },
    )

    assert response.status_code == 400
    assert "alert_level" in response.json()["detail"]


def test_post_event_rejects_an_unknown_hazard_type():
    c = client()

    response = c.post(
        "/events",
        json={
            "corporation": CORP,
            "title": "Something",
            "hazard_type": "meteor",
            "started_at": "2023-06-27T00:00:00",
        },
    )

    assert response.status_code == 400
    assert "hazard_type" in response.json()["detail"]


def test_post_submission_rejects_an_event_owned_by_another_corporation():
    # Data scoping, not authorization: there is no auth in this system. A corp
    # must simply not be able to attach its submission to another corp's event,
    # which would corrupt that event's incident set and report numbering.
    c = client()
    created = c.post(
        "/events",
        json={
            "corporation": "siparia_regional_corporation",
            "title": "Theirs",
            "hazard_type": "flood",
            "started_at": "2023-06-27T00:00:00",
        },
    )
    other_event_id = created.json()["id"]

    response = c.post(
        "/submissions",
        data={
            "corporation": CORP,
            "as_at": "2023-07-01T09:00:00",
            "event_id": other_event_id,
        },
    )

    assert response.status_code == 404
    assert str(other_event_id) in response.json()["detail"]


def test_post_submission_rejects_a_nonexistent_event():
    c = client()

    response = c.post(
        "/submissions",
        data={
            "corporation": CORP,
            "as_at": "2023-07-01T09:00:00",
            "event_id": 99999,
        },
    )

    assert response.status_code == 404


def test_a_submission_with_incidents_and_no_event_is_rejected():
    # Without an event, supersession is skipped, so re-filing a cumulative
    # table triples the incident count and record_ref collides across rows.
    c = client()
    incidents = "Row ID,Incident Type,Date of Event\n1,fallen_tree,2023-06-27\n"

    response = c.post(
        "/submissions",
        data={"corporation": CORP, "as_at": "2023-06-30T16:00:00"},
        files={"incidents_file": ("i.csv", io.BytesIO(incidents.encode()), "text/csv")},
    )

    assert response.status_code == 400
    assert "event" in response.json()["detail"].lower()


def test_a_logs_only_submission_needs_no_event():
    # Logs are point-in-time state: they never supersede and never collide.
    c = client()
    logs = "Category,Statement,Item,Quantity,Unit,Status\nresource,200 sandbags,sandbags,200,bags,available\n"

    response = c.post(
        "/submissions",
        data={"corporation": CORP, "as_at": "2023-06-30T16:00:00"},
        files={"logs_file": ("l.csv", io.BytesIO(logs.encode()), "text/csv")},
    )

    assert response.status_code == 201
    assert response.json()["logs_inserted"] == 1


def test_a_submission_with_incidents_and_an_event_is_accepted():
    c = client()
    created = c.post(
        "/events",
        json={
            "corporation": CORP,
            "title": "Adverse Weather June 2023",
            "hazard_type": "wind",
            "started_at": "2023-06-27T00:00:00",
        },
    )
    event_id = created.json()["id"]
    incidents = "Row ID,Incident Type,Date of Event\n1,fallen_tree,2023-06-27\n"

    response = c.post(
        "/submissions",
        data={"corporation": CORP, "as_at": "2023-06-30T16:00:00", "event_id": event_id},
        files={"incidents_file": ("i.csv", io.BytesIO(incidents.encode()), "text/csv")},
    )

    assert response.status_code == 201
    assert response.json()["incidents_inserted"] == 1
