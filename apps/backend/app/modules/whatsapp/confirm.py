import csv
import tempfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.contracts import SubmissionIngestResult
from app.modules.sitreps.ingest import ingest_submission
from app.modules.sitreps.store import create_event
from app.modules.survey123.normalize import CANONICAL_CORPORATIONS
from app.modules.whatsapp.extract import ProposedIncident, ProposedLog
from app.modules.whatsapp.parse import redact_phones

INCIDENT_HEADER = [
    "Row ID",
    "Community",
    "Street",
    "Incident Type",
    "Date of Event",
    "Incident Summary",
    "Injuries Occurred",
    "Injuries Count",
    "Deaths Occurred",
    "Deaths Count",
    "Building Damage",
    "Special Needs Occupants",
    "Estimated Damage Cost",
    "Action Taken",
    "Relief Supplied",
    "Forwarded To Agency",
    "Further Assessment Required",
    "Other Follow Up",
]

LOG_HEADER = ["Category", "Statement", "Item", "Quantity", "Unit", "Status"]


class ConfirmError(ValueError):
    pass


def _redact(value: str | None) -> str | None:
    if value is None:
        return None
    redacted, _ = redact_phones(value)
    return redacted


def _yes_no(count: int | None) -> str:
    return "True" if count is not None and count > 0 else "False"


def _incident_row(proposal: ProposedIncident, row_id: str, as_at: datetime) -> list:
    event_date = proposal.event_date or as_at.date().isoformat()
    summary, _ = redact_phones(proposal.incident_summary)
    return [
        row_id,
        _redact(proposal.community) or "",
        _redact(proposal.street) or "",
        proposal.incident_type or "",
        event_date,
        summary,
        _yes_no(proposal.injuries_count),
        "" if proposal.injuries_count is None else str(proposal.injuries_count),
        _yes_no(proposal.deaths_count),
        "" if proposal.deaths_count is None else str(proposal.deaths_count),
        "",
        "",
        "",
        "",
        "False",
        "False",
        "False",
        "False",
    ]


def _log_row(proposal: ProposedLog) -> list:
    statement, _ = redact_phones(proposal.statement)
    return [
        proposal.category,
        statement,
        _redact(proposal.item) or "",
        "" if proposal.quantity is None else str(proposal.quantity),
        proposal.unit or "",
        proposal.status or "",
    ]


def _write_csv(path: Path, header: list[str], rows: list[list]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def _require_canonical(rows: list[ProposedIncident] | list[ProposedLog]) -> None:
    for row in rows:
        if row.corporation not in CANONICAL_CORPORATIONS:
            raise ConfirmError(
                "every selected row needs a corporation from the fourteen regional corporations"
            )


def confirm_proposals(
    session: Session,
    *,
    as_at: datetime,
    filename: str,
    incidents: list[ProposedIncident],
    logs: list[ProposedLog],
) -> list[SubmissionIngestResult]:
    if not incidents and not logs:
        raise ConfirmError("select at least one row")
    _require_canonical(incidents)
    _require_canonical(logs)

    grouped_incidents: dict[str, list[ProposedIncident]] = defaultdict(list)
    grouped_logs: dict[str, list[ProposedLog]] = defaultdict(list)
    order: list[str] = []
    for row in incidents:
        corp = row.corporation
        assert corp is not None
        if corp not in order:
            order.append(corp)
        grouped_incidents[corp].append(row)
    for row in logs:
        corp = row.corporation
        assert corp is not None
        if corp not in order:
            order.append(corp)
        grouped_logs[corp].append(row)

    source_name = f"whatsapp:{filename or 'export.txt'}"
    results: list[SubmissionIngestResult] = []

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        for corporation in order:
            corp_incidents = grouped_incidents[corporation]
            corp_logs = grouped_logs[corporation]
            event_id = None
            if corp_incidents:
                event = create_event(
                    session,
                    corporation=corporation,
                    title=f"WhatsApp update {as_at.date().isoformat()}",
                    hazard_type="other",
                    started_at=as_at,
                )
                event_id = event.id

            incidents_path = None
            logs_path = None
            if corp_incidents:
                incidents_path = tmp_path / f"{corporation}-incidents.csv"
                rows = [
                    _incident_row(proposal, f"wa-{index}", as_at)
                    for index, proposal in enumerate(corp_incidents, start=1)
                ]
                _write_csv(incidents_path, INCIDENT_HEADER, rows)
            if corp_logs:
                logs_path = tmp_path / f"{corporation}-logs.csv"
                _write_csv(
                    logs_path, LOG_HEADER, [_log_row(proposal) for proposal in corp_logs]
                )

            results.append(
                ingest_submission(
                    session,
                    corporation=corporation,
                    as_at=as_at,
                    event_id=event_id,
                    alert_level="none",
                    incidents_path=incidents_path,
                    logs_path=logs_path,
                    source_name=source_name,
                )
            )

    return results
