from datetime import datetime

from sqlalchemy.orm import sessionmaker

from app.db import Base, make_engine
from app.modules.sitreps.store import (
    create_event,
    create_submission,
    get_event,
    latest_submission,
    list_events,
    next_sequence_no,
)

CORP = "diego_martin_regional_corporati"
OTHER_CORP = "siparia_regional_corporation"


def make_session(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_create_event_returns_a_persisted_event(tmp_path):
    session = make_session(tmp_path)

    event = create_event(
        session,
        corporation=CORP,
        title="Adverse Weather June 2023",
        hazard_type="wind",
        started_at=datetime(2023, 6, 27),
    )

    assert event.id is not None
    assert event.ended_at is None
    assert get_event(session, event.id).title == "Adverse Weather June 2023"


def test_list_events_is_scoped_to_one_corporation(tmp_path):
    session = make_session(tmp_path)
    create_event(
        session, corporation=CORP, title="Mine", hazard_type="flood",
        started_at=datetime(2023, 6, 27),
    )
    create_event(
        session, corporation=OTHER_CORP, title="Theirs", hazard_type="flood",
        started_at=datetime(2023, 6, 27),
    )

    titles = [e.title for e in list_events(session, CORP)]
    assert titles == ["Mine"]


def test_sequence_no_increments_per_event(tmp_path):
    session = make_session(tmp_path)
    event = create_event(
        session, corporation=CORP, title="Storm", hazard_type="wind",
        started_at=datetime(2023, 6, 27),
    )

    first = create_submission(
        session, corporation=CORP, as_at=datetime(2023, 6, 27, 9), event_id=event.id
    )
    second = create_submission(
        session, corporation=CORP, as_at=datetime(2023, 6, 28, 9), event_id=event.id
    )

    assert first.sequence_no == 1
    assert second.sequence_no == 2
    assert next_sequence_no(session, CORP, event.id) == 3


def test_event_less_submissions_always_start_at_one(tmp_path):
    session = make_session(tmp_path)

    first = create_submission(session, corporation=CORP, as_at=datetime(2024, 1, 5, 9))
    second = create_submission(session, corporation=CORP, as_at=datetime(2024, 1, 6, 9))

    assert first.sequence_no == 1
    assert second.sequence_no == 1


def test_latest_submission_picks_the_newest_as_at(tmp_path):
    session = make_session(tmp_path)
    event = create_event(
        session, corporation=CORP, title="Storm", hazard_type="wind",
        started_at=datetime(2023, 6, 27),
    )
    create_submission(
        session, corporation=CORP, as_at=datetime(2023, 6, 27, 9), event_id=event.id,
        alert_level="yellow",
    )
    create_submission(
        session, corporation=CORP, as_at=datetime(2023, 6, 30, 16), event_id=event.id,
        alert_level="discontinued",
    )

    assert latest_submission(session, CORP, event.id).alert_level == "discontinued"


def test_latest_submission_returns_none_when_corp_has_not_reported(tmp_path):
    session = make_session(tmp_path)

    assert latest_submission(session, CORP) is None
