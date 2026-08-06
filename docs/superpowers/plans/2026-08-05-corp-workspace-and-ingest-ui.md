# Corp Workspace and Ingest UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the browser able to do the whole job — a corporation declares an event, uploads its spreadsheets, sees exactly what landed and what was rejected, and the DMU sees who has reported.

**Architecture:** Adds a submission read API and persisted row errors to the backend, then builds the corp workspace (events → filings → result) and the two real upload forms on top. The corp workspace is organised around the event, because a multi-day storm is one event with a run of filings and the backend already numbers them.

**Tech Stack:** FastAPI, SQLAlchemy 2.x, Alembic, pytest · React 19, TanStack Router (file-based) + Query + Form, Tailwind 4, Vitest.

**Spec:** `docs/superpowers/specs/2026-07-27-corp-dmu-frontend-design.md` (plans 2 and 3 of its build order)

## Global Constraints

- **No authentication exists and none is added.** Identity is a `localStorage` declaration read via `useIdentity()`. The acting corporation comes from that context — never a dropdown on a corp-facing form. Do not add lock icons, "signed in as", or permission language.
- **A submission carrying incidents MUST name an event.** `POST /submissions` already returns 400 otherwise. Situation logs may be filed with no event. The UI must make this structural — reach the filing form *through* an event — not by validating a field.
- **Row numbers are already spreadsheet-relative.** `ingest_submission` enumerates from 2 because the header is row 1. The UI displays `row_number` **as-is**. Adding an offset would double-count and send an officer to the wrong line.
- **Blank CSV template downloads are required**, one per file type, with the exact headers the parser expects. Nobody can guess `Further Assessment Required`.
- **Every filter on `GET /submissions` is optional.** The corp event view passes `event_id`; the DMU dashboard passes only a window and needs all fourteen corporations back. Requiring `corporation` would make the DMU view impossible.
- **All database contents are disposable and migrations may change anything.** Choose the correct schema outright.
- **Backend tests:** `cd apps/backend && .venv/bin/python -m pytest`. Baseline **394 passed, 0 failed** — any failure is yours. **Frontend:** `cd apps/frontend && pnpm test` (28 passed) and `pnpm exec tsc --noEmit -p tsconfig.json`. Never add a `test` block to `vite.config.ts`.
- **Migrations must apply from empty:** `rm -f /tmp/m.db && DATABASE_URL="sqlite:////tmp/m.db" .venv/bin/python -m alembic upgrade head && ... alembic check`. SQLite has no `ALTER COLUMN` — use `op.batch_alter_table`. Current head is `47c3e3d7deb2`; confirm with `alembic heads` before writing a migration.
- **Re-seed to see changes:** `cd apps/backend && .venv/bin/python scripts/seed_demo.py` rebuilds Postgres from `fixtures/demo/`. It is destructive and reproducible.

---

## File Structure

**Backend — create:**
- `apps/backend/alembic/versions/<rev>_add_row_errors_to_submissions.py`

**Backend — modify:**
- `app/modules/sitreps/models.py` — `Submission.row_errors` JSON column.
- `app/modules/sitreps/ingest.py` — persist the row errors it already builds.
- `app/modules/sitreps/store.py` — `list_submissions`, `get_submission_detail`.
- `app/api/submissions.py` — `GET /submissions`, `GET /submissions/{id}`.

**Frontend — create:**
- `src/lib/api/submissions.ts`, `src/lib/queries/submissions.ts` — data layer.
- `src/lib/csv-templates.ts` — blank CSV headers + download helper (pure, tested).
- `src/routes/corp/events/new.tsx`, `src/routes/corp/events/$eventId/index.tsx`, `src/routes/corp/events/$eventId/file.tsx`, `src/routes/corp/submissions.tsx`
- `src/components/submissions/submission-result.tsx` — accepted/rejected summary.
- `src/components/submissions/csv-template-links.tsx`

**Frontend — modify:**
- `src/types/dmcu.ts` — submission and event types.
- `src/routes/corp/index.tsx` — events list, replacing the empty state.
- `src/routes/dmu/field-data.tsx` — the real Survey123 upload, replacing the placeholder.
- `src/routes/dmu/index.tsx` — who-has-reported panel.
- `src/components/app-sidebar.tsx` — corp nav gains its remaining items.

---

## Task 1: Persist row errors

