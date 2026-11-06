# Officer UI Redesign: Design and Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the DMU officer pages fit the officer's real jobs: see who to chase during an event, issue a report the Minister can read, and work with verified Survey123 data afterwards.

**Architecture:** The backend gains a small "report identity" (kind, title, period, verified, older format) so no page shows raw templates or params. Reports store their clean text. The frontend gets one page container, one vocabulary, dialogs for creating things, and sheets for supporting detail.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, pytest (`apps/backend`, `uv run pytest`); React, TanStack Router and Query, shadcn UI, Vitest (`apps/frontend`, `npm test`).

**Spec:** Part 1 of this document, read with `docs/reporting-flow.md` (the three-report model).

---

# Part 1: Design

## What the live app showed (5 November 2026)

Reviewed at `app.rural.climate.lab.tt` as a DMU user, read-only.

| Page | What an officer sees | Problem |
|---|---|---|
| Dashboard | Red "10 reports need review" banner; cards reading 15581, 64, 10, "connected" | Every report is flagged, so the banner stops meaning anything. The cards prompt no action, and "connected" can never read anything else. |
| Dashboard | "Who has reported": 1 row filled, 13 "No reports at this time", over a 30-day window | Too long a window for hourly reporting. The list sits below the fold, and the corporations to chase are at the bottom. |
| Reports | Rows titled "Minister Situation Report v1" with `Date From: … · Date To: …` | All rows look alike. Status is the same on every row. There are two Generate buttons. A retired "Whatsapp Hour Briefing" is mixed in. |
| Report | Title is `Report 042600c0-f118-…` | The document starts about three screens down, after rating, parameters, metrics and a long list of raw codes such as `invented_number`. |
| Report | Fact table beside the document | Clipped sideways, and 22 rows of mostly "Data Coverage". It competes with the document. |
| Report | Six "Claims needing a verdict" above the document on a corporation report | Review work blocks reading. |
| Generate | Template dropdown with one option, shown as `minister_situation_report` | Internal names, labels generated from field names, free text for Hazard. |
| Field data | Page titled "Ingest", telling users to "go to /corp"; the table starts below two forms | The table is what they come for. The Survey123 template download isn't needed, since they export from ArcGIS. |
| Corporation | Date filter, four cards, a one-block alert strip, filing table, events table | Filings and events are separate tables. Event "titles" are whole sentences of officer text. |
| All | Dates appear as `Nov 04, 2026`, `2026-11-04 18:25` and `dd/mm/yyyy` | Three formats, one of them American-style in a Trinidad system. |

**Missing entirely:** no way to print or get a clean copy of a report from the DMU side. The report page shows only the version with citation markers, and the `reports` table doesn't store the clean version.

## Design principles

1. **Organise around the officer's jobs.** During an event: who to chase, and issue the minister report. After an event: upload and report on verified data. For one corporation: its status and filings.
2. **The document comes first.** Supporting detail lives in sheets, opened on request.
3. **Verified or unverified is always visible** wherever a report appears.
4. **No internal words.** Officers never see template, params, metric, ingest, submission, CID or a report UUID.
5. **Create in dialogs.** Lists stay on screen behind them.

## Vocabulary

Use these terms everywhere, and test copy against this table.

| Say | Instead of |
|---|---|
| Report | briefing, sitrep (in UI labels), template |
| Corporation report / Minister report / Survey123 summary | Corp Situation Report, minister_situation_report |
| Filing | submission |
| Uploaded | ingested |
| Dashboard | Overview |
| Field data | Ingest |
| Corporation (as a source label) | SITREP |
| Survey123 (as a source label) | Field |
| Sources | fact table, metrics used |
| Ready | OK |

Dates: `4 Nov 2026` and `4 Nov 2026, 18:25` everywhere; `1 Jan – 2 Nov 2026` for periods.

## Pages

**Shell.** All DMU pages sit in one centred container, `max-w-6xl`, matching corporation pages' `max-w-5xl` in spirit. Documents use `max-w-[46rem]`. The header subtitle "Cited briefings" goes.

**Sidebar.** Dashboard, Reports, Incidents & logs, Field data, then a collapsible **Corporations** group of all 14 with a dot for the latest alert level. It opens automatically on a corporation page. Administration stays at the bottom.

**Dashboard.** Two panels.
- *Left:* three cards, then Recent reports (title, type, status, when).
  - **Reporting:** "1 of 14 in the last 24 hours".
  - **Reports to review:** count, linking to the filtered list. Older-format reports are not counted.
  - **Highest alert:** level and corporation.
