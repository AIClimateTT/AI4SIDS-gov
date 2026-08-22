# Live Corp Sitrep Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the dummy Sitrep tab and local Issue button with a real templated sitrep: preview from the capture working set, Issue to ingest structured data and persist an immutable cited report the DMU can open.

**Architecture:** Preview never writes `sitrep_incidents` (ingest would supersede live event rows). A working-set fact assembler produces the same sitreps metrics the engine already knows, the corp template narrates them, and a verbatim preamble carries overview / activity / logs. Issue calls the existing file/ingest path, regenerates from `submission_id`-scoped metrics, stores a `reports` row, and locks the session.

**Tech Stack:** FastAPI, SQLAlchemy 2.x, Alembic, pytest · React 19, TanStack Query, Vitest.

**Spec:** Product flow locked in the corp sitrep UI slice and F11 in `docs/superpowers/plans/2026-08-18-chat-first-corp-capture.md`. Design decisions below are the spec this plan argues from.

## Global Constraints

- **No authentication is added.** Corporation still comes from `useIdentity()`.
- **The LLM never chooses a join key.** Event attachment stays a human tap. Issue does not infer `event_id`.
- **A filing carrying incidents MUST name an event.** Same 400 as `POST /capture/sessions/{id}/file` today (`app/api/capture.py` `file_session`).
- **Manual values outrank model values.** Issue/preview read the pinned working set, not the chat transcript.
- **Minister / DMU dashboards read submitted data, not report prose.** Unissued conversations must not ingest. Issued conversations ingest once, then metrics see those rows.
- **Do not ingest a draft.** `ingest_submission` upserts on `(corporation, event_id, row_id)`. A preview ingest would rewrite an already-issued event table.
- **Situation Overview, Present Activity, and log statements are corp-supplied prose.** Render them verbatim in a preamble. Do not ask the LLM to rewrite them. Cited figures come only from the fact table (Decision 4 and 5 in `docs/superpowers/specs/2026-07-26-corp-sitrep-realignment-design.md`).
- **Session status stays `draft` | `filed`.** The UI label for `filed` is **Issued**. Do not add a third status string.
- **Generate the corp sitrep synchronously** with `get_llm_client("chat")`. Do not enqueue `generate_report`. The officer is waiting on the Sitrep tab. Tests use `FakeLLMClient`.
- **Keep `POST /capture/sessions/{id}/file`.** Issue calls the same ingest helper. The corp UI never calls `/file` directly.
- **Backend tests:** `cd apps/backend && .venv/bin/python -m pytest`. Baseline **528 passed**. Any failure is yours.
- **Frontend tests:** `cd apps/frontend && pnpm test`. `@testing-library/jest-dom` is NOT installed — use `expect(el).not.toBeNull()`, not `toBeInTheDocument`. First line of render tests: `// @vitest-environment jsdom`.
- **Migrations must apply from empty.** Current Alembic head is **`d7f2a6c81b3e`** — confirm with `alembic heads` before writing. SQLite has no `ALTER COLUMN`; use `op.batch_alter_table`.
- **YAGNI:** no draft-session TTL, no `GET /events/{id}`, no model-proposed event chip, no CSV-as-chat, no renaming `/file`.

---

## Decisions (locked)

1. **Three states, one conversation.** Capturing (Facts tab, `status=draft`) → draft sitrep (Sitrep tab has a preview) → Issued (`status=filed`, `report_id` set, working set frozen).
2. **Sitrep = this conversation**, not a corporation-wide date-range report. That is F11. The existing `corp_situation_report` template stays for DMU date-range generation.
3. **Preview facts come from the working set.** Issued facts come from the submission just ingested, filtered by `submission_id`. A golden test proves the two fact tables match for the same incidents.
4. **Issue is the DMU gate for this narrative** and for this conversation's rows. CSV `POST /submissions` is unchanged and remains immediately visible to metrics.
5. **Refresh, don't stream.** Opening the Sitrep tab (or clicking Refresh) POSTs preview if the working set is newer than the stored preview. Turns do not auto-generate.

---

## File Structure

**Backend — create:**
- `apps/backend/alembic/versions/<rev>_capture_sitrep_report.py` — `capture_sessions.report_id`, JSON preview columns.
- `apps/backend/app/modules/capture/facts.py` — working-set → duck-typed incident rows → fact list.
- `apps/backend/app/modules/capture/sitrep.py` — preamble, preview, issue (ingest + generate + persist).
- `apps/backend/app/templates/definitions/corp_sitrep_single.yaml` — one-submission corp sitrep.
- `apps/backend/tests/test_capture_facts.py`
- `apps/backend/tests/test_capture_sitrep.py`
- `apps/backend/tests/test_metrics_submission_id.py`

**Backend — modify:**
- `app/modules/survey123/metrics.py` — `submission_id` filter; `rows=` override via shared loader.
- `app/modules/capture/models.py` — `report_id`, preview fields.
- `app/api/capture.py` — extract ingest from `file_session`; add preview + issue; include sitrep on session response.
- `app/core/report_store.py` — no change unless a helper is needed to save a fully generated report (already have `save_report`).

**Frontend — create:**
- `apps/frontend/src/components/capture/sitrep-draft-pane.test.tsx`

**Frontend — modify:**
- `src/types/dmcu.ts` — `report_id`, `sitrep` on `CaptureSession`.
- `src/lib/api/capture.ts`, `src/lib/queries/capture.ts` — preview + issue mutations.
- `src/components/capture/sitrep-draft-pane.tsx` — live report, Refresh, Issue.
- `src/routes/corp/c/$sessionId.tsx` — drop local `issued` state; use `session.status` / `session.sitrep`.
- `src/components/corp/corp-sidebar.tsx` — label `filed` as Issued.