**Files:** Modify `app/modules/sitreps/models.py`, `app/modules/sitreps/ingest.py`; create a migration. Test: `apps/backend/tests/test_sitreps_submission_ingest.py`.

**Interfaces produced:** `Submission.row_errors: list` (JSON, defaults `[]`).

- [ ] **Step 1: Write the failing test**

```python
def test_row_errors_are_persisted_on_the_submission(tmp_path):
    # Ephemeral row errors mean an officer who closes the tab loses the list of
    # what to fix and must re-upload to rediscover it.
    session = make_session(tmp_path)
    event = create_event(
        session, corporation=CORP, title="Storm", hazard_type="wind",
        started_at=datetime(2023, 6, 27),
    )
    path = write_csv(
        tmp_path, "bad.csv",
        ["Row ID", "Incident Type", "Date of Event"],
        [["1", "fire", "2023-06-27"], ["", "landslide", "2023-06-28"]],
    )

    result = ingest_submission(
        session, corporation=CORP, as_at=datetime(2023, 6, 30),
        event_id=event.id, incidents_path=path,
    )

    stored = session.get(Submission, result.submission_id)
    assert stored.row_errors == [
        {"file": "incidents", "row_number": 3, "reason": "Row ID is required"}
    ]
```

Add `Submission` to the imports at the top of that test file if it is not already there.

- [ ] **Step 2: Run it.** `cd apps/backend && .venv/bin/python -m pytest tests/test_sitreps_submission_ingest.py -q -k row_errors_are_persisted` → FAIL, `Submission` has no attribute `row_errors`.

- [ ] **Step 3: Add the column.** In `app/modules/sitreps/models.py`, on `Submission`:

```python
    # Persisted so an officer can reopen a filing and see what was rejected.
    # These are built during ingest anyway; keeping them only in the response
    # meant closing the tab lost them.
    row_errors: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
```

`JSON` is already imported in this module.

- [ ] **Step 4: Persist them.** In `ingest_submission` (`app/modules/sitreps/ingest.py`), the `Submission(...)` construction happens before rows are parsed — move the `row_errors=` assignment to just before the final `session.commit()`, so the list is complete:

```python
    submission.row_errors = [e.model_dump() for e in row_errors]
```

- [ ] **Step 5: Migration.** Confirm the head with `.venv/bin/python -m alembic heads`, then create a revision chaining off it:

```python
def upgrade() -> None:
    with op.batch_alter_table("submissions") as batch:
        batch.add_column(
            sa.Column("row_errors", sa.JSON(), nullable=False, server_default="[]")
        )


def downgrade() -> None:
    with op.batch_alter_table("submissions") as batch:
        batch.drop_column("row_errors")
```

- [ ] **Step 6: Verify.** `rm -f /tmp/m.db && DATABASE_URL="sqlite:////tmp/m.db" .venv/bin/python -m alembic upgrade head && DATABASE_URL="sqlite:////tmp/m.db" .venv/bin/python -m alembic check` — succeeds, no drift, single head. Then the full suite: 0 failed.

- [ ] **Step 7: Commit** `sitreps: persist row errors on the submission`

---

## Task 2: Submission read API

**Files:** Modify `app/modules/sitreps/store.py`, `app/api/submissions.py`. Test: `apps/backend/tests/test_api_submissions.py`.

**Interfaces produced:**
- `list_submissions(session, *, corporation=None, event_id=None, date_from=None, date_to=None) -> list[Submission]` — newest first, every filter optional.
- `GET /submissions` → `list[SubmissionSummary]`; `GET /submissions/{id}` → `SubmissionDetail`.
- `SubmissionSummary`: `id, corporation, event_id, event_title, as_at, alert_level, sequence_no, incident_count, log_count`
- `SubmissionDetail`: the above plus `present_activity, situation_overview, row_errors, source_file`

- [ ] **Step 1: Write the failing tests**

Append to `apps/backend/tests/test_api_submissions.py`, reusing its `client()` helper and `CORP`:

