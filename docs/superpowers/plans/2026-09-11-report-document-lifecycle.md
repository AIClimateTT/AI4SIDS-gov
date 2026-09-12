# Report Document Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Start gate:** do **not** implement this plan until WhatsApp chat-first **Phase 3 (live briefing)** is merged to `main`. That work owns Record | Briefing tabs, stale/refresh on the hour draft, and the provisional banner. This plan must not reopen it, merge WhatsApp into `CaptureSession`, or treat a WhatsApp briefing as a cited national SITREP.
>
> **Phase gate:** do not start Phase N+1 until Phase N's implementation self-review is written into the PR and every item is fixed or explicitly deferred with a reason.

**Goal:** Give DMU / minister reports the same **document** contract corp sitreps already have — a draft that goes stale when source facts change, refresh in place, issue as a frozen snapshot — plus a **minor chat** that steers the narrative without rewriting store figures. This becomes the standard path for curating a report as new data arrives over time.

**Architecture:** Lifecycle lives on the `reports` row, not on `CaptureSession` and not on `whatsapp_drafts`. Facts still come from the engine and the store (sitreps, Survey123, etc.). A stored `source_observed_at` is compared to the latest relevant store timestamps for the report's params; if the store is newer, the draft is stale. Refresh rebuilds markdown and the fact table **on the same id** while `lifecycle=draft`. Issue freezes the row. Chat may only add narrative instructions; it must not write quantity fields. Corp figure corrections stay on the corp session or WhatsApp draft; the minister draft then goes stale and refreshes.

**Tech Stack:** FastAPI, SQLAlchemy 2.x, Alembic, pytest · React 19, TanStack Router + Query + `@tanstack/ai-react`, Tailwind 4, Vitest + Testing Library.

**Depends on (must already be on `main`):**

- Corp live sitrep: `docs/superpowers/plans/2026-08-21-live-corp-sitrep.md` (preview / stale / issue on the **session**).
- WhatsApp chat-first Phases 1–3: `docs/superpowers/plans/2026-09-11-whatsapp-chat-first-ingest.md` (dual input, conversation, **live provisional briefing**).

**Does not replace:** corp `POST /capture/sessions/{id}/preview` and `/issue`. Those remain the one-corp filing path. This plan is the DMU document path.

---

## Why this is a different plan from WhatsApp Phase 3

| | WhatsApp Phase 3 | This plan |
|---|---|---|
| When | Next on the ingest branch, before this | After Phase 3 is on `main` |
| Object | `whatsapp_drafts` working set + briefing tab | `reports` row (minister / template reports) |
| Audience | DMU hour, multi-corp, **provisional** | Minister / national pack, cited |
| Chat | Already exists (Phase 2) — edits **facts** with provenance + allowed numbers | **New, minor** — steers **prose**, not store counts |
| Issue | File-to-store still optional; briefing stays provisional | Issue = freeze the document that went to the minister |
| Stale vs | Rail `updated_at` vs last briefing | Store timestamps in the param window vs `source_observed_at` |

Copying corp Issue onto the WhatsApp hour would imply the hour is a signed national SITREP. It is not. Phase 3 already covers live briefing for that surface.

---

## Global Constraints

- **Do not reuse `CaptureSession`.** One corp filing its own sitrep is a different object from a minister pack.
- **Do not merge WhatsApp hour into this table.** After Phase 3, a WhatsApp generate still writes a `reports` row; that row may later *join* this lifecycle (draft/issued) without changing the hour workspace. Do not put WhatsApp `manual_fields` or source quotes on `reports`.
- **Minister chat must not invent figures.** Allowed numbers = the current fact table ∪ digits the officer typed in that message. `strip_invented_numbers` / citation check still apply. Chat must not PATCH `sitrep_incidents` or Survey123 rows.
- **Corrections of a corp count happen on the corp session or WhatsApp draft.** The minister draft goes stale; the officer refreshes. No back door into the authoritative tables.
- **Issue does not ingest.** `ingest_submission` stays on capture file/issue and WhatsApp promote. Issuing a minister report only freezes prose + facts already in `reports`.
- **Issued rows are immutable.** Refresh on `lifecycle=issued` is 409. “Revise” clones template, params, data_requirements, and narrative instructions into a **new** draft id.
- **Do not conflate job status with lifecycle.** Keep existing `status` (`queued` / `running` / `ok` / `needs_review` / `failed`). Add `lifecycle` (`draft` | `issued`). A failed generate is still a draft.
- **Refresh, don't stream the full report.** Same rule as corp sitrep Decision 5: turns do not auto-generate the document. The officer clicks Refresh (or Issue, which regenerates then freezes).
- **`@testing-library/jest-dom` is NOT installed.** Plain matchers. Render tests start with `// @vitest-environment jsdom`.
- **Backend tests:** `cd apps/backend && .venv/bin/python -m pytest`. **Frontend:** `cd apps/frontend && pnpm test` and `pnpm exec tsc --noEmit -p tsconfig.json`.
- **Migrations apply from empty.** SQLite has no `ALTER COLUMN`; use `op.batch_alter_table`. Confirm `alembic heads` on the **then-current `main`** (after Phase 3) before writing a revision. Do not assume a head id from the day this plan was filed.
- **YAGNI:** no report TTL, no multi-user locking, no freehand markdown editor, no merging templates, no predictive “what changed” LLM summary unless a later plan adds it.