**Frontend — delete:**
- `src/lib/dummy-sitrep.ts`, `src/lib/dummy-sitrep.test.ts`

---

### Task 1: Filter sitreps metrics by `submission_id`

**Files:**
- Modify: `apps/backend/app/modules/survey123/metrics.py`
- Test: `apps/backend/tests/test_metrics_submission_id.py`
- Also update: `apps/backend/tests/test_metrics_helpers.py` if `QUERY_PARAMS` / `build_query_ref` assertions list keys.

**Interfaces:**
- Consumes: `SitrepIncident.submission_id`, existing `apply_common_filters` / `base_query`.
- Produces: `params["submission_id"]` narrows sitrep rows; ignored on `FieldObservation` (no such column). `QUERY_PARAMS` includes `"submission_id"`.

- [ ] **Step 1: Write the failing test**

Create `apps/backend/tests/test_metrics_submission_id.py`:

```python
from datetime import datetime

from app.modules.sitreps.ingest import ingest_submission
from app.modules.sitreps.module import sitrep_module
from app.modules.sitreps.store import create_event
from app.modules.survey123.metrics import build_query_ref
from tests.conftest import Session  # if no Session helper, open a sessionmaker on db_engine like test_api_capture.py


CORP = "diego_martin_regional_corporati"


def _ingest(db, *, as_at: datetime, row_id: str, summary: str, event_id: int):
    return ingest_submission(
        db,
        corporation=CORP,
        as_at=as_at,
        event_id=event_id,
        alert_level="yellow",
        present_activity=None,
        situation_overview=None,
        source_name="test",
        incident_rows=[
            {
                "Row ID": row_id,
                "Community": "Petit Valley",
                "Incident Type": "flooding",
                "Incident Summary": summary,
                "Date of Event": "2026-08-18",
            }
        ],
        log_rows=[],
        structured_defaults=True,
    )


def test_incident_count_can_scope_to_one_submission(tmp_path, monkeypatch):
    # Follow the session fixture style in test_sitreps_structured_ingest.py
    # (tmp_path DATABASE_URL). Two filings, two row_ids so supersession
    # does not collapse them.
    from sqlalchemy.orm import sessionmaker
    from app.db import engine as db_engine

    db = sessionmaker(bind=db_engine)()
    event = create_event(
        db,
        corporation=CORP,
        title="Flood",
        hazard_type="flood",
        started_at=datetime(2026, 8, 18),
    )
    first = _ingest(db, as_at=datetime(2026, 8, 18, 10), row_id="1", summary="A", event_id=event.id)
    second = _ingest(db, as_at=datetime(2026, 8, 18, 16), row_id="2", summary="B", event_id=event.id)

    all_facts = sitrep_module.run_metric(
        "incident_count", {"corporation": CORP, "date_from": "2026-08-01", "date_to": "2026-08-31"}, db
    )
    one = sitrep_module.run_metric(
        "incident_count",
        {"corporation": CORP, "submission_id": second.submission_id},
        db,
    )
    db.close()
    assert all_facts[0].value == 2
    assert one[0].value == 1
    assert f"submission_id={second.submission_id}" in one[0].citation.query_ref


def test_submission_id_is_ignored_when_the_model_has_no_such_column():
    from app.modules.survey123.metrics import apply_common_filters
    from app.modules.survey123.models import FieldObservation
    from sqlalchemy import select

    stmt = apply_common_filters(select(FieldObservation), {"submission_id": 99}, FieldObservation)
    compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "submission_id" not in compiled
```

If `tests.conftest` has no shared DB reset, copy the `tmp_path` / `DATABASE_URL` pattern from `tests/test_sitreps_structured_ingest.py` exactly — do not invent a new fixture style.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend && .venv/bin/python -m pytest tests/test_metrics_submission_id.py -v`

Expected: FAIL — both submissions counted, or `query_ref` lacks `submission_id`.

- [ ] **Step 3: Implement the filter**

In `apply_common_filters`, after the community filter:

```python
if params.get("submission_id") and column_exists(model, "submission_id"):
    stmt = stmt.where(model.submission_id == int(params["submission_id"]))
```

Add `"submission_id"` to `QUERY_PARAMS`.

In `build_scope`, add `"submission": str(params["submission_id"])` when `params.get("submission_id")` is truthy.

- [ ] **Step 4: Run tests**

Run: `cd apps/backend && .venv/bin/python -m pytest tests/test_metrics_submission_id.py tests/test_metrics_helpers.py tests/test_metrics_incident_count.py -v`

Expected: PASS. Fix any `QUERY_PARAMS` length assertions in helpers.

- [ ] **Step 5: Commit**

```bash
git add apps/backend/app/modules/survey123/metrics.py apps/backend/tests/test_metrics_submission_id.py apps/backend/tests/test_metrics_helpers.py
git commit -m "$(cat <<'EOF'
feat: allow sitrep metrics to scope to one submission

