from datetime import datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.contracts import DataRequirement, Template
from app.core.engine import GeneratedReport
from app.core.report_models import Report


def add_report(report: GeneratedReport, session: Session) -> Report:
    db_report = Report(
        id=report.request_id,
        template=report.template,
        template_version=report.template_version,
        params=report.params,
        data_requirements=[r.model_dump() for r in report.data_requirements],
        fact_table=report.fact_table.model_dump(mode="json"),
        narrative=report.narrative,
        markdown=report.markdown,
        status=report.status,
        error=None,
        violations=[v.model_dump() for v in report.violations],
        quality_eval=report.quality_eval.model_dump(mode="json") if report.quality_eval else None,
        created_at=datetime.now(timezone.utc),
    )
    session.add(db_report)
    return db_report


def save_report(report: GeneratedReport, session: Session) -> Report:
    db_report = add_report(report, session)
    session.commit()
    return db_report


def save_placeholder_report(
    session: Session,
    *,
    report_id: str,
    template: Template,
    params: dict,
    data_requirements: list[DataRequirement] | None,
) -> Report:
    now = datetime.now(timezone.utc)
    db_report = Report(
        id=report_id,
        template=template.name,
        template_version=template.version,
        params=params,
        data_requirements=[r.model_dump() for r in (data_requirements or [])],
        fact_table={
            "request_id": report_id,
            "template": template.name,
            "template_version": template.version,
            "params": params,
            "generated_at": now.isoformat(),
            "facts": [],
            "gaps": [],
        },
        narrative="",
        markdown="",
        status="queued",
        error=None,
        violations=[],
        quality_eval=None,
        created_at=now,
    )
    session.add(db_report)
    session.commit()
    session.refresh(db_report)
    return db_report


def mark_report_running(row: Report, session: Session) -> Report:
    row.status = "running"
    session.commit()
    session.refresh(row)
    return row


def mark_report_failed(row: Report, session: Session, error: str) -> Report:
    row.status = "failed"
    row.error = error[:2000]
    session.commit()
    session.refresh(row)
    return row


def apply_generated_report(row: Report, report: GeneratedReport, session: Session) -> Report:
    row.template = report.template
    row.template_version = report.template_version
    row.params = report.params
    row.data_requirements = [r.model_dump() for r in report.data_requirements]
    row.fact_table = report.fact_table.model_dump(mode="json")
    row.narrative = report.narrative
    row.markdown = report.markdown
    row.status = report.status
    row.error = None
    row.violations = [v.model_dump() for v in report.violations]
    row.quality_eval = (
        report.quality_eval.model_dump(mode="json") if report.quality_eval else None
    )
    session.commit()
    session.refresh(row)
    return row


def get_report(report_id: str, session: Session) -> Report | None:
    return session.get(Report, report_id)


def list_reports(
    session: Session,
    *,
    page: int = 1,
    page_size: int = 10,
    q: str | None = None,
    status: str | None = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> tuple[list[Report], int]:
    filters = []

    if status and status != "all":
        filters.append(Report.status == status)

    if q:
        pattern = f"%{q.strip()}%"
        filters.append(or_(Report.id.ilike(pattern), Report.template.ilike(pattern)))

    count_stmt = select(func.count()).select_from(Report)
    if filters:
        count_stmt = count_stmt.where(*filters)
    total = session.scalar(count_stmt) or 0

    sortable = {
        "created_at": Report.created_at,
        "template": Report.template,
        "status": Report.status,
        "id": Report.id,
    }
    sort_column = sortable.get(sort_by, Report.created_at)
    order = sort_column.asc() if sort_order == "asc" else sort_column.desc()

    page = max(page, 1)
    page_size = max(min(page_size, 100), 1)
    offset = (page - 1) * page_size

    list_stmt = select(Report)
    if filters:
        list_stmt = list_stmt.where(*filters)
    list_stmt = list_stmt.order_by(order).offset(offset).limit(page_size)

    items = list(session.scalars(list_stmt).all())
    return items, total
