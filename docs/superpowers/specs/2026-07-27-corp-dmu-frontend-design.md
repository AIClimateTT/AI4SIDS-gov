# Corp and DMU Frontend — Submission Workspace

**Date:** 2026-07-27
**Status:** Approved design, ready for implementation planning
**Builds on:** `docs/superpowers/specs/2026-07-26-corp-sitrep-realignment-design.md` (the realignment spec) and the completed backend plan 1 (`docs/superpowers/plans/2026-07-26-events-submissions-situation-logs.md`)

---

## 1. Problem

The frontend speaks the system's vocabulary, not the users'. Today's navigation reads *Overview · Ingest · Reports · Corp report · Templates · Modules* — six items, every one of them a noun from the processing pipeline. Nobody in a regional corporation says "ingest" or "module"; they say "the sitrep". The DMU does not think in "templates"; it thinks "the Minister needs the report by 3pm". Both audiences share one menu in which each sees mostly things that are not theirs.

There is also no notion of who is using the application. "Which corporation" is a dropdown re-answered on every form, so nothing feels like a given corporation's workspace and nothing filters to them.

**What users expect** is the document and the routine that produces it — not a view of the machinery that computes it.

### A constraint that shapes the scope

Both report templates (`app/templates/definitions/*.yaml`) request **only `survey123` metrics**. Nothing requests SITREP data. A corp officer could upload their spreadsheet today, generate a "region report", and receive a document built from Survey123 field observations rather than from what they just submitted — the exact provenance confusion this system exists to prevent.

So the corp **upload** workflow is fully supported by the current backend, and the corp **report** workflow is blocked on realignment plan 3. This spec covers the half that works.

---

## 2. Decisions

| # | Decision | Rationale |
|---|---|---|
| 1 | **Build the submission workspace now; report generation comes with plan 3.** | Ships real value against a backend that fully supports it, and avoids a report whose numbers come from the wrong source. |
| 2 | **Identity is a declaration chosen once, persisted locally, shown in the header.** | Turns "which corporation" from a repeated form field into app context. A real login later fills the same context and no screen is redesigned. |
| 3 | **No security theatre.** | The context is a claim, not a credential. Presenting it as a boundary would train users to trust something that does not exist. |
| 4 | **The corp workspace is organised around the event.** | A multi-day storm is one event with a run of filings. The backend already numbers them (`sequence_no`), which is the "Situation Report #4" on the real document. |
| 5 | **Add a minimal submission read API only.** | `GET /submissions` + `GET /submissions/{id}` is what the event view needs. "Who has reported" is derived client-side at fourteen rows, then replaced by plan 2's `corps_reporting` metric rather than duplicated now. |
| 6 | **Persist row errors on the submission.** | They are currently ephemeral, returned once at ingest. An officer who closes the tab loses the list of what to fix and must re-upload to rediscover it. |

---

## 3. The shell — identity, roles, navigation

**Identity** is `{ role: 'corp', corporation: string } | { role: 'dmu' }`, held in `localStorage` under one key and exposed through a React context. First visit renders a single question — *Who are you?* — offering the DMU or one of the fourteen corporations from `src/lib/corporations.ts`. The choice shows permanently in the header ("Borough of Diego Martin") with a plain **Switch** link beside it.

**No security theatre.** No lock icons, no "sign out", no password field. Switching is one click with no friction. Opening a `/corp/*` URL while acting as the DMU renders an inline *"You're viewing as the DMU — switch to Diego Martin?"* prompt, never a 403. This is deliberate: the application must not imply an access boundary it does not enforce.

**Routes split by role.** `/corp/*` and `/dmu/*`, with `/` redirecting to the stored identity or, if none, to the who-are-you screen. When real authentication arrives, that redirect reads a session instead of `localStorage` and nothing else changes.

**Navigation, per role:**

- **Corp** — Events · File a report · My submissions
- **DMU** — Dashboard · Corporations · Field data · Reports · Admin

The corp nav's **File a report** is a shortcut, not a separate screen: with exactly one running event it goes straight to that event's filing form; with several it goes to `/corp` with the running events listed; with none it offers the two starting points (declare an event, or log routine incidents). It never presents an event picker as a form field — the event is chosen by navigation, which is what keeps §4's structure intact.

**Templates and Modules move rather than disappear.** They become `/dmu/admin`, reachable only under the DMU role. They are real tools for whoever configures the system, and were never things a corp officer should see in a primary nav.

---

## 4. The corp workspace

### `/corp` — Events

