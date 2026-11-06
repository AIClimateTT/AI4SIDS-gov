# Sitrep Baseline Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove WhatsApp and the pluggable-module machinery. Make reports A (corporation sitrep) and B (minister sitrep) render in the stakeholder baseline formats from the sitrep store alone. Make report C (Survey123, verified) a short report generated directly from the Field data page. Give the DMU a table view of all corporation incidents and situation logs. Require a login on every data endpoint.

**Architecture:** The three-report model in `docs/reporting-flow.md` §2: A and B read only the sitrep store; C reads only the field store. The capture → sitrep store path stays. A and B become deterministic renders of stored data, with no LLM narration. Report C keeps full LLM narration around computed numbers, citation-checked. Capture keeps its LLM. The corp `filing` layout is reworked to the baseline. A new `ministerial` layout renders one section per corporation from a new `corporation_status` metric. The minister template stops reading Survey123. Survey123 keeps its CSV upload in this plan. The ArcGIS API pull, and the later hand-off of corporation incidents into Survey123, get their own plan.

**Already done outside this plan (2026-11-02):** the citation checker now accepts typographic dashes in dates and ignores numbered-list markers (`docs/reporting-flow.md` §6).

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, pytest (`apps/backend`, run with `uv run pytest`); React + TanStack Router + Vitest (`apps/frontend`, run with `npm test`).

**Spec:** `docs/reporting-flow.md` (§4.1 corp format, §4.2 minister format). The baseline documents are in `docs/examples/`.

## Global Constraints

- Survey123 code and its CSV upload stay as they are. No ArcGIS API work.
- No report mixes the two sources: A and B use only `sitreps` metrics; C uses only `survey123` metrics.
- The minister report reads corp **data** only, never corp report text (invariant from `2026-07-26-corp-sitrep-realignment-design.md`).
- No number in either report may come from anywhere but a stored column (`quantity`, counts of stored rows). Officer and Ministry prose (overview, present activity, alert detail, ministry response) renders verbatim and uncited.
- Times shown in reports are Trinidad local time via `app.core.localtime.to_local`, formatted `"%-I:%M %p on %d/%m/%Y"` lowercased am/pm (e.g. `4:00 pm on 30/06/2023`).
- Templates are YAML files in `app/templates/definitions/`, changed only in code by the developer. Each file has a `version:`, bumped when its content changes. Each report records the `template` and `template_version` that created it.
- The 14 corporations and their display names come from `CORPORATION_LABELS` in `app/modules/survey123/normalize.py`, in that dict's order.
- The issued document (`final_markdown`) never contains `[Cxxx]` markers, Cite columns, or a data-gaps section. The draft (`markdown`) keeps them.

## Review Focus

1. **A corp with a submission in the window but zero logs and zero incidents.** It must render its heading with "No reports at this time.", the same as a corp that never filed. Test in Task 6.
2. **A corp with several submissions in the window.** Only the latest `as_at` is used. Older submissions' logs must not leak into its section. Test in Task 5.
3. **A submission whose `as_at` is outside the window but whose event is still open.** It is excluded. The window filters `Submission.as_at`, not the event. Test in Task 5.
4. **Reports issued before this work.** They keep their stored markdown and template version; only new generations use the new YAML. Test in Task 3 (a template with sections still calls the LLM).
5. **Removing the `whatsapp_drafts` table on a database that has rows.** The downgrade must recreate the table (without data), and the upgrade must not fail on SQLite. Test in Task 1.

---

## File Structure

| File | Change | Responsibility |
|---|---|---|
| `app/modules/whatsapp/`, `app/api/whatsapp.py`, `app/jobs/whatsapp.py`, `tests/test_*whatsapp*.py` | delete | — |
| `app/modules/capture/model_json.py` | create | `parse_model_json`, moved out of `whatsapp/extract.py` |
| `alembic/versions/<new>_drop_whatsapp_drafts.py` | create | drop `whatsapp_drafts` |
| `app/core/engine.py` | modify | skip the LLM when a template has no `output_sections` |
| `app/modules/sitreps/models.py` | modify | `Submission.alert_detail`; `adverse_weather` hazard |
| `alembic/versions/<new>_submission_alert_detail.py` | create | add column |
| `app/modules/capture/sitrep.py` | modify | baseline header block |
| `app/core/renderer.py` | modify | baseline `filing` layout; new `render_ministerial` |
| `app/modules/sitreps/minister_metrics.py` | create | `corporation_status` metric |
| `app/core/contracts.py` | modify | `layout` gains `"ministerial"`; `TemplateParam.multiline` |
| `app/templates/definitions/*.yaml` | modify | corp and minister templates |
| `apps/frontend/src/...whatsapp...` | delete | — |
| `apps/frontend/src/routes/dmu/reports/new.tsx` | modify | textarea for multiline params |

---

### Task 1: Remove WhatsApp from the backend