Corp sitreps need figures for this filing, not a date-range across every
prior sitrep for the corporation.
EOF
)"
```

---

### Task 2: `rows=` path so metrics can run without SQL

**Files:**
- Modify: `apps/backend/app/modules/survey123/metrics.py` (`incident_count` and every function in `METRIC_FUNCTIONS` that calls `base_query`)
- Test: `apps/backend/tests/test_capture_facts.py` (first test only in this task)

**Interfaces:**
- Consumes: existing metric bodies.
- Produces:

```python
def load_metric_rows(params: dict, session: Session | None, model, rows=None) -> list:
    if rows is not None:
        return list(rows)
    if session is None:
        raise ValueError("session is required when rows are not supplied")
    return list(session.execute(base_query(params, model)).scalars().all())
```

Each metric loads rows through `load_metric_rows`. Preview (Task 3) will pass `rows=`.

- [ ] **Step 1: Write a failing unit test** in `tests/test_capture_facts.py`:

```python
from types import SimpleNamespace
from datetime import datetime, timezone

from app.modules.sitreps.models import SitrepIncident
from app.modules.survey123.metrics import incident_count


def test_incident_count_accepts_preloaded_rows():
    row = SimpleNamespace(
        corporation="diego_martin_regional_corporati",
        event_id=1,
        row_id="1",
        incident_type="flooding",
        community="Petit Valley",
        street=None,
        event_date=datetime(2026, 8, 18),
        injuries_occurred=False,
        injuries_count=0,
        deaths_occurred=False,
        deaths_count=0,
        building_damage=None,
        special_needs_occupants=0,
        estimated_damage_cost=None,
        follow_up_flags={},
        validation_status="validated",
        record_ref="diego_martin_regional_corporati:1:1",
        global_id=None,
    )
    facts = incident_count(
        {"corporation": "diego_martin_regional_corporati"},
        session=None,
        model=SitrepIncident,
        rows=[row],
    )
    assert facts[0].value == 1
```

This fails until `incident_count` grows a `rows` kwarg.

- [ ] **Step 2: Run it**

Run: `cd apps/backend && .venv/bin/python -m pytest tests/test_capture_facts.py::test_incident_count_accepts_preloaded_rows -v`

Expected: FAIL (`rows` unexpected keyword).

- [ ] **Step 3: Add `load_metric_rows` and thread `rows=None` through every `METRIC_FUNCTIONS` entry** that currently does `session.execute(base_query(...))`. Keep `session` required when `rows` is omitted so Survey123 callers are unchanged.

Do not change metric names, citation descriptions (except they already use `build_window_label`), or return shapes.

- [ ] **Step 4: Run**

Run: `cd apps/backend && .venv/bin/python -m pytest tests/test_capture_facts.py::test_incident_count_accepts_preloaded_rows tests/test_metrics_incident_count.py tests/test_sitreps_module.py tests/test_field_observations_split.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/backend/app/modules/survey123/metrics.py apps/backend/tests/test_capture_facts.py
git commit -m "$(cat <<'EOF'
feat: let sitrep metrics run on preloaded rows

Preview must cite the capture working set without writing sitrep_incidents.
EOF
)"
```

---

### Task 3: Working-set fact assembler

**Files:**
- Create: `apps/backend/app/modules/capture/facts.py`
- Modify: `apps/backend/tests/test_capture_facts.py`

**Interfaces:**
- Consumes: `CaptureWorkingSet`, `METRIC_FUNCTIONS` keys used by `corp_situation_report.yaml`.
- Produces:

```python
CORP_SITREP_METRICS = (
    "incident_count",
    "street_level_tally",
    "homes_affected_count",
    "casualty_summary",
    "relief_actions_summary",
    "special_needs_count",
    "estimated_damage_total",
)

def working_set_incident_rows(
    working: CaptureWorkingSet,
    *,
    corporation: str,
    event_id: int | None,
) -> list: ...

def assemble_working_set_facts(
    working: CaptureWorkingSet,
    *,
    corporation: str,
    event_id: int | None,
) -> list[Fact]: ...
```

`working_set_incident_rows` maps each `CaptureIncident` to a `SimpleNamespace` with: `corporation`, `event_id`, `row_id`, `incident_type`, `community`, `street`, `event_date` (parse ISO date or None), injury/death/building/special_needs/estimated_damage fields, `follow_up_flags` dict from the four booleans, `validation_status="validated"`, `record_ref=f"{corporation}:{event_id or '-'}:{row_id}"`, `global_id=None`.

`assemble_working_set_facts` calls each metric in `CORP_SITREP_METRICS` with `session=None`, `model=SitrepIncident`, `rows=working_set_incident_rows(...)`, `params={"corporation": corporation}`.

- [ ] **Step 1: Write the failing tests** (append to `test_capture_facts.py`):

```python
from datetime import datetime

from app.modules.capture.facts import assemble_working_set_facts
from app.modules.capture.schemas import CaptureIncident, CaptureWorkingSet


def _working() -> CaptureWorkingSet:
    return CaptureWorkingSet(
        as_at=datetime(2026, 8, 21, 12),
        alert_level="yellow",
        present_activity="Shelter open",
        situation_overview="River overtopped",
        incidents=[
            CaptureIncident(
                row_id="1",
                community="Arima",
                street="Queen Street",
                incident_type="flooding",
                incident_summary="Five houses flooded",
                event_date=datetime(2026, 8, 21),
                injuries_occurred=True,
                injuries_count=1,
                deaths_occurred=False,
                deaths_count=0,
                special_needs_occupants=0,
                relief_supplied=True,
            )
        ],
        logs=[],
        manual_fields=[],
    )


def test_working_set_facts_count_the_captured_incident():
    facts = assemble_working_set_facts(
        _working(),
        corporation="arima_borough_corporation",
        event_id=2,
    )
    by_metric = {f.metric: f for f in facts}
    assert by_metric["incident_count"].value == 1
    assert by_metric["casualty_summary"].breakdown["injuries"] == 1
