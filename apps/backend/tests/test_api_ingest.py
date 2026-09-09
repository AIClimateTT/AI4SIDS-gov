from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.registry import reset_registry
from app.db import Base, engine as db_engine
from app import create_app

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "sample_small.csv"
SITREP_FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "sample_sitrep_small.csv"
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


def make_client() -> TestClient:
    import app.modules.survey123.models  # noqa: F401

    Base.metadata.create_all(db_engine)
    app = create_app()
    return TestClient(app)


@pytest.mark.workflow("survey123_ingest")
def test_post_ingest_survey123_returns_ingest_result():
    client = make_client()

    with open(FIXTURE_PATH, "rb") as f:
        response = client.post("/ingest/survey123", files={"file": ("sample_small.csv", f, "text/csv")})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["rows_read"] == 30
    assert body["rows_inserted"] == 30
    assert body["duplicates_flagged"] == 4
    assert "Name of Person" in body["pii_columns_dropped"]


def test_post_ingest_sitreps_is_retired_in_favour_of_submissions():
    # Task 5 removed the CSV-ingest branch for sitreps entirely: sitreps data
    # now arrives as a submission (see tests/test_api_submissions.py), not as a
    # bare file upload with a free-text corporation field. This replaces two
    # older tests that both exercised the old behaviour: one asserted a missing
    # corporation was rejected (no longer meaningful — the whole path is
    # rejected regardless of corporation), the other asserted a 200 with rows
    # inserted, which no longer happens for any input.
    client = make_client()

    with open(SITREP_FIXTURE_PATH, "rb") as f:
        response = client.post(
            "/ingest/sitreps",
            files={"file": ("sample_sitrep_small.csv", f, "text/csv")},
            data={"corporation": "Diego Martin"},
        )

    assert response.status_code == 400
    assert "/submissions" in response.json()["detail"]


def test_post_ingest_unknown_module_returns_404():
    client = make_client()

    with open(FIXTURE_PATH, "rb") as f:
        response = client.post("/ingest/not_a_real_module", files={"file": ("sample_small.csv", f, "text/csv")})

    assert response.status_code == 404