```python
def _event(c, corporation=CORP, title="Adverse Weather June 2023"):
    return c.post("/events", json={
        "corporation": corporation, "title": title, "hazard_type": "wind",
        "started_at": "2023-06-27T00:00:00"}).json()["id"]


def _file(c, event_id, corporation=CORP, as_at="2023-06-28T09:00:00", rows=1):
    body = "Row ID,Incident Type,Date of Event\n" + "".join(
        f"{i},fallen_tree,2023-06-27\n" for i in range(1, rows + 1)
    )
    return c.post(
        "/submissions",
        data={"corporation": corporation, "as_at": as_at, "event_id": event_id},
        files={"incidents_file": ("i.csv", io.BytesIO(body.encode()), "text/csv")},
    )


def test_list_submissions_is_newest_first_with_counts():
    c = client()
    event_id = _event(c)
    _file(c, event_id, as_at="2023-06-28T09:00:00", rows=1)
    _file(c, event_id, as_at="2023-06-30T16:00:00", rows=3)

    body = c.get("/submissions").json()

    assert [s["sequence_no"] for s in body] == [2, 1]
    assert body[0]["incident_count"] == 3
    assert body[0]["event_title"] == "Adverse Weather June 2023"


def test_list_submissions_with_no_filters_returns_every_corporation():
    # The DMU dashboard passes only a window and needs all corporations back.
    c = client()
    _file(c, _event(c), rows=1)
    other = "siparia_regional_corporation"
    _file(c, _event(c, corporation=other), corporation=other, rows=1)

    corps = {s["corporation"] for s in c.get("/submissions").json()}

    assert corps == {CORP, "siparia_regional_corporation"}


def test_list_submissions_filters_by_corporation_and_event():
    c = client()
    first, second = _event(c), _event(c, title="Second Event")
    _file(c, first, rows=1)
    _file(c, second, as_at="2023-07-02T09:00:00", rows=1)

    by_event = c.get("/submissions", params={"event_id": first}).json()
    by_corp = c.get("/submissions", params={"corporation": "arima_borough_corporation"}).json()

    assert [s["event_id"] for s in by_event] == [first]
    assert by_corp == []


def test_list_submissions_filters_by_window():
    c = client()
    event_id = _event(c)
    _file(c, event_id, as_at="2023-06-28T09:00:00", rows=1)
    _file(c, event_id, as_at="2023-07-15T09:00:00", rows=1)

    june = c.get(
        "/submissions", params={"date_from": "2023-06-01", "date_to": "2023-06-30"}
    ).json()

    assert len(june) == 1


def test_submission_detail_carries_row_errors_and_overview():
    c = client()
    event_id = _event(c)
    incidents = "Row ID,Incident Type,Date of Event\n,landslide,2023-06-27\n2,fire,2023-06-28\n"
    created = c.post(
        "/submissions",
        data={
            "corporation": CORP, "as_at": "2023-06-30T16:00:00", "event_id": event_id,
            "situation_overview": "Heavy rainfall affected the Borough.",
        },
        files={"incidents_file": ("i.csv", io.BytesIO(incidents.encode()), "text/csv")},
    ).json()

    detail = c.get(f"/submissions/{created['submission_id']}").json()

    assert detail["situation_overview"] == "Heavy rainfall affected the Borough."
    assert detail["row_errors"] == [
        {"file": "incidents", "row_number": 2, "reason": "Row ID is required"}
    ]


def test_submission_detail_404s_for_an_unknown_id():
    assert client().get("/submissions/99999").status_code == 404
```

- [ ] **Step 2: Run them.** All fail with 404 — the routes do not exist.

- [ ] **Step 3: Add the store functions.** In `app/modules/sitreps/store.py`:

```python
def list_submissions(
    session: Session,
    *,
    corporation: str | None = None,
    event_id: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> list[Submission]:
    """Newest first. EVERY filter is optional — the DMU dashboard passes only a
    window and must get all fourteen corporations back."""
    stmt = select(Submission)
    if corporation is not None:
        stmt = stmt.where(Submission.corporation == corporation)
    if event_id is not None:
        stmt = stmt.where(Submission.event_id == event_id)
    if date_from is not None:
        stmt = stmt.where(Submission.as_at >= date_from)
    if date_to is not None:
        # date_to arrives as a date-only string parsed to midnight; compare
        # against the start of the next day so the whole day is included.
        stmt = stmt.where(Submission.as_at < date_to + timedelta(days=1))
    stmt = stmt.order_by(Submission.as_at.desc(), Submission.id.desc())
    return list(session.scalars(stmt).all())


def submission_counts(session: Session, submission_id: int) -> tuple[int, int]:
    """(incidents, logs) attributed to this submission."""
    incidents = session.scalar(
        select(func.count()).select_from(SitrepIncident).where(
            SitrepIncident.submission_id == submission_id
        )
    ) or 0
    logs = session.scalar(
        select(func.count()).select_from(SituationLog).where(
            SituationLog.submission_id == submission_id
        )
    ) or 0
    return incidents, logs
```

