from datetime import datetime

from sqlalchemy.orm import sessionmaker

from app.db import Base, make_engine
from app.modules.sitreps.models import Event, SitrepIncident, SituationLog, Submission
from app.modules.whatsapp.confirm import ConfirmError, confirm_proposals
from app.modules.whatsapp.extract import ProposedIncident, ProposedLog

CORP = "diego_martin_regional_corporati"
OTHER = "sangre_grande_regional_corporat"


def make_session(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False)()


def _incident(**overrides) -> ProposedIncident:
    data = {
        "corporation": CORP,
        "community": "Petit Valley",
        "street": None,
        "incident_type": "flooding_",
        "incident_summary": "3 houses flooded",
        "event_date": "2026-08-15",
        "injuries_count": None,
        "deaths_count": None,
        "source_index": 1,
        "source_quote": "3 houses flooded in Petit Valley",
    }
    data.update(overrides)
    return ProposedIncident.model_validate(data)


def _log(**overrides) -> ProposedLog:
    data = {
        "corporation": CORP,
        "category": "resource",
        "statement": "200 sandbags remaining at depot",
        "item": "sandbags",
        "quantity": 200,
        "unit": "bags",
        "status": "available",
        "source_index": 2,
        "source_quote": "200 sandbags remaining at depot",
    }
    data.update(overrides)
    return ProposedLog.model_validate(data)


def test_rejects_empty_selection(tmp_path):
    session = make_session(tmp_path)

    try:
        confirm_proposals(
            session,
            as_at=datetime(2026, 8, 15, 16, 0),
            filename="chat.txt",
            incidents=[],
            logs=[],
        )
    except ConfirmError as exc:
        assert "select at least one" in str(exc).lower()
    else:
        raise AssertionError("expected ConfirmError")


def test_rejects_selected_row_without_corporation(tmp_path):
    session = make_session(tmp_path)

    try:
        confirm_proposals(
            session,
            as_at=datetime(2026, 8, 15, 16, 0),
            filename="chat.txt",
            incidents=[],
            logs=[_log(corporation=None)],
        )
    except ConfirmError as exc:
        assert "corporation" in str(exc).lower()
    else:
        raise AssertionError("expected ConfirmError")
    assert session.query(SituationLog).count() == 0


def test_unpassed_rows_never_land(tmp_path):
    session = make_session(tmp_path)
    kept = _log(statement="200 sandbags remaining")
    # The dropped row is simply not passed — confirm only sees selected rows.
    results = confirm_proposals(
        session,
        as_at=datetime(2026, 8, 15, 16, 0),
        filename="chat.txt",
        incidents=[],
        logs=[kept],
    )

    assert len(results) == 1
    assert session.query(SituationLog).count() == 1
    assert session.query(SituationLog).one().statement == "200 sandbags remaining"


def test_incidents_create_an_event_and_a_submission(tmp_path):
    session = make_session(tmp_path)
    as_at = datetime(2026, 8, 15, 16, 0)

    results = confirm_proposals(
        session,
        as_at=as_at,
        filename="group.txt",
        incidents=[_incident()],
        logs=[_log()],
    )

    assert len(results) == 1
    event = session.query(Event).one()
    assert event.corporation == CORP
    assert event.title == "WhatsApp update 2026-08-15"
    assert event.hazard_type == "other"
    submission = session.query(Submission).one()
    assert submission.event_id == event.id
    assert submission.source_file == "whatsapp:group.txt"
    assert submission.alert_level == "none"
    assert submission.situation_overview is None
    assert session.query(SitrepIncident).one().row_id == "wa-1"
    assert session.query(SituationLog).count() == 1


def test_logs_only_skip_the_event(tmp_path):
    session = make_session(tmp_path)

    confirm_proposals(
        session,
        as_at=datetime(2026, 8, 15, 16, 0),
        filename="chat.txt",
        incidents=[],
        logs=[_log()],
    )

    assert session.query(Event).count() == 0
    submission = session.query(Submission).one()
    assert submission.event_id is None
    assert submission.source_file == "whatsapp:chat.txt"


def test_phone_in_edited_statement_is_redacted_before_write(tmp_path):
    session = make_session(tmp_path)

    confirm_proposals(
        session,
        as_at=datetime(2026, 8, 15, 16, 0),
        filename="chat.txt",
        incidents=[],
        logs=[_log(statement="Call +1 868-555-1234 for the sandbag count: 200")],
    )

    stored = session.query(SituationLog).one().statement
    assert "+1 868-555-1234" not in stored
    assert "868-555-1234" not in stored
    assert "[phone]" in stored
    assert "200" in stored


def test_two_corporations_become_two_submissions(tmp_path):
    session = make_session(tmp_path)

    results = confirm_proposals(
        session,
        as_at=datetime(2026, 8, 15, 16, 0),
        filename="chat.txt",
        incidents=[],
        logs=[
            _log(corporation=CORP, statement="Diego Martin sandbags"),
            _log(corporation=OTHER, statement="Sangre Grande sandbags"),
        ],
    )

    assert len(results) == 2
    corps = {s.corporation for s in session.query(Submission).all()}
    assert corps == {CORP, OTHER}