```

Match `CaptureIncident` field names to `app/modules/capture/schemas.py` — do not invent fields. If `event_date` is `date | datetime | str | None` on the schema, pass what the schema accepts.

- [ ] **Step 2: Run** — expect FAIL (`assemble_working_set_facts` missing).

- [ ] **Step 3: Implement `facts.py`** as specified.

- [ ] **Step 4: Run** `pytest tests/test_capture_facts.py -v` — PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/backend/app/modules/capture/facts.py apps/backend/tests/test_capture_facts.py
git commit -m "$(cat <<'EOF'
feat: assemble sitrep facts from a capture working set

Preview can cite captured incidents without ingesting them.
EOF
)"
```

---

### Task 4: Single-submission template + preamble + generate helper

**Files:**
- Create: `apps/backend/app/templates/definitions/corp_sitrep_single.yaml`
- Create: `apps/backend/app/modules/capture/sitrep.py`
- Test: `apps/backend/tests/test_capture_sitrep.py`

**Interfaces:**
- Consumes: `assemble_working_set_facts`, `narrate_fact_table`, `render_report`, `CaptureWorkingSet`.
- Produces:

```python
def sitrep_preamble(
    *,
    event_title: str,
    alert_level: str,
    as_at: datetime,
    situation_overview: str | None,
    present_activity: str | None,
    logs: list[CaptureLog],
) -> str: ...

def generate_working_set_sitrep(
    working: CaptureWorkingSet,
    *,
    corporation: str,
    event_id: int | None,
    event_title: str,
    template: Template,
    llm_client: LLMClient,
    request_id: str,
) -> GeneratedReport: ...
```

`sitrep_preamble` returns markdown **without** a `#` title (the renderer already prints `template.title`):

```markdown
**Event:** Flooding in Arima
**Alert:** yellow
**As at:** 2026-08-21 12:00

River overtopped

Present activity: Shelter open

## Situation logs

- Sandbagging ongoing on Queen Street
```

If overview / activity / logs are empty, omit that block (do not write "None"). Logs are the corp's `statement` lines only — never parse quantities out of the sentence.

`corp_sitrep_single.yaml`:

```yaml
name: corp_sitrep_single
title: Corporation Situation Report
description: One sitrep filing — this conversation's incidents, cited.
params:
  - name: corporation
    required: true
  - name: submission_id
    required: false
data_requirements:
  - module: sitreps
    metric: incident_count
    params: { corporation: "{corporation}", submission_id: "{submission_id}" }
  - module: sitreps
    metric: street_level_tally
    params: { corporation: "{corporation}", submission_id: "{submission_id}" }
  - module: sitreps
    metric: homes_affected_count
    params: { corporation: "{corporation}", submission_id: "{submission_id}" }
  - module: sitreps
    metric: casualty_summary
    params: { corporation: "{corporation}", submission_id: "{submission_id}" }
  - module: sitreps
    metric: relief_actions_summary
    params: { corporation: "{corporation}", submission_id: "{submission_id}" }
  - module: sitreps
    metric: special_needs_count
    params: { corporation: "{corporation}", submission_id: "{submission_id}" }
  - module: sitreps
    metric: estimated_damage_total
    params: { corporation: "{corporation}", submission_id: "{submission_id}" }
narration:
  system_prompt: |
    You are drafting one regional corporation situation report for onward
    submission to the Disaster Management Coordinating Unit.

    The Event, Alert, As-at, overview, present activity, and situation log
    lines are supplied separately and must not be rewritten here.

    Using ONLY the fact table JSON, write short paragraphs covering
    street-level impact, casualties, and relief actions. Every figure must
    carry its [C001]-style citation. Do not invent counts.
  output_sections:
    - streets_and_impact
    - relief_response
    - data_gaps
render:
  format: markdown
  include_citation_appendix: true
```

`generate_working_set_sitrep`:
1. `facts = assemble_working_set_facts(...)`
2. Build a `FactTable` the same way `assemble_fact_table` renumbers cids (`C001`…). Copy that loop; do not call `assemble_fact_table` (it hits the DB).
3. `generated = narrate_fact_table(template, fact_table, llm_client, template.data_requirements)`
4. Prepend `sitrep_preamble(...)` to `generated.markdown` after the renderer title: split on first blank line after `# title`, insert preamble, or simpler: `markdown = generated.markdown.replace(f"# {template.title}\n\n", f"# {template.title}\n\n{preamble}\n\n", 1)`.
5. Return `generated.model_copy(update={"markdown": markdown, "params": {"corporation": corporation}})`.

Template `submission_id: "{submission_id}"` with `required: false` — `resolve_params` will insert `None` if missing. `apply_common_filters` already treats falsy as absent. Preview does not pass `submission_id`. Issue does.

Placeholder `{submission_id}` must be declared in `params` even if optional, or `validate_template_payload` fails. Declare it `required: false`.

- [ ] **Step 1: Failing tests** in `tests/test_capture_sitrep.py`:

