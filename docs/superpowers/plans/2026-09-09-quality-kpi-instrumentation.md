# Quality KPI Instrumentation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist per-report quality scores and operator signals so the PM thresholds (faithfulness, critical numbers, citations, completeness, hallucinations, unsupported claims, unaided task completion, test-workflow reliability, usability) can be measured from this codebase — without predictive analytics.

**Architecture:** Pure functions in `app/quality/` score a generated report from the fact table, narrative, markdown, and citation-check result. `narrate_fact_table` stores the document on `reports.quality_eval`. Separate tables record workflow events and 1–5 ratings. A summary endpoint aggregates rates against the spec thresholds. Named pytest `workflow` marks are the system-reliability suite.

**Tech Stack:** Python 3.13, Pydantic v2, FastAPI, SQLAlchemy 2.x, Alembic, pytest · React 19, TanStack Query, Vitest.

**Spec:** `docs/superpowers/specs/2026-09-09-quality-kpi-instrumentation-design.md`

## Global Constraints

- **No LLM in the scorer.** `score_quality` is deterministic from facts + text + violations.
- **Do not weaken `check_citations`.** Word-number detection only adds tokens; invented digits still fail. Keep a test that `99` in a cited sentence is still `invented_number`.
- **`quality_eval` never goes to the model.** It lives on `GeneratedReport` / the `reports` row only.
- **Predictive analytics is out of scope.** No precision/recall/MAE code, no model training.
- **No Langfuse, OpenTelemetry, PostHog, or Playwright in this plan.**
- **Backend tests:** `cd apps/backend && .venv/bin/python -m pytest`. Any new failure is yours.
- **Frontend tests:** `cd apps/frontend && pnpm test` and `pnpm exec tsc --noEmit -p tsconfig.json`. `@testing-library/jest-dom` is not installed — use `expect(el).not.toBeNull()`, not `toBeInTheDocument`. Render tests start with `// @vitest-environment jsdom`.
- **Alembic head today:** `c8e3a1b47d90`. New revision must revise that id. SQLite has no `ALTER COLUMN`; new columns are nullable JSON/text or created as new tables.
- **Demo DB:** never point verification at `apps/backend/dev.db` — API tests delete it.

---

## File Structure

**Create:**
- `apps/backend/app/quality/__init__.py` — re-exports `score_quality`, `QualityEval`.
- `apps/backend/app/quality/denominators.py` — critical metrics, word numbers, named workflows, thresholds.
- `apps/backend/app/quality/contracts.py` — Pydantic `QualityEval` and nested score types.
- `apps/backend/app/quality/citations.py` — citation proxy rate from `CitationCheckResult`.
- `apps/backend/app/quality/completeness.py` — required metrics + layout sections.
- `apps/backend/app/quality/numerical.py` — critical figure match.
- `apps/backend/app/quality/claims.py` — claim inventory + auto verdicts.
- `apps/backend/app/quality/score.py` — `score_quality(...)` orchestrator.
- `apps/backend/app/quality/models.py` — ORM `WorkflowEvent`, `ReportRating`.
- `apps/backend/app/quality/store.py` — event/rating/claim persistence helpers.
- `apps/backend/app/quality/summary.py` — aggregate `QualitySummary`.
- `apps/backend/app/api/quality.py` — HTTP routes.
- `apps/backend/alembic/versions/e5b1c7d83a24_add_quality_instrumentation.py`
- `apps/backend/tests/test_quality_denominators.py`
- `apps/backend/tests/test_quality_citations.py`
- `apps/backend/tests/test_quality_completeness.py`
- `apps/backend/tests/test_quality_numerical.py`
- `apps/backend/tests/test_quality_claims.py`
- `apps/backend/tests/test_quality_score.py`
- `apps/backend/tests/test_api_quality.py`
- `apps/backend/tests/test_workflow_markers.py`
- `apps/frontend/src/lib/api/quality.ts`
- `apps/frontend/src/lib/queries/quality.ts`
- `apps/frontend/src/components/reports/report-rating.tsx`
- `apps/frontend/src/components/reports/report-rating.test.tsx`
- `apps/frontend/src/components/dmu/quality-band.tsx`
- `apps/frontend/src/components/dmu/quality-band.test.tsx`

**Modify:**
- `apps/backend/app/core/citation_check.py` — public `split_narrative_units`, word-number tokens in the number scan.
- `apps/backend/app/core/engine.py` — `GeneratedReport.quality_eval`; call `score_quality` after the check.
- `apps/backend/app/core/report_models.py` — `quality_eval` JSON column.
- `apps/backend/app/core/report_store.py` — persist `quality_eval` on insert/apply.
- `apps/backend/app/api/reports.py` — include `quality_eval` on detail; `POST /reports/{id}/rating`; claim PATCH can live on quality router.
- `apps/backend/app/api/__init__.py` — unused; mount from `app/__init__.py`.
- `apps/backend/app/__init__.py` — include quality router.
- `apps/backend/app/api/capture.py` — write workflow events on session create / issue.
- `apps/backend/app/api/whatsapp.py` — events on extract / briefing.
- `apps/backend/app/api/ingest.py` — event on ingest.
- `apps/backend/app/jobs/reports.py` — event succeeded/failed when generation finishes.
- `apps/backend/cli.py` — `quality rescore` command.
- `apps/backend/alembic/env.py` — import `app.quality.models`.
- `apps/backend/pyproject.toml` — `workflow` pytest marker.
- `apps/backend/tests/test_citation_check.py` — word-number cases; keep invented-digit case.
- `apps/backend/tests/test_engine_generate.py` — `quality_eval` present after generate.
- `apps/backend/tests/test_report_store.py` — round-trip `quality_eval` through `save_report` / `get_report`.
- `apps/backend/tests/test_migrations.py` — new column + tables.
- `apps/backend/tests/test_api_reports.py` — mark `workflow("dmu_generate_report")`; detail includes `quality_eval`.
- `apps/backend/tests/test_api_capture.py` — mark `workflow("corp_capture_issue")`; events written.
- `apps/backend/tests/test_api_whatsapp.py` — mark `workflow("whatsapp_briefing")`.
- `apps/backend/tests/test_api_ingest.py` — mark `workflow("survey123_ingest")`.
- `apps/frontend/src/types/dmcu.ts` — `QualityEval`, `QualitySummary`, rating types.
- `apps/frontend/src/lib/api/reports.ts` — `postReportRating`.
- `apps/frontend/src/lib/queries/reports.ts` — rating mutation.
- `apps/frontend/src/routes/dmu/reports/$reportId.tsx` — rating + pending claims.
- `apps/frontend/src/routes/dmu/index.tsx` — quality band.
- `apps/frontend/src/components/capture/sitrep-draft-pane.tsx` — rating after issue (`filed` + `report_id`).
- `apps/frontend/src/components/reports/index.ts` — export rating.

