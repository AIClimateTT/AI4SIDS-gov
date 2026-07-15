from pathlib import Path

from sqlalchemy.orm import sessionmaker

from app.db import Base, make_engine
from app.modules.survey123.ingest import ingest_csv
from app.modules.survey123.metrics import incident_count, incidents_by_corporation

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "sample_small.csv"


def make_session(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    ingest_csv(FIXTURE_PATH, session, salt="test-salt")
    return session


def test_incident_count_default_validated_only(tmp_path):
    session = make_session(tmp_path)

    facts = incident_count({}, session)

    assert len(facts) == 1
    fact = facts[0]
    assert fact.metric == "incident_count"
    assert fact.value == 19
    assert fact.unit == "incidents"
    assert fact.breakdown == {
        "flooding_": 7,
        "other": 2,
        "landslide": 4,
        "fallen_tree": 2,
        "over grown tree": 2,
        "fire": 1,
        "unmapped": 1,
    }
    assert fact.verification == "validated"
    assert fact.citation.cid == "survey123-incident_count-0"
    assert fact.citation.record_ids is not None
    assert len(fact.citation.record_ids) == 19


def test_incident_count_include_pending_widens_result(tmp_path):
    session = make_session(tmp_path)

    facts = incident_count({"include_pending": True}, session)

    fact = facts[0]
    assert fact.value == 26
    assert fact.breakdown == {
        "flooding_": 7,
        "fire": 4,
        "other": 2,
        "landslide": 4,
        "blown_off_roof": 2,
        "fallen_tree": 2,
        "earthquake": 2,
        "over grown tree": 2,
        "unmapped": 1,
    }
    assert fact.verification == "mixed"


def test_incident_count_filters_by_corporation(tmp_path):
    session = make_session(tmp_path)

    facts = incident_count({"corporation": "sangre_grande_regional_corporat"}, session)

    fact = facts[0]
    assert fact.value == 10
    assert fact.breakdown == {"flooding_": 7, "other": 2, "unmapped": 1}
    assert fact.scope["corporation"] == "sangre_grande_regional_corporat"


def test_incident_count_filters_by_community(tmp_path):
    session = make_session(tmp_path)

    facts = incident_count({"community": "San Fernando"}, session)

    fact = facts[0]
    assert fact.value == 6
    assert fact.breakdown == {"landslide": 4, "fallen_tree": 2}


def test_incident_count_filters_by_date_from(tmp_path):
    session = make_session(tmp_path)

    facts = incident_count({"date_from": "2024-06-15"}, session)

    fact = facts[0]
    assert fact.value == 8
    assert fact.scope["window"] == "2024-06-15..latest"


def test_incidents_by_corporation_default_includes_blank_bucket(tmp_path):
    session = make_session(tmp_path)

    facts = incidents_by_corporation({}, session)

    assert len(facts) == 1
    fact = facts[0]
    assert fact.metric == "incidents_by_corporation"
    assert fact.value == 19
    assert fact.breakdown == {
        "sangre_grande_regional_corporat": 10,
        "san_fernando_city_corporation": 6,
        "(no corporation recorded)": 2,
        "unmapped": 1,
    }
    assert fact.verification == "validated"


def test_incidents_by_corporation_include_pending_widens_blank_bucket(tmp_path):
    session = make_session(tmp_path)

    facts = incidents_by_corporation({"include_pending": True}, session)

    fact = facts[0]
    assert fact.value == 26
    assert fact.breakdown == {
        "sangre_grande_regional_corporat": 13,
        "san_fernando_city_corporation": 8,
        "(no corporation recorded)": 4,
        "unmapped": 1,
    }
    assert fact.verification == "mixed"