Add `from datetime import timedelta` and import `SitrepIncident`, `SituationLog` from `app.modules.sitreps.models`.

- [ ] **Step 4: Add the endpoints.** In `app/api/submissions.py`:

```python
class SubmissionSummary(BaseModel):
    id: int
    corporation: str
    event_id: int | None
    event_title: str | None
    as_at: datetime
    alert_level: str
    sequence_no: int
    incident_count: int
    log_count: int


class SubmissionDetail(SubmissionSummary):
    present_activity: str | None
    situation_overview: str | None
    source_file: str | None
    row_errors: list


def _summary(session: Session, submission) -> SubmissionSummary:
    incidents, logs = submission_counts(session, submission.id)
    event = get_event(session, submission.event_id) if submission.event_id else None
    return SubmissionSummary(
        id=submission.id,
        corporation=submission.corporation,
        event_id=submission.event_id,
        event_title=event.title if event else None,
        as_at=submission.as_at,
        alert_level=submission.alert_level,
        sequence_no=submission.sequence_no,
        incident_count=incidents,
        log_count=logs,
    )


@router.get("/submissions", response_model=list[SubmissionSummary])
def get_submissions(
    corporation: str | None = None,
    event_id: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    session: Session = Depends(get_session),
) -> list[SubmissionSummary]:
    return [
        _summary(session, s)
        for s in list_submissions(
            session, corporation=corporation, event_id=event_id,
            date_from=date_from, date_to=date_to,
        )
    ]


@router.get("/submissions/{submission_id}", response_model=SubmissionDetail)
def get_submission(
    submission_id: int, session: Session = Depends(get_session)
) -> SubmissionDetail:
    submission = session.get(Submission, submission_id)
    if submission is None:
        raise HTTPException(status_code=404, detail=f"submission not found: {submission_id}")
    summary = _summary(session, submission)
    return SubmissionDetail(
        **summary.model_dump(),
        present_activity=submission.present_activity,
        situation_overview=submission.situation_overview,
        source_file=submission.source_file,
        row_errors=submission.row_errors,
    )
```

Import `Submission` from `app.modules.sitreps.models` and `list_submissions`, `submission_counts` from `app.modules.sitreps.store`.

**Route order matters:** `/submissions/{submission_id}` must be declared AFTER the existing `POST /submissions`; FastAPI matches in declaration order and a path param would otherwise shadow nothing here, but keep the GETs together below the POST for readability.

- [ ] **Step 5: Run the new tests and the full suite.** 0 failed.

- [ ] **Step 6: Commit** `api: add submission list and detail endpoints`

---

## Task 3: Frontend data layer and CSV templates

**Files:** Create `src/lib/api/submissions.ts`, `src/lib/queries/submissions.ts`, `src/lib/csv-templates.ts`, `src/lib/csv-templates.test.ts`. Modify `src/types/dmcu.ts`, `src/lib/api/ingest.ts`.

**Interfaces produced:**
- Types `EventSummary`, `SubmissionSummary`, `SubmissionDetail`, `SubmissionIngestResult`, `RowErrorInfo`, `CreateEventInput`, `FileSubmissionInput`
- `getEvents(corporation)`, `createEvent(input)`, `getSubmissions(params)`, `getSubmission(id)`, `fileSubmission(input)`
- `eventQueries.list(corporation)`, `submissionQueries.list(params)`, `submissionQueries.detail(id)`, `useCreateEvent()`, `useFileSubmission()`
- `INCIDENT_CSV_HEADERS: string[]`, `LOG_CSV_HEADERS: string[]`, `csvTemplateBlobUrl(headers): string`

- [ ] **Step 1: Write the failing test**

Create `src/lib/csv-templates.test.ts`:

