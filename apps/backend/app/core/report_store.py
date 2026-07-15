from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.engine import GeneratedReport
from app.core.report_models import Report


def save_report(report: GeneratedReport, session: Session) -> Report:
    db_report = Report(
        id=report.request_id,
        template=report.template,
        params=report.params,
        fact_table=report.fact_table.model_dump(mode="json"),
        narrative=report.narrative,
        markdown=report.markdown,
        status=report.status,
        violations=[v.model_dump() for v in report.violations],
        created_at=datetime.now(timezone.utc),
    )
    session.add(db_report)
    session.commit()
    return db_report


def get_report(report_id: str, session: Session) -> Report | None:
    return session.get(Report, report_id)
