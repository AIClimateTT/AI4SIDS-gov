from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.sitreps.models import Event, SitrepIncident, SituationLog, Submission


def create_event(
    session: Session,
    *,
    corporation: str,
    title: str,
    hazard_type: str,
    started_at: datetime,
    ended_at: datetime | None = None,
) -> Event:
    event = Event(
        corporation=corporation,
        title=title,
        hazard_type=hazard_type,
        started_at=started_at,
        ended_at=ended_at,
        created_at=datetime.now(timezone.utc),
    )
    session.add(event)
    session.commit()
    return event


def get_event(session: Session, event_id: int) -> Event | None:
    return session.get(Event, event_id)


def list_events(session: Session, corporation: str) -> list[Event]:
    stmt = (
        select(Event)
        .where(Event.corporation == corporation)
        .order_by(Event.started_at.desc(), Event.id.desc())
    )
    return list(session.scalars(stmt).all())


def next_sequence_no(session: Session, corporation: str, event_id: int | None) -> int:
    # A submission with no event is standalone: it never accumulates a sequence,
    # so "Situation Report #N" numbering only exists within an event.
    if event_id is None:
        return 1
    current = session.scalar(
        select(func.max(Submission.sequence_no)).where(
            Submission.corporation == corporation,
            Submission.event_id == event_id,
        )
    )
    return (current or 0) + 1


def create_submission(
    session: Session,
    *,
    corporation: str,
    as_at: datetime,
    event_id: int | None = None,
    alert_level: str = "none",
    present_activity: str | None = None,
    situation_overview: str | None = None,
    source_file: str | None = None,
) -> Submission:
    submission = Submission(
        corporation=corporation,
        event_id=event_id,
        as_at=as_at,
        alert_level=alert_level,
        present_activity=present_activity,
        situation_overview=situation_overview,
        sequence_no=next_sequence_no(session, corporation, event_id),
        source_file=source_file,
        ingested_at=datetime.now(timezone.utc),
    )
    session.add(submission)
    session.commit()
    return submission


def latest_submission(
    session: Session, corporation: str, event_id: int | None = None
) -> Submission | None:
    stmt = select(Submission).where(Submission.corporation == corporation)
    if event_id is not None:
        stmt = stmt.where(Submission.event_id == event_id)
    stmt = stmt.order_by(Submission.as_at.desc(), Submission.id.desc()).limit(1)
    return session.scalars(stmt).first()


def list_submissions(
    session: Session,
    *,
    corporation: str | None = None,
    event_id: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> list[Submission]:
    """Newest first. EVERY filter is optional — the DMU dashboard passes only a
    window and must get all fourteen corporations back."""
    stmt = select(Submission)
    if corporation is not None:
        stmt = stmt.where(Submission.corporation == corporation)
    if event_id is not None:
        stmt = stmt.where(Submission.event_id == event_id)
    if date_from is not None:
        stmt = stmt.where(Submission.as_at >= date_from)
    if date_to is not None:
        # date_to arrives as a date-only string parsed to midnight; compare
        # against the start of the next day so the whole day is included.
        stmt = stmt.where(Submission.as_at < date_to + timedelta(days=1))
    stmt = stmt.order_by(Submission.as_at.desc(), Submission.id.desc())
    return list(session.scalars(stmt).all())


def submission_counts(session: Session, submission_id: int) -> tuple[int, int]:
    """(incidents, logs) attributed to this submission."""
    incidents = session.scalar(
        select(func.count()).select_from(SitrepIncident).where(
            SitrepIncident.submission_id == submission_id
        )
    ) or 0
    logs = session.scalar(
        select(func.count()).select_from(SituationLog).where(
            SituationLog.submission_id == submission_id
        )
    ) or 0
    return incidents, logs
