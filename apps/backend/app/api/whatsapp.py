from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.contracts import SubmissionIngestResult
from app.core.llm import get_default_llm_client
from app.core.report_store import save_report
from app.db import get_session
from app.modules.whatsapp.adjust import adjust_working_set
from app.modules.whatsapp.briefing import BriefingError, generate_briefing
from app.modules.whatsapp.confirm import ConfirmError, confirm_proposals
from app.modules.whatsapp.extract import (
    DraftIncident,
    DraftLog,
    ExtractionResult,
    ProposedIncident,
    ProposedLog,
    extract_proposals,
    to_draft_incidents,
    to_draft_logs,
)
from app.modules.whatsapp.facts import (
    included_attributed_incidents,
    included_attributed_logs,
)
from app.modules.whatsapp.models import WhatsAppDraft
from app.modules.whatsapp.parse import parse_export, redact_phones
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
    as_at: datetime
    updated_at: datetime
    incident_count: int
    log_count: int


class DraftResponse(BaseModel):
    id: int
    draft_id: int
    filename: str
    as_at: datetime
    message_count: int
    pii_redacted: bool
    incidents: list[DraftIncident]
    logs: list[DraftLog]
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


def _as_response(draft: WhatsAppDraft) -> DraftResponse:
    return DraftResponse(
        id=draft.id,
        draft_id=draft.id,
        filename=draft.filename,
        as_at=draft.as_at,
        message_count=draft.message_count,
        pii_redacted=draft.pii_redacted,
        incidents=draft_incidents(draft),
        logs=draft_logs(draft),
        created_at=draft.created_at,
        updated_at=draft.updated_at,
    )


def _require_draft(session: Session, draft_id: int) -> WhatsAppDraft:
    draft = get_draft(session, draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail=f"draft not found: {draft_id}")
    return draft


@router.post("/whatsapp/extract", response_model=DraftResponse)
async def post_extract(
    file: UploadFile,
    as_at: datetime | None = Form(None),
    session: Session = Depends(get_session),
) -> DraftResponse:
    filename = file.filename or "export.txt"
    if not filename.lower().endswith(".txt"):
        raise HTTPException(status_code=400, detail="upload a WhatsApp .txt export")

    raw_bytes = await file.read()
    if not raw_bytes.strip():
        raise HTTPException(status_code=400, detail="export is empty")

    text = raw_bytes.decode("utf-8", errors="replace")
    _, pii_redacted = redact_phones(text)
    messages = parse_export(text)
    if not messages:
        raise HTTPException(status_code=400, detail="no messages found in export")

    try:
        extracted: ExtractionResult = extract_proposals(
            messages, get_default_llm_client()
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    draft = create_draft(
        session,
        filename=filename,
        as_at=as_at or datetime.now(timezone.utc).replace(tzinfo=None),
        message_count=len(messages),
        pii_redacted=pii_redacted,
        incidents=to_draft_incidents(extracted.incidents),
        logs=to_draft_logs(extracted.logs),
    )
    return _as_response(draft)


@router.get("/whatsapp/drafts", response_model=list[DraftSummary])
def get_drafts(
    limit: int = 10, session: Session = Depends(get_session)
) -> list[DraftSummary]:
    return [
        DraftSummary(
            id=draft.id,
            filename=draft.filename,
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
            get_default_llm_client(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _as_response(update_draft(session, draft, incidents=incidents, logs=logs))


@router.post("/whatsapp/drafts/{draft_id}/briefing", response_model=BriefingResponse)
def post_briefing(
    draft_id: int, session: Session = Depends(get_session)
) -> BriefingResponse:
    draft = _require_draft(session, draft_id)
    try:
        report = generate_briefing(
            draft_incidents(draft),
            draft_logs(draft),
            draft.as_at,
            get_default_llm_client(),
        )
    except BriefingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    saved = save_report(report, session)
    return BriefingResponse(
        id=saved.id, status=report.status, markdown=report.markdown
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
