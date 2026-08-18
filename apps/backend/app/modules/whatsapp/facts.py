import uuid
from datetime import datetime, timezone

from app.core.contracts import Citation, Fact, FactTable
from app.modules.whatsapp.extract import DraftIncident, DraftLog


def included_attributed_incidents(
    incidents: list[DraftIncident],
) -> list[DraftIncident]:
    return [
        row
        for row in incidents
        if row.included and row.corporation is not None
    ]


def included_attributed_logs(logs: list[DraftLog]) -> list[DraftLog]:
    return [row for row in logs if row.included and row.corporation is not None]


def _incident_value(row: DraftIncident) -> tuple[int | float | str, str | None]:
    if row.injuries_count is not None:
        return row.injuries_count, "injuries"
    if row.deaths_count is not None:
        return row.deaths_count, "deaths"
    return 1, "incident"


def _log_value(row: DraftLog) -> tuple[int | float | str, str | None]:
    if row.quantity is not None:
        return row.quantity, row.unit
    return 1, "statement"


def _incident_breakdown(row: DraftIncident) -> dict[str, int | float] | None:
    breakdown: dict[str, int | float] = {}
    if row.injuries_count is not None:
        breakdown["injuries"] = row.injuries_count
    if row.deaths_count is not None:
        breakdown["deaths"] = row.deaths_count
    return breakdown or None


def facts_from_working_set(
    incidents: list[DraftIncident],
    logs: list[DraftLog],
    as_at: datetime,
    request_id: str | None = None,
) -> FactTable:
    """Build a pending fact table from included, attributed draft rows only."""
    facts: list[Fact] = []
    cid_index = 1

    def next_cid() -> str:
        nonlocal cid_index
        cid = f"C{cid_index:03d}"
        cid_index += 1
        return cid

    for row in included_attributed_incidents(incidents):
        value, unit = _incident_value(row)
        facts.append(
            Fact(
                metric="whatsapp_incident",
                value=value,
                unit=unit,
                scope={
                    "corporation": row.corporation or "all",
                    "community": row.community or "all",
                    "summary": row.incident_summary,
                },
                breakdown=_incident_breakdown(row),
                verification="pending",
                citation=Citation(
                    cid=next_cid(),
                    module="whatsapp",
                    description=(
                        f"WhatsApp draft, message {row.source_index}, unconfirmed"
                    ),
                    query_ref=f"whatsapp.message:{row.source_index}",
                    record_ids=None,
                    as_of=as_at,
                ),
            )
        )

    for row in included_attributed_logs(logs):
        value, unit = _log_value(row)
        facts.append(
            Fact(
                metric="whatsapp_log",
                value=value,
                unit=unit,
                scope={
                    "corporation": row.corporation or "all",
                    "category": row.category,
                    "statement": row.statement,
                },
                breakdown=None,
                verification="pending",
                citation=Citation(
                    cid=next_cid(),
                    module="whatsapp",
                    description=(
                        f"WhatsApp draft, message {row.source_index}, unconfirmed"
                    ),
                    query_ref=f"whatsapp.message:{row.source_index}",
                    record_ids=None,
                    as_of=as_at,
                ),
            )
        )

    return FactTable(
        request_id=request_id or str(uuid.uuid4()),
        template="whatsapp_hour_briefing",
        template_version=1,
        params={"as_at": as_at.isoformat()},
        generated_at=datetime.now(timezone.utc),
        facts=facts,
        gaps=[],
    )
