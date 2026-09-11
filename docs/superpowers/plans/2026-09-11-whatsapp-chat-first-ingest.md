# Chat-First WhatsApp Ingest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Phase gate:** do not start Phase N+1 until Phase N's implementation self-review is written into the PR and every item in that review is either fixed or explicitly deferred with a reason.

**Goal:** Let a DMU officer start a WhatsApp hour from **pasted text or a `.txt` export**, then (in later phases) chat against that context to capture incidents/logs and produce the provisional briefing — the same interaction pattern as corp capture, without merging the two pipelines.

**Architecture:** Three shippable phases. (1) **Dual input** — `POST /whatsapp/extract` accepts a textarea body *or* a text file; export-shaped text is parsed as WhatsApp messages, free text becomes one context blob; the existing draft form still works. (2) **Conversation** — the draft gains a real chat thread and a record rail; each turn updates the working set with corp-style provenance and a stricter number-invention guard that still sees the source transcript. (3) **Live briefing** — the rail gains a draft briefing tab regenerated from included, attributed rows. `CaptureSession` is **not** reused.

**Tech Stack:** FastAPI, SQLAlchemy 2.x, Alembic, pytest · React 19, TanStack Router + Query + Form + `@tanstack/ai-react`, Tailwind 4, Vitest + Testing Library.

**Source review:** current WhatsApp hour is upload-only (`POST /whatsapp/extract` requires a `.txt` file, `parse_export` must find messages, else 400). Adjustment is a single `POST .../adjust` with no history and **no transcript in the prompt**. Corp capture at `/corp` + `/corp/c/$sessionId` is the interaction template: composer, SSE turns, working-set rail, `pin_manual_fields`, `strip_invented_numbers`.

---

## Global Constraints

- **Do not merge WhatsApp into `CaptureSession`.** Corp capture is one corporation filing its own sitrep. WhatsApp hour is DMU-facing, multi-corp, quote-backed, and produces a *provisional* briefing. Reuse `ChatThread` / SSE / `strip_invented_numbers` / the pin-manual-fields *idea*. Do not reuse the capture table, file endpoint, or event chip.
- **No authentication work.** Identity stays a `localStorage` declaration. This screen is DMU-only (`RoleMismatchNotice expected="dmu"`). Do not add lock icons or permission language.
- **Input in Phase 1 is exclusive-or:** a textarea **or** a `.txt` file, never both, never neither. Empty `<input type="file">` from the browser is *absent*, not a file.
- **PII redaction runs on every source before extract**, paste included. `redact_phones` already exists in `app/modules/whatsapp/parse.py`.
- **The LLM never commits a corporation.** It may fill `corporation` as a proposal. `included` stays false until a canonical slug is set. Once the officer sets a corporation by hand, that path is manual (Phase 2).
- **Never invent a number** that is not in the source transcript, the current working set, or the officer's latest message. Zero is always allowed. This is the same guard as `modules/capture/numbers.py` and `modules/whatsapp/adjust.py` — Phase 2 must *widen* the allowed set to include `source_text`, not drop it.
- **Briefing is not a cited national SITREP.** Keep `PROVISIONAL_BANNER`. File-to-store remains optional and must stay visibly secondary.
- **A submission carrying incidents MUST name an event.** Promote already auto-creates `WhatsApp update {date}` events. Do not silently change that in Phases 1–2. Phase 3 warns; stopping auto-create is deferred.
- **`@testing-library/jest-dom` is NOT installed.** Assert with plain matchers. Every frontend test file that renders starts with `// @vitest-environment jsdom`.
- **Backend tests:** `cd apps/backend && .venv/bin/python -m pytest`. **Frontend:** `cd apps/frontend && pnpm test` and `pnpm exec tsc --noEmit -p tsconfig.json`. Never add a `test` block to `vite.config.ts`.
- **Migrations apply from empty.** SQLite has no `ALTER COLUMN` — use `op.batch_alter_table`. Confirm head with `alembic heads` before writing; at plan time head is **`e5b1c7d83a24`**.
- **Mobile is in scope from Phase 2.** DMU may use a laptop, but the corp plan's 390px check still applies to the conversation workspace.

---

## Flaw Register

