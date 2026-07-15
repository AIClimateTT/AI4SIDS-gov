from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.registry import reset_registry, reset_template_registry
from app.db import Base, engine as db_engine
from app.main import create_app
from app.modules.survey123.ingest import ingest_csv

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "sample_small.csv"
DEV_DB_PATH = Path(__file__).parent.parent / "dev.db"


@pytest.fixture(autouse=True)
def _clean_registry():
    reset_registry()
    reset_template_registry()
    db_engine.dispose()
    if DEV_DB_PATH.exists():
        DEV_DB_PATH.unlink()
    yield
    reset_registry()
    reset_template_registry()
    db_engine.dispose()
    if DEV_DB_PATH.exists():
        DEV_DB_PATH.unlink()


def make_client(monkeypatch) -> TestClient:
    monkeypatch.setattr("app.core.llm.settings.llm_provider", "fake")
    Base.metadata.create_all(db_engine)
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
            "template": "minister_regional_comparison",
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
        "/reports", json={"template": "minister_regional_comparison", "params": {"date_from": "2024-06-01"}}
    )

    assert response.status_code == 400


def test_get_reports_by_id_returns_full_detail(monkeypatch):
    client = make_client(monkeypatch)
    _ingest_fixture()

    create_response = client.post(
        "/reports",
        json={
            "template": "minister_regional_comparison",
            "params": {"date_from": "2024-06-01", "date_to": "2024-06-30"},
        },
    )
    report_id = create_response.json()["id"]

    response = client.get(f"/reports/{report_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == report_id
    assert body["template"] == "minister_regional_comparison"
    assert "facts" in body["fact_table"]
    assert isinstance(body["violations"], list)


def test_get_reports_unknown_id_returns_404(monkeypatch):
    client = make_client(monkeypatch)

    response = client.get("/reports/does-not-exist")

    assert response.status_code == 404
