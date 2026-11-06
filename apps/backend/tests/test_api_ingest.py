from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db import Base, engine as db_engine
from app import create_app

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "sample_small.csv"
VALIDATED_FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "sample_small_validated.csv"
SITREP_FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "sample_sitrep_small.csv"
DEV_DB_PATH = Path(__file__).parent.parent / "dev.db"


@pytest.fixture(autouse=True)
def _clean_registry():
    db_engine.dispose()
    if DEV_DB_PATH.exists():
        DEV_DB_PATH.unlink()
    yield
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

    with open(VALIDATED_FIXTURE_PATH, "rb") as f:
        response = client.post("/field-data/upload", files={"file": ("sample_small.csv", f, "text/csv")})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["rows_read"] == 21
    assert body["rows_inserted"] == 21
    assert body["duplicates_flagged"] == 2
    assert "Name of Person" in body["pii_columns_dropped"]


def test_post_ingest_survey123_missing_global_id_returns_400():
    client = make_client()
    payload = b"ObjectID,Community,Validated/NotValidated\n1,Sangre Grande,Validated\n"

    response = client.post(
        "/field-data/upload",
        files={"file": ("bad.csv", payload, "text/csv")},
    )

    assert response.status_code == 400
    assert "GlobalID" in response.json()["detail"]


def test_post_ingest_survey123_bad_date_names_the_row_and_column():
    client = make_client()
    payload = b"ObjectID,GlobalID,Date of Event,Validated/NotValidated\n1,GUID-1,not-a-date,Validated\n"

    response = client.post(
        "/field-data/upload",
        files={"file": ("bad.csv", payload, "text/csv")},
    )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "Row 2" in detail
    assert "Date of Event" in detail


def test_post_ingest_rejects_a_file_with_an_unvalidated_row(tmp_path):
    client = make_client()
    path = tmp_path / "export.csv"
    path.write_text("ObjectID,GlobalID,Validated/NotValidated\n1,g-1,Validated\n2,g-2,\n")

    with open(path, "rb") as f:
        response = client.post("/field-data/upload", files={"file": ("export.csv", f, "text/csv")})

    assert response.status_code == 400
    assert response.json()["detail"].startswith("1 row(s) are not marked Validated (first: row 3).")