**Files:**
- Create: `apps/backend/app/modules/capture/model_json.py`, `apps/backend/alembic/versions/<rev>_drop_whatsapp_drafts.py`, `apps/backend/tests/test_capture_model_json.py`
- Modify: `app/modules/capture/turn.py:27`, `app/__init__.py:12,48`, `app/jobs/tasks.py`, `app/jobs/queue.py`, `app/core/llm.py` (`_fake_whatsapp_turn` and its branch, around lines 54 and 124–142), `app/quality/denominators.py:50`, `alembic/env.py:12`
- Delete: `app/modules/whatsapp/`, `app/api/whatsapp.py`, `app/jobs/whatsapp.py`, `tests/test_api_whatsapp.py`, `tests/test_whatsapp_*.py`

**Interfaces:**
- Produces: `app.modules.capture.model_json.parse_model_json(raw: str) -> dict`, the same behaviour as today's `whatsapp/extract.py:247`, with `_FENCE_RE` moved alongside it.

- [ ] **Step 1: Write failing tests** in `tests/test_capture_model_json.py`:
  - `test_parse_model_json_strips_fences`: `parse_model_json('```json\n{"a": 1}\n```') == {"a": 1}`
  - `test_parse_model_json_rejects_non_object`: `pytest.raises(ValueError)` on `"[1]"`
  - `test_drop_whatsapp_migration_round_trips(tmp_path)`: on a SQLite file, `alembic upgrade head`, then `downgrade -1`, then `upgrade head`, each without error. After the final upgrade, `inspect(engine).has_table("whatsapp_drafts") is False`.
- [ ] **Step 2: Run** `uv run pytest tests/test_capture_model_json.py -v`. Expected: FAIL (module not found).
- [ ] **Step 3: Move `parse_model_json`** into `capture/model_json.py` and point `capture/turn.py` at it.
- [ ] **Step 4: Delete the WhatsApp files** listed above and remove every reference in the modified files. Write the migration: `down_revision = "d4c8a2f61b35"`; `upgrade` drops `whatsapp_drafts`; `downgrade` recreates it from the columns in today's `app/modules/whatsapp/models.py` (copy them into the migration before deleting the model).
- [ ] **Step 5: Verify.** `grep -rni whatsapp app alembic/env.py tests` prints nothing except migration files. `uv run pytest` passes.
- [ ] **Step 6: Commit** `refactor: remove WhatsApp intake; capture replaces it`

### Task 2: Remove WhatsApp from the frontend

