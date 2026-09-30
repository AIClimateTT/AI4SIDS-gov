"""Read-back of stored incidents from both sources.

Survey123 rows live in field_observations and corporation incidents live in
sitrep_incidents. They stay separate tables. This list only projects the
columns an officer scans, tagged with which table the row came from.
"""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.localtime import as_utc
from app.modules.sitreps.models import SitrepIncident
from app.modules.survey123.models import FieldObservation

SOURCES = ("all", "survey123", "sitreps")


def list_incidents(
    session: Session,
    *,
    page: int = 1,
    page_size: int = 10,
    q: str | None = None,
    source: str = "all",
) -> tuple[list[dict], int]:
    if source not in SOURCES:
        raise ValueError(f"source must be one of: {', '.join(SOURCES)}")

    rows: list[dict] = []
    if source in ("all", "survey123"):
        rows.extend(_field_row(row) for row in session.scalars(select(FieldObservation)))
    if source in ("all", "sitreps"):
        rows.extend(_sitrep_row(row) for row in session.scalars(select(SitrepIncident)))

    needle = (q or "").strip().lower()
    if needle:
        rows = [row for row in rows if _matches(row, needle)]

    rows.sort(key=_sort_key, reverse=True)

    page = max(page, 1)
    page_size = max(min(page_size, 100), 1)
    start = (page - 1) * page_size
    return rows[start : start + page_size], len(rows)


def _sort_key(row: dict) -> tuple:
    event_date = row["event_date"]
    # Dated rows sort ahead of undated ones when reversed, then newest first.
    return (event_date is not None, event_date or date.min, as_utc(row["ingested_at"]))


def _matches(row: dict, needle: str) -> bool:
    haystack = " ".join(
        str(row[name] or "")
        for name in ("corporation", "community", "incident_type", "incident_summary")
    ).lower()
    return needle in haystack


def _field_row(row: FieldObservation) -> dict:
    return {
        "id": f"survey123:{row.id}",
        "source": "survey123",
        "corporation": row.corporation,
        "community": row.community,
        "incident_type": row.incident_type,
        "event_date": row.event_date,
        "incident_summary": row.incident_summary,
        "injuries_occurred": row.injuries_occurred,
        "injuries_count": row.injuries_count,
        "deaths_occurred": row.deaths_occurred,
        "deaths_count": row.deaths_count,
        "ingested_at": as_utc(row.ingested_at),
        "validation_status": row.validation_status,
        "is_duplicate": row.is_duplicate,
    }


def _sitrep_row(row: SitrepIncident) -> dict:
    return {
        "id": f"sitreps:{row.id}",
        "source": "sitreps",
        "corporation": row.corporation,
        "community": row.community,
        "incident_type": row.incident_type,
        "event_date": row.event_date,
        "incident_summary": row.incident_summary,
        "injuries_occurred": row.injuries_occurred,
        "injuries_count": row.injuries_count,
        "deaths_occurred": row.deaths_occurred,
        "deaths_count": row.deaths_count,
        "ingested_at": as_utc(row.ingested_at),
        "validation_status": None,
        "is_duplicate": None,
    }
