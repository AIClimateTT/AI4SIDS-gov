from datetime import date, datetime

import pytest
from sqlalchemy.orm import sessionmaker

from app.db import Base, make_engine
from app.modules.sitreps.minister_metrics import corporation_status
from app.modules.sitreps.models import Event, SitrepIncident, SituationLog, Submission
from app.modules.sitreps.module import sitrep_module

ARIMA = "arima_borough_corporation"
SIPARIA = "siparia_regional_corporation"
WINDOW = {"date_from": "2026-08-21", "date_to": "2026-08-22"}


@pytest.fixture
def db(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/m.db")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _event(db, corporation=ARIMA) -> Event:
    event = Event(
        corporation=corporation,
        title="Flood",
        hazard_type="flood",
        started_at=datetime(2026, 8, 21),
        created_at=datetime(2026, 8, 21),
    )
    db.add(event)
    db.flush()
    return event


def _submission(db, as_at, event=None, corporation=ARIMA, sequence=1) -> Submission:
    row = Submission(
        corporation=corporation,
        event_id=event.id if event else None,
        as_at=as_at,
        sequence_no=sequence,
        ingested_at=as_at,
    )
    db.add(row)
    db.flush()
    return row


def _log(db, submission, statement, quantity=None) -> None:
    db.add(
        SituationLog(
            submission_id=submission.id,
            category="activity",
            statement=statement,
            quantity=quantity,
        )
    )
    db.flush()


def _incident(db, submission, row_id, incident_type) -> None:
    db.add(
        SitrepIncident(
            submission_id=submission.id,
            corporation=submission.corporation,
            event_id=submission.event_id,
            row_id=row_id,
            incident_type=incident_type,
            event_date=date(2026, 8, 21),
            ingested_at=datetime(2026, 8, 21),
        )
    )
    db.flush()


def test_uses_latest_submission_in_window(db):
    early = _submission(db, datetime(2026, 8, 21, 14))
    late = _submission(db, datetime(2026, 8, 21, 20))
    _log(db, early, "Sandbags filled")
    _log(db, late, "CERT on standby")

    facts = corporation_status(WINDOW, db)

    assert [fact.value for fact in facts] == ["CERT on standby"]
    assert facts[0].scope["corporation"] == ARIMA
    assert facts[0].scope["kind"] == "log"


def test_each_corporation_gets_its_own_latest(db):
    _log(db, _submission(db, datetime(2026, 8, 21, 14)), "Arima log")
    _log(db, _submission(db, datetime(2026, 8, 21, 14), corporation=SIPARIA), "Siparia log")

    facts = corporation_status(WINDOW, db)

    assert {(f.scope["corporation"], f.value) for f in facts} == {
        (ARIMA, "Arima log"),
        (SIPARIA, "Siparia log"),
    }


def test_excludes_submission_outside_window_even_if_its_event_is_open(db):
    event = _event(db)
    before = _submission(db, datetime(2026, 8, 20, 14), event)
    _log(db, before, "Sandbags filled")
    _incident(db, before, "1", "landslide")

    assert corporation_status(WINDOW, db) == []


def test_incident_breakdown_is_cumulative_for_the_event(db):
    event = _event(db)
    first = _submission(db, datetime(2026, 8, 21, 14), event, sequence=1)
    second = _submission(db, datetime(2026, 8, 21, 20), event, sequence=2)
    _incident(db, first, "1", "landslide")
    _incident(db, first, "2", "landslide")
    _incident(db, second, "3", "flooding_")

    facts = corporation_status(WINDOW, db)

    assert len(facts) == 1
    assert facts[0].scope["kind"] == "incidents"
    assert facts[0].value == 3
    assert facts[0].breakdown == {"landslide": 2, "flooding_": 1}


def test_statement_is_verbatim_even_when_the_row_has_a_quantity(db):
    row = _submission(db, datetime(2026, 8, 21, 14))
    _log(db, row, "200 sandbags available for distribution", quantity=200)

    facts = corporation_status(WINDOW, db)

    assert facts[0].value == "200 sandbags available for distribution"


def test_facts_are_marked_unverified_and_cite_their_rows(db):
    row = _submission(db, datetime(2026, 8, 21, 14))
    _log(db, row, "CERT on standby")

    fact = corporation_status(WINDOW, db)[0]

    assert fact.verification == "pending"
    assert fact.citation.module == "sitreps"
    assert fact.citation.record_ids


def test_the_sitreps_module_offers_it(db):
    _log(db, _submission(db, datetime(2026, 8, 21, 14)), "CERT on standby")

    assert "corporation_status" in {spec.name for spec in sitrep_module.list_metrics()}
    assert sitrep_module.run_metric("corporation_status", WINDOW, db)[0].value == "CERT on standby"