---

### Task 1: Denominators and QualityEval contracts

**Files:**
- Create: `apps/backend/app/quality/__init__.py`
- Create: `apps/backend/app/quality/denominators.py`
- Create: `apps/backend/app/quality/contracts.py`
- Test: `apps/backend/tests/test_quality_denominators.py`

**Interfaces:**
- Consumes: nothing from later tasks.
- Produces: `CRITICAL_METRICS: frozenset[str]`; `WORD_NUMBERS: dict[str, float]`; `NAMED_WORKFLOWS: tuple[str, ...]`; `THRESHOLDS` dataclass; Pydantic models `CompletenessScore`, `NumericalMatch`, `NumericalScore`, `CitationProxy`, `ClaimRecord`, `ClaimScore`, `QualityEval` (see code in Step 3).

- [ ] **Step 1: Write the failing test**

```python
from app.quality.denominators import CRITICAL_METRICS, NAMED_WORKFLOWS, THRESHOLDS, WORD_NUMBERS


def test_critical_metrics_are_the_spec_set():
    assert CRITICAL_METRICS == frozenset(
        {
            "casualty_summary",
            "incident_count",
            "homes_affected_count",
            "estimated_damage_total",
            "special_needs_count",
            "incident_register",
        }
    )


def test_fifteen_is_a_word_number():
    assert WORD_NUMBERS["fifteen"] == 15.0


def test_named_workflows_match_the_spec():
    assert NAMED_WORKFLOWS == (
        "corp_capture_issue",
        "dmu_generate_report",
        "whatsapp_briefing",
        "survey123_ingest",
    )


def test_thresholds_match_the_pm_message():
    assert THRESHOLDS.faithfulness == 0.90
    assert THRESHOLDS.critical_numerical == 1.0
    assert THRESHOLDS.citation_accuracy == 0.95
    assert THRESHOLDS.completeness == 0.95
    assert THRESHOLDS.critical_hallucination == 0.0
    assert THRESHOLDS.unsupported_claim == 0.05
    assert THRESHOLDS.task_completion == 0.80
    assert THRESHOLDS.workflow_reliability == 0.95
    assert THRESHOLDS.usability_mean == 4.0
    assert THRESHOLDS.usability_positive == 0.80
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend && .venv/bin/python -m pytest tests/test_quality_denominators.py -v`

Expected: FAIL with `ModuleNotFoundError: app.quality`

- [ ] **Step 3: Write minimal implementation**

`apps/backend/app/quality/denominators.py`:

```python
from dataclasses import dataclass

CRITICAL_METRICS = frozenset(
    {
        "casualty_summary",
        "incident_count",
        "homes_affected_count",
        "estimated_damage_total",
        "special_needs_count",
        "incident_register",
    }
)

WORD_NUMBERS: dict[str, float] = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
    "hundred": 100,
    "thousand": 1000,
}

NAMED_WORKFLOWS = (
    "corp_capture_issue",
    "dmu_generate_report",
    "whatsapp_briefing",
    "survey123_ingest",
)

ZERO_EVENT_PHRASES = (
    "no casualties",
    "no deaths",
    "no injuries",
    "no one was injured",
    "nobody was injured",
)


@dataclass(frozen=True)
class Thresholds:
    faithfulness: float = 0.90
    critical_numerical: float = 1.0
    citation_accuracy: float = 0.95
    completeness: float = 0.95
    critical_hallucination: float = 0.0
    unsupported_claim: float = 0.05
    task_completion: float = 0.80
    workflow_reliability: float = 0.95
    usability_mean: float = 4.0
    usability_positive: float = 0.80


THRESHOLDS = Thresholds()
```

`apps/backend/app/quality/contracts.py`:

```python
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class CompletenessScore(BaseModel):
    expected: list[str]
    present: list[str]
    missing: list[str]
    rate: float


class NumericalMatch(BaseModel):
    metric: str
    cid: str
    expected: float | str
    appeared: bool
    matched: bool


class NumericalScore(BaseModel):
    items: list[NumericalMatch]
    rate: float
    passed: bool


class CitationProxy(BaseModel):
    citation_instances: int
    missing: int
    misattributed: int
    invented: int
    rate: float


class ClaimRecord(BaseModel):
    claim_id: str
    sentence: str
    cited_cids: list[str]
    number_tokens: list[str]
    critical: bool
    auto_verdict: Literal["supported", "unsupported", "pending_semantic"]
    human_verdict: Literal["supported", "unsupported"] | None = None


class ClaimScore(BaseModel):
    claims: list[ClaimRecord]
    material_count: int
    unsupported_count: int
    critical_unsupported_count: int
    faithfulness_rate: float | None
    unsupported_rate: float | None
    critical_hallucination_rate: float | None


class QualityEval(BaseModel):
    scored_at: datetime
    scorer_version: int = 1
    completeness: CompletenessScore
    numerical: NumericalScore
    citations: CitationProxy
    claims: ClaimScore
```

`apps/backend/app/quality/__init__.py`:

```python
from app.quality.contracts import QualityEval
from app.quality.denominators import CRITICAL_METRICS, THRESHOLDS

__all__ = ["CRITICAL_METRICS", "QualityEval", "THRESHOLDS"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/backend && .venv/bin/python -m pytest tests/test_quality_denominators.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/backend/app/quality/__init__.py apps/backend/app/quality/denominators.py apps/backend/app/quality/contracts.py apps/backend/tests/test_quality_denominators.py docs/superpowers/specs/2026-09-09-quality-kpi-instrumentation-design.md docs/superpowers/plans/2026-09-09-quality-kpi-instrumentation.md
git commit -m "$(cat <<'EOF'
Add quality KPI denominators and eval contracts.

EOF
)"
```

---

### Task 2: Citation proxy, completeness, and critical numerical scorers

**Files:**
- Create: `apps/backend/app/quality/citations.py`
- Create: `apps/backend/app/quality/completeness.py`
- Create: `apps/backend/app/quality/numerical.py`
- Test: `apps/backend/tests/test_quality_citations.py`
- Test: `apps/backend/tests/test_quality_completeness.py`
- Test: `apps/backend/tests/test_quality_numerical.py`

**Interfaces:**
- Consumes: `CitationCheckResult` / `CitationViolation` from `app.core.citation_check`; `FactTable`, `Template`, `DataRequirement` from `app.core.contracts`; `CRITICAL_METRICS`; score types from Task 1.
- Produces: `score_citations(result: CitationCheckResult, narrative: str) -> CitationProxy`; `score_completeness(template: Template, fact_table: FactTable, markdown: str) -> CompletenessScore`; `score_numerical(fact_table: FactTable, markdown: str, result: CitationCheckResult) -> NumericalScore`.

