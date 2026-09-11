from datetime import datetime

from sqlalchemy.orm import sessionmaker

from app.db import Base, make_engine
from app.modules.whatsapp.extract import DraftIncident, DraftLog
from app.modules.whatsapp.store import (
    attach_briefing_report,
    create_draft,
    draft_incidents,
    get_draft,
    list_drafts,
    update_draft,
)

CORP = "diego_martin_regional_corporati"


def make_session(tmp_path):
    import app.modules.whatsapp.models  # noqa: F401

    engine = make_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_create_and_reload_draft(tmp_path):
    session = make_session(tmp_path)
    draft = create_draft(
        session,
        filename="hour.txt",
        as_at=datetime(2026, 8, 15, 16, 0),
        message_count=2,
        pii_redacted=True,
        incidents=[
            DraftIncident(
                corporation=CORP,
                incident_summary="3 houses flooded",
                source_index=1,
                source_quote="3 houses flooded",
                included=True,
            )
        ],
        logs=[],
    )

    loaded = get_draft(session, draft.id)
    assert loaded is not None
    rows = draft_incidents(loaded)
    assert rows[0].incident_summary == "3 houses flooded"
    assert rows[0].included is True
    assert loaded.pii_redacted is True
    assert loaded.source_kind == "export"


def test_update_draft_redacts_phones(tmp_path):
    session = make_session(tmp_path)
    draft = create_draft(
        session,
        filename="hour.txt",
        as_at=datetime(2026, 8, 15, 16, 0),
        message_count=1,
        pii_redacted=False,
        incidents=[],
        logs=[
            DraftLog(
                corporation=CORP,
                statement="200 sandbags",
                source_index=1,
                source_quote="200 sandbags",
                included=True,
            )
        ],
    )

    update_draft(
        session,
        draft,
        logs=[
            DraftLog(
                corporation=CORP,
                statement="Call +1 868-555-1234 for 200 sandbags",
                source_index=1,
                source_quote="Call +1 868-555-1234 for 200 sandbags",
                included=True,
            )
        ],
    )

    from app.modules.whatsapp.store import draft_logs

    log = draft_logs(get_draft(session, draft.id))[0]
    assert "+1 868-555-1234" not in log.statement
    assert "[phone]" in log.statement
    assert "200" in log.statement


def test_list_drafts_newest_first(tmp_path):
    session = make_session(tmp_path)
    create_draft(
        session,
        filename="older.txt",
        as_at=datetime(2026, 8, 15, 15, 0),
        message_count=0,
        pii_redacted=False,
        incidents=[],
        logs=[],
    )
    create_draft(
        session,
        filename="newer.txt",
        as_at=datetime(2026, 8, 15, 16, 0),
        message_count=0,
        pii_redacted=False,
        incidents=[],
        logs=[],
    )

    listed = list_drafts(session, limit=10)
    assert [d.filename for d in listed] == ["newer.txt", "older.txt"]


def test_attach_briefing_report_does_not_bump_updated_at(tmp_path):
    session = make_session(tmp_path)
    draft = create_draft(
        session,
        filename="hour.txt",
        as_at=datetime(2026, 8, 15, 16, 0),
        message_count=0,
        pii_redacted=False,
        incidents=[],
        logs=[],
    )
    before = draft.updated_at

    attached = attach_briefing_report(session, draft, "report-1")
    assert attached.briefing_report_id == "report-1"
    assert attached.updated_at == before