```python
from datetime import datetime

from app.core.llm import FakeLLMClient
from app.modules.capture.schemas import CaptureIncident, CaptureLog, CaptureWorkingSet
from app.modules.capture.sitrep import generate_working_set_sitrep, sitrep_preamble
from app.templates.loader import load_template
from pathlib import Path

TEMPLATE = load_template(
    Path(__file__).parent.parent / "app/templates/definitions/corp_sitrep_single.yaml"
)


def test_preamble_renders_verbatim_overview_and_logs():
    text = sitrep_preamble(
        event_title="Flooding in Arima",
        alert_level="yellow",
        as_at=datetime(2026, 8, 21, 12, 0),
        situation_overview="River overtopped overnight.",
        present_activity="Shelter open.",
        logs=[CaptureLog(row_id="1", category="activity", statement="Sandbagging on Queen Street")],
    )
    assert "Flooding in Arima" in text
    assert "River overtopped overnight." in text
    assert "Sandbagging on Queen Street" in text
    assert "None" not in text


def test_working_set_sitrep_markdown_cites_incident_count():
    working = CaptureWorkingSet(
        as_at=datetime(2026, 8, 21, 12),
        alert_level="yellow",
        present_activity="Shelter open.",
        situation_overview="River overtopped overnight.",
        incidents=[
            CaptureIncident(
                row_id="1",
                community="Arima",
                incident_type="flooding",
                incident_summary="Five houses flooded",
                injuries_count=0,
                deaths_count=0,
            )
        ],
        logs=[],
        manual_fields=[],
    )
    report = generate_working_set_sitrep(
        working,
        corporation="arima_borough_corporation",
        event_id=2,
        event_title="Flooding in Arima",
        template=TEMPLATE,
        llm_client=FakeLLMClient(),
        request_id="preview-test",
    )
    assert "Flooding in Arima" in report.markdown
    assert "River overtopped overnight." in report.markdown
    assert "[C001]" in report.markdown
    assert report.fact_table.facts[0].citation.cid == "C001"
```

Fill `CaptureIncident` / `CaptureLog` with whatever the schema requires (copy from `test_capture_facts.py`). `FakeLLMClient._auto_narrative` reads `user_content` JSON `facts` and emits cited sentences — that is enough.

- [ ] **Step 2: Run** — FAIL (module / yaml missing).

- [ ] **Step 3: Add the yaml and `sitrep.py`.**

- [ ] **Step 4: Run** `pytest tests/test_capture_sitrep.py tests/test_template_loader.py -v`

`test_template_loader.py` may assert the count of yaml files in definitions — bump if it hard-codes 3.

- [ ] **Step 5: Commit**

```bash
git add apps/backend/app/templates/definitions/corp_sitrep_single.yaml \
  apps/backend/app/modules/capture/sitrep.py \
  apps/backend/tests/test_capture_sitrep.py
git commit -m "$(cat <<'EOF'
feat: generate a cited corp sitrep from a capture working set

Verbatim overview and logs stay outside the LLM; figures come from facts.
EOF
)"
```

---

### Task 5: Persist preview and issued report on the session

**Files:**
- Create: `apps/backend/alembic/versions/<rev>_capture_sitrep_report.py` (`down_revision = "d7f2a6c81b3e"` unless `alembic heads` says otherwise)
- Modify: `apps/backend/app/modules/capture/models.py`
- Test: `apps/backend/tests/test_migrations.py` (table/column assertions if that file lists `capture_sessions` columns)

**Interfaces:**
- Produces columns on `capture_sessions`:

| Column | Type | Notes |
|---|---|---|
| `report_id` | `String`, FK `reports.id`, nullable | Set on Issue |
| `sitrep_markdown` | `Text`, nullable | Last preview or issued markdown |
| `sitrep_fact_table` | `JSON`, nullable | |
| `sitrep_violations` | `JSON`, nullable, default `[]` | |
| `sitrep_status` | `String`, nullable | `ok` / `needs_review` from the engine |
| `sitrep_generated_at` | `DateTime`, nullable | |
| `sitrep_source_updated_at` | `DateTime`, nullable | `session.updated_at` at generate time; UI uses this for stale |

Do **not** FK-on-delete-cascade the report; issued reports stay in `reports` even if a session row is later removed.

- [ ] **Step 1: Add a migration test** if `test_migrations.py` enumerates columns — expect the new names after upgrade. If it only checks table existence, add:

```python
def test_capture_sessions_have_sitrep_columns():
    # use the same inspector pattern as neighbouring tests
    ...
    assert "report_id" in columns
    assert "sitrep_markdown" in columns
```

- [ ] **Step 2: Run** — FAIL.

- [ ] **Step 3: Write the Alembic revision** (`batch_alter_table` for SQLite) and update `CaptureSession`.

- [ ] **Step 4: Verify migration from empty**

```bash
cd apps/backend
rm -f /tmp/m.db
DATABASE_URL="sqlite:////tmp/m.db" .venv/bin/python -m alembic upgrade head
DATABASE_URL="sqlite:////tmp/m.db" .venv/bin/python -m alembic check
.venv/bin/python -m pytest tests/test_migrations.py -v
```

Expected: PASS, `alembic check` clean.

- [ ] **Step 5: Commit**

```bash
git add apps/backend/alembic/versions/*_capture_sitrep_report.py \
  apps/backend/app/modules/capture/models.py \
  apps/backend/tests/test_migrations.py
git commit -m "$(cat <<'EOF'
feat: store sitrep preview and issued report id on capture sessions
EOF
)"
```

---

### Task 6: Preview and Issue API

**Files:**
- Modify: `apps/backend/app/api/capture.py`
- Modify: `apps/backend/app/modules/capture/sitrep.py` (apply generated report onto the row; issue orchestration)
- Modify: `apps/backend/app/modules/capture/store.py` if `_to_response` helpers belong there — prefer keeping mapping in the API file next to `_to_response`.
- Test: `apps/backend/tests/test_api_capture.py` (append)

