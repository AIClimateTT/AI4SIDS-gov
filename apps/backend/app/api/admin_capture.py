"""Admin review of corp capture sessions, drafts included.

Drafts are the officer's unfinished work: the register shows that they exist
and the transcript export is the only way into one. Filed sessions are already
readable through submissions and reports; the export adds the conversation
behind them."""

import json
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.dependencies import require_admin_user
from app.db import get_session
from app.modules.capture.models import CaptureSession
from app.modules.capture.store import get_session_row, list_sessions
from app.modules.capture.transcript import build_transcript, transcript_markdown
from app.modules.sitreps.store import get_event
from app.modules.survey123.normalize import CANONICAL_CORPORATIONS

router = APIRouter(
    prefix="/admin/capture", dependencies=[Depends(require_admin_user)]
)


class AdminCaptureSessionSummary(BaseModel):
    id: int
    corporation: str
    event_id: int | None
    status: str
    as_at: datetime
    message_count: int
    officer_message_count: int
    submission_id: int | None
    report_id: str | None
    has_sitrep: bool
    created_at: datetime
    updated_at: datetime


def _summary(row: CaptureSession) -> AdminCaptureSessionSummary:
    messages = row.messages or []
    return AdminCaptureSessionSummary(
        id=row.id,
        corporation=row.corporation,
        event_id=row.event_id,
        status=row.status,
        as_at=row.as_at,
        message_count=len(messages),
        officer_message_count=sum(
            1 for item in messages if isinstance(item, dict) and item.get("role") == "user"
        ),
        submission_id=row.submission_id,
        report_id=row.report_id,
        has_sitrep=row.sitrep_markdown is not None,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("/sessions", response_model=list[AdminCaptureSessionSummary])
def get_admin_sessions(
    corporation: str, db: Session = Depends(get_session)
) -> list[AdminCaptureSessionSummary]:
    if corporation not in CANONICAL_CORPORATIONS:
        raise HTTPException(status_code=400, detail=f"unknown corporation: {corporation}")
    return [_summary(row) for row in list_sessions(db, corporation=corporation)]


@router.get("/sessions/{session_id}/transcript")
def get_transcript(
    session_id: int,
    format: Literal["json", "md"] = "json",
    db: Session = Depends(get_session),
) -> Response:
    row = get_session_row(db, session_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"capture session not found: {session_id}")
    event = get_event(db, row.event_id) if row.event_id is not None else None
    data = build_transcript(row, event)
    stamp = row.updated_at.strftime("%Y%m%d-%H%M")
    name = f"capture-{row.corporation}-{row.id}-{row.status}-{stamp}.{format}"
    if format == "md":
        content, media_type = transcript_markdown(data), "text/markdown; charset=utf-8"
    else:
        content, media_type = json.dumps(data, indent=2), "application/json"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )
