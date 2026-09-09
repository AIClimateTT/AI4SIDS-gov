import json
import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.contracts import RowErrorInfo, SubmissionIngestResult
from app.core.llm import get_llm_client
from app.core.renderer import strip_citation_markup
from app.core.report_store import add_report
from app.core.template_store import get_latest_template_version
from app.db import get_session
from app.quality.store import record_event
from app.modules.capture.csv_import import import_csv_rows, read_csv_bytes
from app.modules.capture.file import working_set_to_ingest_rows
from app.modules.capture.models import CaptureSession
from app.modules.capture.schemas import (
    CaptureIncident,
    CaptureLog,
    CaptureWorkingSet,
    MissingField,
)
from app.modules.capture.sitrep import (
    generate_working_set_sitrep,
    persist_issued_sitrep,
    save_sitrep_preview,
)
from app.modules.capture.store import (
    apply_working_set,
    create_session,
    get_session_row,
    list_sessions,
    save_session,
    session_messages,
    session_missing,
    working_set_from_session,
)
from app.modules.capture.prompt import compose_capture_prompt
from app.modules.capture.turn import apply_turn, stream_turn
from app.modules.sitreps.ingest import ingest_submission
from app.modules.sitreps.models import ALERT_LEVELS, HAZARD_TYPES
from app.modules.sitreps.store import create_event, get_event
from app.modules.survey123.normalize import CANONICAL_CORPORATIONS

router = APIRouter()


class CreateSessionRequest(BaseModel):
    corporation: str
    event_id: int | None = None


class CaptureMessageOut(BaseModel):
    role: str
    content: str
    created_at: datetime


class SitrepOut(BaseModel):
    markdown: str
    final_markdown: str
    fact_table: dict
    violations: list
    status: str
    generated_at: datetime
    source_updated_at: datetime
    stale: bool


class CaptureSessionResponse(BaseModel):
    id: int
    corporation: str
    event_id: int | None
    status: str
    as_at: datetime
    alert_level: str
    present_activity: str | None
    situation_overview: str | None
    incidents: list[CaptureIncident]
    logs: list[CaptureLog]
    manual_fields: list[str]
    messages: list[CaptureMessageOut]
    missing: list[MissingField]
    submission_id: int | None
    report_id: str | None = None
    sitrep: SitrepOut | None = None
    created_at: datetime
    updated_at: datetime


class TurnRequest(BaseModel):
    message: str


class StreamTurnRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    messages: list[dict] = Field(default_factory=list)
    data: dict | None = None
    forwardedProps: dict | None = None
    threadId: str | None = None
    runId: str | None = None


class UpdateSessionRequest(BaseModel):
    as_at: datetime | None = None
    alert_level: str | None = None
    present_activity: str | None = None
    situation_overview: str | None = None
    incidents: list[CaptureIncident]
    logs: list[CaptureLog]
    manual_fields: list[str] | None = None


class FileSessionResponse(BaseModel):
    session: CaptureSessionResponse
    ingest: SubmissionIngestResult


class CsvImportResponse(BaseModel):
    session: CaptureSessionResponse
    kind: Literal["incidents", "logs"]
    rows_read: int
    rows_accepted: int
    row_errors: list[RowErrorInfo]


def _require_corporation(corporation: str) -> str:
    if corporation not in CANONICAL_CORPORATIONS:
        raise HTTPException(status_code=400, detail=f"unknown corporation: {corporation}")
    return corporation


def _sitrep_out(row: CaptureSession) -> SitrepOut | None:
    if row.sitrep_markdown is None or row.sitrep_generated_at is None:
        return None
    source = row.sitrep_source_updated_at
    stale = source is None or source < row.updated_at
    return SitrepOut(
        markdown=row.sitrep_markdown,
        # Sitreps drafted before the final variant existed have no stored
        # copy; the draft stands in until the officer refreshes. Strip the
        # appendix either way — the issued document is the prose, and the
        # draft view already has a fact table for citations.
        final_markdown=strip_citation_markup(
            row.sitrep_final_markdown or row.sitrep_markdown
        ),
        fact_table=row.sitrep_fact_table or {},
        violations=row.sitrep_violations or [],
        status=row.sitrep_status or "",
        generated_at=row.sitrep_generated_at,
        source_updated_at=source or row.updated_at,
        stale=stale,
    )


