from datetime import datetime, timezone
import json
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.contracts import SubmissionIngestResult
from app.core.jobs import enqueue
from app.core.llm import get_llm_client
from app.core.report_store import get_report, save_placeholder_report
from app.db import get_session
from app.quality.store import record_event
from app.modules.capture.schemas import MissingField
from app.modules.whatsapp.briefing import BRIEFING_TEMPLATE, briefing_is_stale
from app.modules.whatsapp.confirm import ConfirmError, confirm_proposals
from app.modules.whatsapp.extract import (
    DraftIncident,
    DraftLog,
    ProposedIncident,
    ProposedLog,
    WhatsAppMessage,
    coerce_draft_incidents,
    coerce_draft_logs,
)
from app.modules.whatsapp.facts import (
    included_attributed_incidents,
    included_attributed_logs,
)
from app.modules.whatsapp.missing import missing_fields
from app.modules.whatsapp.models import WhatsAppDraft
from app.modules.whatsapp.parse import messages_from_source
from app.modules.whatsapp.store import (
    attach_briefing_report,
    create_draft,
    draft_incidents,
    draft_logs,
    draft_manual_fields,
    draft_messages,
    get_draft,
    list_drafts,
    update_draft,
    working_set_from_draft,
)
from app.modules.whatsapp.turn import apply_turn, stream_turn

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
    messages: list[WhatsAppMessage] = Field(default_factory=list)
    manual_fields: list[str] = Field(default_factory=list)
    missing: list[MissingField] = Field(default_factory=list)
    status: str
    error: str | None = None
    briefing_report_id: str | None = None
    briefing_stale: bool = False
    created_at: datetime
    updated_at: datetime


class DraftUpdateRequest(BaseModel):
    as_at: datetime | None = None
    incidents: list[DraftIncident]
    logs: list[DraftLog]
    manual_fields: list[str] | None = None


class AdjustRequest(BaseModel):
    instruction: str


class TurnRequest(BaseModel):
    message: str


class StreamTurnRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    messages: list[dict] = Field(default_factory=list)
    data: dict | None = None
    forwardedProps: dict | None = None
    threadId: str | None = None
    runId: str | None = None


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


def _as_response(draft: WhatsAppDraft, session: Session) -> DraftResponse:
    working = working_set_from_draft(draft)
    report_created_at = None
    if draft.briefing_report_id:
        row = get_report(draft.briefing_report_id, session)
        if row is not None:
            report_created_at = row.created_at
    return DraftResponse(
        id=draft.id,
        draft_id=draft.id,
        filename=draft.filename,
        source_kind=draft.source_kind,
        as_at=draft.as_at,
        message_count=draft.message_count,
        pii_redacted=draft.pii_redacted,
        incidents=working.incidents,
        logs=working.logs,
        messages=draft_messages(draft),
        manual_fields=draft_manual_fields(draft),
        missing=missing_fields(working),
        status=draft.status,
        error=draft.error,
        briefing_report_id=draft.briefing_report_id,
        briefing_stale=briefing_is_stale(
            briefing_report_id=draft.briefing_report_id,
            draft_updated_at=draft.updated_at,
            report_created_at=report_created_at,
        ),
        created_at=draft.created_at,
        updated_at=draft.updated_at,
    )


def _require_draft(session: Session, draft_id: int) -> WhatsAppDraft:
    draft = get_draft(session, draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail=f"draft not found: {draft_id}")
    return draft


def _require_ready(draft: WhatsAppDraft) -> None:
    if draft.status != "ready":
        raise HTTPException(
            status_code=400, detail="draft is not ready for conversation"
        )


def _texts_from_parts(parts: list) -> list[str]:
    texts: list[str] = []
    for part in parts:
        if isinstance(part, str):
            texts.append(part)
            continue
        if not isinstance(part, dict):
            continue
        for key in ("text", "content"):
            value = part.get(key)
            if isinstance(value, str):
                texts.append(value)
                break
    return texts


def _latest_user_text(messages: list[dict]) -> str:
    for msg in reversed(messages):
        if not isinstance(msg, dict) or msg.get("role") != "user":
            continue
        content = msg.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
        chunks: list[str] = []
        if isinstance(content, list):
            chunks.extend(_texts_from_parts(content))
        parts = msg.get("parts")
        if isinstance(parts, list):
            chunks.extend(_texts_from_parts(parts))
        joined = "".join(chunks).strip()
        if joined:
            return joined
    raise HTTPException(status_code=400, detail="message is required")


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"


def _persist_turn(session: Session, draft: WhatsAppDraft, done) -> WhatsAppDraft:
    return update_draft(
        session,
        draft,
        as_at=done.working.as_at,
        incidents=done.working.incidents,
        logs=done.working.logs,
        messages=done.messages,
        manual_fields=done.working.manual_fields,
    )


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
    return _as_response(draft, session)


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
    return _as_response(_require_draft(session, draft_id), session)