**Files:**
- Delete: `src/components/whatsapp/`, `src/routes/dmu/whatsapp.tsx`, `src/lib/whatsapp-paths.ts(.test.ts)`, `src/lib/queries/whatsapp.ts`, `src/lib/api/whatsapp.ts`
- Modify: `src/components/app-sidebar.tsx:67` (drop the WhatsApp nav item), `src/components/app-sidebar.test.tsx`, `src/types/dmcu.ts` (drop WhatsApp types), `src/routeTree.gen.ts` (regenerate; don't hand-edit)

- [ ] **Step 1: Update the sidebar test** to assert no link has `href="/dmu/whatsapp"`. Run `npm test -- app-sidebar`. Expected: FAIL.
- [ ] **Step 2: Delete the files and references above**, then regenerate the route tree with the project's router codegen (`npm run build` triggers the TanStack plugin).
- [ ] **Step 3: Verify.** `grep -rni whatsapp src` prints nothing. `npm test` and `npx tsc --noEmit` pass.
- [ ] **Step 4: Commit** `refactor(frontend): remove WhatsApp tab`

### Task 3: Prose-free templates skip the LLM

**Files:**
- Modify: `apps/backend/app/core/engine.py` (`narrate_fact_table`)
- Test: `apps/backend/tests/test_engine_generate.py`

**Interfaces:**
- Produces: when `template.narration.output_sections == []`, `narrate_fact_table` makes **no** `llm_client.generate` call. It sets `narrative = ""`, `status = "ok"`, `violations = []`, and still renders `markdown`/`final_markdown` and runs `score_quality`.

- [ ] **Step 1: Write failing tests:**
  - `test_no_output_sections_skips_llm`: a client whose `generate` raises `AssertionError`. Calling it with `NarrationConfig.of(output_sections=[])` returns `status == "ok"` and `narrative == ""`.
  - `test_output_sections_still_call_llm`: a recording fake with `output_sections=["connective_prose"]` is called once (this covers Review Focus 4).
- [ ] **Step 2: Run** `uv run pytest tests/test_engine_generate.py -v`. Expected: the first test FAILS.
- [ ] **Step 3: Add the early branch** in `narrate_fact_table`, using `CitationCheckResult(passed=True, violations=[])` from `app/core/citation_check.py` as the result.
- [ ] **Step 4: Run** the tests. Expected: PASS. If `score_quality` throws on an empty narrative, guard it there and add a test for that case.
- [ ] **Step 5: Commit** `feat(engine): skip narration for templates with no prose sections`

### Task 4: Alert detail and report number reach the corp filing

**Files:**
- Modify: `app/modules/sitreps/models.py` (`Submission.alert_detail: Mapped[str | None]`, Text, nullable; add `"adverse_weather"` first in `HAZARD_TYPES`), `app/modules/sitreps/ingest.py` (`ingest_submission(..., alert_detail: str | None = None)`, stored on the submission), `app/modules/capture/schemas.py` (`CaptureWorkingSet.alert_detail: str | None = None`), `app/modules/capture/provenance.py:14` (add `"alert_detail"` to `SESSION_FIELDS`), `app/modules/capture/prompt.py` (add `"alert_detail": "<officer's own words for the alert, e.g. 'Localized Flooding Alert #2 – Yellow Level – extended until Mon 19th May 6pm', or null>"` to the schema, and a rule that it must be the officer's words), the call site that passes working-set fields into `ingest_submission` (`capture/file.py` / `api/capture.py`), and the frontend hazard-type list (find it with `grep -rn "'landslide'" apps/frontend/src`)
- Create: `alembic/versions/<rev>_submission_alert_detail.py` (down_revision = Task 1's revision)
- Test: `tests/test_sitreps_submission_ingest.py`, `tests/test_capture_provenance.py` (or the existing provenance test file)

- [ ] **Step 1: Write failing tests:**
  - `test_ingest_submission_stores_alert_detail`: `ingest_submission(..., alert_detail="Flood Alert #2 – Yellow")` gives `submission.alert_detail == "Flood Alert #2 – Yellow"`.
  - `test_alert_detail_is_a_pinned_session_field`: a manual edit to `alert_detail` survives an LLM turn that returns a different value (mirror the existing `present_activity` pin test).
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement** the column, migration, schema field, prompt line, and pass-through.
- [ ] **Step 4: Run** `uv run pytest`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(sitreps): capture the officer's alert wording and adverse-weather hazard`

### Task 5: `corporation_status` metric for the minister report

**Files:**
- Create: `app/modules/sitreps/minister_metrics.py`, `tests/test_sitreps_minister_metrics.py`
- Modify: `app/modules/sitreps/module.py` (dispatch and list the new metric alongside `LOG_METRIC_*`)

**Interfaces:**
- Produces: `corporation_status(params: dict, session: Session | None = None, rows=None) -> list[Fact]`, with params `date_from` and `date_to` (ISO dates, both optional, inclusive, compared on `to_local(Submission.as_at).date()`).
  - For each corporation, select its submission with the greatest `as_at` in the window. Emit, in order:
    - One `Fact(metric="corporation_status", value=<statement>, unit=None, scope={"corporation", "as_at" (ISO), "submission_id", "kind": "log"})` per `SituationLog` row of that submission. `value` is `statement` verbatim.
    - If that submission has an `event_id` and the event has incidents: one `Fact(metric="corporation_status", value=<incident count>, unit="incidents", scope={..., "kind": "incidents"}, breakdown={incident_type: count})`, counting `SitrepIncident` rows with that `event_id` (cumulative for the event).
  - Each fact gets `verification="pending"` and a citation via `build_citation(...)` whose `record_ids` are the rows' `record_ref`.
  - Corporations with no submission in the window emit nothing. The renderer names them (Task 6).
- `MetricSpec(name="corporation_status", module="sitreps", description="Latest in-window submission per corporation: its situation-log statements and its event's incident counts by type.", params_schema=METRIC_PARAMS_SCHEMA)`

- [ ] **Step 1: Write failing tests** (DB set up like `tests/test_sitrep_log_metrics.py:69`):
  - `test_uses_latest_submission_in_window`: Arima has submissions at 10:00 ("Sandbags filled") and 16:00 ("CERT on standby"). Only "CERT on standby" is returned (Review Focus 2).
  - `test_excludes_submission_outside_window`: a submission on 2026-08-20 with `date_from="2026-08-21"` returns `[]` (Review Focus 3).
  - `test_incident_breakdown_is_cumulative_for_event`: 2 landslides on submission 1 and 1 flood on submission 2, same event. The latest gives `value == 3` and `breakdown == {"landslide": 2, "flooding_": 1}` (use whatever slugs `normalize_corp_incident_type` produces).
  - `test_statement_rendered_verbatim`: `value == "200 sandbags available for distribution"` even when the row also has `quantity=200`.
- [ ] **Step 2: Run** `uv run pytest tests/test_sitreps_minister_metrics.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** in `minister_metrics.py` and register it in `SitrepModule.list_metrics` / `run_metric`.
- [ ] **Step 4: Run.** Expected: PASS. Also run `uv run pytest tests/test_sitreps_module.py`.
- [ ] **Step 5: Commit** `feat(sitreps): corporation_status metric for the minister roll-up`

### Task 6: Ministerial layout and minister template

**Files:**
- Modify: `app/core/contracts.py` (`RenderConfig.layout: Literal["narrative", "filing", "ministerial"]`; `TemplateParam.multiline: bool = False`), `app/core/renderer.py` (add `render_ministerial`, and dispatch it in `render_report`), `app/templates/definitions/minister_situation_report.yaml`
- Test: `tests/test_renderer_ministerial.py`; update `tests/test_engine_generate.py`, `tests/test_template_store.py`, `tests/test_cli_generate.py`, and `tests/test_api_quality.py` where they assert the old minister template's metrics or sections

**Interfaces:**
- Consumes: `corporation_status` facts (Task 5); prose-free narration (Task 3).
- Produces: `render_ministerial(template: Template, fact_table: FactTable, *, include_citations: bool = True) -> str`. Template params, all strings:

| param | required | multiline | renders as |
|---|---|---|---|
| `date_from`, `date_to` | yes | no | window only (not printed) |
| `as_at` | yes | no | `**As at:** 3:00 pm on 05/05/2023` (Trinidad local; param is ISO datetime) |
| `hazard` | no | no | title `{HAZARD.upper()} SITUATION REPORT`; blank → `SITUATION REPORT` |
| `present_activity` | no | no | `**Present Activity:** …` |
| `alert_level` | no | no | `**Alert Level:** …` verbatim |
| `situation_overview` | no | yes | `## Situation Overview` + verbatim text |
| `ministry_response` | no | yes | `## Response from the Ministry of Rural Development and Local Government` + verbatim text |

Layout, in order:
1. `# {title}`
2. Header lines, one paragraph each. `**Location:** Ministry of Rural Development and Local Government, Kent House` is fixed text.
3. Overview.
4. For each key of `CORPORATION_LABELS`, in order:
   - `## {label}`
   - its `kind="log"` facts as `- {value}` bullets;
   - then, if present, an `- Incidents reported: {Type} {n}, {Type} {n}` bullet from the `kind="incidents"` breakdown, using `_humanize` for types and descending counts;
   - `[Cxxx]` after each bullet only when `include_citations`.
   - A corp with no facts gets the single bullet `- No reports at this time.`
5. Ministry response. Omit the heading when blank.
6. `END OF REPORT`.

Minister YAML:
- `data_requirements` is exactly one entry: `{module: sitreps, metric: corporation_status, params: {date_from: "{date_from}", date_to: "{date_to}"}}`.
- `narration.output_sections: []`; keep the `identity`; set `skills.compose` to `"Not narrated; rendered from data."`.
- `render: {layout: ministerial, include_citation_appendix: false}`.
- The description must drop Survey123.

- [ ] **Step 1: Write failing tests** in `tests/test_renderer_ministerial.py`:
  - `test_every_corporation_has_a_section`: `len(re.findall(r"^## ", md, re.M))` equals `len(CORPORATION_LABELS)` plus 1 for the overview (with no ministry response).
  - `test_silent_corporation_reads_no_reports`: no facts for Siparia → `"## Siparia Regional Corporation\n\n- No reports at this time."` appears. A corp whose only submission had zero logs and zero incidents produces the same text (Review Focus 1).
  - `test_log_statements_are_bullets_verbatim`
  - `test_incident_line_orders_by_count`: breakdown `{"landslide": 2, "flooding_": 4}` → `- Incidents reported: Flooding 4, Landslide 2`
  - `test_final_has_no_citations`: with `include_citations=False`, no `[C` appears anywhere.
  - `test_ends_with_end_of_report`
  - `test_minister_template_reads_no_survey123`: load the YAML and assert every `data_requirements[].module == "sitreps"`.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement** the contract changes, the renderer, and the YAML.
- [ ] **Step 4: Run** `uv run pytest`. Fix the listed tests that pinned the old minister template's metrics or sections.
- [ ] **Step 5: Commit** `feat(reports): minister sitrep in the baseline per-corporation format`

### Task 7: Corp filing in the baseline format

**Files:**
- Modify: `app/modules/capture/sitrep.py` (`sitrep_preamble`, `generate_working_set_sitrep`), `app/api/capture.py` (`_event_title` → also return the event's `hazard_type`, and pass `report_number = next_sequence_no(db, row.corporation, row.event_id)` from `app/modules/sitreps/store.py:44`), `app/core/renderer.py` (`render_filing`, `_document_title` for `filing`), `app/templates/definitions/corp_situation_report.yaml`
- Test: `tests/test_corp_filing_golden.py` (rewrite expected output), `tests/test_capture_sitrep.py`, `tests/test_renderer.py` (filing cases)

**Interfaces:**
- `generate_working_set_sitrep(working, *, corporation, event_id, event_title, hazard_type: str | None, report_number: int | None, template, llm_client, request_id)`. `hazard_type` and `report_number` are put into `FactTable.params` so the renderer can read them.
- `sitrep_preamble(*, corporation_label: str, report_number: int | None, as_at: datetime, present_activity: str | None, alert_level: str, alert_detail: str | None, situation_overview: str | None) -> str`

Rendered order (§4.1):
1. Title `# {HAZARD_TITLES[hazard_type]} SITUATION REPORT #{report_number}`.
   - `HAZARD_TITLES = {"adverse_weather": "ADVERSE WEATHER", "flood": "FLOOD", "landslide": "LANDSLIDE", "wind": "HIGH WIND", "fire": "FIRE", "other": ""}`
   - Drop ` #n` when `report_number` is None, and drop the hazard word when it's blank.
2. Header paragraphs: `**As at:** …`, `**Location:** {corporation_label}`, `**Present Activity:** …` (omitted if blank), `**Alert Level:** {alert_detail or alert_level title-cased}`.
3. `## Situation Overview` + the officer text, omitted if blank.
4. `## Situation Summary`: the existing Type | Count table.
5. `## Disaster Relief Distribution Summary`: `relief_stock_summary` facts whose `scope["category"] == "relief_distributed"`, as Item | Quantity | Unit.
6. `## Resources`: the remaining `relief_stock_summary` facts, as Item | Quantity | Unit | Status.
7. `## Summary of Activities`: the `activity_log` bullets.
8. `## Incidents`: No. | Date | Location | Type | Description | Injuries | Deaths | Action Taken. No. counts from 1; Location is `_place`; Description is `summary`. Empty columns are still dropped by `_md_table`.
9. `## Data Gaps`, **draft only** (`include_citations=True`). Removed from the issued document.
10. Closing line: `No further reports to be submitted.` when `alert_level == "discontinued"`, otherwise `END OF REPORT`.

Corp YAML: `narration.output_sections: []`. Keep the `skills.capture` text as is. Set `skills.compose` to `"Not narrated; rendered from data."`.

- [ ] **Step 1: Rewrite `tests/test_corp_filing_golden.py`** to the order above. Use the existing Arima working set plus `alert_detail="Flood Alert #1 – Yellow Level"`, `hazard_type="adverse_weather"`, `report_number=2`. Assert:
  - final markdown starts with `# ADVERSE WEATHER SITUATION REPORT #2`;
  - section headings appear in the order above;
  - the final contains no `Data Gaps` and no `Information not yet available`;
  - it ends with `END OF REPORT`;
  - a `discontinued` variant ends with `No further reports to be submitted.`;
  - relief rows with category `relief_distributed` appear under the distribution heading and not under Resources;
  - the incident table's first data cell is `1`;
  - the fake LLM is not called.
- [ ] **Step 2: Run** `uv run pytest tests/test_corp_filing_golden.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** the preamble, the renderer, the call-site arguments, and the YAML.
- [ ] **Step 4: Run** `uv run pytest`. Update `test_capture_sitrep.py` and `test_api_capture.py` assertions that pinned the old `**Event:**` header or the connective prose. Run `npm test` too, since the draft pane renders this markdown.
- [ ] **Step 5: Commit** `feat(capture): corp sitrep in the baseline format, no generated prose`

### Task 8: Multi-line params on the report form

**Files:**
- Modify: `apps/frontend/src/routes/dmu/reports/new.tsx`, `apps/frontend/src/lib/api/templates.ts` (type gains `multiline?: boolean`), `app/api/templates.py` if its response model lists param fields explicitly
- Test: the existing `new.tsx` route test or a new `reports-new.test.tsx`

- [ ] **Step 1: Write a failing test:** for a template whose param `situation_overview` has `multiline: true`, the form renders a `textarea` named `situation_overview` and an `input` for `as_at`.
- [ ] **Step 2: Run** `npm test -- reports`. Expected: FAIL.
- [ ] **Step 3: Implement.** Render a `Textarea` from the shadcn components already used in `src/components/ui` when `param.multiline`.
- [ ] **Step 4: Run** `npm test`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(reports): multi-line inputs for Ministry overview and response`

### Task 9: Ship the templates and close out docs

**Files:**
- Modify: `docs/superpowers/specs/2026-07-26-corp-sitrep-realignment-design.md` (add a line under Decision 6: "Superseded 2026-10-29 by `docs/reporting-flow.md`"), `apps/backend/scripts/seed_demo.py` (drop WhatsApp seeding if any; confirm it imports the new template versions), `docs/outstanding-issues.md` (remove WhatsApp items)

- [ ] **Step 1: Confirm** both changed YAML files have a bumped `version:`.
- [ ] **Step 2: End-to-end check** with `uv run python scripts/seed_demo.py`:
  - issue one corp sitrep through capture, and generate a minister report for its date;
  - read both `final_markdown`s against `docs/examples/` §4.1 and §4.2 of the spec;
  - expect no `[C` markers, all 14 corporation headings, and "No reports at this time." for the silent corps.
- [ ] **Step 3: Run** `uv run pytest` and `npm test`. Both must pass.
- [ ] **Step 4: Commit** `docs: record the agreed reporting flow; supersede Survey123 corroboration`

### Task 10: Report C generated directly from the Field data page

**Why:** the stakeholder uploaded 2026 Survey123 data and could generate only `minister_situation_report`. Its main figures come from the empty sitrep store, so the report said "zero incidents" (`docs/reporting-flow.md` §6). `field_data_region_review` can't replace it: it requires one corporation, and its wording calls the data raw and unverified.

**Files:**
- Create: `apps/backend/app/templates/definitions/survey123_summary.yaml`, `apps/backend/tests/test_survey123_summary_template.py`
- Modify: `apps/backend/app/modules/survey123/metrics.py` (`incidents_by_corporation`), `apps/frontend/src/routes/dmu/field-data.tsx`
- Test: the `field-data` route test (create if absent)

**Interfaces:**
- Template `survey123_summary`, title "Survey123 Summary Report".
  - Params: `date_from` and `date_to` required; `corporation` optional.
  - Metrics, all `module: survey123`: `incident_count`, `incidents_by_corporation`, `homes_affected_count`, `casualty_summary`, `relief_actions_summary`, `estimated_damage_total`.
  - `layout: narrative`.
  - `output_sections: [overview, by_corporation, impact_and_relief, damage_caveat]`.
  - Compose rule: the records were verified by field staff; cite every figure; keep to one page; include the coverage caveat on damage.
- An empty window adds this gap to the fact: `"No Survey123 records found for this period. Confirm data for it has been uploaded."` Use the `SITREP` label for the sitrep model, through `source_label_of(model)`. The gap is what stops an empty window reading as "nothing happened".

- [ ] **Step 1: Write failing tests:**
  - `test_template_reads_only_survey123`: every `data_requirements[].module == "survey123"`.
  - `test_empty_window_reports_a_gap_not_just_zero`: no rows in the window → `incidents_by_corporation` returns `value == 0` with the gap text above.
  - Frontend: Field data renders date inputs, an optional corporation select and a "Generate report" button. Submitting posts `{template: "survey123_summary", params}` to `/reports` and navigates to the new report.
- [ ] **Step 2: Run** `uv run pytest tests/test_survey123_summary_template.py -v` and `npm test -- field-data`. Expected: FAIL.
- [ ] **Step 3: Implement** the YAML, the gap, and the form. Default the dates to 1 January of the current year through today. The Reports page's Generate form stays minister-only.
- [ ] **Step 4: Verify end to end** with a real LLM. Upload `apps/backend/survey_0.csv`, after filtering out blank-validation rows (Task 11), and generate for 2026-01-01 to 2026-11-02. Expected: the report states 719 incidents and has no citation violations.
- [ ] **Step 5: Commit** `feat(reports): generate a Survey123 summary directly from Field data`

### Task 11: Reject a Survey123 file with any unvalidated row

**Why:** the `Validated/NotValidated` column must be filled. A blank means the export was filtered wrongly, so the whole file is rejected (stakeholder, 2026-11-05). Today a blank is stored as `pending` and silently left out of reports. `survey_0.csv` has 834 such rows.

**Files:**
- Modify: `apps/backend/app/modules/survey123/ingest.py` (`REQUIRED_COLUMNS`, `ingest_csv`)
- Test: `apps/backend/tests/test_survey123_ingest.py` (or the existing ingest test file), and every fixture CSV that relies on a blank value

**Interfaces:**
- `ingest_csv` raises `IngestFormatError` **before any row is written** when any row's value, stripped and lowercased, isn't `validated`. This also rejects `NotValidated`. The message is exactly: `"{n} row(s) are not marked Validated (first: row {row}). Filter the Survey123 export to validated records and upload again. Nothing was saved."`
- A file without the column is rejected through `REQUIRED_COLUMNS`.
- Rows already stored as `pending` stay as they are and stay excluded from reports. No migration.

- [ ] **Step 1: Write failing tests:**
  - `test_blank_validation_rejects_whole_file`: three rows, the third blank → raises, message contains `1 row(s)` and `row 4`; the table has 0 rows.
  - `test_not_validated_value_rejects_whole_file`
  - `test_missing_validation_column_rejects_file`
  - `test_upload_returns_400_with_the_message`, via the API.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.** Check after the header check and before the first `session` call. Keep the existing per-cell date errors.
- [ ] **Step 4: Run** `uv run pytest`. Update fixtures and tests that uploaded blanks to exercise `pending`; set those rows directly in the DB instead.
- [ ] **Step 5: Commit** `fix(ingest): reject a Survey123 file containing unvalidated rows`

### Task 12: DMU table of all incidents and situation logs

**Why:** the DMU needs to see every corporation's records, all together and per filed report.

**Files:**
- Create: `apps/frontend/src/routes/dmu/records.tsx`, `apps/frontend/src/lib/api/situation-logs.ts`, `apps/frontend/src/lib/queries/situation-logs.ts`, `apps/backend/app/api/situation_logs.py`, `apps/backend/tests/test_api_situation_logs.py`
- Modify: `apps/backend/app/modules/incident_list.py` and `app/api/incidents.py` (filters), `app/__init__.py` (router), `apps/frontend/src/components/app-sidebar.tsx`, `src/routes/dmu/corporations/$corporation.tsx` (link each filing), `src/routes/dmu/field-data.tsx` (Survey123 rows only; drop the source filter)

**Interfaces:**
- `GET /incidents` gains `corporation: str | None` and `submission_id: int | None`. `submission_id` applies only to corporation rows, and it leaves Survey123 rows out.
- `GET /situation-logs?corporation&submission_id&q&page&page_size` returns `{items, total}`. Each item has `id, corporation, submission_id, as_at, event_title, category, statement, item, quantity, unit, status`. Newest `as_at` first; `page_size` is capped at 100.
- Route `/dmu/records`, nav label "Incidents & logs" under Operations, visible to DMU and admin. It has tabs **Incidents** and **Situation logs**, a corporation select, a filing select (filled from `submissionQueries.list`, enabled once a corporation is chosen) and search. All of these are held in URL search params. It always requests `source=sitreps`.

- [ ] **Step 1: Write failing tests:**
  - `test_situation_logs_filter_by_corporation_and_submission`
  - `test_situation_logs_paginate_newest_first`
  - `test_incidents_filter_by_submission_excludes_survey123`
  - Frontend: choosing a corporation refetches both tabs; `/dmu/records?corporation=x&submission_id=y` opens with both filters set.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.** On the filing select, show this hint: "Incidents appear under the filing that last updated them." Re-filing a row moves its `submission_id` (`sitreps/ingest.py:209`), so an older filing's incident list shrinks. Situation logs never move. Each row of the corporation page's filing table links to `/dmu/records` with both filters set, and to its issued report through the existing `resolveSitrepHref`.
- [ ] **Step 4: Run** `uv run pytest` and `npm test`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(dmu): table of corporation incidents and situation logs, per filing`

### Task 13: Remove the module concept

**Why:** there are now exactly two fixed sources. Sitreps hold unvalidated corporation incidents and logs; Survey123 goes straight to its own report. A plug-in registry, MCP transport and metric picker have nothing left to plug in.

**Keeps, deliberately:**
- The `app/modules/...` folder paths. Renaming them is hundreds of import changes for no behaviour.
- `DataRequirement.module`, `Citation.module` and `__module_name__`, as source labels. Stored template versions and issued reports carry these and must still load.

**Files:**
- Delete: `app/core/registry.py`, `app/core/mcp_module.py`, `app/mcp_server/`, `app/modules/sitreps/module.py`, `app/modules/survey123/module.py`, the `/modules` route in `app/api/meta.py`, `settings.survey123_transport` in `app/config.py`, the MCP dependency in `pyproject.toml` if nothing else uses it, and their tests. Frontend: `src/routes/dmu/admin/modules.tsx`, `src/lib/api/modules.ts`, `src/lib/queries/modules.ts`, the sidebar item, and the metric picker in `src/routes/dmu/reports/new.tsx`.
- Create: `app/core/metrics.py`, `tests/test_core_metrics.py`
- Modify: `app/core/engine.py:75`, `app/core/template_store.py:32-36`, `app/__init__.py`, `app/api/ingest.py`, `cli.py`, `scripts/seed_demo.py`, and `app/api/reports.py` (drop the `data_requirements` request override; keep the stored column for existing reports)

**Interfaces:**
- `metric_names(source: str) -> set[str]`
- `run_metric(source: str, name: str, params: dict, session: Session) -> list[Fact]`. `source` is `"sitreps"` or `"survey123"`; anything else raises `ValueError`. It keeps today's rule that a stored template naming `data_coverage` on sitreps returns `[]` instead of crashing.
- Survey123 upload moves from `POST /ingest/{module_name}` to `POST /field-data/upload`, with the same response body.

- [ ] **Step 1: Write failing tests:**
  - `test_run_metric_dispatches_each_source`
  - `test_unknown_source_raises`
  - `test_stored_template_with_data_coverage_on_sitreps_still_generates`
  - `test_field_data_upload_route_ingests`
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement `app/core/metrics.py`,** moving the dispatch and `LOG_METRIC_*`/`corporation_status` wiring out of `SitrepModule`. Point the engine, template store, ingest API, CLI and seed script at it, then delete the files listed above.
- [ ] **Step 4: Verify.** `grep -rnE "get_module|list_modules|McpDataModule|survey123_transport" apps/backend/app apps/backend/cli.py` prints nothing. `uv run pytest`, `npm test` and `npx tsc --noEmit` pass.
- [ ] **Step 5: Commit** `refactor: replace the module registry with two fixed report sources`

### Task 14: Remove the quality section from the DMU dashboard

**Files:**
- Modify: `apps/frontend/src/routes/dmu/index.tsx` (remove `OverviewQualityBand` and its imports)
- Delete: `src/components/dmu/quality-band.tsx` and `quality-band.test.tsx`, once nothing imports them
- Test: the dashboard route test (create if absent)

The Admin → Quality page stays. `NeedsReviewBand` also stays: it's a call to action, not a quality score.

- [ ] **Step 1: Write a failing test:** the dashboard renders no quality band and makes no request for the quality summary.
- [ ] **Step 2: Run** `npm test -- dmu`. Expected: FAIL.
- [ ] **Step 3: Implement.** Keep `useQualitySummary` if `admin/quality.tsx` still uses it.
- [ ] **Step 4: Run** `npm test` and `npx tsc --noEmit`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(dmu): remove the quality band from the dashboard`

### Task 15: Templates become YAML files only

**Decided by Devon, 2026-11-05.** The stakeholder gives feedback and the developer (Devon is the only one) adjusts templates directly in code. There is no page and no database table. This replaces the July design of editable, DB-versioned templates; git is the version history.

**Files:**
- Create: `apps/backend/app/core/template_catalog.py`, `apps/backend/alembic/versions/<rev>_drop_report_templates.py`, `apps/backend/tests/test_template_catalog.py`
- Delete: `app/core/template_store.py`, `app/core/template_models.py`, `tests/test_template_store.py`, `tests/test_cli_templates.py`; frontend `src/routes/dmu/admin/templates/` (all), `src/components/templates/`, and the sidebar item
- Modify: `app/api/templates.py` (read-only list for the report form), `app/api/reports.py`, `app/api/capture.py:510`, `app/jobs/reports.py`, `cli.py` (remove `templates` commands), `scripts/seed_demo.py`, `alembic/env.py`, every `app/templates/definitions/*.yaml` (`version: 100`), `src/routes/dmu/reports/new.tsx`, and the tests that seed templates through the store

**Interfaces:**
- `get_template(name: str) -> Template | None` and `list_templates() -> list[Template]`. They load from `app/templates/definitions/` once per process and validate each file's metrics and placeholders with today's `validate_template_payload` logic. An invalid YAML fails at startup, not at report time.
- `GET /templates` returns the current YAML templates for the report form. Removed: `POST /templates`, the `/versions` routes, and the `version` field on `POST /reports`.
- YAML versions start at `100`, so they can't collide with the numbers already stored on reports issued from the DB era.
- A queued job uses the current YAML, and the report records that version when it runs. An issued report keeps its stored markdown and fact table, so nothing needs old template text.

- [ ] **Step 1: Write failing tests:**
  - `test_get_template_returns_yaml_with_its_version`
  - `test_unknown_template_returns_none`
  - `test_invalid_metric_fails_catalog_load`: a directory with a bad metric raises `ValueError` naming the file.
  - `test_report_records_template_version`: a report generated from a YAML with `version: 100` stores `template_version == 100`, and generating again after a bump to `101` stores `101` on the new report only.
  - `test_post_templates_is_gone`: 405.
  - `test_drop_report_templates_migration_round_trips`
  - Frontend: the sidebar has no Templates item.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement** the catalog, point every caller at it, delete the store, table, page and CLI commands, and write the migration. `upgrade` drops `report_templates`; `downgrade` recreates it empty.
- [ ] **Step 4: Run** `uv run pytest`, `npm test` and `npx tsc --noEmit`. Expected: PASS.
- [ ] **Step 5: Commit** `refactor(templates): YAML files replace the template table and page`

### Task 16: Require a login on every data endpoint

**Why (checked 2026-11-05):** with no token, `GET /incidents`, `GET /submissions`, `GET /templates` and `GET /quality/summary` all return 200, and `POST /templates` reaches body validation (422, not 401). The admin check exists only in the frontend. Task 12 shows more data, and field offices start testing soon, so do this first.

**Files:**
- Modify: `apps/backend/app/__init__.py` (`include_router(..., dependencies=[...])`), `app/api/quality.py`, `tests/conftest.py` (authenticated test client)
- Test: `apps/backend/tests/test_api_auth_required.py`

**Interfaces:**
- `/healthcheck` and the login routes stay public.
- Any signed-in user: `capture`, `submissions`, `reports`.
- `require_dmu_workspace`: `overview`, `incidents`, `situation-logs`, Survey123 upload, `quality`.
- `require_admin_user`: writes to `templates`, and `users` as today.

- [ ] **Step 1: Write failing tests,** parametrized over every route in the app: no token → 401 unless it's on the public list. A corporation user → 403 on the DMU routes. A new route that nobody listed therefore fails by default.
- [ ] **Step 2: Run** `uv run pytest tests/test_api_auth_required.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement,** then give the existing API tests a signed-in client through `conftest.py`.
- [ ] **Step 4: Check one corporation can't read another's data.** Read `_load_owned` in `app/api/capture.py` and the `corporation` handling in `app/api/submissions.py`. If the corporation comes from the client instead of the signed-in user, add a failing test and fix it here.
- [ ] **Step 5: Run** `uv run pytest` and `npm test`. Expected: PASS.
- [ ] **Step 6: Commit** `fix(auth): require a login on every data endpoint`

---

## Suggested order

Field-office testing is close, so the work that affects it goes first:

1. **Task 16** login, **Task 11** file rejection, **Task 15** YAML templates, **Task 10** report C, **Task 14** dashboard: what testers will touch. Task 15 comes before Task 10 so the new template needs no import step.
2. **Tasks 1–2** remove WhatsApp.
3. **Tasks 3–9** reports A and B in the baseline formats.
4. **Task 12** records table.
5. **Task 13** remove modules. It comes after Tasks 5–6, which add the new metric.
