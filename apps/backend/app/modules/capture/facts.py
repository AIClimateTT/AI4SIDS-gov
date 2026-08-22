from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

from app.core.contracts import Fact
from app.modules.capture.schemas import CaptureIncident, CaptureWorkingSet
from app.modules.sitreps.log_metrics import LOG_METRIC_FUNCTIONS
from app.modules.sitreps.models import SitrepIncident
from app.modules.survey123.metrics import METRIC_FUNCTIONS

CORP_INCIDENT_METRICS = (
    "incident_count",
    "incident_register",
    "casualty_summary",
    "special_needs_count",
    "estimated_damage_total",
)

CORP_LOG_METRICS = (
    "relief_stock_summary",
    "activity_log",
)

CORP_SITREP_METRICS = CORP_INCIDENT_METRICS + CORP_LOG_METRICS

# Appear in tables/prose only when the officer recorded a positive figure.
_OMIT_WHEN_ZERO = frozenset({"special_needs_count", "estimated_damage_total"})


def _is_presentable(fact: Fact) -> bool:
    if fact.metric not in _OMIT_WHEN_ZERO:
        return True
    value = fact.value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value > 0
    return bool(value)


def _parse_event_date(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _decimal_cost(value: float | None) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def _follow_up_flags(incident: CaptureIncident) -> dict[str, bool]:
    return {
        "relief_supplied": bool(incident.relief_supplied),
        "forwarded_to_agency": bool(incident.forwarded_to_agency),
        "further_assessment_required": bool(incident.further_assessment_required),
        "other": bool(incident.other_follow_up),
    }


def working_set_incident_rows(
    working: CaptureWorkingSet,
    *,
    corporation: str,
    event_id: int | None,
) -> list:
    return [
        SimpleNamespace(
            corporation=corporation,
            event_id=event_id,
            row_id=incident.row_id,
            incident_type=incident.incident_type,
            raw_incident_type=incident.raw_incident_type,
            community=incident.community,
            street=incident.street,
            incident_summary=incident.incident_summary,
            action_taken=incident.action_taken,
            event_date=_parse_event_date(incident.event_date),
            injuries_occurred=incident.injuries_occurred,
            injuries_count=incident.injuries_count,
            deaths_occurred=incident.deaths_occurred,
            deaths_count=incident.deaths_count,
            building_damage=incident.building_damage,
            special_needs_occupants=incident.special_needs_occupants,
            estimated_damage_cost=_decimal_cost(incident.estimated_damage_cost),
            follow_up_flags=_follow_up_flags(incident),
            validation_status="validated",
            record_ref=f"{corporation}:{event_id or '-'}:{incident.row_id}",
            global_id=None,
        )
        for incident in working.incidents
    ]


def working_set_log_rows(
    working: CaptureWorkingSet,
    *,
    corporation: str,
) -> list:
    return [
        SimpleNamespace(
            id=index,
            submission_id=0,
            category=log.category,
            statement=log.statement,
            item=log.item,
            quantity=log.quantity,
            unit=log.unit,
            status=log.status,
            record_ref=f"{corporation}:log:{log.row_id or index}",
            global_id=None,
        )
        for index, log in enumerate(working.logs, start=1)
    ]


def assemble_working_set_facts(
    working: CaptureWorkingSet,
    *,
    corporation: str,
    event_id: int | None,
) -> list[Fact]:
    incidents = working_set_incident_rows(
        working, corporation=corporation, event_id=event_id
    )
    logs = working_set_log_rows(working, corporation=corporation)
    params = {"corporation": corporation}
    facts: list[Fact] = []
    for name in CORP_INCIDENT_METRICS:
        facts.extend(
            METRIC_FUNCTIONS[name](
                params,
                session=None,
                model=SitrepIncident,
                rows=incidents,
            )
        )
    for name in CORP_LOG_METRICS:
        facts.extend(LOG_METRIC_FUNCTIONS[name](params, session=None, rows=logs))
    return [fact for fact in facts if _is_presentable(fact)]
