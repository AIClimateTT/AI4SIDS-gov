from app.core.report_store import apply_generated_report, get_report, mark_report_failed, mark_report_running
from app.quality.store import record_event
from app.db import SessionLocal
from app.modules.whatsapp.briefing import BriefingError, generate_briefing
from app.modules.whatsapp.extract import extract_proposals, to_draft_incidents, to_draft_logs
from app.modules.whatsapp.parse import parse_export
from app.modules.whatsapp.store import (
    draft_incidents,
    draft_logs,
    get_draft,
    mark_draft_failed,
    mark_draft_ready,
    mark_draft_running,
)


def run_extract(draft_id: int) -> None:
    from app.core.llm import get_llm_client

    session = SessionLocal()
    try:
        draft = get_draft(session, draft_id)
        if draft is None or not draft.source_text:
            return
        mark_draft_running(draft, session)
        messages = parse_export(draft.source_text)
        extracted = extract_proposals(messages, get_llm_client("batch"))
        mark_draft_ready(
            draft,
            session,
            incidents=to_draft_incidents(extracted.incidents),
            logs=to_draft_logs(extracted.logs),
        )
    except Exception as exc:
        session.rollback()
        draft = get_draft(session, draft_id)
        if draft is not None:
            mark_draft_failed(draft, session, str(exc))
        else:
            raise
    finally:
        session.close()


def run_briefing(draft_id: int, report_id: str) -> None:
    from app.core.llm import get_llm_client

    session = SessionLocal()
    try:
        row = get_report(report_id, session)
        draft = get_draft(session, draft_id)
        if row is None or draft is None:
            return
        mark_report_running(row, session)
        generated = generate_briefing(
            draft_incidents(draft),
            draft_logs(draft),
            draft.as_at,
            get_llm_client("batch"),
        )
        generated = generated.model_copy(update={"request_id": report_id})
        apply_generated_report(row, generated, session)
        record_event(
            session,
            workflow="whatsapp_briefing",
            step="briefing",
            outcome="succeeded",
            subject_id=report_id,
        )
    except BriefingError as exc:
        session.rollback()
        row = get_report(report_id, session)
        if row is not None:
            mark_report_failed(row, session, str(exc))
    except Exception as exc:
        session.rollback()
        row = get_report(report_id, session)
        if row is not None:
            mark_report_failed(row, session, str(exc))
        else:
            raise
    finally:
        session.close()
