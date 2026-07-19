from pathlib import Path

from sqlalchemy.orm import sessionmaker

from app.db import Base, make_engine
from app.modules.survey123.models import Incident
from app.modules.sitreps.ingest import PII_COLUMNS_SITREPS, ingest_sitrep_csv

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "sample_sitrep_small.csv"
CORPORATION = "diego_martin_regional_corporati"


def make_session(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


def test_ingest_sitrep_csv_reads_all_rows(tmp_path):
    session = make_session(tmp_path)

    result = ingest_sitrep_csv(FIXTURE_PATH, CORPORATION, session)

    assert result.rows_read == 3
    assert result.rows_inserted == 3
    assert result.rows_updated == 0
    assert result.pii_columns_dropped == PII_COLUMNS_SITREPS


def test_ingest_sitrep_csv_tags_rows_with_sitreps_source(tmp_path):
    session = make_session(tmp_path)

    ingest_sitrep_csv(FIXTURE_PATH, CORPORATION, session)

    rows = session.query(Incident).all()
    assert len(rows) == 3
    assert all(r.source == "sitreps" for r in rows)


def test_ingest_sitrep_csv_normalizes_corporation(tmp_path):
    session = make_session(tmp_path)

    ingest_sitrep_csv(FIXTURE_PATH, CORPORATION, session)

    rows = session.query(Incident).all()
    assert all(r.corporation == CORPORATION for r in rows)


def test_ingest_sitrep_csv_flags_unmapped_corporation(tmp_path):
    session = make_session(tmp_path)

    result = ingest_sitrep_csv(FIXTURE_PATH, "Not A Real Corporation", session)

    assert result.unmapped_values["Corporation"] == ["Not A Real Corporation"]
    rows = session.query(Incident).all()
    assert all(r.corporation == "unmapped" for r in rows)


def test_ingest_sitrep_csv_drops_pii_never_stores_it(tmp_path):
    session = make_session(tmp_path)

    ingest_sitrep_csv(FIXTURE_PATH, CORPORATION, session)

    columns = set(Incident.__table__.columns.keys())
    assert "name_of_person" not in columns
    assert "contact_information" not in columns
    row = session.query(Incident).filter_by(global_id=f"sitreps-{CORPORATION}-1").one()
    assert "Velma Cupidore" not in (row.incident_summary or "")
    assert "793-9056" not in (row.incident_summary or "")


def test_ingest_sitrep_csv_marks_validated_and_not_duplicate(tmp_path):
    session = make_session(tmp_path)

    ingest_sitrep_csv(FIXTURE_PATH, CORPORATION, session)

    rows = session.query(Incident).all()
    assert all(r.validation_status == "validated" for r in rows)
    assert all(r.is_duplicate is False for r in rows)


def test_ingest_sitrep_csv_is_idempotent_on_reingest(tmp_path):
    session = make_session(tmp_path)
    ingest_sitrep_csv(FIXTURE_PATH, CORPORATION, session)

    result = ingest_sitrep_csv(FIXTURE_PATH, CORPORATION, session)

    assert result.rows_inserted == 0
    assert result.rows_updated == 3
    assert session.query(Incident).count() == 3


def test_ingest_sitrep_csv_parses_incident_type_and_damage_fields(tmp_path):
    session = make_session(tmp_path)

    ingest_sitrep_csv(FIXTURE_PATH, CORPORATION, session)

    fire_row = session.query(Incident).filter_by(global_id=f"sitreps-{CORPORATION}-3").one()
    assert fire_row.incident_type == "fire"
    assert fire_row.injuries_occurred is True
    assert fire_row.injuries_count == 1
    assert float(fire_row.estimated_damage_cost) == 500.0
    assert fire_row.follow_up_flags == {
        "relief_supplied": False,
        "forwarded_to_agency": True,
        "further_assessment_required": False,
        "other": False,
    }
