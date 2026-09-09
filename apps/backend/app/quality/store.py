import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.quality.claims import recompute_claim_rates
from app.quality.contracts import QualityEval
from app.quality.models import ReportRating, WorkflowEvent
from app.core.report_models import Report


def record_event(
    session: Session,
    *,
    workflow: str,
    step: str,
    outcome: str,
    subject_id: str | None = None,
    user_id: uuid.UUID | None = None,
    assisted: bool = False,
) -> WorkflowEvent:
    row = WorkflowEvent(
        id=str(uuid.uuid4()),
        workflow=workflow,
        step=step,
        outcome=outcome,
        subject_id=subject_id,
        user_id=user_id,
        assisted=assisted,
        created_at=datetime.now(timezone.utc),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def list_events(
    session: Session,
    *,
    subject_id: str | None = None,
    workflow: str | None = None,
) -> list[WorkflowEvent]:
    query = session.query(WorkflowEvent)
    if subject_id is not None:
        query = query.filter(WorkflowEvent.subject_id == subject_id)
    if workflow is not None:
        query = query.filter(WorkflowEvent.workflow == workflow)
    return list(query.order_by(WorkflowEvent.created_at.asc()).all())


def get_event(session: Session, event_id: str) -> WorkflowEvent | None:
    return session.get(WorkflowEvent, event_id)


def set_assisted(session: Session, event_id: str, assisted: bool) -> WorkflowEvent | None:
    row = get_event(session, event_id)
    if row is None:
        return None
    row.assisted = assisted
    session.commit()
    session.refresh(row)
    return row


def save_rating(
    session: Session,
    *,
    report_id: str,
    user_id: uuid.UUID,
    rating: int,
    comment: str | None = None,
) -> ReportRating:
    existing = (
        session.query(ReportRating)
        .filter(ReportRating.report_id == report_id, ReportRating.user_id == user_id)
        .one_or_none()
    )
    if existing is None:
        existing = ReportRating(
            id=str(uuid.uuid4()),
            report_id=report_id,
            user_id=user_id,
            rating=rating,
            comment=comment,
            created_at=datetime.now(timezone.utc),
        )
        session.add(existing)
    else:
        existing.rating = rating
        existing.comment = comment
    session.commit()
    session.refresh(existing)
    return existing


def apply_claim_verdict(
    row: Report, claim_id: str, verdict: str
) -> QualityEval:
    if not row.quality_eval:
        raise KeyError(claim_id)
    eval_ = QualityEval.model_validate(row.quality_eval)
    found = False
    updated_claims = []
    for claim in eval_.claims.claims:
        if claim.claim_id == claim_id:
            found = True
            updated_claims.append(claim.model_copy(update={"human_verdict": verdict}))
        else:
            updated_claims.append(claim)
    if not found:
        raise KeyError(claim_id)
    claims = recompute_claim_rates(eval_.claims.model_copy(update={"claims": updated_claims}))
    return eval_.model_copy(update={"claims": claims})