- *Right:* **Who has reported.** A headline count and a window choice of 24 hours, 7 days or 30 days, with no date inputs. Corporations not reported in the window come first, each showing when they last filed ("Last filed 2 days ago" or "Never filed"). Then those reported, most severe alert first, with time since filing and alert badge. Each row links to the corporation.
- *Removed:* API card, all-time Survey123 and corporation counts (Survey123's moves to Field data), the two header buttons (the sidebar and dialogs cover them).

**Reports.** One toolbar: search, type tabs (All, Corporation, Minister, Survey123), status filter, and a single "New report" button. Columns: Report (title, with period underneath), Type (badge plus Verified or Unverified), Status, Created. The whole row opens the report. Params and version go.

**New report dialog.** Opened from Reports, or from Field data with Survey123 preselected.
- Choose Minister report or Survey123 summary.
- *Survey123 summary:* date range and optional corporation.
- *Minister report:* date range, then as-at (defaults to now), hazard (dropdown), present activity, alert wording, and optional Ministry overview and response in a second step. Editing a report after generation is **deferred** (decided 5 November), so these sections have to be written before generating.
- Corporation reports aren't offered, as they come from capture. The `/dmu/reports/new` page goes away.

**Report page.**
- Header: readable title, type badge, Verified or Unverified, period, created time. Actions: **Print**, **Sources**, and **Review** (only when there's something to review).
- Body: the clean document at reading width.
- If it needs review, a one-line notice above the document: "3 figures could not be traced to their source. Review before issuing."
- **Sources sheet:** the source table full width, plus the template name and version and report ID in small text at the bottom, for traceability.
- **Review sheet:** problems in plain language, each with its sentence; claims needing a verdict; the rating. Opening it switches the document to show citation markers and highlights.
- **Print view:** clean document with a small header (report title, verified status, "Needs review" if it applies). Printing isn't blocked for reports needing review.

**Older-format reports.** Anything made before the YAML templates (version below 100), including the WhatsApp briefing, shows an "Older format" badge and is hidden from the default list, with a toggle to show it. The figures in those reports weren't produced by the current rules, and the banner shouldn't count them.

**Field data.** Table first. Header: count of records and last upload, with **Upload** and **Generate report** buttons that open dialogs. Upload results and rejections show in the dialog. Add a corporation filter. Remove the Survey123 template download.

**Corporation page.** Header: name, current alert badge, last filed. Tabs:
- **Filings** (default): grouped by event, newest first. Each group shows event title, hazard and running or ended. Each row shows number, as-at, alert, incident and log counts, and links to the report.
- **Incidents** and **Situation logs:** the Incidents & logs view locked to this corporation.
- *Removed:* date filter, four stat cards, alert strip, separate events table, "Back to overview".

**Incidents & logs.** Unchanged, apart from vocabulary and dates.

## Not in this plan

- Editing a minister report after generation (deferred).
- An "Overdue" status: it needs a reporting-frequency rule from the stakeholder. Until then the dashboard shows time since last filing.
- Corporation account pages, apart from shared date formats and labels.

## Noticed, for later

- **Events never end.** There's no way to close an event in the UI, so Arima has three "Still running". Filings can't be tied to a "current event" until this exists.
- **Event titles are whole sentences,** because the proposed title comes from the officer's overview. The hazard can also be wrong: a flood alert was recorded as Landslide because it follows the first incident. The redesign clips long titles; fixing the proposal is corporation-side work.

---

# Part 2: Implementation Plan

## Global Constraints

- Use the vocabulary table and date formats above in all new and changed copy.
- Verified means `kind == "survey123"`. Corporation and minister reports are unverified.
- Older format means `template_version < 100`.
- No report mixes sources; nothing in this plan changes report content or calculations.
- Issued reports stay immutable. No editing controls.
- Corporation routes keep working: extract shared code, don't move their behaviour.
- All new endpoints and fields sit behind the existing login rules. A corporation user must not gain access to any DMU view.

## Review Focus

1. **A report still generating or failed** has no document. The page shows its state, and Print, Sources and Review are hidden. Test in Task 4.
2. **Older reports with no stored clean text.** They fall back to the citation-stripped text. Test in Task 1.
3. **A report with blank or missing params** (a corporation report without `submission_id`, or a minister report with one date) still gets a sensible title and period. Test in Task 1.
4. **A corporation with no filings at all** shows "Never filed" on the dashboard, a grey sidebar dot, and an empty state on its page, not an error or a zero that reads as "nothing happened". Tests in Tasks 7 and 8.
5. **Upload rejected in the dialog.** The dialog stays open and shows the message, and the table doesn't change. Test in Task 6.

---

### Task 1: Report identity and stored clean text

**Files:**
- Create: `apps/backend/app/core/report_identity.py`, `apps/backend/alembic/versions/<rev>_report_final_markdown.py` (down_revision `e7d2b5c04a91`), `apps/backend/tests/test_report_identity.py`
- Modify: `app/core/report_models.py` (`final_markdown: Text, nullable`), `app/core/report_store.py` (save it; add a `kind` filter and `include_older` to `list_reports`), `app/api/reports.py`, `app/api/overview.py`, `src/types/dmcu.ts`, `src/lib/api/reports.ts`

**Interfaces:**
- `report_kind(template: str) -> Literal["corporation", "minister", "survey123", "other"]`: `corp_situation_report`, `minister_situation_report`, `survey123_summary` and `field_data_region_review` (survey123); anything else is `other`.
- `report_title(template: str, params: dict, report_number: int | None) -> str`: `"Arima Borough Corporation report #2"`, `"Minister report"`, `"Survey123 summary"` or `"Survey123 summary: Arima Borough Corporation"`, `"WhatsApp briefing"` for the retired template, otherwise the template name humanised.
- `report_period(params: dict) -> str | None`: `"1 Jan – 2 Nov 2026"`, `"From 1 Jan 2026"`, `"To 2 Nov 2026"`, or `None`.
- `clean_markdown(row: Report) -> str`: `row.final_markdown` or `strip_citation_markup(row.markdown)`.
- List and overview items add `kind`, `title`, `period`, `verified: bool`, `older_format: bool`. Detail adds the same plus `final_markdown` (via `clean_markdown`).
- `GET /reports` adds `kind: str | None` and `include_older: bool = False`.
- `needs_review_count` in the overview counts only `template_version >= 100`.

- [ ] **Step 1: Write failing tests:**
  - `test_kind_for_each_template`
  - `test_title_for_a_corporation_report_with_a_number`
  - `test_title_without_a_corporation_still_reads`
  - `test_period_formats` (both dates, one date, none, blank strings)
  - `test_clean_markdown_falls_back_to_stripping_old_reports`
  - `test_generated_report_stores_final_markdown`
  - `test_reports_filter_by_kind`
  - `test_older_reports_are_hidden_unless_asked`
  - `test_overview_review_count_ignores_older_reports`
  - `test_report_final_markdown_migration_round_trips`
- [ ] **Step 2: Run** `uv run pytest tests/test_report_identity.py -v`. Expected: FAIL (module not found).
- [ ] **Step 3: Implement.** Read `report_number` from `fact_table.params` when present.
- [ ] **Step 4: Run** `uv run pytest`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(reports): readable report identity and stored clean text`

### Task 2: One container, one vocabulary, one date format

**Files:**
- Modify: `src/routes/dmu.tsx` (wrap `Outlet` in `mx-auto w-full max-w-6xl space-y-6`), `src/lib/format-when.ts`, `src/components/app-sidebar.tsx`, `src/components/shared/source-badge.tsx`, `src/components/shared/status-badge.tsx`, page titles and descriptions across `src/routes/dmu/`, and `src/lib/format-when` tests
- Test: `src/lib/format-when.test.ts`, `src/components/shared/source-badge.test.tsx`

**Interfaces:**
- `formatWhen` returns `4 Nov 2026, 18:25`; `formatDay` returns `4 Nov 2026`. Locale `en-GB`, 24-hour.

- [ ] **Step 1: Write failing tests:** `formatWhen('2026-11-04T18:25:00')` is `4 Nov 2026, 18:25`; `formatDay('2026-06-30')` is `30 Jun 2026`; source badge reads `Corporation` and `Survey123`; status badge reads `Ready` for `ok`.
- [ ] **Step 2: Run** `npm test -- format-when source-badge`. Expected: FAIL.
- [ ] **Step 3: Implement.** Retitle Overview to Dashboard and Ingest to Field data; rewrite page descriptions in plain words; remove "Cited briefings" and any "/corp" text.
- [ ] **Step 4: Verify.** `grep -rniE "briefing|ingest(ed)?\b|citation-checked" src/routes/dmu src/components/app-sidebar.tsx` finds no user-visible text. `npm test` and `npx tsc --noEmit` pass.
- [ ] **Step 5: Commit** `feat(dmu): shared container, plain vocabulary and one date format`

### Task 3: Reports list

**Files:**
- Create: `src/components/reports/report-type-badge.tsx` and its test
- Modify: `src/routes/dmu/reports/index.tsx`, `src/lib/queries/reports.ts`, `src/lib/api/reports.ts`

**Interfaces:**
- Consumes: Task 1 fields and filters.
- Produces: `ReportTypeBadge({ kind, verified, olderFormat })`, shown wherever a report is listed.

- [ ] **Step 1: Write failing tests:** the badge shows `Minister · Unverified`, `Survey123 · Verified` and `Older format`, and each kind looks visually distinct (assert a distinct class). The list shows title and period and no text matching `Date From` or `v1`.
- [ ] **Step 2: Run** `npm test -- report-type-badge`. Expected: FAIL.
- [ ] **Step 3: Implement** type tabs, status filter, "Show older reports" switch, a single New report button, and whole-row links.
- [ ] **Step 4: Run** `npm test` and `npx tsc --noEmit`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(reports): tell report types apart in the list`

### Task 4: Report page, sheets and print

**Files:**
- Create: `src/components/reports/report-sources-sheet.tsx`, `src/components/reports/report-review-sheet.tsx`, `src/components/reports/report-print-document.tsx`, `src/routes/dmu/reports/$reportId.print.tsx`, and tests
- Modify: `src/routes/dmu/reports/$reportId.tsx`, `src/components/reports/violations-panel.tsx`, `src/routes/corp/print.$sessionId.tsx` (use the shared print document)

**Interfaces:**
- `violationMessage(kind: string, token?: string | null): string`: `invented_number` becomes "The figure {token} doesn't match any source."; `missing_citation` becomes "This sentence has a figure with no source."; `misattributed_number` becomes "The figure {token} belongs to a different source."; `empty_narrative` becomes "The report cites no sources."
- `ReportPrintDocument({ title, statusLine, markdown })`, used by both print routes.

- [ ] **Step 1: Write failing tests:**
  - The page heading is the report title and no UUID appears outside the Sources sheet.
  - `Parameters`, `Metrics used` and `Fact table` aren't on the page by default.
  - The clean document contains no `[C001]`; opening Review shows markers.
  - Review appears only with violations or pending claims.
  - `queued`, `running` and `failed` show their state and hide Print, Sources and Review.
  - `violationMessage` covers all four kinds and never returns a raw code.
  - The print route shows the status line and "Needs review" when it applies.
- [ ] **Step 2: Run** `npm test -- report-`. Expected: FAIL.
- [ ] **Step 3: Implement.** The Print button opens the print route in a new tab, which calls `window.print()`, as the corporation route does.
- [ ] **Step 4: Run** `npm test` and `npx tsc --noEmit`. Expected: PASS. Corporation print tests still pass.
- [ ] **Step 5: Commit** `feat(reports): document-first report page with sources, review and print`

### Task 5: New report dialog

**Files:**
- Create: `src/components/reports/new-report-dialog.tsx` and its test
- Delete: `src/routes/dmu/reports/new.tsx`, `src/components/dmu/survey123-report-card.tsx` and its test, `paramInputKind` in `src/lib/templates.ts` if unused
- Modify: `src/routes/dmu/reports/index.tsx`

**Interfaces:**
- `NewReportDialog({ open, onOpenChange, initialKind?: "minister" | "survey123" })`. Posts `minister_situation_report` or `survey123_summary`, drops blanks, and navigates to the new report.
- Hazard options: Adverse weather, Flood, Landslide, High wind, Fire, Other. It stores the display text the report title uses.
- `as_at` defaults to the current Trinidad wall-clock time.
- A link or bookmark to `/dmu/reports/new` redirects to `/dmu/reports`.

- [ ] **Step 1: Write failing tests:**
  - Survey123 asks only for dates and optional corporation, and defaults to 1 January through today.
  - Minister shows dates first, then a second step with the Ministry sections, and can be submitted with them blank.
  - `date_to` before `date_from` blocks submission with a message.
  - The right payload is posted for each kind, then it navigates to the report.
  - A failed request keeps the dialog open and shows the error.
- [ ] **Step 2: Run** `npm test -- new-report-dialog`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `npm test`, `npx tsc --noEmit` and `npx tsr generate`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(reports): create reports from a dialog`

### Task 6: Field data page

**Files:**
- Create: `src/components/dmu/upload-field-data-dialog.tsx` and its test
- Modify: `src/routes/dmu/field-data.tsx`, `src/lib/csv-templates.ts` (remove the Survey123 template if unused), `app/modules/incident_list.py` only if a last-upload value is needed, `app/api/overview.py` (`survey123_last_uploaded_at`)

- [ ] **Step 1: Write failing tests:**
  - The table renders first, with no upload form on the page.
  - Upload opens a dialog; success shows counts and duplicates and refreshes the table.
  - A rejected file keeps the dialog open with the server's message, and the table doesn't refetch.
  - Generate report opens the dialog with Survey123 preselected.
  - The corporation filter passes `corporation` to the request.
- [ ] **Step 2: Run** `npm test -- upload-field-data`. Expected: FAIL.
- [ ] **Step 3: Implement.** Show `15,581 records · last upload 2 Nov 2026` in the header.
- [ ] **Step 4: Run** `npm test`, `npx tsc --noEmit` and `uv run pytest`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(field-data): table first, with upload and report dialogs`

### Task 7: Dashboard

**Files:**
- Create: `src/components/dmu/who-has-reported.tsx` and its test
- Modify: `src/routes/dmu/index.tsx`, `src/lib/who-reported.ts` and its test

**Interfaces:**
- `deriveWhoReported(submissions: SubmissionSummary[], now: Date, windowHours: 24 | 168 | 720) -> { reportedCount, rows }`.
- Each row: `{ corporation, label, latest, inWindow: boolean }`. Rows out of window come first, in corporation order; then rows in window, most severe alert first.
- All submissions are fetched with no date filter, so "Last filed 2 days ago" works for any window.

- [ ] **Step 1: Write failing tests:**
  - A filing 25 hours old is out of window at 24 hours and in window at 7 days.
  - Out-of-window rows come before in-window rows.
  - A corporation with no filings shows "Never filed".
  - One with an old filing shows "Last filed 2 days ago".
  - The headline reads `1 of 14 in the last 24 hours`.
  - The dashboard has no `API`, `Survey123 incidents` or `SITREP incidents` text.
- [ ] **Step 2: Run** `npm test -- who-`. Expected: FAIL.
- [ ] **Step 3: Implement** the two-panel layout (`lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]`, stacking on small screens) and the three cards.
- [ ] **Step 4: Run** `npm test` and `npx tsc --noEmit`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(dmu): dashboard answers who to chase`

### Task 8: Corporation page and sidebar

**Files:**
- Create: `src/lib/group-filings.ts` and its test
- Modify: `src/routes/dmu/corporations/$corporation.tsx`, `src/components/dmu/records-view.tsx` (add `lockedCorporation?: string`), `src/components/app-sidebar.tsx` and its test
- Delete: `src/components/dmu/alert-trajectory.tsx` and its test, if nothing else uses it

**Interfaces:**
- `groupFilingsByEvent(filings: SubmissionSummary[], events: EventSummary[]) -> { event: EventSummary | null, filings: SubmissionSummary[] }[]`: newest group first; filings with no event go in a final "No event" group.

- [ ] **Step 1: Write failing tests:**
  - Filings group under their event and order newest first.
  - No filings shows the empty state: "This corporation has filed nothing yet. That's a gap to chase, not a report of no incidents."
  - Locked `RecordsView` hides the corporation filter and always sends that corporation.
  - The sidebar lists all 14 in a collapsible group, open when on a corporation page, closed elsewhere.
  - The dot uses the alert colour, and grey for no filings.
  - Corporation users don't see the group.
- [ ] **Step 2: Run** `npm test -- group-filings app-sidebar records-view`. Expected: FAIL.
- [ ] **Step 3: Implement.** Clip long event titles to two lines, with the full text as a tooltip.
- [ ] **Step 4: Run** `npm test` and `npx tsc --noEmit`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(dmu): corporation page by event, corporations in the sidebar`

### Task 9: Check it in the running app

- [ ] **Step 1:** Start the app with data and go through each DMU page in a browser at 1440px and 1024px wide. Expected: nothing clipped, and no internal words.
- [ ] **Step 2:** Generate one Survey123 summary and one minister report, and print each. Expected: clean documents with the right status line.
- [ ] **Step 3:** Ask Devon to log into a corporation account, and check capture, the draft pane and printing. Expected: unchanged apart from dates and labels.
- [ ] **Step 4:** Record screenshots against the table in Part 1, and fix anything found with a test first.

## Suggested order

Tasks 1–4 first, because they affect what reaches the Minister. Then Task 7 (dashboard), Task 5 and 6 (dialogs), Task 8 and Task 9. Task 2 is listed early because later tasks build on its container and date format.

## Questions for the stakeholder

1. How often should a corporation report during an event, and does it depend on alert level? This unlocks an "Overdue" status.
2. Should printed reports show "Unverified" or "Verified"? The plan shows it in a small header, outside the document's own format.
