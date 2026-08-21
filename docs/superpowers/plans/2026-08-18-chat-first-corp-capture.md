# Chat-First Corp Capture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make conversation the top-level way a corporation officer files a situation report — open the app, start typing, and have the event, incidents, and situation logs distilled out of the conversation — with manual edits and CSV upload as secondary paths that the conversation can never overwrite.

**Architecture:** Three layers, in order. (1) **Provenance** — every value in a capture session is tagged as model-written or hand-written, and hand-written values are re-pinned deterministically on the backend after every LLM turn, so "be mindful of manual edits" is a guarantee rather than a prompt instruction. (2) **Ungating** — `capture_sessions.event_id` becomes nullable and the event is attached mid-conversation by an explicit one-tap confirmation, never inferred by the model. (3) **Inversion** — the conversation takes the wide column and the structured record becomes a readable right rail with inline editing; the corp sidebar and the event-first route tree are retired in favour of a composer-led home.

**Tech Stack:** FastAPI, SQLAlchemy 2.x, Alembic, pytest · React 19, TanStack Router (file-based) + Query + Form + `@tanstack/ai-react`, Tailwind 4, Vitest + Testing Library.

**Source review:** the corp UI audit in this branch's session — findings are carried into the Flaw Register below.

---

## Global Constraints

- **No authentication exists and none is added.** Identity is a `localStorage` declaration read via `useIdentity()`. The acting corporation always comes from that context — never a dropdown on a corp-facing form.
- **The LLM never chooses an identity or a join key.** It may propose, in prose or as a suggestion payload; a deterministic UI action commits. This applies to event attachment exactly as it already applies to metric selection. A wrong `event_id` silently corrupts a corporation's running record, because cross-submission supersession is event-scoped (`app/modules/sitreps/ingest.py:183-200`).
- **A submission carrying incidents MUST name an event.** `POST /submissions` returns 400 otherwise (`app/api/submissions.py:103-110`). Situation logs may be filed with no event. Capture filing must enforce the same rule at the same boundary.
- **Manual values outrank model values, always.** Enforcement is deterministic and server-side. The prompt line is a courtesy to keep assistant messages coherent — it is never the mechanism.
- **All database contents are disposable and migrations may change anything.** Choose the correct schema outright.
- **Backend tests:** `cd apps/backend && .venv/bin/python -m pytest`. Baseline **478 passed, 0 failed** — any failure is yours.
- **Frontend tests:** `cd apps/frontend && pnpm test` (baseline **52 passed, 11 files**) and `pnpm exec tsc --noEmit -p tsconfig.json`. Never add a `test` block to `vite.config.ts`.
- **`@testing-library/jest-dom` is NOT installed and must not be added.** Existing tests assert with plain matchers — `expect(screen.getByText(x)).not.toBeNull()`, `expect(screen.queryByLabelText(x)).toBeNull()`, and casts for values (`expect((el as HTMLInputElement).value).toBe(...)`). Every test in this plan follows that style. `toBeInTheDocument`, `toHaveValue`, and `toBeDisabled` will throw "is not a function".
- **Each test file that renders needs `// @vitest-environment jsdom` as its first line.** There is no global jsdom environment.
- **Route tree is generated.** After adding or removing a file under `src/routes/`, run `cd apps/frontend && pnpm generate-routes` and commit `src/routeTree.gen.ts`.
- **Migrations must apply from empty:** `cd apps/backend && rm -f /tmp/m.db && DATABASE_URL="sqlite:////tmp/m.db" .venv/bin/python -m alembic upgrade head && DATABASE_URL="sqlite:////tmp/m.db" .venv/bin/python -m alembic check`. SQLite has no `ALTER COLUMN` — use `op.batch_alter_table`. Current head is **`c8d4e1f92a70`**; confirm with `alembic heads` before writing a migration.
- **Mobile is the primary device for a corp officer.** An officer filing during a flood is on a phone. Every layout in this plan must be specified and verified at 390px before its desktop form.

---

## Flaw Register

Every defect found in the audit, where it lives, and where it gets fixed. Nothing here is dropped silently — items marked **Deferred** have a named iteration and a rationale in the Deferred Backlog section.

| ID | Flaw | Location | Severity | Resolution |
|----|------|----------|----------|------------|
| **F1** | In-progress typing in the situation form is wiped whenever an LLM turn completes. `useEffect` resets the form on `session.updated_at`; `capture.updated` fires on every turn. | `components/capture/capture-pane.tsx:94-101` ← `api/capture.py:285-291` | **Data loss** | Task 1 (hotfix, shippable alone) |
| **F2** | No provenance on the working set. The prompt declares the working set the source of truth and demands the model return it in full, so any hand-typed value can be reworded, renumbered, or dropped on the next turn. | `modules/capture/prompt.py:63`, `schemas.py:8-78` | **Data loss** | Tasks 3–5 |
| **F3** | `CaptureLog` has no stable identity. The UI keys on `${statement}-${index}` and removes by index, so a model reorder deletes the wrong log. | `capture-pane.tsx:310`, `:316` | **Data loss** | Task 2 (backend), Task 10 (UI removes by `row_id`) |
| **F4** | Conversation is geometrically declared secondary — chat is a `380px` aside, the form stack is `flex-1`. | `routes/corp/events/$eventId/chat.tsx:177`, `:238` | High | Task 12 |
| **F5** | Chat is four gates deep and the event gate is deliberate and documented in nav. The domain does not require it: `Submission.event_id` is nullable, only `CaptureSession.event_id` is not. | `components/app-sidebar.tsx:27-33`, `modules/capture/models.py:16` | High | Tasks 6, 7, 11, 13, 16 |
| **F6** | Conversations are invisible objects — found-or-created behind a `started` ref, never listed, named, or resumable in the UI, though `GET /capture/sessions` exists. | `chat.tsx:58-70` | High | Tasks 8, 13 |
| **F7** | `alert_level` defaults to `none` with no missing-field check at all — a red-alert flood can be filed as "none" unprompted. `missing_fields` has zero session-level checks. | `modules/capture/missing.py:4-29` | High | Task 5 |
| **F8** | A filed submission can never be reopened. `SubmissionRow` renders no link and no `/corp/filings/$id` route exists, though `GET /submissions/{id}` does. | `routes/corp/events/$eventId/index.tsx:205-218` | High | Task 15 |
| **F9** | Two save contracts on one pane — situation fields need an explicit **Save**, incidents and logs write on add/remove. | `capture-pane.tsx:165` vs `:119`, `:136` | Medium | Task 10 |
| **F10** | Duplicate nagging — `missing` renders as a passive bullet list in one pane while the model asks about the same items in the other, and neither is clickable to the field. | `capture-pane.tsx:144-152` + `prompt.py:64` | Medium | Tasks 9, 10 |
| **F11** | The "report at the end" is a corporation-wide **date-range** report triggered from the conversation, not a report on what was just captured. | `chat.tsx:208-217` | Medium | **Deferred — Iteration 2** |
| **F12** | `sequence_no` is guessed client-side via `Math.max(...)+1`, naming a report number that concurrency can invalidate. | `events/$eventId/index.tsx:56-59` | Low | Task 14 |
| **F13** | The event page `.find()`s over the corporation's whole event list instead of fetching a detail, so it cannot render until the full list loads and a foreign deep link renders a bare "Event". | `events/$eventId/index.tsx:42` | Low | **Deferred — Iteration 3** |
| **F14** | Filing is a one-way door with no preview and no diff, and the page stays put afterwards with a dead disabled chat. | `chat.tsx:190-201` | Medium | Task 14 |
| **F15** | Two near-identical "Situation" forms with divergent behaviour — the CSV form prefills from the last submission, the capture pane does not. | `events/$eventId/file.tsx:188` vs `capture-pane.tsx:162` | Low | Task 10 (capture side) + **Deferred — Iteration 3** (CSV side) |

---

## File Structure

**Backend — create:**
- `apps/backend/alembic/versions/<rev>_capture_provenance_and_optional_event.py` — `manual_fields` column; `event_id` nullable.
- `apps/backend/app/modules/capture/provenance.py` — field-path vocabulary and the deterministic re-pin. One responsibility: deciding which values survive a turn.
- `apps/backend/tests/test_capture_provenance.py`

**Backend — modify:**
- `app/modules/capture/schemas.py` — `CaptureLog.row_id`, `CaptureWorkingSet.manual_fields`.
- `app/modules/capture/models.py` — `manual_fields` column, `event_id` nullable.
- `app/modules/capture/store.py` — optional `event_id` on create/list, `attach_event`.
- `app/modules/capture/turn.py` — assign log ids, call `pin_manual_fields`, send `manual` in the prompt payload.
- `app/modules/capture/missing.py` — session-level gaps.
- `app/modules/capture/prompt.py` — log `row_id`, manual-field rule.
- `app/api/capture.py` — optional `event_id`, `manual_fields` in/out, attach endpoint, file guard.

