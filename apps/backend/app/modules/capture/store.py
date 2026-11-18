from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.localtime import to_local
from app.modules.capture.missing import missing_fields
from app.modules.capture.models import CaptureSession, CaptureTurn
from app.prompts.registry import Prompt
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
        alert_detail=row.alert_detail,
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
    row.alert_detail = working.alert_detail
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
    event_id: int | None = None,
) -> CaptureSession:
    existing = [
        row
        for row in list_sessions(db, corporation=corporation, event_id=event_id)
        if row.status == "draft" and row.event_id == event_id
    ]
    if existing:
        return existing[0]
    now = _now()
    opening = CaptureMessage(role="assistant", content=OPENING_MESSAGE, created_at=now)
    row = CaptureSession(
        corporation=corporation,
        event_id=event_id,
        status="draft",
        # A wall-clock reading like the officer's own entry, not UTC.
        as_at=to_local(datetime.now(timezone.utc)).replace(tzinfo=None),
        alert_level="none",
        alert_detail=None,
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
    db: Session, *, corporation: str, event_id: int | None = None
) -> list[CaptureSession]:
    stmt = select(CaptureSession).where(CaptureSession.corporation == corporation)
    if event_id is not None:
        stmt = stmt.where(CaptureSession.event_id == event_id)
    stmt = stmt.order_by(CaptureSession.updated_at.desc(), CaptureSession.id.desc())
    return list(db.scalars(stmt).all())


def save_session(
    db: Session, row: CaptureSession, *, touch: bool = True
) -> CaptureSession:
    if touch:
        row.updated_at = _now()
    db.commit()
    db.refresh(row)
    return row


def session_missing(row: CaptureSession) -> list[MissingField]:
    return missing_fields(working_set_from_session(row))


def record_turn(
    db: Session,
    row: CaptureSession,
    kind: str,
    *,
    user_message: str | None = None,
    assistant_message: str | None = None,
    raw_output: str | None = None,
    parse_ok: bool | None = None,
    template_version: int | None = None,
    sitrep_markdown: str | None = None,
    prompt: Prompt | None = None,
    model: str | None = None,
    retried: bool | None = None,
    interventions: dict[str, int] | None = None,
) -> CaptureTurn:
    """Snapshot the session's working set as it stands after a change."""
    seq = (
        db.scalar(
            select(func.max(CaptureTurn.seq)).where(CaptureTurn.session_id == row.id)
        )
        or 0
    ) + 1
    turn = CaptureTurn(
        session_id=row.id,
        seq=seq,
        kind=kind,
        user_message=user_message,
        assistant_message=assistant_message,
        raw_output=raw_output,
        parse_ok=parse_ok,
        template_version=template_version,
        prompt_id=prompt.id if prompt else None,
        prompt_version=prompt.version if prompt else None,
        prompt_hash=prompt.hash if prompt else None,
        model=model,
        retried=retried,
        interventions=interventions,
        working=working_set_from_session(row).model_dump(mode="json"),
        missing=[item.model_dump() for item in session_missing(row)],
        sitrep_markdown=sitrep_markdown,
        created_at=_now(),
    )
    db.add(turn)
    db.commit()
    return turn


def list_turns(db: Session, session_id: int) -> list[CaptureTurn]:
    return list(
        db.scalars(
            select(CaptureTurn)
            .where(CaptureTurn.session_id == session_id)
            .order_by(CaptureTurn.seq)
        ).all()
    )


def refresh_as_at(row: CaptureSession) -> None:
    """A sitrep is as at the latest information in it, not when the session
    opened. Siparia's report, opened Nov 13 and last updated Nov 16, went out
    as at Nov 13. An as-at the officer typed is theirs and stays."""
    if "as_at" in (row.manual_fields or []):
        return
    row.as_at = to_local(datetime.now(timezone.utc)).replace(tzinfo=None)
