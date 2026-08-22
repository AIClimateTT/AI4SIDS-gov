import csv
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.contracts import RowErrorInfo, SubmissionIngestResult
from app.modules.sitreps.models import SitrepIncident, SituationLog
from app.modules.sitreps.models import Submission
from app.modules.sitreps.parse import (
    INCIDENT_PII_COLUMNS,
    parse_corp_int,
    parse_incident_row,
    parse_log_row,
)
from app.modules.sitreps.store import next_sequence_no


def _read_rows(path: Path) -> list[dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _stringify_row(row: dict) -> dict[str, str]:
    return {str(key): "" if value is None else str(value) for key, value in row.items()}


def apply_structured_incident_defaults(
    row: dict[str, str], as_at: datetime
) -> dict[str, str]:
    """Fill fields a conversation may leave blank so parse_incident_row can run.

    CSV uploads do not go through this: a missing Date of Event in a spreadsheet
    is a row error, not a guess.
    """
    out = dict(row)
    if not (out.get("Date of Event") or "").strip():
        out["Date of Event"] = as_at.date().isoformat()
    injuries = parse_corp_int(out.get("Injuries Count"))
    if not (out.get("Injuries Occurred") or "").strip() and isinstance(injuries, int):
        out["Injuries Occurred"] = "yes" if injuries > 0 else "no"
    deaths = parse_corp_int(out.get("Deaths Count"))
    if not (out.get("Deaths Occurred") or "").strip() and isinstance(deaths, int):
        out["Deaths Occurred"] = "yes" if deaths > 0 else "no"
    return out


def ingest_submission(
    session: Session,
    *,
    corporation: str,
    as_at: datetime,
    event_id: int | None = None,
    alert_level: str = "none",
    present_activity: str | None = None,
    situation_overview: str | None = None,
    incidents_path: Path | None = None,
    logs_path: Path | None = None,
    source_name: str | None = None,
    incident_rows: list[dict] | None = None,
    log_rows: list[dict] | None = None,
    structured_defaults: bool = False,
    commit: bool = True,
) -> SubmissionIngestResult:
    """Create one submission and load its incident and log rows.

    Both files are parsed in full before anything is written, and the submission
    plus all of its child rows commit in a single transaction, so a submission
    never lands half-populated. Individual bad rows are collected and reported;
    they do not abort the batch.

    ``incidents_path``/``logs_path`` are wherever the caller spooled the CSV
    to on disk -- for the API that's a tempfile path, meaningless once the
    request ends. ``source_name`` is the human-meaningful name to record on
    the submission instead (e.g. the filename the corp actually uploaded).
    When both files are present, callers should pass them comma-separated.

    ``incident_rows``/``log_rows`` are the same CSV-shaped dicts, already in
    memory (conversation capture). When provided they take precedence over
    the file paths. ``structured_defaults`` fills blank dates and casualty
    flags; it must stay off for spreadsheet uploads.
    """
    if incident_rows is not None:
        loaded_incidents = [_stringify_row(row) for row in incident_rows]
    else:
        loaded_incidents = _read_rows(incidents_path) if incidents_path else []
    if log_rows is not None:
        loaded_logs = [_stringify_row(row) for row in log_rows]
    else:
        loaded_logs = _read_rows(logs_path) if logs_path else []

    if structured_defaults:
        loaded_incidents = [
            apply_structured_incident_defaults(row, as_at) for row in loaded_incidents
        ]

    incident_rows = loaded_incidents
    log_rows = loaded_logs

    row_errors: list[RowErrorInfo] = []
    unmapped_values: dict[str, list[str]] = {}

    parsed_incidents: list[dict] = []
    # start=2: the header occupies spreadsheet row 1, so the first data row is
    # row 2. These numbers are read by a corp officer looking at their own file.
    for number, raw in enumerate(incident_rows, start=2):
        fields, error = parse_incident_row(raw, number)
        if error is not None:
            row_errors.append(
                RowErrorInfo(file="incidents", row_number=error.row_number, reason=error.reason)
            )
            continue
        if fields["raw_incident_type"]:
            values = unmapped_values.setdefault("Incident Type", [])
            if fields["raw_incident_type"] not in values:
                values.append(fields["raw_incident_type"])
        parsed_incidents.append(fields)

    parsed_logs: list[dict] = []
    # start=2: the header occupies spreadsheet row 1, so the first data row is
    # row 2. These numbers are read by a corp officer looking at their own file.
    for number, raw in enumerate(log_rows, start=2):
        fields, error = parse_log_row(raw, number)
        if error is not None:
            row_errors.append(
                RowErrorInfo(file="logs", row_number=error.row_number, reason=error.reason)
            )
            continue
        parsed_logs.append(fields)

    if source_name is not None:
        source_file = source_name
    elif incidents_path or logs_path:
        # Fallback for callers that do not pass the real uploaded/provided
        # name: derive it from whatever path we were handed. For the API this
        # would be a tempfile path (superseded by source_name in practice),
        # but it keeps this function usable standalone, e.g. from tests.
        source_file = str(incidents_path or logs_path)
    else:
        source_file = None

    # Build the Submission inline and flush (not store.create_submission, which
    # commits): the submission and its child rows must land in ONE transaction,
    # or a failure mid-write leaves an orphaned submission with no rows behind it.
    # flush() assigns submission.id without ending the transaction.
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
    session.flush()

    inserted = 0
    updated = 0
    now = datetime.now(timezone.utc)

    # Tracks every SitrepIncident this batch has already staged, keyed by row_id.
    # The DB lookup below only sees rows that have actually been flushed, and
    # production's SessionLocal is autoflush=False (app/db.py), so two rows with
    # the same Row ID in one CSV would otherwise both miss the DB lookup and both
    # get inserted -- surfacing only as an IntegrityError at the final commit,
    # which would abort the whole submission. Checking this dict first makes
    # supersession work regardless of session autoflush configuration.
    #
    # This dict is intentionally NOT gated on event_id. Cross-submission
    # supersession is event-scoped (see the comment below), but a repeated
    # Row ID *within a single file* is a restatement either way -- even for an
    # event-less submission, which never supersedes rows from an earlier
    # submission but must still collapse duplicates inside itself.
    staged_by_row_id: dict[str, SitrepIncident] = {}

    for fields in parsed_incidents:
        row_id = fields["row_id"]
        existing = staged_by_row_id.get(row_id)

        # Explicit lookup rather than relying on the unique index: event_id is
        # nullable, and SQL does not collide NULLs, so an event-less submission
        # is standalone by design rather than by accident of the constraint.
        if existing is None and event_id is not None:
            existing = session.scalars(
                select(SitrepIncident).where(
                    SitrepIncident.corporation == corporation,
                    SitrepIncident.event_id == event_id,
                    SitrepIncident.row_id == row_id,
                )
            ).first()

        if existing is None:
            existing = SitrepIncident(
                **fields,
                submission_id=submission.id,
                corporation=corporation,
                event_id=event_id,
                ingested_at=now,
            )
            session.add(existing)
            inserted += 1
        else:
            for key, value in fields.items():
                setattr(existing, key, value)
            existing.submission_id = submission.id
            existing.ingested_at = now
            updated += 1

        staged_by_row_id[row_id] = existing

    for fields in parsed_logs:
        session.add(SituationLog(**fields, submission_id=submission.id))

    submission.row_errors = [e.model_dump() for e in row_errors]
    if commit:
        session.commit()
    else:
        session.flush()

    return SubmissionIngestResult(
        submission_id=submission.id,
        sequence_no=submission.sequence_no,
        incidents_read=len(incident_rows),
        incidents_inserted=inserted,
        incidents_updated=updated,
        logs_read=len(log_rows),
        logs_inserted=len(parsed_logs),
        row_errors=row_errors,
        unmapped_values=unmapped_values,
        pii_columns_dropped=list(INCIDENT_PII_COLUMNS),
    )
