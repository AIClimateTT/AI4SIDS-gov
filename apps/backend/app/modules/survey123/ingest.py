import hashlib
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation

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
]

DUPLICATE_MARKER = "duplicate entry"


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


def parse_datetime(raw: str | None) -> datetime | None:
    cleaned = (raw or "").strip()
    if not cleaned:
        return None
    return datetime.fromisoformat(cleaned)


def compute_dedup_hash(id_number_raw: str | None, salt: str) -> str | None:
    cleaned = (id_number_raw or "").strip()
    if not cleaned:
        return None
    return hashlib.sha256((salt + cleaned).encode("utf-8")).hexdigest()


def is_duplicate_marker(name_raw: str | None, summary_raw: str | None) -> bool:
    return (name_raw or "").strip().lower() == DUPLICATE_MARKER or (
        summary_raw or ""
    ).strip().lower() == DUPLICATE_MARKER


def parse_row(row: dict[str, str], salt: str) -> dict:
    corporation, raw_corporation = normalize_corporation(row.get("Municipal Boundary"))
    incident_type, raw_incident_type = normalize_incident_type(row.get("Incident Type"))
    address = (row.get("Address") or "").strip()
    street = address.split(",")[0].strip() if address else None

    return {
        "global_id": row["GlobalID"].strip(),
        "object_id": int(row["ObjectID"]),
        "corporation": corporation,
        "raw_corporation": raw_corporation,
        "community": (row.get("Community") or "").strip() or None,
        "street": street or None,
        "incident_type": incident_type,
        "raw_incident_type": raw_incident_type,
        "incident_type_other": (row.get("Other - Incident Type") or "").strip() or None,
        "incident_summary": (row.get("Incident Summary") or "").strip() or None,
        "event_date": parse_datetime(row.get("Date of Event")),
        "event_time": (row.get("Time of Event") or "").strip() or None,
        "assessment_date": parse_datetime(row.get("Assessment Date")),
        "creation_date": parse_datetime(row.get("CreationDate")),
        "edit_date": parse_datetime(row.get("EditDate")),
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
        "officer_name": (row.get("Name of Officer") or "").strip() or None,
        "officer_position": (row.get("Position") or "").strip() or None,
        "dedup_hash": compute_dedup_hash(row.get("Identification Card Number"), salt),
    }
