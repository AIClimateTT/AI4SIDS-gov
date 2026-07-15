from datetime import datetime
from decimal import Decimal
from typing import Literal

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.core.contracts import Citation, Fact, MetricSpec
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


HOME_AFFECTING_INCIDENT_TYPES = {"flooding_", "fire", "blown_off_roof"}


def homes_affected_count(params: dict, session: Session) -> list[Fact]:
    full_params = dict(params)
    full_params["include_pending"] = True
    rows = session.execute(base_query(full_params)).scalars().all()

    affected = [
        r for r in rows if (r.building_damage or "").strip() or r.incident_type in HOME_AFFECTING_INCIDENT_TYPES
    ]

    breakdown = {"validated": 0, "pending": 0}
    for r in affected:
        if r.validation_status in breakdown:
            breakdown[r.validation_status] += 1

    include_pending = bool(params.get("include_pending", False))
    contributing = affected if include_pending else [r for r in affected if r.validation_status == "validated"]

    global_ids = [r.global_id for r in contributing]
    citation = build_citation(
        "homes_affected_count",
        0,
        params,
        global_ids,
        f"Survey123 homes affected, {build_window_label(params.get('date_from'), params.get('date_to'))}",
    )

    return [
        Fact(
            metric="homes_affected_count",
            value=len(contributing),
            unit="incidents",
            scope=build_scope(params),
            breakdown=breakdown,
            verification=determine_verification([r.validation_status for r in contributing]),
            citation=citation,
        )
    ]


def casualty_summary(params: dict, session: Session) -> list[Fact]:
    rows = session.execute(base_query(params)).scalars().all()

    injury_rows = [r for r in rows if (r.injuries_count or 0) > 0]
    death_rows = [r for r in rows if (r.deaths_count or 0) > 0]

    injuries_citation = build_citation(
        "casualty_summary",
        0,
        params,
        [r.global_id for r in injury_rows],
        f"Survey123 injuries, {build_window_label(params.get('date_from'), params.get('date_to'))}",
    )
    deaths_citation = build_citation(
        "casualty_summary",
        1,
        params,
        [r.global_id for r in death_rows],
        f"Survey123 deaths, {build_window_label(params.get('date_from'), params.get('date_to'))}",
    )

    return [
        Fact(
            metric="casualty_summary",
            value=sum(r.injuries_count or 0 for r in rows),
            unit="persons",
            scope=build_scope(params, category="injuries"),
            breakdown=None,
            verification=determine_verification([r.validation_status for r in injury_rows]),
            citation=injuries_citation,
        ),
        Fact(
            metric="casualty_summary",
            value=sum(r.deaths_count or 0 for r in rows),
            unit="persons",
            scope=build_scope(params, category="deaths"),
            breakdown=None,
            verification=determine_verification([r.validation_status for r in death_rows]),
            citation=deaths_citation,
        ),
    ]


FOLLOW_UP_FLAG_KEYS = ["relief_supplied", "forwarded_to_agency", "further_assessment_required", "other"]


def street_level_tally(params: dict, session: Session) -> list[Fact]:
    rows = session.execute(base_query(params)).scalars().all()

    breakdown: dict[str, int] = {}
    for r in rows:
        community = r.community or "(unknown community)"
        street = r.street or "(unknown street)"
        key = f"{community} / {street}"
        breakdown[key] = breakdown.get(key, 0) + 1

    global_ids = [r.global_id for r in rows]
    citation = build_citation(
        "street_level_tally",
        0,
        params,
        global_ids,
        f"Survey123 street-level tally, {build_window_label(params.get('date_from'), params.get('date_to'))}",
    )

    return [
        Fact(
            metric="street_level_tally",
            value=len(rows),
            unit="incidents",
            scope=build_scope(params),
            breakdown=breakdown or None,
            verification=determine_verification([r.validation_status for r in rows]),
            citation=citation,
        )
    ]


def relief_actions_summary(params: dict, session: Session) -> list[Fact]:
    rows = session.execute(base_query(params)).scalars().all()

    breakdown = {key: 0 for key in FOLLOW_UP_FLAG_KEYS}
    contributing_ids: set[str] = set()
    for r in rows:
        flags = r.follow_up_flags or {}
        any_flag = False
        for key in FOLLOW_UP_FLAG_KEYS:
            if flags.get(key):
                breakdown[key] += 1
                any_flag = True
        if any_flag:
            contributing_ids.add(r.global_id)

    global_ids = sorted(contributing_ids)
    contributing_rows = [r for r in rows if r.global_id in contributing_ids]
    citation = build_citation(
        "relief_actions_summary",
        0,
        params,
        global_ids,
        f"Survey123 relief actions, {build_window_label(params.get('date_from'), params.get('date_to'))}",
    )

    return [
        Fact(
            metric="relief_actions_summary",
            value=len(contributing_ids),
            unit="incidents",
            scope=build_scope(params),
            breakdown=breakdown,
            verification=determine_verification([r.validation_status for r in contributing_rows]),
            citation=citation,
        )
    ]


def special_needs_count(params: dict, session: Session) -> list[Fact]:
    rows = session.execute(base_query(params)).scalars().all()
    contributing = [r for r in rows if (r.special_needs_occupants or 0) > 0]

    global_ids = [r.global_id for r in contributing]
    citation = build_citation(
        "special_needs_count",
        0,
        params,
        global_ids,
        f"Survey123 special needs occupants, {build_window_label(params.get('date_from'), params.get('date_to'))}",
    )

    return [
        Fact(
            metric="special_needs_count",
            value=sum(r.special_needs_occupants or 0 for r in rows),
            unit="persons",
            scope=build_scope(params),
            breakdown=None,
            verification=determine_verification([r.validation_status for r in contributing]),
            citation=citation,
        )
    ]


