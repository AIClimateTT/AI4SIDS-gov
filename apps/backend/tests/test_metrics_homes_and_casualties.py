from pathlib import Path

from sqlalchemy.orm import sessionmaker

from app.db import Base, make_engine
from app.modules.survey123.ingest import ingest_csv
from app.modules.survey123.metrics import casualty_summary, homes_affected_count

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "sample_small.csv"


def make_session(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    ingest_csv(FIXTURE_PATH, session, salt="test-salt")
    return session


def test_homes_affected_count_default_is_validated_only_value_with_full_breakdown(tmp_path):
    session = make_session(tmp_path)

    facts = homes_affected_count({}, session)

    assert len(facts) == 1
    fact = facts[0]
    assert fact.metric == "homes_affected_count"
    assert fact.value == 12
    assert fact.breakdown == {"validated": 12, "pending": 7}
    assert fact.verification == "validated"
    assert len(fact.citation.record_ids) == 12


def test_homes_affected_count_include_pending_widens_value_but_not_breakdown(tmp_path):
    session = make_session(tmp_path)

    facts = homes_affected_count({"include_pending": True}, session)

    fact = facts[0]
    assert fact.value == 19
    assert fact.breakdown == {"validated": 12, "pending": 7}
    assert fact.verification == "mixed"
    assert len(fact.citation.record_ids) == 19


def test_casualty_summary_default_returns_injuries_and_deaths_facts(tmp_path):
    session = make_session(tmp_path)

    facts = casualty_summary({}, session)

    assert len(facts) == 2
    injuries, deaths = facts
    assert injuries.metric == "casualty_summary"
    assert injuries.scope["category"] == "injuries"
    assert injuries.value == 2
    assert injuries.unit == "persons"
    assert injuries.breakdown is None
    assert injuries.citation.cid == "survey123-casualty_summary-0"

    assert deaths.scope["category"] == "deaths"
    assert deaths.value == 1
    assert deaths.citation.cid == "survey123-casualty_summary-1"


def test_casualty_summary_include_pending_widens_injuries_not_deaths(tmp_path):
    session = make_session(tmp_path)

    facts = casualty_summary({"include_pending": True}, session)

    injuries, deaths = facts
    assert injuries.value == 3
    assert injuries.verification == "mixed"
    assert deaths.value == 1
    assert deaths.verification == "validated"