def _to_response(row: CaptureSession) -> CaptureSessionResponse:
    working = working_set_from_session(row)
    return CaptureSessionResponse(
        id=row.id,
        corporation=row.corporation,
        event_id=row.event_id,
        status=row.status,
        as_at=row.as_at,
        alert_level=row.alert_level,
        present_activity=row.present_activity,
        situation_overview=row.situation_overview,
        incidents=working.incidents,
        logs=working.logs,
        manual_fields=working.manual_fields,
        messages=[
            CaptureMessageOut.model_validate(item) for item in (row.messages or [])
        ],
        missing=session_missing(row),
        submission_id=row.submission_id,
        report_id=row.report_id,
        sitrep=_sitrep_out(row),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _load_owned(
    db: Session, session_id: int
) -> CaptureSession:
    row = get_session_row(db, session_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"capture session not found: {session_id}")
    return row


def _require_draft(row: CaptureSession) -> None:
    if row.status != "draft":
        raise HTTPException(status_code=409, detail="this capture session has already been filed")


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


@router.post("/capture/sessions", response_model=CaptureSessionResponse, status_code=201)
def post_session(
    request: CreateSessionRequest, db: Session = Depends(get_session)
) -> CaptureSessionResponse:
    corporation = _require_corporation(request.corporation)
    if request.event_id is not None:
        event = get_event(db, request.event_id)
        if event is None or event.corporation != corporation:
            raise HTTPException(
                status_code=404,
                detail=f"event not found for this corporation: {request.event_id}",
            )
    row = create_session(db, corporation=corporation, event_id=request.event_id)
    record_event(
        db,
        workflow="corp_capture_issue",
        step="create",
        outcome="started",
        subject_id=str(row.id),
    )
    return _to_response(row)


@router.get("/capture/sessions", response_model=list[CaptureSessionResponse])
def get_sessions(
    corporation: str,
    event_id: int | None = None,
    db: Session = Depends(get_session),
) -> list[CaptureSessionResponse]:
    _require_corporation(corporation)
    return [_to_response(row) for row in list_sessions(db, corporation=corporation, event_id=event_id)]


@router.get("/capture/sessions/{session_id}", response_model=CaptureSessionResponse)
def get_one_session(
    session_id: int, db: Session = Depends(get_session)
) -> CaptureSessionResponse:
    return _to_response(_load_owned(db, session_id))


class AttachEventRequest(BaseModel):
    event_id: int | None = None
    title: str | None = None
    hazard_type: str | None = None
    started_at: datetime | None = None


@router.post("/capture/sessions/{session_id}/event", response_model=CaptureSessionResponse)
def post_session_event(
    session_id: int, request: AttachEventRequest, db: Session = Depends(get_session)
) -> CaptureSessionResponse:
    row = _load_owned(db, session_id)
    _require_draft(row)

    if request.event_id is not None:
        event = get_event(db, request.event_id)
        if event is None or event.corporation != row.corporation:
            raise HTTPException(
                status_code=404,
                detail=f"event not found for this corporation: {request.event_id}",
            )
        row.event_id = event.id
    elif request.title and request.hazard_type and request.started_at:
        if request.hazard_type not in HAZARD_TYPES:
            raise HTTPException(
                status_code=400, detail=f"unknown hazard_type: {request.hazard_type}"
            )
        event = create_event(
            db,
            corporation=row.corporation,
            title=request.title,
            hazard_type=request.hazard_type,
            started_at=request.started_at,
        )
        row.event_id = event.id
    else:
        raise HTTPException(
            status_code=400,
            detail="attach an existing event_id, or give title, hazard_type and started_at",
        )

    save_session(db, row)
    return _to_response(row)


@router.post("/capture/sessions/{session_id}/turns", response_model=CaptureSessionResponse)
def post_turn(
    session_id: int, request: TurnRequest, db: Session = Depends(get_session)
) -> CaptureSessionResponse:
    row = _load_owned(db, session_id)
    _require_draft(row)
    working, _message, _missing, messages = apply_turn(
        working_set_from_session(row),
        session_messages(row),
        request.message,
        get_llm_client("chat"),
        system_prompt=compose_capture_prompt(_sitrep_template(db)),
    )
    apply_working_set(row, working)
    row.messages = [item.model_dump(mode="json") for item in messages]
    save_session(db, row)
    return _to_response(row)


@router.post("/capture/sessions/{session_id}/turns/stream")
def post_turn_stream(
    session_id: int,
    request: StreamTurnRequest,
    db: Session = Depends(get_session),
) -> StreamingResponse:
    row = _load_owned(db, session_id)
    _require_draft(row)
    user_message = _latest_user_text(request.messages)
    thread_id = request.threadId or str(session_id)
    run_id = request.runId or str(uuid.uuid4())
    message_id = str(uuid.uuid4())
    working = working_set_from_session(row)
    history = session_messages(row)
    llm = get_llm_client("chat")

    def events():
        yield _sse(
            {"type": "RUN_STARTED", "threadId": thread_id, "runId": run_id}
        )
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
                system_prompt=compose_capture_prompt(_sitrep_template(db)),
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
                raise RuntimeError("capture turn did not complete")
            if not streamed and done.assistant_message:
                yield _sse(
                    {
                        "type": "TEXT_MESSAGE_CONTENT",
                        "messageId": message_id,
                        "delta": done.assistant_message,
                    }
                )
            yield _sse({"type": "TEXT_MESSAGE_END", "messageId": message_id})
            apply_working_set(row, done.working)
            row.messages = [item.model_dump(mode="json") for item in done.messages]
            save_session(db, row)
            yield _sse(
                {
                    "type": "CUSTOM",
                    "name": "capture.updated",
                    "value": _to_response(row).model_dump(mode="json"),
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


@router.put("/capture/sessions/{session_id}", response_model=CaptureSessionResponse)
def put_session(
    session_id: int, request: UpdateSessionRequest, db: Session = Depends(get_session)
) -> CaptureSessionResponse:
    row = _load_owned(db, session_id)
    _require_draft(row)
    if request.alert_level is not None and request.alert_level not in ALERT_LEVELS:
        raise HTTPException(status_code=400, detail=f"unknown alert_level: {request.alert_level}")
    working = CaptureWorkingSet(
        as_at=request.as_at or row.as_at,
        alert_level=request.alert_level or row.alert_level,
        present_activity=(
            request.present_activity
            if request.present_activity is not None
            else row.present_activity
        ),
        situation_overview=(
            request.situation_overview
            if request.situation_overview is not None
            else row.situation_overview
        ),
        incidents=request.incidents,
        logs=request.logs,
        manual_fields=(
            request.manual_fields
            if request.manual_fields is not None
            else list(row.manual_fields or [])
        ),
    )
    apply_working_set(row, working)
    save_session(db, row)
    return _to_response(row)


@router.post(
    "/capture/sessions/{session_id}/csv",
    response_model=CsvImportResponse,
)
async def post_session_csv(
    session_id: int,
    kind: Literal["incidents", "logs"] = Form(),
    file: UploadFile = File(),
    db: Session = Depends(get_session),
) -> CsvImportResponse:
    row = _load_owned(db, session_id)
    _require_draft(row)
    contents = await file.read()
    try:
        rows = read_csv_bytes(contents)
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=400, detail="file is not valid UTF-8 CSV"
        ) from exc

    before = working_set_from_session(row)
    working, errors = import_csv_rows(before, kind=kind, rows=rows)
    apply_working_set(row, working)
    save_session(db, row)
    return CsvImportResponse(
        session=_to_response(row),
        kind=kind,
        rows_read=len(rows),
        rows_accepted=len(rows) - len(errors),
        row_errors=errors,
    )


def _require_event_if_incidents(row: CaptureSession) -> None:
    working = working_set_from_session(row)
    if row.event_id is None and working.incidents:
        raise HTTPException(
            status_code=400,
            detail=(
                "a filing carrying incidents must be attached to an event; "
                "attach one before filing. Situation logs may be filed without one."
            ),
        )


def _sitrep_template(db: Session):
    template = get_latest_template_version("corp_situation_report", db)
    if template is None:
        raise HTTPException(
            status_code=400,
            detail="template corp_situation_report is not installed; run templates import-all",
        )
    return template


def _event_title(db: Session, row: CaptureSession) -> str:
    if row.event_id is None:
        return "Untitled event"
    event = get_event(db, row.event_id)
    return event.title if event is not None else "Untitled event"


def _generate_preview(db: Session, row: CaptureSession) -> CaptureSession:
    template = _sitrep_template(db)
    working = working_set_from_session(row)
    generated = generate_working_set_sitrep(
        working,
        corporation=row.corporation,
        event_id=row.event_id,
        event_title=_event_title(db, row),
        template=template,
        llm_client=get_llm_client("chat"),
        request_id=str(uuid.uuid4()),
    )
    return save_sitrep_preview(db, row, generated, source_updated_at=row.updated_at)


def ingest_working_set(
    db: Session, row: CaptureSession, *, commit: bool = True
) -> SubmissionIngestResult:
    _require_event_if_incidents(row)
    working = working_set_from_session(row)
    incident_rows, log_rows = working_set_to_ingest_rows(working)
    return ingest_submission(
        db,
        corporation=row.corporation,
        as_at=working.as_at or row.as_at,
        event_id=row.event_id,
        alert_level=working.alert_level,
        present_activity=working.present_activity,
        situation_overview=working.situation_overview,
        source_name="conversation",
        incident_rows=incident_rows,
        log_rows=log_rows,
        structured_defaults=True,
        commit=commit,
    )


def file_working_set(db: Session, row: CaptureSession) -> SubmissionIngestResult:
    ingest = ingest_working_set(db, row)
    row.status = "filed"
    row.submission_id = ingest.submission_id
    save_session(db, row)
    return ingest


@router.post(
    "/capture/sessions/{session_id}/file",
    response_model=FileSessionResponse,
    status_code=201,
)
def file_session(
    session_id: int, db: Session = Depends(get_session)
) -> FileSessionResponse:
    row = _load_owned(db, session_id)
    _require_draft(row)
    ingest = file_working_set(db, row)
    return FileSessionResponse(session=_to_response(row), ingest=ingest)


@router.post(
    "/capture/sessions/{session_id}/preview",
    response_model=CaptureSessionResponse,
)
def preview_session(
    session_id: int, db: Session = Depends(get_session)
) -> CaptureSessionResponse:
    row = _load_owned(db, session_id)
    _require_draft(row)
    row = _generate_preview(db, row)
    return _to_response(row)


@router.post(
    "/capture/sessions/{session_id}/issue",
    response_model=FileSessionResponse,
    status_code=201,
)
def issue_session(
    session_id: int, db: Session = Depends(get_session)
) -> FileSessionResponse:
    row = _load_owned(db, session_id)
    _require_draft(row)
    _require_event_if_incidents(row)
    ingest = ingest_working_set(db, row, commit=False)
    template = _sitrep_template(db)
    generated = generate_working_set_sitrep(
        working_set_from_session(row),
        corporation=row.corporation,
        event_id=row.event_id,
        event_title=_event_title(db, row),
        template=template,
        llm_client=get_llm_client("chat"),
        request_id=str(uuid.uuid4()),
    )
    generated = generated.model_copy(
        update={
            "params": {
                "corporation": row.corporation,
                "submission_id": ingest.submission_id,
            }
        }
    )
    saved = add_report(generated, db)
    row.status = "filed"
    row.submission_id = ingest.submission_id
    persist_issued_sitrep(
        db,
        row,
        generated,
        report_id=saved.id,
        source_updated_at=row.updated_at,
    )
    record_event(
        db,
        workflow="corp_capture_issue",
        step="issue",
        outcome="succeeded",
        subject_id=saved.id,
    )
    return FileSessionResponse(session=_to_response(row), ingest=ingest)
