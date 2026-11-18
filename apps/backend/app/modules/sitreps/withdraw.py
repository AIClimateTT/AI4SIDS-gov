"""Take a filing back out of the register.

For a submission that should never have been filed (UAT test data reached the
live register as Point Fortin's submission 8). Its incidents, logs and issued
report are deleted. The capture session behind it is kept, marked withdrawn,
so its transcript and turn snapshots stay available for review."""

from dataclasses import dataclass, field

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.report_models import Report
from app.modules.capture.models import CaptureSession
from app.modules.sitreps.models import SitrepIncident, SituationLog, Submission
from app.quality.models import ReportRating


@dataclass
class WithdrawPlan:
    submission_id: int
    corporation: str
    event_id: int | None
    sequence_no: int
    incident_ids: list[int] = field(default_factory=list)
    log_ids: list[int] = field(default_factory=list)
    report_ids: list[str] = field(default_factory=list)
    rating_count: int = 0
    session_ids: list[int] = field(default_factory=list)

    def lines(self) -> list[str]:
        return [
            f"submission {self.submission_id}: {self.corporation}, event {self.event_id}, "
            f"filing #{self.sequence_no}",
            f"incidents to delete: {len(self.incident_ids)}",
            f"situation logs to delete: {len(self.log_ids)}",
            f"reports to delete: {', '.join(self.report_ids) or 'none'}"
            + (f" (with {self.rating_count} ratings)" if self.rating_count else ""),
            f"capture sessions to mark withdrawn (kept for review): "
            f"{', '.join(map(str, self.session_ids)) or 'none'}",
        ]


def plan_withdrawal(db: Session, submission_id: int) -> WithdrawPlan | None:
    submission = db.get(Submission, submission_id)
    if submission is None:
        return None
    sessions = list(
        db.scalars(
            select(CaptureSession).where(CaptureSession.submission_id == submission_id)
        )
    )
    report_ids = {row.report_id for row in sessions if row.report_id}
    # A report issued from this submission names it in its params even when
    # no capture session points at it (e.g. generated from the DMU side).
    for report in db.scalars(select(Report)):
        if (report.params or {}).get("submission_id") == submission_id:
            report_ids.add(report.id)
    ratings = (
        list(db.scalars(select(ReportRating).where(ReportRating.report_id.in_(report_ids))))
        if report_ids
        else []
    )
    return WithdrawPlan(
        submission_id=submission.id,
        corporation=submission.corporation,
        event_id=submission.event_id,
        sequence_no=submission.sequence_no,
        incident_ids=list(
            db.scalars(
                select(SitrepIncident.id).where(SitrepIncident.submission_id == submission_id)
            )
        ),
        log_ids=list(
            db.scalars(select(SituationLog.id).where(SituationLog.submission_id == submission_id))
        ),
        report_ids=sorted(report_ids),
        rating_count=len(ratings),
        session_ids=[row.id for row in sessions],
    )


def withdraw_submission(db: Session, plan: WithdrawPlan) -> None:
    for row in db.scalars(
        select(CaptureSession).where(CaptureSession.id.in_(plan.session_ids))
    ):
        row.status = "withdrawn"
        row.submission_id = None
        row.report_id = None
    db.flush()
    if plan.report_ids:
        db.execute(delete(ReportRating).where(ReportRating.report_id.in_(plan.report_ids)))
        db.execute(delete(Report).where(Report.id.in_(plan.report_ids)))
    db.execute(delete(SitrepIncident).where(SitrepIncident.submission_id == plan.submission_id))
    db.execute(delete(SituationLog).where(SituationLog.submission_id == plan.submission_id))
    db.execute(delete(Submission).where(Submission.id == plan.submission_id))
    db.commit()
