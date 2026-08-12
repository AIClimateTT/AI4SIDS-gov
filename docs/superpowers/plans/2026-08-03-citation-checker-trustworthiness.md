# Citation Checker Trustworthiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `needs_review` mean something — stop the checker flagging dates and identifiers as invented figures, and stop an empty narrative passing as `ok`.

**Architecture:** Three surgical changes. `citation_check.py` gains a word-boundary number pattern and prose-date stripping so it stops firing on non-figures, plus a new violation for a narrative that cites nothing. `llm.py`/`config.py` set Ollama's `num_ctx` explicitly, fixing the silent 2048-token truncation that produced the empty narrative in the first place. One line joins the shared prompt rules.

**Tech Stack:** Python 3.13, Pydantic v2, `langchain-ollama`, pytest. Frontend touch is React/TypeScript (one guard).

**Spec:** `docs/superpowers/specs/2026-08-03-citation-checker-trustworthiness-design.md`

## Global Constraints

- **The fix must not disable the check.** Every task that loosens the checker must keep a test proving a genuinely invented number in a cited sentence is still flagged. A plan that only removes false positives has removed the guarantee.
- **A bare 4-digit year with no adjacent month is still checked.** `2023` alone is indistinguishable from a figure; only date-shaped phrases are stripped.
- **Violation `sentence` fields carry the original text**, not the date-stripped copy. Stripping happens on a throwaway string used solely for number extraction, so a reviewer sees what was actually written.
- **Backend tests:** `cd apps/backend && .venv/bin/python -m pytest`. Baseline is **294 passed, 2 failed** — the 2 failures are in `tests/test_llm.py`, pre-existing, caused by leftover Cursor debug instrumentation, and **out of scope**. Do not fix them; do not count them as regressions. Any OTHER failure is yours.
- **Frontend:** `cd apps/frontend && pnpm test` (19 tests) and `pnpm exec tsc --noEmit -p tsconfig.json`.
- **Demo database for end-to-end verification:** `apps/backend/demo.db`, driven with `DATABASE_URL="sqlite:///./demo.db"`. Never point verification at `dev.db` — the API tests delete it.

---

## File Structure

**Modify:**
- `apps/backend/app/core/citation_check.py` — the number pattern, prose-date stripping, the new violation kind. This file is ~100 lines and stays the single home of the checking rules.
- `apps/backend/app/config.py` — one setting.
- `apps/backend/app/core/llm.py` — pass the setting to `ChatOllama`.
- `apps/backend/app/core/engine.py` — one line in `CITATION_RULES`.
- `apps/frontend/src/components/reports/citation-utils.ts` — one guard.

**Test:**
- `apps/backend/tests/test_citation_check.py` and `test_citation_check_helpers.py` — existing files, extended.
- `apps/backend/tests/test_llm.py` — extended (without touching the 2 failing tests).

---

## Task 1: Checker precision

**Files:**
- Modify: `apps/backend/app/core/citation_check.py`
- Test: `apps/backend/tests/test_citation_check.py`

**Interfaces:**
- Consumes: `FactTable`, `Fact`, `Citation` from `app.core.contracts`.
- Produces: `PROSE_DATE_RE`; a `NUMBER_TOKEN_RE` anchored at a word boundary; `_strip_dates` now removing prose dates as well as ISO. `check_citations`'s signature is unchanged.

- [ ] **Step 1: Write the failing tests**

Append to `apps/backend/tests/test_citation_check.py`. **Use the file's existing `make_fact_table()` helper — do not add another.** Its default table holds the values `19`, `98000.0`, `15` and breakdown values `7`, `2`, `5`, `19`, `66.7`, `13.3`, and its first fact's cid is `survey123-incident_count-0`. Every number used below is chosen against that set: `15` matches a real fact, `99` and `2023` deliberately do not.

Add this constant beside the helpers, then the tests:

