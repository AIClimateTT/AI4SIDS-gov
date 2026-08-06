import re
from typing import Literal

from pydantic import BaseModel

from app.core.contracts import FactTable

ISO_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
# A newline ends a unit of text as surely as a full stop does. Splitting only
# on .!? made a markdown list or table one enormous "sentence", so a single
# citation at the end of the block laundered every figure above it:
#   "- Incidents recorded: 12\n- Deaths: 7 [C002]"
# passed with 12 attributed to a fact that never contained it. List items and
# table rows must be checked individually.
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")

_MONTH = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?"
    r"|Aug(?:ust)?|Sep(?:t|tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
)
_DAY = r"\d{1,2}(?:st|nd|rd|th)?"
# An ordinal suffix makes a day unambiguous on its own, which matters for a
# range like "June 1st - June 30th, 2023" where only the last part carries the
# year. A BARE "June 15" still is not stripped: that could be "In June 15 homes
# were affected", and swallowing the 15 would hide a real figure.
_ORDINAL_DAY = r"\d{1,2}(?:st|nd|rd|th)"
# Bounded to plausible years. An unbounded \d{4} swallowed any 4-digit figure
# following a month name — "In May 2500 households were affected" was erased
# before the number scan, so both the invented-number and missing-citation
# checks were skipped and an uncited invented figure shipped as "ok".
_YEAR = r"(?:19|20)\d{2}"

# Prose dates carry digits that are not figures. Every alternative REQUIRES a
# 4-digit year: a bare "June 15" is deliberately left alone, because stripping
# it would swallow the 15 in "In June 15 homes were affected".
PROSE_DATE_RE = re.compile(
    rf"\b(?:{_DAY}\s+{_MONTH},?\s+{_YEAR}"
    rf"|{_MONTH}\s+{_DAY},?\s+{_YEAR}"
    rf"|{_MONTH}\s+{_ORDINAL_DAY}"
    rf"|{_MONTH}\s+{_YEAR})\b",
    re.IGNORECASE,
)


class CitationViolation(BaseModel):
    kind: Literal[
        "invented_number", "misattributed_number", "missing_citation", "empty_narrative"
    ]
    detail: str
    sentence: str
    token: str | None = None


class CitationCheckResult(BaseModel):
    passed: bool
    violations: list[CitationViolation]


def _fact_numbers(fact) -> set[float]:
    """Every figure one fact licenses: its value and its breakdown values.

    The breakdown is included because a fact's own decomposition is part of
    what it says — "of these, 7 were flooding incidents [C001]" is a correct
    statement about C001, not a borrowed figure.
    """
    numbers: set[float] = set()
    if isinstance(fact.value, (int, float)):
        numbers.add(float(fact.value))
    if fact.breakdown:
        for value in fact.breakdown.values():
            numbers.add(float(value))
    return numbers


def _collect_fact_numbers_by_cid(fact_table: FactTable) -> dict[str, set[float]]:
    """Numbers grouped by the citation that licenses them.

    The whole point of the checker is that a figure traces to its source. A
    flat union across all facts could only ever answer "does this number exist
    somewhere in the table", which is a different and much weaker question: an
    unverified Survey123 field count published under a corporation's signed-off
    SITREP citation passed it cleanly.
    """
    by_cid: dict[str, set[float]] = {}
    for fact in fact_table.facts:
        by_cid.setdefault(fact.citation.cid, set()).update(_fact_numbers(fact))
    return by_cid


def _collect_fact_numbers(fact_table: FactTable) -> set[float]:
    numbers: set[float] = set()
    for fact in fact_table.facts:
        numbers.update(_fact_numbers(fact))
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


# One bracket may carry several cids — "[C008, C009, C010]" is how a model
# naturally cites a figure drawn from more than one fact. Matching only a single
# cid read the whole bracket as unparseable, so a correctly-cited sentence was
# reported as citing nothing.
CITATION_MARKER_RE = re.compile(r"\[([A-Za-z0-9_,\s-]+)\]")


def _cids_in(text: str) -> set[str]:
    return {
        cid.strip()
        for group in CITATION_MARKER_RE.findall(text)
        for cid in group.split(",")
        if cid.strip()
    }
# \b so a digit run glued to a word is not a figure: "Survey123" must not
# yield "123", and a bare "C001" marker must not yield "001". Real figures
# ("15", "115,800", "66.7%") always follow a boundary.
NUMBER_TOKEN_RE = re.compile(r"\b\d[\d,]*(?:\.\d+)?%?")


def check_citations(narrative: str, fact_table: FactTable) -> CitationCheckResult:
    numbers_by_cid = _collect_fact_numbers_by_cid(fact_table)
    fact_numbers = _collect_fact_numbers(fact_table)
    valid_cids = _valid_cids(fact_table)
    violations: list[CitationViolation] = []
    cited_any = False

    for sentence in _split_sentences(narrative):
        cited_ids = _cids_in(sentence)
        cited_valid_ids = cited_ids & valid_cids
        has_valid_citation = bool(cited_valid_ids)
        # Only the facts this sentence actually cites license its figures.
        licensed_numbers: set[float] = set()
        for cid in cited_valid_ids:
            licensed_numbers.update(numbers_by_cid.get(cid, set()))
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
            elif has_valid_citation and not _matches_any(value, licensed_numbers):
                # The number exists in the table but belongs to a different
                # fact than the one cited. Reported separately from
                # invented_number because the failure is different in kind and
                # worse in effect: the figure is real, so nothing about the
                # sentence looks wrong, while its stated provenance —
                # verification status, module, source authority — is another
                # fact's. A sentence with no valid citation at all is left to
                # missing_citation rather than double-reported here.
                cited = ", ".join(sorted(cited_valid_ids))
                violations.append(
                    CitationViolation(
                        kind="misattributed_number",
                        detail=(
                            f"Number {token!r} does not appear in the fact(s) cited here "
                            f"({cited}); it belongs to a different fact"
                        ),
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
