from datetime import datetime

from sqlalchemy.orm import sessionmaker

from app.db import Base, make_engine
from app.modules.sitreps.models import (
    ALERT_LEVELS,
    HAZARD_TYPES,
    LOG_CATEGORIES,
    Event,
    SitrepIncident,
    SituationLog,
    Submission,
)


def make_session(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_submission_can_hang_off_an_event(tmp_path):
    session = make_session(tmp_path)
    event = Event(
        corporation="diego_martin_regional_corporati",
        title="Adverse Weather June 2023",
        hazard_type="wind",
        started_at=datetime(2023, 6, 27),
        created_at=datetime(2023, 6, 27),
    )
    session.add(event)
    session.flush()

    submission = Submission(
        corporation="diego_martin_regional_corporati",
        event_id=event.id,
        as_at=datetime(2023, 6, 30, 16, 0),
        alert_level="discontinued",
        present_activity="Adverse Weather Alert",
        situation_overview="Heavy rainfall and high winds affected the Borough.",
        sequence_no=4,
        ingested_at=datetime(2023, 6, 30, 16, 5),
    )
    session.add(submission)
    session.commit()

    stored = session.query(Submission).one()
    assert stored.event_id == event.id
    assert stored.sequence_no == 4
    assert stored.alert_level == "discontinued"


def test_submission_without_an_event_is_allowed(tmp_path):
    session = make_session(tmp_path)
    session.add(
        Submission(
            corporation="siparia_regional_corporation",
            event_id=None,
            as_at=datetime(2024, 1, 5, 9, 0),
            alert_level="none",
            ingested_at=datetime(2024, 1, 5, 9, 1),
        )
    )
    session.commit()

    assert session.query(Submission).one().event_id is None


def test_sitrep_incident_record_ref_is_stable(tmp_path):
    session = make_session(tmp_path)
    session.add(
        Submission(
            corporation="diego_martin_regional_corporati",
            as_at=datetime(2023, 6, 27),
            alert_level="yellow",
            ingested_at=datetime(2023, 6, 27),
        )
    )
    session.flush()
    incident = SitrepIncident(
        submission_id=1,
        corporation="diego_martin_regional_corporati",
        event_id=None,
        row_id="1",
        incident_type="fallen_tree",
        event_date=datetime(2023, 6, 27),
        ingested_at=datetime(2023, 6, 27),
    )
    session.add(incident)
    session.commit()

    assert incident.record_ref == "diego_martin_regional_corporati:-:1:1"


def test_situation_log_quantity_is_optional(tmp_path):
    session = make_session(tmp_path)
    session.add(
        Submission(
            corporation="tunapuna_piarco_regional_corpor",
            as_at=datetime(2025, 5, 18, 18, 30),
            alert_level="yellow",
            ingested_at=datetime(2025, 5, 18, 18, 30),
        )
    )
    session.flush()
    session.add_all(
        [
            SituationLog(
                submission_id=1,
                category="activity",
                statement="Tree cutting team on stand by",
            ),
            SituationLog(
                submission_id=1,
                category="resource",
                statement="200 sandbags available for distribution",
                item="sandbags",
                quantity=200,
                unit="bags",
                status="available",
            ),
        ]
    )
    session.commit()

    logs = session.query(SituationLog).order_by(SituationLog.id).all()
    assert logs[0].quantity is None
    assert logs[1].quantity == 200


def test_enum_tuples_match_the_spec():
    assert ALERT_LEVELS == ("green", "yellow", "orange", "red", "discontinued", "none")
    assert HAZARD_TYPES == ("flood", "landslide", "wind", "fire", "other")
    assert LOG_CATEGORIES == (
        "resource",
        "personnel",
        "facility",
        "activity",
        "relief_distributed",
        "other",
    )


def test_record_ref_distinguishes_rows_from_different_submissions(tmp_path):
    # Previously "corp:-:1" for every event-less row, so one identifier named
    # many rows and no auditor could trace a figure back to one of them.
    from datetime import datetime

    from app.modules.sitreps.models import SitrepIncident

    session = make_session(tmp_path)
    first = SitrepIncident(
        submission_id=1,
        corporation="diego_martin_regional_corporati",
        event_id=None,
        row_id="1",
        ingested_at=datetime(2023, 6, 27),
    )
    second = SitrepIncident(
        submission_id=2,
        corporation="diego_martin_regional_corporati",
        event_id=None,
        row_id="1",
        ingested_at=datetime(2023, 6, 28),
    )

    assert first.record_ref != second.record_ref
