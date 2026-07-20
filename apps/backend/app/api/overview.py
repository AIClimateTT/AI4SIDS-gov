from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.report_models import Report
from app.db import get_session
from app.modules.survey123.models import Incident

router = APIRouter()


class ReportListItem(BaseModel):
    id: str
    template: str
    template_version: int
    params: dict
    status: str
    created_at: datetime


class OverviewSummary(BaseModel):
    incident_count_survey123: int
    incident_count_sitreps: int
    report_count: int
    needs_review_count: int
    recent_reports: list[ReportListItem]


@router.get("/overview", response_model=OverviewSummary)
def get_overview(
    recent_limit: int = Query(5, ge=1, le=20),
    session: Session = Depends(get_session),
) -> OverviewSummary:
    survey123_count = (
        session.scalar(
            select(func.count()).select_from(Incident).where(Incident.source == "survey123")
        )
        or 0
    )
    sitreps_count = (
        session.scalar(
            select(func.count()).select_from(Incident).where(Incident.source == "sitreps")
        )
        or 0
    )
    report_count = session.scalar(select(func.count()).select_from(Report)) or 0
    needs_review_count = (
        session.scalar(
            select(func.count()).select_from(Report).where(Report.status == "needs_review")
        )
        or 0
    )
    recent = list(
        session.scalars(
            select(Report).order_by(Report.created_at.desc()).limit(recent_limit)
        ).all()
    )

    return OverviewSummary(
        incident_count_survey123=survey123_count,
        incident_count_sitreps=sitreps_count,
        report_count=report_count,
        needs_review_count=needs_review_count,
        recent_reports=[
            ReportListItem(
                id=item.id,
                template=item.template,
                template_version=item.template_version,
                params=item.params,
                status=item.status,
                created_at=item.created_at,
            )
            for item in recent
        ],
    )
