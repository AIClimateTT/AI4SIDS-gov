from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.engine import generate_report
from app.core.llm import get_default_llm_client
from app.core.report_store import get_report, list_reports, save_report
from app.core.template_store import get_latest_template_version
from app.db import get_session

router = APIRouter()


class GenerateReportRequest(BaseModel):
    template: str
    params: dict


class GenerateReportResponse(BaseModel):
    id: str
    status: str
    markdown: str


@router.post("/reports", response_model=GenerateReportResponse)
def create_report(
    request: GenerateReportRequest, session: Session = Depends(get_session)
) -> GenerateReportResponse:
    template = get_latest_template_version(request.template, session)
    if template is None:
        raise HTTPException(status_code=404, detail=f"unknown template: {request.template}")

    try:
        report = generate_report(template, request.params, session, get_default_llm_client())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    save_report(report, session)

    return GenerateReportResponse(id=report.request_id, status=report.status, markdown=report.markdown)


class ReportListItem(BaseModel):
    id: str
    template: str
    template_version: int
    params: dict
    status: str
    created_at: datetime


class ReportListResponse(BaseModel):
    items: list[ReportListItem]
    total: int


@router.get("/reports", response_model=ReportListResponse)
def get_reports(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    q: str | None = None,
    status: str | None = None,
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    session: Session = Depends(get_session),
) -> ReportListResponse:
    items, total = list_reports(
        session,
        page=page,
        page_size=page_size,
        q=q,
        status=status,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return ReportListResponse(
        items=[
            ReportListItem(
                id=item.id,
                template=item.template,
                template_version=item.template_version,
                params=item.params,
                status=item.status,
                created_at=item.created_at,
            )
            for item in items
        ],
        total=total,
    )


class ReportDetail(BaseModel):
    id: str
    template: str
    template_version: int
    params: dict
    fact_table: dict
    narrative: str
    markdown: str
    status: str
    violations: list
    created_at: datetime


@router.get("/reports/{report_id}", response_model=ReportDetail)
def read_report(report_id: str, session: Session = Depends(get_session)) -> ReportDetail:
    db_report = get_report(report_id, session)
    if db_report is None:
        raise HTTPException(status_code=404, detail=f"report not found: {report_id}")

    return ReportDetail(
        id=db_report.id,
        template=db_report.template,
        template_version=db_report.template_version,
        params=db_report.params,
        fact_table=db_report.fact_table,
        narrative=db_report.narrative,
        markdown=db_report.markdown,
        status=db_report.status,
        violations=db_report.violations,
        created_at=db_report.created_at,
    )