- [ ] **Step 1: Write the failing tests**

Reuse `make_citation` / `make_fact_table` pattern from `tests/test_citation_check.py` — copy the helpers into each new test file (do not import from the test module). Use `check_citations` from `app.core.citation_check`.

`tests/test_quality_citations.py`:

```python
from datetime import datetime

from app.core.citation_check import check_citations
from app.core.contracts import Citation, Fact, FactTable
from app.quality.citations import score_citations


def make_table() -> FactTable:
    fact = Fact(
        metric="incident_count",
        value=19,
        unit="incidents",
        scope={"corporation": "all"},
        breakdown=None,
        verification="validated",
        citation=Citation(
            cid="C001",
            module="sitreps",
            description="count",
            query_ref="q",
            record_ids=["1"],
            as_of=datetime(2024, 7, 1),
        ),
    )
    return FactTable(
        request_id="r",
        template="t",
        params={},
        generated_at=datetime(2024, 7, 1),
        facts=[fact],
        gaps=[],
    )


def test_perfect_citation_rate_is_one():
    narrative = "There were 19 incidents [C001]."
    result = check_citations(narrative, make_table())
    proxy = score_citations(result, narrative)
    assert result.passed
    assert proxy.citation_instances == 1
    assert proxy.rate == 1.0
    assert proxy.missing == 0
    assert proxy.misattributed == 0
    assert proxy.invented == 0


def test_missing_citation_drops_the_rate():
    narrative = "There were 19 incidents."
    result = check_citations(narrative, make_table())
    proxy = score_citations(result, narrative)
    assert proxy.missing >= 1
    assert proxy.rate < 1.0
```

`tests/test_quality_completeness.py` — build a `Template` with `RenderConfig(layout="filing")`, `output_sections=["connective_prose", "data_gaps"]`, one `DataRequirement(module="sitreps", metric="incident_count")`. Fact table with `incident_count` (value 3, breakdown `{"flooding_": 3}`) and empty gaps. Markdown containing `# Title`, `## Situation summary`, `## Citation Appendix`.

```python
def test_filing_with_justified_sections_is_complete():
    score = score_completeness(template, fact_table, markdown)
    assert score.missing == []
    assert score.rate == 1.0


def test_missing_metric_without_a_gap_is_incomplete():
    # data_requirements include casualty_summary but facts and gaps do not
    score = score_completeness(template, fact_table, markdown)
    assert "sitreps.casualty_summary" in score.missing
    assert score.rate < 1.0


def test_gap_naming_the_metric_counts_as_present():
    fact_table = fact_table.model_copy(
        update={"gaps": ["No data returned for sitreps.casualty_summary with params {}"]}
    )
    score = score_completeness(template, fact_table, markdown)
    assert "sitreps.casualty_summary" not in score.missing
```

`tests/test_quality_numerical.py`:

```python
def test_critical_count_in_markdown_matches_the_fact():
    markdown = "There were 19 incidents [C001].\n"
    result = check_citations(markdown, table)
    score = score_numerical(table, markdown, result)
    assert score.passed
    assert score.rate == 1.0


def test_invented_critical_number_fails():
    markdown = "There were 99 incidents [C001].\n"
    result = check_citations(markdown, table)
    score = score_numerical(table, markdown, result)
    assert score.passed is False
```

Use an `incident_count` fact with cid `C001` and value `19` as in the citation tests. `casualty_summary` is also critical — include a second test where markdown omits a zero `deaths` fact and `passed` stays True (`appeared` False is allowed).

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/backend && .venv/bin/python -m pytest tests/test_quality_citations.py tests/test_quality_completeness.py tests/test_quality_numerical.py -v`

Expected: FAIL `ModuleNotFoundError` for the three modules.

- [ ] **Step 3: Write minimal implementation**

`citations.py`: count `[C00n]` markers in `narrative` with `CITATION_MARKER_RE` from `citation_check` (import the existing regex). `missing` / `misattributed` / `invented` = counts of those `result.violations` kinds. `rate = 1.0` if `citation_instances == 0` else `max(0.0, 1.0 - (missing + misattributed) / citation_instances)`. Invented numbers are not in this rate (they are hallucination / numerical); they are still stored on the proxy for the summary.

`completeness.py` expected keys:
- For each `template.data_requirements` item: `f"{module}.{metric}"` present if any `fact.metric == metric` **or** any gap contains that `module.metric` string.
- Filing layout (`template.render.layout == "filing"`): if an `incident_count` fact has a truthy value and breakdown, expect heading `Situation summary` in markdown; if any `relief_stock_summary` fact has truthy value, `Relief and resources`; if any `incident_register` facts, `Incidents`; if any `activity_log` facts, `Activities`; if any non-empty gap not equal `none`, `Data Gaps` **or** `Information not yet available`; if `template.render.include_citation_appendix`, `Citation Appendix`.
- Narrative layout: if any fact has a breakdown, expect `Data Tables`; gaps → `Data Gaps`; appendix flag → `Citation Appendix`.

`rate = len(present) / len(expected)` if expected else `1.0`.

`numerical.py`: for each fact whose `metric in CRITICAL_METRICS`:
- `expected` = `fact.value` (and for `incident_register`, also parse `scope["injuries"]` / `scope["deaths"]` when they look numeric).
- `appeared` = formatted number (`str(int(v))` if whole float else `str(v)`) occurs as a token in markdown **or** a violation token matches.
- `matched` = not appeared, **or** appeared and no `invented_number`/`misattributed_number` on a sentence that cites this cid.
- `passed` = all items `matched`; `rate` = matched/items or `1.0` if no critical facts.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/backend && .venv/bin/python -m pytest tests/test_quality_citations.py tests/test_quality_completeness.py tests/test_quality_numerical.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/backend/app/quality/citations.py apps/backend/app/quality/completeness.py apps/backend/app/quality/numerical.py apps/backend/tests/test_quality_citations.py apps/backend/tests/test_quality_completeness.py apps/backend/tests/test_quality_numerical.py
git commit -m "$(cat <<'EOF'
Score citation proxy, completeness, and critical numbers.

EOF
)"
```

---

### Task 3: Claim inventory

**Files:**
- Create: `apps/backend/app/quality/claims.py`
- Modify: `apps/backend/app/core/citation_check.py` — add public `split_narrative_units(text: str) -> list[str]` that is `_split_sentences`.
- Test: `apps/backend/tests/test_quality_claims.py`

**Interfaces:**
- Consumes: `split_narrative_units`, `CITATION_MARKER_RE`, `_cids_in` (export as `cids_in` public alias), `NUMBER_TOKEN_RE`, `CitationCheckResult`, `FactTable`, `CRITICAL_METRICS`, `ZERO_EVENT_PHRASES`.
- Produces: `extract_claims(narrative: str, fact_table: FactTable, result: CitationCheckResult) -> ClaimScore`.