```ts
import { describe, expect, it } from 'vitest'

import {
  INCIDENT_CSV_HEADERS,
  LOG_CSV_HEADERS,
  csvTemplateText,
} from '@/lib/csv-templates'

describe('csv templates', () => {
  it('matches the exact headers the incident parser reads', () => {
    // Nobody can guess "Further Assessment Required". These strings must stay
    // in step with parse_incident_row in the backend.
    expect(INCIDENT_CSV_HEADERS).toEqual([
      'Row ID', 'Community', 'Street', 'Incident Type', 'Date of Event',
      'Incident Summary', 'Injuries Occurred', 'Injuries Count',
      'Deaths Occurred', 'Deaths Count', 'Building Damage',
      'Special Needs Occupants', 'Estimated Damage Cost', 'Action Taken',
      'Relief Supplied', 'Forwarded To Agency', 'Further Assessment Required',
      'Other Follow Up',
    ])
  })

  it('matches the exact headers the log parser reads', () => {
    expect(LOG_CSV_HEADERS).toEqual([
      'Category', 'Statement', 'Item', 'Quantity', 'Unit', 'Status',
    ])
  })

  it('renders a header-only csv', () => {
    expect(csvTemplateText(['A', 'B'])).toBe('A,B\n')
  })

  it('quotes a header containing a comma', () => {
    expect(csvTemplateText(['A,B', 'C'])).toBe('"A,B",C\n')
  })
})
```

- [ ] **Step 2: Run it.** `cd apps/frontend && pnpm test src/lib/csv-templates.test.ts` → FAIL, module not found.

- [ ] **Step 3: Write `src/lib/csv-templates.ts`.**

```ts
/**
 * Blank CSV templates a corporation downloads before filling one in.
 *
 * These header strings must match parse_incident_row / parse_log_row in the
 * backend exactly — a mismatch means a column is silently ignored, which is
 * the failure the row-level error reporting exists to prevent.
 */
export const INCIDENT_CSV_HEADERS = [
  'Row ID', 'Community', 'Street', 'Incident Type', 'Date of Event',
  'Incident Summary', 'Injuries Occurred', 'Injuries Count',
  'Deaths Occurred', 'Deaths Count', 'Building Damage',
  'Special Needs Occupants', 'Estimated Damage Cost', 'Action Taken',
  'Relief Supplied', 'Forwarded To Agency', 'Further Assessment Required',
  'Other Follow Up',
] as const

export const LOG_CSV_HEADERS = [
  'Category', 'Statement', 'Item', 'Quantity', 'Unit', 'Status',
] as const

export function csvTemplateText(headers: readonly string[]): string {
  const escaped = headers.map((h) =>
    h.includes(',') || h.includes('"') ? `"${h.replace(/"/g, '""')}"` : h,
  )
  return `${escaped.join(',')}\n`
}

