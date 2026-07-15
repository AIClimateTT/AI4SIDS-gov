from pathlib import Path

from sqlalchemy.orm import sessionmaker

from app.db import Base, make_engine
from app.modules.survey123.ingest import ingest_csv
from app.modules.survey123.metrics import relief_actions_summary, street_level_tally

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "sample_small.csv"


def make_session(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    ingest_csv(FIXTURE_PATH, session, salt="test-salt")
    return session


def test_street_level_tally_within_corporation(tmp_path):
    session = make_session(tmp_path)

    facts = street_level_tally({"corporation": "sangre_grande_regional_corporat"}, session)

    assert len(facts) == 1
    fact = facts[0]
    assert fact.metric == "street_level_tally"
    assert fact.value == 10
    assert fact.breakdown == {
        "Sangre Grande / 1 Flood Street": 1,
        "Sangre Grande / 2 Flood Street": 1,
        "Sangre Grande / 3 Flood Street": 1,
        "Sangre Grande / 4 Flood Street": 1,
        "Sangre Grande / 5 Flood Street": 1,
        "Sangre Grande / 9 Sinkhole Road": 1,
        "Sangre Grande / 10 Sinkhole Road": 1,
        "Sangre Grande / 24 Volcano Trace": 1,
        "Sangre Grande / 29 Big Family Trace": 1,
        "Sangre Grande / 30 Big Family Trace": 1,
    }
    assert fact.scope["corporation"] == "sangre_grande_regional_corporat"


def test_relief_actions_summary_default_counts_distinct_incidents_and_flags(tmp_path):
    session = make_session(tmp_path)

    facts = relief_actions_summary({}, session)

    assert len(facts) == 1
    fact = facts[0]
    assert fact.metric == "relief_actions_summary"
    assert fact.value == 16
    assert fact.breakdown == {
        "relief_supplied": 7,
        "forwarded_to_agency": 9,
        "further_assessment_required": 5,
        "other": 4,
    }
    assert fact.verification == "validated"
    assert len(fact.citation.record_ids) == 16


def test_relief_actions_summary_include_pending_widens_result(tmp_path):
    session = make_session(tmp_path)

    facts = relief_actions_summary({"include_pending": True}, session)

    fact = facts[0]
    assert fact.value == 21
    assert fact.breakdown == {
        "relief_supplied": 9,
        "forwarded_to_agency": 12,
        "further_assessment_required": 5,
        "other": 4,
    }
    assert fact.verification == "mixed"