---

## Decisions (locked)

1. **Shared contract, different fact sources.**
   ```
   source-specific facts
     corp session  |  WhatsApp draft  |  store metrics
           \              |               /
            draft document (stale when facts change)
                         |
                 refresh / issue
   ```
   Shared: draft, stale, refresh, issued snapshot, open-report. Not shared: capture table, event chip, WhatsApp quotes, minister citation appendix.

2. **Lifecycle column on `reports`.** Default `draft` after generate. `issued` only via an explicit Issue action. List UI can filter “Drafts” vs “Issued”.

3. **Stale is store-vs-snapshot, not “there is a newer reports row”.** Compute `source_high_water(params)` = max timestamp of submissions, sitrep incidents, situation logs, and field observations that fall in the report's `date_from` / `date_to` (and optional `corporation`). Stale iff `lifecycle=draft` and `source_high_water > source_observed_at`. Job `queued`/`running` is not stale; it is generating.

4. **Refresh updates the same report id** while draft. It re-runs `generate_report` with the same template, params, data_requirements, and any stored narrative instructions. It overwrites markdown, fact_table, narrative, violations, quality_eval, and `source_observed_at`. History of previous drafts is not kept (YAGNI). Issued copies are the history.

5. **Issue regenerates if stale, then freezes.** Same as corp issue always regenerating. Sets `lifecycle=issued`, `issued_at=now`. Detail page shows Issued; Refresh is replaced by Revise (clone).

6. **Minor chat is narrative steering, not a second working set.** Payload to the model: current fact table (read-only), current markdown, `messages`, `user_message`. Model returns `assistant_message` plus optional `narrative_instructions` (a short brief: emphasis, corps to drop, window reminder). It must **not** return a mutated fact table. After the turn, the document is **stale** until Refresh (do not auto-narrate on each turn — Decision 5).

7. **WhatsApp briefing rows may opt into lifecycle later** (`lifecycle` default draft is enough). Do not add Issue to the hour workspace in this plan. Phase 3 already has live briefing + provisional banner. A follow-up, if wanted, is “Issue this briefing copy” on the **report detail** page only, still showing provisional.

---

## Flaw Register

| ID | Flaw | Location | Severity | Resolution |
|----|------|----------|----------|------------|
| **R1** | Every `POST /reports` mints a new id. Tweaking params or waiting for a late corp filing leaves a pile of near-duplicate rows with no stale signal. | `app/api/reports.py` `create_report`, `routes/dmu/reports` | High | Phase 1 |
| **R2** | No draft vs issued. The document that went to the minister is indistinguishable from a trial generate. | `reports.status` is only the job | High | Phase 1 |
| **R3** | Source data can change after generate with no UI cue. | `Report` has `created_at` only | High | Phase 1 |
| **R4** | No in-place refresh. Officers regenerate from `/dmu/reports/new` and lose the thread of which row they meant. | `new.tsx` always creates | High | Phase 1 |
| **R5** | No way to say “emphasize flooding in Diego Martin” without changing store data or re-picking metrics. | report detail is read-only | Medium | Phase 2 |
| **R6** | A chat that could edit counts would diverge from `sitrep_incidents`. | (does not exist yet — prevent it) | High (product) | Phase 2 constraints |
| **R7** | Corp sitrep already has preview/issue on the session; duplicating that onto `reports` without a clear split would confuse “filed sitrep” vs “minister pack”. | capture `preview`/`issue` | Medium | Constraints: do not touch capture issue |
| **R8** | WhatsApp generate already writes `reports` with a provisional banner. Applying Issue there without care would look like a national SITREP. | `modules/whatsapp/briefing.py` | High (product) | Out of scope for the hour UI; optional report-detail freeze only |

---

## File Structure

