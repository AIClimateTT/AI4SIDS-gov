import math
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation

from app.modules.sitreps.models import LOG_CATEGORIES, LOG_STATUSES
from app.modules.survey123.normalize import normalize_incident_type

INCIDENT_PII_COLUMNS = ["Name of Person", "Contact Information"]


@dataclass(frozen=True)
class RowError:
    row_number: int
    reason: str


def _clean(raw: str | None) -> str | None:
    cleaned = (raw or "").strip()
    return cleaned or None


# Sentinel for "this cell had content that could not be read", kept distinct
# from None, which means "this cell was empty". Collapsing the two is exactly
# what let "$12,500" become None and report TTD 0.
UNPARSEABLE = object()

TRUE_VALUES = {"true", "yes", "y", "1"}
FALSE_VALUES = {"false", "no", "n", "0"}


def parse_corp_bool(raw: str | None) -> bool | None:
    """None means unparseable. An empty cell is False, not an error.

    survey123's parse_bool treats everything that is not "true" as False,
    which is right for a machine-generated export and wrong here: corps type
    these by hand, and "Yes" silently becoming False zeroes a relief count in
    a ministerial report.
    """
    cleaned = _clean(raw)
    if cleaned is None:
        return False
    lowered = cleaned.lower()
    if lowered in TRUE_VALUES:
        return True
    if lowered in FALSE_VALUES:
        return False
    return None


def parse_corp_decimal(raw: str | None) -> "Decimal | None | object":
    """Returns Decimal, None for an empty cell, or UNPARSEABLE.

    Accepts what a person types: a leading currency symbol and thousands
    separators. "$12,500" is a number; "about ten grand" is a row error.
    """
    cleaned = _clean(raw)
    if cleaned is None:
        return None
    stripped = cleaned.lstrip("$").replace(",", "").strip()
    try:
        return Decimal(stripped)
    except InvalidOperation:
        return UNPARSEABLE


def parse_corp_int(raw: str | None) -> "int | None | object":
    """Returns int, None for an empty cell, or UNPARSEABLE."""
    cleaned = _clean(raw)
    if cleaned is None:
        return None
    try:
        return int(cleaned.replace(",", ""))
    except ValueError:
        return UNPARSEABLE


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

    numeric_cells = {
        "Injuries Count": "injuries_count",
        "Deaths Count": "deaths_count",
        "Special Needs Occupants": "special_needs_occupants",
    }
    numbers: dict[str, int | None] = {}
    for column, field in numeric_cells.items():
        value = parse_corp_int(row.get(column))
        if value is UNPARSEABLE:
            return None, RowError(
                row_number=row_number,
                reason=f"{column} is not a whole number: {_clean(row.get(column))!r}",
            )
        numbers[field] = value

    cost = parse_corp_decimal(row.get("Estimated Damage Cost"))
    if cost is UNPARSEABLE:
        return None, RowError(
            row_number=row_number,
            reason=f"Estimated Damage Cost is not a number: "
            f"{_clean(row.get('Estimated Damage Cost'))!r}",
        )

    boolean_cells = {
        "Injuries Occurred": "injuries_occurred",
        "Deaths Occurred": "deaths_occurred",
        "Relief Supplied": "relief_supplied",
        "Forwarded To Agency": "forwarded_to_agency",
        "Further Assessment Required": "further_assessment_required",
        "Other Follow Up": "other",
    }
    flags: dict[str, bool] = {}
    for column, field in boolean_cells.items():
        value = parse_corp_bool(row.get(column))
        if value is None:
            return None, RowError(
                row_number=row_number,
                reason=f"{column} is not yes or no: {_clean(row.get(column))!r}",
            )
        flags[field] = value

    return (
        {
            "row_id": row_id,
            "community": _clean(row.get("Community")),
            "street": _clean(row.get("Street")),
            "incident_type": incident_type,
            "raw_incident_type": raw_incident_type,
            "incident_summary": _clean(row.get("Incident Summary")),
            "event_date": event_date,
            "injuries_occurred": flags["injuries_occurred"],
            "injuries_count": numbers["injuries_count"],
            "deaths_occurred": flags["deaths_occurred"],
            "deaths_count": numbers["deaths_count"],
            "building_damage": _clean(row.get("Building Damage")),
            "special_needs_occupants": numbers["special_needs_occupants"],
            "estimated_damage_cost": cost,
            "action_taken": _clean(row.get("Action Taken")),
            "follow_up_flags": {
                "relief_supplied": flags["relief_supplied"],
                "forwarded_to_agency": flags["forwarded_to_agency"],
                "further_assessment_required": flags["further_assessment_required"],
                "other": flags["other"],
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
