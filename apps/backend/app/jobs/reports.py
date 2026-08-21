from app.core.contracts import DataRequirement
from app.core.engine import generate_report
from app.core.report_store import apply_generated_report, get_report, mark_report_failed, mark_report_running
from app.core.template_store import get_template_version
from app.db import SessionLocal


def run_generate_report(report_id: str) -> None:
    from app.core.llm import get_llm_client
    session = SessionLocal()
    try:
        row = get_report(report_id, session)
        if row is None:
            return
        mark_report_running(row, session)
        template = get_template_version(row.template, row.template_version, session)
        if template is None:
            mark_report_failed(row, session, f"unknown template: {row.template}")
            return
        override = row.data_requirements or None
        requirements = (
            [DataRequirement.model_validate(item) for item in override]
            if override
            else None
        )
        generated = generate_report(
            template,
            row.params,
            session,
            get_llm_client("batch"),
            data_requirements=requirements,
            request_id=row.id,
        )
        apply_generated_report(row, generated, session)
    except Exception as exc:
        session.rollback()
        row = get_report(report_id, session)
        if row is not None:
            mark_report_failed(row, session, str(exc))
        else:
            raise
    finally:
        session.close()