**Interfaces:**
- Consumes: `generate_working_set_sitrep`, existing ingest inside `file_session`, `generate_report` / `assemble_fact_table` + `narrate_fact_table` for the issued path, `save_report`, `get_latest_template_version`.
- Produces:

```
POST /capture/sessions/{id}/preview  -> CaptureSessionResponse   # 200
POST /capture/sessions/{id}/issue    -> FileSessionResponse      # 201
```

`CaptureSessionResponse` gains:

```python
report_id: str | None
sitrep: SitrepOut | None

class SitrepOut(BaseModel):
    markdown: str
    fact_table: dict
    violations: list
    status: str
    generated_at: datetime
    source_updated_at: datetime
    stale: bool  # generated source_updated_at < session.updated_at
```

`_to_response` sets `stale` when `sitrep_source_updated_at` is None or `< row.updated_at`.

**Preview (`status` must be `draft`):**
1. 409 if already filed (`_require_draft`).
2. Load `corp_sitrep_single` via `get_latest_template_version`. If missing, 400 `"template corp_sitrep_single is not installed; run templates import-all"`.
3. `event_title` from `get_event` or `"Untitled event"`.
4. `generated = generate_working_set_sitrep(...)` with `get_llm_client("chat")`.
5. Write sitrep_* columns; `sitrep_source_updated_at = row.updated_at` (**do not** bump `updated_at` here or the preview is immediately stale). If `save_session` always touches `updated_at`, add `save_session(..., touch=False)` or set the columns and `commit` without changing `updated_at`.
6. Return `_to_response(row)`.

**Issue:**
1. Same guards as `file_session` (draft, event required if incidents).
2. If `sitrep_markdown` is missing or `stale`, run preview generate first (do not require an extra client round-trip).
3. Call the current ingest body of `file_session` (extract `def file_working_set(db, row) -> SubmissionIngestResult` so `/file` and `/issue` share it). `/file` behaviour stays: ingest, `status=filed`, `submission_id` set, **no** report generation (keeps existing tests).
4. `generate_report(template, {"corporation": row.corporation, "submission_id": ingest.submission_id}, db, get_llm_client("chat"))`, then prepend the same preamble using the working set (overview/logs still verbatim; cited body now matches ingested rows).
5. `save_report(generated, db)`; `row.report_id = saved.id`; copy markdown/fact_table/violations/status onto sitrep_* ; `sitrep_source_updated_at = row.updated_at`; `row.status = "filed"`.
6. Return `FileSessionResponse`.

**Golden equality (in `test_capture_sitrep.py` or API test):** after issue, `incident_count` from `assemble_working_set_facts` equals `sitrep_module.run_metric(..., submission_id=...)` for the same incidents. Assert values, not markdown.

Tests in `test_api_capture.py` must import/install the template. Neighbouring tests that generate reports call `templates import-all` or `load_templates_from_directory` + `create_template_version`. Copy that from `test_api_reports.py` / `make_client` — do not skip installing `corp_sitrep_single` or preview 400s.

- [ ] **Step 1: Write failing API tests** (append):

```python
def test_preview_does_not_ingest_incidents(monkeypatch):
    client = make_client(monkeypatch)
    # install templates the same way test_api_reports does
    event_id = create_event(client)
    session_id = create_capture(client, event_id)["id"]
    client.post(
        f"/capture/sessions/{session_id}/turns",
        json={"message": "5 houses flooded in Petit Valley. 200 sandbags remaining."},
    )
    response = client.post(f"/capture/sessions/{session_id}/preview")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "draft"
    assert body["submission_id"] is None
    assert body["sitrep"]["markdown"]
    assert body["sitrep"]["stale"] is False
    from sqlalchemy.orm import sessionmaker
    from app.db import engine as db_engine
    from app.modules.sitreps.models import SitrepIncident
    db = sessionmaker(bind=db_engine)()
    assert db.query(SitrepIncident).count() == 0
    db.close()


def test_issue_ingests_and_persists_a_report(monkeypatch):
    client = make_client(monkeypatch)
    event_id = create_event(client)
    session_id = create_capture(client, event_id)["id"]
    client.post(
        f"/capture/sessions/{session_id}/turns",
        json={"message": "5 houses flooded in Petit Valley."},
    )
    response = client.post(f"/capture/sessions/{session_id}/issue")
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["session"]["status"] == "filed"
    assert body["session"]["report_id"]
    assert body["ingest"]["incidents_inserted"] == 1
    report = client.get(f"/reports/{body['session']['report_id']}")
    assert report.status_code == 200
    assert "[C001]" in report.json()["markdown"]


def test_issue_rejects_incidents_without_an_event(monkeypatch):
    client = make_client(monkeypatch)
    session_id = create_capture(client, event_id=None)["id"]
    # put an incident on the working set via PUT
    ...
    response = client.post(f"/capture/sessions/{session_id}/issue")
    assert response.status_code == 400


def test_preview_on_filed_session_is_conflict(monkeypatch):
    ...
    client.post(f"/capture/sessions/{session_id}/file")
    assert client.post(f"/capture/sessions/{session_id}/preview").status_code == 409
```

For `create_capture(..., event_id=None)` use the existing create helper; if it always sends an event, POST `/capture/sessions` with only `corporation`.

- [ ] **Step 2: Run** — FAIL (404 on `/preview`).

- [ ] **Step 3: Implement endpoints.** Extract ingest from `file_session` first so `/file` tests still pass unchanged.

