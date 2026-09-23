import csv
import hashlib
import logging
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.contracts import IngestResult
from app.modules.survey123.models import FieldObservation
from app.modules.survey123.normalize import (
    normalize_corporation,
    normalize_incident_type,
    normalize_validation_status,
    parse_follow_up_flags,
    parse_occupants,
)

logger = logging.getLogger(__name__)

PII_COLUMNS = [
    "Name of Person",
    "Contact Information",
    "Identification Card Number",
    "Name of Second Person",
    "Second Contact Information",
    "Second Identification Card Number",
    "Please list the names of the occupants and their relation",
    "Name of Officer",
    "Position",
]

DUPLICATE_MARKER = "duplicate entry"

REQUIRED_COLUMNS = ("ObjectID", "GlobalID")


class IngestFormatError(Exception):
    """A Survey123 CSV the officer can fix. The API maps this to HTTP 400."""

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


def require_survey123_headers(fieldnames: list[str] | None) -> None:
    present = set(fieldnames or [])
    missing = [name for name in REQUIRED_COLUMNS if name not in present]
    if not missing:
        return
    joined = ", ".join(missing)
    raise IngestFormatError(
        f"Survey123 CSV is missing required column(s): {joined}. "
        "ObjectID and GlobalID are required, and dates must be ISO-8601 "
        "(2024-06-01T09:00:00)."
    )


def parse_bool(raw: str | None) -> bool:
    return (raw or "").strip().lower() == "true"


def parse_int(raw: str | None) -> int | None:
    cleaned = (raw or "").strip()
    return int(cleaned) if cleaned.isdigit() else None


def parse_float(raw: str | None) -> float | None:
    cleaned = (raw or "").strip()
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_decimal(raw: str | None) -> Decimal | None:
    cleaned = (raw or "").strip()
    if not cleaned:
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def _cell(row: dict[str, str], column: str) -> str:
    return (row.get(column) or "").strip()


def _require_global_id(row: dict[str, str], row_number: int) -> str:
    value = _cell(row, "GlobalID")
    if not value:
        raise IngestFormatError(f"Row {row_number}: GlobalID is required")
    return value


def _require_object_id(row: dict[str, str], row_number: int) -> int:
    raw = _cell(row, "ObjectID")
    if not raw:
        raise IngestFormatError(f"Row {row_number}: ObjectID is required")
    try:
        return int(raw)
    except ValueError:
        raise IngestFormatError(
            f"Row {row_number}: ObjectID must be a whole number"
        ) from None


def _parse_datetime_cell(row: dict[str, str], column: str, row_number: int) -> datetime | None:
    raw = _cell(row, column)
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        raise IngestFormatError(
            f"Row {row_number}: {column} must be an ISO-8601 datetime "
            "(2024-06-01T09:00:00)"
        ) from None


def compute_dedup_hash(id_number_raw: str | None, salt: str) -> str | None:
    cleaned = (id_number_raw or "").strip()
    if not cleaned:
        return None
    return hashlib.sha256((salt + cleaned).encode("utf-8")).hexdigest()


def is_duplicate_marker(name_raw: str | None, summary_raw: str | None) -> bool:
    return (name_raw or "").strip().lower() == DUPLICATE_MARKER or (
        summary_raw or ""
    ).strip().lower() == DUPLICATE_MARKER


def parse_row(row: dict[str, str], salt: str, *, row_number: int = 2) -> dict:
    corporation, raw_corporation = normalize_corporation(row.get("Municipal Boundary"))
    incident_type, raw_incident_type = normalize_incident_type(row.get("Incident Type"))
    address = (row.get("Address") or "").strip()
    street = address.split(",")[0].strip() if address else None

    return {
        "global_id": _require_global_id(row, row_number),
        "object_id": _require_object_id(row, row_number),
        "corporation": corporation,
        "raw_corporation": raw_corporation,
        "community": (row.get("Community") or "").strip() or None,
        "street": street or None,
        "incident_type": incident_type,
        "raw_incident_type": raw_incident_type,
        "incident_type_other": (row.get("Other - Incident Type") or "").strip() or None,
        "incident_summary": (row.get("Incident Summary") or "").strip() or None,
        "event_date": _parse_datetime_cell(row, "Date of Event", row_number),
        "event_time": (row.get("Time of Event") or "").strip() or None,
        "assessment_date": _parse_datetime_cell(row, "Assessment Date", row_number),
        "creation_date": _parse_datetime_cell(row, "CreationDate", row_number),
        "edit_date": _parse_datetime_cell(row, "EditDate", row_number),
        "occupants_count": parse_occupants(
            row.get("Household Occupants"), row.get("If more than 6 persons - Household Occupants")
        ),
        "injuries_occurred": parse_bool(row.get("Did any injuries occur?")),
        "injuries_count": parse_int(row.get("Injuries")),
        "deaths_occurred": parse_bool(row.get("Did any deaths occur?")),
        "deaths_count": parse_int(row.get("Deaths")),
        "building_damage": (row.get("Building Damage") or "").strip() or None,
        "crops_livestock": (row.get("Crops and Livestock") or "").strip() or None,
        "personal_items": (row.get("Personal Items") or "").strip() or None,
        "furniture_appliances": (row.get("Furniture and Appliances") or "").strip() or None,
        "action_taken": (row.get("Action Taken") or "").strip() or None,
        "relief_items": (row.get("Relief Items") or "").strip() or None,
        "shelter": (row.get("Shelter") or "").strip() or None,
        "special_needs_occupants": parse_int(row.get("Please indicate the number of special needs occupants")),
        "estimated_damage_cost": parse_decimal(row.get("Estimate Cost of Damage")),
        "follow_up": (row.get("Follow Up Recommendation") or "").strip() or None,
        "follow_up_flags": parse_follow_up_flags(row.get("Follow Up Recommendation")),
        "validation_status": normalize_validation_status(row.get("Validated/NotValidated")),
        "flood_type": (row.get("Flood Type") or "").strip() or None,
        "flood_trigger": (row.get("Flood Trigger") or "").strip() or None,
        "flood_height": (row.get("Flood Height") or "").strip() or None,
        "lon": parse_float(row.get("x")),
        "lat": parse_float(row.get("y")),
        "dedup_hash": compute_dedup_hash(row.get("Identification Card Number"), salt),
    }


