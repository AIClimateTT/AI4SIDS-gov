from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import create_app
from app.config import settings
from app.db import Base, SessionLocal, engine as db_engine
from app.modules.survey123 import client as survey123_client
from app.modules.survey123.models import FieldObservation
from app.modules.survey123.pull import feature_row, layer_header

ITEM_ID = "68834896188a40ab8472f5eefedea1f4"
SERVICE = "https://portal.example.test/server/rest/services/Hosted/survey_results/FeatureServer"
DEV_DB_PATH = Path(__file__).parent.parent / "dev.db"


def ms(moment: datetime) -> int:
    return int(moment.timestamp() * 1000)


def field(name: str, alias: str, kind: str = "String") -> dict:
    return {"name": name, "alias": alias, "type": f"esriFieldType{kind}"}


# A survey published by Survey123: fields labelled with the question text.
LABELLED_FIELDS = [
    field("objectid", "ObjectID", "OID"),
    field("globalid", "GlobalID", "GlobalID"),
    field("CreationDate", "CreationDate", "Date"),
    field("EditDate", "EditDate", "Date"),
    field("date_of_event", "Date of Event", "Date"),
    field("community", "Community ", "String"),
    field("municipal_boundary", "Municipal Boundary"),
    field("incident_type", "Incident Type"),
    field("did_any_injuries_occur", "Did any injuries occur?"),
    field("injuries", "Injuries ", "Double"),
    field("estimate_cost", "Estimate Cost of Damage", "Double"),
    field("identification_card_number", "Identification Card Number"),
    field("validated", "Validated/NotValidated"),
    field("community_2", "Community"),
]


def labelled_feature(object_id: int, global_id: str, **overrides) -> dict:
    attributes = {
        "objectid": object_id,
        "globalid": global_id,
        "CreationDate": ms(datetime(2024, 6, 9, 15, 0, tzinfo=timezone.utc)),
        "EditDate": ms(datetime(2024, 6, 9, 15, 30, tzinfo=timezone.utc)),
        # Noon in Trinidad, as Survey123 stores a date-only question.
        "date_of_event": ms(datetime(2024, 6, 9, 16, 0, tzinfo=timezone.utc)),
        "community": None,
        "municipal_boundary": "san_fernando_city_corporation",
        "incident_type": "Flooding_",
        "did_any_injuries_occur": "yes",
        "injuries": 2.0,
        "estimate_cost": 1500.5,
        "identification_card_number": f"ID-{object_id}",
        "validated": "Validated",
        "community_2": "Marabella",
        **overrides,
    }
    return {"attributes": attributes, "geometry": {"x": -61.46, "y": 10.27}}


@pytest.fixture(autouse=True)
def _clean_db():
    db_engine.dispose()
    if DEV_DB_PATH.exists():
        DEV_DB_PATH.unlink()
    import app.modules.survey123.models  # noqa: F401

    Base.metadata.create_all(db_engine)
    yield
    db_engine.dispose()
    if DEV_DB_PATH.exists():
        DEV_DB_PATH.unlink()


@pytest.fixture
def survey(monkeypatch):
    """Serves a survey whose results layer holds the given features, in pages."""
    monkeypatch.setattr(settings, "survey123_api_key", "test-key-not-real")
    monkeypatch.setattr(settings, "survey123_api_url", f"https://survey123.arcgis.com/share/{ITEM_ID}")
    queries: list[httpx.Request] = []

    def serve(fields: list[dict], features: list[dict], page_size: int = 2):
        def handler(request: httpx.Request) -> httpx.Response:
            path = request.url.path
            if path.endswith("/relatedItems"):
                return httpx.Response(200, json={"relatedItems": [{"url": SERVICE}]})
            if path.endswith("/0/query"):
                queries.append(request)
                start = int(request.url.params["resultOffset"])
                page = features[start : start + page_size]
                more = start + page_size < len(features)
                return httpx.Response(200, json={"features": page, "exceededTransferLimit": more})
            if path.endswith("/0"):
                return httpx.Response(
                    200,
                    json={"fields": fields, "maxRecordCount": page_size, "objectIdField": "objectid"},
                )
            raise AssertionError(f"unexpected request {request.url}")

        monkeypatch.setattr(
            survey123_client,
            "_client",
            lambda: httpx.Client(transport=httpx.MockTransport(handler)),
        )
        return queries

    return serve