```python
CID = "survey123-incident_count-0"


def test_module_name_containing_digits_is_not_a_figure():
    # "Survey123" yielded "123" five times in a real ministerial report.
    result = check_citations(
        f"Survey123 field observations corroborate the total [{CID}].", make_fact_table()
    )

    assert result.violations == []


def test_dotted_module_reference_is_not_a_figure():
    result = check_citations(
        f"No data returned for survey123.data_coverage [{CID}].", make_fact_table()
    )

    assert [v for v in result.violations if v.kind == "invented_number"] == []


def test_prose_date_with_day_month_year_is_not_a_figure():
    result = check_citations(
        f"This report covers June 1, 2023, to December 31, 2024 [{CID}].", make_fact_table()
    )

    assert result.violations == []


def test_prose_date_with_an_ordinal_day_is_not_a_figure():
    result = check_citations(
        f"As of August 3rd, 2026, 15 incidents were recorded [{CID}].", make_fact_table()
    )

    assert result.violations == []


def test_day_first_prose_date_is_not_a_figure():
    result = check_citations(
        f"Filed 31 December 2024 by the corporation [{CID}].", make_fact_table()
    )

    assert result.violations == []


def test_month_and_year_alone_is_not_a_figure():
    result = check_citations(
        f"Situation Report - Diego Martin Regional Corporation - June 2023 [{CID}].",
        make_fact_table(),
    )

    assert result.violations == []


def test_iso_date_is_still_not_a_figure():
    result = check_citations(
        f"Window 2023-06-01 to 2023-06-30 covered 15 incidents [{CID}].", make_fact_table()
    )

    assert result.violations == []


def test_an_invented_number_in_a_cited_sentence_is_still_flagged():
    # The test that proves the precision fix did not simply disable the check.
    result = check_citations(
        f"A total of 99 incidents were recorded [{CID}].", make_fact_table()
    )

    assert [v.token for v in result.violations if v.kind == "invented_number"] == ["99"]


def test_a_bare_year_with_no_month_is_still_checked():
    # 2023 alone is indistinguishable from a figure, so it must not be excused.
    result = check_citations(
        f"The corporation recorded 2023 affected households [{CID}].", make_fact_table()
    )

    assert [v.token for v in result.violations if v.kind == "invented_number"] == ["2023"]


def test_a_figure_without_a_citation_is_still_flagged():
    result = check_citations("A total of 15 incidents were recorded.", make_fact_table())

    assert [v.kind for v in result.violations] == ["missing_citation"]


def test_violation_sentence_keeps_the_original_text():
    # Date stripping happens on a throwaway copy; a reviewer must see what was written.
    result = check_citations(
        f"On June 1, 2023 there were 99 incidents [{CID}].", make_fact_table()
    )

    assert "June 1, 2023" in result.violations[0].sentence
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/backend && .venv/bin/python -m pytest tests/test_citation_check.py -v -k "module_name or dotted or prose_date or ordinal or day_first or month_and_year"`
Expected: FAIL — these currently produce `invented_number` violations for `123`, `1`, `2023`, `31`, `2024`, `3`, `2026`.

- [ ] **Step 3: Anchor the number pattern at a word boundary**

In `apps/backend/app/core/citation_check.py`, change:

```python
NUMBER_TOKEN_RE = re.compile(r"\d[\d,]*(?:\.\d+)?%?")
```

to:

```python
# \b so a digit run glued to a word is not a figure: "Survey123" must not
# yield "123", and a bare "C001" marker must not yield "001". Real figures
# ("15", "115,800", "66.7%") always follow a boundary.
NUMBER_TOKEN_RE = re.compile(r"\b\d[\d,]*(?:\.\d+)?%?")
```

- [ ] **Step 4: Add prose-date stripping**

Add beside `ISO_DATE_RE`:

```python
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
```

Then extend the stripper:

```python
def _strip_dates(text: str) -> str:
    # Longest form first: prose dates before ISO, so "June 1, 2023" is removed
    # whole rather than leaving an orphaned "1".
    return ISO_DATE_RE.sub("", PROSE_DATE_RE.sub("", text))
```

- [ ] **Step 5: Run the new tests**

Run: `cd apps/backend && .venv/bin/python -m pytest tests/test_citation_check.py -v`
Expected: PASS, including the three "still flagged" tests.

- [ ] **Step 6: Run the whole suite**

Run: `cd apps/backend && .venv/bin/python -m pytest -q`
Expected: 2 failed (the pre-existing `tests/test_llm.py` pair), everything else passing.

