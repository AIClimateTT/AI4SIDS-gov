from app.core.contracts import FactTable, Template
from app.quality.contracts import CompletenessScore

_FILING_HEADINGS = (
    ("incident_count", "Situation summary", "value_and_breakdown"),
    ("relief_stock_summary", "Relief and resources", "truthy_value"),
    ("incident_register", "Incidents", "any_fact"),
    ("activity_log", "Activities", "any_fact"),
)


def _metric_covered(module: str, metric: str, fact_table: FactTable) -> bool:
    if any(fact.metric == metric for fact in fact_table.facts):
        return True
    needle = f"{module}.{metric}"
    return any(needle in gap for gap in fact_table.gaps)


def _has_heading(markdown: str, heading: str) -> bool:
    return f"## {heading}" in markdown or heading in markdown.splitlines()


def _real_gaps(fact_table: FactTable) -> list[str]:
    return [
        gap
        for gap in fact_table.gaps
        if gap.strip() and gap.strip().lower() != "none"
    ]


def _facts_for(fact_table: FactTable, metric: str):
    return [fact for fact in fact_table.facts if fact.metric == metric]


def score_completeness(
    template: Template, fact_table: FactTable, markdown: str
) -> CompletenessScore:
    expected: list[str] = []
    present: list[str] = []

    for requirement in template.data_requirements:
        key = f"{requirement.module}.{requirement.metric}"
        expected.append(key)
        if _metric_covered(requirement.module, requirement.metric, fact_table):
            present.append(key)

    if template.render.layout == "filing":
        for metric, heading, rule in _FILING_HEADINGS:
            facts = _facts_for(fact_table, metric)
            justified = False
            if rule == "value_and_breakdown":
                justified = any(fact.value and fact.breakdown for fact in facts)
            elif rule == "truthy_value":
                justified = any(fact.value for fact in facts)
            elif rule == "any_fact":
                justified = bool(facts)
            if justified:
                expected.append(heading)
                if _has_heading(markdown, heading):
                    present.append(heading)
        gaps = _real_gaps(fact_table)
        if gaps:
            expected.append("Data Gaps")
            if _has_heading(markdown, "Data Gaps") or _has_heading(
                markdown, "Information not yet available"
            ):
                present.append("Data Gaps")
    else:
        if any(fact.breakdown for fact in fact_table.facts):
            expected.append("Data Tables")
            if _has_heading(markdown, "Data Tables"):
                present.append("Data Tables")
        if _real_gaps(fact_table):
            expected.append("Data Gaps")
            if _has_heading(markdown, "Data Gaps"):
                present.append("Data Gaps")

    if template.render.include_citation_appendix:
        expected.append("Citation Appendix")
        if _has_heading(markdown, "Citation Appendix"):
            present.append("Citation Appendix")

    missing = [item for item in expected if item not in present]
    rate = 1.0 if not expected else len(present) / len(expected)
    return CompletenessScore(
        expected=expected, present=present, missing=missing, rate=rate
    )
