from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.capture.missing import missing_fields
from app.modules.capture.models import CaptureSession
from app.modules.capture.schemas import (
    CaptureIncident,
    CaptureLog,
    CaptureMessage,
    CaptureWorkingSet,
    MissingField,
)


OPENING_MESSAGE = (
    "Tell me what is happening in your region. I will capture incidents and "
    "situation logs as we go, and ask if something needed for the report is missing."
)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def working_set_from_session(row: CaptureSession) -> CaptureWorkingSet:
    return CaptureWorkingSet(
        as_at=row.as_at,
        alert_level=row.alert_level,
        present_activity=row.present_activity,
        situation_overview=row.situation_overview,
        incidents=[CaptureIncident.model_validate(item) for item in (row.incidents or [])],
        logs=[CaptureLog.model_validate(item) for item in (row.logs or [])],
        manual_fields=list(row.manual_fields or []),
    )


def apply_working_set(row: CaptureSession, working: CaptureWorkingSet) -> None:
    if working.as_at is not None:
        row.as_at = working.as_at
    row.alert_level = working.alert_level
    row.present_activity = working.present_activity
    row.situation_overview = working.situation_overview
    row.incidents = [item.model_dump(mode="json") for item in working.incidents]
    row.logs = [item.model_dump(mode="json") for item in working.logs]
    row.manual_fields = list(working.manual_fields)


def session_messages(row: CaptureSession) -> list[CaptureMessage]:
    return [CaptureMessage.model_validate(item) for item in (row.messages or [])]


def create_session(
    db: Session,
    *,
    corporation: str,
    event_id: int,
) -> CaptureSession:
    existing = [
        row
        for row in list_sessions(db, corporation=corporation, event_id=event_id)
        if row.status == "draft"
    ]
    if existing:
        return existing[0]
    now = _now()
    opening = CaptureMessage(role="assistant", content=OPENING_MESSAGE, created_at=now)
    row = CaptureSession(
        corporation=corporation,
        event_id=event_id,
        status="draft",
        as_at=now,
        alert_level="none",
        present_activity=None,
        situation_overview=None,
        incidents=[],
        logs=[],
        manual_fields=[],
        messages=[opening.model_dump(mode="json")],
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_session_row(db: Session, session_id: int) -> CaptureSession | None:
    return db.get(CaptureSession, session_id)


def list_sessions(
    db: Session, *, corporation: str, event_id: int
) -> list[CaptureSession]:
    stmt = (
        select(CaptureSession)
        .where(
            CaptureSession.corporation == corporation,
            CaptureSession.event_id == event_id,
        )
        .order_by(CaptureSession.updated_at.desc(), CaptureSession.id.desc())
    )
    return list(db.scalars(stmt).all())


def save_session(db: Session, row: CaptureSession) -> CaptureSession:
    row.updated_at = _now()
    db.commit()
    db.refresh(row)
    return row


def session_missing(row: CaptureSession) -> list[MissingField]:
    return missing_fields(working_set_from_session(row))
