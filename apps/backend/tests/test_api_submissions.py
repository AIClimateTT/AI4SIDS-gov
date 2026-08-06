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


def _event(c, corporation=CORP, title="Adverse Weather June 2023"):
    return c.post("/events", json={
        "corporation": corporation, "title": title, "hazard_type": "wind",
        "started_at": "2023-06-27T00:00:00"}).json()["id"]


def _file(c, event_id, corporation=CORP, as_at="2023-06-28T09:00:00", rows=1):
    body = "Row ID,Incident Type,Date of Event\n" + "".join(
        f"{i},fallen_tree,2023-06-27\n" for i in range(1, rows + 1)
    )
    return c.post(
        "/submissions",
        data={"corporation": corporation, "as_at": as_at, "event_id": event_id},
        files={"incidents_file": ("i.csv", io.BytesIO(body.encode()), "text/csv")},
    )


def test_list_submissions_is_newest_first_with_counts():
    c = client()
    event_id = _event(c)
    _file(c, event_id, as_at="2023-06-28T09:00:00", rows=1)
    _file(c, event_id, as_at="2023-06-30T16:00:00", rows=3)

    body = c.get("/submissions").json()

    assert [s["sequence_no"] for s in body] == [2, 1]
    assert body[0]["incident_count"] == 3
    assert body[0]["event_title"] == "Adverse Weather June 2023"


def test_list_submissions_with_no_filters_returns_every_corporation():
    # The DMU dashboard passes only a window and needs all corporations back.
    c = client()
    _file(c, _event(c), rows=1)
    other = "siparia_regional_corporation"
    _file(c, _event(c, corporation=other), corporation=other, rows=1)

    corps = {s["corporation"] for s in c.get("/submissions").json()}

    assert corps == {CORP, "siparia_regional_corporation"}


def test_list_submissions_filters_by_corporation_and_event():
    c = client()
    first, second = _event(c), _event(c, title="Second Event")
    _file(c, first, rows=1)
    _file(c, second, as_at="2023-07-02T09:00:00", rows=1)

    by_event = c.get("/submissions", params={"event_id": first}).json()
    by_corp = c.get("/submissions", params={"corporation": "arima_borough_corporation"}).json()

    assert [s["event_id"] for s in by_event] == [first]
    assert by_corp == []


def test_list_submissions_filters_by_window():
    c = client()
    event_id = _event(c)
    _file(c, event_id, as_at="2023-06-28T09:00:00", rows=1)
    _file(c, event_id, as_at="2023-07-15T09:00:00", rows=1)

    june = c.get(
        "/submissions", params={"date_from": "2023-06-01", "date_to": "2023-06-30"}
    ).json()

    assert len(june) == 1


def test_submission_detail_carries_row_errors_and_overview():
    c = client()
    event_id = _event(c)
    incidents = "Row ID,Incident Type,Date of Event\n,landslide,2023-06-27\n2,fire,2023-06-28\n"
    created = c.post(
        "/submissions",
        data={
            "corporation": CORP, "as_at": "2023-06-30T16:00:00", "event_id": event_id,
            "situation_overview": "Heavy rainfall affected the Borough.",
        },
        files={"incidents_file": ("i.csv", io.BytesIO(incidents.encode()), "text/csv")},
    ).json()

    detail = c.get(f"/submissions/{created['submission_id']}").json()

    assert detail["situation_overview"] == "Heavy rainfall affected the Borough."
    assert detail["row_errors"] == [
        {"file": "incidents", "row_number": 2, "reason": "Row ID is required"}
    ]


def test_submission_detail_404s_for_an_unknown_id():
    assert client().get("/submissions/99999").status_code == 404
