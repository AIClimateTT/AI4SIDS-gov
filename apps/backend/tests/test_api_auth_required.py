import re
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app import create_app
from app.auth.models import User
from app.auth.tokens import create_access_token
from app.core.report_models import Report
from app.db import Base, SessionLocal, engine as db_engine
from app.modules.capture.store import create_session
from app.modules.sitreps.models import Event, Submission

pytestmark = pytest.mark.real_auth

ARIMA = "arima_borough_corporation"
SIPARIA = "siparia_regional_corporation"

# Everything else must refuse an anonymous caller. A new route nobody listed
# here fails by default, which is the point.
PUBLIC_ROUTES = {
    ("GET", "/healthcheck"),
    ("POST", "/auth/login"),
    ("POST", "/auth/otp/request"),
    ("POST", "/auth/otp/verify"),
    ("POST", "/auth/otp/resend"),
    ("POST", "/auth/refresh"),
    ("POST", "/auth/logout"),
}

# Corporation users work through capture, filings and their own report only.
CORP_ALLOWED_PREFIXES = ("/capture", "/events", "/submissions", "/auth", "/healthcheck")
CORP_ALLOWED_ROUTES = {
    ("GET", "/reports/{report_id}"),
    ("POST", "/reports/{report_id}/rating"),
}


def _all_routes() -> list[tuple[str, str]]:
    # The OpenAPI document, not app.routes: included routers are not flattened
    # onto app.routes, so walking it finds nothing and these tests would skip.
    routes = sorted(
        (method.upper(), path)
        for path, operations in create_app().openapi()["paths"].items()
        for method in operations
    )
    assert routes
    return routes


def _concrete(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "1", path)


@pytest.fixture(autouse=True)
def _schema():
    Base.metadata.drop_all(db_engine)
    Base.metadata.create_all(db_engine)
    yield
    Base.metadata.drop_all(db_engine)


def _client_for(role: str, corporation: str | None = None) -> TestClient:
    db = SessionLocal()
    user = User(
        email=f"{uuid.uuid4()}@example.com",
        role=role,
        first_name="Test",
        corporation=corporation,
        is_active=True,
    )
    db.add(user)
    db.commit()
    token = create_access_token(user_id=user.user_id, role=user.role, email=user.email)
    db.close()
    client = TestClient(create_app(), raise_server_exceptions=False)
    client.headers["Authorization"] = f"Bearer {token}"
    return client


@pytest.mark.parametrize(
    "method,path", [r for r in _all_routes() if r not in PUBLIC_ROUTES]
)
def test_anonymous_caller_is_refused(method, path):
    client = TestClient(create_app(), raise_server_exceptions=False)

    assert client.request(method, _concrete(path)).status_code == 401


@pytest.mark.parametrize(
    "method,path",
    [
        r
        for r in _all_routes()
        if r not in PUBLIC_ROUTES
        and r not in CORP_ALLOWED_ROUTES
        and not r[1].startswith(CORP_ALLOWED_PREFIXES)
        and not r[1].startswith("/users")
    ],
)
def test_corporation_user_is_refused_dmu_routes(method, path):
    client = _client_for("corp", ARIMA)

    assert client.request(method, _concrete(path)).status_code == 403


def test_dmu_user_reads_dmu_routes():
    client = _client_for("dmu")

    assert client.get("/incidents").status_code == 200


def test_corporation_user_cannot_open_a_capture_session_for_another():
    client = _client_for("corp", ARIMA)

    response = client.post("/capture/sessions", json={"corporation": SIPARIA})

    assert response.status_code == 403


def test_corporation_user_cannot_list_another_corporations_sessions():
    client = _client_for("corp", ARIMA)

    assert client.get("/capture/sessions", params={"corporation": SIPARIA}).status_code == 403


def test_corporation_user_cannot_read_another_corporations_session():
    client = _client_for("corp", ARIMA)
    db = SessionLocal()
    row = create_session(db, corporation=SIPARIA, event_id=None)
    session_id = row.id
    db.close()

    assert client.get(f"/capture/sessions/{session_id}").status_code == 403


def test_corporation_user_reads_its_own_session():
    client = _client_for("corp", ARIMA)
    db = SessionLocal()
    row = create_session(db, corporation=ARIMA, event_id=None)
    session_id = row.id
    db.close()

    assert client.get(f"/capture/sessions/{session_id}").status_code == 200


def test_dmu_user_reads_any_corporations_session():
    client = _client_for("dmu")
    db = SessionLocal()
    row = create_session(db, corporation=SIPARIA, event_id=None)
    session_id = row.id
    db.close()

    assert client.get(f"/capture/sessions/{session_id}").status_code == 200


def test_corporation_user_cannot_create_or_list_another_corporations_events():
    client = _client_for("corp", ARIMA)
    body = {
        "corporation": SIPARIA,
        "title": "Flood",
        "hazard_type": "flood",
        "started_at": "2026-08-21T10:00:00",
    }

    assert client.post("/events", json=body).status_code == 403
    assert client.get("/events", params={"corporation": SIPARIA}).status_code == 403


def _submission(corporation: str) -> int:
    db = SessionLocal()
    row = Submission(
        corporation=corporation,
        as_at=datetime(2026, 8, 21, 10),
        sequence_no=1,
        ingested_at=datetime(2026, 8, 21, 10),
    )
    db.add(row)
    db.commit()
    row_id = row.id
    db.close()
    return row_id


def test_corporation_user_submission_list_is_limited_to_its_own():
    client = _client_for("corp", ARIMA)
    own = _submission(ARIMA)
    _submission(SIPARIA)

    response = client.get("/submissions")

    assert [item["id"] for item in response.json()] == [own]
    assert client.get("/submissions", params={"corporation": SIPARIA}).status_code == 403


def test_corporation_user_cannot_read_another_corporations_submission():
    client = _client_for("corp", ARIMA)
    other = _submission(SIPARIA)

    assert client.get(f"/submissions/{other}").status_code == 403


def test_corporation_user_cannot_file_for_another_corporation():
    client = _client_for("corp", ARIMA)

    response = client.post(
        "/submissions",
        data={"corporation": SIPARIA, "as_at": "2026-08-21T10:00:00"},
    )

    assert response.status_code == 403


def _report(params: dict) -> str:
    db = SessionLocal()
    row = Report(
        id=str(uuid.uuid4()),
        template="corp_situation_report",
        template_version=1,
        params=params,
        fact_table={
            "request_id": "r",
            "template": "corp_situation_report",
            "params": params,
            "generated_at": "2026-08-21T10:00:00",
            "facts": [],
            "gaps": [],
        },
        narrative="",
        markdown="",
        status="ok",
        violations=[],
        created_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.commit()
    row_id = row.id
    db.close()
    return row_id


def test_corporation_user_reads_only_its_own_report():
    client = _client_for("corp", ARIMA)
    own = _report({"corporation": ARIMA})
    other = _report({"corporation": SIPARIA})
    national = _report({"date_from": "2026-01-01", "date_to": "2026-02-01"})

    assert client.get(f"/reports/{own}").status_code == 200
    assert client.get(f"/reports/{other}").status_code == 403
    assert client.get(f"/reports/{national}").status_code == 403