Preview must not call `save_session` if that function overwrites `updated_at`. Implement `save_sitrep_preview(db, row, generated, source_updated_at)` that commits sitrep columns only.

- [ ] **Step 4: Run**

```bash
cd apps/backend && .venv/bin/python -m pytest tests/test_api_capture.py tests/test_capture_sitrep.py -v
```

Expected: PASS. Then full `pytest` — still 528+ and green.

- [ ] **Step 5: Commit**

```bash
git add apps/backend/app/api/capture.py apps/backend/app/modules/capture/sitrep.py \
  apps/backend/app/modules/capture/store.py apps/backend/tests/test_api_capture.py
git commit -m "$(cat <<'EOF'
feat: preview and issue a cited sitrep from a capture session

Preview stays off the incidents table; Issue files the submission and
stores the report the DMU can open.
EOF
)"
```

---

### Task 7: Frontend types, API, and query hooks

**Files:**
- Modify: `apps/frontend/src/types/dmcu.ts`
- Modify: `apps/frontend/src/lib/api/capture.ts`
- Modify: `apps/frontend/src/lib/queries/capture.ts`

**Interfaces:**
- Consumes: Task 6 JSON shape.
- Produces:

```ts
export type CaptureSitrep = {
  markdown: string
  fact_table: FactTable
  violations: CitationViolation[]
  status: string
  generated_at: string
  source_updated_at: string
  stale: boolean
}

// on CaptureSession:
report_id: string | null
sitrep: CaptureSitrep | null

previewCaptureSession(id: number): Promise<CaptureSession>
issueCaptureSession(id: number): Promise<CaptureFileResult>
```

`usePreviewCaptureSession` / `useIssueCaptureSession`: onSuccess `setQueryData(captureKeys.detail)`, invalidate lists + `submissionKeys` + `overviewKeys` on issue. Toasts: preview failure `"Failed to generate sitrep"`; issue success `"Sitrep issued"`; issue error `"Failed to issue sitrep"`.

Keep `fileCaptureSession` / `useFileCaptureSession` for now (unused by the chat UI). Do not delete in this task.

- [ ] **Step 1:** No isolated frontend test required if types are used in Task 8. If you add a thin mapper test, put it next to `sitrep-href.test.ts` — do not add a dummy interpolator.

- [ ] **Step 2: Implement types + fetchers + hooks.** `fact_table` in JSON is snake_case matching `FactTable`.

- [ ] **Step 3:** `cd apps/frontend && pnpm exec tsc --noEmit -p tsconfig.json` — clean.

- [ ] **Step 4: Commit**

```bash
git add apps/frontend/src/types/dmcu.ts apps/frontend/src/lib/api/capture.ts apps/frontend/src/lib/queries/capture.ts
git commit -m "$(cat <<'EOF'
feat: add capture preview and issue API clients
EOF
)"
```

---

### Task 8: Live Sitrep pane and session page

**Files:**
- Modify: `apps/frontend/src/components/capture/sitrep-draft-pane.tsx`
- Create: `apps/frontend/src/components/capture/sitrep-draft-pane.test.tsx`
- Modify: `apps/frontend/src/routes/corp/c/$sessionId.tsx`
- Modify: `apps/frontend/src/components/corp/corp-sidebar.tsx`
- Delete: `apps/frontend/src/lib/dummy-sitrep.ts`, `apps/frontend/src/lib/dummy-sitrep.test.ts`

**Interfaces:**
- Consumes: `session.sitrep`, `session.status`, `usePreviewCaptureSession`, `useIssueCaptureSession`.
- Produces: Sitrep tab shows `CitationMarkdown` + `ReportFactTable` + `ViolationsPanel` when `sitrep` is present. Badge: Draft / Issued (`filed`). Stale draft: helper text `"Facts changed — refresh to update the draft."` and enabled Refresh. Issue disabled when `status==='filed'` or preview pending. Filed sessions hide Refresh.

`SitrepDraftPane` props:

```tsx
{
  session: CaptureSession
  eventTitle?: string | null
  onPreview: () => void
  onIssue: () => void
  previewPending: boolean
  issuePending: boolean
}
```

No local `issued` boolean. No toast `"Would issue to DMU"`.

Session page: drop `useState(false)` for issued. On Sitrep tab select, if `status==='draft'` and (`sitrep==null` or `sitrep.stale`), call preview once (guard with a ref so switching away and back does not hammer). Buttons still work if the auto-call fails.

Sidebar: `sitrep.status === 'draft' ? 'Draft' : 'Issued'` (replace `'Filed'`).

- [ ] **Step 1: Write failing pane tests**