export function downloadCsvTemplate(filename: string, headers: readonly string[]): void {
  const blob = new Blob([csvTemplateText(headers)], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}
```

- [ ] **Step 4: Add the types.** Append to `src/types/dmcu.ts`:

```ts
export type EventSummary = {
  id: number
  corporation: string
  title: string
  hazard_type: string
  started_at: string
  ended_at: string | null
}

export type CreateEventInput = {
  corporation: string
  title: string
  hazard_type: string
  started_at: string
}

export type RowErrorInfo = {
  file: 'incidents' | 'logs'
  /** Spreadsheet row — the header is row 1. Display as-is; the backend
   *  already offsets it, so adding another would send an officer to the
   *  wrong line. */
  row_number: number
  reason: string
}

export type SubmissionSummary = {
  id: number
  corporation: string
  event_id: number | null
  event_title: string | null
  as_at: string
  alert_level: string
  sequence_no: number
  incident_count: number
  log_count: number
}

export type SubmissionDetail = SubmissionSummary & {
  present_activity: string | null
  situation_overview: string | null
  source_file: string | null
  row_errors: RowErrorInfo[]
}

export type SubmissionIngestResult = {
  submission_id: number
  sequence_no: number
  incidents_read: number
  incidents_inserted: number
  incidents_updated: number
  logs_read: number
  logs_inserted: number
  row_errors: RowErrorInfo[]
  unmapped_values: Record<string, string[]>
  pii_columns_dropped: string[]
}

export type FileSubmissionInput = {
  corporation: string
  as_at: string
  event_id?: number
  alert_level: string
  present_activity?: string
  situation_overview?: string
  incidentsFile?: File
  logsFile?: File
}
```

- [ ] **Step 5: Write `src/lib/api/submissions.ts`**, following the shape of `src/lib/api/reports.ts`:

```ts
import { apiClient } from '@/lib/api/client'
import { withApiError } from '@/lib/api/errors'
import type {
  CreateEventInput,
  EventSummary,
  FileSubmissionInput,
  SubmissionDetail,
  SubmissionIngestResult,
  SubmissionSummary,
} from '@/types/dmcu'

export async function getEvents(corporation: string): Promise<EventSummary[]> {
  return withApiError(async () => {
    const { data } = await apiClient.get<EventSummary[]>('/events', {
      params: { corporation },
    })
    return data
  })
}

export async function createEvent(input: CreateEventInput): Promise<EventSummary> {
  return withApiError(async () => {
    const { data } = await apiClient.post<EventSummary>('/events', input)
    return data
  })
}

export async function getSubmissions(params: {
  corporation?: string
  event_id?: number
  date_from?: string
  date_to?: string
}): Promise<SubmissionSummary[]> {
  return withApiError(async () => {
    const { data } = await apiClient.get<SubmissionSummary[]>('/submissions', { params })
    return data
  })
}

export async function getSubmission(id: number): Promise<SubmissionDetail> {
  return withApiError(async () => {
    const { data } = await apiClient.get<SubmissionDetail>(`/submissions/${id}`)
    return data
  })
}

export async function fileSubmission(
  input: FileSubmissionInput,
): Promise<SubmissionIngestResult> {
  return withApiError(async () => {
    const form = new FormData()
    form.append('corporation', input.corporation)
    form.append('as_at', input.as_at)
    form.append('alert_level', input.alert_level)
    if (input.event_id !== undefined) form.append('event_id', String(input.event_id))
    if (input.present_activity) form.append('present_activity', input.present_activity)
    if (input.situation_overview) form.append('situation_overview', input.situation_overview)
    if (input.incidentsFile) form.append('incidents_file', input.incidentsFile)
    if (input.logsFile) form.append('logs_file', input.logsFile)
    const { data } = await apiClient.post<SubmissionIngestResult>('/submissions', form)
    return data
  })
}
```

- [ ] **Step 6: Write `src/lib/queries/submissions.ts`**, matching the pattern in `src/lib/queries/reports.ts` (read that file first for the exact `queryOptions` / mutation idiom this project uses, including how it invalidates and how `useCreateReport` takes an `onSuccess` id callback). Expose `eventQueries.list(corporation)`, `submissionQueries.list(params)`, `submissionQueries.detail(id)`, `useCreateEvent(onSuccess)` and `useFileSubmission(onSuccess)`, invalidating the submission and event lists after a successful mutation.

- [ ] **Step 7: Verify.** `pnpm test` (32 passing: 28 + 4 new) and `pnpm exec tsc --noEmit -p tsconfig.json` clean.

- [ ] **Step 8: Commit** `frontend: add the submission data layer and blank CSV templates`

---

## Task 4: Corp events list and event creation

**Files:** Modify `src/routes/corp/index.tsx`; create `src/routes/corp/events/new.tsx`. Modify `src/components/app-sidebar.tsx`.

**Interfaces consumed:** `eventQueries.list`, `useCreateEvent`, `useIdentity`, `identityLabel`.

- [ ] **Step 1: Rebuild `/corp` as the events list.**

Replace the `EmptyState` body. Use `useIdentity()` for the acting corporation; if `identity?.role !== 'corp'`, render only the existing `<RoleMismatchNotice expected="corp" />` and a line telling them to switch. Otherwise query `eventQueries.list(identity.corporation)` and render:

- Running events first — `ended_at === null` — then past ones, each as a `ContentCard` linking to `/corp/events/$eventId`, showing title, hazard type, and start date.
- An `EmptyState` when there are none, with a "Declare an event" button.
- A `PageHeader` titled with `identityLabel(identity)` and an action button linking to `/corp/events/new`.

Follow `src/routes/dmu/reports/index.tsx` for the loading/error/empty idiom (`LoadingBlock`, `EmptyState`).

- [ ] **Step 2: Write `/corp/events/new`.**

A `useAppForm` with `title` (text, required), `hazard_type` (select from `flood`, `landslide`, `wind`, `fire`, `other`), and `started_at` (date, required, defaulting to today). Corporation comes from identity and is **not** a field. On success navigate to `/corp/events/$eventId`. Follow the form idiom in `src/routes/dmu/reports/new.tsx` (`form.AppForm`, `form.AppField`, `field.TextField`, `field.SelectField`, `form.SubmitButton`).

- [ ] **Step 3: Extend the corp nav.** In `src/components/app-sidebar.tsx`, `CORP_NAV` becomes:

```tsx
const CORP_NAV = [
  { title: 'Events', to: '/corp', icon: CalendarIcon },
  { title: 'My submissions', to: '/corp/submissions', icon: FileTextIcon },
] as const
```

"File a report" is deliberately absent — filing happens through an event, and a nav item that cannot know which event would have to ask, which is the picker the spec rejects.

- [ ] **Step 4: Verify.** `pnpm generate-routes`, then `tsc --noEmit` clean and `pnpm test` passing.

- [ ] **Step 5: Commit** `frontend: corp events list and event creation`

---

## Task 5: The filing form and its result

**Files:** Create `src/routes/corp/events/$eventId/index.tsx`, `src/routes/corp/events/$eventId/file.tsx`, `src/components/submissions/submission-result.tsx`, `src/components/submissions/csv-template-links.tsx`.

**Interfaces consumed:** `submissionQueries.list`, `useFileSubmission`, `downloadCsvTemplate`, `INCIDENT_CSV_HEADERS`, `LOG_CSV_HEADERS`.

- [ ] **Step 1: Write the result component.**

`src/components/submissions/submission-result.tsx` takes `result: SubmissionIngestResult` and renders:

- A headline: `{incidents_inserted + incidents_updated} of {incidents_read} incident rows accepted`, and the same for logs when `logs_read > 0`.
- When `row_errors.length > 0`, a table with columns **Row** / **File** / **Reason**, rendering `row_number` **verbatim** — add a comment saying the backend already offsets for the header and a second offset would send the officer to the wrong line.
- When `unmapped_values` is non-empty, a note listing the values, because an unrecognised incident type is accepted but affects which metrics count the row.
- `pii_columns_dropped` rendered as a plain reassurance line: these columns were present and were not stored.

- [ ] **Step 2: Write the CSV template links.**

`src/components/submissions/csv-template-links.tsx` renders two buttons calling `downloadCsvTemplate('incidents.csv', INCIDENT_CSV_HEADERS)` and `downloadCsvTemplate('situation-logs.csv', LOG_CSV_HEADERS)`, with one line of copy saying to fill these in and upload them.

- [ ] **Step 3: Write the event page** `/corp/events/$eventId`.

Header block mirroring the real document: event title, and from the most recent submission — present activity, alert level, and "As at {as_at}". Below, the run of filings from `submissionQueries.list({ event_id })` newest first, each showing `Situation Report #{sequence_no}`, its as-at, alert level, and accepted counts, linking to nothing yet. Primary action: a button to `/corp/events/$eventId/file` labelled **`File report #{next}`** where `next` is `max(sequence_no) + 1`, or `#1` when there are none.

- [ ] **Step 4: Write the filing form** `/corp/events/$eventId/file`.

Fields: `as_at` (datetime-local, defaults to now), `alert_level` (select: green, yellow, orange, red, discontinued, none), `present_activity` (text), `situation_overview` (textarea), and two file inputs. **Pre-fill `alert_level`, `present_activity` and `situation_overview` from the most recent submission for this event** so a follow-up is an edit rather than a blank form.

Zero files is valid and must be allowed — that is the "no reports at this time" filing. Say so in the copy under the file inputs.

On success, render `<SubmissionResult>` in place of the form rather than navigating away, so the officer reads what landed. Give them a link back to the event.

Render `<CsvTemplateLinks />` above the file inputs.

- [ ] **Step 5: Verify.** `pnpm generate-routes`, `tsc --noEmit` clean, `pnpm test` passing.

- [ ] **Step 6: Commit** `frontend: corp filing form with accepted and rejected row reporting`

---

## Task 6: My submissions, and the real Survey123 upload

**Files:** Create `src/routes/corp/submissions.tsx`. Modify `src/routes/dmu/field-data.tsx`.

- [ ] **Step 1: Write `/corp/submissions`.** A flat table of everything this corporation has filed, newest first, from `submissionQueries.list({ corporation })`: as-at, event title, `#{sequence_no}`, alert level, incident and log counts. `EmptyState` when there are none.

- [ ] **Step 2: Replace the Survey123 placeholder.** `src/routes/dmu/field-data.tsx` currently renders `<FormPlaceholder>`. Replace with a real form: one file input plus a submit, calling the existing `ingestModule('survey123', file)` from `src/lib/api/ingest.ts` (it already exists and works). On success render the returned `IngestResult` — rows read, inserted, updated, duplicates flagged, and the `pii_columns_dropped` list. On failure render the error message.

Keep the corrected copy: this page is Survey123 field data only, and situation reports go through `/corp`.

- [ ] **Step 3: Verify.** `pnpm generate-routes`, `tsc --noEmit` clean, `pnpm test` passing.

- [ ] **Step 4: Commit** `frontend: my submissions list and the real Survey123 upload`

---

## Task 7: Who has reported

**Files:** Modify `src/routes/dmu/index.tsx`.

- [ ] **Step 1: Add the panel.** Below the existing stat cards, a `ContentCard` titled "Who has reported" with a date-window control defaulting to the last 30 days. Query `submissionQueries.list({ date_from, date_to })` and derive per-corporation status client-side over `CANONICAL_CORPORATIONS` from `@/lib/corporations` — fourteen rows makes that honest, and the spec chose it over a second endpoint so there is only one implementation of "who reported".

Each row: corporation display name via `CORPORATION_LABELS`, and either the latest as-at, alert level and counts, or a plain **"No reports at this time"**. Sort reported first.

- [ ] **Step 2: Verify.** `tsc --noEmit` clean, `pnpm test` passing.

- [ ] **Step 3: Commit** `frontend: show the DMU which corporations have reported`

---

## Task 8: End-to-end walkthrough

Verification only; changes no files. Re-seed first so the data matches the committed fixtures.

- [ ] **Step 1: Re-seed and start both servers.**

```bash
cd apps/backend && .venv/bin/python scripts/seed_demo.py
cd apps/backend && .venv/bin/python -m uvicorn app:app --port 8000
cd apps/frontend && pnpm dev
```

- [ ] **Step 2: Walk the corp path.** Clear site data, load `/`, pick **Diego Martin Regional Corporation**. Confirm: `/corp` lists the seeded "Adverse Weather June 2023" event; opening it shows Situation Report #1 and #2 with their alert levels and counts, and a "File report #3" button; the filing form pre-fills alert level and overview from #2.

- [ ] **Step 3: File a deliberately broken CSV.** Download the incidents template, fill three rows, blank the `Row ID` on the second, upload. Confirm the result reports 2 of 3 accepted and names **row 3** — open the file and check that is the row you broke.

- [ ] **Step 4: Walk the DMU path.** Switch to the DMU. Confirm "Who has reported" lists five corporations with filings and **Siparia Regional Corporation with "No reports at this time"**. Upload `fixtures/demo/survey123_june_2023.csv` on `/dmu/field-data` and confirm the result renders. Open a report and confirm citations still jump to their fact rows.

- [ ] **Step 5: Record the outcome** — each step, what you saw, and any deviation. No commit.

---

## Done when

- A corporation can declare an event, file a spreadsheet, and read what was accepted and what was rejected with the row number their spreadsheet shows — without a terminal.
- Blank CSV templates download with headers matching the parser exactly.
- A filing with no files at all is accepted as "nothing to report".
- Row errors survive a page reload, because they are persisted.
- The DMU sees who has reported and who has not, naming the corporations that filed nothing.
- `GET /submissions` with no filters returns every corporation.
- Backend 0 failed; frontend `tsc` clean and all tests passing.

---

## Deliberately not in this plan

**`/dmu/corporations/$corp`** — the spec's read-only view of one corporation's events and filings. Task 7's who-has-reported panel answers the question the DMU actually asks during an event ("who is outstanding"), and a per-corporation drill-down is a comfort feature on top of it. Deferred so this plan ends at a working demo rather than a complete one.

**Report generation from the corp side.** A corporation still cannot press "generate my situation report" — that screen belongs with the corp workspace but the template it needs (`corp_situation_report`) is now committed and works, so it is a small follow-up rather than a blocker. The DMU can generate it today from `/dmu/reports/new`.

**A test for running-versus-past event grouping.** The spec's §7 lists it. Task 4 implements the grouping but the derivation is three lines inside a component; extracting it to test would be the only reason to extract it. Worth doing when the corp workspace grows a second consumer of that rule.