Running events first (no `ended_at`, latest submission's alert level not `discontinued`), past events below. Each card carries the title, current alert level, and *"last filed: report #3, as at 4:00 pm 30/06"*. The empty state points at the two ways in: declare an event, or log routine incidents.

### `/corp/events/new` — Declare an event

Title (free prose, e.g. "Adverse Weather June 2023"), hazard type, start date. Nothing else — the alert level belongs to each submission, not to the event.

### `/corp/events/$id` — The event

The page header deliberately mirrors the corporation's own document: title, present activity, current alert level, and *"As at 4:00 pm on 30/06/2023"*, all read from the latest submission. Below it, the run of filings as a timeline (#1 … #N), each showing as-at time, alert level, and accepted counts. Primary action: **"File report #4"**, with the number computed rather than typed.

### `/corp/events/$id/file` — File a report

Pre-filled from the previous submission in that event: alert level, present activity and situation overview carry forward as editable defaults, so a follow-up during a storm is a small edit and two file pickers rather than a blank form at 2am.

Fields: as-at (defaults to now), alert level, present activity, situation overview (textarea), incidents CSV, logs CSV.

Three properties that decide whether this is adopted:

**"Nothing to report" is a real filing.** The backend accepts a submission with no files, and that is precisely Full Sitrep 2023's *"Siparia Regional Corporation — No reports at this time."* The form allows zero files and says so. It is a positive signal to the DMU, not an absence.

**Downloadable blank CSV templates**, one per file type, carrying the exact headers the parser expects. Nobody can guess `Further Assessment Required`. This is the smallest feature with the largest effect on adoption.

**Row numbers are translated to spreadsheet rows.** `RowErrorInfo.row_number` counts from the first *data* row; a user counts from what their spreadsheet shows, where row 1 is the header. The UI adds the offset and reports *"Row 3"*, matching the line they will go and fix. Unadjusted, every rejection message sends someone to the wrong row. The translation lives in one function with its own test.

### The result screen

After filing: *"4 of 5 incident rows accepted"*, plus a table of rejections giving spreadsheet row and reason. Reachable again later from the submission detail, because row errors are persisted (§6).

### `/corp/submissions` — My submissions

A flat list of everything this corporation has filed, across all events and event-less filings, newest first.

### Routine incidents

A separate, simpler path for filings with no event: the same form minus the event context. These do not accumulate a sequence number and do not supersede one another, matching the backend's behaviour.

---

## 5. The DMU workspace

**`/dmu` — Dashboard.** The DMU's live question during an event is *who has reported?*, so that is the page: all fourteen corporations for a chosen window, each either reported (latest as-at, alert level, counts) or not, derived client-side from `GET /submissions`. Fourteen rows makes client-side derivation honest; plan 2's `corps_reporting` metric replaces it when the minister report needs the same answer server-side.

**`/dmu/corporations/$corp`** — read-only view of one corporation's events and filings.

**`/dmu/field-data`** — today's `/ingest`, renamed to what it is: the Survey123 upload. This replaces the current `FormPlaceholder`, which means there is presently no working ingest UI at all.

**`/dmu/reports`** — the existing reports list and citation-linked detail view, which already work and are kept as-is.

**`/dmu/admin`** — Templates and Modules.

---

## 6. Backend additions

Three small changes, all in `apps/backend`.

**`GET /submissions`** — returns id, corporation, event_id, as_at, alert_level, sequence_no, and accepted incident and log counts, newest first.

**Every filter is optional**, and this matters in both directions: the corp event view calls it with `event_id`, while the DMU dashboard calls it with only a window and needs *all fourteen corporations back*. An implementation that requires `corporation` would silently make the DMU dashboard impossible. Filters: `corporation`, `event_id`, `date_from`, `date_to` (the window filters on `as_at`).

**`GET /submissions/{id}`** — the above plus `situation_overview`, `present_activity`, and the persisted row errors.

**`row_errors` JSON column on `submissions`**, written by `ingest_submission`, with an Alembic migration. Defaults to an empty list. This is what makes the detail endpoint worth having, and it gives the DMU visibility into which corporations are submitting malformed spreadsheets and therefore need help.

Note for the implementer: `app/modules/sitreps/ingest.py` already builds the `RowErrorInfo` list before it commits; persisting it is storing that same list on the submission row inside the existing single transaction, not recomputing it.

---

## 7. Testing

Proportionate to risk. Vitest, following the existing `src/lib/format-constant.test.ts` precedent, covering the logic that can be silently wrong:

- **Spreadsheet row translation** — a data row of 1 renders as row 2, and the offset holds across both file types.
- **Identity persistence and rehydration** — a stored corp identity survives reload; an absent or malformed stored value falls back to the who-are-you screen rather than crashing.
- **Event grouping** — running versus past, including the two independent ways an event stops being active (`ended_at` set, or latest submission `discontinued`).

Backend additions get pytest coverage in the existing style: filtering by each parameter, a submission with no event appearing in an unfiltered list, and row errors surviving a round trip through `GET /submissions/{id}`.

Not tested: whole-page rendering, navigation chrome, styling.

---

## 8. Out of scope

- Authentication, and any real access control.
- Corp report generation — realignment plan 3.
- Report editing and revisions, and the "shared with DMU" marker — realignment plan 4.
- Any incidents data-table browser.
- Live Google Sheets integration; the path remains CSV export and upload.

---

## 9. Build order

Three plans:

1. **Shell and identity** — the who-are-you screen, identity context and persistence, role-shaped navigation, `/corp` and `/dmu` route split, and the demotion of Templates and Modules to `/dmu/admin`.
2. **Backend read API and row-error persistence** — the migration, the two endpoints, and their tests.
3. **The two workspaces** — corp events, filing, result screen, CSV templates and submissions list; DMU dashboard, corporation view and the real field-data upload.
