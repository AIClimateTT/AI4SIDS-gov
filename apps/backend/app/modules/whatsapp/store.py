from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.whatsapp.extract import (
    DraftIncident,
    DraftLog,
    WhatsAppMessage,
    WhatsAppWorkingSet,
    coerce_draft_incidents,
    coerce_draft_logs,
    redact_draft_incidents,
    redact_draft_logs,
)
from app.modules.whatsapp.models import WhatsAppDraft


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def create_draft(
    session: Session,
    *,
    filename: str,
    as_at: datetime,
    message_count: int,
    pii_redacted: bool,
    incidents: list[DraftIncident],
    logs: list[DraftLog],
    status: str = "ready",
    source_text: str | None = None,
    source_kind: str = "export",
    error: str | None = None,
    messages: list[WhatsAppMessage] | None = None,
    manual_fields: list[str] | None = None,
) -> WhatsAppDraft:
    now = _now()
    draft = WhatsAppDraft(
        filename=filename,
        as_at=as_at,
        message_count=message_count,
        pii_redacted=pii_redacted,
        incidents=[
            row.model_dump() for row in redact_draft_incidents(incidents)
        ],
        logs=[row.model_dump() for row in redact_draft_logs(logs)],
        messages=[item.model_dump(mode="json") for item in (messages or [])],
        manual_fields=list(manual_fields or []),
        status=status,
        error=error,
        source_text=source_text,
        source_kind=source_kind,
        created_at=now,
        updated_at=now,
    )
    session.add(draft)
    session.commit()
    session.refresh(draft)
    return draft


def get_draft(session: Session, draft_id: int) -> WhatsAppDraft | None:
    return session.get(WhatsAppDraft, draft_id)


def list_drafts(session: Session, *, limit: int = 10) -> list[WhatsAppDraft]:
    stmt = (
        select(WhatsAppDraft)
        .order_by(WhatsAppDraft.updated_at.desc(), WhatsAppDraft.id.desc())
        .limit(limit)
    )
    return list(session.scalars(stmt).all())


def update_draft(
    session: Session,
    draft: WhatsAppDraft,
    *,
    as_at: datetime | None = None,
    incidents: list[DraftIncident] | None = None,
    logs: list[DraftLog] | None = None,
    messages: list[WhatsAppMessage] | None = None,
    manual_fields: list[str] | None = None,
) -> WhatsAppDraft:
    if as_at is not None:
        draft.as_at = as_at
    if incidents is not None:
        draft.incidents = [
            row.model_dump() for row in redact_draft_incidents(incidents)
        ]
    if logs is not None:
        draft.logs = [row.model_dump() for row in redact_draft_logs(logs)]
    if messages is not None:
        draft.messages = [item.model_dump(mode="json") for item in messages]
    if manual_fields is not None:
        draft.manual_fields = list(manual_fields)
    draft.updated_at = _now()
    session.commit()
    session.refresh(draft)
    return draft


def draft_incidents(draft: WhatsAppDraft) -> list[DraftIncident]:
    return coerce_draft_incidents(draft.incidents)


def draft_logs(draft: WhatsAppDraft) -> list[DraftLog]:
    return coerce_draft_logs(draft.logs)


def draft_messages(draft: WhatsAppDraft) -> list[WhatsAppMessage]:
    return [
        WhatsAppMessage.model_validate(item) for item in (draft.messages or [])
    ]


def draft_manual_fields(draft: WhatsAppDraft) -> list[str]:
    return [str(item) for item in (draft.manual_fields or [])]


def working_set_from_draft(draft: WhatsAppDraft) -> WhatsAppWorkingSet:
    return WhatsAppWorkingSet(
        as_at=draft.as_at,
        incidents=draft_incidents(draft),
        logs=draft_logs(draft),
        manual_fields=draft_manual_fields(draft),
    )


def mark_draft_running(draft: WhatsAppDraft, session: Session) -> WhatsAppDraft:
    draft.status = "running"
    draft.error = None
    draft.updated_at = _now()
    session.commit()
    session.refresh(draft)
    return draft


def mark_draft_failed(draft: WhatsAppDraft, session: Session, error: str) -> WhatsAppDraft:
    draft.status = "failed"
    draft.error = error[:2000]
    draft.updated_at = _now()
    session.commit()
    session.refresh(draft)
    return draft


def mark_draft_ready(
    draft: WhatsAppDraft,
    session: Session,
    *,
    incidents: list[DraftIncident],
    logs: list[DraftLog],
) -> WhatsAppDraft:
    return update_draft_status(
        session,
        draft,
        status="ready",
        incidents=incidents,
        logs=logs,
        error=None,
    )


def update_draft_status(
    session: Session,
    draft: WhatsAppDraft,
    *,
    status: str,
    incidents: list[DraftIncident] | None = None,
    logs: list[DraftLog] | None = None,
    error: str | None = None,
) -> WhatsAppDraft:
    draft.status = status
    draft.error = error
    if incidents is not None:
        draft.incidents = [
            row.model_dump() for row in redact_draft_incidents(incidents)
        ]
    if logs is not None:
        draft.logs = [row.model_dump() for row in redact_draft_logs(logs)]
    draft.updated_at = _now()
    session.commit()
    session.refresh(draft)
    return draft