@router.put("/whatsapp/drafts/{draft_id}", response_model=DraftResponse)
def put_draft(
    draft_id: int,
    request: DraftUpdateRequest,
    session: Session = Depends(get_session),
) -> DraftResponse:
    draft = _require_draft(session, draft_id)
    incidents = coerce_draft_incidents(
        [row.model_dump() for row in request.incidents]
    )
    logs = coerce_draft_logs([row.model_dump() for row in request.logs])
    return _as_response(
        update_draft(
            session,
            draft,
            as_at=request.as_at,
            incidents=incidents,
            logs=logs,
            manual_fields=request.manual_fields,
        ),
        session,
    )


@router.post("/whatsapp/drafts/{draft_id}/adjust", response_model=DraftResponse)
def post_adjust(
    draft_id: int,
    request: AdjustRequest,
    session: Session = Depends(get_session),
) -> DraftResponse:
    draft = _require_draft(session, draft_id)
    _require_ready(draft)
    if not request.instruction.strip():
        raise HTTPException(status_code=400, detail="instruction is required")
    try:
        _working, _message, _missing, messages = apply_turn(
            working_set_from_draft(draft),
            draft_messages(draft),
            request.instruction,
            get_llm_client("chat"),
            source_text=draft.source_text or "",
            source_kind=draft.source_kind,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _as_response(
        update_draft(
            session,
            draft,
            as_at=_working.as_at,
            incidents=_working.incidents,
            logs=_working.logs,
            messages=messages,
            manual_fields=_working.manual_fields,
        ),
        session,
    )


@router.post("/whatsapp/drafts/{draft_id}/turns", response_model=DraftResponse)
def post_turn(
    draft_id: int,
    request: TurnRequest,
    session: Session = Depends(get_session),
) -> DraftResponse:
    draft = _require_draft(session, draft_id)
    _require_ready(draft)
    try:
        working, _message, _missing, messages = apply_turn(
            working_set_from_draft(draft),
            draft_messages(draft),
            request.message,
            get_llm_client("chat"),
            source_text=draft.source_text or "",
            source_kind=draft.source_kind,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _as_response(
        update_draft(
            session,
            draft,
            as_at=working.as_at,
            incidents=working.incidents,
            logs=working.logs,
            messages=messages,
            manual_fields=working.manual_fields,
        ),
        session,
    )


@router.post("/whatsapp/drafts/{draft_id}/turns/stream")
def post_turn_stream(
    draft_id: int,
    request: StreamTurnRequest,
    session: Session = Depends(get_session),
) -> StreamingResponse:
    draft = _require_draft(session, draft_id)
    _require_ready(draft)
    user_message = _latest_user_text(request.messages)
    thread_id = request.threadId or str(draft_id)
    run_id = request.runId or str(uuid.uuid4())
    message_id = str(uuid.uuid4())
    working = working_set_from_draft(draft)
    history = draft_messages(draft)
    llm = get_llm_client("chat")
    source_text = draft.source_text or ""
    source_kind = draft.source_kind

    def events():
        yield _sse({"type": "RUN_STARTED", "threadId": thread_id, "runId": run_id})
        try:
            yield _sse(
                {
                    "type": "TEXT_MESSAGE_START",
                    "messageId": message_id,
                    "role": "assistant",
                }
            )
            streamed = False
            done = None
            for item in stream_turn(
                working,
                history,
                user_message,
                llm,
                source_text=source_text,
                source_kind=source_kind,
            ):
                if isinstance(item, str):
                    streamed = True
                    yield _sse(
                        {
                            "type": "TEXT_MESSAGE_CONTENT",
                            "messageId": message_id,
                            "delta": item,
                        }
                    )
                else:
                    done = item
            if done is None:
                raise RuntimeError("whatsapp turn did not complete")
            if not streamed and done.assistant_message:
                yield _sse(
                    {
                        "type": "TEXT_MESSAGE_CONTENT",
                        "messageId": message_id,
                        "delta": done.assistant_message,
                    }
                )
            yield _sse({"type": "TEXT_MESSAGE_END", "messageId": message_id})
            saved = _persist_turn(session, draft, done)
            yield _sse(
                {
                    "type": "CUSTOM",
                    "name": "whatsapp.updated",
                    "value": _as_response(saved, session).model_dump(mode="json"),
                }
            )
            yield _sse(
                {"type": "RUN_FINISHED", "threadId": thread_id, "runId": run_id}
            )
        except Exception as exc:
            yield _sse({"type": "RUN_ERROR", "message": str(exc)})

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


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
    attach_briefing_report(session, draft, report_id)
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
