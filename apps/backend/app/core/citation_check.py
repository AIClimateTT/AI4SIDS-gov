import re
from typing import Literal

from pydantic import BaseModel

from app.core.contracts import FactTable

ISO_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


class CitationViolation(BaseModel):
    kind: Literal["invented_number", "missing_citation"]
    detail: str
    sentence: str
    token: str | None = None


class CitationCheckResult(BaseModel):
    passed: bool
    violations: list[CitationViolation]


def _collect_fact_numbers(fact_table: FactTable) -> set[float]:
    numbers: set[float] = set()
    for fact in fact_table.facts:
        if isinstance(fact.value, (int, float)):
            numbers.add(float(fact.value))
        if fact.breakdown:
            for value in fact.breakdown.values():
                numbers.add(float(value))
    return numbers


def _valid_cids(fact_table: FactTable) -> set[str]:
    return {fact.citation.cid for fact in fact_table.facts}


def _parse_number_token(token: str) -> float:
    cleaned = token.rstrip("%").replace(",", "")
    return float(cleaned)


def _strip_dates(text: str) -> str:
    return ISO_DATE_RE.sub("", text)


def _split_sentences(text: str) -> list[str]:
    stripped = text.strip()
    if not stripped:
        return []
    return [s.strip() for s in SENTENCE_SPLIT_RE.split(stripped) if s.strip()]


def _matches_any(value: float, candidates: set[float], epsilon: float = 1e-6) -> bool:
    return any(abs(value - c) < epsilon for c in candidates)


CITATION_MARKER_RE = re.compile(r"\[([A-Za-z0-9_-]+)\]")
NUMBER_TOKEN_RE = re.compile(r"\d[\d,]*(?:\.\d+)?%?")


def check_citations(narrative: str, fact_table: FactTable) -> CitationCheckResult:
    fact_numbers = _collect_fact_numbers(fact_table)
    valid_cids = _valid_cids(fact_table)
    violations: list[CitationViolation] = []

    for sentence in _split_sentences(narrative):
        cited_ids = set(CITATION_MARKER_RE.findall(sentence))
        has_valid_citation = bool(cited_ids & valid_cids)

        text_for_numbers = CITATION_MARKER_RE.sub("", sentence)
        text_for_numbers = _strip_dates(text_for_numbers)
        tokens = NUMBER_TOKEN_RE.findall(text_for_numbers)

        if not tokens:
            continue

        if not has_valid_citation:
            violations.append(
                CitationViolation(
                    kind="missing_citation",
                    detail="Sentence contains a figure but no valid [cid] citation marker",
                    sentence=sentence,
                    token=None,
                )
            )

        for token in tokens:
            value = _parse_number_token(token)
            if not _matches_any(value, fact_numbers):
                violations.append(
                    CitationViolation(
                        kind="invented_number",
                        detail=f"Number {token!r} does not match any fact or breakdown value",
                        sentence=sentence,
                        token=token,
                    )
                )

    return CitationCheckResult(passed=not violations, violations=violations)
