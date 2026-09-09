from datetime import datetime
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser

from app.core.contracts import DataRequirement
from app.core.engine import PLACEHOLDER_RE, resolve_effective_requirements, validate_params
from app.core.jobs import enqueue
from app.core.report_store import get_report, list_reports, save_placeholder_report
from app.core.template_store import get_latest_template_version, get_template_version
from app.db import get_session
from app.modules.survey123.normalize import CANONICAL_CORPORATIONS
from app.quality.store import record_event, save_rating

router = APIRouter()


class DataRequirementInput(BaseModel):
    module: str
    metric: str
    params: dict = {}


class GenerateReportRequest(BaseModel):
    template: str
    params: dict
    version: int | None = None
    data_requirements: list[DataRequirementInput] | None = None


class GenerateReportResponse(BaseModel):
    id: str
    status: str
    markdown: str
    error: str | None = None


def validate_corporations(request: GenerateReportRequest) -> None:
    """Reject a corporation that is not one of the fourteen, before any query.

    A typo matches no row, so every metric returns a confident zero and the
    report reads as an authoritative "nothing happened" for a region that may
    have filed plenty. Checked on the template params and on any literal value
    in a data_requirements override, which is caller-controlled — a placeholder
    like "{corporation}" resolves from the params already checked.
    """
    values = [request.params.get("corporation")]
    for requirement in request.data_requirements or []:
        values.append(requirement.params.get("corporation"))

    for value in values:
        if value is None or value == "":
            continue
        if isinstance(value, str) and PLACEHOLDER_RE.match(value):
            continue
        if value not in CANONICAL_CORPORATIONS:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"unknown corporation: {value!r}; expected one of the fourteen "
                    "regional corporations"
                ),
            )


@router.post("/reports", response_model=GenerateReportResponse, status_code=202)
def create_report(
    request: GenerateReportRequest, session: Session = Depends(get_session)
) -> GenerateReportResponse:
    validate_corporations(request)

    if request.version is not None:
        template = get_template_version(request.template, request.version, session)
    else:
        template = get_latest_template_version(request.template, session)
    if template is None:
        raise HTTPException(status_code=404, detail=f"unknown template: {request.template}")

    override = None
    if request.data_requirements is not None:
        override = [
            DataRequirement(module=d.module, metric=d.metric, params=d.params)
            for d in request.data_requirements
        ]

    try:
        resolve_effective_requirements(template, override)
        validate_params(template, request.params)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    report_id = str(uuid.uuid4())
    save_placeholder_report(
        session,
        report_id=report_id,
        template=template,
        params=request.params,
        data_requirements=override,
    )
    record_event(
        session,
        workflow="dmu_generate_report",
        step="create",
        outcome="started",
        subject_id=report_id,
    )
    enqueue("generate_report", report_id=report_id)
    session.expire_all()
    row = get_report(report_id, session)
    if row is None:
        raise HTTPException(status_code=500, detail="report placeholder missing after enqueue")
    return GenerateReportResponse(
        id=row.id, status=row.status, markdown=row.markdown, error=row.error
    )


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
    data_requirements: list
    fact_table: dict
    narrative: str
    markdown: str
    status: str
    violations: list
    quality_eval: dict | None = None
    error: str | None = None
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
        data_requirements=db_report.data_requirements or [],
        fact_table=db_report.fact_table,
        narrative=db_report.narrative,
        markdown=db_report.markdown,
        status=db_report.status,
        violations=db_report.violations,
        quality_eval=db_report.quality_eval,
        error=db_report.error,
        created_at=db_report.created_at,
    )


class RatingIn(BaseModel):
    rating: int
    comment: str | None = None

    @field_validator("rating")
    @classmethod
    def one_to_five(cls, value: int) -> int:
        if value < 1 or value > 5:
            raise ValueError("rating must be 1..5")
        return value


class RatingOut(BaseModel):
    id: str
    report_id: str
    rating: int


@router.post("/reports/{report_id}/rating", response_model=RatingOut)
def post_report_rating(
    report_id: str,
    body: RatingIn,
    current_user: CurrentUser,
    session: Session = Depends(get_session),
) -> RatingOut:
    db_report = get_report(report_id, session)
    if db_report is None:
        raise HTTPException(status_code=404, detail=f"report not found: {report_id}")
    saved = save_rating(
        session,
        report_id=report_id,
        user_id=current_user.user_id,
        rating=body.rating,
        comment=body.comment,
    )
    return RatingOut(id=saved.id, report_id=saved.report_id, rating=saved.rating)