**Frontend — create:**
- `src/routes/corp/c/$sessionId.tsx` — the conversation workspace.
- `src/routes/corp/filings/$submissionId.tsx` — read back a filed sitrep (F8).
- `src/components/capture/capture-record.tsx` — the right rail: readable cards, inline edit, missing chips.
- `src/components/capture/incident-card.tsx`, `src/components/capture/log-card.tsx`
- `src/components/capture/event-chip.tsx` — event attachment control.
- `src/components/capture/review-file-sheet.tsx` — preview before filing (F14).
- `src/components/corp/composer.tsx` — the home composer.
- `src/lib/capture-paths.ts` — manual-field path helpers, pure and tested.
- Tests alongside each: `*.test.tsx` / `*.test.ts`.

**Frontend — modify:**
- `src/types/dmcu.ts` — `row_id` on `CaptureLog`, `manual_fields`, nullable `event_id`.
- `src/lib/api/capture.ts`, `src/lib/queries/capture.ts` — optional `event_id`, attach mutation.
- `src/routes/corp/index.tsx` — becomes the composer-led home.
- `src/components/app-sidebar.tsx` — corp nav retired.
- `src/routes/__root.tsx` — sidebar suppressed for corp identity.

**Frontend — delete:**
- `src/routes/corp/events/$eventId/chat.tsx` (superseded by `/corp/c/$sessionId`)
- `src/components/capture/capture-pane.tsx` + `capture-pane.test.tsx` (superseded by `capture-record.tsx`)
- `src/routes/corp/submissions.tsx` (becomes a tab on the home page)

---

## Task 1: Stop the situation form from clobbering in-progress typing (F1)

Standalone hotfix. Ships on its own, before any redesign. The bug is live today.

**Files:**
- Modify: `apps/frontend/src/components/capture/capture-pane.tsx:94-101`
- Test: `apps/frontend/src/components/capture/capture-pane.test.tsx`

**Interfaces produced:** none — behaviour change only.

- [ ] **Step 1: Write the failing test**

Append to `capture-pane.test.tsx`:

```tsx
it('keeps in-progress typing when the session updates from a chat turn', () => {
  const { rerender } = render(
    <CapturePane session={session} onSave={vi.fn()} />,
  )
  const overview = screen.getByLabelText('Situation overview')
  fireEvent.change(overview, { target: { value: 'Water rising on Diego Martin Main Rd' } })

  // An LLM turn lands: same session id, new updated_at, model-written fields.
  rerender(
    <CapturePane
      session={{
        ...session,
        updated_at: '2026-08-18T14:05:00',
        present_activity: 'Heavy rainfall',
      }}
      onSave={vi.fn()}
    />,
  )

  const after = screen.getByLabelText('Situation overview') as HTMLTextAreaElement
  expect(after.value).toBe('Water rising on Diego Martin Main Rd')
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/frontend && pnpm test -- capture-pane`
Expected: FAIL — received `''`, because the effect reset the form.

- [ ] **Step 3: Write the minimal implementation**

Replace the effect at `capture-pane.tsx:94-101` with a dirty-guarded reset:

```tsx
// A chat turn must never overwrite what the officer is typing. Only adopt
// server values into fields the officer has not touched since the last save.
useEffect(() => {
  const dirty = situationForm.state.isDirty
  if (dirty) return
  situationForm.reset({
    as_at: toDatetimeLocal(session.as_at),
    alert_level: session.alert_level,
    present_activity: session.present_activity ?? '',
    situation_overview: session.situation_overview ?? '',
  })
}, [session.updated_at])
```

TanStack Form's `isDirty` means "has been changed since the last reset", not "differs from the reset value" — so once the officer types, this pane stops adopting server values into the situation fields until it saves. That is the correct trade for a hotfix: a stale server value is recoverable, a lost sentence is not. Task 10 removes the ambiguity entirely by mounting an edit form only while a card is open.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/frontend && pnpm test && pnpm exec tsc --noEmit -p tsconfig.json`
Expected: PASS, 53 tests.

- [ ] **Step 5: Commit**

```bash
git add apps/frontend/src/components/capture/capture-pane.tsx apps/frontend/src/components/capture/capture-pane.test.tsx
git commit -m "fix: stop chat turns clobbering in-progress capture edits"
```

---

## Task 2: Give situation logs a stable identity (F3)

**Files:**
- Modify: `apps/backend/app/modules/capture/schemas.py`, `apps/backend/app/modules/capture/turn.py`, `apps/backend/app/modules/capture/prompt.py`
- Test: `apps/backend/tests/test_capture_turn.py`

**Interfaces produced:** `CaptureLog.row_id: str` — assigned by `coerce_working_set` when the model omits it, stable across turns thereafter.

- [ ] **Step 1: Write the failing test**

Append to `apps/backend/tests/test_capture_turn.py`:

```python
def test_logs_get_stable_row_ids_and_keep_them():
    previous = CaptureWorkingSet(
        logs=[CaptureLog(row_id="1", statement="200 sandbags in stock", category="resource")]
    )
    raw = {
        "capture": {
            "logs": [
                {"row_id": "1", "statement": "200 sandbags in stock", "category": "resource"},
                {"statement": "6 staff on standby", "category": "personnel"},
            ]
        }
    }
    working = coerce_working_set(raw, previous)
    assert [log.row_id for log in working.logs] == ["1", "2"]


def test_duplicate_log_row_ids_are_reassigned():
    raw = {
        "capture": {
            "logs": [
                {"row_id": "1", "statement": "a", "category": "other"},
                {"row_id": "1", "statement": "b", "category": "other"},
            ]
        }
    }
    working = coerce_working_set(raw, CaptureWorkingSet())
    ids = [log.row_id for log in working.logs]
    assert len(set(ids)) == 2
```

Add `CaptureLog` to the existing import block at the top of the file if absent.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend && .venv/bin/python -m pytest tests/test_capture_turn.py -k row_id -v`
Expected: FAIL — `CaptureLog` has no attribute `row_id`.

- [ ] **Step 3: Write the implementation**

In `schemas.py`, add the field as the first member of `CaptureLog`:

```python
class CaptureLog(BaseModel):
    row_id: str = ""
    category: str = "other"
```

In `turn.py`, replace the log loop inside `coerce_working_set` (currently lines 81-85) with the same id-assignment shape the incident loop uses:

```python
    logs: list[CaptureLog] = []
    used_log_ids: set[str] = set()
    next_log_id = 1
    for item in capture_raw.get("logs") or []:
        while str(next_log_id) in used_log_ids:
            next_log_id += 1
        log = _coerce_log(item if isinstance(item, dict) else {})
        if log is None:
            continue
        if not log.row_id or log.row_id in used_log_ids:
            log = log.model_copy(update={"row_id": str(next_log_id)})
        used_log_ids.add(log.row_id)
        logs.append(log)
```

In `prompt.py`, add `"row_id": "<stable id, keep existing ids>",` as the first key of the `logs[]` object in the JSON shape, and extend the existing rule at line 69:

```
- Preserve row_id on existing incidents AND logs. Assign a new integer row_id as a string for new rows.
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/backend && .venv/bin/python -m pytest -q`
Expected: PASS, 480 passed.

- [ ] **Step 5: Commit**

```bash
git add apps/backend/app/modules/capture apps/backend/tests/test_capture_turn.py
git commit -m "feat: give capture logs stable row ids"
```

---

## Task 3: Field-path vocabulary for provenance (F2)

Pure module, no I/O. Establishes the path grammar every later task uses.

**Files:**
- Create: `apps/backend/app/modules/capture/provenance.py`
- Test: `apps/backend/tests/test_capture_provenance.py`

**Interfaces produced:**
- `SESSION_FIELDS: tuple[str, ...]` — `("as_at", "alert_level", "present_activity", "situation_overview")`
- `incident_path(row_id: str, field: str) -> str` → `"incident:<row_id>.<field>"`
- `log_path(row_id: str, field: str) -> str` → `"log:<row_id>.<field>"`
- `row_paths(manual: Iterable[str], kind: str, row_id: str) -> set[str]` — the field names manually set on one row.

- [ ] **Step 1: Write the failing test**

Create `apps/backend/tests/test_capture_provenance.py`:

```python
from app.modules.capture.provenance import (
    SESSION_FIELDS,
    incident_path,
    log_path,
    row_paths,
)


def test_paths_are_namespaced_by_kind():
    assert incident_path("3", "injuries_count") == "incident:3.injuries_count"
    assert log_path("3", "quantity") == "log:3.quantity"


def test_session_fields_cover_the_editable_header():
    assert SESSION_FIELDS == (
        "as_at",
        "alert_level",
        "present_activity",
        "situation_overview",
    )


def test_row_paths_selects_only_the_named_row_and_kind():
    manual = {
        "incident:1.injuries_count",
        "incident:1.community",
        "incident:2.deaths_count",
        "log:1.quantity",
        "alert_level",
    }
    assert row_paths(manual, "incident", "1") == {"injuries_count", "community"}
    assert row_paths(manual, "log", "1") == {"quantity"}
    assert row_paths(manual, "incident", "9") == set()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend && .venv/bin/python -m pytest tests/test_capture_provenance.py -v`
Expected: FAIL — `ModuleNotFoundError: app.modules.capture.provenance`.

- [ ] **Step 3: Write the implementation**

Create `apps/backend/app/modules/capture/provenance.py`:

```python
"""Which values in a capture session were written by hand.

A capture session mixes two authors: the LLM, which rewrites the whole
working set on every turn, and the officer, who edits fields directly.
Manual values must survive every subsequent turn, so they are recorded as
explicit field paths and re-pinned server-side after the model answers.
Prompt instructions are not a mechanism — this module is.
"""

