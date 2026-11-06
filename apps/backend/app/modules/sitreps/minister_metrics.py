from collections import Counter
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.contracts import Fact, MetricSpec
from app.modules.sitreps.models import SitrepIncident, SituationLog, Submission
from app.modules.survey123.metrics import (
    METRIC_PARAMS_SCHEMA,
    build_citation,
    build_scope,
    build_window_label,
    incident_type_label,
    parse_date_param,
    record_ref_of,
)


def _day(value: str | datetime | None) -> date | None:
    parsed = parse_date_param(value)
    return parsed.date() if parsed is not None else None


def _latest_per_corporation(params: dict, session: Session) -> list[Submission]:
    date_from = _day(params.get("date_from"))
    date_to = _day(params.get("date_to"))
    latest: dict[str, Submission] = {}
    # The window filters when the submission was filed, not its event: an open
    # event must not pull an old filing into this report.
    for row in session.scalars(
        select(Submission).order_by(Submission.as_at.desc(), Submission.id.desc())
    ):
        # as_at is the officer's Trinidad wall-clock reading, so no conversion.
        day = row.as_at.date()
        if date_from is not None and day < date_from:
            continue
        if date_to is not None and day > date_to:
            continue
        latest.setdefault(row.corporation, row)
    return [latest[corporation] for corporation in sorted(latest)]


def corporation_status(params: dict, session: Session) -> list[Fact]:
    window = build_window_label(params.get("date_from"), params.get("date_to"))
    facts: list[Fact] = []

    def scope(submission: Submission, kind: str) -> dict[str, str]:
        return build_scope(
            params,
            corporation=submission.corporation,
            as_at=submission.as_at.isoformat(),
            submission_id=str(submission.id),
            kind=kind,
        )

    for submission in _latest_per_corporation(params, session):
        logs = session.scalars(
            select(SituationLog)
            .where(SituationLog.submission_id == submission.id)
            .order_by(SituationLog.id)
        ).all()
        for log in logs:
            facts.append(
                Fact(
                    metric="corporation_status",
                    value=log.statement,
                    unit=None,
                    scope=scope(submission, "log"),
                    breakdown=None,
                    verification="pending",
                    citation=build_citation(
                        "corporation_status",
                        len(facts),
                        params,
                        [record_ref_of(log)],
                        f"SITREP situation log, {window}",
                        SituationLog,
                    ),
                )
            )

        if submission.event_id is None:
            continue
        incidents = session.scalars(
            select(SitrepIncident).where(SitrepIncident.event_id == submission.event_id)
        ).all()
        if incidents:
            facts.append(
                Fact(
                    metric="corporation_status",
                    value=len(incidents),
                    unit="incidents",
                    scope=scope(submission, "incidents"),
                    breakdown=dict(Counter(incident_type_label(row) for row in incidents)),
                    verification="pending",
                    citation=build_citation(
                        "corporation_status",
                        len(facts),
                        params,
                        [record_ref_of(row) for row in incidents],
                        f"SITREP incidents for the event, {window}",
                        SitrepIncident,
                    ),
                )
            )
    return facts


MINISTER_METRIC_FUNCTIONS = {"corporation_status": corporation_status}

MINISTER_METRIC_SPECS = [
    MetricSpec(
        name="corporation_status",
        description=(
            "Latest in-window submission per corporation: its situation-log "
            "statements and its event's incident counts by type."
        ),
        params_schema=METRIC_PARAMS_SCHEMA,
        module="sitreps",
    ),
]
