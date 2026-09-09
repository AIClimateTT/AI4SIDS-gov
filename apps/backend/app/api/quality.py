from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.dependencies import DmuUser
from app.core.report_store import get_report
from app.db import get_session
from app.quality.contracts import QualityEval
from app.quality.denominators import NAMED_WORKFLOWS
from app.quality.store import apply_claim_verdict, get_event, list_events, record_event, set_assisted
from app.quality.summary import QualitySummary, build_quality_summary

router = APIRouter()

_OUTCOMES = ("started", "succeeded", "failed")


class EventIn(BaseModel):
    workflow: str
    step: str
    outcome: Literal["started", "succeeded", "failed"]
    subject_id: str | None = None


class EventOut(BaseModel):
    id: str
    workflow: str
    step: str
    outcome: str
    subject_id: str | None
    assisted: bool
    created_at: datetime


class EventList(BaseModel):
    items: list[EventOut]


class AssistedIn(BaseModel):
    assisted: bool


def _to_out(row) -> EventOut:
    return EventOut(
        id=row.id,
        workflow=row.workflow,
        step=row.step,
        outcome=row.outcome,
        subject_id=row.subject_id,
        assisted=row.assisted,
        created_at=row.created_at,
    )


@router.get("/quality/summary", response_model=QualitySummary)
def get_quality_summary(session: Session = Depends(get_session)) -> QualitySummary:
    return build_quality_summary(session)


@router.get("/quality/events", response_model=EventList)
def get_quality_events(
    subject_id: str | None = Query(None),
    workflow: str | None = Query(None),
    session: Session = Depends(get_session),
) -> EventList:
    return EventList(
        items=[_to_out(row) for row in list_events(session, subject_id=subject_id, workflow=workflow)]
    )


@router.post("/quality/events", response_model=EventOut, status_code=201)
def post_quality_event(body: EventIn, session: Session = Depends(get_session)) -> EventOut:
    if body.workflow not in NAMED_WORKFLOWS:
        raise HTTPException(
            status_code=400,
            detail=f"unknown workflow: {body.workflow!r}; expected one of {NAMED_WORKFLOWS}",
        )
    if body.outcome not in _OUTCOMES:
        raise HTTPException(status_code=400, detail="unknown outcome")
    row = record_event(
        session,
        workflow=body.workflow,
        step=body.step,
        outcome=body.outcome,
        subject_id=body.subject_id,
    )
    return _to_out(row)


@router.patch("/quality/events/{event_id}", response_model=EventOut)
def patch_quality_event(
    event_id: str, body: AssistedIn, session: Session = Depends(get_session)
) -> EventOut:
    row = set_assisted(session, event_id, body.assisted)
    if row is None:
        raise HTTPException(status_code=404, detail=f"event not found: {event_id}")
    return _to_out(row)


class VerdictIn(BaseModel):
    verdict: Literal["supported", "unsupported"]


@router.patch("/reports/{report_id}/claims/{claim_id}", response_model=QualityEval)
def patch_claim_verdict(
    report_id: str,
    claim_id: str,
    body: VerdictIn,
    current_user: DmuUser,
    session: Session = Depends(get_session),
) -> QualityEval:
    row = get_report(report_id, session)
    if row is None:
        raise HTTPException(status_code=404, detail=f"report not found: {report_id}")
    try:
        eval_ = apply_claim_verdict(row, claim_id, body.verdict)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"claim not found: {claim_id}") from None
    row.quality_eval = eval_.model_dump(mode="json")
    session.commit()
    return eval_