- [ ] **Step 1: Write the failing tests**

```python
def test_cited_matching_number_is_supported():
    score = extract_claims("There were 19 incidents [C001].", table, result)
    assert score.material_count == 1
    assert score.claims[0].auto_verdict == "supported"
    assert score.unsupported_rate == 0.0
    assert score.faithfulness_rate == 1.0


def test_invented_number_is_unsupported():
    score = extract_claims("There were 99 incidents [C001].", table, result)
    assert score.claims[0].auto_verdict == "unsupported"
    assert score.unsupported_count == 1


def test_connective_prose_is_not_material():
    score = extract_claims("The situation remains dynamic.", table, empty_pass_result)
    assert score.material_count == 0
    assert score.claims == []


def test_no_deaths_without_a_zero_fact_is_critical_unsupported():
    score = extract_claims("There were no deaths.", table_without_casualty, result)
    assert score.claims[0].critical is True
    assert score.claims[0].auto_verdict == "unsupported"
    assert score.critical_unsupported_count == 1
    assert score.critical_hallucination_rate == 1.0


def test_cited_prose_without_digits_is_pending_semantic():
    score = extract_claims("Flooding affected Arima [C001].", table, result)
    assert score.claims[0].auto_verdict == "pending_semantic"
    assert score.faithfulness_rate is None  # no resolved material claims yet
```

`faithfulness_rate` = supported / (supported + unsupported) among claims whose effective verdict is not `pending_semantic`. Effective verdict = `human_verdict or auto_verdict`. If that resolved set is empty, rates are `None`.

`critical_hallucination_rate` = critical_unsupported / critical_claims, or `None` if no critical claims, or `0.0` if critical claims exist and none unsupported.

Pending semantic claims are **excluded** from faithfulness and unsupported rates until a human verdict exists (Task 8). They still appear in `claims[]`.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend && .venv/bin/python -m pytest tests/test_quality_claims.py -v`

Expected: FAIL import

- [ ] **Step 3: Implement**

In `citation_check.py` add:

```python
def split_narrative_units(text: str) -> list[str]:
    return _split_sentences(text)


def cids_in(text: str) -> set[str]:
    return _cids_in(text)
```

`extract_claims`:
1. Split narrative.
2. Skip a sentence if it has no number tokens (after date strip), no cids, and no `ZERO_EVENT_PHRASES` hit (`phrase in sentence.lower()`).
3. `critical` if any cited fact’s metric is in `CRITICAL_METRICS` **or** a zero-event phrase matched.
4. If any violation (except `empty_narrative`) has `v.sentence == sentence` (or sentence in `v.sentence`): `unsupported`.
5. Else if zero-event phrase and no fact with metric `casualty_summary` whose value is `0` or whose breakdown has a `0` deaths/injuries key: `unsupported`.
6. Else if number tokens and valid cids: `supported`.
7. Else: `pending_semantic`.
8. `claim_id` = `f"cl{index:03d}"` 1-based in inventory order.

Pending facts with `verification == "pending"`: if the claim only cites pending facts, force `pending_semantic` even if numbers match (cannot pass faithfulness on WhatsApp).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/backend && .venv/bin/python -m pytest tests/test_quality_claims.py tests/test_citation_check.py -v`

Expected: PASS (existing citation tests still pass)

- [ ] **Step 5: Commit**

```bash
git add apps/backend/app/quality/claims.py apps/backend/app/core/citation_check.py apps/backend/tests/test_quality_claims.py
git commit -m "$(cat <<'EOF'
Extract material claims and auto-verdict them from the fact table.

EOF
)"
```

---

### Task 4: Spelled-out numbers in the citation checker

**Files:**
- Modify: `apps/backend/app/core/citation_check.py`
- Test: `apps/backend/tests/test_citation_check.py`

**Interfaces:**
- Consumes: `WORD_NUMBERS` from `app.quality.denominators`.
- Produces: `check_citations` treats word numbers as tokens after date stripping. Signature unchanged.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_citation_check.py`. Use existing `make_fact_table()` (values include `15`).

```python
def test_spelled_out_invented_number_is_flagged():
    result = check_citations(
        "There were ninety-nine homes affected [survey123-incident_count-0].",
        make_fact_table(),
    )
    kinds = {v.kind for v in result.violations}
    assert "invented_number" in kinds


def test_spelled_out_licensed_number_passes():
    result = check_citations(
        "There were fifteen records [survey123-data_coverage-2].",
        make_fact_table(),
    )
    assert [v for v in result.violations if v.kind == "invented_number"] == []


def test_digit_invented_number_still_flagged():
    result = check_citations(
        "There were 99 incidents [survey123-incident_count-0].",
        make_fact_table(),
    )
    assert any(v.kind == "invented_number" and v.token == "99" for v in result.violations)
```

Do **not** require hyphenated `ninety-nine` if that is painful: implement whole-word keys only (`ninety` is 90, which is still invented vs 19/15/98000). Then change the first test to `"There were ninety homes affected [survey123-incident_count-0]."` so the token is `ninety` → 90.0.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/backend && .venv/bin/python -m pytest tests/test_citation_check.py::test_spelled_out_invented_number_is_flagged tests/test_citation_check.py::test_spelled_out_licensed_number_passes -v`

Expected: FAIL (`invented_number` missing on “ninety”)

- [ ] **Step 3: Implement**

After `NUMBER_TOKEN_RE.findall`, also find word numbers:

```python
_WORD_RE = re.compile(
    r"\b(" + "|".join(re.escape(w) for w in sorted(WORD_NUMBERS, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)
```

For each match, treat `token` as the matched word (original casing) and `value = WORD_NUMBERS[word.lower()]`. Feed them through the same invented / misattributed branches. Skip words that sit inside a prose date that was already stripped (scan the date-stripped string only).

Keep `NUMBER_TOKEN_RE` behaviour identical for digits.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/backend && .venv/bin/python -m pytest tests/test_citation_check.py -v`

Expected: PASS including the new cases and the old invented-digit cases.

- [ ] **Step 5: Commit**

```bash
git add apps/backend/app/core/citation_check.py apps/backend/tests/test_citation_check.py
git commit -m "$(cat <<'EOF'
Treat spelled-out numbers as citation-checked figures.

