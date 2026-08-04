import re
from typing import Literal

from pydantic import BaseModel

from app.core.contracts import FactTable

ISO_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")

_MONTH = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?"
    r"|Aug(?:ust)?|Sep(?:t|tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
)
_DAY = r"\d{1,2}(?:st|nd|rd|th)?"
_YEAR = r"\d{4}"

# Prose dates carry digits that are not figures. Every alternative REQUIRES a
# 4-digit year: a bare "June 15" is deliberately left alone, because stripping
# it would swallow the 15 in "In June 15 homes were affected".
PROSE_DATE_RE = re.compile(
    rf"\b(?:{_DAY}\s+{_MONTH},?\s+{_YEAR}"
    rf"|{_MONTH}\s+{_DAY},?\s+{_YEAR}"
    rf"|{_MONTH}\s+{_YEAR})\b",
    re.IGNORECASE,
)


class CitationViolation(BaseModel):
    kind: Literal["invented_number", "missing_citation", "empty_narrative"]
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
    # Longest form first: prose dates before ISO, so "June 1, 2023" is removed
    # whole rather than leaving an orphaned "1".
    return ISO_DATE_RE.sub("", PROSE_DATE_RE.sub("", text))


def _split_sentences(text: str) -> list[str]:
    stripped = text.strip()
    if not stripped:
        return []
    return [s.strip() for s in SENTENCE_SPLIT_RE.split(stripped) if s.strip()]


def _matches_any(value: float, candidates: set[float], epsilon: float = 1e-6) -> bool:
    return any(abs(value - c) < epsilon for c in candidates)


CITATION_MARKER_RE = re.compile(r"\[([A-Za-z0-9_-]+)\]")
# \b so a digit run glued to a word is not a figure: "Survey123" must not
# yield "123", and a bare "C001" marker must not yield "001". Real figures
# ("15", "115,800", "66.7%") always follow a boundary.
NUMBER_TOKEN_RE = re.compile(r"\b\d[\d,]*(?:\.\d+)?%?")


def check_citations(narrative: str, fact_table: FactTable) -> CitationCheckResult:
    fact_numbers = _collect_fact_numbers(fact_table)
    valid_cids = _valid_cids(fact_table)
    violations: list[CitationViolation] = []
    cited_any = False

    for sentence in _split_sentences(narrative):
        cited_ids = set(CITATION_MARKER_RE.findall(sentence))
        has_valid_citation = bool(cited_ids & valid_cids)
        # Recorded before the no-tokens `continue` below, so a sentence that
        # cites a fact but states no figure still counts as having reported.
        if has_valid_citation:
            cited_any = True

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

    if fact_table.facts and not cited_any:
        # No citation anywhere while facts exist means the model produced no
        # report. Without this, an empty narrative has no numbers, therefore no
        # violations, therefore status "ok" — a clean-looking report with no
        # prose, which invites no second look.
        violations.append(
            CitationViolation(
                kind="empty_narrative",
                detail="Narrative cites no facts; the model produced no report",
                sentence=narrative.strip()[:200],
                token=None,
            )
        )

    return CitationCheckResult(passed=not violations, violations=violations)
