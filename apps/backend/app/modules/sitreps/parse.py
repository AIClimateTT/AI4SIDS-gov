import math
from dataclasses import dataclass
from datetime import datetime

from app.modules.sitreps.models import LOG_CATEGORIES, LOG_STATUSES
from app.modules.survey123.ingest import parse_bool, parse_decimal, parse_int
from app.modules.survey123.normalize import normalize_incident_type

INCIDENT_PII_COLUMNS = ["Name of Person", "Contact Information"]


@dataclass(frozen=True)
class RowError:
    row_number: int
    reason: str


def _clean(raw: str | None) -> str | None:
    cleaned = (raw or "").strip()
    return cleaned or None


def parse_incident_row(
    row: dict[str, str], row_number: int
) -> tuple[dict | None, RowError | None]:
    """Parse one incidents.csv row.

    Returns (fields, None) on success or (None, RowError) on a rejectable row.
    Never raises for bad data — a malformed row must not abort the batch, since
    corps author these spreadsheets by hand.
    """
    row_id = _clean(row.get("Row ID"))
    if row_id is None:
        return None, RowError(row_number=row_number, reason="Row ID is required")

    raw_date = _clean(row.get("Date of Event"))
    if raw_date is None:
        return None, RowError(row_number=row_number, reason="Date of Event is required")
    try:
        event_date = datetime.fromisoformat(raw_date)
    except ValueError:
        return None, RowError(
            row_number=row_number,
            reason=f"Date of Event is not an ISO date: {raw_date!r}",
        )

    incident_type, raw_incident_type = normalize_incident_type(row.get("Incident Type"))

    return (
        {
            "row_id": row_id,
            "community": _clean(row.get("Community")),
            "street": _clean(row.get("Street")),
            "incident_type": incident_type,
            "raw_incident_type": raw_incident_type,
            "incident_summary": _clean(row.get("Incident Summary")),
            "event_date": event_date,
            "injuries_occurred": parse_bool(row.get("Injuries Occurred")),
            "injuries_count": parse_int(row.get("Injuries Count")),
            "deaths_occurred": parse_bool(row.get("Deaths Occurred")),
            "deaths_count": parse_int(row.get("Deaths Count")),
            "building_damage": _clean(row.get("Building Damage")),
            "special_needs_occupants": parse_int(row.get("Special Needs Occupants")),
            "estimated_damage_cost": parse_decimal(row.get("Estimated Damage Cost")),
            "action_taken": _clean(row.get("Action Taken")),
            "follow_up_flags": {
                "relief_supplied": parse_bool(row.get("Relief Supplied")),
                "forwarded_to_agency": parse_bool(row.get("Forwarded To Agency")),
                "further_assessment_required": parse_bool(
                    row.get("Further Assessment Required")
                ),
                "other": parse_bool(row.get("Other Follow Up")),
            },
        },
        None,
    )


def parse_log_row(
    row: dict[str, str], row_number: int
) -> tuple[dict | None, RowError | None]:
    """Parse one logs.csv row.

    A log is a prose statement, optionally carrying a structured quantity. Any
    number the report later states must come from the quantity column, so an
    unparseable quantity is rejected rather than silently nulled.
    """
    statement = _clean(row.get("Statement"))
    if statement is None:
        return None, RowError(row_number=row_number, reason="Statement is required")

    category = (_clean(row.get("Category")) or "other").lower()
    if category not in LOG_CATEGORIES:
        return None, RowError(
            row_number=row_number,
            reason=f"Category {category!r} is not one of {', '.join(LOG_CATEGORIES)}",
        )

    quantity: float | None = None
    raw_quantity = _clean(row.get("Quantity"))
    if raw_quantity is not None:
        try:
            quantity = float(raw_quantity)
        except ValueError:
            return None, RowError(
                row_number=row_number,
                reason=f"Quantity is not a number: {raw_quantity!r}",
            )
        if not math.isfinite(quantity):
            return None, RowError(
                row_number=row_number,
                reason=f"Quantity is not a finite number: {raw_quantity!r}",
            )

    status = _clean(row.get("Status"))
    if status is not None and status.lower() not in LOG_STATUSES:
        return None, RowError(
            row_number=row_number,
            reason=f"Status {status!r} is not one of {', '.join(LOG_STATUSES)}",
        )

    return (
        {
            "category": category,
            "statement": statement,
            "item": _clean(row.get("Item")),
            "quantity": quantity,
            "unit": _clean(row.get("Unit")),
            "status": status.lower() if status else None,
        },
        None,
    )