| ID | Flaw | Location | Severity | Resolution |
|----|------|----------|----------|------------|
| **W1** | Extract is file-only. Officers often have a forwarded snippet, not `Export chat → Without media`. | `api/whatsapp.py:117-135`, `routes/dmu/whatsapp.tsx` upload form | High | Phase 1 |
| **W2** | Free text that is not a WhatsApp export 400s (`no messages found`). | `api/whatsapp.py:134-135` | High | Phase 1 |
| **W3** | Draft status `queued`/`running` is not polled. On a non-eager job backend the workspace renders an empty extract until refresh. | `whatsappQueries.draft` has no `refetchInterval` | High | Phase 1 |
| **W4** | "Chat" is a one-shot adjust box with no history and no streaming. | `POST .../adjust`, `whatsapp.tsx` instruction textarea | High | Phase 2 |
| **W5** | Adjust never sees the transcript. A pasted snippet that extract missed cannot be recovered by talking. | `adjust.py` docstring + prompt payload | High | Phase 2 |
| **W6** | No provenance. A hand-typed corporation or count can be rewritten by the next adjust. | `WhatsAppDraft` JSON columns; no `manual_fields` | High | Phase 2 |
| **W7** | Rows keyed by `${source_index}-${index}`. A model reorder deletes the wrong card. | `whatsapp.tsx` IncidentCard/LogCard keys | High | Phase 2 |
| **W8** | Geometry is form-first. Conversation (when it exists) is a box above the cards. | `DraftWorkspace` | Medium | Phase 2 |
| **W9** | Briefing is a bottom-of-page one-shot, not a live view of the working set. | `POST .../briefing` + result card | Medium | Phase 3 |
| **W10** | Promote writes into `sitrep_incidents` as if corporations signed the figures, and auto-creates events. | `confirm.py:146-180` | High (product) | Phase 3 warning; auto-create **deferred** |
| **W11** | `.zip` / With media exports, and images, are unsupported. | parse | Low | **Deferred** |

---

## File Structure

**Phase 1 — create:**
- `apps/frontend/src/components/whatsapp/source-form.tsx` + `source-form.test.tsx`

**Phase 1 — modify:**
- `app/modules/whatsapp/parse.py` — `messages_from_source`
- `app/modules/whatsapp/models.py`, `store.py`, `api/whatsapp.py`
- `apps/backend/alembic/versions/<rev>_whatsapp_source_kind.py`
- `app/jobs/whatsapp.py` — pass `source_kind` through extract
- `apps/frontend/src/lib/api/whatsapp.ts`, `lib/queries/whatsapp.ts`, `types/dmcu.ts`
- `apps/frontend/src/routes/dmu/whatsapp.tsx` — landing uses the source form; draft polls

**Phase 2 — create:**
- `app/modules/whatsapp/turn.py`, `provenance.py`, `missing.py`
- `apps/frontend/src/components/whatsapp/draft-record.tsx` (+ incident/log cards if they leave the route file)
- `apps/frontend/src/lib/whatsapp-paths.ts`
- `apps/frontend/src/routes/dmu/whatsapp.$draftId.tsx` (optional split; otherwise invert in place)

**Phase 2 — modify:**
- Draft model: `messages`, `manual_fields`
- `api/whatsapp.py` — turns + stream
- `prompt.py` — turn prompt (keep extract prompt)
- Frontend ChatThread wiring

**Phase 3 — create:**
- `apps/frontend/src/components/whatsapp/briefing-pane.tsx`
- `apps/frontend/src/components/whatsapp/review-briefing-sheet.tsx`

**Phase 3 — modify:**
- Briefing generation to also persist a preview on the draft (or reuse `reports` with polling, which already exists)
- File-to-store copy/warning

Do **not** delete `POST /whatsapp/extract` or `POST /whatsapp/drafts/{id}/adjust` until Phase 2's turn path is the UI's only adjust. Adjust may become a wrapper around `apply_turn`.

---

# Phase 1 — Dual input (textarea or `.txt`)

Shippable alone. After this phase a DMU officer can paste the hour *or* upload a WhatsApp `.txt`, get a draft, and use today's adjust / briefing / promote. No conversation workspace yet.

## Task 1: Classify source text (export vs paste)

**Files:**
- Modify: `apps/backend/app/modules/whatsapp/parse.py`
- Test: `apps/backend/tests/test_whatsapp_parse.py`

**Interfaces produced:**

```python
SourceKind = Literal["export", "paste"]

def messages_from_source(text: str) -> tuple[list[ParsedMessage], SourceKind, bool]:
    """Redact, then parse as a WhatsApp export if any messages match.

    If parse_export finds nothing, return a single synthetic message:
    index=1, timestamp=None, sender="paste", body=<redacted text>.
    The bool is whether any phone token was redacted.
    """
```

