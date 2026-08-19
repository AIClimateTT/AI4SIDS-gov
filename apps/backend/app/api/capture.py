import json
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.contracts import SubmissionIngestResult
from app.core.llm import get_llm_client
from app.db import get_session
from app.modules.capture.file import working_set_to_ingest_rows
from app.modules.capture.models import CaptureSession
from app.modules.capture.schemas import (
    CaptureIncident,
    CaptureLog,
    CaptureWorkingSet,
    MissingField,
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
from app.modules.capture.turn import apply_turn, stream_turn
from app.modules.sitreps.ingest import ingest_submission
from app.modules.sitreps.models import ALERT_LEVELS
from app.modules.sitreps.store import get_event
from app.modules.survey123.normalize import CANONICAL_CORPORATIONS

router = APIRouter()


class CreateSessionRequest(BaseModel):
    corporation: str
    event_id: int


class CaptureMessageOut(BaseModel):
    role: str
    content: str
    created_at: datetime


class CaptureSessionResponse(BaseModel):
    id: int
    corporation: str
    event_id: int
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
    manual_fields: list[str] = Field(default_factory=list)


class FileSessionResponse(BaseModel):
    session: CaptureSessionResponse
    ingest: SubmissionIngestResult


def _require_corporation(corporation: str) -> str:
    if corporation not in CANONICAL_CORPORATIONS:
        raise HTTPException(status_code=400, detail=f"unknown corporation: {corporation}")
    return corporation


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
    event = get_event(db, request.event_id)
    if event is None or event.corporation != corporation:
        raise HTTPException(
            status_code=404,
            detail=f"event not found for this corporation: {request.event_id}",
        )
    row = create_session(db, corporation=corporation, event_id=request.event_id)
    return _to_response(row)


@router.get("/capture/sessions", response_model=list[CaptureSessionResponse])
def get_sessions(
    corporation: str,
    event_id: int,
    db: Session = Depends(get_session),
) -> list[CaptureSessionResponse]:
    _require_corporation(corporation)
    return [_to_response(row) for row in list_sessions(db, corporation=corporation, event_id=event_id)]


@router.get("/capture/sessions/{session_id}", response_model=CaptureSessionResponse)
def get_one_session(
    session_id: int, db: Session = Depends(get_session)
) -> CaptureSessionResponse:
    return _to_response(_load_owned(db, session_id))


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
            for item in stream_turn(working, history, user_message, llm):
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
        manual_fields=request.manual_fields,
    )
    apply_working_set(row, working)
    save_session(db, row)
    return _to_response(row)


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
    working = working_set_from_session(row)
    incident_rows, log_rows = working_set_to_ingest_rows(working)
    ingest = ingest_submission(
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
    )
    row.status = "filed"
    row.submission_id = ingest.submission_id
    save_session(db, row)
    return FileSessionResponse(session=_to_response(row), ingest=ingest)
