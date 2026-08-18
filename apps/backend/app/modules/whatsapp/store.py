from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.whatsapp.extract import (
    DraftIncident,
    DraftLog,
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
) -> WhatsAppDraft:
    if as_at is not None:
        draft.as_at = as_at
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


def draft_incidents(draft: WhatsAppDraft) -> list[DraftIncident]:
    return [DraftIncident.model_validate(row) for row in draft.incidents]


def draft_logs(draft: WhatsAppDraft) -> list[DraftLog]:
    return [DraftLog.model_validate(row) for row in draft.logs]
