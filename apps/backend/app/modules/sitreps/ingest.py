import csv
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.contracts import IngestResult
from app.modules.survey123.ingest import parse_bool, parse_datetime, parse_decimal, parse_int
from app.modules.survey123.models import Incident
from app.modules.survey123.normalize import normalize_corporation, normalize_incident_type

PII_COLUMNS_SITREPS = ["Name of Person", "Contact Information"]


def parse_sitrep_row(row: dict[str, str], corporation: str) -> dict:
    incident_type, raw_incident_type = normalize_incident_type(row.get("Incident Type"))
    row_id = (row.get("Row ID") or "").strip()

    return {
        "global_id": f"sitreps-{corporation}-{row_id}",
        "object_id": int(row_id),
        "corporation": corporation,
        "raw_corporation": None,
        "community": (row.get("Community") or "").strip() or None,
        "street": (row.get("Street") or "").strip() or None,
        "incident_type": incident_type,
        "raw_incident_type": raw_incident_type,
        "incident_type_other": None,
        "incident_summary": (row.get("Incident Summary") or "").strip() or None,
        "event_date": parse_datetime(row.get("Date of Event")),
        "event_time": None,
        "assessment_date": None,
        "creation_date": datetime.now(timezone.utc),
        "edit_date": None,
        "occupants_count": None,
        "injuries_occurred": parse_bool(row.get("Injuries Occurred")),
        "injuries_count": parse_int(row.get("Injuries Count")),
        "deaths_occurred": parse_bool(row.get("Deaths Occurred")),
        "deaths_count": parse_int(row.get("Deaths Count")),
        "building_damage": (row.get("Building Damage") or "").strip() or None,
        "crops_livestock": None,
        "personal_items": None,
        "furniture_appliances": None,
        "action_taken": (row.get("Action Taken") or "").strip() or None,
        "relief_items": None,
        "shelter": None,
        "special_needs_occupants": parse_int(row.get("Special Needs Occupants")),
        "estimated_damage_cost": parse_decimal(row.get("Estimated Damage Cost")),
        "follow_up": None,
        "follow_up_flags": {
            "relief_supplied": parse_bool(row.get("Relief Supplied")),
            "forwarded_to_agency": parse_bool(row.get("Forwarded To Agency")),
            "further_assessment_required": parse_bool(row.get("Further Assessment Required")),
            "other": parse_bool(row.get("Other Follow Up")),
        },
        "validation_status": "validated",
        "flood_type": None,
        "flood_trigger": None,
        "flood_height": None,
        "lon": None,
        "lat": None,
        "officer_name": (row.get("Officer Name") or "").strip() or None,
        "officer_position": (row.get("Officer Position") or "").strip() or None,
        "dedup_hash": None,
        "source": "sitreps",
    }


def ingest_sitrep_csv(file_path: Path, corporation_raw: str, session: Session) -> IngestResult:
    corporation, raw_corporation = normalize_corporation(corporation_raw)
    corporation = corporation or "unmapped"

    with open(file_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        raw_rows = list(reader)

    unmapped_values: dict[str, list[str]] = {}
    if raw_corporation:
        unmapped_values["Corporation"] = [raw_corporation]

    rows_read = 0
    rows_inserted = 0
    rows_updated = 0

    for raw in raw_rows:
        rows_read += 1
        fields = parse_sitrep_row(raw, corporation)

        if fields["raw_incident_type"]:
            values = unmapped_values.setdefault("Incident Type", [])
            if fields["raw_incident_type"] not in values:
                values.append(fields["raw_incident_type"])

        existing = (
            session.execute(select(Incident).where(Incident.global_id == fields["global_id"]))
            .scalars()
            .first()
        )

        if existing is None:
            incident = Incident(
                **fields,
                is_duplicate=False,
                duplicate_reason=None,
                source_file=str(file_path),
                ingested_at=datetime.now(timezone.utc),
            )
            session.add(incident)
            rows_inserted += 1
        else:
            for key, value in fields.items():
                setattr(existing, key, value)
            existing.source_file = str(file_path)
            existing.ingested_at = datetime.now(timezone.utc)
            rows_updated += 1

    session.commit()

    return IngestResult(
        rows_read=rows_read,
        rows_inserted=rows_inserted,
        rows_updated=rows_updated,
        duplicates_flagged=0,
        unmapped_values=unmapped_values,
        pii_columns_dropped=list(PII_COLUMNS_SITREPS),
    )