from collections.abc import Iterable

SESSION_FIELDS = ("as_at", "alert_level", "present_activity", "situation_overview")


def incident_path(row_id: str, field: str) -> str:
    return f"incident:{row_id}.{field}"


def log_path(row_id: str, field: str) -> str:
    return f"log:{row_id}.{field}"


def row_paths(manual: Iterable[str], kind: str, row_id: str) -> set[str]:
    prefix = f"{kind}:{row_id}."
    return {item[len(prefix) :] for item in manual if item.startswith(prefix)}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/backend && .venv/bin/python -m pytest tests/test_capture_provenance.py -v`
Expected: PASS, 3 passed.

- [ ] **Step 5: Commit**

```bash
git add apps/backend/app/modules/capture/provenance.py apps/backend/tests/test_capture_provenance.py
git commit -m "feat: add capture field-path vocabulary for provenance"
```

---

## Task 4: Re-pin manual values after every turn (F2)

**Files:**
- Modify: `apps/backend/app/modules/capture/schemas.py`, `apps/backend/app/modules/capture/provenance.py`, `apps/backend/app/modules/capture/turn.py`, `apps/backend/app/modules/capture/prompt.py`
- Test: `apps/backend/tests/test_capture_provenance.py`

**Interfaces consumed:** `SESSION_FIELDS`, `row_paths` (Task 3); `CaptureLog.row_id` (Task 2).

**Interfaces produced:**
- `CaptureWorkingSet.manual_fields: list[str]`
- `pin_manual_fields(next_working: CaptureWorkingSet, previous: CaptureWorkingSet) -> CaptureWorkingSet` — returns `next_working` with every manually-set value restored from `previous`, including rows the model dropped entirely.

- [ ] **Step 1: Write the failing test**

Append to `apps/backend/tests/test_capture_provenance.py`:

```python
from app.modules.capture.provenance import pin_manual_fields
from app.modules.capture.schemas import CaptureIncident, CaptureLog, CaptureWorkingSet


def test_manual_session_field_survives_a_model_rewrite():
    previous = CaptureWorkingSet(
        alert_level="red",
        situation_overview="Officer's own words",
        manual_fields=["alert_level", "situation_overview"],
    )
    model_said = CaptureWorkingSet(
        alert_level="yellow", situation_overview="Rewritten by the model"
    )
    pinned = pin_manual_fields(model_said, previous)
    assert pinned.alert_level == "red"
    assert pinned.situation_overview == "Officer's own words"


def test_model_may_still_write_fields_never_touched_by_hand():
    previous = CaptureWorkingSet(alert_level="red", manual_fields=["alert_level"])
    model_said = CaptureWorkingSet(alert_level="yellow", present_activity="Heavy rainfall")
    pinned = pin_manual_fields(model_said, previous)
    assert pinned.alert_level == "red"
    assert pinned.present_activity == "Heavy rainfall"


def test_manual_incident_field_survives_and_siblings_do_not():
    previous = CaptureWorkingSet(
        incidents=[
            CaptureIncident(row_id="1", injuries_count=4, incident_summary="model text")
        ],
        manual_fields=["incident:1.injuries_count"],
    )
    model_said = CaptureWorkingSet(
        incidents=[
            CaptureIncident(row_id="1", injuries_count=0, incident_summary="new model text")
        ]
    )
    pinned = pin_manual_fields(model_said, previous)
    assert pinned.incidents[0].injuries_count == 4
    assert pinned.incidents[0].incident_summary == "new model text"


def test_a_hand_added_row_the_model_dropped_is_restored():
    previous = CaptureWorkingSet(
        incidents=[CaptureIncident(row_id="7", incident_summary="Typed by hand")],
        logs=[CaptureLog(row_id="2", statement="Typed by hand", category="resource")],
        manual_fields=["incident:7.incident_summary", "log:2.statement"],
    )
    model_said = CaptureWorkingSet(incidents=[], logs=[])
    pinned = pin_manual_fields(model_said, previous)
    assert [row.row_id for row in pinned.incidents] == ["7"]
    assert [row.row_id for row in pinned.logs] == ["2"]