def pull() -> httpx.Response:
    return TestClient(create_app()).post("/field-data/survey123/pull")


def stored() -> dict[str, FieldObservation]:
    with SessionLocal() as session:
        rows = session.execute(select(FieldObservation)).scalars().all()
        return {row.global_id: row for row in rows}


def test_pull_stores_every_page_of_validated_responses(survey):
    features = [labelled_feature(n, f"gid-{n}") for n in range(1, 6)]
    queries = survey(LABELLED_FIELDS, features)

    response = pull()

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["rows_read"] == 5
    assert body["rows_inserted"] == 5
    assert set(stored()) == {f"gid-{n}" for n in range(1, 6)}
    assert [q.url.params["resultOffset"] for q in queries] == ["0", "2", "4"]
    assert all(q.url.params["orderByFields"] == "objectid" for q in queries)


def test_pulled_values_read_as_an_export_would(survey):
    survey(LABELLED_FIELDS, [labelled_feature(7, "gid-7")])

    assert pull().status_code == 200

    row = stored()["gid-7"]
    assert row.object_id == 7
    assert row.corporation == "san_fernando_city_corporation"
    assert row.incident_type == "flooding_"
    assert row.event_date == date(2024, 6, 9)
    assert row.creation_date.replace(tzinfo=timezone.utc) == datetime(2024, 6, 9, 15, 0, tzinfo=timezone.utc)
    assert row.injuries_occurred is True
    assert row.injuries_count == 2
    assert row.estimated_damage_cost == Decimal("1500.5")
    assert row.community == "Marabella"
    assert (row.lon, row.lat) == (-61.46, 10.27)
    assert row.dedup_hash is not None
    assert row.source_file == f"survey123:{ITEM_ID}/0"


def test_unvalidated_responses_are_left_for_a_later_pull(survey):
    features = [
        labelled_feature(1, "gid-1"),
        labelled_feature(2, "gid-2", validated=" "),
        labelled_feature(3, "gid-3", validated=None),
    ]
    survey(LABELLED_FIELDS, features)

    body = pull().json()

    assert set(stored()) == {"gid-1"}
    assert "2 response(s) are not marked Validated yet, so they were not stored." in body["warnings"]


def test_a_second_pull_updates_only_responses_edited_since(survey):
    later = ms(datetime(2024, 7, 1, tzinfo=timezone.utc))
    survey(LABELLED_FIELDS, [labelled_feature(1, "gid-1"), labelled_feature(2, "gid-2")])
    assert pull().status_code == 200

    survey(
        LABELLED_FIELDS,
        [labelled_feature(1, "gid-1"), labelled_feature(2, "gid-2", EditDate=later, injuries=5.0)],
    )
    body = pull().json()

    assert (body["rows_inserted"], body["rows_updated"]) == (0, 1)
    assert stored()["gid-2"].injuries_count == 5


def test_a_layer_without_object_or_global_ids_is_refused(survey):
    survey([field("municipal_boundary", "Municipal Boundary")], [])

    response = pull()

    assert response.status_code == 502
    assert "GlobalID" in response.json()["detail"]


def test_the_test_survey_short_field_names_map_to_export_columns():
    fields = [
        field("objectid", "OBJECTID", "OID"),
        field("globalid", "globalid"),
        field("administra", "administra"),
        field("field_43", "field_43"),
        field("community_", "community_"),
        field("community", "community"),
        field("globalid_1", "globalid_1", "GlobalID"),
    ]

    assert layer_header(fields) == [
        "ObjectID",
        "GlobalID",
        "Municipal Boundary",
        "Follow Up Recommendation",
        "Community",
        "Community_2",
        "globalid_1",
        "x",
        "y",
    ]


def test_bare_dates_and_blank_date_markers_read_as_calendar_days():
    fields = [field("date_of_ev", "date_of_ev", "Date"), field("assessment", "assessment", "Date")]
    header = layer_header(fields)
    feature = {
        "attributes": {
            # Stored as a bare date: midnight UTC is the day itself, not 8pm the day before.
            "date_of_ev": ms(datetime(2022, 1, 1, tzinfo=timezone.utc)),
            "assessment": ms(datetime(1899, 12, 30, tzinfo=timezone.utc)),
        }
    }

    row = feature_row(feature, fields, header)

    assert row["Date of Event"] == "2022-01-01"
    assert row["Assessment Date"] == ""
    assert (row["x"], row["y"]) == ("", "")
