from datetime import datetime, timezone
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.contracts import SubmissionIngestResult
from app.core.jobs import enqueue
from app.core.llm import get_llm_client
from app.core.report_store import get_report, save_placeholder_report
from app.db import get_session
from app.quality.store import record_event
from app.modules.whatsapp.adjust import adjust_working_set
from app.modules.whatsapp.briefing import BRIEFING_TEMPLATE
from app.modules.whatsapp.confirm import ConfirmError, confirm_proposals
from app.modules.whatsapp.extract import (
    DraftIncident,
    DraftLog,
    ProposedIncident,
    ProposedLog,
)
from app.modules.whatsapp.facts import (
    included_attributed_incidents,
    included_attributed_logs,
)
from app.modules.whatsapp.models import WhatsAppDraft
from app.modules.whatsapp.parse import messages_from_source
from app.modules.whatsapp.store import (
    create_draft,
    draft_incidents,
    draft_logs,
    get_draft,
    list_drafts,
    update_draft,
)

router = APIRouter()


class DraftSummary(BaseModel):
    id: int
    filename: str
    source_kind: str
    as_at: datetime
    updated_at: datetime
    incident_count: int
    log_count: int


class DraftResponse(BaseModel):
    id: int
    draft_id: int
    filename: str
    source_kind: str
    as_at: datetime
    message_count: int
    pii_redacted: bool
    incidents: list[DraftIncident]
    logs: list[DraftLog]
    status: str
    error: str | None = None
    created_at: datetime
    updated_at: datetime


class DraftUpdateRequest(BaseModel):
    as_at: datetime | None = None
    incidents: list[DraftIncident]
    logs: list[DraftLog]


class AdjustRequest(BaseModel):
    instruction: str


class ConfirmRequest(BaseModel):
    as_at: datetime
    filename: str
    incidents: list[ProposedIncident] = []
    logs: list[ProposedLog] = []


class ConfirmResponse(BaseModel):
    submissions: list[SubmissionIngestResult]


class BriefingResponse(BaseModel):
    id: str
    status: str
    markdown: str
    error: str | None = None


def _as_response(draft: WhatsAppDraft) -> DraftResponse:
    return DraftResponse(
        id=draft.id,
        draft_id=draft.id,
        filename=draft.filename,
        source_kind=draft.source_kind,
        as_at=draft.as_at,
        message_count=draft.message_count,
        pii_redacted=draft.pii_redacted,
        incidents=draft_incidents(draft),
        logs=draft_logs(draft),
        status=draft.status,
        error=draft.error,
        created_at=draft.created_at,
        updated_at=draft.updated_at,
    )


def _require_draft(session: Session, draft_id: int) -> WhatsAppDraft:
    draft = get_draft(session, draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail=f"draft not found: {draft_id}")
    return draft


async def _read_source(
    file: UploadFile | None, text: str | None
) -> tuple[str, str, str, bool, int]:
    file_bytes = b""
    filename = ""
    if file is not None:
        filename = file.filename or ""
        file_bytes = await file.read()

    has_file = bool(file_bytes.strip())
    pasted = (text or "").strip()
    has_text = bool(pasted)

    if has_file and has_text:
        raise HTTPException(
            status_code=400, detail="send either a file or pasted text, not both"
        )
    if not has_file and not has_text:
        raise HTTPException(
            status_code=400,
            detail="paste the hour or upload a WhatsApp .txt export",
        )

    if has_file:
        if not filename.lower().endswith(".txt"):
            raise HTTPException(
                status_code=400, detail="upload a WhatsApp .txt export"
            )
        raw = file_bytes.decode("utf-8", errors="replace")
        messages, kind, pii = messages_from_source(raw)
        if not messages:
            raise HTTPException(status_code=400, detail="no messages found in export")
        return raw, filename or "export.txt", kind, pii, len(messages)

    messages, kind, pii = messages_from_source(pasted)
    if not messages:
        raise HTTPException(
            status_code=400,
            detail="paste the hour or upload a WhatsApp .txt export",
        )
    return pasted, "pasted.txt", kind, pii, len(messages)


@router.post("/whatsapp/extract", response_model=DraftResponse, status_code=202)
async def post_extract(
    file: UploadFile | None = File(None),
    text: str | None = Form(None),
    as_at: datetime | None = Form(None),
    session: Session = Depends(get_session),
) -> DraftResponse:
    raw, filename, source_kind, pii_redacted, message_count = await _read_source(
        file, text
    )

    draft = create_draft(
        session,
        filename=filename,
        as_at=as_at or datetime.now(timezone.utc).replace(tzinfo=None),
        message_count=message_count,
        pii_redacted=pii_redacted,
        incidents=[],
        logs=[],
        status="queued",
        source_text=raw,
        source_kind=source_kind,
    )
    enqueue("extract_whatsapp", draft_id=draft.id)
    record_event(
        session,
        workflow="whatsapp_briefing",
        step="extract",
        outcome="started",
        subject_id=str(draft.id),
    )
    session.expire_all()
    draft = _require_draft(session, draft.id)
    return _as_response(draft)