def test_manual_fields_carry_forward_untouched():
    previous = CaptureWorkingSet(manual_fields=["alert_level"])
    pinned = pin_manual_fields(CaptureWorkingSet(), previous)
    assert pinned.manual_fields == ["alert_level"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend && .venv/bin/python -m pytest tests/test_capture_provenance.py -v`
Expected: FAIL — `CaptureWorkingSet` has no field `manual_fields`.

- [ ] **Step 3: Write the implementation**

In `schemas.py`, add to `CaptureWorkingSet`:

```python
    manual_fields: list[str] = Field(default_factory=list)
```

Append to `provenance.py`:

```python
from app.modules.capture.schemas import CaptureIncident, CaptureLog, CaptureWorkingSet


def _pin_rows(
    kind: str,
    next_rows: list,
    previous_rows: list,
    manual: set[str],
    model,
) -> list:
    prior_by_id = {row.row_id: row for row in previous_rows}
    pinned: list = []
    for row in next_rows:
        prior = prior_by_id.get(row.row_id)
        if prior is None:
            pinned.append(row)
            continue
        fields = row_paths(manual, kind, row.row_id) & set(model.model_fields)
        if not fields:
            pinned.append(row)
            continue
        pinned.append(row.model_copy(update={f: getattr(prior, f) for f in fields}))

    # A row the officer created or corrected must not vanish because the model
    # forgot to echo it back.
    returned = {row.row_id for row in pinned}
    for row_id, prior in prior_by_id.items():
        if row_id not in returned and row_paths(manual, kind, row_id):
            pinned.append(prior)
    return pinned


def pin_manual_fields(
    next_working: CaptureWorkingSet, previous: CaptureWorkingSet
) -> CaptureWorkingSet:
    """Restore every hand-written value onto the model's fresh working set."""
    manual = set(previous.manual_fields)
    patch: dict = {"manual_fields": list(previous.manual_fields)}
    if not manual:
        return next_working.model_copy(update=patch)

    for name in SESSION_FIELDS:
        if name in manual:
            patch[name] = getattr(previous, name)

    patch["incidents"] = _pin_rows(
        "incident", next_working.incidents, previous.incidents, manual, CaptureIncident
    )
    patch["logs"] = _pin_rows(
        "log", next_working.logs, previous.logs, manual, CaptureLog
    )
    return next_working.model_copy(update=patch)
```

In `turn.py`, import it and apply it in `_finish_turn`. Replace line 167 (`next_working = coerce_working_set(parsed, working)`) with:

```python
    next_working = pin_manual_fields(coerce_working_set(parsed, working), working)
```

Add the import beside the existing capture imports:

```python
from app.modules.capture.provenance import pin_manual_fields
```

Also thread the manual list into the prompt so the assistant does not narrate changes it cannot make. In `_prompt_payload`, add to `payload`:

```python
        "manual": list(working.manual_fields),
```

And add a rule to `prompt.py`:

```
- Field paths listed under "manual" were typed by the officer. Treat them as
  settled: you may refer to them, never restate them with a different value.
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/backend && .venv/bin/python -m pytest -q`
Expected: PASS, 488 passed (478 baseline + 2 from Task 2 + 3 from Task 3 + 5 here).

- [ ] **Step 5: Commit**

```bash
git add apps/backend/app/modules/capture apps/backend/tests/test_capture_provenance.py
git commit -m "feat: re-pin manually edited capture fields after every LLM turn"
```

---

## Task 5: Record provenance on manual edits, and flag an unset alert level (F2, F7)

**Files:**
- Modify: `apps/backend/app/modules/capture/models.py`, `store.py`, `missing.py`, `apps/backend/app/api/capture.py`
- Create: `apps/backend/alembic/versions/<rev>_capture_provenance_and_optional_event.py`
- Test: `apps/backend/tests/test_api_capture.py`, `apps/backend/tests/test_capture_provenance.py`

**Interfaces consumed:** `pin_manual_fields`, `SESSION_FIELDS`, `incident_path`, `log_path`.

**Interfaces produced:**
- `CaptureSession.manual_fields` JSON column, default `[]`.
- `PUT /capture/sessions/{id}` accepts and returns `manual_fields: list[str]`.
- `missing_fields` now reports `alert_level` and `as_at` at session level.

This task also creates the migration that Task 6 extends — write both column changes now, since `alembic check` must stay clean and two migrations touching one table is churn. `event_id` becomes nullable here; the API keeps requiring it until Task 6.

- [ ] **Step 1: Write the failing test**

Append to `apps/backend/tests/test_capture_provenance.py`:

```python
from app.modules.capture.missing import missing_fields


def test_unset_alert_level_is_reported_missing():
    paths = {item.path for item in missing_fields(CaptureWorkingSet())}
    assert "alert_level" in paths


def test_alert_level_set_by_hand_is_not_reported_missing():
    working = CaptureWorkingSet(alert_level="none", manual_fields=["alert_level"])
    paths = {item.path for item in missing_fields(working)}
    assert "alert_level" not in paths
```

Append to `apps/backend/tests/test_api_capture.py`. That file has no pytest fixtures for these — it uses the module helpers `make_client(monkeypatch)`, `create_event(client)`, `create_capture(client, event_id)` and the constant `CORP`. Match that style exactly:

```python
def test_put_session_records_manual_fields(monkeypatch):
    client = make_client(monkeypatch)
    event_id = create_event(client)
    session_id = create_capture(client, event_id)["id"]

    response = client.put(
        f"/capture/sessions/{session_id}",
        json={
            "alert_level": "red",
            "incidents": [],
            "logs": [],
            "manual_fields": ["alert_level"],
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["manual_fields"] == ["alert_level"]

    reread = client.get(f"/capture/sessions/{session_id}")
    assert reread.json()["manual_fields"] == ["alert_level"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/backend && .venv/bin/python -m pytest tests/test_capture_provenance.py tests/test_api_capture.py -k "manual_fields or alert_level" -v`
Expected: FAIL — `alert_level` absent from missing paths; `manual_fields` absent from the API response.

- [ ] **Step 3: Write the implementation**

`missing.py` — prepend session-level checks inside `missing_fields`:

```python
def missing_fields(working: CaptureWorkingSet) -> list[MissingField]:
    missing: list[MissingField] = []
    manual = set(working.manual_fields)
    # "none" is both the default and a legal answer. Provenance is what tells
    # the two apart: an officer who chose it has a manual_fields entry.
    if working.alert_level == "none" and "alert_level" not in manual:
        missing.append(
            MissingField(path="alert_level", message="Current alert level for the region")
        )
    if working.as_at is None:
        missing.append(
            MissingField(path="as_at", message="Time this report is accurate as at")
        )
    for index, incident in enumerate(working.incidents):
        ...  # existing loop unchanged
```

`models.py` — add the column and relax the foreign key:

```python
    event_id: Mapped[int | None] = mapped_column(
        ForeignKey("events.id"), nullable=True, index=True
    )
    manual_fields: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
```

`store.py` — carry the list through both directions:

```python
def working_set_from_session(row: CaptureSession) -> CaptureWorkingSet:
    return CaptureWorkingSet(
        ...,
        manual_fields=list(row.manual_fields or []),
    )


def apply_working_set(row: CaptureSession, working: CaptureWorkingSet) -> None:
    ...
    row.manual_fields = list(working.manual_fields)
```

and add `manual_fields=[]` to the `CaptureSession(...)` constructor in `create_session`.

`api/capture.py` — add `manual_fields: list[str]` to `CaptureSessionResponse` (populated from `working.manual_fields` in `_to_response`) and to `UpdateSessionRequest`:

```python
class UpdateSessionRequest(BaseModel):
    ...
    manual_fields: list[str] = Field(default_factory=list)
```

and pass it into the `CaptureWorkingSet(...)` built in `put_session`:

```python
        manual_fields=request.manual_fields,
```

Migration — create `apps/backend/alembic/versions/<rev>_capture_provenance_and_optional_event.py` with `down_revision = "c8d4e1f92a70"`:

```python
def upgrade() -> None:
    with op.batch_alter_table("capture_sessions") as batch:
        batch.add_column(
            sa.Column("manual_fields", sa.JSON(), nullable=False, server_default="[]")
        )
        batch.alter_column("event_id", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("capture_sessions") as batch:
        batch.alter_column("event_id", existing_type=sa.Integer(), nullable=False)
        batch.drop_column("manual_fields")
```

- [ ] **Step 4: Run tests and the migration check**

```bash
cd apps/backend && .venv/bin/python -m pytest -q
rm -f /tmp/m.db && DATABASE_URL="sqlite:////tmp/m.db" .venv/bin/python -m alembic upgrade head
DATABASE_URL="sqlite:////tmp/m.db" .venv/bin/python -m alembic check
```

Expected: PASS, 491 passed; `alembic check` reports no new upgrade operations.

- [ ] **Step 5: Commit**

```bash
git add apps/backend/app/modules/capture apps/backend/app/api/capture.py apps/backend/alembic/versions apps/backend/tests
git commit -m "feat: persist capture provenance and flag an unset alert level"
```

---

## Task 6: Let a conversation start without an event (F5)

**Files:**
- Modify: `apps/backend/app/modules/capture/store.py`, `apps/backend/app/api/capture.py`
- Test: `apps/backend/tests/test_api_capture.py`

**Interfaces consumed:** nullable `event_id` column (Task 5).

**Interfaces produced:**
- `create_session(db, *, corporation, event_id: int | None = None)`
- `list_sessions(db, *, corporation, event_id: int | None = None)` — `None` lists every session for the corporation.
- `POST /capture/sessions` with `event_id` optional.
- `GET /capture/sessions?corporation=...` with `event_id` optional.
- `POST /capture/sessions/{id}/file` returns 400 when incidents exist and no event is attached.

- [ ] **Step 1: Write the failing test**

First widen the module helper so later tests can start a session with no event. Change `create_capture` in `apps/backend/tests/test_api_capture.py:144` to:

```python
def create_capture(client: TestClient, event_id: int | None = None) -> dict:
    payload: dict = {"corporation": CORP}
    if event_id is not None:
        payload["event_id"] = event_id
    response = client.post("/capture/sessions", json=payload)
    assert response.status_code == 201, response.text
    return response.json()
```

Then append:

```python
def test_session_can_start_with_no_event(monkeypatch):
    client = make_client(monkeypatch)
    assert create_capture(client)["event_id"] is None


def test_sessions_list_without_event_filter(monkeypatch):
    client = make_client(monkeypatch)
    create_capture(client)
    response = client.get("/capture/sessions", params={"corporation": CORP})
    assert response.status_code == 200
    assert len(response.json()) >= 1


def test_filing_incidents_without_an_event_is_rejected(monkeypatch):
    client = make_client(monkeypatch)
    session_id = create_capture(client)["id"]
    client.put(
        f"/capture/sessions/{session_id}",
        json={
            "incidents": [{"row_id": "1", "incident_summary": "5 houses flooded"}],
            "logs": [],
        },
    )
    response = client.post(f"/capture/sessions/{session_id}/file")
    assert response.status_code == 400
    assert "event" in response.json()["detail"]


def test_filing_logs_only_without_an_event_is_allowed(monkeypatch):
    client = make_client(monkeypatch)
    session_id = create_capture(client)["id"]
    client.put(
        f"/capture/sessions/{session_id}",
        json={
            "incidents": [],
            "logs": [
                {"row_id": "1", "statement": "200 sandbags in stock", "category": "resource"}
            ],
        },
    )
    assert client.post(f"/capture/sessions/{session_id}/file").status_code == 201
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/backend && .venv/bin/python -m pytest tests/test_api_capture.py -k "no_event or without" -v`
Expected: FAIL — 422 on the create call, `event_id` is required.

- [ ] **Step 3: Write the implementation**

`store.py`:

```python
def create_session(
    db: Session,
    *,
    corporation: str,
    event_id: int | None = None,
) -> CaptureSession:
    existing = [
        row
        for row in list_sessions(db, corporation=corporation, event_id=event_id)
        if row.status == "draft" and row.event_id == event_id
    ]
    ...


def list_sessions(
    db: Session, *, corporation: str, event_id: int | None = None
) -> list[CaptureSession]:
    stmt = select(CaptureSession).where(CaptureSession.corporation == corporation)
    if event_id is not None:
        stmt = stmt.where(CaptureSession.event_id == event_id)
    stmt = stmt.order_by(CaptureSession.updated_at.desc(), CaptureSession.id.desc())
    return list(db.scalars(stmt).all())
```

`api/capture.py`:

```python
class CreateSessionRequest(BaseModel):
    corporation: str
    event_id: int | None = None
```

`post_session` — only validate the event when one is named:

```python
    corporation = _require_corporation(request.corporation)
    if request.event_id is not None:
        event = get_event(db, request.event_id)
        if event is None or event.corporation != corporation:
            raise HTTPException(
                status_code=404,
                detail=f"event not found for this corporation: {request.event_id}",
            )
    row = create_session(db, corporation=corporation, event_id=request.event_id)
```

`get_sessions` — `event_id: int | None = None`, passed straight through.

`file_session` — add the guard before ingesting, mirroring `POST /submissions`:

```python
    working = working_set_from_session(row)
    if row.event_id is None and working.incidents:
        raise HTTPException(
            status_code=400,
            detail=(
                "a filing carrying incidents must be attached to an event; "
                "attach one before filing. Situation logs may be filed without one."
            ),
        )
```

`CaptureSessionResponse.event_id` becomes `int | None`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/backend && .venv/bin/python -m pytest -q`
Expected: PASS, 495 passed.

- [ ] **Step 5: Commit**

```bash
git add apps/backend/app/modules/capture/store.py apps/backend/app/api/capture.py apps/backend/tests/test_api_capture.py
git commit -m "feat: allow capture sessions to start without an event"
```

---

## Task 7: Attach an event mid-conversation (F5)

**Files:**
- Modify: `apps/backend/app/modules/capture/store.py`, `apps/backend/app/api/capture.py`
- Test: `apps/backend/tests/test_api_capture.py`

**Interfaces consumed:** nullable `event_id`, `create_event` / `get_event` from `app.modules.sitreps.store`.

**Interfaces produced:** `POST /capture/sessions/{id}/event` — body is either `{"event_id": int}` (attach existing) or `{"title": str, "hazard_type": str, "started_at": datetime}` (create then attach). Returns `CaptureSessionResponse`. 409 if already filed; 400 if neither branch is fully specified; 404 if the event belongs to another corporation.

- [ ] **Step 1: Write the failing test**

Append to `apps/backend/tests/test_api_capture.py`:

```python
def test_attach_existing_event_to_a_session(monkeypatch):
    client = make_client(monkeypatch)
    event_id = create_event(client)
    session_id = create_capture(client)["id"]

    response = client.post(
        f"/capture/sessions/{session_id}/event", json={"event_id": event_id}
    )
    assert response.status_code == 200, response.text
    assert response.json()["event_id"] == event_id


def test_attach_creates_a_new_event_when_given_details(monkeypatch):
    client = make_client(monkeypatch)
    session_id = create_capture(client)["id"]

    response = client.post(
        f"/capture/sessions/{session_id}/event",
        json={
            "title": "August flooding",
            "hazard_type": "flood",
            "started_at": "2026-08-18T00:00:00",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["event_id"] is not None

    events = client.get("/events", params={"corporation": CORP}).json()
    assert any(item["title"] == "August flooding" for item in events)


def test_attach_requires_one_of_the_two_branches(monkeypatch):
    client = make_client(monkeypatch)
    session_id = create_capture(client)["id"]
    assert client.post(f"/capture/sessions/{session_id}/event", json={}).status_code == 400


def test_attach_rejects_an_event_owned_by_another_corporation(monkeypatch):
    client = make_client(monkeypatch)
    other = client.post(
        "/events",
        json={
            "corporation": OTHER_CORP,
            "title": "Someone else's storm",
            "hazard_type": "flood",
            "started_at": "2026-08-18T00:00:00",
        },
    ).json()["id"]
    session_id = create_capture(client)["id"]

    response = client.post(
        f"/capture/sessions/{session_id}/event", json={"event_id": other}
    )
    assert response.status_code == 404
```

`OTHER_CORP` is any second entry from `CANONICAL_CORPORATIONS` — define it beside the existing `CORP` constant. This test is the guard on the Global Constraint that a wrong `event_id` silently corrupts a running record.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/backend && .venv/bin/python -m pytest tests/test_api_capture.py -k attach -v`
Expected: FAIL — 405, the route does not exist.

- [ ] **Step 3: Write the implementation**

In `api/capture.py`, import `create_event` alongside the existing `get_event` import, then add:

```python
class AttachEventRequest(BaseModel):
    event_id: int | None = None
    title: str | None = None
    hazard_type: str | None = None
    started_at: datetime | None = None


@router.post("/capture/sessions/{session_id}/event", response_model=CaptureSessionResponse)
def post_session_event(
    session_id: int, request: AttachEventRequest, db: Session = Depends(get_session)
) -> CaptureSessionResponse:
    row = _load_owned(db, session_id)
    _require_draft(row)

    if request.event_id is not None:
        event = get_event(db, request.event_id)
        if event is None or event.corporation != row.corporation:
            raise HTTPException(
                status_code=404,
                detail=f"event not found for this corporation: {request.event_id}",
            )
        row.event_id = event.id
    elif request.title and request.hazard_type and request.started_at:
        if request.hazard_type not in HAZARD_TYPES:
            raise HTTPException(
                status_code=400, detail=f"unknown hazard_type: {request.hazard_type}"
            )
        event = create_event(
            db,
            corporation=row.corporation,
            title=request.title,
            hazard_type=request.hazard_type,
            started_at=request.started_at,
        )
        row.event_id = event.id
    else:
        raise HTTPException(
            status_code=400,
            detail="attach an existing event_id, or give title, hazard_type and started_at",
        )

    save_session(db, row)
    return _to_response(row)
```

Add `HAZARD_TYPES` to the existing `from app.modules.sitreps.models import ALERT_LEVELS` line. Check `create_event`'s signature in `app/modules/sitreps/store.py:9` and match its keyword names exactly.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/backend && .venv/bin/python -m pytest -q`
Expected: PASS, 499 passed.

- [ ] **Step 5: Commit**

```bash
git add apps/backend/app/api/capture.py apps/backend/tests/test_api_capture.py
git commit -m "feat: attach or create an event from inside a capture session"
```

---

## Task 8: Frontend data layer for the new capture contract

**Files:**
- Modify: `apps/frontend/src/types/dmcu.ts`, `src/lib/api/capture.ts`, `src/lib/queries/capture.ts`
- Create: `apps/frontend/src/lib/capture-paths.ts`, `src/lib/capture-paths.test.ts`

**Interfaces consumed:** Tasks 5–7 endpoints.

**Interfaces produced:**
- Types: `CaptureLog.row_id: string`, `CaptureSession.event_id: number | null`, `CaptureSession.manual_fields: string[]`, `CaptureSessionUpdate.manual_fields: string[]`.
- `listCaptureSessions(corporation: string, eventId?: number)`, `createCaptureSession(corporation: string, eventId?: number)`, `attachCaptureEvent(id: number, body: AttachEventBody)`.
- `captureQueries.list(corporation, eventId?)`, `useAttachCaptureEvent()`.
- `src/lib/capture-paths.ts`: `SESSION_FIELDS`, `incidentPath(rowId, field)`, `logPath(rowId, field)`, `withManual(manual: string[], path: string): string[]` — appends without duplicating.

- [ ] **Step 1: Write the failing test**

Create `apps/frontend/src/lib/capture-paths.test.ts`:

```ts
import { describe, expect, it } from 'vitest'

import { incidentPath, logPath, withManual } from '@/lib/capture-paths'

describe('capture paths', () => {
  it('namespaces paths by row kind, matching the backend vocabulary', () => {
    expect(incidentPath('3', 'injuries_count')).toBe('incident:3.injuries_count')
    expect(logPath('3', 'quantity')).toBe('log:3.quantity')
  })

  it('appends a path without duplicating an existing one', () => {
    expect(withManual(['alert_level'], 'incident:1.community')).toEqual([
      'alert_level',
      'incident:1.community',
    ])
    expect(withManual(['alert_level'], 'alert_level')).toEqual(['alert_level'])
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/frontend && pnpm test -- capture-paths`
Expected: FAIL — cannot resolve `@/lib/capture-paths`.

- [ ] **Step 3: Write the implementation**

Create `apps/frontend/src/lib/capture-paths.ts`:

```ts
// Mirrors app/modules/capture/provenance.py. The backend is the enforcement
// point; these helpers only build the paths the UI reports as hand-edited.
export const SESSION_FIELDS = [
  'as_at',
  'alert_level',
  'present_activity',
  'situation_overview',
] as const

export function incidentPath(rowId: string, field: string): string {
  return `incident:${rowId}.${field}`
}

export function logPath(rowId: string, field: string): string {
  return `log:${rowId}.${field}`
}

export function withManual(manual: string[], path: string): string[] {
  return manual.includes(path) ? manual : [...manual, path]
}
```

In `types/dmcu.ts`: add `row_id: string` to `CaptureLog`; change `CaptureSession.event_id` to `number | null`; add `manual_fields: string[]` to both `CaptureSession` and `CaptureSessionUpdate`; add

```ts
export type AttachEventBody =
  | { event_id: number }
  | { title: string; hazard_type: string; started_at: string }
```

In `lib/api/capture.ts`, make `eventId` optional on the list and create calls (omit the param entirely when undefined) and add:

```ts
export async function attachCaptureEvent(
  id: number,
  body: AttachEventBody,
): Promise<CaptureSession> {
  return withApiError(async () => {
    const { data } = await apiClient.post<CaptureSession>(
      `/capture/sessions/${id}/event`,
      body,
    )
    return data
  })
}
```

In `lib/queries/capture.ts`: make `captureKeys.list` and `captureQueries.list` take `eventId?: number` (drop the `eventId > 0` clause from `enabled`, keep `!!corporation`), and add:

```ts
export function useAttachCaptureEvent() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: { id: number; body: AttachEventBody }) =>
      attachCaptureEvent(input.id, input.body),
    onSuccess: (session) => {
      queryClient.setQueryData(captureKeys.detail(session.id), session)
      void queryClient.invalidateQueries({ queryKey: captureKeys.lists() })
      void queryClient.invalidateQueries({ queryKey: eventKeys.lists() })
    },
    onError: (error: Error) =>
      toast.error('Failed to attach event', { description: error.message }),
  })
}
```

Update `capture-pane.test.tsx`'s fixture with `manual_fields: []` and `row_id` on any logs so types still compile.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/frontend && pnpm test && pnpm exec tsc --noEmit -p tsconfig.json`
Expected: PASS, 55 tests, no type errors.

- [ ] **Step 5: Commit**

```bash
git add apps/frontend/src/types apps/frontend/src/lib
git commit -m "feat: frontend data layer for optional-event capture sessions"
```

---

## Task 9: Incident and log cards with inline editing (F9, F10)

The card is the unit of the record rail: readable by default, expands into fields in place, marks what it knows is missing, and reports every edit as a manual field path. No separate add-form panel.

**Files:**
- Create: `apps/frontend/src/components/capture/incident-card.tsx`, `src/components/capture/log-card.tsx`, `src/components/capture/incident-card.test.tsx`
- Test: as above

**Interfaces consumed:** `incidentPath`, `logPath` (Task 8).

**Interfaces produced:**

```ts
type IncidentCardProps = {
  incident: CaptureIncident
  missing: CaptureMissingField[]   // already filtered to this row by the caller
  disabled?: boolean
  onEdit: (next: CaptureIncident, paths: string[]) => void
  onRemove: () => void
}
```

`LogCardProps` is identical with `log: CaptureLog` and `next: CaptureLog`. `paths` holds only the fields whose value actually changed.

- [ ] **Step 1: Write the failing test**

Create `apps/frontend/src/components/capture/incident-card.test.tsx`:

```tsx
// @vitest-environment jsdom
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { IncidentCard } from '@/components/capture/incident-card'
import type { CaptureIncident } from '@/types/dmcu'

const incident = {
  row_id: '1',
  community: 'Petit Valley',
  street: null,
  incident_type: 'flooding',
  raw_incident_type: null,
  incident_summary: '5 houses flooded',
  event_date: null,
  injuries_occurred: null,
  injuries_count: null,
  deaths_occurred: null,
  deaths_count: null,
  building_damage: null,
  special_needs_occupants: null,
  estimated_damage_cost: null,
  action_taken: null,
  relief_supplied: null,
  forwarded_to_agency: null,
  further_assessment_required: null,
  other_follow_up: null,
} satisfies CaptureIncident

describe('IncidentCard', () => {
  it('reads as prose until it is opened', () => {
    render(
      <IncidentCard incident={incident} missing={[]} onEdit={vi.fn()} onRemove={vi.fn()} />,
    )
    expect(screen.getByText('5 houses flooded')).not.toBeNull()
    expect(screen.queryByLabelText('Community')).toBeNull()
  })

  it('reports only the changed field as a manual path', () => {
    const onEdit = vi.fn()
    render(
      <IncidentCard incident={incident} missing={[]} onEdit={onEdit} onRemove={vi.fn()} />,
    )
    fireEvent.click(screen.getByRole('button', { name: /edit/i }))
    fireEvent.change(screen.getByLabelText('Injuries count'), {
      target: { value: '4' },
    })
    fireEvent.click(screen.getByRole('button', { name: /save/i }))

    expect(onEdit).toHaveBeenCalledWith(
      expect.objectContaining({ injuries_count: 4 }),
      ['incident:1.injuries_count'],
    )
  })

  it('offers each missing detail as a control that opens the card', () => {
    render(
      <IncidentCard
        incident={incident}
        missing={[{ path: 'incidents[0].event_date', message: 'Date of the incident' }]}
        onEdit={vi.fn()}
        onRemove={vi.fn()}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: 'Date of the incident' }))
    expect(screen.getByLabelText('Date')).not.toBeNull()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/frontend && pnpm test -- incident-card`
Expected: FAIL — cannot resolve `@/components/capture/incident-card`.

- [ ] **Step 3: Write the implementation**

Create both card components. Lift the field layout and the `formToCaptureIncident` / `formToCaptureLog` mapping out of `capture-pane.tsx` (lines 244-289 and 326-379) rather than rewriting them — they already handle the string-to-number coercion. The card holds one `useAppForm`, mounted only while open, so the F1 clobber cannot recur: a closed card has no state to lose, and an open card is never reset by a server update.

Shape:

```tsx
export function IncidentCard({ incident, missing, disabled, onEdit, onRemove }: IncidentCardProps) {
  const [open, setOpen] = useState(false)
  const [focusField, setFocusField] = useState<string | null>(null)
  // ...summary view when !open: summary line, then type · community · date
  // ...missing chips: <Button variant="outline" size="sm"> per entry, each
  //    setOpen(true) and setFocusField(fieldOf(entry.path))
  // ...open view: the field grid, Cancel + Save
}
```

On save, diff the submitted values against `incident`, build `paths` with `incidentPath(incident.row_id, field)` for each changed key, and call `onEdit(next, paths)`. Return early with no call if nothing changed.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/frontend && pnpm test && pnpm exec tsc --noEmit -p tsconfig.json`
Expected: PASS, 58 tests.

- [ ] **Step 5: Commit**

```bash
git add apps/frontend/src/components/capture
git commit -m "feat: inline-editable incident and log cards"
```

---

## Task 10: The capture record rail (F4, F9, F10)

**Files:**
- Create: `apps/frontend/src/components/capture/capture-record.tsx`, `src/components/capture/capture-record.test.tsx`
- Delete: `src/components/capture/capture-pane.tsx`, `src/components/capture/capture-pane.test.tsx`

**Interfaces consumed:** `IncidentCard`, `LogCard` (Task 9); `withManual`, `SESSION_FIELDS` (Task 8).

**Interfaces produced:**

```ts
type CaptureRecordProps = {
  session: CaptureSession
  disabled?: boolean
  pending?: boolean
  onSave: (payload: CaptureSessionUpdate) => void
  onReview: () => void
}
```

Every edit saves immediately — one contract, replacing F9's two. `onSave` always carries the full `manual_fields` list, extended with whatever paths the edit touched.

- [ ] **Step 1: Write the failing test**

Create `apps/frontend/src/components/capture/capture-record.test.tsx` reusing the fixture shape from `capture-pane.test.tsx` (add `manual_fields: []`, `row_id` on logs):

```tsx
it('saves an incident edit immediately with its manual path recorded', () => {
  const onSave = vi.fn()
  render(<CaptureRecord session={session} onSave={onSave} onReview={vi.fn()} />)

  fireEvent.click(screen.getByRole('button', { name: /edit/i }))
  fireEvent.change(screen.getByLabelText('Injuries count'), { target: { value: '4' } })
  fireEvent.click(screen.getByRole('button', { name: /save/i }))

  expect(onSave).toHaveBeenCalledWith(
    expect.objectContaining({ manual_fields: ['incident:1.injuries_count'] }),
  )
})

it('summarises the record and offers review', () => {
  const onReview = vi.fn()
  render(<CaptureRecord session={session} onSave={vi.fn()} onReview={onReview} />)
  expect(screen.getByText(/1 incident/)).not.toBeNull()
  fireEvent.click(screen.getByRole('button', { name: /review & file/i }))
  expect(onReview).toHaveBeenCalled()
})

it('does not render a separate still-needed list', () => {
  render(
    <CaptureRecord
      session={{
        ...session,
        missing: [{ path: 'incidents[0].event_date', message: 'Date of the incident' }],
      }}
      onSave={vi.fn()}
      onReview={vi.fn()}
    />,
  )
  expect(screen.queryByText('Still needed')).toBeNull()
  expect(screen.getByRole('button', { name: 'Date of the incident' })).not.toBeNull()
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/frontend && pnpm test -- capture-record`
Expected: FAIL — cannot resolve `@/components/capture/capture-record`.

- [ ] **Step 3: Write the implementation**

Structure, top to bottom:

1. **Header chips** — event chip slot (filled by Task 11), alert level, `as_at`. Each is a button that opens a small popover editor; changing one calls `onSave` with the value and `withManual(session.manual_fields, 'alert_level')`. Session-level `missing` entries (`alert_level`, `as_at`) render the chip in `variant="outline"` with the message as its label.
2. **Incidents** — `IncidentCard` per row, `missing` filtered by `incidents[<index>]` prefix, then `+ Add manually` appending a blank row with a fresh `row_id` (`String(Math.max(0, ...ids) + 1)`).
3. **Situation logs** — the same with `LogCard`. Remove by `row_id`, never by index — this is F3's UI half.
4. **Footer** — sticky within the rail: `{n} incidents · {m} logs · {k} details needed` and a primary **Review & file**.

Keep `payloadOf` from the old pane; extend it to carry `manual_fields`. Delete `capture-pane.tsx` and its test in this task.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/frontend && pnpm test && pnpm exec tsc --noEmit -p tsconfig.json`
Expected: PASS. `capture-pane` tests are gone; `capture-record` tests replace them.

- [ ] **Step 5: Commit**

```bash
git add apps/frontend/src/components/capture
git commit -m "feat: replace the capture form pane with an inline-editable record rail"
```

---

## Task 11: The event chip — propose, never infer (F5)

**Files:**
- Create: `apps/frontend/src/components/capture/event-chip.tsx`, `src/components/capture/event-chip.test.tsx`
- Modify: `src/components/capture/capture-record.tsx`

**Interfaces consumed:** `useAttachCaptureEvent`, `eventQueries.list` (Task 8).

**Interfaces produced:**

```ts
type EventChipProps = {
  session: CaptureSession
  events: EventSummary[]          // this corporation's events
  disabled?: boolean
}
```

Behaviour, in order of precedence:
1. Attached → chip shows the event title, click opens the picker to change it.
2. Not attached, exactly one running event (`ended_at === null`) → chip reads `Attach to "<title>"?` and one click attaches. **Pre-selected is not pre-attached** — the officer taps.
3. Not attached, zero or many running events → chip reads `No event`, opens a sheet listing running events plus a **New event** form (title, hazard type, start date) that posts the create-and-attach branch.

- [ ] **Step 1: Write the failing test**

```tsx
it('never attaches an event without an explicit action', () => {
  const attach = vi.fn()
  renderChip({ session: sessionWithoutEvent, events: [runningEvent], attach })
  expect(attach).not.toHaveBeenCalled()
  expect(screen.getByRole('button', { name: /August flooding/ })).not.toBeNull()
})

it('attaches the single running event in one click', () => {
  const attach = vi.fn()
  renderChip({ session: sessionWithoutEvent, events: [runningEvent], attach })
  fireEvent.click(screen.getByRole('button', { name: /August flooding/ }))
  expect(attach).toHaveBeenCalledWith({ id: 1, body: { event_id: 9 } })
})

it('offers a picker rather than guessing when several events are running', () => {
  renderChip({
    session: sessionWithoutEvent,
    events: [runningEvent, otherRunningEvent],
    attach: vi.fn(),
  })
  expect(screen.getByRole('button', { name: 'No event' })).not.toBeNull()
})
```

`renderChip` wraps `EventChip` in a `QueryClientProvider` and mocks `useAttachCaptureEvent` via `vi.mock('@/lib/queries/capture', ...)`. Follow the mocking style already used in `src/components/chat/chat-thread.test.tsx`.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/frontend && pnpm test -- event-chip`
Expected: FAIL — module not found.

- [ ] **Step 3: Write the implementation**

Build the chip, then mount it as the first header chip in `CaptureRecord`. Pass `events` down from the route.

Add the constraint as a comment at the top of the file:

```tsx
// The model may talk about which event this is; it never sets event_id.
// Cross-submission supersession is event-scoped, so a wrong attachment
// silently merges one storm's record into another's.
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/frontend && pnpm test && pnpm exec tsc --noEmit -p tsconfig.json`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/frontend/src/components/capture
git commit -m "feat: attach an event from inside the conversation, by explicit tap"
```

---

## Task 12: The conversation workspace at `/corp/c/$sessionId` (F4, F6)

**Files:**
- Create: `apps/frontend/src/routes/corp/c/$sessionId.tsx`
- Delete: `src/routes/corp/events/$eventId/chat.tsx`
- Modify: `src/routeTree.gen.ts` (generated)

**Interfaces consumed:** `CaptureRecord` (Task 10), `EventChip` (Task 11), `ChatThread`, `createSseConnection`.

**Interfaces produced:** route `/corp/c/$sessionId`.

This is F4's fix: the geometry inverts.

- [ ] **Step 1: Write the failing test**

There is no route-level test harness in this codebase, so verification here is a typecheck plus a manual pass. Write the route, then run the app.

- [ ] **Step 2: Create the route**

Port `CaptureChatSession` from `chat.tsx` with these changes:

- The session comes from the route param, not from find-or-create. No `started` ref, no implicit creation — creation happens on the home page (Task 13).
- **Layout inverted.** Chat is the wide centred column; the record is the fixed rail:

```tsx
<div className="-m-4 flex min-h-0 flex-1 flex-col md:-m-6 md:flex-row">
  <main className="order-2 flex min-h-0 flex-1 flex-col px-4 py-4 md:order-1 md:px-6">
    <div className="mx-auto flex w-full min-w-0 max-w-[46rem] flex-1 flex-col">
      <ChatThread ... />
    </div>
  </main>
  <aside className="order-1 w-full shrink-0 border-b md:order-2 md:sticky md:top-0 md:h-[calc(100svh-3.5rem)] md:w-[400px] md:self-start md:overflow-y-auto md:border-b-0 md:border-l">
    <CaptureRecord ... onReview={() => setReviewing(true)} />
  </aside>
</div>
```

- **Mobile:** the rail collapses to a bottom sheet. Render a fixed bottom bar reading `{n} incidents · {m} logs` that opens `CaptureRecord` inside the existing `Sheet` component (`src/components/ui/sheet.tsx`), and hide the `aside` under `md:`. The chat is full-height above it. Verify at 390px.
- Drop the "Generate situation report" button entirely — F11 is deferred and the current button does the wrong thing. Filing goes through Task 14's sheet.
- Delete `src/routes/corp/events/$eventId/chat.tsx`.

- [ ] **Step 3: Regenerate the route tree and typecheck**

```bash
cd apps/frontend && pnpm generate-routes && pnpm exec tsc --noEmit -p tsconfig.json && pnpm test
```

Expected: no type errors, tests pass.

- [ ] **Step 4: Verify in the running app at both widths**

Start the stack, open a conversation, and confirm: the chat occupies the wide column at 1280px; at 390px the chat is full-screen with the record behind a bottom bar; an LLM turn updates the rail without disturbing an open card.

- [ ] **Step 5: Commit**

```bash
git add apps/frontend/src/routes apps/frontend/src/routeTree.gen.ts
git commit -m "feat: conversation workspace with chat as the primary column"
```

---

## Task 13: The composer-led home (F5, F6)

**Files:**
- Create: `apps/frontend/src/components/corp/composer.tsx`, `src/components/corp/composer.test.tsx`
- Modify: `src/routes/corp/index.tsx`
- Delete: `src/routes/corp/submissions.tsx`, `src/routes/corp/events/new.tsx`

**Interfaces consumed:** `useCreateCaptureSession` with optional `eventId` (Task 8).

**Interfaces produced:**
- `Composer` — a textarea that, on submit, creates an event-less session, navigates to `/corp/c/$sessionId`, and sends the typed text as the first turn.
- `/corp` renders: resume strip (if a draft exists) → composer → **Live now** → **Recent filings**.

- [ ] **Step 1: Write the failing test**

```tsx
it('creates an event-less session and hands off the first message', async () => {
  const create = vi.fn().mockResolvedValue({ id: 12 })
  const onStarted = vi.fn()
  render(<Composer corporation={CORP} createSession={create} onStarted={onStarted} />)

  fireEvent.change(screen.getByRole('textbox'), {
    target: { value: 'Flooding on Diego Martin Main Road, five houses' },
  })
  fireEvent.click(screen.getByRole('button', { name: /start/i }))

  await waitFor(() => expect(create).toHaveBeenCalledWith({ corporation: CORP }))
  await waitFor(() =>
    expect(onStarted).toHaveBeenCalledWith(
      12,
      'Flooding on Diego Martin Main Road, five houses',
    ),
  )
})

it('does not start a session on empty input', () => {
  const create = vi.fn()
  render(<Composer corporation={CORP} createSession={create} onStarted={vi.fn()} />)
  fireEvent.click(screen.getByRole('button', { name: /start/i }))
  expect(create).not.toHaveBeenCalled()
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/frontend && pnpm test -- composer`
Expected: FAIL — module not found.

- [ ] **Step 3: Write the implementation**

`Composer` takes `createSession` and `onStarted` as props so it is testable without a router or query client. The route wires them to `useCreateCaptureSession()` and `navigate({ to: '/corp/c/$sessionId', params, search: { first: text } })`; `/corp/c/$sessionId` reads `first` from search on mount and sends it as the opening turn, then clears it.

`/corp/index.tsx` becomes:

- **Resume strip** — only when `captureQueries.list(corporation)` returns a `draft`. One row: `Resume your draft from {updated_at}` → link to `/corp/c/$id`. Never a list; drafts are unfinished business, not a catalogue.
- **Composer** — centred, `max-w-2xl`, `autoFocus`, placeholder `What's happening in ${corporationLabel}?`. A `⋯` `DropdownMenu` beside it: *Upload CSV* → `/corp/import`, *Add an incident manually* → starts a session and opens the record rail directly.
- **Live now** — `eventQueries.list` filtered to `ended_at === null`, as full-width rows (alert level, incident count, last filed), linking to `/corp/events/$eventId`.
- **Recent filings** — the table lifted verbatim from `corp/submissions.tsx`, each row now linking to `/corp/filings/$submissionId` (Task 15).

Delete `corp/submissions.tsx` and `corp/events/new.tsx` — event creation now lives in the event chip's sheet (Task 11).

- [ ] **Step 4: Regenerate routes, run tests**

```bash
cd apps/frontend && pnpm generate-routes && pnpm test && pnpm exec tsc --noEmit -p tsconfig.json
```

- [ ] **Step 5: Commit**

```bash
git add apps/frontend/src
git commit -m "feat: composer-led corp home replacing the events-first landing"
```

---

## Task 14: Review before filing (F12, F14)

**Files:**
- Create: `apps/frontend/src/components/capture/review-file-sheet.tsx`, `src/components/capture/review-file-sheet.test.tsx`
- Modify: `src/routes/corp/c/$sessionId.tsx`

**Interfaces produced:**

```ts
type ReviewFileSheetProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  session: CaptureSession
  filing: boolean
  onFile: () => void
}
```

- [ ] **Step 1: Write the failing test**

```tsx
it('lists exactly what will be created and blocks filing on a missing event', () => {
  render(
    <ReviewFileSheet
      open
      onOpenChange={vi.fn()}
      session={{ ...session, event_id: null }}
      filing={false}
      onFile={vi.fn()}
    />,
  )
  expect(screen.getByText(/1 incident/)).not.toBeNull()
  expect(screen.getByText(/incidents must be attached to an event/i)).not.toBeNull()
  const button = screen.getByRole('button', { name: /file/i }) as HTMLButtonElement
  expect(button.disabled).toBe(true)
})

it('does not name a report number before the backend assigns one', () => {
  render(
    <ReviewFileSheet open onOpenChange={vi.fn()} session={session} filing={false} onFile={vi.fn()} />,
  )
  const button = screen.getByRole('button', {
    name: 'File situation report',
  }) as HTMLButtonElement
  expect(button.disabled).toBe(false)
  expect(screen.queryByText(/#\d/)).toBeNull()
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/frontend && pnpm test -- review-file-sheet`
Expected: FAIL — module not found.

- [ ] **Step 3: Write the implementation**

A `Sheet` (side `right` on desktop, `bottom` on mobile) containing: the event, alert level and `as_at`; counts; the incident and log summaries as read-only rows; any remaining `missing` entries as a warning block (filing with gaps is allowed — an officer under pressure files what they have); then the primary action.

The button reads **File situation report**, with no number — F12. `sequence_no` is backend-assigned and only known from the response, so it is shown afterwards, not before. Disable it, with the reason stated inline, when `event_id === null && incidents.length > 0` — the client-side mirror of Task 6's 400.

On success, close the sheet and navigate to `/corp/filings/$submissionId` (Task 15) so the officer lands on the durable artifact rather than a dead disabled chat — F14's second half.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/frontend && pnpm test && pnpm exec tsc --noEmit -p tsconfig.json`

- [ ] **Step 5: Commit**

```bash
git add apps/frontend/src/components/capture apps/frontend/src/routes
git commit -m "feat: review sheet before filing a captured situation report"
```

---

## Task 15: Read back a filed situation report (F8)

**Files:**
- Create: `apps/frontend/src/routes/corp/filings/$submissionId.tsx`
- Modify: `src/routes/corp/events/$eventId/index.tsx`

**Interfaces consumed:** `submissionQueries.detail` (exists), `GET /submissions/{id}` (exists — `app/api/submissions.py:196`). No backend work.

**Interfaces produced:** route `/corp/filings/$submissionId`.

- [ ] **Step 1: Build the route**

Header: `Situation Report #{sequence_no}`, `As at {as_at} · {alert_level}`, back-link to the event. Body: present activity and situation overview; incident and log counts; `SubmissionResult`-style rendering of `row_errors` when non-empty; the source (`source_file`, or `conversation` for captured filings).

- [ ] **Step 2: Link the rows that had no link**

In `events/$eventId/index.tsx`, wrap `SubmissionRow`'s `ContentCard` in a `Link` to `/corp/filings/$submissionId`. Do the same for the Recent filings rows on the home page (Task 13).

- [ ] **Step 3: Regenerate routes and typecheck**

```bash
cd apps/frontend && pnpm generate-routes && pnpm exec tsc --noEmit -p tsconfig.json && pnpm test
```

- [ ] **Step 4: Verify in the running app**

File a report, land on the filing page, navigate away, reopen it from both the event page and the home table.

- [ ] **Step 5: Commit**

```bash
git add apps/frontend/src
git commit -m "feat: reopen a filed situation report"
```

---

## Task 16: Retire the corp sidebar and the old routes (F5)

**Files:**
- Modify: `apps/frontend/src/components/app-sidebar.tsx`, `src/routes/__root.tsx`
- Delete: `src/routes/corp/events/$eventId/file.tsx` → moved to `src/routes/corp/import.tsx`

**Interfaces produced:** corp identity renders no sidebar; DMU is unchanged.

- [ ] **Step 1: Suppress the sidebar for corp**

In `__root.tsx`, read `useIdentity()` inside a child of `IdentityProvider` and render `<AppSidebar />` and `<SidebarTrigger />` only when `identity?.role !== 'corp'`. For corp, the header carries the app name, the corporation, and `IdentityBadge` — nothing else. Two nav links do not earn 256px on a phone.

In `app-sidebar.tsx`, delete `CORP_NAV` and the stale comment at lines 27-29 — the constraint it documents is exactly what this plan removed.

- [ ] **Step 2: Move CSV upload to `/corp/import`**

Move `events/$eventId/file.tsx` to `src/routes/corp/import.tsx`, taking `event_id` from a search param rather than the path. It stays reachable from the composer's `⋯` menu and from the event page. It is unchanged otherwise — F15's CSV half is deferred.

- [ ] **Step 3: Regenerate routes and typecheck**

```bash
cd apps/frontend && pnpm generate-routes && pnpm exec tsc --noEmit -p tsconfig.json && pnpm test
```

Expected: no dangling `Link to` references to deleted routes.

- [ ] **Step 4: Full verification**

```bash
cd apps/backend && .venv/bin/python -m pytest -q
cd ../frontend && pnpm test && pnpm exec tsc --noEmit -p tsconfig.json && pnpm build
```

Then walk the whole path in the running app at 390px and 1280px: land on `/corp` → type into the composer → conversation opens → facts land in the rail → attach the event by tapping the chip → correct a number by hand → send another turn and confirm the correction survives → review → file → land on the filing → reopen it from home.

- [ ] **Step 5: Commit**

```bash
git add apps/frontend/src
git commit -m "feat: retire the corp sidebar and event-gated route tree"
```

---

## Deferred Backlog

Named, scoped, and deliberately out of this iteration.

### Iteration 2 — the live draft report (F11)

**Flaw:** the current "Generate situation report" button (`chat.tsx:208-217`) produces a corporation-wide `corp_situation_report` over `date_from`→`date_to`, not a report on what the conversation captured. Task 12 removes the button rather than fixing it, because fixing it correctly needs a report template scoped to a single submission — a backend change to `app/core/report_models.py` and a new template version, which is its own plan.

**Target:** the record rail gains a **Draft** tab holding the rendered sitrep, regenerated as the working set changes. This gives one surface three jobs — the review step, a continuous "here is what the DMU will see", and the most natural place to catch a wrong number. Note the sitrep is a *running* record (#1, #2, #3 during one event), so this must never be framed as a terminal step.

**Prerequisite:** a `corp_situation_report_single` template parameterised by `submission_id`, plus a preview endpoint that renders an unfiled working set.

### Iteration 2 — model-proposed event attachment (F5, partial)

Task 11 ships precedence rules 1–3 without any model involvement. The natural next step is for the turn response to carry an `event_suggestion` — `{event_id, confidence, reason}` or a proposed new-event title — surfaced as a one-tap chip inside the thread. It is deferred because it widens the prompt contract and the streaming payload, and because the zero-or-one-running-event case that rules 1–3 already cover is the overwhelming majority. **The rule does not relax:** the model proposes, the tap commits.

### Iteration 3 — event detail endpoint (F13)

`events/$eventId/index.tsx:42` finds the event by scanning `eventQueries.list(corporation)`, so the page cannot render until the whole list loads and a foreign deep link renders a bare "Event". Needs `GET /events/{id}` plus `eventQueries.detail`. Low severity — corporations have few events — but it is the difference between a 404 and a silently blank page.

### Iteration 3 — unify the two situation forms (F15)

`events/$eventId/file.tsx:188` and the capture header collect the same four fields with different behaviour: the CSV form prefills from the last submission, the capture record does not. Task 10 fixes the capture side; the CSV side keeps its own form until the two can share one component. Carry-forward prefill is arguably right for both — an officer filing #4 is usually editing #3 — and should be decided once rather than diverging further.

### Iteration 3 — draft lifecycle

Nothing ages out a draft capture session. The resume strip in Task 13 shows the most recent one, but a corporation that starts five conversations during a storm accumulates five drafts forever. Needs a policy — auto-discard empty drafts after N days, prompt to file or discard on reopen — and a `DELETE /capture/sessions/{id}`.

### Iteration 3 — concurrent officers

Two officers of one corporation can hold two draft sessions against one event and file both. `next_sequence_no` will number them correctly, but neither officer can see the other's draft. Out of scope until identity is more than a `localStorage` declaration, but worth recording: the fix is a presence indicator on the resume strip, not locking.

---

## Verification Summary

| Gate | Command | Expected |
|------|---------|----------|
| Backend | `cd apps/backend && .venv/bin/python -m pytest` | 478 baseline → 499 after Task 7, no failures |
| Migration | `rm -f /tmp/m.db && DATABASE_URL="sqlite:////tmp/m.db" .venv/bin/python -m alembic upgrade head && ... alembic check` | applies from empty; no pending operations |
| Frontend | `cd apps/frontend && pnpm test` | 52 baseline → higher, no failures |
| Types | `cd apps/frontend && pnpm exec tsc --noEmit -p tsconfig.json` | clean |
| Build | `cd apps/frontend && pnpm build` | succeeds |
| Manual | full corp path at **390px** and 1280px | see Task 16 Step 4 |
