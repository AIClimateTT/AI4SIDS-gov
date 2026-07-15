from pathlib import Path

from sqlalchemy.orm import sessionmaker

from app.db import Base, make_engine
from app.modules.survey123.ingest import ingest_csv
from app.modules.survey123.metrics import data_coverage, estimated_damage_total, special_needs_count

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "sample_small.csv"


def make_session(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    ingest_csv(FIXTURE_PATH, session, salt="test-salt")
    return session


def test_special_needs_count_default(tmp_path):
    session = make_session(tmp_path)

    facts = special_needs_count({}, session)

    assert len(facts) == 1
    fact = facts[0]
    assert fact.metric == "special_needs_count"
    assert fact.value == 2
    assert fact.unit == "persons"
    assert fact.breakdown is None


def test_special_needs_count_include_pending(tmp_path):
    session = make_session(tmp_path)

    facts = special_needs_count({"include_pending": True}, session)

    assert facts[0].value == 4


def test_estimated_damage_total_default_reports_coverage(tmp_path):
    session = make_session(tmp_path)

    facts = estimated_damage_total({}, session)

    assert len(facts) == 1
    fact = facts[0]
    assert fact.metric == "estimated_damage_total"
    assert fact.value == 98000.0
    assert fact.unit == "TTD"
    assert fact.breakdown == {"records_reporting_cost": 5, "records_total": 19}


def test_estimated_damage_total_include_pending_widens_denominator_only(tmp_path):
    session = make_session(tmp_path)

    facts = estimated_damage_total({"include_pending": True}, session)

    fact = facts[0]
    assert fact.value == 98000.0
    assert fact.breakdown == {"records_reporting_cost": 5, "records_total": 26}


def test_data_coverage_returns_one_fact_per_corporation_including_blank_bucket(tmp_path):
    session = make_session(tmp_path)

    facts = data_coverage({}, session)

    assert len(facts) == 4
    by_scope_corp = {f.scope["corporation"]: f for f in facts}

    assert by_scope_corp["(no corporation recorded)"].value == 4
    assert by_scope_corp["(no corporation recorded)"].breakdown == {"pct_validated": 50.0, "pct_duplicates": 0.0}

    assert by_scope_corp["san_fernando_city_corporation"].value == 10
    assert by_scope_corp["san_fernando_city_corporation"].breakdown == {"pct_validated": 80.0, "pct_duplicates": 20.0}

    assert by_scope_corp["sangre_grande_regional_corporat"].value == 15
    assert by_scope_corp["sangre_grande_regional_corporat"].breakdown == {"pct_validated": 66.7, "pct_duplicates": 13.3}

    assert by_scope_corp["unmapped"].value == 1
    assert by_scope_corp["unmapped"].breakdown == {"pct_validated": 100.0, "pct_duplicates": 0.0}

    for fact in facts:
        assert fact.metric == "data_coverage"
        assert fact.unit == "records"
        assert fact.verification == "n/a"


def test_data_coverage_includes_pending_and_duplicates_by_design(tmp_path):
    session = make_session(tmp_path)

    facts = data_coverage({}, session)
    total_records = sum(f.value for f in facts)

    assert total_records == 30
