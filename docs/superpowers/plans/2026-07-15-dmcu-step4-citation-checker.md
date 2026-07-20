# DMCU Reporting — Step 4: Citation Checker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the deterministic citation checker: a pure function `check_citations(narrative: str, fact_table: FactTable) -> CitationCheckResult` that catches invented numbers and missing citations in narrative text before it's ever shown to a minister. `PLAN.md` §1: "Reports failing the check are flagged, never silently delivered."

**Architecture:** One file, `app/core/citation_check.py`, built in two tasks (extraction/matching helpers, then the sentence-level orchestrator that uses them) — same growing-file pattern Steps 2–3 used. This module has **no dependency on the LLM engine, templates, or any data module** — it takes narrative text and a `FactTable` and returns a verdict. The retry-once-then-`needs_review` orchestration logic described in `PLAN.md` §5.4 belongs to `core/engine.py`, a later step; this module only answers "does this text pass or fail," never retries or calls an LLM.

**Tech Stack:** Same as Steps 1–3 (Python 3.13, Pydantic v2). No new dependencies — pure stdlib `re` plus the `Fact`/`FactTable` contracts from Step 1.

## Global Constraints

- `check_citations` is a pure function: no I/O, no DB, no network, no hidden state (`PLAN.md` §7: "No LLM call anywhere except `core/llm.py`; everything else must be testable without a network").
- Per `PLAN.md` §5.4, the checker must: extract every numeric token (handling comma-formatted thousands like `"14,942"`, unit-suffixed numbers like `"2 hours"`, and percentages like `"66.7%"`); ignore citation markers (`[cid]`) and dates when extracting numbers; verify each extracted number equals a `Fact.value` or a value inside a `Fact.breakdown` dict **anywhere in the fact table** (not scoped to the sentence's own citation — this is a deliberate consequence of the literal spec, "each must equal a fact value or breakdown value in the table," and is a known, accepted limitation: the checker verifies numeric *traceability*, not that a number is semantically tied to the specific fact it's near); and verify every figure-bearing sentence contains a `[cid]` marker whose `cid` actually exists in the fact table (a bracketed marker with an unrecognized `cid` counts the same as no marker at all).
- **Date exclusion is implemented as: strip every ISO-format date-shaped substring (`YYYY-MM-DD`) from a sentence before extracting numeric tokens**, rather than cross-checking against `FactTable.params["date_from"]`/`["date_to"]` specifically. This is a deliberate simplification: date-shaped tokens are categorically exempt from citation checking (they describe report scope, not a fact), which is simpler and more robust than requiring exact-window matching, and still satisfies `PLAN.md`'s literal requirement ("ignore citation markers and dates matching the requested window").
- Citation markers (`[cid]`) are stripped from a sentence's text **before** numeric-token extraction, so a cid string containing digits (e.g. `[survey123-data_coverage-3]`) never leaks a spurious "3" into the number check — verified during planning with a dedicated test case.
- Percentage tokens (`"66.7%"`) are matched against fact/breakdown values with the `%` stripped (i.e. compare `66.7`, not `"66.7%"` as a string) — percentages in this codebase (e.g. `data_coverage`'s `pct_validated`/`pct_duplicates` from Step 3) are stored as plain floats, not pre-formatted strings.
- Float comparison uses a small epsilon (`1e-6`) rather than exact equality, to avoid floating-point representation edge cases — not because any current fact value is expected to need it (Step 3's `estimated_damage_total` and `data_coverage` percentages are already clean), but because the checker must not produce false positives from representation noise.
- `check_citations`'s two Pydantic result models (`CitationViolation`, `CitationCheckResult`) live directly in `app/core/citation_check.py`, not in `app/core/contracts.py` — this keeps the already-shipped, already-reviewed Step 1 contracts file untouched, and these two models are specific to this checker's output shape rather than a cross-cutting data contract other modules construct independently.
- Every scenario in this plan's tests was independently verified during planning by actually running a draft of this exact logic against constructed narrative/fact-table pairs (including a caught planning mistake — see Task 2's note on coincidental value matches) — trust the expected outcomes as given.
- Definition of done for this plan (`PLAN.md` §6 Step 4): pure function, heavily tested; test suite covers passing case, invented-number case, missing-citation case, formatted numbers, and percentages.

---

### Task 1: Extraction and matching helpers

**Files:**
- Create: `apps/backend/app/core/citation_check.py`
- Create: `apps/backend/tests/test_citation_check_helpers.py`

**Interfaces:**
- Consumes: `app.core.contracts.Fact`/`FactTable` (Step 1).
- Produces (all in `app.core.citation_check`): `CitationViolation` (Pydantic `BaseModel`: `kind: Literal["invented_number", "missing_citation"]`, `detail: str`, `sentence: str`, `token: str | None = None`), `CitationCheckResult` (`BaseModel`: `passed: bool`, `violations: list[CitationViolation]`), `ISO_DATE_RE: re.Pattern`, `SENTENCE_SPLIT_RE: re.Pattern`, `_collect_fact_numbers(fact_table: FactTable) -> set[float]`, `_valid_cids(fact_table: FactTable) -> set[str]`, `_parse_number_token(token: str) -> float`, `_strip_dates(text: str) -> str`, `_split_sentences(text: str) -> list[str]`, `_matches_any(value: float, candidates: set[float], epsilon: float = 1e-6) -> bool`. Task 2 imports and orchestrates all of these into `check_citations`.

- [ ] **Step 1: Write the failing tests**

Create `apps/backend/tests/test_citation_check_helpers.py`:

```python
from datetime import datetime

from app.core.contracts import Citation, Fact, FactTable
from app.core.citation_check import (
    _collect_fact_numbers,
    _matches_any,
    _parse_number_token,
    _split_sentences,
    _strip_dates,
    _valid_cids,
)


def make_citation(cid: str) -> Citation:
    return Citation(
        cid=cid,
        module="survey123",
        description="test citation",
        query_ref="test()",
        record_ids=["GUID-1"],
        as_of=datetime(2024, 7, 1),
    )


def make_fact_table() -> FactTable:
    return FactTable(
        request_id="req-1",
        template="minister_regional_comparison",
        params={"date_from": "2024-06-01", "date_to": "2024-06-30"},
        generated_at=datetime(2024, 7, 1),
        facts=[
            Fact(
                metric="incident_count",
                value=19,
                unit="incidents",
                scope={"corporation": "all"},
                breakdown={"flooding_": 7, "other": 2},
                verification="validated",
                citation=make_citation("survey123-incident_count-0"),
            ),
            Fact(
                metric="estimated_damage_total",
                value=98000.0,
                unit="TTD",
                scope={"corporation": "all"},
                breakdown={"records_reporting_cost": 5, "records_total": 19},
                verification="validated",
                citation=make_citation("survey123-estimated_damage_total-0"),
            ),
        ],
        gaps=[],
    )


def test_parse_number_token_plain_integer():
    assert _parse_number_token("42") == 42.0


def test_parse_number_token_comma_formatted():
    assert _parse_number_token("14,942") == 14942.0


def test_parse_number_token_percentage():
    assert _parse_number_token("66.7%") == 66.7


def test_parse_number_token_comma_and_decimal():
    assert _parse_number_token("98,000.50") == 98000.50


def test_strip_dates_removes_iso_date():
    assert _strip_dates("from 2024-06-01 to 2024-06-30") == "from  to "


def test_strip_dates_leaves_text_without_dates_unchanged():
    assert _strip_dates("no dates here") == "no dates here"


def test_split_sentences_basic():
    assert _split_sentences("A. B! C?") == ["A.", "B!", "C?"]


def test_split_sentences_empty_string():
    assert _split_sentences("") == []


def test_split_sentences_whitespace_only():
    assert _split_sentences("   ") == []


def test_split_sentences_decimal_does_not_cause_false_split():
    assert _split_sentences("Rate was 66.7% of total. Next sentence.") == [
        "Rate was 66.7% of total.",
        "Next sentence.",
    ]


def test_collect_fact_numbers_includes_value_and_breakdown():
    fact_table = make_fact_table()

    numbers = _collect_fact_numbers(fact_table)

    assert numbers == {19.0, 7.0, 2.0, 98000.0, 5.0}


def test_collect_fact_numbers_skips_string_values():
    fact_table = FactTable(
        request_id="req-1",
        template="t",
        params={},
        generated_at=datetime(2024, 7, 1),
        facts=[
            Fact(
                metric="m",
                value="some string value",
                unit=None,
                scope={},
                breakdown=None,
                verification="n/a",
                citation=make_citation("m-0"),
            )
        ],
        gaps=[],
    )

    assert _collect_fact_numbers(fact_table) == set()


def test_valid_cids_returns_all_citation_ids():
    fact_table = make_fact_table()

    assert _valid_cids(fact_table) == {
        "survey123-incident_count-0",
        "survey123-estimated_damage_total-0",
    }


def test_matches_any_exact_match():
    assert _matches_any(19.0, {19.0, 7.0}) is True


def test_matches_any_no_match():
    assert _matches_any(20.0, {19.0, 7.0}) is False


def test_matches_any_within_epsilon():
    assert _matches_any(66.70000005, {66.7}) is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd apps/backend
uv run pytest tests/test_citation_check_helpers.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.citation_check'`.

- [ ] **Step 3: Implement `app/core/citation_check.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd apps/backend
uv run pytest tests/test_citation_check_helpers.py -v
```

Expected: `16 passed`.

- [ ] **Step 5: Run the full suite**

```bash
cd apps/backend
uv run pytest -v
```

Expected: `125 passed`.

- [ ] **Step 6: Commit**

```bash
git add apps/backend/app/core/citation_check.py apps/backend/tests/test_citation_check_helpers.py
git commit -m "backend: add citation checker extraction and matching helpers"
```

---

### Task 2: `check_citations` orchestrator

**Files:**
- Modify: `apps/backend/app/core/citation_check.py` (append)
- Create: `apps/backend/tests/test_citation_check.py`

**Interfaces:**
- Consumes: `CitationViolation`, `CitationCheckResult`, `_collect_fact_numbers`, `_valid_cids`, `_parse_number_token`, `_strip_dates`, `_split_sentences`, `_matches_any`, `ISO_DATE_RE`, `SENTENCE_SPLIT_RE` (Task 1).
- Produces: `check_citations(narrative: str, fact_table: FactTable) -> CitationCheckResult` — the module's public entry point. A later step (`core/engine.py`, not yet built) will call this after LLM narration and implement the retry-once-then-`needs_review` policy `PLAN.md` §5.4 describes; that retry/status logic is explicitly out of scope for this function, which only reports pass/fail plus violations.
- **Planning note on a caught mistake:** while verifying this logic against constructed scenarios during planning, a test case using `"Officers responded within 2 hours"` against a fact table whose `incident_count` breakdown happened to include `{"other": 2}` was initially expected to fail (2 isn't a "real" fact about hours) but the checker correctly reported it as passing — `2` legitimately equals a real breakdown value in the table, even though the semantic association is coincidental. This is not a bug: it's the direct, accepted consequence of `PLAN.md`'s literal spec ("each must equal a fact value or breakdown value in the table" — value equality, not semantic linkage to a specific cited fact). The test suite below uses numbers verified to be genuinely absent from the fact table, not this coincidental-match trap.

- [ ] **Step 1: Write the failing tests**

Create `apps/backend/tests/test_citation_check.py`:

```python
from datetime import datetime

from app.core.contracts import Citation, Fact, FactTable
from app.core.citation_check import check_citations


def make_citation(cid: str) -> Citation:
    return Citation(
        cid=cid,
        module="survey123",
        description="test citation",
        query_ref="test()",
        record_ids=["GUID-1"],
        as_of=datetime(2024, 7, 1),
    )


def make_fact_table(facts=None) -> FactTable:
    if facts is None:
        facts = [
            Fact(
                metric="incident_count",
                value=19,
                unit="incidents",
                scope={"corporation": "all"},
                breakdown={"flooding_": 7, "other": 2},
                verification="validated",
                citation=make_citation("survey123-incident_count-0"),
            ),
            Fact(
                metric="estimated_damage_total",
                value=98000.0,
                unit="TTD",
                scope={"corporation": "all"},
                breakdown={"records_reporting_cost": 5, "records_total": 19},
                verification="validated",
                citation=make_citation("survey123-estimated_damage_total-0"),
            ),
            Fact(
                metric="data_coverage",
                value=15,
                unit="records",
                scope={"corporation": "sangre_grande_regional_corporat"},
                breakdown={"pct_validated": 66.7, "pct_duplicates": 13.3},
                verification="n/a",
                citation=make_citation("survey123-data_coverage-2"),
            ),
        ]
    return FactTable(
        request_id="req-1",
        template="minister_regional_comparison",
        params={"date_from": "2024-06-01", "date_to": "2024-06-30"},
        generated_at=datetime(2024, 7, 1),
        facts=facts,
        gaps=[],
    )


def test_passing_narrative_with_cited_matching_numbers():
    fact_table = make_fact_table()
    narrative = (
        "There were 19 incidents recorded [survey123-incident_count-0]. "
        "Estimated damage totaled $98,000 [survey123-estimated_damage_total-0]."
    )

    result = check_citations(narrative, fact_table)

    assert result.passed is True
    assert result.violations == []


def test_invented_number_is_flagged():
    fact_table = make_fact_table()
    narrative = "There were 20 incidents recorded [survey123-incident_count-0]."

    result = check_citations(narrative, fact_table)

    assert result.passed is False
    assert len(result.violations) == 1
    assert result.violations[0].kind == "invented_number"
    assert result.violations[0].token == "20"


def test_missing_citation_is_flagged():
    fact_table = make_fact_table()
    narrative = "There were 19 incidents recorded."

    result = check_citations(narrative, fact_table)

    assert result.passed is False
    assert len(result.violations) == 1
    assert result.violations[0].kind == "missing_citation"


def test_comma_formatted_number_matches():
    fact_table = make_fact_table()
    narrative = "Estimated damage totaled $98,000 [survey123-estimated_damage_total-0]."

    result = check_citations(narrative, fact_table)

    assert result.passed is True


def test_percentage_matches_breakdown_value():
    fact_table = make_fact_table()
    narrative = "66.7% of records in Sangre Grande were validated [survey123-data_coverage-2]."

    result = check_citations(narrative, fact_table)

    assert result.passed is True


def test_iso_dates_are_ignored_without_citation():
    fact_table = make_fact_table()
    narrative = "This report covers the period from 2024-06-01 to 2024-06-30."

    result = check_citations(narrative, fact_table)

    assert result.passed is True
    assert result.violations == []


def test_cid_embedded_digit_does_not_leak_as_invented_number():
    fact_table = make_fact_table()
    narrative = "15 records were reviewed for this corporation [survey123-data_coverage-2]."

    result = check_citations(narrative, fact_table)

    assert result.passed is True


def test_unrecognized_citation_marker_counts_as_missing():
    fact_table = make_fact_table()
    narrative = "There were 19 incidents recorded [fake-cid-99]."

    result = check_citations(narrative, fact_table)

    assert result.passed is False
    assert result.violations[0].kind == "missing_citation"


def test_number_genuinely_absent_from_fact_table_is_invented():
    fact_table = make_fact_table()
    narrative = "Officers responded within 9 hours [survey123-incident_count-0]."

    result = check_citations(narrative, fact_table)

    assert result.passed is False
    assert result.violations[0].kind == "invented_number"
    assert result.violations[0].token == "9"


def test_breakdown_value_from_a_different_fact_in_the_table_matches():
    fact_table = make_fact_table()
    narrative = "Of these, 7 were flooding incidents [survey123-incident_count-0]."

    result = check_citations(narrative, fact_table)

    assert result.passed is True


def test_multi_sentence_narrative_flags_only_the_problem_sentence():
    fact_table = make_fact_table()
    narrative = (
        "There were 19 incidents recorded [survey123-incident_count-0]. "
        "Officers responded within 9 hours. "
        "Estimated damage totaled $98,000 [survey123-estimated_damage_total-0]."
    )

    result = check_citations(narrative, fact_table)

    assert result.passed is False
    kinds = {v.kind for v in result.violations}
    assert kinds == {"missing_citation", "invented_number"}
    for violation in result.violations:
        assert violation.sentence == "Officers responded within 9 hours."


def test_two_numbers_one_sentence_mixed_validity():
    fact_table = make_fact_table()
    narrative = "There were 19 incidents and 42 fires recorded [survey123-incident_count-0]."

    result = check_citations(narrative, fact_table)

    assert result.passed is False
    assert len(result.violations) == 1
    assert result.violations[0].kind == "invented_number"
    assert result.violations[0].token == "42"


def test_empty_narrative_passes_trivially():
    fact_table = make_fact_table()

    result = check_citations("", fact_table)

    assert result.passed is True
    assert result.violations == []


def test_prose_without_numbers_needs_no_citation():
    fact_table = make_fact_table()

    result = check_citations("No incidents were recorded this period.", fact_table)

    assert result.passed is True
    assert result.violations == []


def test_empty_fact_table_flags_any_stated_number():
    empty_fact_table = make_fact_table(facts=[])

    result = check_citations("There were 19 incidents.", empty_fact_table)

    assert result.passed is False
    kinds = {v.kind for v in result.violations}
    assert kinds == {"missing_citation", "invented_number"}
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd apps/backend
uv run pytest tests/test_citation_check.py -v
```

Expected: FAIL — `ImportError: cannot import name 'check_citations' from 'app.core.citation_check'`.

- [ ] **Step 3: Append to `app/core/citation_check.py`**

No new imports are needed — `FactTable` is already imported by Task 1, and `check_citations`'s body only needs `re` (also already imported).

Append at the end of the file:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd apps/backend
uv run pytest tests/test_citation_check.py -v
```

Expected: `15 passed`.

- [ ] **Step 5: Run the full suite**

```bash
cd apps/backend
uv run pytest -v
```

Expected: `140 passed`.

- [ ] **Step 6: Commit**

```bash
git add apps/backend/app/core/citation_check.py apps/backend/tests/test_citation_check.py
git commit -m "backend: add check_citations orchestrator"
```

---

## Definition of Done (matches `PLAN.md` §6 Step 4)

- [ ] `cd apps/backend && uv run pytest -v` — all 140 tests pass, 0 failures.
- [ ] Pure function, heavily tested (31 tests total across both task files for a single module).
- [ ] Test suite covers: passing case (`test_passing_narrative_with_cited_matching_numbers`), invented-number case (`test_invented_number_is_flagged`, `test_number_genuinely_absent_from_fact_table_is_invented`, `test_two_numbers_one_sentence_mixed_validity`), missing-citation case (`test_missing_citation_is_flagged`, `test_unrecognized_citation_marker_counts_as_missing`), formatted numbers (`test_comma_formatted_number_matches`, `test_parse_number_token_comma_formatted`), percentages (`test_percentage_matches_breakdown_value`, `test_parse_number_token_percentage`).