EOF
)"
```

---

### Task 5: Orchestrator, persist quality_eval, hook generate

**Files:**
- Create: `apps/backend/app/quality/score.py`
- Modify: `apps/backend/app/core/engine.py`
- Modify: `apps/backend/app/core/report_models.py`
- Modify: `apps/backend/app/core/report_store.py`
- Modify: `apps/backend/app/api/reports.py` (`ReportDetail.quality_eval`)
- Create: `apps/backend/alembic/versions/e5b1c7d83a24_add_quality_instrumentation.py`
- Modify: `apps/backend/alembic/env.py`
- Modify: `apps/backend/tests/test_migrations.py`
- Modify: `apps/backend/tests/test_engine_generate.py`
- Modify: `apps/backend/cli.py`
- Test: `apps/backend/tests/test_quality_score.py`

**Interfaces:**
- Consumes: the four scorers; `GeneratedReport`; `Report` ORM.
- Produces: `score_quality(template, fact_table, narrative, markdown, result) -> QualityEval`; `GeneratedReport.quality_eval: QualityEval | None = None` filled by `narrate_fact_table`; `Report.quality_eval: dict | None`; `apply_generated_report` / `add_report` write it; `GET /reports/{id}` returns it; `cli quality-rescore` walks rows with narrative.

- [ ] **Step 1: Write the failing tests**

`tests/test_quality_score.py`:

```python
def test_score_quality_composes_all_sections():
    eval_ = score_quality(template, fact_table, narrative, markdown, result)
    assert eval_.scorer_version == 1
    assert eval_.citations.rate == 1.0
    assert eval_.completeness.rate == 1.0
    assert eval_.numerical.passed
    assert eval_.claims.material_count >= 1
```

In `tests/test_report_store.py`, after a `save_report` of a `GeneratedReport` that includes a stub `QualityEval`, `get_report(...).quality_eval["scorer_version"] == 1`.

In `tests/test_engine_generate.py` `test_generate_report_with_auto_narrative_fake_client_passes`, add:

```python
    assert report.quality_eval is not None
    assert report.quality_eval.citations.rate >= 0.0
```

In `tests/test_migrations.py` `test_the_backfilled_columns_keep_their_shape`, after the `error` asserts:

```python
    assert "quality_eval" in reports
    assert reports["quality_eval"][3] == 0  # nullable
```

In `test_every_table_exists_after_upgrade_head` add `"workflow_events"` and `"report_ratings"` to the required set (tables are created in this same migration even if unused until Tasks 6–7).

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/backend && .venv/bin/python -m pytest tests/test_quality_score.py tests/test_engine_generate.py::test_generate_report_with_auto_narrative_fake_client_passes tests/test_migrations.py::test_the_backfilled_columns_keep_their_shape -v`

Expected: FAIL missing `score_quality` / `quality_eval`

- [ ] **Step 3: Implement**

`score.py`:

```python
from datetime import datetime, timezone

from app.core.citation_check import CitationCheckResult
from app.core.contracts import FactTable, Template
from app.quality.claims import extract_claims
from app.quality.citations import score_citations
from app.quality.completeness import score_completeness
from app.quality.contracts import QualityEval
from app.quality.numerical import score_numerical


def score_quality(
    template: Template,
    fact_table: FactTable,
    narrative: str,
    markdown: str,
    result: CitationCheckResult,
) -> QualityEval:
    return QualityEval(
        scored_at=datetime.now(timezone.utc),
        completeness=score_completeness(template, fact_table, markdown),
        numerical=score_numerical(fact_table, markdown, result),
        citations=score_citations(result, narrative),
        claims=extract_claims(narrative, fact_table, result),
    )
```

`GeneratedReport` add `quality_eval: QualityEval | None = None`.

In `narrate_fact_table`, after `final_markdown = render_report(...)`:

```python
    quality_eval = score_quality(template, fact_table, narrative, markdown, result)
```

and pass it into `GeneratedReport(...)`.

`Report` model:

```python
    quality_eval: Mapped[dict | None] = mapped_column(JSON, nullable=True)
```

`add_report` / `apply_generated_report`:

```python
    quality_eval=report.quality_eval.model_dump(mode="json") if report.quality_eval else None
```

`save_placeholder_report` leaves `quality_eval=None`.

`ReportDetail` add `quality_eval: dict | None = None` and pass `db_report.quality_eval`.

Migration `e5b1c7d83a24` revises `c8e3a1b47d90`:

```python
def upgrade() -> None:
    op.add_column("reports", sa.Column("quality_eval", sa.JSON(), nullable=True))
    op.create_table(
        "workflow_events",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("workflow", sa.String(), nullable=False),
        sa.Column("step", sa.String(), nullable=False),
        sa.Column("outcome", sa.String(), nullable=False),
        sa.Column("subject_id", sa.String(), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("assisted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "report_ratings",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("report_id", sa.String(), sa.ForeignKey("reports.id"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("report_id", "user_id", name="uq_report_ratings_report_user"),
    )


def downgrade() -> None:
    op.drop_table("report_ratings")
    op.drop_table("workflow_events")
    op.drop_column("reports", "quality_eval")
```

After `create_table`, SQLite keeps `server_default` on `assisted`. Follow the existing pattern: if tests require no server default, add a second batch dropping it. Prefer ORM `default=False` without server_default and set the column `nullable=False` only if SQLite create_table can do it for empty DBs — **new table, so `nullable=False` without server_default is OK**.

`alembic/env.py` add `from app.quality import models as quality_models  # noqa: F401`

ORM models in Task 6; for this task create `apps/backend/app/quality/models.py` with both tables so `create_all` in API tests includes them. Empty file with the two classes now (copy column types from the migration).

CLI: `@app.command("quality-rescore")` loads every `Report` with non-empty `narrative`, reconstructs `FactTable` and a `Template` via `get_template_version`, runs `check_citations` + `score_quality`, writes `row.quality_eval`. Skip rows whose template is missing.

- [ ] **Step 4: Run tests**

Run:

```
cd apps/backend && .venv/bin/python -m pytest tests/test_quality_score.py tests/test_engine_generate.py tests/test_migrations.py tests/test_api_reports.py tests/test_citation_check.py tests/test_quality_claims.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/backend/app/quality/score.py apps/backend/app/quality/models.py apps/backend/app/core/engine.py apps/backend/app/core/report_models.py apps/backend/app/core/report_store.py apps/backend/app/api/reports.py apps/backend/alembic/versions/e5b1c7d83a24_add_quality_instrumentation.py apps/backend/alembic/env.py apps/backend/cli.py apps/backend/tests/test_quality_score.py apps/backend/tests/test_engine_generate.py apps/backend/tests/test_migrations.py
git commit -m "$(cat <<'EOF'
Persist a quality eval on every generated report.

EOF
)"
```

---

### Task 6: Workflow events and quality summary API

**Files:**
- Create: `apps/backend/app/quality/store.py`
- Create: `apps/backend/app/quality/summary.py`
- Create: `apps/backend/app/api/quality.py`
- Modify: `apps/backend/app/__init__.py`
- Modify: `apps/backend/app/api/capture.py`
- Modify: `apps/backend/app/api/reports.py` (create_report started; job layer for succeeded)
- Modify: `apps/backend/app/jobs/reports.py`
- Modify: `apps/backend/app/api/whatsapp.py`
- Modify: `apps/backend/app/api/ingest.py`
- Test: `apps/backend/tests/test_api_quality.py`
- Modify: `apps/backend/tests/test_api_capture.py` (one assertion that an event row exists after issue)
- Modify: `apps/backend/pyproject.toml` — not yet markers (Task 9)

