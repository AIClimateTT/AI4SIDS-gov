import tempfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.contracts import SubmissionIngestResult
from app.db import get_session
from app.modules.sitreps.ingest import ingest_submission
from app.modules.sitreps.models import ALERT_LEVELS, HAZARD_TYPES, Submission
from app.modules.sitreps.store import (
    create_event,
    get_event,
    list_events,
    list_submissions,
    submission_counts,
)
from app.modules.survey123.normalize import CANONICAL_CORPORATIONS

router = APIRouter()


class CreateEventRequest(BaseModel):
    corporation: str
    title: str
    hazard_type: str
    started_at: datetime
    ended_at: datetime | None = None


class EventSummary(BaseModel):
    id: int
    corporation: str
    title: str
    hazard_type: str
    started_at: datetime
    ended_at: datetime | None


def _require_corporation(corporation: str) -> str:
    if corporation not in CANONICAL_CORPORATIONS:
        raise HTTPException(
            status_code=400, detail=f"unknown corporation: {corporation}"
        )
    return corporation


@router.post("/events", response_model=EventSummary, status_code=201)
def post_event(
    request: CreateEventRequest, session: Session = Depends(get_session)
) -> EventSummary:
    _require_corporation(request.corporation)
    if request.hazard_type not in HAZARD_TYPES:
        raise HTTPException(
            status_code=400, detail=f"unknown hazard_type: {request.hazard_type}"
        )
    event = create_event(
        session,
        corporation=request.corporation,
        title=request.title,
        hazard_type=request.hazard_type,
        started_at=request.started_at,
        ended_at=request.ended_at,
    )
    return EventSummary.model_validate(event, from_attributes=True)


@router.get("/events", response_model=list[EventSummary])
def get_events(
    corporation: str, session: Session = Depends(get_session)
) -> list[EventSummary]:
    return [
        EventSummary.model_validate(e, from_attributes=True)
        for e in list_events(session, corporation)
    ]


async def _spool(upload: UploadFile | None) -> tuple[Path, str] | None:
    if upload is None:
        return None
    contents = await upload.read()
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
        tmp.write(contents)
        return Path(tmp.name), upload.filename or Path(tmp.name).name


@router.post("/submissions", response_model=SubmissionIngestResult, status_code=201)
async def post_submission(
    corporation: str = Form(...),
    as_at: datetime = Form(...),
    event_id: int | None = Form(None),
    alert_level: str = Form("none"),
    present_activity: str | None = Form(None),
    situation_overview: str | None = Form(None),
    incidents_file: UploadFile | None = None,
    logs_file: UploadFile | None = None,
    session: Session = Depends(get_session),
) -> SubmissionIngestResult:
    _require_corporation(corporation)
    if alert_level not in ALERT_LEVELS:
        raise HTTPException(status_code=400, detail=f"unknown alert_level: {alert_level}")
    if incidents_file is not None and event_id is None:
        raise HTTPException(
            status_code=400,
            detail=(
                "a submission carrying incidents must name an event; "
                "create one with POST /events first. Situation logs may be "
                "filed without an event."
            ),
        )
    if event_id is not None:
        event = get_event(session, event_id)
        if event is None or event.corporation != corporation:
            raise HTTPException(
                status_code=404, detail=f"event not found for this corporation: {event_id}"
            )

    spooled_incidents = await _spool(incidents_file)
    spooled_logs = await _spool(logs_file)
    incidents_path, incidents_name = spooled_incidents if spooled_incidents else (None, None)
    logs_path, logs_name = spooled_logs if spooled_logs else (None, None)
    source_name = ",".join(name for name in (incidents_name, logs_name) if name) or None
    try:
        return ingest_submission(
            session,
            corporation=corporation,
            as_at=as_at,
            event_id=event_id,
            alert_level=alert_level,
            present_activity=present_activity,
            situation_overview=situation_overview,
            incidents_path=incidents_path,
            logs_path=logs_path,
            source_name=source_name,
        )
    finally:
        for path in (incidents_path, logs_path):
            if path is not None:
                path.unlink(missing_ok=True)


class SubmissionSummary(BaseModel):
    id: int
    corporation: str
    event_id: int | None
    event_title: str | None
    as_at: datetime
    alert_level: str
    sequence_no: int
    incident_count: int
    log_count: int


class SubmissionDetail(SubmissionSummary):
    present_activity: str | None
    situation_overview: str | None
    source_file: str | None
    row_errors: list


def _summary(session: Session, submission) -> SubmissionSummary:
    incidents, logs = submission_counts(session, submission.id)
    event = get_event(session, submission.event_id) if submission.event_id else None
    return SubmissionSummary(
        id=submission.id,
        corporation=submission.corporation,
        event_id=submission.event_id,
        event_title=event.title if event else None,
        as_at=submission.as_at,
        alert_level=submission.alert_level,
        sequence_no=submission.sequence_no,
        incident_count=incidents,
        log_count=logs,
    )


@router.get("/submissions", response_model=list[SubmissionSummary])
def get_submissions(
    corporation: str | None = None,
    event_id: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    session: Session = Depends(get_session),
) -> list[SubmissionSummary]:
    return [
        _summary(session, s)
        for s in list_submissions(
            session, corporation=corporation, event_id=event_id,
            date_from=date_from, date_to=date_to,
        )
    ]


@router.get("/submissions/{submission_id}", response_model=SubmissionDetail)
def get_submission(
    submission_id: int, session: Session = Depends(get_session)
) -> SubmissionDetail:
    submission = session.get(Submission, submission_id)
    if submission is None:
        raise HTTPException(status_code=404, detail=f"submission not found: {submission_id}")
    summary = _summary(session, submission)
    return SubmissionDetail(
        **summary.model_dump(),
        present_activity=submission.present_activity,
        situation_overview=submission.situation_overview,
        source_file=submission.source_file,
        row_errors=submission.row_errors,
    )