def estimated_damage_total(params: dict, session: Session) -> list[Fact]:
    rows = session.execute(base_query(params)).scalars().all()
    with_cost = [r for r in rows if r.estimated_damage_cost is not None]

    total = sum((r.estimated_damage_cost for r in with_cost), start=Decimal("0"))
    global_ids = [r.global_id for r in with_cost]
    citation = build_citation(
        "estimated_damage_total",
        0,
        params,
        global_ids,
        f"Survey123 estimated damage cost, {build_window_label(params.get('date_from'), params.get('date_to'))}",
    )

    return [
        Fact(
            metric="estimated_damage_total",
            value=float(total),
            unit="TTD",
            scope=build_scope(params),
            breakdown={"records_reporting_cost": len(with_cost), "records_total": len(rows)},
            verification=determine_verification([r.validation_status for r in with_cost]),
            citation=citation,
        )
    ]


def data_coverage(params: dict, session: Session) -> list[Fact]:
    stmt = select(Incident)
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

    rows = session.execute(stmt).scalars().all()

    by_corp: dict[str, list[Incident]] = {}
    for r in rows:
        key = r.corporation or "(no corporation recorded)"
        by_corp.setdefault(key, []).append(r)

    facts: list[Fact] = []
    for index, (corp_label, corp_rows) in enumerate(sorted(by_corp.items())):
        n = len(corp_rows)
        pct_validated = round(100.0 * sum(1 for r in corp_rows if r.validation_status == "validated") / n, 1)
        pct_duplicates = round(100.0 * sum(1 for r in corp_rows if r.is_duplicate) / n, 1)
        latest = max((r.creation_date for r in corp_rows if r.creation_date is not None), default=None)
        latest_label = latest.isoformat() if latest is not None else "unknown"
        global_ids = [r.global_id for r in corp_rows]
        citation = build_citation(
            "data_coverage",
            index,
            params,
            global_ids,
            f"Survey123 data coverage for {corp_label}, latest record as of {latest_label}",
        )
        facts.append(
            Fact(
                metric="data_coverage",
                value=n,
                unit="records",
                scope=build_scope(params, corporation=corp_label),
                breakdown={"pct_validated": pct_validated, "pct_duplicates": pct_duplicates},
                verification="n/a",
                citation=citation,
            )
        )
    return facts


METRIC_PARAMS_SCHEMA = {
    "type": "object",
    "properties": {
        "corporation": {"type": "string"},
        "community": {"type": "string"},
        "date_from": {"type": "string", "format": "date"},
        "date_to": {"type": "string", "format": "date"},
        "include_pending": {"type": "boolean", "default": False},
    },
}

METRIC_SPECS: list[MetricSpec] = [
    MetricSpec(
        name="incident_count",
        description="Total incidents, breakdown by incident_type.",
        params_schema=METRIC_PARAMS_SCHEMA,
        module="survey123",
    ),
    MetricSpec(
        name="incidents_by_corporation",
        description="Counts per corporation, including a (no corporation recorded) bucket for blanks.",
        params_schema=METRIC_PARAMS_SCHEMA,
        module="survey123",
    ),
    MetricSpec(
        name="homes_affected_count",
        description=(
            "Incidents where building damage text is non-empty OR incident_type is flooding_, fire, "
            "or blown_off_roof; breakdown validated vs pending."
        ),
        params_schema=METRIC_PARAMS_SCHEMA,
        module="survey123",
    ),
    MetricSpec(
        name="casualty_summary",
        description="Injuries and deaths totals, reported as two separate citable facts.",
        params_schema=METRIC_PARAMS_SCHEMA,
        module="survey123",
    ),
    MetricSpec(
        name="street_level_tally",
        description="Incidents grouped by community and street.",
        params_schema=METRIC_PARAMS_SCHEMA,
        module="survey123",
    ),
    MetricSpec(
        name="relief_actions_summary",
        description=(
            "Counts of follow-up actions taken: relief supplied, forwarded to agency, "
            "further assessment required, other."
        ),
        params_schema=METRIC_PARAMS_SCHEMA,
        module="survey123",
    ),
    MetricSpec(
        name="special_needs_count",
        description="Sum of special needs occupants.",
        params_schema=METRIC_PARAMS_SCHEMA,
        module="survey123",
    ),
    MetricSpec(
        name="estimated_damage_total",
        description=(
            "Sum of estimated damage cost where present, with an explicit coverage caveat "
            "(N of M records reporting a cost estimate) — this field is sparsely filled and "
            "must never be presented as a complete total."
        ),
        params_schema=METRIC_PARAMS_SCHEMA,
        module="survey123",
    ),
    MetricSpec(
        name="data_coverage",
        description=(
            "Per-corporation record count, % validated, % duplicates flagged, and latest record "
            "timestamp. Spans all rows including pending and flagged duplicates by design."
        ),
        params_schema=METRIC_PARAMS_SCHEMA,
        module="survey123",
    ),
]

METRIC_FUNCTIONS = {
    "incident_count": incident_count,
    "incidents_by_corporation": incidents_by_corporation,
    "homes_affected_count": homes_affected_count,
    "casualty_summary": casualty_summary,
    "street_level_tally": street_level_tally,
    "relief_actions_summary": relief_actions_summary,
    "special_needs_count": special_needs_count,
    "estimated_damage_total": estimated_damage_total,
    "data_coverage": data_coverage,
}