**Interfaces:**
- Consumes: `NAMED_WORKFLOWS`; `WorkflowEvent` ORM; `Report.quality_eval`; `THRESHOLDS`.
- Produces: `record_event(session, *, workflow, step, outcome, subject_id=None, user_id=None, assisted=False) -> WorkflowEvent`; `GET /quality/summary -> QualitySummary`; `POST /quality/events`; `PATCH /quality/events/{id}` body `{assisted: bool}`.

`QualitySummary` Pydantic:

```python
class ThresholdStatus(BaseModel):
    name: str
    threshold: float
    actual: float | None
    met: bool | None
    sample: int


class QualitySummary(BaseModel):
    report_count: int
    scored_count: int
    thresholds: list[ThresholdStatus]
    rating_count: int = 0
    rating_mean: float | None = None
    rating_positive_rate: float | None = None
    task_started: int = 0
    task_succeeded_unaided: int = 0
```

Aggregation:
- Among reports with `quality_eval` not null: mean of `claims.faithfulness_rate` ignoring None; mean citation `rate`; fraction of `numerical.passed`; mean completeness `rate`; mean `claims.critical_hallucination_rate` ignoring None; mean `claims.unsupported_rate` ignoring None.
- Tasks: count `outcome=started` vs `outcome=succeeded AND assisted=false` grouped by workflow, then overall `unaided_successes / started` if started > 0.
- Ratings filled in Task 7 (keep zeros).

`record_event` generates `id=str(uuid.uuid4())`, `created_at=now(timezone.utc)`, `session.add` — **do not commit**; caller already commits.

Hook points (commit with the existing request transaction):
- `create_report`: `workflow="dmu_generate_report", step="create", outcome="started", subject_id=report_id`
- `run_generate_report` after `apply_generated_report`: `step="generate", outcome="succeeded"`; `mark_report_failed`: `outcome="failed"`
- `POST /capture/sessions`: `corp_capture_issue` / `create` / `started` / `subject_id=str(session.id)`
- `issue_session` after success: `step="issue"` / `succeeded` / `subject_id=saved.id`
- `POST /whatsapp/extract`: started; `POST .../briefing` after enqueue or sync complete: succeeded
- `POST /ingest/survey123`: started then succeeded in the same handler if ingest returns 200

- [ ] **Step 1: Write failing API tests** in `tests/test_api_quality.py` using the same `make_client` pattern as `test_api_reports.py` (fake LLM, import templates, ingest fixture).

```python
def test_summary_includes_scored_report_after_generate(monkeypatch):
    client = make_client(monkeypatch)
    _ingest_fixture()
    created = client.post(
        "/reports",
        json={"template": "minister_situation_report", "params": {"date_from": "2024-06-01", "date_to": "2024-06-30"}},
    )
    assert created.status_code == 202
    summary = client.get("/quality/summary")
    assert summary.status_code == 200
    body = summary.json()
    assert body["scored_count"] >= 1
    names = {row["name"] for row in body["thresholds"]}
    assert names >= {
        "faithfulness",
        "critical_numerical",
        "citation_accuracy",
        "completeness",
        "critical_hallucination",
        "unsupported_claim",
        "task_completion",
        "usability_mean",
        "usability_positive",
    }


def test_create_report_writes_a_started_event(monkeypatch):
    client = make_client(monkeypatch)
    _ingest_fixture()
    created = client.post("/reports", json={...})
    events = client.get("/quality/events", params={"subject_id": created.json()["id"]})
    assert events.status_code == 200
    outcomes = {e["outcome"] for e in events.json()["items"]}
    assert "started" in outcomes
    assert "succeeded" in outcomes
```

Also `POST /quality/events` with `{workflow, step, outcome, subject_id}` returns 201.

`PATCH /quality/events/{id}` `{"assisted": true}` then summary `task_succeeded_unaided` does not count that event.

- [ ] **Step 2: Run to verify fail**

Run: `cd apps/backend && .venv/bin/python -m pytest tests/test_api_quality.py -v`

Expected: 404 on `/quality/summary`

- [ ] **Step 3: Implement** store, summary, router `APIRouter()` with the three routes, `app.include_router(quality_router)`. GET `/quality/events` with optional `subject_id` / `workflow` query for tests.

Unknown `workflow` on POST → 400 listing `NAMED_WORKFLOWS`.

- [ ] **Step 4: Run tests**

Run: `cd apps/backend && .venv/bin/python -m pytest tests/test_api_quality.py tests/test_api_reports.py tests/test_api_capture.py tests/test_api_whatsapp.py tests/test_api_ingest.py -v`

Expected: PASS. Capture/whatsapp/ingest tests must still pass after the extra `record_event` calls — events are additive.

- [ ] **Step 5: Commit**

```bash
git add apps/backend/app/quality/store.py apps/backend/app/quality/summary.py apps/backend/app/api/quality.py apps/backend/app/__init__.py apps/backend/app/api/capture.py apps/backend/app/api/reports.py apps/backend/app/jobs/reports.py apps/backend/app/api/whatsapp.py apps/backend/app/api/ingest.py apps/backend/tests/test_api_quality.py
git commit -m "$(cat <<'EOF'
Record workflow events and expose a quality summary.

EOF
)"
```

---

### Task 7: Report ratings

**Files:**
- Modify: `apps/backend/app/quality/store.py` — `save_rating`
- Modify: `apps/backend/app/api/quality.py` or `reports.py` — `POST /reports/{report_id}/rating`
- Modify: `apps/backend/app/quality/summary.py` — fill rating fields
- Modify: `apps/backend/tests/test_api_quality.py`
- Modify: `apps/backend/tests/auth_helpers.py` only if you need a helper to login; prefer existing OTP flow from `tests/test_api_auth.py`.

**Interfaces:**
- Consumes: `CurrentUser`; `ReportRating`.
- Produces: `POST /reports/{report_id}/rating` body `{rating: int, comment?: str}` → `{id, report_id, rating}`; 401 without auth; 404 unknown report; 422 if rating not in 1..5. Upsert on `(report_id, user_id)`.

- [ ] **Step 1: Write failing tests**

Use `make_auth_client` + `create_user` + the OTP verify path already in `test_api_auth.py`. If that is heavy, add a test helper `bearer_for(user)` in `auth_helpers.py` that mints an access token via `app.auth.tokens` the same way production does — **only if a function already exists**. Search `create_access_token` / `encode` in `app/auth/tokens.py` and call it.