- [ ] **Step 7: Commit**

```bash
cd apps/backend
git add app/core/citation_check.py tests/test_citation_check.py
git commit -m "citations: stop flagging prose dates and digits inside identifiers"
```

---

## Task 2: Empty-narrative violation

**Files:**
- Modify: `apps/backend/app/core/citation_check.py`
- Modify: `apps/frontend/src/components/reports/citation-utils.ts`
- Test: `apps/backend/tests/test_citation_check.py`

**Interfaces:**
- Consumes: Task 1's `check_citations`.
- Produces: `CitationViolation.kind` gains the literal `"empty_narrative"`.

- [ ] **Step 1: Write the failing tests**

Append to `apps/backend/tests/test_citation_check.py`, reusing the file's existing `make_fact_table()` helper and the `CID` constant added in Task 1:

```python
def test_a_narrative_that_cites_nothing_is_a_violation():
    # A real ministerial report returned exactly this and was saved status "ok".
    result = check_citations("**", make_fact_table())

    assert result.passed is False
    assert [v.kind for v in result.violations] == ["empty_narrative"]


def test_an_empty_narrative_is_a_violation():
    result = check_citations("", make_fact_table())

    assert [v.kind for v in result.violations] == ["empty_narrative"]


def test_prose_that_cites_nothing_is_a_violation():
    # "Cited nothing" rather than "wrote nothing": prose naming no fact is
    # equally a failure to report.
    result = check_citations("The situation remains under review.", make_fact_table())

    assert [v.kind for v in result.violations] == ["empty_narrative"]


def test_a_narrative_citing_a_fact_is_not_empty():
    result = check_citations(f"There were 15 incidents [{CID}].", make_fact_table())

    assert result.passed is True


def test_an_empty_narrative_with_no_facts_is_not_a_violation():
    # Nothing was requested, so nothing going unreported is correct.
    empty = make_fact_table()
    empty.facts.clear()

    result = check_citations("", empty)

    assert result.violations == []


def test_empty_narrative_violation_carries_a_readable_excerpt():
    result = check_citations("x" * 500, make_fact_table())

    assert len(result.violations[0].sentence) == 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/backend && .venv/bin/python -m pytest tests/test_citation_check.py -v -k "cites_nothing or empty_narrative"`
Expected: FAIL — `check_citations("**", ...)` currently returns `passed=True` with no violations.

- [ ] **Step 3: Add the violation kind**

In `apps/backend/app/core/citation_check.py`, widen the literal:

```python
class CitationViolation(BaseModel):
    kind: Literal["invented_number", "missing_citation", "empty_narrative"]
```

- [ ] **Step 4: Detect it in `check_citations`**

Track whether any sentence carried a valid citation, and append the violation after the loop. Inside the existing `for sentence in _split_sentences(narrative):` loop, immediately after `has_valid_citation` is computed, record it:

```python
        if has_valid_citation:
            cited_any = True
```

Initialise `cited_any = False` beside `violations: list[CitationViolation] = []`, and add this immediately before the `return`:

```python
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
```

Note the existing `if not tokens: continue` sits between these two edits — `cited_any` must be set *before* that `continue`, or a sentence that cites a fact but contains no digits would not count.

- [ ] **Step 5: Run the new tests and the whole suite**

Run: `cd apps/backend && .venv/bin/python -m pytest tests/test_citation_check.py -v && .venv/bin/python -m pytest -q`
Expected: all citation tests pass; suite shows 2 failed (pre-existing `tests/test_llm.py`), everything else passing.

- [ ] **Step 6: Guard the frontend highlighter**

`markViolationSentences` in `apps/frontend/src/components/reports/citation-utils.ts` wraps each violation's `sentence` in `<mark>`. An `empty_narrative` violation's sentence is an excerpt of the *whole* narrative, so it would mark the entire report body. Filter it out:

```ts
  const sentences = violations
    // empty_narrative's sentence is an excerpt of the whole narrative, not a
    // flagged span — marking it would highlight the entire report.
    .filter((v) => v.kind !== 'empty_narrative')
    .map((v) => v.sentence?.trim())
    .filter((s): s is string => !!s && s.length > 0)
    .sort((a, b) => b.length - a.length)
```

