import re

from app.core.citation_check import CitationCheckResult
from app.core.contracts import Fact, FactTable
from app.quality.contracts import NumericalMatch, NumericalScore
from app.quality.denominators import CRITICAL_METRICS

_CRITICAL_VIOLATION_KINDS = {"invented_number", "misattributed_number"}


def _format_number(value: int | float | str) -> str:
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, int):
        return str(value)
    return str(value)


def _parse_scope_number(raw: str) -> float | None:
    cleaned = raw.strip().replace(",", "")
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _expected_figures(fact: Fact) -> list[tuple[str, float | str]]:
    figures: list[tuple[str, float | str]] = [(fact.metric, fact.value)]
    if fact.metric == "incident_register":
        for key in ("injuries", "deaths"):
            raw = fact.scope.get(key)
            if raw is None:
                continue
            parsed = _parse_scope_number(str(raw))
            if parsed is not None:
                figures.append((f"{fact.metric}.{key}", parsed))
    return figures


def _appeared(markdown: str, expected: float | str) -> bool:
    token = re.escape(_format_number(expected))
    return re.search(rf"\b{token}\b", markdown) is not None


def _cid_has_critical_violation(result: CitationCheckResult, cid: str) -> bool:
    for violation in result.violations:
        if violation.kind not in _CRITICAL_VIOLATION_KINDS:
            continue
        if cid in violation.sentence:
            return True
    return False


def score_numerical(
    fact_table: FactTable, markdown: str, result: CitationCheckResult
) -> NumericalScore:
    items: list[NumericalMatch] = []
    for fact in fact_table.facts:
        if fact.metric not in CRITICAL_METRICS:
            continue
        cid = fact.citation.cid
        tainted = _cid_has_critical_violation(result, cid)
        for metric_name, expected in _expected_figures(fact):
            appeared = _appeared(markdown, expected)
            matched = not tainted
            items.append(
                NumericalMatch(
                    metric=metric_name,
                    cid=cid,
                    expected=expected,
                    appeared=appeared,
                    matched=matched,
                )
            )

    matched_count = sum(1 for item in items if item.matched)
    rate = 1.0 if not items else matched_count / len(items)
    passed = all(item.matched for item in items)
    return NumericalScore(items=items, rate=rate, passed=passed)