```python
def test_rating_requires_auth(monkeypatch):
    client = make_client(monkeypatch)
    response = client.post("/reports/nope/rating", json={"rating": 5})
    assert response.status_code == 401


def test_authenticated_user_can_rate_a_report(monkeypatch):
    # create report via fake LLM client, login, POST rating 5
    ...
    summary = client.get("/quality/summary").json()
    assert summary["rating_count"] == 1
    assert summary["rating_mean"] == 5.0
    assert summary["rating_positive_rate"] == 1.0
```

- [ ] **Step 2: Run to verify fail**

Run: `cd apps/backend && .venv/bin/python -m pytest tests/test_api_quality.py -k rating -v`

Expected: 404 or 401 on the rating route missing

- [ ] **Step 3: Implement**

```python
class RatingIn(BaseModel):
    rating: int
    comment: str | None = None

    @field_validator("rating")
    @classmethod
    def one_to_five(cls, value: int) -> int:
        if value < 1 or value > 5:
            raise ValueError("rating must be 1..5")
        return value
```

Positive rate = count(rating >= 4) / count.

- [ ] **Step 4: Run tests**

Run: `cd apps/backend && .venv/bin/python -m pytest tests/test_api_quality.py tests/test_api_auth.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/backend/app/quality/store.py apps/backend/app/api/quality.py apps/backend/app/api/reports.py apps/backend/app/quality/summary.py apps/backend/tests/test_api_quality.py apps/backend/tests/auth_helpers.py
git commit -m "$(cat <<'EOF'
Accept 1-5 usefulness ratings on generated reports.

EOF
)"
```

---

### Task 8: Human claim verdicts

**Files:**
- Modify: `apps/backend/app/quality/store.py` — `apply_claim_verdict(row: Report, claim_id: str, verdict: Literal["supported","unsupported"]) -> QualityEval`
- Modify: `apps/backend/app/api/quality.py` — `PATCH /reports/{report_id}/claims/{claim_id}` with `DmuUser`
- Modify: `apps/backend/tests/test_api_quality.py`
- Test: add a unit test in `tests/test_quality_claims.py` that after `human_verdict="supported"` on a pending claim, `faithfulness_rate` becomes 1.0. Put the recompute in `recompute_claim_rates(score: ClaimScore) -> ClaimScore` and call it from `apply_claim_verdict`.

**Interfaces:**
- Consumes: stored `quality_eval` JSON.
- Produces: PATCH updates that claim’s `human_verdict`, recomputes the three rates, writes back JSON.

- [ ] **Step 1: Write failing tests**

```python
def test_human_verdict_resolves_pending_semantic():
    score = extract_claims("Flooding affected Arima [C001].", table, passing_result)
    assert score.claims[0].auto_verdict == "pending_semantic"
    score.claims[0].human_verdict = "supported"
    updated = recompute_claim_rates(score)
    assert updated.faithfulness_rate == 1.0
    assert updated.unsupported_rate == 0.0
```

API: DMU user PATCHes; 403 for corp role; 404 for unknown claim_id.

- [ ] **Step 2: Run to verify fail**

Run: `cd apps/backend && .venv/bin/python -m pytest tests/test_quality_claims.py tests/test_api_quality.py -k verdict -v`

- [ ] **Step 3: Implement** `recompute_claim_rates` using effective verdict = `human_verdict or auto_verdict`. Pending semantic without human still excluded.

- [ ] **Step 4: Run**

Run: `cd apps/backend && .venv/bin/python -m pytest tests/test_quality_claims.py tests/test_api_quality.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/backend/app/quality/claims.py apps/backend/app/quality/store.py apps/backend/app/api/quality.py apps/backend/tests/test_quality_claims.py apps/backend/tests/test_api_quality.py
git commit -m "$(cat <<'EOF'
Allow DMU officers to verdict pending semantic claims.

EOF
)"
```

---

### Task 9: Named pytest workflow suite

**Files:**
- Modify: `apps/backend/pyproject.toml`
- Modify: `apps/backend/tests/test_api_reports.py` — `@pytest.mark.workflow("dmu_generate_report")` on `test_post_reports_returns_id_status_markdown`
- Modify: `apps/backend/tests/test_api_capture.py` — mark the existing issue-success test (the one that posts `/capture/sessions/{id}/issue` and expects 201) as `workflow("corp_capture_issue")`
- Modify: `apps/backend/tests/test_api_whatsapp.py` — mark the briefing-success test `workflow("whatsapp_briefing")`
- Modify: `apps/backend/tests/test_api_ingest.py` — mark the happy-path ingest `workflow("survey123_ingest")`
- Create: `apps/backend/tests/test_workflow_markers.py`
- Create: `apps/backend/scripts/workflow_pass_rate.py`

**Interfaces:**
- Consumes: pytest marker `workflow`.
- Produces: `python scripts/workflow_pass_rate.py` prints `passed/collected` and exits 1 if `< 0.95`.

- [ ] **Step 1: Write the failing test**

`pyproject.toml` under `[tool.pytest.ini_options]`:

```toml
markers = [
    "workflow(name): named PM system-reliability workflow",
]
```

`tests/test_workflow_markers.py`:

```python
import pytest


def test_every_named_workflow_has_at_least_one_test(request):
    from app.quality.denominators import NAMED_WORKFLOWS

    seen: set[str] = set()
    for item in request.session.items:
        marker = item.get_closest_marker("workflow")
        if marker and marker.args:
            seen.add(marker.args[0])
    missing = set(NAMED_WORKFLOWS) - seen
    assert missing == set(), f"no pytest.mark.workflow tests for {sorted(missing)}"
```

This test only passes once the four marks exist. Write it first, run, then add marks.

- [ ] **Step 2: Run to verify fail**

Run: `cd apps/backend && .venv/bin/python -m pytest tests/test_workflow_markers.py -v`

Expected: FAIL missing workflow names (or unknown mark warning until pyproject is updated)

- [ ] **Step 3: Add the four marks and the script**

`scripts/workflow_pass_rate.py`:

```python
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
proc = subprocess.run(
    [sys.executable, "-m", "pytest", "-m", "workflow", "-q", "--tb=no"],
    cwd=ROOT,
    capture_output=True,
    text=True,
)
# Parse the last line "n passed" / "n failed" — if collected == 0, exit 1.
# Exit 0 only when passed/collected >= 0.95.
```

Keep parsing simple: run `pytest -m workflow --collect-only -q` to get count, then `pytest -m workflow`. If you would rather not parse pytest output, the marker test plus a full `pytest -m workflow` in this task’s verify step **is** the 95% gate (all marked tests must pass ⇒ 100%).

- [ ] **Step 4: Run**

Run:

```
cd apps/backend && .venv/bin/python -m pytest -m workflow -v
cd apps/backend && .venv/bin/python -m pytest tests/test_workflow_markers.py -v
```

