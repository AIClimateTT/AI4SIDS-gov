"""Merge an officer-authored CSV into a capture working set.

This is not ingest. Rows land on the draft session so chat, the Facts pane,
and Issue all see them. POST /submissions still files a CSV as a submission
for non-corp callers; the corp UI does not.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime
from decimal import Decimal
from typing import Literal

from app.core.contracts import RowErrorInfo
from app.modules.capture.provenance import incident_path, log_path
from app.modules.capture.schemas import CaptureIncident, CaptureLog, CaptureWorkingSet
from app.modules.capture.turn import _assign_row_ids
from app.modules.sitreps.parse import parse_incident_row, parse_log_row

CsvKind = Literal["incidents", "logs"]


def read_csv_bytes(data: bytes) -> list[dict[str, str]]:
    text = data.decode("utf-8-sig")
    if not text.strip():
        return []
    return list(csv.DictReader(io.StringIO(text)))


def _event_date_cell(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    return str(value)


def _cost_cell(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def incident_from_parsed(fields: dict) -> CaptureIncident:
    flags = fields.get("follow_up_flags") or {}
    return CaptureIncident(
        row_id=fields["row_id"],
        community=fields.get("community"),
        street=fields.get("street"),
        incident_type=fields.get("incident_type"),
        raw_incident_type=fields.get("raw_incident_type"),
        incident_summary=fields.get("incident_summary"),
        event_date=_event_date_cell(fields.get("event_date")),
        injuries_occurred=fields.get("injuries_occurred"),
        injuries_count=fields.get("injuries_count"),
        deaths_occurred=fields.get("deaths_occurred"),
        deaths_count=fields.get("deaths_count"),
        building_damage=fields.get("building_damage"),
        special_needs_occupants=fields.get("special_needs_occupants"),
        estimated_damage_cost=_cost_cell(fields.get("estimated_damage_cost")),
        action_taken=fields.get("action_taken"),
        relief_supplied=flags.get("relief_supplied"),
        forwarded_to_agency=flags.get("forwarded_to_agency"),
        further_assessment_required=flags.get("further_assessment_required"),
        other_follow_up=flags.get("other"),
    )


def log_from_parsed(fields: dict) -> CaptureLog:
    return CaptureLog(
        category=fields["category"],
        statement=fields["statement"],
        item=fields.get("item"),
        quantity=fields.get("quantity"),
        unit=fields.get("unit"),
        status=fields.get("status"),
    )


def _pin_incident(manual: list[str], row_id: str) -> list[str]:
    prefix = f"incident:{row_id}."
    kept = [path for path in manual if not path.startswith(prefix)]
    return kept + [
        incident_path(row_id, name)
        for name in CaptureIncident.model_fields
        if name != "row_id"
    ]


def _pin_log(manual: list[str], row_id: str) -> list[str]:
    prefix = f"log:{row_id}."
    kept = [path for path in manual if not path.startswith(prefix)]
    return kept + [
        log_path(row_id, name) for name in CaptureLog.model_fields if name != "row_id"
    ]


def _merge_incidents(
    existing: list[CaptureIncident], incoming: list[CaptureIncident]
) -> list[CaptureIncident]:
    by_id = {item.row_id: item for item in existing}
    order = list(existing)
    for item in incoming:
        if item.row_id in by_id:
            index = next(i for i, row in enumerate(order) if row.row_id == item.row_id)
            order[index] = item
        else:
            order.append(item)
        by_id[item.row_id] = item
    return order


def import_csv_rows(
    working: CaptureWorkingSet,
    *,
    kind: CsvKind,
    rows: list[dict[str, str]],
) -> tuple[CaptureWorkingSet, list[RowErrorInfo]]:
    """Parse CSV-shaped dicts and merge accepted rows into the working set.

    Incident Row IDs replace an existing row with the same id. Logs have no
    spreadsheet id, so they always append. Rejected rows are reported and
    skipped; they do not abort the batch.
    """
    errors: list[RowErrorInfo] = []
    manual = list(working.manual_fields)

    if kind == "incidents":
        accepted: list[CaptureIncident] = []
        seen: dict[str, CaptureIncident] = {}
        for number, raw in enumerate(rows, start=2):
            fields, error = parse_incident_row(raw, number)
            if error is not None:
                errors.append(
                    RowErrorInfo(
                        file="incidents",
                        row_number=error.row_number,
                        reason=error.reason,
                    )
                )
                continue
            incident = incident_from_parsed(fields)
            seen[incident.row_id] = incident
        accepted = list(seen.values())
        incidents = _merge_incidents(working.incidents, accepted)
        for incident in accepted:
            manual = _pin_incident(manual, incident.row_id)
        return working.model_copy(update={"incidents": incidents, "manual_fields": manual}), errors

    accepted_logs: list[CaptureLog] = []
    for number, raw in enumerate(rows, start=2):
        fields, error = parse_log_row(raw, number)
        if error is not None:
            errors.append(
                RowErrorInfo(file="logs", row_number=error.row_number, reason=error.reason)
            )
            continue
        accepted_logs.append(log_from_parsed(fields))
    logs = _assign_row_ids([*working.logs, *accepted_logs])
    imported_ids = {row.row_id for row in logs[len(working.logs) :]}
    for row_id in imported_ids:
        manual = _pin_log(manual, row_id)
    return working.model_copy(update={"logs": logs, "manual_fields": manual}), errors