```tsx
// @vitest-environment jsdom
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { SitrepDraftPane } from './sitrep-draft-pane'
import type { CaptureSession } from '@/types/dmcu'

function session(overrides: Partial<CaptureSession> = {}): CaptureSession {
  return {
    /* copy the dummy-sitrep.test.ts fixture, plus report_id: null, sitrep: null */
    ...overrides,
  } as CaptureSession
}

it('shows a generate prompt when there is no sitrep yet', () => {
  render(
    <SitrepDraftPane
      session={session()}
      onPreview={vi.fn()}
      onIssue={vi.fn()}
      previewPending={false}
      issuePending={false}
    />,
  )
  expect(screen.getByRole('button', { name: 'Generate draft' })).not.toBeNull()
  expect(screen.queryByRole('button', { name: 'Issue' })).toBeNull()
})

it('renders live markdown and issue when a draft sitrep is present', () => {
  const onIssue = vi.fn()
  render(
    <SitrepDraftPane
      session={session({
        sitrep: {
          markdown: '# Corporation Situation Report\n\n**Event:** Flooding in Arima\n\n1 incident [C001].',
          fact_table: { facts: [] },
          violations: [],
          status: 'ok',
          generated_at: '2026-08-21T12:00:00',
          source_updated_at: '2026-08-21T12:00:00',
          stale: false,
        },
      })}
      onPreview={vi.fn()}
      onIssue={onIssue}
      previewPending={false}
      issuePending={false}
    />,
  )
  expect(screen.getByText(/Flooding in Arima/)).not.toBeNull()
  fireEvent.click(screen.getByRole('button', { name: 'Issue' }))
  expect(onIssue).toHaveBeenCalledTimes(1)
})

it('disables issue when the session is already filed', () => {
  render(
    <SitrepDraftPane
      session={session({
        status: 'filed',
        sitrep: {
          markdown: 'Issued body',
          fact_table: { facts: [] },
          violations: [],
          status: 'ok',
          generated_at: '2026-08-21T12:00:00',
          source_updated_at: '2026-08-21T12:00:00',
          stale: false,
        },
      })}
      onPreview={vi.fn()}
      onIssue={vi.fn()}
      previewPending={false}
      issuePending={false}
    />,
  )
  expect((screen.getByRole('button', { name: 'Issued' }) as HTMLButtonElement).disabled).toBe(true)
})
```

Empty-state button label: **Generate draft**. After a sitrep exists: **Refresh** + **Issue**. Filed: button label **Issued**, disabled.

- [ ] **Step 2: Run** `cd apps/frontend && pnpm test -- sitrep-draft-pane` — FAIL.

- [ ] **Step 3: Implement the pane; wire `$sessionId.tsx`; delete dummy sitrep files; update sidebar copy; fix any fixture that omitted `sitrep` / `report_id`.**

If `CitationMarkdown` needs a non-empty fact table for `[C001]` links, include one fact in the test fixture.

- [ ] **Step 4: Run**

```bash
cd apps/frontend && pnpm test && pnpm exec tsc --noEmit -p tsconfig.json
```

Expected: all passing, tsc clean. No remaining imports of `dummySitrep`.

- [ ] **Step 5: Commit**

```bash
git add apps/frontend/src/components/capture/sitrep-draft-pane.tsx \
  apps/frontend/src/components/capture/sitrep-draft-pane.test.tsx \
  apps/frontend/src/routes/corp/c/\$sessionId.tsx \
  apps/frontend/src/components/corp/corp-sidebar.tsx
git rm apps/frontend/src/lib/dummy-sitrep.ts apps/frontend/src/lib/dummy-sitrep.test.ts
git commit -m "$(cat <<'EOF'
feat: drive the sitrep tab from live preview and issue APIs

Removes the interpolated dummy document and the local-only Issue flag.
EOF
)"
```

---

### Task 9: Install the template in demo/dev and verify end-to-end

**Files:**
- Modify: `apps/backend/scripts/seed_demo.py` only if it imports templates from `definitions/` by glob — a new yaml is picked up automatically. If it lists names, add `corp_sitrep_single`.
- Docs: none unless `README` lists template names.

- [ ] **Step 1:** Confirm `templates import-all` / seed loads four yaml files.

Run: `cd apps/backend && .venv/bin/python -m pytest tests/test_cli_templates.py tests/test_api_templates.py tests/test_template_loader.py -v`

- [ ] **Step 2: Full backend + frontend**

```bash
cd apps/backend && .venv/bin/python -m pytest
cd apps/frontend && pnpm test && pnpm exec tsc --noEmit -p tsconfig.json
```

Expected: backend ≥ 528, all green; frontend all green.

- [ ] **Step 3: Manual check** (390px and 1280px)

1. Corp identity → start a sitrep → attach event → capture one incident and one log.
2. Open Sitrep tab: draft markdown with verbatim overview/log and `[C001]` citations; Facts unchanged.
3. Add another incident on Facts, return to Sitrep: stale + Refresh updates the count.
4. Issue: badge Issued, chat/facts read-only (existing `isFiled`), sidebar says Issued, home filings row opens this chat, `GET /reports/{id}` (or DMU Reports list) shows the document.
5. Confirm `sitrep_incidents` did not grow during step 2 (preview), only after step 4.

- [ ] **Step 4: Commit** only if seed/docs changed; otherwise skip.

---

## Out of scope

- Generating a sitrep for sessions already `filed` before this ships (`report_id` null). They stay labelled Issued in the sidebar with an empty Sitrep tab unless someone re-files — do not backfill.
- `Submission.capture_session_id` — `CaptureSession.submission_id` is enough for `resolveSitrepHref`.
- Streaming the sitrep token-by-token.
- Changing minister `corp_situation_report` date-range behaviour.
- Auth / logout (Switch in the sidebar footer stays Switch).

---

## Self-review

| Spec / decision | Task |
|---|---|
| Preview does not ingest | 6 (`test_preview_does_not_ingest_incidents`) |
| Issue ingests + stores report | 6 |
| Working-set facts === submission facts | 3 + 6 golden assert |
| Verbatim overview / logs | 4 |
| `submission_id` metrics | 1 |
| Dummy UI removed | 8 |
| `/file` preserved | 6 |
| Sync generate | 6 (`get_llm_client("chat")`) |
| Status `draft` \| `filed` | 6, 8 |
