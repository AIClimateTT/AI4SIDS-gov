from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.registry import reset_registry
from app.db import Base, engine as db_engine
from app import create_app

TEMPLATES_DIR = Path(__file__).parent.parent / "app" / "templates" / "definitions"
DEV_DB_PATH = Path(__file__).parent.parent / "dev.db"


@pytest.fixture(autouse=True)
def _clean_state():
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
    from sqlalchemy.orm import sessionmaker

    Base.metadata.create_all(db_engine)
    Session = sessionmaker(bind=db_engine)
    session = Session()
    session.close()

    app = create_app()
    return TestClient(app)


def test_get_templates_returns_every_shipped_template():
    client = make_client()

    response = client.get("/templates")

    assert response.status_code == 200
    body = response.json()
    names = {t["name"] for t in body}
    assert names == {
        "corp_situation_report",
        "minister_situation_report",
        "field_data_region_review",
        "survey123_summary",
    }
    assert all(t["version"] >= 100 for t in body)


def test_get_templates_includes_full_template_fields():
    client = make_client()

    response = client.get("/templates")

    body = response.json()
    minister = next(t for t in body if t["name"] == "minister_situation_report")
    required = {p["name"] for p in minister["params"] if p["required"]}
    assert required == {"date_from", "date_to"}
    assert len(minister["data_requirements"]) > 0
    summary = next(t for t in body if t["name"] == "survey123_summary")
    assert summary["narration"]["identity"]
    assert summary["narration"]["skills"]["compose"]
    assert not summary["narration"]["skills"]["capture"]
    assert summary["narration"]["output_sections"]
    corp = next(t for t in body if t["name"] == "corp_situation_report")
    assert {p["name"] for p in corp["params"]} == {"corporation", "submission_id"}
    assert corp["narration"]["skills"]["capture"]
    assert corp["narration"]["skills"]["compose"]


def test_post_templates_is_gone():
    client = TestClient(create_app())

    assert client.post("/templates", json={}).status_code == 405
