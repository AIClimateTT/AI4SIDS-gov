from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.contracts import Fact, MetricSpec
from app.modules.sitreps.models import SituationLog, Submission
from app.modules.survey123.metrics import (
    METRIC_PARAMS_SCHEMA,
    build_citation,
    build_scope,
    build_window_label,
    determine_verification,
    record_ref_of,
)


def load_log_rows(params: dict, session: Session | None, rows=None) -> list:
    if rows is not None:
        return list(rows)
    if session is None:
        raise ValueError("session is required when rows are not supplied")
    stmt = select(SituationLog)
    if params.get("submission_id"):
        stmt = stmt.where(SituationLog.submission_id == int(params["submission_id"]))
    elif params.get("corporation"):
        stmt = stmt.join(Submission, SituationLog.submission_id == Submission.id).where(
            Submission.corporation == params["corporation"]
        )
    return list(session.execute(stmt).scalars().all())


def _quantity(row) -> float | None:
    value = getattr(row, "quantity", None)
    if value is None:
        return None
    return float(value)


def relief_stock_summary(params: dict, session: Session | None = None, rows=None) -> list[Fact]:
    logs = load_log_rows(params, session, rows)
    quantified = [row for row in logs if _quantity(row) is not None]
    facts: list[Fact] = []
    for index, row in enumerate(quantified):
        item = (getattr(row, "item", None) or getattr(row, "statement", "") or "item").strip()
        citation = build_citation(
            "relief_stock_summary",
            index,
            params,
            [record_ref_of(row)],
            f"SITREP relief or stock, {build_window_label(params.get('date_from'), params.get('date_to'))}",
            SituationLog,
        )
        facts.append(
            Fact(
                metric="relief_stock_summary",
                value=_quantity(row),
                unit=getattr(row, "unit", None) or "units",
                scope=build_scope(
                    params,
                    item=item,
                    category=getattr(row, "category", "") or "",
                    status=getattr(row, "status", None) or "",
                    statement=getattr(row, "statement", "") or "",
                ),
                breakdown=None,
                verification=determine_verification(["validated"]),
                citation=citation,
            )
        )
    return facts


def activity_log(params: dict, session: Session | None = None, rows=None) -> list[Fact]:
    logs = load_log_rows(params, session, rows)
    statements = [row for row in logs if _quantity(row) is None and (getattr(row, "statement", None) or "").strip()]
    facts: list[Fact] = []
    for index, row in enumerate(statements):
        statement = row.statement.strip()
        citation = build_citation(
            "activity_log",
            index,
            params,
            [record_ref_of(row)],
            f"SITREP activity, {build_window_label(params.get('date_from'), params.get('date_to'))}",
            SituationLog,
        )
        facts.append(
            Fact(
                metric="activity_log",
                value=statement,
                unit=None,
                scope=build_scope(params, category=getattr(row, "category", "") or ""),
                breakdown=None,
                verification=determine_verification(["validated"]),
                citation=citation,
            )
        )
    return facts


LOG_METRIC_FUNCTIONS = {
    "relief_stock_summary": relief_stock_summary,
    "activity_log": activity_log,
}

LOG_METRIC_SPECS = [
    MetricSpec(
        name="relief_stock_summary",
        description="Quantified situation logs (relief distributed and remaining stock) by item.",
        params_schema=METRIC_PARAMS_SCHEMA,
        module="sitreps",
    ),
    MetricSpec(
        name="activity_log",
        description="Non-quantity situation-log statements as attributed text facts.",
        params_schema=METRIC_PARAMS_SCHEMA,
        module="sitreps",
    ),
]
