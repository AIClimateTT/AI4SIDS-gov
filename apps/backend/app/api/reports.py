from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.engine import generate_report
from app.core.llm import get_default_llm_client
from app.core.registry import get_template
from app.core.report_store import get_report, save_report
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
    template = get_template(request.template)
    if template is None:
        raise HTTPException(status_code=404, detail=f"unknown template: {request.template}")

    try:
        report = generate_report(template, request.params, session, get_default_llm_client())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    save_report(report, session)

    return GenerateReportResponse(id=report.request_id, status=report.status, markdown=report.markdown)


class ReportDetail(BaseModel):
    id: str
    template: str
    params: dict
    fact_table: dict
    narrative: str
    markdown: str
    status: str
    violations: list


@router.get("/reports/{report_id}", response_model=ReportDetail)
def read_report(report_id: str, session: Session = Depends(get_session)) -> ReportDetail:
    db_report = get_report(report_id, session)
    if db_report is None:
        raise HTTPException(status_code=404, detail=f"report not found: {report_id}")

    return ReportDetail(
        id=db_report.id,
        template=db_report.template,
        params=db_report.params,
        fact_table=db_report.fact_table,
        narrative=db_report.narrative,
        markdown=db_report.markdown,
        status=db_report.status,
        violations=db_report.violations,
    )
