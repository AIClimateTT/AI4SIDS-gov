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
    app = create_app()
    return TestClient(app)


def _ingest_fixture():
    from sqlalchemy.orm import sessionmaker

    Session = sessionmaker(bind=db_engine)
    session = Session()
    ingest_csv(FIXTURE_PATH, session, salt="test-salt")
    session.close()


def test_post_reports_returns_id_status_markdown(monkeypatch):
    client = make_client(monkeypatch)
    _ingest_fixture()

    response = client.post(
        "/reports",
        json={
            "template": "minister_situation_report",
            "params": {"date_from": "2024-06-01", "date_to": "2024-06-30"},
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"]
    assert body["status"] == "ok"
    assert "# " in body["markdown"]
    assert "## Citation Appendix" in body["markdown"]


def test_post_reports_unknown_template_returns_404(monkeypatch):
    client = make_client(monkeypatch)

    response = client.post("/reports", json={"template": "not_a_real_template", "params": {}})

    assert response.status_code == 404


def test_post_reports_missing_required_param_returns_400(monkeypatch):
    client = make_client(monkeypatch)
    _ingest_fixture()

    response = client.post(
        "/reports", json={"template": "minister_situation_report", "params": {"date_from": "2024-06-01"}}
    )

    assert response.status_code == 400


def test_get_reports_by_id_returns_full_detail(monkeypatch):
    client = make_client(monkeypatch)
    _ingest_fixture()

    create_response = client.post(
        "/reports",
        json={
            "template": "minister_situation_report",
            "params": {"date_from": "2024-06-01", "date_to": "2024-06-30"},
        },
    )
    report_id = create_response.json()["id"]

    response = client.get(f"/reports/{report_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == report_id
    assert body["template"] == "minister_situation_report"
    assert body["template_version"] == 1
    assert "facts" in body["fact_table"]
    assert isinstance(body["violations"], list)
    assert body["created_at"]


def test_post_reports_blank_optional_param_counts_the_same_as_an_omitted_one(monkeypatch):
    # The Generate Report form seeds every template param to "" and validates
    # only the required ones, so an untouched optional `community` arrived
    # here as "". It reached SQL as `WHERE community = ''`, matched no row,
    # and the report read "0 incidents in Sangre Grande" with status ok.
    client = make_client(monkeypatch)
    _ingest_fixture()

    def facts_for(params: dict) -> dict[str, float]:
        response = client.post(
            "/reports", json={"template": "field_data_region_review", "params": params}
        )
        assert response.status_code == 200, response.text
        detail = client.get(f"/reports/{response.json()['id']}")
        assert detail.status_code == 200, detail.text
        return {
            f"{fact['metric']}:{fact['scope'].get('corporation')}": fact["value"]
            for fact in detail.json()["fact_table"]["facts"]
        }

    base = {
        "corporation": "sangre_grande_regional_corporat",
        "date_from": "2024-06-01",
        "date_to": "2024-06-30",
    }
    blank = facts_for({**base, "community": ""})
    omitted = facts_for(base)

    assert blank == omitted
    assert blank["incident_count:sangre_grande_regional_corporat"] > 0


def test_post_reports_blank_date_param_does_not_400(monkeypatch):
    # datetime.fromisoformat("") raises, and generate_report's ValueError path
    # turned that into a 400 on an otherwise valid request.
    client = make_client(monkeypatch)
    _ingest_fixture()

    response = client.post(
        "/reports",
        json={
            "template": "minister_situation_report",
            "params": {"date_from": "", "date_to": ""},
        },
    )

    assert response.status_code == 200, response.text


def test_post_reports_unknown_corporation_returns_400(monkeypatch):
    # A corporation that is not one of the fourteen matches no row, so every
    # metric returns zero and the report reads as an authoritative "nothing
    # happened" for a region that may have filed plenty.
    client = make_client(monkeypatch)
    _ingest_fixture()

    response = client.post(
        "/reports",
        json={
            "template": "field_data_region_review",
            "params": {
                "corporation": "Diego Martin",
                "date_from": "2024-06-01",
                "date_to": "2024-06-30",
            },
        },
    )

    assert response.status_code == 400
    assert "unknown corporation" in response.json()["detail"]


def test_post_reports_rejects_an_unknown_corporation_in_a_requirement_override(
    monkeypatch,
):
    # data_requirements is caller-controlled, so a literal corporation can
    # reach a query without ever appearing in params.
    client = make_client(monkeypatch)
    _ingest_fixture()

    response = client.post(
        "/reports",
        json={
            "template": "minister_situation_report",
            "params": {"date_from": "2024-06-01", "date_to": "2024-06-30"},
            "data_requirements": [
                {
                    "module": "survey123",
                    "metric": "incident_count",
                    "params": {"corporation": "Sangre Grande"},
                }
            ],
        },
    )

    assert response.status_code == 400


def test_post_reports_still_accepts_a_placeholder_corporation_in_a_requirement(
    monkeypatch,
):
    client = make_client(monkeypatch)
    _ingest_fixture()

    response = client.post(
        "/reports",
        json={
            "template": "field_data_region_review",
            "params": {
                "corporation": "sangre_grande_regional_corporat",
                "date_from": "2024-06-01",
                "date_to": "2024-06-30",
            },
            "data_requirements": [
                {
                    "module": "survey123",
                    "metric": "incident_count",
                    "params": {"corporation": "{corporation}"},
                }
            ],
        },
    )

    assert response.status_code == 200, response.text


def test_get_reports_list_returns_paginated_items(monkeypatch):
    client = make_client(monkeypatch)
    _ingest_fixture()

    first = client.post(
        "/reports",
        json={
            "template": "minister_situation_report",
            "params": {"date_from": "2024-06-01", "date_to": "2024-06-30"},
        },
    )
    second = client.post(
        "/reports",
        json={
            "template": "field_data_region_review",
            "params": {
                "corporation": "diego_martin_regional_corporati",
                "date_from": "2024-06-01",
                "date_to": "2024-06-30",
            },
        },
    )
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text

    response = client.get("/reports", params={"page": 1, "page_size": 10})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 2
    assert len(body["items"]) >= 2
    assert {"id", "template", "template_version", "params", "status", "created_at"} <= set(
        body["items"][0]
    )


def test_get_reports_list_filters_by_q_and_status(monkeypatch):
    client = make_client(monkeypatch)
    _ingest_fixture()

    client.post(
        "/reports",
        json={
            "template": "minister_situation_report",
            "params": {"date_from": "2024-06-01", "date_to": "2024-06-30"},
        },
    )
    client.post(
        "/reports",
        json={
            "template": "field_data_region_review",
            "params": {
                "corporation": "diego_martin_regional_corporati",
                "date_from": "2024-06-01",
                "date_to": "2024-06-30",
            },
        },
    )

    by_template = client.get("/reports", params={"q": "minister"})
    assert by_template.status_code == 200
    assert by_template.json()["total"] >= 1
    assert all("minister" in item["template"] for item in by_template.json()["items"])

    by_status = client.get("/reports", params={"status": "ok"})
    assert by_status.status_code == 200
    assert all(item["status"] == "ok" for item in by_status.json()["items"])


def test_get_reports_unknown_id_returns_404(monkeypatch):
    client = make_client(monkeypatch)

    response = client.get("/reports/does-not-exist")

    assert response.status_code == 404