`ViolationsPanel` needs no change: it renders `kind` and `detail` generically, and `CitationViolation.kind` is typed `string` in `src/types/dmcu.ts`, so the new kind displays as-is.

- [ ] **Step 7: Verify the frontend**

Run: `cd apps/frontend && pnpm exec tsc --noEmit -p tsconfig.json && pnpm test`
Expected: `tsc` silent; 19 tests pass.

- [ ] **Step 8: Commit**

```bash
cd /Users/devonmurray/just-projects/AI4SIDS-repos/gov
git add apps/backend/app/core/citation_check.py apps/backend/tests/test_citation_check.py apps/frontend/src/components/reports/citation-utils.ts
git commit -m "citations: flag a narrative that cites nothing instead of passing it"
```

---

## Task 3: Ollama context and the digits prompt rule

**Files:**
- Modify: `apps/backend/app/config.py`
- Modify: `apps/backend/app/core/llm.py`
- Modify: `apps/backend/app/core/engine.py`
- Test: `apps/backend/tests/test_llm.py`, `apps/backend/tests/test_engine_assembly.py`

**Interfaces:**
- Consumes: `settings` from `app.config`.
- Produces: `Settings.ollama_num_ctx: int = 8192`; `OllamaLLMClient.__init__` passes `num_ctx` to `ChatOllama`.

- [ ] **Step 1: Write the failing tests**

Append to `apps/backend/tests/test_llm.py`. **Do not modify the two existing failing tests in that file** — they are out of scope.

```python
def test_ollama_client_sets_an_explicit_context_window():
    # Ollama defaults num_ctx to 2048. A fact table of ~2,049 tokens silently
    # produced an empty narrative, which the checker then passed as "ok".
    from app.config import settings
    from app.core.llm import OllamaLLMClient

    client = OllamaLLMClient(base_url="http://localhost:11434", model="gemma3:4b")

    assert client._chat.num_ctx == settings.ollama_num_ctx


def test_default_context_window_is_large_enough_for_a_real_fact_table():
    from app.config import Settings

    assert Settings().ollama_num_ctx >= 8192
```

Append to `apps/backend/tests/test_engine_assembly.py`:

```python
def test_citation_rules_require_digits_not_words():
    # A ministerial report wrote "Fifteen incidents ... Thirteen homes", none of
    # which the digit-scanning checker ever examined.
    from app.core.engine import CITATION_RULES

    assert "digits" in CITATION_RULES.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/backend && .venv/bin/python -m pytest tests/test_llm.py::test_ollama_client_sets_an_explicit_context_window tests/test_engine_assembly.py::test_citation_rules_require_digits_not_words -v`
Expected: FAIL — `Settings` has no `ollama_num_ctx`, and `CITATION_RULES` says nothing about digits.

- [ ] **Step 3: Add the setting**

In `apps/backend/app/config.py`, add to `Settings` beside `ollama_model`:

```python
    ollama_num_ctx: int = 8192
```

- [ ] **Step 4: Pass it to ChatOllama**

In `apps/backend/app/core/llm.py`, `OllamaLLMClient.__init__` currently builds `ChatOllama(base_url=base_url, model=model)`. Change that call to:

```python
        self._chat = chat or ChatOllama(
            base_url=base_url, model=model, num_ctx=settings.ollama_num_ctx
        )
```

`settings` is already imported in this module. The injected `chat` parameter is untouched, so tests passing a fake client are unaffected.

- [ ] **Step 5: Add the prompt rule**

In `apps/backend/app/core/engine.py`, add a final bullet to `CITATION_RULES`:

```
- Write every figure as digits, never words — "15", not "fifteen".
```

It must sit inside the existing triple-quoted string so it is prepended to every template's prompt by `compose_system_prompt`.

- [ ] **Step 6: Run the new tests and the whole suite**

Run: `cd apps/backend && .venv/bin/python -m pytest -q`
Expected: 2 failed (the same pre-existing `tests/test_llm.py` pair), everything else passing. If a *third* `test_llm.py` test now fails, your `num_ctx` change broke it — those two stub `settings` with an object lacking real fields.

- [ ] **Step 7: Commit**

