# DMCU Reporting — Corp SITREP Realignment

**Date:** 2026-07-26
**Status:** Approved design, ready for implementation planning
**Supersedes:** `PLAN.md`, `HANDOFF.md`, `.cursor/plans/corp_ux_and_report_review_e09eaf2a.plan.md` (all removed)

---

## 1. Problem

Two user groups exist. Fourteen **regional corporations** each cover a region of Trinidad and report to the **Disaster Management Coordinating Unit (DMU)**. The DMU reports to the Minister.

The minister's SITREP must be built from all fourteen corps' SITREPs plus validated Survey123 data. The blocker: corp SITREPs arrive in inconsistent, non-standard formats (see `docs/examples/`). Parsing those documents with an LLM to recover figures is exactly the hallucination risk this system exists to prevent.

The resolution is to move the structure upstream. Corps use the system to produce their own SITREPs from structured data they upload. The minister's SITREP is then generated from that **structured data directly** — never by parsing corp report prose.

These are government corporations. We cannot dictate their workflow. Therefore data arrives as **CSV** (they work in spreadsheets), never as one-by-one form entry.

A corp SITREP splits into two distinct streams:

- **Incidents** — discrete events with a location, a type, and a response (Diego Martin's numbered table).
- **Situation logs** — operational and preparedness state (TPRC's "Summary of Activities", Full Sitrep 2023's per-corp bullets: "200 sandbags available", "22 facilities inspected").

### Source authority (from stakeholder)

- Survey123 is raw, unverified field observation. Rows carry a validation status that field supervisors toggle.
- SITREPs are human-verified operational summaries and carry the **authoritative** figures.
- Standard operations pull **only validated** Survey123 records.
- During active events, figures are early and unverified — such reports must carry a **Provisional** tag, and are replaced once field verification resumes.

---

## 2. Decisions

These were settled in brainstorming and are not open for reinterpretation during implementation.

| # | Decision | Rationale |
|---|---|---|
| 1 | **Events are corp-owned, structured, and reusable.** | An adverse weather event may hit the south while the north is unaffected, so a DMU-declared national event is wrong. Corp-owned means zero coordination cost and no codes to distribute. Reusable across submissions gives "Situation Report #4" numbering and cumulative counts. |
| 2 | **The ingest unit is a submission**: corporation + as-at time + files. | It is what a corp knows without being told anything, and it is the provenance anchor that makes a citation honest. |
| 3 | **Alert level and present activity live on the submission, not the event.** | Diego Martin #4 reads "Discontinuation – Green Level"; #1 read Yellow. Same event. Alert level is a state *as at* a moment. |
| 4 | **Situation Overview is corp-supplied prose, rendered verbatim.** | Full Sitrep 2023's overview describes a tropical wave's longitude and forward speed. No data in the system could produce it; asking the LLM to write it guarantees invention. Rendering it verbatim and attributed keeps it outside the citation guarantee rather than quietly breaking it. |
| 5 | **Situation logs are a prose line plus optional structured quantity.** | Corps write both "Informed CEO, Engineer and PMOH" (no number) and "200 sandbags available" (countable). Any number the report states must come from the quantity column, never lifted from prose. |
| 6 | **SITREP and Survey123 facts are separate and labelled, never merged.** | SITREP is the authoritative headline; validated Survey123 is corroboration. Divergence stays visible and provenance is unambiguous per citation. |
| 7 | **Generated reports are immutable; edits create flagged revisions.** | The citation checker re-runs on save and labels unbacked figures, but never blocks — a blocked save sends a government user with a deadline into Word. Safe because edits are terminal artifacts that can never feed a downstream number. |
| 8 | **Provisional is derived automatically and cannot be overridden.** | A manual flag is forgettable under exactly the time pressure it exists for. |
| 9 | **"Shared with DMU" is a status marker, not an approval gate.** | Gating the minister report on report approval is incoherent when the minister report reads data, not reports. Non-reporting corps are named explicitly, as the real document already does. |
| 10 | **Schema splits the two sources with a shared metric core.** | The sources are never merged and carry different authority; encoding that as a string column on a shared table keeps the old premise. |

### Load-bearing invariant

**The minister report reads corp *data*. It never reads corp report text, narrative, or revisions.** This is what makes flagged-not-blocked editing safe, and it gets an explicit test.

---

## 3. Domain model

Five tables.

### `events` — corp-owned, reusable

| Column | Notes |
|---|---|
| `id` | |
| `corporation` | owner; a corp only ever sees its own events |
| `title` | free prose, e.g. "Adverse Weather June 2023" |
| `hazard_type` | enum: `flood`, `landslide`, `wind`, `fire`, `other` |
| `started_at` | |
| `ended_at` | nullable; null means still running |
| `created_at` | |

No alert state — that moves with each submission (Decision 3).

### `submissions` — ingest unit and provenance anchor

| Column | Notes |
|---|---|
| `id` | |
| `corporation` | |
| `event_id` | **nullable** — routine incidents need no event |
| `as_at` | the "As at 4:00 pm on 30/06/2023" timestamp |
| `alert_level` | enum: `green`, `yellow`, `orange`, `red`, `discontinued`, `none` |
| `present_activity` | prose, e.g. "Adverse Weather Alert", "Overcast" |
| `situation_overview` | prose, rendered verbatim (Decision 4) |
| `sequence_no` | computed per event → "Situation Report #4" |
| `source_file`, `ingested_at` | |

### `sitrep_incidents` — authoritative, corp-entered

`submission_id`, `row_id` (the corp's own numbering), `community`, `street`, `incident_type` + `raw_incident_type`, `incident_summary`, `occurred_on`, `injuries_occurred`/`injuries_count`, `deaths_occurred`/`deaths_count`, `building_damage`, `special_needs_occupants`, `estimated_damage_cost`, `action_taken`, `follow_up_flags` (JSON: relief_supplied, forwarded_to_agency, further_assessment_required, other).

**No PII.** Name and contact columns are dropped at parse time and never written, as today.

### `situation_logs`

`submission_id`, `category` (enum: `resource`, `personnel`, `facility`, `activity`, `relief_distributed`, `other`), `statement` (the corp's own sentence, **required**), then optional `item`, `quantity`, `unit`, `status` (`available`, `prepositioned`, `in_stock`, `inspected`, `on_standby`, `ongoing`, `completed`, `procuring`).

This also absorbs Diego Martin's "Disaster Relief Distribution Summary" — Tarpaulins 18 is `relief_distributed / tarpaulins / 18 / units`.

### `field_observations` — Survey123, raw

Today's `incidents` table renamed and stripped to Survey123's own shape: keeps `validation_status`, `lat`/`lon`, `flood_type`/`flood_trigger`/`flood_height`, `dedup_hash`, `is_duplicate`, `occupants_count`, assessment/creation/edit dates. No `submission_id`, no `event_id`, no `source` column — the table *is* the source.

### Supersession

- **Sitrep incidents upsert on `(corporation, event_id, row_id)`.** A corp re-sending its cumulative table for report #4 supersedes rows 1–25 rather than double-counting them. The row records the submission that last reported it.
- **Situation logs never upsert.** They are state, not occurrences. Metrics read the **latest submission per corporation** in the window.
- **A submission with no event is standalone** and supersedes nothing.

---

## 4. Ingest

One atomic action creates a submission: corporation, as-at, alert level, present activity, situation overview, an event (an existing one of theirs, or new event fields), and up to two CSV files. Either file may be omitted — a corp with only preparedness activity submits logs alone; a corp with only field incidents submits incidents alone. If any part fails, none of it lands.

**`incidents.csv`** — `Row ID`, `Community`, `Street`, `Incident Type`, `Date of Event`, `Incident Summary`, `Injuries Occurred`, `Injuries Count`, `Deaths Occurred`, `Deaths Count`, `Building Damage`, `Special Needs Occupants`, `Estimated Damage Cost`, `Action Taken`, `Relief Supplied`, `Forwarded To Agency`, `Further Assessment Required`, `Other Follow Up`.

`Name of Person` and `Contact Information` are tolerated if present (real corp spreadsheets carry them, per Diego Martin) and **dropped without being written**.

**`logs.csv`** — `Category`, `Statement`, `Item`, `Quantity`, `Unit`, `Status`.

**Row-level error reporting.** Today a malformed `Row ID` raises an uncaught `ValueError` and aborts the whole batch. That is unacceptable now that corps are the authors: valid rows must land, and rejected rows must come back with row number and reason. This closes a known open weakness.

**Normalization** reuses the existing `normalize_corporation` / `normalize_incident_type` helpers. Unmapped incident types fall through to `raw_incident_type` and are surfaced in the ingest result rather than silently coerced.

---

## 5. Metrics, facts, citations

**Shared metric core.** Metric functions take the model class plus filters rather than a source string. Two modules register against the existing `DataModule` protocol: `sitreps` (over `sitrep_incidents` and `situation_logs`) and `survey123` (over `field_observations`). The engine is untouched — it still calls `module.run_metric(...)`.

**Survey123 defaults to validated-only.** `include_pending` must be passed explicitly; standard operations never see unvalidated rows.

**New log metrics:**
- `resource_availability` — sums `quantity` by `item` across the latest submission per corp ("sandbags available nationally: 880").
- `relief_distributed_summary` — same shape over the `relief_distributed` category.
- `activity_log` — non-quantified statements returned as attributed text facts carrying no numbers.
- `corps_reporting` — which of the fourteen have a submission in the window and which do not, so the minister report can state "Siparia Regional Corporation: no reports at this time."

**Citation provenance extends to the submission.** A citation description becomes "Borough of Diego Martin, Situation Report #4, as at 4:00 pm 30/06/2023" rather than a bare window label.

**Provisional derivation.** A fact is provisional if it draws on unvalidated Survey123 rows, **or** its submission belongs to an event still considered active. An event is active when `ended_at` is null **and** the corp's latest submission for it carries an alert level other than `discontinued` — two independent ways for a corp to clear it, so nothing is stranded provisional forever. A report is provisional if any contributing fact is. The flag is stored on the report, watermarked in the render, and marked per fact in the citation appendix. Regenerating after validation completes produces a clean report with no human action, which is the "replace provisional data once verification resumes" behaviour.

---

## 6. Templates and reports

Both templates are DB-versioned via the existing `template_store`, so the template, prompt, params and metric set that produced any report stay frozen and reproducible.

**A deliberate shift: more of the report is rendered deterministically, less is narrated.** Header blocks, verbatim overviews, and tables are emitted by the renderer. The LLM's job shrinks to connective prose and comparison. This strengthens the citation premise rather than relying on it.

### `corp_situation_report`

Params: corporation, event (or date window).

Sections mirroring the real documents — header block (location / present activity / alert level / as at, rendered from the submission), Situation Overview (verbatim), Situation Summary (incident counts by type, cited), Relief Distribution (from logs, cited), Activities (log statements, attributed), Data Gaps.

### `minister_situation_report`

Params: date window, optional hazard filter, plus the DMU's own header block and national overview prose — their framing, exactly as Full Sitrep 2023 shows the Ministry header sitting above corp-authored content.

Then **one section per corporation in fixed order**, each carrying that corp's own alert level, counts and activities, with non-reporting corps named explicitly. Validated Survey123 figures appear as **separate labelled corroborating facts**, never folded into a corp's number.

---

## 7. Report lifecycle

`reports` stays the frozen artifact and gains `scope` (`corp` or `dmu`), `corporation`, `provisional`, and `shared_with_dmu_at`. It already carries template, template version, params, resolved data requirements, fact table, narrative, markdown, status and violations.

`report_revisions` is new: `report_id`, `revision_no`, `markdown`, `edited_by`, `created_at`, `citation_status` (`ok` / `flagged`), `violations`. The generated original is revision 0 and is immutable. On save the citation checker re-runs; unbacked figures are recorded and highlighted, and the save always succeeds. The original stays retrievable and diffable, and a reader can always tell they are holding edited prose.

`shared_with_dmu_at` marks a corp report as shared. The DMU gets a list. Nothing blocks, and the minister report ignores it entirely.

---

## 8. Surfaces

**Corp workspace** — New Submission (pick or create an event, as-at, alert level, present activity, situation overview, up to two CSVs), My Events, Generate Report (no template picker — corporation and window only), Report view with clickable citations, Edit → revision, Share with DMU.

**DMU workspace** — Overview (who has reported in this window and who has not), Survey123 field-data ingest, Generate minister report, Report view and edit, Templates admin.

**Realignment of existing code:**
- The `/ingest` route is currently a `FormPlaceholder` with no working ingest UI at all; it is replaced by the real submission and Survey123 upload forms.
- `routes/reports/corp.tsx` is retargeted to `corp_situation_report`.
- The per-request `data_requirements` metric picker is **retained on the DMU admin route only** and removed from the corp path. It is an escape hatch for ad-hoc ministerial asks; a corp officer never picks metrics.
- The Cursor debug instrumentation in `app/core/llm.py` and `app/api/reports.py` (`# #region agent log`, hardcoded absolute log path) is removed. It currently breaks two tests.
- The duplicate `components/form-components/` and `components/forms/` directories are consolidated.

---

## 9. Migration and testing

**Migration.** New tables created fresh. Existing `incidents` rows with `source = 'survey123'` are backfilled into `field_observations`; rows with `source = 'sitreps'` are backfilled into `sitrep_incidents` under one synthetic backfill submission per corporation, carrying `alert_level = none` and a null event. `alembic/env.py` must import the new models so autogenerate does not propose dropping them — the same trap that was hit once already.

**Tests.**
- Per-row ingest error reporting: a malformed row is rejected with a reason while valid rows land.
- Supersession: re-uploading a cumulative incident table for report #4 updates rows 1–25 rather than duplicating them.
- Latest-log-wins: two submissions from one corp yield only the later submission's logs.
- Cross-source isolation: adapted from the existing discriminating test — each module sees only its own table.
- Provisional derivation: both triggers independently, and both clearing paths (`ended_at` set, and latest alert level `discontinued`).
- `corps_reporting` names non-reporting corporations.
- Revision citation re-check: an edit introducing an unbacked number saves successfully and is flagged.
- **Invariant test:** generating a minister report touches no report narrative, markdown, or revision row.
- PII: name and contact columns present in an uploaded CSV are never written to any table.

---

## 10. Build order

Four sequenced plans, each independently reviewable:

1. **Events, submissions, situation logs** — schema split, migration, backfill, both CSV ingest paths with row-level error reporting.
2. **Metrics and source semantics** — shared metric core over model classes, validated-only default, log metrics, `corps_reporting`, submission-level citation provenance, provisional derivation.
3. **Templates** — `corp_situation_report` and `minister_situation_report`, deterministic rendering of header blocks and tables, verbatim situation overview.
4. **Lifecycle and surfaces** — report revisions, share marker, corp and DMU workspaces, removal of the debug instrumentation and the placeholder ingest route.
