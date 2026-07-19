from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.registry import reset_registry
from app.core.template_store import import_template_directory
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
    import_template_directory(TEMPLATES_DIR, session)
    session.close()

    app = create_app()
    return TestClient(app)


def test_get_templates_returns_both_real_templates():
    client = make_client()

    response = client.get("/templates")

    assert response.status_code == 200
    body = response.json()
    names = {t["name"] for t in body}
    assert names == {"minister_regional_comparison", "single_region_report"}
    assert all(t["version"] == 1 for t in body)


def test_get_templates_includes_params_with_required_flags():
    client = make_client()

    response = client.get("/templates")

    body = response.json()
    minister = next(t for t in body if t["name"] == "minister_regional_comparison")
    param_names = {p["name"] for p in minister["params"]}
    assert param_names == {"date_from", "date_to"}
    assert all(p["required"] for p in minister["params"])