**Create:**
- `apps/backend/app/core/report_lifecycle.py` — `source_high_water`, `is_stale`, `assert_draft`.
- `apps/backend/alembic/versions/<rev>_report_lifecycle.py` — `lifecycle`, `source_observed_at`, `issued_at`, `narrative_instructions`, `messages`.
- `apps/backend/app/modules/reports/turn.py` — minor chat (Phase 2).
- `apps/backend/tests/test_report_lifecycle.py`
- `apps/backend/tests/test_report_turn.py` (Phase 2)
- `apps/frontend/src/components/reports/report-lifecycle-bar.tsx` (+ test)
- `apps/frontend/src/components/reports/report-narrative-chat.tsx` (+ test, Phase 2)

**Modify:**
- `app/core/report_models.py` — new columns.
- `app/core/report_store.py` — persist lifecycle fields; set `source_observed_at` on successful generate.
- `app/core/engine.py` / `jobs/reports.py` — stamp `source_observed_at` from `source_high_water` at generate time; pass `narrative_instructions` into narration.
- `app/api/reports.py` — detail includes `lifecycle`, `stale`, `issued_at`; `POST /reports/{id}/refresh`; `POST /reports/{id}/issue`; `POST /reports/{id}/revise`; Phase 2: `POST /reports/{id}/turns` + `/turns/stream`.
- `app/templates` / narration prompt — optional “Officer instructions:” block when `narrative_instructions` is set.
- Frontend types, `lib/api/reports.ts`, `lib/queries/reports.ts`.
- `routes/dmu/reports/$reportId.tsx` — stale banner, Refresh / Issue / Revise.
- `routes/dmu/reports/index.tsx` — draft vs issued (light: badge is enough).

**Do not modify (this plan):**
- `app/modules/capture/sitrep.py` preview/issue.
- WhatsApp draft workspace Record | Briefing tabs (Phase 3).
- `ingest_submission` / promote.

---

# Phase 1 — Draft, stale, refresh, issue on `reports`

Shippable alone. After this phase a DMU officer can generate a minister report, see it go stale when a corp files into the same window, refresh in place, and issue a frozen copy. No chat yet.

## Task 1: Schema + `source_high_water`

**Files:**
- Create: Alembic revision off **then-current `main` head**
- Create: `app/core/report_lifecycle.py`
- Modify: `report_models.py`, `report_store.py`
- Test: `tests/test_report_lifecycle.py`, `tests/test_migrations.py` (columns exist after upgrade head)

**Columns on `reports`:**

| Column | Type | Notes |
|---|---|---|
| `lifecycle` | `String`, NOT NULL, default `'draft'` | `draft` \| `issued` |
| `source_observed_at` | `DateTime`, nullable | Set when generate/refresh succeeds |
| `issued_at` | `DateTime`, nullable | Set on issue |
| `narrative_instructions` | `Text`, nullable | Unused until Phase 2; add now so chat does not need a second migration |
| `messages` | `JSON`, NOT NULL, default `[]` | Same |

SQLite: `op.batch_alter_table`; `server_default='draft'` / `'[]'` for backfill.

**`source_high_water(session, params) -> datetime | None`:**
- Read `date_from`, `date_to`, optional `corporation` from `params` (same names the minister template already uses).
- Max of:
  - `submissions.created_at` (filter corp / as_at in range as the sitrep metrics do)
  - `sitrep_incidents` timestamps available on that table (`created_at` today)
  - `situation_logs` equivalently
  - `field_observations` equivalently
- If nothing matches, return `None` (report is not stale; there is no newer source).
- Do **not** use `reports.created_at` of other reports.

- [ ] **Step 1: Failing tests** — high water moves after a new ingest in-window; out-of-window ingest does not; missing dates return None.
- [ ] **Step 2: Migration + model + function.** `alembic upgrade head` from empty sqlite; `alembic check`.
- [ ] **Step 3: Commit** `feat: stamp report drafts with a store high-water time`

## Task 2: Stamp `source_observed_at` on generate; expose `stale`

**Files:**
- Modify: `jobs/reports.py` / `apply_generated_report`, `api/reports.py` detail
- Test: `tests/test_api_reports.py`

After a successful generate, `source_observed_at = source_high_water(...)` (or generate time if high water is None).

Detail response adds:

```python
lifecycle: str
stale: bool
issued_at: datetime | None
source_observed_at: datetime | None
```

`stale = lifecycle == "draft" and is_stale(row, session)`.

- [ ] **Step 1: Test** generate then ingest a newer in-window submission → GET detail `stale is True`. Generate with no later ingest → `stale is False`.
- [ ] **Step 2: Implement.** Existing generate tests still pass (`status` unchanged).
- [ ] **Step 3: Commit** `feat: mark a minister draft stale when the store moves`

