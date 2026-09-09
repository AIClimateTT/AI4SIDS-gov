# Quality KPI instrumentation — design

DMCU already generates reports from a deterministic fact table and machine-checks every digit in the narrative. This spec turns the PM quality thresholds (except predictive analytics) into measurable scores, persisted on each report and aggregated for operators.

**Out of scope:** predictive analytics (no models exist); Langfuse / OpenTelemetry / PostHog; LLM-as-judge; Playwright browser E2E. Named pytest API workflows are the system-reliability suite.

## Thresholds in scope

| KPI | Threshold | Unit |
|-----|-----------|------|
| Factual accuracy / faithfulness | ≥90% | material claims supported by cited facts |
| Critical numerical accuracy | 100% | critical figures in the report match `Fact.value` / breakdown |
| Citation / source accuracy | ≥95% | `[C00n]` instances license the associated statement |
| Report completeness | ≥95% | required metrics and layout sections represented |
| Critical hallucination rate | 0% | unsupported critical claims |
| Overall unsupported-claim rate | ≤5% | unsupported / material claims |
| User task completion (unaided) | ≥80% | named tasks finished without `assisted=true` |
| System workflow reliability | ≥95% | named pytest workflow tests passing |
| User usability / usefulness | ≥80% positive or mean ≥4/5 | ratings on issued reports |

## Operational definitions

**Critical metrics** (frozen in code): `casualty_summary`, `incident_count`, `homes_affected_count`, `estimated_damage_total`, `special_needs_count`, `incident_register` (injuries / deaths in `scope`). Same names on `sitreps` and `survey123`.

**Material claim:** a narrative sentence (checker split: `.!?` or newline) that contains a figure, a `[C00n]` marker, or a critical-metric assertion (including “no casualties / no deaths / no injuries”). Connective prose with none of those is not counted.

**Supported claim (automatic):** every number token in the sentence is licensed by the cited cid(s), and at least one valid cid is present. **Unsupported (automatic):** `invented_number`, `misattributed_number`, `missing_citation`, or a critical zero-event claim (“no deaths”) when no matching zero fact exists. **Pending semantic:** no digits, has a citation — counted in the denominator only after a human verdict.

**Authoritative source:** a cited fact with `verification` in `validated` / `mixed`. `pending` (WhatsApp) cannot support a faithfulness pass; those claims stay pending or unsupported.

**Completeness item:** (1) each `data_requirements` metric has ≥1 fact **or** a `FactTable.gaps` entry naming `{module}.{metric}`; (2) renderer layout headings that the facts justify (`Situation summary`, `Incidents`, … for filing; `## Data Tables` / `## Data Gaps` / `## Citation Appendix` for narrative when applicable). A documented gap counts as present. Capture `_OMIT_WHEN_ZERO` omissions are not incomplete.

**Critical figure match:** if a critical fact’s value (or breakdown / register casualty) appears as a number token in `markdown`, that token must equal the fact. Omitted zero facts are not failures. Any `invented_number` / `misattributed_number` on a critical fact is a numerical fail and a critical hallucination.

**Named user tasks:** `corp_capture_issue`, `dmu_generate_report`, `whatsapp_briefing`, `survey123_ingest`. Success = the backend mutation finished (report `ok` or `needs_review` counts as generated). `assisted` defaults false; an operator PATCH sets true.

**Named test workflows:** pytest mark `workflow` with those same ids (plus `corp_capture_preview` if a distinct existing test covers preview). Pass rate = passing marked tests / collected marked tests.

**Usability:** integer 1–5 on a report. Positive = 4 or 5.

## Architecture

Pure scoring functions take `Template`, `FactTable`, narrative, markdown, and `CitationCheckResult` and return a `QualityEval` JSON document. `narrate_fact_table` (used by batch reports and corp sitrep issue) persists it on `reports.quality_eval`.

```
generate / issue
  fact_table → llm → check_citations → score_quality → persist
```

No new tracing vendor. The report row is the replay store. Claim human verdicts PATCH the stored `quality_eval.claims`.

Workflow events and ratings are separate tables, not mixed into `violations`.

## Data

`reports.quality_eval` JSON nullable. Rows generated after this change always have it. Summary scoring skips null (pre-change rows) or a CLI rescores them.

`workflow_events`: id, workflow, step, outcome (`started` \| `succeeded` \| `failed`), subject_id, user_id nullable, assisted bool default false, created_at.

`report_ratings`: id, report_id FK, user_id, rating 1–5, comment nullable, created_at. Unique (report_id, user_id).

## HTTP

- `GET /quality/summary` — aggregates `QualityEval` rates, workflow completion, rating mean / % positive, vs thresholds.
- `POST /quality/events` — optional client `started`; server also writes on mutations.
- `PATCH /quality/events/{id}` — set `assisted`.
- `POST /reports/{id}/rating` — authenticated.
- `PATCH /reports/{id}/claims/{claim_id}` — authenticated DMU, body `{ "verdict": "supported" | "unsupported" }`.

## Frontend

- 1–5 control on DMU report detail and corp issued sitrep (when a `report_id` exists).
- Quality band on `/dmu` overview from `GET /quality/summary` (rates vs thresholds, not raw counts only).
- Workflow `started` / `succeeded` / `failed` are written by the API handlers, not the browser, so task-completion rates are not double-counted.

## Constraints

- Numbers remain SQL-derived. Scoring must not call an LLM.
- Do not weaken `check_citations`: every invented digit still fails. Word-number detection only **adds** tokens.
- `quality_eval` must not be sent to the LLM. Strip it the same way `record_ids` are stripped from the LLM copy if it ever lands on `FactTable` (it must not).
- Frontend tests: no `toBeInTheDocument`; jsdom tests start with `// @vitest-environment jsdom`.
- Backend tests: `cd apps/backend && .venv/bin/python -m pytest`.
- Predictive analytics stays unimplemented.
