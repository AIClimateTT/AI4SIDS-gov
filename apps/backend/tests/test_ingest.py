import csv
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.db import Base, make_engine
from app.modules.survey123.ingest import PII_COLUMNS, ingest_csv
from app.modules.survey123.models import Incident

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "sample_small.csv"

HEADER = [
    "ObjectID", "GlobalID", "CreationDate", "Creator", "EditDate", "Editor", "Name of Officer",
    "Position", "Organisation", "Other - Organisation", "Date of Event", "Time of Event",
    "Name of Person", "Contact Information", "Address", "Community", "Municipal Boundary",
    "Incident Type", "Other - Incident Type", "Incident Summary", "Household Occupants",
    "If more than 6 persons - Household Occupants", "Did any injuries occur?", "Injuries",
    "Type of Injuries", "Did any deaths occur?", "Deaths", "Building Damage",
    "Crops and Livestock", "Personal Items", "Furniture and Appliances", "Action Taken",
    "Relief Items", "Other Agency", "Shelter", "Are there any special needs occupants?",
    "Please indicate the number of special needs occupants", "Estimate Cost of Damage",
    "Identification Card Type", "Other - Identification Card Type", "Identification Card Number",
    "Follow Up Recommendation", "Other - Follow Up Recommendation", "Assessment Date",
    "Is the property insured?", "Island", "District", "Ownership", "Property Type",
    "Structure Type", "Other - Structure Type", "Age of Structure (years)", "Type of Household",
    "Number of Male Occupants", "Number of Female Occupants", "What are the age groups of occupants?",
    "Are there any dependents in the household", "Number of Dependents", "Validated/NotValidated",
    "Please list the names of the occupants and their relation", "Employment Status",
    "Employment Sector", "Other - Employment Sector", "Flood Type", "Flood Trigger",
    "Other - Flood Trigger", "Flood Height", "Other Agency_2", "Community_2", "Other - Community",
    "Other Agency_3", "Other - Other Agency", "Name of Second Person", "Second Contact Information",
    "Second Identification Card Number", "Second Employment Status", "x", "y",
]


def make_session(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


def write_csv(path: Path, rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=HEADER)
        writer.writeheader()
        for r in rows:
            full_row = {h: "" for h in HEADER}
            full_row.update(r)
            writer.writerow(full_row)


def test_ingest_fixture_yields_expected_row_count_and_corporation_breakdown(tmp_path):
    session = make_session(tmp_path)

    result = ingest_csv(FIXTURE_PATH, session, salt="test-salt")

    assert result.rows_read == 30
    assert result.rows_inserted == 30
    assert result.rows_updated == 0

    def count_corp(value):
        return len(session.execute(select(Incident).where(Incident.corporation == value)).scalars().all())

    assert count_corp("sangre_grande_regional_corporat") == 15
    assert count_corp("san_fernando_city_corporation") == 10
    assert count_corp("unmapped") == 1
    assert len(session.execute(select(Incident).where(Incident.corporation.is_(None))).scalars().all()) == 4


def test_ingest_fixture_incident_type_breakdown(tmp_path):
    session = make_session(tmp_path)
    ingest_csv(FIXTURE_PATH, session, salt="test-salt")

    def count_type(value):
        return len(session.execute(select(Incident).where(Incident.incident_type == value)).scalars().all())

    assert count_type("flooding_") == 9
    assert count_type("fire") == 6
    assert count_type("other") == 2
    assert count_type("landslide") == 4
    assert count_type("blown_off_roof") == 2
    assert count_type("fallen_tree") == 2
    assert count_type("earthquake") == 2
    assert count_type("over grown tree") == 2
    assert count_type("unmapped") == 1


def test_ingest_fixture_validation_status_breakdown(tmp_path):
    session = make_session(tmp_path)
    ingest_csv(FIXTURE_PATH, session, salt="test-salt")

    validated = session.execute(select(Incident).where(Incident.validation_status == "validated")).scalars().all()
    pending = session.execute(select(Incident).where(Incident.validation_status == "pending")).scalars().all()

    assert len(validated) == 21
    assert len(pending) == 9


def test_ingest_fixture_flags_duplicate_marker_and_repeated_id_date(tmp_path):
    session = make_session(tmp_path)

    result = ingest_csv(FIXTURE_PATH, session, salt="test-salt")

    assert result.duplicates_flagged == 4

    marker_rows = session.execute(
        select(Incident).where(Incident.global_id.in_(["GUID-025", "GUID-026"]))
    ).scalars().all()
    for r in marker_rows:
        assert r.is_duplicate is True
        assert r.duplicate_reason == "marker"

    repeated_rows = session.execute(
        select(Incident).where(Incident.global_id.in_(["GUID-027", "GUID-028"]))
    ).scalars().all()
    for r in repeated_rows:
        assert r.is_duplicate is True
        assert r.duplicate_reason == "repeated_id_date"


def test_ingest_fixture_reports_unmapped_values_and_pii_columns_dropped(tmp_path):
    session = make_session(tmp_path)

    result = ingest_csv(FIXTURE_PATH, session, salt="test-salt")

    assert result.unmapped_values == {
        "Municipal Boundary": ["Unknown_Corp_Typo"],
        "Incident Type": ["Volcanic_Eruption_Typo"],
    }
    assert result.pii_columns_dropped == PII_COLUMNS


def test_ingest_fixture_no_pii_value_persisted_anywhere(tmp_path):
    session = make_session(tmp_path)
    ingest_csv(FIXTURE_PATH, session, salt="test-salt")

    all_incidents = session.execute(select(Incident)).scalars().all()
    serialized = " ".join(
        str(getattr(incident, col.name)) for incident in all_incidents for col in Incident.__table__.columns
    )
    for pii_value in ["Fake Person 1", "8685550001", "19800101001", "Real Person 27"]:
        assert pii_value not in serialized


def test_reingesting_same_file_is_a_no_op(tmp_path):
    session = make_session(tmp_path)

    first = ingest_csv(FIXTURE_PATH, session, salt="test-salt")
    second = ingest_csv(FIXTURE_PATH, session, salt="test-salt")

    assert first.rows_inserted == 30
    assert second.rows_inserted == 0
    assert second.rows_updated == 0
    assert second.rows_read == 30


def test_cross_ingest_duplicate_detected_against_already_persisted_rows(tmp_path):
    session = make_session(tmp_path)
    ingest_csv(FIXTURE_PATH, session, salt="test-salt")

    second_file = tmp_path / "second_batch.csv"
    write_csv(
        second_file,
        [
            {
                "ObjectID": "99",
                "GlobalID": "GUID-099",
                "CreationDate": "2024-07-05T09:00:00",
                "EditDate": "2024-07-05T09:00:00",
                "Date of Event": "2024-06-27T00:00:00",
                "Name of Person": "Another Real Person",
                "Municipal Boundary": "san_fernando_city_corporation",
                "Incident Type": "Flooding_",
                "Identification Card Number": "19850315099",
                "Validated/NotValidated": "Validated",
            }
        ],
    )

    result = ingest_csv(second_file, session, salt="test-salt")

    assert result.rows_inserted == 1
    assert result.duplicates_flagged == 1

    new_row = session.execute(select(Incident).where(Incident.global_id == "GUID-099")).scalar_one()
    assert new_row.is_duplicate is True
    assert new_row.duplicate_reason == "repeated_id_date"
