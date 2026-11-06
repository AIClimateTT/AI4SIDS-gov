from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_session
from app.modules.sitreps.models import Event, SituationLog, Submission

router = APIRouter()


class SituationLogItem(BaseModel):
    id: int
    corporation: str
    submission_id: int
    as_at: datetime
    event_title: str | None
    category: str
    statement: str
    item: str | None
    quantity: float | None
    unit: str | None
    status: str | None


class SituationLogListResponse(BaseModel):
    items: list[SituationLogItem]
    total: int


@router.get("/situation-logs", response_model=SituationLogListResponse)
def get_situation_logs(
    corporation: str | None = None,
    submission_id: int | None = None,
    q: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    session: Session = Depends(get_session),
) -> SituationLogListResponse:
    filters = []
    if corporation:
        filters.append(Submission.corporation == corporation)
    if submission_id is not None:
        filters.append(SituationLog.submission_id == submission_id)
    needle = (q or "").strip()
    if needle:
        filters.append(SituationLog.statement.icontains(needle, autoescape=True))

    total = session.scalar(
        select(func.count())
        .select_from(SituationLog)
        .join(Submission, SituationLog.submission_id == Submission.id)
        .where(*filters)
    )
    rows = session.execute(
        select(SituationLog, Submission, Event.title)
        .join(Submission, SituationLog.submission_id == Submission.id)
        .outerjoin(Event, Submission.event_id == Event.id)
        .where(*filters)
        .order_by(Submission.as_at.desc(), SituationLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return SituationLogListResponse(
        items=[
            SituationLogItem(
                id=log.id,
                corporation=submission.corporation,
                submission_id=submission.id,
                as_at=submission.as_at,
                event_title=event_title,
                category=log.category,
                statement=log.statement,
                item=log.item,
                quantity=float(log.quantity) if log.quantity is not None else None,
                unit=log.unit,
                status=log.status,
            )
            for log, submission, event_title in rows
        ],
        total=total or 0,
    )
