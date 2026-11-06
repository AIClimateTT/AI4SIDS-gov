from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app import create_app
from app.core.report_models import Report
from app.db import Base, SessionLocal, engine as db_engine
from app.modules.capture.models import CaptureSession
from app.modules.sitreps.models import Event, SitrepIncident, SituationLog, Submission
from app.modules.survey123.models import FieldObservation

ARIMA = "arima_borough_corporation"
SIPARIA = "siparia_regional_corporation"


@pytest.fixture(autouse=True)
def _schema():
    Base.metadata.drop_all(db_engine)
    Base.metadata.create_all(db_engine)
    yield
    Base.metadata.drop_all(db_engine)


def _submission(db, corporation, as_at, event_id=None, sequence=1) -> Submission:
    row = Submission(
        corporation=corporation,
        event_id=event_id,
        as_at=as_at,
        sequence_no=sequence,
        ingested_at=as_at,
    )
    db.add(row)
    db.flush()
    return row


def _log(db, submission, statement) -> None:
    db.add(SituationLog(submission_id=submission.id, category="activity", statement=statement))


@pytest.fixture
def seeded():
    db = SessionLocal()
    event = Event(
        corporation=ARIMA,
        title="June rains",
        hazard_type="flood",
        started_at=datetime(2026, 6, 1),
        created_at=datetime(2026, 6, 1),
    )
    db.add(event)
    db.flush()
    first = _submission(db, ARIMA, datetime(2026, 6, 1, 10), event.id, 1)
    second = _submission(db, ARIMA, datetime(2026, 6, 2, 10), event.id, 2)
    other = _submission(db, SIPARIA, datetime(2026, 6, 3, 10))
    _log(db, first, "Sandbags filled")
    _log(db, second, "CERT on standby")
    _log(db, other, "Shelter inspected")
    db.add(
        SitrepIncident(
            submission_id=first.id,
            corporation=ARIMA,
            event_id=event.id,
            row_id="1",
            community="Arima",
            incident_summary="Flooded road",
            event_date=date(2026, 6, 1),
            ingested_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        )
    )
    db.add(
        FieldObservation(
            global_id="g-1",
            object_id=1,
            corporation=ARIMA,
            community="Arima",
            incident_summary="Field row",
            validation_status="validated",
            source_file="f.csv",
            ingested_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        )
    )
    db.commit()
    ids = {"first": first.id, "second": second.id, "other": other.id}
    db.close()
    return ids


def test_situation_logs_are_listed_newest_first_with_their_filing(seeded):
    body = TestClient(create_app()).get("/situation-logs").json()

    assert body["total"] == 3
    assert [item["statement"] for item in body["items"]] == [
        "Shelter inspected",
        "CERT on standby",
        "Sandbags filled",
    ]
    assert body["items"][1]["event_title"] == "June rains"
    assert body["items"][1]["corporation"] == ARIMA
    assert body["items"][1]["submission_id"] == seeded["second"]


def test_situation_logs_filter_by_corporation_and_submission(seeded):
    client = TestClient(create_app())

    by_corp = client.get("/situation-logs", params={"corporation": ARIMA}).json()
    by_filing = client.get("/situation-logs", params={"submission_id": seeded["first"]}).json()

    assert by_corp["total"] == 2
    assert [item["statement"] for item in by_filing["items"]] == ["Sandbags filled"]


def test_situation_logs_paginate_and_search(seeded):
    client = TestClient(create_app())

    page = client.get("/situation-logs", params={"page": 2, "page_size": 2}).json()
    found = client.get("/situation-logs", params={"q": "cert"}).json()

    assert page["total"] == 3
    assert [item["statement"] for item in page["items"]] == ["Sandbags filled"]
    assert found["total"] == 1


def test_incidents_filter_by_corporation(seeded):
    body = TestClient(create_app()).get(
        "/incidents", params={"source": "sitreps", "corporation": SIPARIA}
    ).json()

    assert body["total"] == 0


def test_incidents_filter_by_submission_excludes_survey123(seeded):
    body = TestClient(create_app()).get(
        "/incidents", params={"submission_id": seeded["first"]}
    ).json()

    assert [item["incident_summary"] for item in body["items"]] == ["Flooded road"]


def test_submission_summary_links_its_issued_report(seeded):
    db = SessionLocal()
    db.add(
        Report(
            id="report-1",
            template="corp_situation_report",
            template_version=101,
            params={"corporation": ARIMA},
            fact_table={},
            narrative="",
            markdown="",
            status="ok",
            violations=[],
            created_at=datetime(2026, 6, 1),
        )
    )
    db.flush()
    db.add(
        CaptureSession(
            corporation=ARIMA,
            status="filed",
            submission_id=seeded["first"],
            report_id="report-1",
            as_at=datetime(2026, 6, 1),
            created_at=datetime(2026, 6, 1),
            updated_at=datetime(2026, 6, 1),
        )
    )
    db.commit()
    db.close()

    body = TestClient(create_app()).get("/submissions", params={"corporation": ARIMA}).json()

    by_id = {item["id"]: item for item in body}
    assert by_id[seeded["first"]]["report_id"] == "report-1"
    assert by_id[seeded["second"]]["report_id"] is None