Rules:
- Always run `redact_phones` on the raw text first (and `parse_export` already redacts per-message; do not double-mark if the export path already redacts — redact once at the top, then parse the redacted string, **or** keep parse_export's redaction and only redact the paste blob. Prefer: redact the full string once, then parse; update `parse_export` tests if behaviour of already-redacted `[phone]` is unchanged).
- `sender="paste"` is **not** a corporation slug. Canonical slug validation must never treat it as one.
- Do not invent timestamps for paste.
- Empty / whitespace-only text returns `([], "paste", False)` — the API layer 400s. This helper does not raise.

- [ ] **Step 1: Write the failing tests** in `test_whatsapp_parse.py`:

```python
def test_messages_from_source_keeps_a_bracket_export():
    messages, kind, pii = messages_from_source(BRACKET_EXPORT)
    assert kind == "export"
    assert len(messages) == 2
    assert messages[0].sender == "Jane Doe"


def test_messages_from_source_wraps_free_text_as_one_paste_message():
    text = "Diego Martin: 5 houses flooded on Main Rd. Siparia standing by."
    messages, kind, pii = messages_from_source(text)
    assert kind == "paste"
    assert len(messages) == 1
    assert messages[0].index == 1
    assert messages[0].sender == "paste"
    assert messages[0].timestamp is None
    assert "5 houses" in messages[0].body


def test_messages_from_source_redacts_phones_in_pasted_text():
    messages, kind, pii = messages_from_source(
        "Call +1 868-555-1234 about the depot"
    )
    assert kind == "paste"
    assert pii is True
    assert "[phone]" in messages[0].body
    assert "868-555-1234" not in messages[0].body
```

- [ ] **Step 2:** `cd apps/backend && .venv/bin/python -m pytest tests/test_whatsapp_parse.py -k messages_from_source -v` → FAIL (`messages_from_source` missing).

- [ ] **Step 3: Implement** `messages_from_source` next to `parse_export`. Reuse `_PHONE_RE` / `redact_phones`. If `parse_export(redacted)` is non-empty → `("export", ...)`. Else if redacted strip is non-empty → one `ParsedMessage`. Else empty list.

- [ ] **Step 4:** Re-run the parse file. All existing parse tests still pass.

- [ ] **Step 5: Commit** `feat: classify pasted WhatsApp context vs export`

## Task 2: Persist `source_kind` and accept text or file on extract

**Files:**
- Modify: `models.py`, `store.py`, `api/whatsapp.py`, `jobs/whatsapp.py` (only if extract needs the kind; job can keep calling `parse_export` **or** switch to `messages_from_source` so paste extracts)
- Create: Alembic revision off current head
- Test: `tests/test_api_whatsapp.py`, `tests/test_whatsapp_store.py` if store helpers change

**Job change (required):** `run_extract` must call `messages_from_source(draft.source_text)` instead of `parse_export`, so a paste draft actually extracts. Today `parse_export` on free text yields `[]` and `extract_proposals` returns empty.

**API contract:**

```
POST /whatsapp/extract   multipart/form-data
  file: UploadFile | omitted
  text: str | omitted
  as_at: datetime | omitted   # default now, unchanged
```

- File present and non-empty **xor** `text` stripped non-empty. Both → 400 `"send either a file or pasted text, not both"`. Neither → 400 `"paste the hour or upload a WhatsApp .txt export"`.
- File still must end in `.txt` (case-insensitive). Pasted text has no filename check.
- Empty file bytes → treat as absent (then fall through to text / neither).
- `filename`: upload's filename, or `"pasted.txt"` for the text path.
- `source_kind` stored and returned on `DraftResponse` / `DraftSummary`.
- Existing file-only tests keep passing (they only send `file`).

`create_draft` gains `source_kind: str = "export"`.

Migration:

```python
def upgrade() -> None:
    with op.batch_alter_table("whatsapp_drafts") as batch:
        batch.add_column(
            sa.Column("source_kind", sa.String(), nullable=False, server_default="export")
        )
```

- [ ] **Step 1: Failing API tests** (append to `test_api_whatsapp.py`, same `make_client` / `CHAT` / `EXTRACT_JSON` fixtures):

```python
def test_extract_accepts_pasted_text(monkeypatch):
    client = make_client(monkeypatch)
    response = client.post(
        "/whatsapp/extract",
        data={"text": "Diego Martin: 3 houses flooded in Petit Valley"},
    )
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["filename"] == "pasted.txt"
    assert body["source_kind"] == "paste"
    assert body["message_count"] == 1
    assert body["incidents"]  # extract ran against the paste blob


def test_extract_pasted_export_text_is_classified_as_export(monkeypatch):
    client = make_client(monkeypatch)
    response = client.post("/whatsapp/extract", data={"text": CHAT})
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["source_kind"] == "export"
    assert body["filename"] == "pasted.txt"
    assert body["message_count"] == 2


def test_extract_rejects_file_and_text_together(monkeypatch):
    client = make_client(monkeypatch)
    response = client.post(
        "/whatsapp/extract",
        data={"text": "Diego Martin standing by"},
        files={"file": ("hour.txt", CHAT.encode("utf-8"), "text/plain")},
    )
    assert response.status_code == 400


def test_extract_rejects_neither_file_nor_text(monkeypatch):
    client = make_client(monkeypatch)
    response = client.post("/whatsapp/extract", data={"as_at": "2026-08-15T16:00:00"})
    assert response.status_code == 400
```

Keep `test_extract_rejects_non_txt` and `test_extract_rejects_empty_file`. Add: empty file + non-empty text is accepted as paste (browser will do this if both widgets exist — the API still 400s on *both nonempty*; the UI will not send both. Optional extra test: `files={"file": ("", b"", "application/octet-stream")}` + `text=...` → 202 paste. Implement if FastAPI actually forwards that empty part.)

- [ ] **Step 2:** Run the new tests → FAIL (no `text` field / no `source_kind`).

- [ ] **Step 3: Implement.** `file: UploadFile | None = File(None)`, `text: str | None = Form(None)`. Helper `_read_source(file, text) -> tuple[str, str, str]` returning `(raw_text, filename, source_kind)` after `messages_from_source`. `message_count = len(messages)`. Reject `len(messages)==0`. Enqueue extract as today.

- [ ] **Step 4:** Full whatsapp pytest file + `alembic upgrade head` + `alembic check` from empty sqlite.

- [ ] **Step 5: Commit** `feat: accept pasted text or a WhatsApp txt on extract`

## Task 3: Frontend source form — textarea or file

**Files:**
- Create: `apps/frontend/src/components/whatsapp/source-form.tsx`, `source-form.test.tsx`
- Modify: `lib/api/whatsapp.ts`, `lib/queries/whatsapp.ts`, `types/dmcu.ts`, `routes/dmu/whatsapp.tsx`

**UI (required):** one landing card, two modes, exclusive-or.

```
WhatsApp hour
Start from a pasted snippet or a .txt export (Chat → Export chat → Without media).

( ) Paste text     ( ) Upload .txt     ← tabs or segmented control, Paste default

[ textarea, min-h ~ 8rem
  placeholder: "Paste the hour, a forwarded snippet, or anything operational…" ]

  — or, in Upload mode —

[ file field accept=".txt,text/plain" ]

As at  [datetime-local, default now]
[ Extract ]   disabled while the active input is empty
```

Switching mode **clears** the other value so the client cannot send both.

`extractWhatsApp` becomes:

```ts
export async function extractWhatsApp(input: {
  file?: File
  text?: string
  asAt: string
}): Promise<WhatsAppExtractResult>
```

Append `file` xor `text` to `FormData`. Types: `WhatsAppDraft.source_kind: 'export' | 'paste'`. Summaries too if listed.

Draft query polls while extracting:

```ts
refetchInterval: (query) => {
  const status = query.state.data?.status
  return status === 'queued' || status === 'running' ? 2000 : false
}
```

Workspace: if `status` is queued/running, show `LoadingBlock` (or a one-line "Extracting the hour…") instead of the empty-cards empty state. If `failed`, show `draft.error`. Filename line: paste → "Pasted context" (do not show `pasted.txt` as if it were an export). `formatDisplayLabel` is fine for slugs, not for this — hardcode the paste label.

- [ ] **Step 1: Failing component tests** (`source-form.test.tsx`, jsdom, same style as `composer.test.tsx`):

```tsx
it('submits pasted text and not a file', async () => {
  const onSubmit = vi.fn().mockResolvedValue(undefined)
  render(<WhatsAppSourceForm onSubmit={onSubmit} />)
  fireEvent.change(screen.getByLabelText(/paste/i), {
    target: { value: 'Diego Martin: 5 houses flooded' },
  })
  fireEvent.click(screen.getByRole('button', { name: /extract/i }))
  await waitFor(() =>
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ text: 'Diego Martin: 5 houses flooded' }),
    ),
  )
  expect(onSubmit.mock.calls[0][0].file).toBeUndefined()
})

it('submits a txt file and not text', async () => {
  const onSubmit = vi.fn().mockResolvedValue(undefined)
  render(<WhatsAppSourceForm onSubmit={onSubmit} />)
  fireEvent.click(screen.getByRole('tab', { name: /upload/i })) // or the segmented button
  const file = new File(['[15/08/2026, 14:32:10] Jane: hello'], 'hour.txt', {
    type: 'text/plain',
  })
  fireEvent.change(screen.getByLabelText(/whatsapp export/i), { target: { files: [file] } })
  fireEvent.click(screen.getByRole('button', { name: /extract/i }))
  await waitFor(() =>
    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ file })),
  )
  expect(onSubmit.mock.calls[0][0].text).toBeUndefined()
})

it('does not submit when paste is empty', () => {
  const onSubmit = vi.fn()
  render(<WhatsAppSourceForm onSubmit={onSubmit} />)
  fireEvent.click(screen.getByRole('button', { name: /extract/i }))
  expect(onSubmit).not.toHaveBeenCalled()
})
```

Label the textarea with a real `<Label htmlFor>` so `getByLabelText` works. Do **not** use `toBeInTheDocument`.

- [ ] **Step 2:** `pnpm test -- source-form` → FAIL (module missing).

- [ ] **Step 3: Implement** the form (props: `onSubmit`, `pending?`, `error?`). Wire `UploadView` to it. Drop the old file-only `uploadSchema` that required `File`. Update page description: paste or upload.

- [ ] **Step 4:** `pnpm test && pnpm exec tsc --noEmit -p tsconfig.json`

- [ ] **Step 5: Commit** `feat: start WhatsApp hour from paste or txt upload`

## Task 4: Phase 1 verification

```bash
cd apps/backend && .venv/bin/python -m pytest tests/test_whatsapp_parse.py tests/test_api_whatsapp.py tests/test_whatsapp_extract.py tests/test_whatsapp_store.py -q
rm -f /tmp/m.db && DATABASE_URL="sqlite:////tmp/m.db" .venv/bin/python -m alembic upgrade head
DATABASE_URL="sqlite:////tmp/m.db" .venv/bin/python -m alembic check
cd ../frontend && pnpm test && pnpm exec tsc --noEmit -p tsconfig.json
```

Manual (or browser): DMU identity → `/dmu/whatsapp` → paste a snippet → Extract → draft with rows. Back → Upload tab → sample `apps/backend/fixtures/sample_whatsapp.txt` → same workspace. Confirm you cannot fill both at once.

---

## Phase 1 — Author self-review

Reviewed against the product ask ("textarea or text file upload, then later chat to capture").

**What this phase gets right**
- XOR input matches the ask. File-only is the current trap; adding paste *without* removing the required file would still block people who only have a snippet.
- Classifying paste vs export avoids inventing fake WhatsApp senders for "Diego Martin, 5 houses". That would poison `source_quote` and later attribution.
- Running extract on the paste blob means Phase 1 is useful *before* chat exists. If we stored text and showed an empty form, officers would have only Adjust — and Adjust cannot see the transcript today (W5).
- Polling (W3) is in Phase 1 because paste and file both enqueue. Shipping dual input without it looks broken on Postgres.

**Risks caught, and how the phase handles them**
- *Empty file + pasted text:* browsers often submit an empty file part. The API treats empty file as absent; the UI clears the inactive mode. Implementation self-review must hit this with a TestClient case if FastAPI forwards empty uploads.
- *Sender `"paste"` attributed as a corp:* it is not a canonical slug; `canonical_or_none` returns null. Extract may still guess Diego Martin from the body — that is existing extract behaviour and is OK as a proposal (`included` follows `default_included`).
- *Paste that happens to contain one `[dd/mm/yyyy, hh:mm] Name:` line:* classified as export. Correct: it *is* an export fragment.
- *as_at still on the form:* the user asked for textarea or file, not to remove as-at. Default now. Leave it.
- *Scope creep:* this phase does **not** add ChatThread, provenance, or briefing changes. If those land here, revert them.

**Would I change the design?** No. Alternative considered: send JSON `{text}` instead of multipart — worse, because the file path is already multipart. One endpoint, two parts, XOR.

---

## Phase 1 — Implementation self-review (gate)

After the code exists, answer these in the PR before Phase 2. If an answer is "no", fix it or defer with a reason.

1. Can a DMU officer extract from **only** a textarea, with no file chosen?
2. Can they extract from **only** a `.txt` upload, with the textarea empty/hidden?
3. Does sending both nonempty file and text 400?
4. Are phones in a paste replaced with `[phone]` before the model sees them?
5. Does a non-export paste still produce `message_count >= 1` and run extract (not 400 `no messages found`)?
6. Does an actual export (bracket or dash) still set `source_kind=export` and keep real senders?
7. Does the draft workspace poll until `ready`/`failed` instead of flashing empty cards?
8. Do existing file extract / confirm / briefing tests still pass?
9. Did this phase add a conversation UI? (Must be **no**.)

---

# Phase 2 — Conversation over the working set

Make talking the way the officer corrects and completes the extract. Extract from Phase 1 remains the seeding turn. Do not invert briefing yet.

## Task 5: Stable row ids and field-path provenance

Mirror capture Tasks 2–4, **on WhatsApp types**, not by importing `CaptureWorkingSet`.

**Files:**
- Create: `app/modules/whatsapp/provenance.py`
- Modify: `extract.py` (`DraftIncident.row_id`, `DraftLog.row_id`), `adjust.py` / future `turn.py`
- Tests: `tests/test_whatsapp_provenance.py`, extend `test_whatsapp_adjust.py`

Paths: `incident:<row_id>.<field>`, `log:<row_id>.<field>`, plus `as_at` if the officer sets it. `corporation` and `included` are pin-able — a hand-assigned corp must survive the next turn.

`pin_manual_fields` for WhatsApp restores dropped rows that have any manual path, same as capture.

Adjust (until Task 7 replaces it) must pin after coerce, or hand edits remain unsafe as soon as the UI records `manual_fields`.

- [ ] Tests: manual corporation survives a model rewrite; invented injuries_count stripped unless in instruction/working set/**source_text** (add source_text to allowed numbers in the turn module, Task 7; adjust can keep today's narrower set until then).
- [ ] Commit `feat: pin hand-edited WhatsApp draft fields`

## Task 6: Persist messages and manual_fields

**Files:** models, store, api `DraftResponse`, Alembic, `test_api_whatsapp.py`

```python
messages: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
manual_fields: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
```

`PUT /whatsapp/drafts/{id}` accepts `manual_fields`. Coerce `row_id` on read if old drafts omit it.

- [ ] Commit `feat: persist WhatsApp draft conversation provenance`

## Task 7: Chat turns (sync + SSE)

**Files:**
- Create: `app/modules/whatsapp/turn.py`, `missing.py`
- Modify: `prompt.py` (new `TURN_PROMPT`; do not break `SYSTEM_PROMPT` / `ADJUST_PROMPT`), `api/whatsapp.py`

**Endpoints:**

```
POST /whatsapp/drafts/{id}/turns            { "message": str }
POST /whatsapp/drafts/{id}/turns/stream     same SSE shape as capture (`RUN_STARTED`, `TEXT_MESSAGE_*`, `CUSTOM` with working set)
```

Copy the capture SSE envelope from `api/capture.py` so `createSseConnection` + `ChatThread` work unchanged.

**Turn payload to the model:**

```json
{
  "working": { "as_at", "incidents", "logs", "manual_fields" },
  "missing": [ { "path", "message" } ],
  "manual": ["..."],
  "source_kind": "export" | "paste",
  "source": "<serialize_messages of the stored source, redacted, possibly truncated with a note>",
  "messages": [ { "role", "content" } ],
  "user_message": "..."
}
```

`TURN_PROMPT` returns `{ "assistant_message", "incidents", "logs" }` (and may echo `as_at`). Rules: full working set each time; preserve `row_id` / `source_index` / `source_quote` unless the officer drops the row; at most two missing-field probes; never invent numbers; never copy phones; corporation null when unsure.

**Allowed numbers** = `extract_numbers(user_message) | numbers_from_working_set(working) | extract_numbers(source_text)`. This is the W5 fix. Truncating `source` in the prompt for context size does **not** remove those numbers from the allowed set — compute allowed from the full `source_text`.

**Missing fields (WhatsApp-specific):**
- `as_at` if somehow unset
- each row with `corporation is null`: "Assign a corporation"
- included row with empty summary/statement

Do not nag `alert_level` — WhatsApp drafts have no corp alert level.

**Adjust wrapper:** `POST .../adjust` calls the same `apply_turn` with `instruction` as the user message, so existing tests keep working. Point `get_llm_client("chat")` the same way.

400 if draft status is not `ready` (still extracting / failed).

- [ ] Tests: turn updates rows; invented number from the model but present in `source_text` is **kept**; invented number in neither source, working set, nor message is **stripped**; manual corp pinned; empty message 400.
- [ ] Commit `feat: WhatsApp draft chat turns with source-aware number guard`

## Task 8: Conversation workspace UI

**Files:**
- Create: `components/whatsapp/draft-record.tsx` (+ tests), optionally split cards out of `whatsapp.tsx`
- Modify: `routes/dmu/whatsapp.tsx` (or `whatsapp.$draftId.tsx` + generate-routes)

**Geometry:** copy `/corp/c/$sessionId` — chat wide column, record rail ~400px, mobile bottom sheet. Reuse `ChatThread`, `createSseConnection('/whatsapp/drafts/${id}/turns/stream')`.

Landing stays Phase 1's source form (the corp "composer" analogue). After extract `ready`, the workspace is chat + rail, not the adjust textarea.

Rail: include checkbox, corporation select, summary/statement, quote line (`Message {n}: "…"`). Saves go through `PUT` with `manual_fields` via `withManual`. Keys by `row_id`.

Remove the standalone Adjust box. The thread *is* adjust.

Do not add "Generate situation report" that hits corp templates. Briefing stays Phase 3; **keep** the existing Generate briefing + File to store buttons in the rail footer so Phase 2 does not regress the hour.

- [ ] Frontend tests for the rail: include toggle records a manual path; empty thread composer still present.
- [ ] `pnpm generate-routes` if a new route file is added.
- [ ] Commit `feat: chat-first WhatsApp draft workspace`

## Task 9: Phase 2 verification

Backend pytest (whatsapp + capture, capture must not regress). Frontend test + tsc.

Manual at 390px and 1280px: paste → extract → chat "Diego Martin not Siparia" → corp on the rail changes → hand-edit a count → another turn → count survives → briefing still works from the footer.

---

## Phase 2 — Author self-review

**What this phase gets right**
- Conversation is the missing half of the original ask ("chat with the bot to capture and process the report from the WhatsApp context").
- Keeping extract as the seed avoids stuffing a 12k-chunk job into the first SSE turn. Chat then operates on a working set, which is what corp does after the officer's first message.
- Widening allowed numbers to include `source_text` is mandatory. Copying capture's "this message + working set" *only* would make "drop the Siparia row" also drop "5 houses" that only appeared in the export.
- Separate `turn.py` / provenance paths prevent `CaptureWorkingSet` (alert_level, one corporation, no quotes) from leaking into DMU hour.

**Risks caught**
- *Context window:* long exports cannot be fully in every prompt. Allowed-number set still uses full `source_text`; the prompt may send `serialize_messages` truncated. Document the truncation limit in code (reuse `CHUNK_CHAR_LIMIT` or last-N messages + all current `source_quote`s). Implementation review must say which.
- *Adjust vs turn drift:* making adjust a wrapper avoids two prompts that diverge. Do not leave `ADJUST_PROMPT` as a second writer of the working set.
- *Filing during chat:* Phase 2 keeps promote as a footer action, not automatic. A fluent chat must not file.
- *Old drafts without row_id:* coerce on read so resume of Phase 1 drafts does not crash.
- *Identity:* still no auth. Any browser can open `/dmu/whatsapp`. Out of scope (global constraint).

**Would I change the design?** One alternative was "skip extract for paste and use the first chat turn as extract". Rejected for Phase 2: it would make paste and file feel different, and the batch extract already chunks. Chat is for correction and gaps, not for the first 12k pass.

---

## Phase 2 — Implementation self-review (gate)

1. Is there a real thread (history, streaming), not a single instruction box?
2. Does every turn's allowed-number set include digits from `source_text`?
3. Do hand-edited corporation / counts survive the next assistant turn?
4. Are cards keyed by `row_id`, not `source_index + array index`?
5. Does the model setting `corporation` without the officer confirming still leave `included` false when slug is null? When the officer picks a slug, is that path in `manual_fields`?
6. Was `CaptureSession` reused? (Must be **no**.)
7. Can you still generate the existing briefing and file-to-store from this workspace?
8. Mobile: is the record reachable without losing the thread (bottom sheet or equivalent)?
9. Did this phase make briefing "live"? (Must be **no** — that is Phase 3.)

---

# Phase 3 — Live briefing on the rail

The conversation's output is the hour briefing, visible while the officer works, not a one-shot after they remember to click.

## Task 10: Preview briefing from the current working set

**Files:**
- Modify: `briefing.py` / `api/whatsapp.py` — `POST /whatsapp/drafts/{id}/briefing` already exists. Add `GET` or include latest `report_id` on the draft so the rail can poll. Simplest: store `briefing_report_id` on `WhatsAppDraft` when a briefing is requested (migration), return it on `DraftResponse`.
- Alternatively persist markdown on the draft like `CaptureSession.sitrep_markdown`. Prefer **reusing `reports`** + poll, because citation display already exists.

Optional `POST .../briefing/preview` that does not enqueue a named report and returns markdown synchronously for small working sets — only if the existing job feels too slow for a tab. Default: keep the job, poll, show stale flag if `working.updated_at` > `report` time.

- [ ] Tests: briefing still 400 with no included attributed rows; after include+corp, preview/job succeeds; banner still present.
- [ ] Commit `feat: attach briefing report id on the WhatsApp draft`

## Task 11: Briefing tab + review before generate / file

**Files:**
- Create: `briefing-pane.tsx`, `review-briefing-sheet.tsx` (+ tests)
- Modify: draft workspace rail — tabs **Record | Briefing**

Briefing tab: `CitationMarkdown` of the latest report, or empty state "Generate a provisional briefing from the included rows". Footer: **Review & brief** / **File to store**.

Review sheet lists included attributed rows, warns on remaining `corporation: null` rows (excluded), and states:

> File to store writes corporation submissions. This is not a signed corp sitrep. Prefer briefing-only unless the DMU is deliberately promoting the hour.

Disable File if `includedCount === 0` (already). Disable Brief if the same.

Do **not** change `confirm.py` event auto-create in this task.

- [ ] Commit `feat: live WhatsApp hour briefing tab`

## Task 12: Phase 3 verification

Full backend pytest, frontend test + tsc + build.

Manual: paste → chat to fill corps → Briefing tab → generate → read provisional banner → change a row → briefing marked stale or regenerated → File to store still optional and warned.

---

## Phase 3 — Author self-review

**What this phase gets right**
- Matches corp's live sitrep tab without pretending the hour is a national SITREP (banner stays).
- Review sheet is the last chance to see W10 before promote.
- Reusing `reports` avoids a second markdown store.

**Risks caught**
- *Regenerating on every keystroke* would thrash the LLM. Preview is explicit (button / after turn debounce), not per-character. Implementation must not `useEffect` on `incidents` → `generate`.
- *Stale briefing:* if the officer chats after generate, the tab must not look like it reflects the rail. Stale flag or disable "looks current" until regenerate.
- *Not fixing auto-created events:* called out as deferred so this phase does not quietly change how filed data joins to storms. The warning is the honest product change we can ship without a data-model fight.
- *Citation checker on unverified WhatsApp facts:* existing briefing already uses `verification="pending"`. Do not "fix" that into `ok` to make the tab prettier.

**Would I change the design?** Alternative: briefing markdown on the draft row, like capture sitrep. Rejected for v1 because reports already poll, rate, and open at `/dmu/reports/$reportId`. A draft-local copy would drift.

---

## Phase 3 — Implementation self-review (gate)

1. Is the briefing visible next to the working set, not only after scrolling past the cards?
2. Does the provisional banner still lead the markdown?
3. Can the officer tell when the briefing is stale vs the rail?
4. Does File to store still require an explicit action, with copy that this is not a signed corp sitrep?
5. Does generate still 400 when nothing is included and attributed?
6. Did auto-create of `WhatsApp update {date}` events change? (Must be **no** unless the deferred task was explicitly pulled in.)
7. Did any national/minister template get pointed at WhatsApp draft prose? (Must be **no**. Minister report reads structured data, never this briefing.)

---

## Deferred backlog

- **Stop auto-creating events on promote (W10, remainder).** Promote should attach to a running event or require an explicit event, same rule as corp. Own plan: it changes `confirm.py` and every test that expects `WhatsApp update {date}`.
- **ZIP / media exports (W11).** Text only, as the user specified.
- **Delete / age out drafts.** Same as capture Iteration 3.
- **Model-proposed corporation chips** (propose, tap to commit). Phase 2 already has the select; chips can wait.
- **Merging WhatsApp into capture.** Do not.

---

## Verification summary

| Gate | When | Command / check |
|------|------|-----------------|
| Phase 1 tests | after Tasks 1–3 | whatsapp parse + API + frontend `source-form` |
| Phase 1 self-review | before Phase 2 | nine questions above, written in the PR |
| Phase 2 tests | after Tasks 5–8 | whatsapp + capture pytest; frontend; 390px workspace |
| Phase 2 self-review | before Phase 3 | nine questions above |
| Phase 3 tests | after Tasks 10–11 | full pytest + `pnpm test` + tsc + build |
| Phase 3 self-review | before merge | seven questions above |
| Migration | each phase that adds columns | empty sqlite `upgrade head` + `alembic check` |

**Done looks like:** a DMU officer pastes a snippet *or* uploads a `.txt`, talks to the bot to fix attribution and figures, watches a provisional hour briefing update from the included rows, and only then may file to the store.