```bash
cd apps/backend
git add app/config.py app/core/llm.py app/core/engine.py tests/test_llm.py tests/test_engine_assembly.py
git commit -m "llm: set an explicit Ollama context window and require digits in prompts"
```

---

## Task 4: End-to-end verification against real data

This is the acceptance criterion. Unit tests prove the rules; this proves the report that motivated the work now passes.

**Files:** none modified. Verification only.

- [ ] **Step 1: Confirm the demo database is intact**

```bash
cd apps/backend && DATABASE_URL="sqlite:///./demo.db" .venv/bin/python -c "
from sqlalchemy import func, select
from app.db import SessionLocal
from app.modules.survey123.models import FieldObservation
from app.modules.sitreps.models import SitrepIncident, SituationLog
s = SessionLocal()
print('field_observations', s.scalar(select(func.count()).select_from(FieldObservation)))
print('sitrep_incidents  ', s.scalar(select(func.count()).select_from(SitrepIncident)))
print('situation_logs    ', s.scalar(select(func.count()).select_from(SituationLog)))
s.close()"
```
Expected: 30, 15, 11.

If the file is missing, stop and report it rather than regenerating — the demo data was loaded by hand and rebuilding it is not part of this plan.

- [ ] **Step 2: Regenerate the corp report**

```bash
cd apps/backend && DATABASE_URL="sqlite:///./demo.db" OLLAMA_MODEL="gemma3-12b-16k:latest" \
  .venv/bin/python cli.py generate corp_situation_report \
  --corporation diego_martin_regional_corporati \
  --date-from 2023-06-01 --date-to 2023-06-30
```

Expected on stderr: `status: ok`. Before this work it was `status: needs_review` with 3 violations, all of them date components.

If violations remain, record each flagged token in your report — a *new* false positive is a defect in Task 1; a genuine invented number is the checker working and should be reported as such, not suppressed.

- [ ] **Step 3: Regenerate the ministerial report**

```bash
cd apps/backend && DATABASE_URL="sqlite:///./demo.db" OLLAMA_MODEL="gemma3-12b-16k:latest" \
  .venv/bin/python cli.py generate minister_situation_report \
  --date-from 2023-06-01 --date-to 2024-12-31
```

Expected: substantially fewer violations than the 13 recorded before this work, and a non-empty narrative naming both sources separately. Record the exact count and any remaining flagged tokens.

This report is generated by a local model and its wording varies between runs, so an exact violation count is not a pass/fail gate. What must hold: no violation whose token is a date component or a fragment of `Survey123`, and no `empty_narrative`.

- [ ] **Step 4: Confirm the empty-narrative guard fires on the real failure**

Reproduce the original failure by forcing the small context that caused it:

```bash
cd apps/backend && DATABASE_URL="sqlite:///./demo.db" OLLAMA_MODEL="gemma3:4b" OLLAMA_NUM_CTX=2048 \
  .venv/bin/python cli.py generate minister_situation_report \
  --date-from 2023-06-01 --date-to 2024-12-31
```

Expected: if the model returns an empty narrative under the squeezed context, the status is now `needs_review` carrying an `empty_narrative` violation — **not** `ok`. If the model happens to produce usable prose anyway, note that and move on; the unit tests in Task 2 are the binding proof, and this step is corroboration.

- [ ] **Step 5: Record the outcome**

Write the before/after numbers into your report: corp report violations 3 → N, ministerial 13 → M, with any remaining tokens listed. No commit — this task changes no files.

---

## Done when

- `Survey123` and `survey123.data_coverage` no longer yield figures.
- Prose dates in all three shapes, and ISO dates, no longer yield figures.
- A bare year with no adjacent month, an invented number in a cited sentence, and a figure with no citation are all still flagged.
- A narrative citing nothing while facts exist is a violation, and one citing a fact is not.
- `OllamaLLMClient` sets `num_ctx` from settings, defaulting to at least 8192.
- `CITATION_RULES` requires digits.
- The frontend highlighter ignores `empty_narrative` and typechecks.
- The corp report regenerates as `status: ok`.
- Backend suite: 2 failed (pre-existing `tests/test_llm.py`), everything else passing. Frontend: 19 passing, `tsc` clean.