def ingest_csv(file_path: Path, session: Session, salt: str) -> IngestResult:
    with open(file_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        require_survey123_headers(list(reader.fieldnames or []))
        raw_rows = list(reader)

    # Spreadsheet row: the header is row 1, so the first data row is row 2.
    parsed = [
        (raw, parse_row(raw, salt, row_number=index + 2))
        for index, raw in enumerate(raw_rows)
    ]

    batch_groups: dict[tuple[str, datetime], list[int]] = {}
    for idx, (_raw, fields) in enumerate(parsed):
        if fields["dedup_hash"] is not None and fields["event_date"] is not None:
            key = (fields["dedup_hash"], fields["event_date"])
            batch_groups.setdefault(key, []).append(idx)

    in_batch_duplicate_indices: set[int] = set()
    for indices in batch_groups.values():
        if len(indices) > 1:
            in_batch_duplicate_indices.update(indices)

    rows_read = 0
    rows_inserted = 0
    rows_updated = 0
    duplicates_flagged = 0
    unmapped_values: dict[str, list[str]] = {}

    for idx, (raw, fields) in enumerate(parsed):
        rows_read += 1

        if fields["raw_corporation"]:
            values = unmapped_values.setdefault("Municipal Boundary", [])
            if fields["raw_corporation"] not in values:
                values.append(fields["raw_corporation"])
        if fields["raw_incident_type"]:
            values = unmapped_values.setdefault("Incident Type", [])
            if fields["raw_incident_type"] not in values:
                values.append(fields["raw_incident_type"])

        is_duplicate = False
        duplicate_reason: str | None = None

        if is_duplicate_marker(raw.get("Name of Person"), raw.get("Incident Summary")):
            is_duplicate = True
            duplicate_reason = "marker"
        elif idx in in_batch_duplicate_indices:
            is_duplicate = True
            duplicate_reason = "repeated_id_date"
        elif fields["dedup_hash"] is not None and fields["event_date"] is not None:
            existing_match = (
                session.execute(
                    select(FieldObservation).where(
                        FieldObservation.dedup_hash == fields["dedup_hash"],
                        FieldObservation.event_date == fields["event_date"],
                        FieldObservation.global_id != fields["global_id"],
                    )
                )
                .scalars()
                .first()
            )
            if existing_match is not None:
                is_duplicate = True
                duplicate_reason = "repeated_id_date"

        if is_duplicate:
            duplicates_flagged += 1

        existing = (
            session.execute(select(FieldObservation).where(FieldObservation.global_id == fields["global_id"]))
            .scalars()
            .first()
        )

        if existing is None:
            incident = FieldObservation(
                **fields,
                is_duplicate=is_duplicate,
                duplicate_reason=duplicate_reason,
                source_file=str(file_path),
                ingested_at=datetime.now(timezone.utc),
            )
            session.add(incident)
            rows_inserted += 1
        else:
            incoming_edit_date = fields["edit_date"]
            if incoming_edit_date is not None and (
                existing.edit_date is None or incoming_edit_date > existing.edit_date
            ):
                for key, value in fields.items():
                    setattr(existing, key, value)
                existing.is_duplicate = is_duplicate
                existing.duplicate_reason = duplicate_reason
                existing.source_file = str(file_path)
                existing.ingested_at = datetime.now(timezone.utc)
                rows_updated += 1

    session.commit()

    return IngestResult(
        rows_read=rows_read,
        rows_inserted=rows_inserted,
        rows_updated=rows_updated,
        duplicates_flagged=duplicates_flagged,
        unmapped_values=unmapped_values,
        pii_columns_dropped=list(PII_COLUMNS),
    )
