from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app import create_app
from app.core.metrics import metric_names, run_metric
from app.db import Base, make_engine

VALIDATED_FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample_small_validated.csv"


@pytest.fixture
def session(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/m.db")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    yield db
    db.close()


def test_run_metric_dispatches_each_source(session):
    assert run_metric("sitreps", "incident_count", {}, session)[0].citation.module == "sitreps"
    assert run_metric("survey123", "incident_count", {}, session)[0].citation.module == "survey123"


def test_unknown_source_raises(session):
    with pytest.raises(ValueError, match="unknown data source: rainfall"):
        run_metric("rainfall", "incident_count", {}, session)


def test_unknown_metric_raises(session):
    with pytest.raises(ValueError, match="unknown metric for sitreps: nope"):
        run_metric("sitreps", "nope", {}, session)


def test_metric_names_per_source():
    assert "corporation_status" in metric_names("sitreps")
    assert "corporation_status" not in metric_names("survey123")
    assert "data_coverage" in metric_names("survey123")
    assert "data_coverage" not in metric_names("sitreps")


def test_stored_template_with_data_coverage_on_sitreps_still_returns_empty(session):
    assert run_metric("sitreps", "data_coverage", {}, session) == []


def test_field_data_upload_route_ingests():
    from app.db import engine as db_engine

    Base.metadata.create_all(db_engine)
    client = TestClient(create_app())

    with open(VALIDATED_FIXTURE, "rb") as f:
        response = client.post(
            "/field-data/upload", files={"file": ("export.csv", f, "text/csv")}
        )

    assert response.status_code == 200, response.text
    assert response.json()["rows_read"] == 21
    assert client.post("/ingest/" + "survey123").status_code == 404


def test_modules_route_is_gone():
    assert TestClient(create_app()).get("/modules").status_code == 404
