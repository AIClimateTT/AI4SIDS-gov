from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.registry import reset_registry
from app.db import Base, engine as db_engine
from app import create_app
from app.modules.survey123.ingest import ingest_csv

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "sample_small.csv"
TEMPLATES_DIR = Path(__file__).parent.parent / "app" / "templates" / "definitions"
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


def make_client(monkeypatch) -> TestClient:
    from sqlalchemy.orm import sessionmaker

    from app.core.template_store import import_template_directory

    monkeypatch.setattr("app.core.llm.settings.llm_provider", "fake")
    Base.metadata.create_all(db_engine)
    Session = sessionmaker(bind=db_engine)
    session = Session()
    import_template_directory(TEMPLATES_DIR, session)
    session.close()
    return TestClient(create_app())


def _ingest_fixture():
    from sqlalchemy.orm import sessionmaker

    Session = sessionmaker(bind=db_engine)
    session = Session()
    ingest_csv(FIXTURE_PATH, session, salt="test-salt")
    session.close()


def _generate(client: TestClient):
    return client.post(
        "/reports",
        json={
            "template": "minister_situation_report",
            "params": {"date_from": "2024-06-01", "date_to": "2024-06-30"},
        },
    )


def test_summary_includes_scored_report_after_generate(monkeypatch):
    client = make_client(monkeypatch)
    _ingest_fixture()
    created = _generate(client)
    assert created.status_code == 202, created.text
    summary = client.get("/quality/summary")
    assert summary.status_code == 200
    body = summary.json()
    assert body["scored_count"] >= 1
    names = {row["name"] for row in body["thresholds"]}
    assert names >= {
        "faithfulness",
        "critical_numerical",
        "citation_accuracy",
        "completeness",
        "critical_hallucination",
        "unsupported_claim",
        "task_completion",
        "usability_mean",
        "usability_positive",
    }


def test_create_report_writes_started_and_succeeded_events(monkeypatch):
    client = make_client(monkeypatch)
    _ingest_fixture()
    created = _generate(client)
    assert created.status_code == 202, created.text
    report_id = created.json()["id"]
    events = client.get("/quality/events", params={"subject_id": report_id})
    assert events.status_code == 200
    outcomes = {item["outcome"] for item in events.json()["items"]}
    assert "started" in outcomes
    assert "succeeded" in outcomes


def test_post_event_rejects_unknown_workflow(monkeypatch):
    client = make_client(monkeypatch)
    response = client.post(
        "/quality/events",
        json={
            "workflow": "not_a_workflow",
            "step": "create",
            "outcome": "started",
        },
    )
    assert response.status_code == 400


def test_patch_assisted_excludes_event_from_unaided_success(monkeypatch):
    client = make_client(monkeypatch)
    _ingest_fixture()
    created = _generate(client)
    report_id = created.json()["id"]
    events = client.get("/quality/events", params={"subject_id": report_id}).json()["items"]
    succeeded = next(item for item in events if item["outcome"] == "succeeded")
    patched = client.patch(
        f"/quality/events/{succeeded['id']}", json={"assisted": True}
    )
    assert patched.status_code == 200
    summary = client.get("/quality/summary").json()
    assert summary["task_succeeded_unaided"] == 0


def test_rating_requires_auth(monkeypatch):
    client = make_client(monkeypatch)
    response = client.post("/reports/nope/rating", json={"rating": 5})
    assert response.status_code == 401


def test_authenticated_user_can_rate_a_report(monkeypatch):
    from app.auth.tokens import create_access_token
    from tests.auth_helpers import create_user

    client = make_client(monkeypatch)
    _ingest_fixture()
    created = _generate(client)
    report_id = created.json()["id"]
    user = create_user()
    token = create_access_token(
        user_id=user.user_id,
        role=user.role,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        corporation=user.corporation,
    )
    rated = client.post(
        f"/reports/{report_id}/rating",
        json={"rating": 5},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert rated.status_code == 200, rated.text
    assert rated.json()["rating"] == 5
    summary = client.get("/quality/summary").json()
    assert summary["rating_count"] == 1
    assert summary["rating_mean"] == 5.0
    assert summary["rating_positive_rate"] == 1.0


def test_dmu_user_can_verdict_a_pending_claim(monkeypatch):
    from app.auth.tokens import create_access_token
    from tests.auth_helpers import create_user

    client = make_client(monkeypatch)
    _ingest_fixture()
    created = _generate(client)
    report_id = created.json()["id"]
    detail = client.get(f"/reports/{report_id}").json()
    claims = (detail.get("quality_eval") or {}).get("claims", {}).get("claims", [])
    assert claims, "generated report should carry a claim inventory"
    claim_id = claims[0]["claim_id"]
    user = create_user(role="dmu")
    token = create_access_token(
        user_id=user.user_id,
        role=user.role,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        corporation=user.corporation,
    )
    patched = client.patch(
        f"/reports/{report_id}/claims/{claim_id}",
        json={"verdict": "supported"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert patched.status_code == 200, patched.text
    claims = patched.json()["claims"]["claims"]
    updated = next(item for item in claims if item["claim_id"] == claim_id)
    assert updated["human_verdict"] == "supported"


def test_corp_user_cannot_verdict_a_claim(monkeypatch):
    from app.auth.tokens import create_access_token
    from tests.auth_helpers import create_user

    client = make_client(monkeypatch)
    _ingest_fixture()
    created = _generate(client)
    report_id = created.json()["id"]
    detail = client.get(f"/reports/{report_id}").json()
    claims = (detail.get("quality_eval") or {}).get("claims", {}).get("claims", [])
    assert claims
    claim_id = claims[0]["claim_id"]
    user = create_user(role="corp", corporation="arima")
    token = create_access_token(
        user_id=user.user_id,
        role=user.role,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        corporation=user.corporation,
    )
    patched = client.patch(
        f"/reports/{report_id}/claims/{claim_id}",
        json={"verdict": "supported"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert patched.status_code == 403


def test_unknown_claim_returns_404(monkeypatch):
    from app.auth.tokens import create_access_token
    from tests.auth_helpers import create_user

    client = make_client(monkeypatch)
    _ingest_fixture()
    created = _generate(client)
    report_id = created.json()["id"]
    user = create_user(role="dmu")
    token = create_access_token(
        user_id=user.user_id,
        role=user.role,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        corporation=user.corporation,
    )
    patched = client.patch(
        f"/reports/{report_id}/claims/cl999",
        json={"verdict": "supported"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert patched.status_code == 404
