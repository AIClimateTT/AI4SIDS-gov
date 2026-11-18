"""Corp impact totals: households and people affected across a filing's incidents.

Only counts an officer actually stated are summed. A total is emitted per
measure that at least one incident recorded, citing exactly those incidents,
so "24 households" on the filing traces back to the rows that said so."""

from sqlalchemy.orm import Session

from app.core.contracts import Fact, MetricSpec
from app.modules.sitreps.models import SitrepIncident
from app.modules.survey123.metrics import (
    METRIC_PARAMS_SCHEMA,
    build_citation,
    build_scope,
    build_window_label,
    determine_verification,
    load_metric_rows,
    record_ref_of,
)

IMPACT_MEASURES = (
    ("households_affected", "Households affected", "households"),
    ("persons_affected", "Persons affected", "persons"),
    ("persons_displaced", "Persons displaced", "persons"),
    ("persons_marooned", "Persons marooned", "persons"),
)


def impact_summary(
    params: dict, session: Session | None = None, rows=None
) -> list[Fact]:
    incidents = load_metric_rows(params, session, SitrepIncident, rows)
    facts: list[Fact] = []
    for index, (field, label, unit) in enumerate(IMPACT_MEASURES):
        counted = [row for row in incidents if getattr(row, field, None) is not None]
        if not counted:
            continue
        citation = build_citation(
            "impact_summary",
            index,
            params,
            [record_ref_of(row) for row in counted],
            f"SITREP {label.lower()}, "
            f"{build_window_label(params.get('date_from'), params.get('date_to'))}",
            SitrepIncident,
        )
        facts.append(
            Fact(
                metric="impact_summary",
                value=sum(getattr(row, field) for row in counted),
                unit=unit,
                scope=build_scope(params, measure=field, label=label),
                breakdown=None,
                verification=determine_verification(
                    [getattr(row, "validation_status", "validated") for row in counted]
                ),
                citation=citation,
            )
        )
    return facts


IMPACT_METRIC_FUNCTIONS = {"impact_summary": impact_summary}

IMPACT_METRIC_SPECS = [
    MetricSpec(
        name="impact_summary",
        description="Totals of households and persons affected, displaced and marooned, from corp incidents that stated them.",
        params_schema=METRIC_PARAMS_SCHEMA,
        module="sitreps",
    ),
]