## Task 3: `POST /reports/{id}/refresh` and `/issue` and `/revise`

**Files:**
- Modify: `api/reports.py`, `report_store.py`, jobs if refresh reuses `enqueue("generate_report")`
- Test: `tests/test_api_reports.py`

**Refresh** (`lifecycle` must be `draft`; generation `status` must not be `queued`/`running`):
- 409 if issued.
- 400 if not ready.
- Re-enqueue generate on the **same id** (placeholder markdown ok). Frontend already polls `isReportJobPending`.
- Clears `stale` when the job completes.

**Issue:**
- 409 if already issued.
- 400 if generation not `ok` / `needs_review` (failed cannot issue).
- If stale, refresh first (same request, wait if eager; if async, 409 `"refresh this draft before issuing"` is acceptable — pick one and test it; prefer **eager-or-sync regenerate then freeze** so Issue is one click in local/fake, and 409-with-message if a job is still running).
- Sets `lifecycle=issued`, `issued_at=now`.

**Revise:**
- 400 unless issued.
- Creates a **new** placeholder draft copying `template`, `template_version`, `params`, `data_requirements`, `narrative_instructions`. Enqueues generate. Returns the new id (202).

- [ ] **Step 1: Failing API tests** for refresh in place (same id, new markdown), issue freeze, refresh-on-issued 409, revise clones.
- [ ] **Step 2: Implement.**
- [ ] **Step 3: Commit** `feat: refresh and issue a minister report draft`

## Task 4: Detail UI — stale banner, Refresh, Issue, Revise

**Files:**
- Create: `components/reports/report-lifecycle-bar.tsx` + `.test.tsx`
- Modify: `$reportId.tsx`, types, api, queries, list badge
- Do not change `/dmu/reports/new` beyond optional copy that Issue lives on the detail page.

Bar:
- Draft + stale: banner “Source data has changed since this draft. Refresh before issuing.” + Refresh + Issue (Issue disabled while stale **or** Issue allowed and server refreshes — match Task 3).
- Draft + not stale: Refresh still available, Issue enabled when `status` is ok/needs_review.
- Issued: “Issued {when}.” Refresh hidden. Revise button. Markdown remains read-only.

List: a small Draft / Issued badge next to existing job status. Do not build a second list page.

- [ ] **Step 1: Component tests** — stale shows banner; issued hides Refresh.
- [ ] **Step 2: Wire detail page.** `tsc --noEmit` clean.
- [ ] **Step 3: Browser** — generate minister sitrep → ingest or file a corp row in-window → detail shows stale → Refresh updates → Issue → Refresh gone, Revise creates a new draft.
- [ ] **Step 4: Commit** `feat: show draft, stale, and issued on the report page`

## Phase 1 self-review (write in the PR; do not start Phase 2 until done)

1. Does generate still create a `reports` row with the existing job `status`? Must be **yes**.
2. Does a later in-window filing set `stale` without minting a new report id? **Yes.**
3. Does Refresh keep the same id? **Yes.**
4. Is an issued row immutable (refresh 409)? **Yes.**
5. Does Issue ingest sitrep rows? Must be **no**.
6. Was `CaptureSession` / WhatsApp hour UI changed? Must be **no**.
7. Did this phase add chat? Must be **no**.

---

# Phase 2 — Minor narrative chat

Only after Phase 1's self-review. The officer can ask the draft to emphasize or de-emphasize; counts still come from the store.

## Task 5: Turn module (no fact-table writes)

**Files:**
- Create: `app/modules/reports/turn.py`, `app/modules/reports/prompt.py` (or a section in an existing reports prompt module)
- Test: `tests/test_report_turn.py`

Reuse capture/WhatsApp SSE envelope so `createSseConnection` + `ChatThread` work: `RUN_STARTED`, `TEXT_MESSAGE_*`, `CUSTOM` `report.updated` with the full detail payload, `RUN_FINISHED`.