Expected: PASS, collected ≥ 4

- [ ] **Step 5: Commit**

```bash
git add apps/backend/pyproject.toml apps/backend/tests/test_workflow_markers.py apps/backend/scripts/workflow_pass_rate.py apps/backend/tests/test_api_reports.py apps/backend/tests/test_api_capture.py apps/backend/tests/test_api_whatsapp.py apps/backend/tests/test_api_ingest.py
git commit -m "$(cat <<'EOF'
Mark named API tests as the workflow reliability suite.

EOF
)"
```

---

### Task 10: Frontend types, API, rating control, and quality band

**Files:**
- Modify: `apps/frontend/src/types/dmcu.ts`
- Create: `apps/frontend/src/lib/api/quality.ts`
- Create: `apps/frontend/src/lib/queries/quality.ts`
- Modify: `apps/frontend/src/lib/api/reports.ts`
- Modify: `apps/frontend/src/lib/queries/reports.ts`
- Create: `apps/frontend/src/components/reports/report-rating.tsx`
- Create: `apps/frontend/src/components/reports/report-rating.test.tsx`
- Create: `apps/frontend/src/components/dmu/quality-band.tsx`
- Create: `apps/frontend/src/components/dmu/quality-band.test.tsx`
- Modify: `apps/frontend/src/components/reports/index.ts`
- Modify: `apps/frontend/src/routes/dmu/reports/$reportId.tsx`
- Modify: `apps/frontend/src/routes/dmu/index.tsx`
- Modify: `apps/frontend/src/components/capture/sitrep-draft-pane.tsx` — rating after issue.

**Interfaces:**
- Consumes: backend JSON shapes from Tasks 5–8.
- Produces: hooks `useQualitySummary`, `useRateReport`, `useVerdictClaim`; components `ReportRating`, `QualityBand`.

Mirror backend types in `dmcu.ts` (`QualitySummary`, `ThresholdStatus`, `QualityEval`, `ClaimRecord`, `RatingInput`). `ReportDetail.quality_eval?: QualityEval | null`.

`src/lib/api/quality.ts` fetchers only (no React Query): `getQualitySummary`, `patchClaimVerdict`. Do not add `postQualityEvent` — the backend already writes started/succeeded.

`src/lib/queries/quality.ts` keys `qualityKeys.summary()`, `qualityQueries.summary()`, `qualityMutations.rateReport` lives in reports queries because the resource is a report — `postReportRating` in `lib/api/reports.ts`, mutation in `lib/queries/reports.ts` that invalidates `reportKeys.detail(id)` and `qualityKeys.summary()`.

- [ ] **Step 1: Write failing component tests**

`report-rating.test.tsx`:

```tsx
// @vitest-environment jsdom
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { ReportRating } from './report-rating'

describe('ReportRating', () => {
  it('calls onRate with 5 when the last star is clicked', async () => {
    const onRate = vi.fn()
    render(<ReportRating onRate={onRate} />)
    const five = screen.getByRole('button', { name: 'Rate 5 out of 5' })
    await userEvent.click(five)
    expect(onRate).toHaveBeenCalledWith(5)
  })

  it('does not render when the report is still generating', () => {
    const { container } = render(
      <ReportRating onRate={() => undefined} disabled />,
    )
    expect(container.querySelectorAll('button').length).toBe(0)
  })
})
```

If `@testing-library/user-event` is not a dependency, use `five.click()` instead.

`quality-band.test.tsx`: render with a stub summary where completeness `actual: 0.99`, `met: true` and critical_numerical `actual: 0.5`, `met: false`. Assert the failing name is visible and the passing name is visible. Quiet empty: `scored_count === 0` shows “No scored reports yet.”

- [ ] **Step 2: Run to verify fail**

Run: `cd apps/frontend && pnpm test src/components/reports/report-rating.test.tsx src/components/dmu/quality-band.test.tsx`

Expected: FAIL module not found

- [ ] **Step 3: Implement components and wire pages**

`ReportRating`: five buttons `Rate {n} out of 5`. After success, parent shows the saved value. Disabled when `status` is `queued` | `running` | `failed`.

On `$reportId.tsx`: below the status row, `<ReportRating>` calling `useRateReport(reportId)`. If `quality_eval.claims.claims` has `auto_verdict === "pending_semantic"` and no `human_verdict`, show a compact list with Supported / Unsupported buttons calling `useVerdictClaim`.

On `dmu/index.tsx`: `useQuery(qualityQueries.summary())` and `<QualityBand summary={...} />` under `NeedsReviewBand`.

On `SitrepDraftPane`, when `filed && session.report_id`, render `<ReportRating>` against that report id (same hook as the DMU page).

Do **not** POST workflow events from the frontend. Task 6 records started/succeeded on the API; a second client write would double-count task completion.

- [ ] **Step 4: Run frontend tests and tsc**

Run:

```
cd apps/frontend && pnpm test && pnpm exec tsc --noEmit -p tsconfig.json
```

Expected: PASS, tsc clean

- [ ] **Step 5: Full backend pytest once more, then commit**

Run: `cd apps/backend && .venv/bin/python -m pytest`

```bash
git add apps/frontend/src/types/dmcu.ts apps/frontend/src/lib/api/quality.ts apps/frontend/src/lib/queries/quality.ts apps/frontend/src/lib/api/reports.ts apps/frontend/src/lib/queries/reports.ts apps/frontend/src/components/reports/report-rating.tsx apps/frontend/src/components/reports/report-rating.test.tsx apps/frontend/src/components/dmu/quality-band.tsx apps/frontend/src/components/dmu/quality-band.test.tsx apps/frontend/src/components/reports/index.ts apps/frontend/src/routes/dmu/reports/\$reportId.tsx apps/frontend/src/routes/dmu/index.tsx apps/frontend/src/components/capture/sitrep-draft-pane.tsx
git commit -m "$(cat <<'EOF'
Surface quality scores, ratings, and claim verdicts in the DMU UI.

EOF
)"
```

---

## Self-review

**Spec coverage:** faithfulness / unsupported / critical hallucination → Tasks 3, 4, 8; numerical 100% → Task 2 + 5; citation ≥95% → Task 2; completeness → Task 2; task completion → Task 6; workflow reliability → Task 9; usability → Tasks 7, 10. Predictive analytics explicitly omitted.

**Placeholders:** none remaining; word-number hyphenation decided (`ninety` not `ninety-nine`).

**Types:** `QualityEval`, `ClaimRecord.claim_id` as `cl001`, `NAMED_WORKFLOWS` strings reused as pytest marker args and `workflow_events.workflow`.

**Shippable slices:** Tasks 1–5 are a scorecard on reports; 6–7 ops tables; 8 human audit; 9 CI mark; 10 UI. Each slice is useful without the next.
