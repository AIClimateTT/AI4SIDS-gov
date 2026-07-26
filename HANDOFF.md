# DMCU Reporting System — Session Handoff

**Date:** 2026-07-19
**Repo:** `AI4SIDS-repos/gov` (Disaster Management Coordinating Unit reporting backend + frontend, Trinidad & Tobago)
**Branch:** `main` (working directly on main this whole session, no worktree — by explicit user choice)

Use this doc to pick up in a new chat: what shipped, what's mid-flight, what's uncommitted, and the open design questions.

---

## 1. What shipped this session (committed + pushed to `origin/main`)

### Plan A — DB-backed versioned templates + MCP-pluggable data modules
Plan file: `docs/superpowers/plans/2026-07-16-db-templates-and-mcp-modules.md`
Commits: `61bf040..4532125` (8 tasks + 1 post-review fix, all individually reviewed, final whole-branch review clean)

Driven by technical-advisor feedback: (1) report templates shouldn't be rigid YAML files needing a redeploy to add a metric, and (2) data-module queries should be exposed over MCP so a larger LLM has more direct pull access — while explicitly **not** letting the LLM choose which data to query, and **not** building per-request metric exclusion (confirmed unnecessary — usage is additive/read-only, not selectable).

- Templates moved from `app/templates/definitions/*.yaml` (loaded into an in-memory registry at startup) to a versioned `report_templates` DB table (`app/core/template_store.py`), additive-only (each edit = new version row, never edited in place). `Report.template_version` now freezes which version produced a given report, for reproducibility.
- CLI: `cli.py templates import <path>` / `templates import-all <dir>` replace automatic YAML loading — this is the actual "add a metric later without redeploying" workflow.
- A reference MCP server (`app/mcp_server/survey123_server.py`) exposes the existing `survey123` metric functions as MCP tools; a client adapter (`app/core/mcp_module.py`'s `McpDataModule`) conforms to the same `DataModule` protocol as the in-process module; `settings.survey123_transport` switches between them. **`app/core/engine.py` never changes** regardless of which is registered — it always calls `module.run_metric(...)` as a plain function call. This is the core architectural proof of that half of the plan.
- Found+fixed a real bug along the way: `McpDataModule`'s draft code raised `ValueError` for MCP tool errors *inside* nested `async with` blocks, which anyio's `TaskGroup` wraps into a `BaseExceptionGroup` on unwind — moved the raise outside the context managers. Independently re-verified by the reviewer.
- Post-review fix: `alembic/env.py` was missing the `template_models` import, so a future `alembic revision --autogenerate` would have tried to drop the `report_templates` table. Fixed.

### Plan B — Sitreps data module (corp-entered incident data)
Plan file: `docs/superpowers/plans/2026-07-18-sitreps-module.md`
Commits: `55f1d9b..b96b19f` (4 tasks, all reviewed, final whole-branch review clean)

Driven by inspecting three real example sitrep documents (still sitting at repo root: `TPRC SITREP 18th May , 2025.docx`, `Borough of Diego Martin Situation Report #4- Adverse Weather.docx`, `Full Sitrep 2023.docx`). Insight: corp sitreps use non-standard, inconsistent formats — having an LLM parse them to extract numbers would be exactly the hallucination risk the citation-checker system exists to prevent. Fix: let corps enter their own incidents as **structured data** (CSV, Google-Sheets-friendly) that reuses the *existing* `Incident` table shape, rather than any document-parsing pipeline.

- Added one `source` column to the shared `incidents` table (backward compatible — `survey123` behavior unchanged by default). `build_citation`/`apply_common_filters` in `app/modules/survey123/metrics.py` are now source-aware.
- `app/modules/sitreps/ingest.py`: CSV ingest reusing survey123's existing pure parsing helpers (no duplicated logic). PII (name, contact info) is **never written to the DB at all** — verified by an independent reviewer reading the code line-by-line, not just trusting a test.
- `app/modules/sitreps/module.py`: `SitrepModule` delegates to the *same* metric functions `Survey123Module` uses, injecting `source="sitreps"`. A test proves cross-source isolation by ingesting both sources into one DB and confirming each module only sees its own rows (reviewer independently traced this to confirm it's a genuinely discriminating test, not a coincidence).
- CLI: `cli ingest sitreps <corporation> <file>`. Registered alongside `survey123` in `create_app()`.
- **Explicitly out of scope / not built:** a separate preparedness/status-log table (distinct concept — corp readiness state like "sandbags available," not tied to an incident), new report templates that consume sitreps data, live Google Sheets API integration (current path is CSV export/upload only).

### Incidental fix (its own commit, `a211188`, bundled with Plan B)
Found the test suite broken (5 collection errors) from an in-progress, uncommitted move of `app/main.py`'s content into `app/__init__.py` (5 test files still imported `from app.main import ...`). Fixed the imports. Also found a `.env` pointing `DATABASE_URL` at a real Postgres (`localhost:5434`) that was leaking into test runs (tests were hitting a shared, already-populated DB instead of an isolated sqlite file). Added `tests/conftest.py` forcing an isolated sqlite DB for the test session regardless of `.env`.

### Minor open follow-ups (non-blocking, noted by reviewers)
- `app/modules/sitreps/ingest.py`: a malformed/missing `Row ID` in a sitrep CSV raises an uncaught `ValueError` (`int(row_id)`), aborting the whole ingest batch with no row-level error reporting. Mirrors an existing weakness in survey123's own ingest, but sitrep data is manually corp-entered (more failure-prone). Worth hardening later.
- `object_id` on sitrep-sourced incidents is only unique within `(source, corporation)`, not globally — harmless today, no unique constraint depends on it, but worth a comment if anything ever assumes global uniqueness.
- `create_template_version`'s version-increment is read-then-write (not atomic) — fine for the current single-writer CLI usage, would need a retry/lock if ever called from concurrent API requests. A one-line comment documenting this assumption was added.

**Full commit range this session:** `588990b..b96b19f` (main was pushed to origin at both checkpoints).

---

## 2. Uncommitted work currently sitting in the working tree — NOT mine, NOT reviewed

Running `git status --short` right now shows a large, pre-existing set of uncommitted changes that were present **before this session started** and were still there, unchanged, at the end of it. This looks like parallel work (possibly via Cursor — there's an untracked `.cursor/` directory — or another session) building out:

- A templates CRUD API (`app/api/templates.py` new, untracked) and matching frontend (`apps/frontend/src/components/templates/`, `apps/frontend/src/routes/templates/` replacing the old single `templates.tsx`).
- A corp-specific report route (`apps/frontend/src/routes/reports/corp.tsx`, untracked) — interesting, this overlaps with the "corp-tailored" UX gap discussed below.
- Modifications to several backend files my subagents also touched (`app/core/engine.py`, `registry.py`, `report_models.py`, `report_store.py`, `template_store.py`, `app/api/meta.py`, `app/api/reports.py`, `app/__init__.py`) plus `app/core/llm.py`.
- A new migration file `apps/backend/alembic/versions/c4e8f1a2b903_add_data_requirements_to_reports.py` (untracked) and a `test_phase_b_templates.py` (untracked) — suggests a "Phase B" templates effort in progress.
- Frontend: `apps/frontend/src/lib/corporations.ts`, `format-constant.ts` (+ test), `templates.ts`, `src/components/forms/`, `src/components/reports/` — all untracked/new.

**None of this was touched, staged, or committed by me this session.** My subagents only ever `git add`ed the exact files named in their task briefs, so this other work was carried along untouched in the working tree the whole time. **Before doing anything with these files (including running the test suite, which may now behave differently) — read them and understand what they are.** Do not discard or overwrite without investigating; this may be someone else's in-progress work.

Run `git status --short` at the start of the new chat to see the current exact state — it will likely still match what's described above unless someone else has since committed or changed it further.

---

## 3. Open design conversation — frontend (not yet actioned, my last response in the prior chat)

The user asked me to inspect the frontend and give thoughts on: corp-tailored ingest/logging, report formatting for review/editing, citation-click-to-jump, and prompt quality (given the 3 example docx files). Nothing below has been implemented — this is pasted verbatim as the last thing discussed, to pick up from:

> I inspected the frontend and found there's also parallel backend work in progress (an `/overview` endpoint, changes to `ingest.py`/`reports.py`/`report_store.py`) that I haven't touched — it already reuses my `source` column correctly, so it's consistent with what I built, just uncommitted and not mine.
>
> **On the status/preparedness log:** No — that was explicitly scoped out of the sitreps plan as a deferred follow-up, not built.
>
> **On the frontend**, here's what I found and my thoughts, organized by your questions:
>
> **1. It's admin/dev-shaped, not corp-shaped — the ingest page is the clearest example.** `/ingest` today is one generic "pick a module, upload a CSV" form for both `survey123` and `sitreps` (`routes/ingest.tsx:8-24`). But a corp officer logging "1 landslide on Victoria Street" as it happens doesn't want to build a spreadsheet first — they want to log one incident. I'd add a second entry mode alongside CSV bulk-upload: a **"Log Incident" quick-entry form** mirroring `parse_sitrep_row`'s fields directly (community, street, incident type, date, injuries/deaths, damage, relief-action checkboxes) that posts one row at a time. That needs a small new backend endpoint (single-incident POST, not just CSV) — worth its own plan. I'd also lock/default the corporation field per-officer once there's any notion of login, rather than a global 14-corp dropdown every time.
>
> **2. Report generation is one generic form for every template.** For a corp's actual workflow, a simplified path — no template picker, no corporation dropdown, just "generate my situation report for [date range]" — would match how they'd actually use it, versus the ministry admin who genuinely needs the full template/param picker.
>
> **3. Report display is the biggest concrete gap, and it's not just cosmetic.** Right now: markdown renders as a raw `<pre>` block (`MarkdownPreview`'s own comment says "swap for a real renderer later"), and the fact table is a raw `JSON.stringify` dump (`$reportId.tsx:92-96`). Nothing connects a `[C001]` marker in the text to its fact. Concretely, I'd:
>    - Render markdown for real (e.g. `react-markdown`).
>    - Render the fact table as an actual table with anchors (`id="citation-C001"`), then post-process the rendered narrative to turn each `[C001]` into a clickable link that scrolls to and briefly highlights that row — this is exactly your "click to jump to section" ask, and it's a client-side transform, not a backend change.
>    - Surface violations inline (highlight the exact flagged sentence in place) rather than only as a separate list at the top — tightens the actual review loop.
>    - **Editing is the one part I'd stop and design deliberately, not bolt on.** Free-text editing of the narrative can silently reintroduce the exact hallucination risk the citation checker exists to prevent (someone types a number with no backing fact). If you want editing, I'd scope it to per-sentence edits with the citation marker locked/required, re-validated server-side through `check_citations` before save — that's a real design decision worth its own conversation, not a default I should assume.
>
> **4. The prompts can now be sharpened using the actual example docs.** The current templates use generic section names (`headline, streets, actions_taken...`). The real sitreps use recognizable, official-familiar headers — "Present Activity," "Alert Level," "Situation Overview," "As at [time] on [date]." The minister template's prompt could also literally mirror `Full Sitrep 2023`'s structure — one short paragraph per corporation, same order every time — rather than a combined narrative, which also sets up naturally for the corp-by-corp aggregate metric we discussed earlier.
>
> Given the size here, want me to turn any one of these (I'd start with #3, since it's the highest-leverage and lowest-risk) into a plan, or talk through the editing-safety design first?

**My recommendation for where to pick up:** start with #3 (report display/citation-click) — it's purely additive frontend work reading already-existing backend data, lowest risk, highest visible payoff. The "editing" sub-question inside #3 needs its own design conversation before any implementation (risk: undermining the citation-checker's guarantee). #1/#2 (corp-tailored ingest/generate UX) need a small new backend endpoint (single-incident POST) not yet planned. #4 (prompt rewrite using the docx examples) is backend-only (`app/templates/definitions/*.yaml` content, or their DB-stored equivalents) and could be done independently of the frontend work.

---

## 4. Key file map for orientation

- `docs/superpowers/plans/2026-07-16-db-templates-and-mcp-modules.md` — Plan A, done.
- `docs/superpowers/plans/2026-07-18-sitreps-module.md` — Plan B, done.
- `apps/backend/app/core/template_store.py` — versioned template DB store.
- `apps/backend/app/core/mcp_module.py` / `apps/backend/app/mcp_server/survey123_server.py` — MCP plumbing.
- `apps/backend/app/modules/sitreps/` — new sitreps module (ingest.py, module.py).
- `apps/backend/app/modules/survey123/metrics.py` — shared query/citation layer, now source-aware.
- `apps/backend/tests/conftest.py` — forces isolated sqlite for tests regardless of `.env`.
- `.superpowers/sdd/progress.md` (git-ignored, local only) — full subagent-driven-development ledger for both plans, task-by-task, with every reviewer's findings.
- Example sitrep docs at repo root: `TPRC SITREP 18th May , 2025.docx`, `Borough of Diego Martin Situation Report #4- Adverse Weather.docx`, `Full Sitrep 2023.docx` — referenced for the sitreps design and the prompt-improvement idea (#4 above).
- Persistent cross-session memory (not in this repo): `project_dmcu_template_mcp_architecture.md` and `project_dmcu_sitreps_module.md` under the assistant's memory directory — carries the "why" behind both plans forward automatically into future chats on this project.

---

## 5. Test baseline

`cd apps/backend && .venv/bin/python -m pytest -q` → **233 passed, 0 failures** as of `b96b19f` (before any of the uncommitted work in section 2 is touched). Re-check this first thing in a new chat, since the uncommitted files in section 2 may change that count once accounted for.