Turn result:
- Appends user + assistant to `reports.messages`.
- May replace `narrative_instructions` with a short string from the model (or concatenate a bounded latest instruction — pick one; prefer **replace with the model's `narrative_instructions` field**, officer-visible on the page).
- **Does not** change `fact_table`, markdown, or lifecycle.
- Sets the document logically stale: either bump a `instructions_updated_at` compared in `is_stale`, or simply treat “instructions newer than `source_observed_at` / last generate” as stale. Simplest: **set `source_observed_at` to a value that makes `is_stale` true** is a hack — do not. Add `instructions_rev` or compare `updated_at` of the report row vs last generate time. Clean approach: store `generated_at` (fact_table already has `generated_at`) and `reports.updated_at` already exists? **Today `Report` has only `created_at`.** Add `updated_at` in this phase if Phase 1 did not, and `is_stale` also if `updated_at > generated_at` while draft. Task 1 may add `updated_at` if easier — do it in Phase 1 if you touch the migration once.

Prompt rules:
- Return JSON `{ "assistant_message", "narrative_instructions" }`.
- `narrative_instructions` is optional; if omitted, keep previous.
- Never emit counts that are not in the fact table or the user message.
- Do not claim the store changed.

400 if `lifecycle != draft` or job not complete.

- [ ] **Step 1: Tests** — turn stores instructions; fact_table unchanged; invented number in instructions stripped or instructions rejected; empty message 400; issued 409/400.
- [ ] **Step 2: Implement apply_turn + stream_turn.**
- [ ] **Step 3: Commit** `feat: narrative-only turns on a report draft`

## Task 6: Wire ChatThread on the report detail (draft only)

**Files:**
- Create: `report-narrative-chat.tsx` + test (composer present when draft; hidden when issued)
- Modify: `$reportId.tsx` — chat below the lifecycle bar, markdown still the main artifact. Do not invert to a corp-style split unless the page is unreadable at 1280; prefer chat **under** the banner, document **above**, so Issue stays obvious.
- Mobile 390px: chat then document is ok; lifecycle bar sticky.

Placeholder: “Emphasize a region, drop empty corporations, or tighten the window — this does not change filed counts.”

After a turn, banner should show stale until Refresh.

- [ ] **Step 1: Frontend tests** — empty composer on a draft; no composer on issued.
- [ ] **Step 2: Browser 1280 and 390** — generate → chat “Emphasize Diego Martin flooding” → Refresh → prose mentions Diego Martin, fact table counts unchanged → Issue hides chat.
- [ ] **Step 3: Commit** `feat: steer a minister draft in a short chat`

## Phase 2 self-review

1. Can chat change `injuries_count` / fact table quantities? Must be **no**.
2. Does a turn leave the document stale until Refresh? **Yes.**
3. Issued reports: no composer? **Yes.**
4. CaptureSession reused? **No.**
5. WhatsApp hour workspace changed? **No.**

---

# Phase 3 (this plan) — Adopt lifecycle on existing report rows (optional, small)

Not WhatsApp ingest Phase 3.

- Backfill: existing `reports` rows `lifecycle=draft` except those already linked as `capture_sessions.report_id` (those are **issued** corp sitreps — set `lifecycle=issued`, `issued_at=sitrep_generated_at` or `created_at`).
- WhatsApp `whatsapp_hour_briefing` rows stay `draft` and keep the provisional banner. No Issue button on `/dmu/whatsapp`. Optional: Issue on `/dmu/reports/$id` still allowed; the banner stays in the markdown.
- List page: filter chip Draft | Issued | All.

Skip this phase if Phase 1–2 already treat missing `lifecycle` as draft and corp-issued reports are identifiable via `capture_sessions.report_id` in the UI without a backfill. Prefer the backfill so corp issued sitreps cannot be “refreshed” as minister drafts.

- [ ] Self-review: a corp-issued sitrep opened from `/dmu/reports/$id` shows Issued and cannot Refresh.

---

## Deferred (named, not silent)

| Item | Why |
|---|---|
| Freehand markdown edit | Citation checker and quality scores assume generated prose. |
| Chat that writes store counts | Diverges from `sitrep_incidents`; use corp/WhatsApp fact workspaces. |
| Auto-generate on every turn | Corp Decision 5; officer waits on Refresh. |
| Unifying WhatsApp live briefing into this module | Phase 3 of the ingest plan; different object. |
| Stopping WhatsApp promote auto-create events | Already deferred on the ingest plan. |
| Document version history beyond issued snapshots | Issued rows + Revise clones are enough. |
| AuthZ on generate/refresh/issue | Follow whatever `main` does for `/reports` after Phase 3; do not invent a new permission model here. |

---

## Implementation notes for the later branch

1. Branch from **then-current `main`** (Phase 3 already merged). Do not branch from the WhatsApp ingest feature branch.
2. Confirm Alembic head; revise that id.
3. Keep FakeLLM: a minister refresh/issue path must work with `LLM_PROVIDER=fake` (canned narration from the fact table already exists for report JSON payloads).
4. Demo verification uses a **fresh sqlite**, not `dev.db` (API tests delete it).
5. Do not estimate calendar time. If the work splits, ship Phase 1 alone.
