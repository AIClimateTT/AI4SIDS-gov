from datetime import datetime
from typing import Literal

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.core.contracts import Citation, Fact
from app.modules.survey123.models import Incident


def parse_date_param(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)


def build_window_label(date_from: str | None, date_to: str | None) -> str:
    if date_from is None and date_to is None:
        return "all"
    from_label = date_from or "earliest"
    to_label = date_to or "latest"
    return f"{from_label}..{to_label}"


def build_scope(params: dict, **extra: str) -> dict[str, str]:
    scope = {
        "corporation": params.get("corporation") or "all",
        "community": params.get("community") or "all",
        "window": build_window_label(params.get("date_from"), params.get("date_to")),
    }
    scope.update(extra)
    return scope


def build_query_ref(metric_name: str, params: dict) -> str:
    parts = [f"{k}={v}" for k, v in sorted(params.items()) if v is not None and v is not False]
    return f"{metric_name}(" + ", ".join(parts) + ")"


def determine_verification(statuses: list[str]) -> Literal["validated", "pending", "mixed", "n/a"]:
    unique = set(statuses)
    if not unique:
        return "n/a"
    if unique == {"validated"}:
        return "validated"
    if unique == {"pending"}:
        return "pending"
    return "mixed"


def build_citation(metric_name: str, index: int, params: dict, global_ids: list[str], description: str) -> Citation:
    ordered = sorted(global_ids)
    record_ids = ordered[:200] if len(ordered) <= 200 else None
    return Citation(
        cid=f"survey123-{metric_name}-{index}",
        module="survey123",
        description=description,
        query_ref=build_query_ref(metric_name, params),
        record_ids=record_ids,
        as_of=datetime.now(),
    )


def base_query(params: dict) -> Select:
    stmt = select(Incident).where(Incident.is_duplicate.is_(False))
    if params.get("corporation") is not None:
        stmt = stmt.where(Incident.corporation == params["corporation"])
    if params.get("community") is not None:
        stmt = stmt.where(Incident.community == params["community"])
    date_from = parse_date_param(params.get("date_from"))
    if date_from is not None:
        stmt = stmt.where(Incident.event_date >= date_from)
    date_to = parse_date_param(params.get("date_to"))
    if date_to is not None:
        stmt = stmt.where(Incident.event_date <= date_to)
    if not params.get("include_pending", False):
        stmt = stmt.where(Incident.validation_status == "validated")
    return stmt


def incident_count(params: dict, session: Session) -> list[Fact]:
    rows = session.execute(base_query(params)).scalars().all()

    breakdown: dict[str, int] = {}
    for r in rows:
        key = r.incident_type or "(no incident type recorded)"
        breakdown[key] = breakdown.get(key, 0) + 1

    global_ids = [r.global_id for r in rows]
    citation = build_citation(
        "incident_count",
        0,
        params,
        global_ids,
        f"Survey123 incident count, {build_window_label(params.get('date_from'), params.get('date_to'))}",
    )

    return [
        Fact(
            metric="incident_count",
            value=len(rows),
            unit="incidents",
            scope=build_scope(params),
            breakdown=breakdown or None,
            verification=determine_verification([r.validation_status for r in rows]),
            citation=citation,
        )
    ]


def incidents_by_corporation(params: dict, session: Session) -> list[Fact]:
    rows = session.execute(base_query(params)).scalars().all()

    breakdown: dict[str, int] = {}
    for r in rows:
        key = r.corporation or "(no corporation recorded)"
        breakdown[key] = breakdown.get(key, 0) + 1

    global_ids = [r.global_id for r in rows]
    citation = build_citation(
        "incidents_by_corporation",
        0,
        params,
        global_ids,
        f"Survey123 incidents by corporation, {build_window_label(params.get('date_from'), params.get('date_to'))}",
    )

    return [
        Fact(
            metric="incidents_by_corporation",
            value=len(rows),
            unit="incidents",
            scope=build_scope(params),
            breakdown=breakdown or None,
            verification=determine_verification([r.validation_status for r in rows]),
            citation=citation,
        )
    ]