@router.get("/whatsapp/drafts", response_model=list[DraftSummary])
def get_drafts(
    limit: int = 10, session: Session = Depends(get_session)
) -> list[DraftSummary]:
    return [
        DraftSummary(
            id=draft.id,
            filename=draft.filename,
            source_kind=draft.source_kind,
            as_at=draft.as_at,
            updated_at=draft.updated_at,
            incident_count=len(draft.incidents or []),
            log_count=len(draft.logs or []),
        )
        for draft in list_drafts(session, limit=limit)
    ]


@router.get("/whatsapp/drafts/{draft_id}", response_model=DraftResponse)
def get_draft_detail(
    draft_id: int, session: Session = Depends(get_session)
) -> DraftResponse:
    return _as_response(_require_draft(session, draft_id))


@router.put("/whatsapp/drafts/{draft_id}", response_model=DraftResponse)
def put_draft(
    draft_id: int,
    request: DraftUpdateRequest,
    session: Session = Depends(get_session),
) -> DraftResponse:
    draft = _require_draft(session, draft_id)
    return _as_response(
        update_draft(
            session,
            draft,
            as_at=request.as_at,
            incidents=request.incidents,
            logs=request.logs,
        )
    )


@router.post("/whatsapp/drafts/{draft_id}/adjust", response_model=DraftResponse)
def post_adjust(
    draft_id: int,
    request: AdjustRequest,
    session: Session = Depends(get_session),
) -> DraftResponse:
    draft = _require_draft(session, draft_id)
    try:
        incidents, logs = adjust_working_set(
            draft_incidents(draft),
            draft_logs(draft),
            request.instruction,
            get_llm_client("chat"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _as_response(update_draft(session, draft, incidents=incidents, logs=logs))


@router.post("/whatsapp/drafts/{draft_id}/briefing", response_model=BriefingResponse, status_code=202)
def post_briefing(
    draft_id: int, session: Session = Depends(get_session)
) -> BriefingResponse:
    draft = _require_draft(session, draft_id)
    incidents = draft_incidents(draft)
    logs = draft_logs(draft)
    if not included_attributed_incidents(incidents) and not included_attributed_logs(logs):
        raise HTTPException(
            status_code=400,
            detail="include at least one row with a corporation to generate a briefing",
        )

    report_id = str(uuid.uuid4())
    save_placeholder_report(
        session,
        report_id=report_id,
        template=BRIEFING_TEMPLATE,
        params={"as_at": draft.as_at.isoformat()},
        data_requirements=[],
    )
    enqueue("generate_briefing", draft_id=draft.id, report_id=report_id)
    record_event(
        session,
        workflow="whatsapp_briefing",
        step="briefing",
        outcome="started",
        subject_id=report_id,
    )
    session.expire_all()
    row = get_report(report_id, session)
    if row is None:
        raise HTTPException(status_code=500, detail="briefing placeholder missing after enqueue")
    return BriefingResponse(
        id=row.id, status=row.status, markdown=row.markdown, error=row.error
    )


@router.post("/whatsapp/drafts/{draft_id}/promote", response_model=ConfirmResponse)
def post_promote(
    draft_id: int, session: Session = Depends(get_session)
) -> ConfirmResponse:
    draft = _require_draft(session, draft_id)
    incidents = [
        ProposedIncident.model_validate(row.model_dump())
        for row in included_attributed_incidents(draft_incidents(draft))
    ]
    logs = [
        ProposedLog.model_validate(row.model_dump())
        for row in included_attributed_logs(draft_logs(draft))
    ]
    try:
        submissions = confirm_proposals(
            session,
            as_at=draft.as_at,
            filename=draft.filename,
            incidents=incidents,
            logs=logs,
        )
    except ConfirmError as extra:
        raise HTTPException(status_code=400, detail=str(extra)) from extra
    return ConfirmResponse(submissions=submissions)


@router.post("/whatsapp/confirm", response_model=ConfirmResponse)
def post_confirm(
    request: ConfirmRequest, session: Session = Depends(get_session)
) -> ConfirmResponse:
    try:
        submissions = confirm_proposals(
            session,
            as_at=request.as_at,
            filename=request.filename,
            incidents=request.incidents,
            logs=request.logs,
        )
    except ConfirmError as extra:
        raise HTTPException(status_code=400, detail=str(extra)) from extra
    return ConfirmResponse(submissions=submissions)
