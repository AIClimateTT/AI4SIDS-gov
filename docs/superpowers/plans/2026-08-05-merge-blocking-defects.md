# Merge-Blocking Defects Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the four defects that put a wrong or untraceable number into a ministerial report, each of which passed a fully green test suite.

**Architecture:** Four independent fixes. A strict corp-only cell parser rejects unparseable hand-typed values instead of coercing them; `build_query_ref` renders only the parameters the query consumed; the citation checker's year pattern is bounded to real years; and a submission carrying incidents must name an event, which makes supersession always apply and `record_ref` unique.

**Tech Stack:** Python 3.13, Pydantic v2, SQLAlchemy 2.x, FastAPI, Typer, pytest.

**Spec:** `docs/superpowers/specs/2026-08-05-merge-blocking-defects-design.md`

## Global Constraints

- **Every fix lands with its reproduction as a regression test.** All four defects passed a green suite; a fix without the reproducing test has not been demonstrated.
- **Do not change `parse_bool` / `parse_decimal` / `parse_int` in `app/modules/survey123/ingest.py`.** Those serve machine-generated Survey123 exports covering 14,942 rows of existing field data. The new strictness is corp-path only, and lives in `app/modules/sitreps/parse.py`.
- **An empty cell is not an error.** Only a non-empty cell that fails to parse becomes a `RowError`. Blank stays `None` / `False` exactly as today.
- **Unrecognised `query_ref` keys are dropped, never rejected.** Templates stored before the schema split still carry a legacy `source` key; rejecting would turn a reporting defect into an outage.
- **Situation logs remain filable without an event.** Only incidents require one. Logs are point-in-time state, never supersede, and never collide.
- **Tests:** `cd apps/backend && .venv/bin/python -m pytest`. Baseline is **320 passed, 0 failed** — the suite is fully green, so any failure is yours.
- **Frontend:** untouched by this plan.

---

## File Structure

**Modify:**
- `apps/backend/app/modules/sitreps/parse.py` — strict corp cell parsing (F1).
- `apps/backend/app/modules/survey123/metrics.py` — `build_query_ref` allowlist (F2).
- `apps/backend/app/core/citation_check.py` — bounded year pattern (F3).
- `apps/backend/app/modules/sitreps/models.py` — `record_ref` includes `submission_id` (F4).
- `apps/backend/app/api/submissions.py`, `apps/backend/cli.py` — incidents require an event (F4).

**Test:**
- `apps/backend/tests/test_sitreps_parse.py`, `test_metrics_helpers.py`, `test_citation_check.py`, `test_api_submissions.py`, `test_sitreps_models.py` — all existing, extended.

---

## Task 1: F1 — Reject unparseable hand-typed cells

**Files:**
- Modify: `apps/backend/app/modules/sitreps/parse.py`
- Test: `apps/backend/tests/test_sitreps_parse.py`

**Interfaces:**
- Consumes: `RowError`, `_clean` (already in `parse.py`).
- Produces:
  - `UNPARSEABLE` — a module-level sentinel object meaning "this cell had content that could not be read". Distinct from `None`, which means "this cell was empty". Confusing the two is what caused the defect.
  - `parse_corp_bool(raw) -> bool | None` — `True`/`False` when readable, `False` when empty, `None` when unparseable. It returns `None` rather than the sentinel because `bool | None` already has a free slot; the numeric parsers do not, since `None` is a legitimate empty result.
  - `parse_corp_decimal(raw) -> Decimal | None | UNPARSEABLE`
  - `parse_corp_int(raw) -> int | None | UNPARSEABLE`

- [ ] **Step 1: Write the failing tests**

Append to `apps/backend/tests/test_sitreps_parse.py`. It already imports `RowError` and `parse_incident_row` and defines `read_fixture_rows()`.

```python
def _incident_row(**overrides) -> dict:
    row = {
        "Row ID": "1",
        "Incident Type": "fire",
        "Date of Event": "2023-06-27",
        "Injuries Occurred": "False",
        "Deaths Occurred": "False",
        "Relief Supplied": "False",
        "Forwarded To Agency": "False",
        "Further Assessment Required": "False",
        "Other Follow Up": "False",
    }
    row.update(overrides)
    return row


def test_currency_formatted_damage_cost_parses():
    # What a person actually types into a spreadsheet.
    fields, error = parse_incident_row(_incident_row(**{"Estimated Damage Cost": "$12,500"}), 1)

    assert error is None
    assert int(fields["estimated_damage_cost"]) == 12500


def test_unparseable_damage_cost_is_a_row_error_not_a_silent_none():
    # Previously stored None, so the report said TTD 0 with no trace.
    fields, error = parse_incident_row(_incident_row(**{"Estimated Damage Cost": "about ten grand"}), 4)

    assert fields is None
    assert error == RowError(
        row_number=4, reason="Estimated Damage Cost is not a number: 'about ten grand'"
    )


def test_yes_and_y_are_accepted_as_true():
    # Previously coerced to False, silently zeroing relief counts.
    fields, error = parse_incident_row(
        _incident_row(**{"Injuries Occurred": "Yes", "Relief Supplied": "Y"}), 1
    )

    assert error is None
    assert fields["injuries_occurred"] is True
    assert fields["follow_up_flags"]["relief_supplied"] is True


def test_no_and_zero_are_accepted_as_false():
    fields, error = parse_incident_row(
        _incident_row(**{"Injuries Occurred": "No", "Deaths Occurred": "0"}), 1
    )

    assert error is None
    assert fields["injuries_occurred"] is False
    assert fields["deaths_occurred"] is False


def test_an_unrecognised_boolean_is_a_row_error():
    fields, error = parse_incident_row(_incident_row(**{"Injuries Occurred": "maybe"}), 6)

    assert fields is None
    assert error.row_number == 6
    assert "Injuries Occurred" in error.reason


def test_a_non_numeric_count_is_a_row_error():
    fields, error = parse_incident_row(_incident_row(**{"Injuries Count": "two"}), 7)

    assert fields is None
    assert error == RowError(row_number=7, reason="Injuries Count is not a whole number: 'two'")


def test_empty_cells_are_not_errors():
    # Blank must stay permissive — a corp leaves cells empty constantly.
    fields, error = parse_incident_row(
        _incident_row(**{"Estimated Damage Cost": "", "Injuries Count": "", "Injuries Occurred": ""}),
        1,
    )

    assert error is None
    assert fields["estimated_damage_cost"] is None
    assert fields["injuries_count"] is None
    assert fields["injuries_occurred"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/backend && .venv/bin/python -m pytest tests/test_sitreps_parse.py -q -k "currency or unparseable_damage or yes_and_y or no_and_zero or unrecognised_boolean or non_numeric_count"`
Expected: FAIL — `$12,500` currently yields `None` with no error, `"Yes"` yields `False`, `"maybe"` yields `False`, `"two"` yields `None`.

- [ ] **Step 3: Add the strict corp parsers**

In `apps/backend/app/modules/sitreps/parse.py`, add `from decimal import Decimal, InvalidOperation` to the imports and these helpers below `_clean`:

```python
# Sentinel for "this cell had content that could not be read", kept distinct
# from None, which means "this cell was empty". Collapsing the two is exactly
# what let "$12,500" become None and report TTD 0.
UNPARSEABLE = object()

TRUE_VALUES = {"true", "yes", "y", "1"}
FALSE_VALUES = {"false", "no", "n", "0"}


def parse_corp_bool(raw: str | None) -> bool | None:
    """None means unparseable. An empty cell is False, not an error.

    survey123's parse_bool treats everything that is not "true" as False,
    which is right for a machine-generated export and wrong here: corps type
    these by hand, and "Yes" silently becoming False zeroes a relief count in
    a ministerial report.
    """
    cleaned = _clean(raw)
    if cleaned is None:
        return False
    lowered = cleaned.lower()
    if lowered in TRUE_VALUES:
        return True
    if lowered in FALSE_VALUES:
        return False
    return None


def parse_corp_decimal(raw: str | None) -> "Decimal | None | object":
    """Returns Decimal, None for an empty cell, or UNPARSEABLE.

    Accepts what a person types: a leading currency symbol and thousands
    separators. "$12,500" is a number; "about ten grand" is a row error.
    """
    cleaned = _clean(raw)
    if cleaned is None:
        return None
    stripped = cleaned.lstrip("$").replace(",", "").strip()
    try:
        return Decimal(stripped)
    except InvalidOperation:
        return UNPARSEABLE


def parse_corp_int(raw: str | None) -> "int | None | object":
    """Returns int, None for an empty cell, or UNPARSEABLE."""
    cleaned = _clean(raw)
    if cleaned is None:
        return None
    try:
        return int(cleaned.replace(",", ""))
    except ValueError:
        return UNPARSEABLE
```

- [ ] **Step 4: Use them in `parse_incident_row`**

Replace the `parse_bool` / `parse_int` / `parse_decimal` calls in `parse_incident_row`'s returned dict. Because each can now fail, resolve every cell before building the dict, returning a `RowError` on the first failure:

```python
    numeric_cells = {
        "Injuries Count": "injuries_count",
        "Deaths Count": "deaths_count",
        "Special Needs Occupants": "special_needs_occupants",
    }
    numbers: dict[str, int | None] = {}
    for column, field in numeric_cells.items():
        value = parse_corp_int(row.get(column))
        if value is UNPARSEABLE:
            return None, RowError(
                row_number=row_number,
                reason=f"{column} is not a whole number: {_clean(row.get(column))!r}",
            )
        numbers[field] = value

    cost = parse_corp_decimal(row.get("Estimated Damage Cost"))
    if cost is UNPARSEABLE:
        return None, RowError(
            row_number=row_number,
            reason=f"Estimated Damage Cost is not a number: "
            f"{_clean(row.get('Estimated Damage Cost'))!r}",
        )

    boolean_cells = {
        "Injuries Occurred": "injuries_occurred",
        "Deaths Occurred": "deaths_occurred",
        "Relief Supplied": "relief_supplied",
        "Forwarded To Agency": "forwarded_to_agency",
        "Further Assessment Required": "further_assessment_required",
        "Other Follow Up": "other",
    }
    flags: dict[str, bool] = {}
    for column, field in boolean_cells.items():
        value = parse_corp_bool(row.get(column))
        if value is None:
            return None, RowError(
                row_number=row_number,
                reason=f"{column} is not yes or no: {_clean(row.get(column))!r}",
            )
        flags[field] = value
```

Then build the returned dict from `numbers`, `cost` and `flags` rather than calling the survey123 helpers:

```python
            "injuries_occurred": flags["injuries_occurred"],
            "injuries_count": numbers["injuries_count"],
            "deaths_occurred": flags["deaths_occurred"],
            "deaths_count": numbers["deaths_count"],
            "special_needs_occupants": numbers["special_needs_occupants"],
            "estimated_damage_cost": cost,
            ...
            "follow_up_flags": {
                "relief_supplied": flags["relief_supplied"],
                "forwarded_to_agency": flags["forwarded_to_agency"],
                "further_assessment_required": flags["further_assessment_required"],
                "other": flags["other"],
            },
```

Remove `parse_bool`, `parse_decimal`, `parse_int` from the `survey123.ingest` import if nothing else in the file uses them.

- [ ] **Step 5: Run the tests and the full suite**

Run: `cd apps/backend && .venv/bin/python -m pytest tests/test_sitreps_parse.py -q && .venv/bin/python -m pytest -q`
Expected: all parse tests pass; suite 0 failed. The existing fixture `fixtures/sample_submission_incidents.csv` uses `True`/`False`, which remain valid.

- [ ] **Step 6: Commit**

```bash
cd apps/backend
git add app/modules/sitreps/parse.py tests/test_sitreps_parse.py
git commit -m "sitreps: reject unparseable hand-typed cells instead of coercing them"
```

---

## Task 2: F2 — `query_ref` names only the parameters the query used

**Files:**
- Modify: `apps/backend/app/modules/survey123/metrics.py`
- Test: `apps/backend/tests/test_metrics_helpers.py`

**Interfaces:**
- Produces: `QUERY_PARAMS: tuple[str, ...]` — the parameter names the query layer consumes. `build_query_ref` filters on it.

- [ ] **Step 1: Write the failing tests**

Append to `apps/backend/tests/test_metrics_helpers.py`:

```python
def test_query_ref_omits_params_the_query_never_applied():
    # A template carrying a legacy "source" key silently widened its result
    # set while query_ref still advertised the filter. query_ref is the string
    # an auditor uses to reproduce a number.
    from app.modules.survey123.metrics import build_query_ref

    ref = build_query_ref(
        "estimated_damage_total",
        {
            "corporation": "diego_martin_regional_corporati",
            "source": "sitreps",
            "incident_type": "flood",
        },
    )

    assert "source" not in ref
    assert "incident_type" not in ref
    assert "corporation=diego_martin_regional_corporati" in ref


def test_query_ref_still_names_every_applied_filter():
    from app.modules.survey123.metrics import build_query_ref

    ref = build_query_ref(
        "incident_count",
        {
            "corporation": "siparia_regional_corporation",
            "community": "Penal",
            "date_from": "2023-06-01",
            "date_to": "2023-06-30",
            "include_pending": True,
        },
    )

    for expected in (
        "corporation=siparia_regional_corporation",
        "community=Penal",
        "date_from=2023-06-01",
        "date_to=2023-06-30",
        "include_pending=True",
    ):
        assert expected in ref


def test_query_params_covers_every_key_the_query_layer_reads():
    # Guards the two from drifting: a filter added to apply_common_filters or
    # base_query without being listed here would vanish from query_ref.
    import inspect

    from app.modules.survey123 import metrics

    source = inspect.getsource(metrics.apply_common_filters) + inspect.getsource(
        metrics.base_query
    )

    for name in metrics.QUERY_PARAMS:
        assert f'"{name}"' in source, f"{name} is in QUERY_PARAMS but no query reads it"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/backend && .venv/bin/python -m pytest tests/test_metrics_helpers.py -q -k "query_ref_omits or query_params_covers"`
Expected: FAIL — `source` and `incident_type` currently appear in the rendered ref, and `QUERY_PARAMS` does not exist.

- [ ] **Step 3: Add the allowlist and filter on it**

In `apps/backend/app/modules/survey123/metrics.py`, add above `build_query_ref`:

```python
# The parameters the query layer actually consumes. build_query_ref renders
# only these, because query_ref is the string an auditor uses to reproduce a
# figure — printing a key that was silently ignored describes a query that
# never ran. Keep in step with apply_common_filters and base_query.
QUERY_PARAMS = ("corporation", "community", "date_from", "date_to", "include_pending")
```

and change the function:

```python
def build_query_ref(metric_name: str, params: dict) -> str:
    parts = [
        f"{k}={v}"
        for k, v in sorted(params.items())
        if k in QUERY_PARAMS and v is not None and v is not False
    ]
    return f"{metric_name}(" + ", ".join(parts) + ")"
```

- [ ] **Step 4: Run the tests and the full suite**

Run: `cd apps/backend && .venv/bin/python -m pytest -q`
Expected: 0 failed. If an existing test asserted a `query_ref` containing `source`, it encoded the defect — update it and say so in the commit message.

- [ ] **Step 5: Commit**

```bash
cd apps/backend
git add app/modules/survey123/metrics.py tests/test_metrics_helpers.py
git commit -m "metrics: render only applied filters in query_ref"
```

---

## Task 3: F3 — Bound the year pattern to real years

**Files:**
- Modify: `apps/backend/app/core/citation_check.py`
- Test: `apps/backend/tests/test_citation_check.py`

**Interfaces:**
- Consumes: `make_fact_table()` and the `CID` constant already in the test file.

- [ ] **Step 1: Write the failing tests**

Append to `apps/backend/tests/test_citation_check.py`:

```python
def test_a_four_digit_figure_after_a_month_name_is_still_checked():
    # PROSE_DATE_RE's MONTH+YEAR alternative erased these entirely: the
    # sentence ended up with no tokens, so the invented-number AND the
    # missing-citation checks were both skipped.
    result = check_citations(
        f"There were 19 incidents [{CID}]. In May 2500 households were affected.",
        make_fact_table(),
    )

    assert result.passed is False


def test_a_large_invented_figure_after_an_abbreviated_month_is_still_checked():
    result = check_citations(
        f"There were 19 incidents [{CID}]. Sept 1200 people were displaced.",
        make_fact_table(),
    )

    assert result.passed is False


def test_real_month_and_year_is_still_not_a_figure():
    result = check_citations(
        f"Situation Report for June 2023 covering 19 incidents [{CID}].", make_fact_table()
    )

    assert result.violations == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/backend && .venv/bin/python -m pytest tests/test_citation_check.py -q -k "four_digit_figure or large_invented_figure"`
Expected: FAIL — both currently return `passed=True` with zero violations.

- [ ] **Step 3: Bound the year**

In `apps/backend/app/core/citation_check.py`, change:

```python
_YEAR = r"\d{4}"
```

to:

```python
# Bounded to plausible years. An unbounded \d{4} swallowed any 4-digit figure
# following a month name — "In May 2500 households were affected" was erased
# before the number scan, so both the invented-number and missing-citation
# checks were skipped and an uncited invented figure shipped as "ok".
_YEAR = r"(?:19|20)\d{2}"
```

- [ ] **Step 4: Run the tests and the full suite**

Run: `cd apps/backend && .venv/bin/python -m pytest -q`
Expected: 0 failed, including the existing prose-date tests, which all use real years.

- [ ] **Step 5: Commit**

```bash
cd apps/backend
git add app/core/citation_check.py tests/test_citation_check.py
git commit -m "citations: bound the year pattern so it stops erasing large figures"
```

---

## Task 4: F4 — Incidents require an event

**Files:**
- Modify: `apps/backend/app/modules/sitreps/models.py`
- Modify: `apps/backend/app/api/submissions.py`
- Modify: `apps/backend/cli.py`
- Test: `apps/backend/tests/test_api_submissions.py`, `apps/backend/tests/test_sitreps_models.py`

**Interfaces:**
- Consumes: `_require_corporation`, `get_event` (already in `submissions.py`).
- Produces: `SitrepIncident.record_ref` now `f"{corporation}:{event_id or '-'}:{submission_id}:{row_id}"`.

- [ ] **Step 1: Write the failing tests**

Append to `apps/backend/tests/test_api_submissions.py`, reusing its `client()` helper and `CORP` constant:

```python
def test_a_submission_with_incidents_and_no_event_is_rejected():
    # Without an event, supersession is skipped, so re-filing a cumulative
    # table triples the incident count and record_ref collides across rows.
    c = client()
    incidents = "Row ID,Incident Type,Date of Event\n1,fallen_tree,2023-06-27\n"

    response = c.post(
        "/submissions",
        data={"corporation": CORP, "as_at": "2023-06-30T16:00:00"},
        files={"incidents_file": ("i.csv", io.BytesIO(incidents.encode()), "text/csv")},
    )

    assert response.status_code == 400
    assert "event" in response.json()["detail"].lower()


def test_a_logs_only_submission_needs_no_event():
    # Logs are point-in-time state: they never supersede and never collide.
    c = client()
    logs = "Category,Statement,Item,Quantity,Unit,Status\nresource,200 sandbags,sandbags,200,bags,available\n"

    response = c.post(
        "/submissions",
        data={"corporation": CORP, "as_at": "2023-06-30T16:00:00"},
        files={"logs_file": ("l.csv", io.BytesIO(logs.encode()), "text/csv")},
    )

    assert response.status_code == 201
    assert response.json()["logs_inserted"] == 1


def test_a_submission_with_incidents_and_an_event_is_accepted():
    c = client()
    created = c.post(
        "/events",
        json={
            "corporation": CORP,
            "title": "Adverse Weather June 2023",
            "hazard_type": "wind",
            "started_at": "2023-06-27T00:00:00",
        },
    )
    event_id = created.json()["id"]
    incidents = "Row ID,Incident Type,Date of Event\n1,fallen_tree,2023-06-27\n"

    response = c.post(
        "/submissions",
        data={"corporation": CORP, "as_at": "2023-06-30T16:00:00", "event_id": event_id},
        files={"incidents_file": ("i.csv", io.BytesIO(incidents.encode()), "text/csv")},
    )

    assert response.status_code == 201
    assert response.json()["incidents_inserted"] == 1
```

Append to `apps/backend/tests/test_sitreps_models.py`, reusing its `make_session` helper:

```python
def test_record_ref_distinguishes_rows_from_different_submissions(tmp_path):
    # Previously "corp:-:1" for every event-less row, so one identifier named
    # many rows and no auditor could trace a figure back to one of them.
    from datetime import datetime

    from app.modules.sitreps.models import SitrepIncident

    session = make_session(tmp_path)
    first = SitrepIncident(
        submission_id=1,
        corporation="diego_martin_regional_corporati",
        event_id=None,
        row_id="1",
        ingested_at=datetime(2023, 6, 27),
    )
    second = SitrepIncident(
        submission_id=2,
        corporation="diego_martin_regional_corporati",
        event_id=None,
        row_id="1",
        ingested_at=datetime(2023, 6, 28),
    )

    assert first.record_ref != second.record_ref
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/backend && .venv/bin/python -m pytest tests/test_api_submissions.py tests/test_sitreps_models.py -q -k "no_event or logs_only or and_an_event or distinguishes_rows"`
Expected: FAIL — the incidents-without-event post currently returns 201, and both `record_ref` values are `diego_martin_regional_corporati:-:1`.

- [ ] **Step 3: Make `record_ref` unique**

In `apps/backend/app/modules/sitreps/models.py`, change the property:

```python
    @property
    def record_ref(self) -> str:
        # submission_id included so one reference names exactly one row. Without
        # it, every event-less row rendered event_id as "-" and rows from
        # different submissions shared an identifier, making a cited figure
        # untraceable.
        return f"{self.corporation}:{self.event_id or '-'}:{self.submission_id}:{self.row_id}"
```

- [ ] **Step 4: Require an event for incidents in the API**

In `apps/backend/app/api/submissions.py`, add immediately after the `alert_level` check in `post_submission`:

```python
    if incidents_file is not None and event_id is None:
        raise HTTPException(
            status_code=400,
            detail=(
                "a submission carrying incidents must name an event; "
                "create one with POST /events first. Situation logs may be "
                "filed without an event."
            ),
        )
```

It must sit before the files are spooled, so a rejected submission writes no temp files.

- [ ] **Step 5: Apply the same rule in the CLI**

In `apps/backend/cli.py`, inside `create_submission_command`, before the `ingest_submission` call:

```python
    if incidents is not None and event_id is None:
        typer.echo(
            "a submission carrying incidents must name an event; pass --event-id",
            err=True,
        )
        raise typer.Exit(code=1)
```

- [ ] **Step 6: Run the tests and the full suite**

Run: `cd apps/backend && .venv/bin/python -m pytest -q`
Expected: 0 failed. `tests/test_sitreps_submission_ingest.py` calls `ingest_submission` directly rather than through the API, so its event-less incident tests still pass — that is intended. The constraint belongs at the API and CLI boundary, and `test_event_less_submissions_do_not_supersede_each_other` documents the underlying behaviour that the boundary now prevents reaching.

- [ ] **Step 7: Commit**

```bash
cd apps/backend
git add app/modules/sitreps/models.py app/api/submissions.py cli.py tests/test_api_submissions.py tests/test_sitreps_models.py
git commit -m "sitreps: require an event for incidents and make record_ref unique"
```

---

## Task 5: Verify the four reproductions are closed

Verification only; changes no files. Each defect had a concrete reproduction — run them, not just the unit tests.

- [ ] **Step 1: F1 and F3 against live code**

```bash
cd apps/backend && .venv/bin/python -c "
from datetime import datetime
from app.core.contracts import Citation, Fact, FactTable
from app.core.citation_check import check_citations
from app.modules.sitreps.parse import parse_incident_row

ft = FactTable(request_id='r', template='t', template_version=1, params={},
    generated_at=datetime(2026,8,5),
    facts=[Fact(metric='incident_count', value=15, unit='i', scope={}, breakdown=None,
        verification='validated', citation=Citation(cid='C001', module='sitreps',
        description='d', query_ref='q', record_ids=[], as_of=datetime(2026,8,5)))], gaps=[])

print('F3:', check_citations('There were 15 incidents [C001]. In May 2500 households were affected.', ft).passed, '(expect False)')
row = {'Row ID':'1','Incident Type':'fire','Date of Event':'2023-06-27',
       'Estimated Damage Cost':'\$12,500','Injuries Occurred':'Yes'}
f, e = parse_incident_row(row, 1)
print('F1: error=', e, '| cost=', None if f is None else f['estimated_damage_cost'], '(expect no error, 12500)')
"
```
Expected: F3 `False`; F1 no error and cost `12500`.

- [ ] **Step 2: F2 against live code**

```bash
cd apps/backend && .venv/bin/python -c "
from app.modules.survey123.metrics import build_query_ref
print(build_query_ref('estimated_damage_total', {'corporation':'diego_martin_regional_corporati','source':'sitreps','incident_type':'flood'}))
"
```
Expected: names `corporation` only — no `source`, no `incident_type`.

- [ ] **Step 3: F4 against a real database**

```bash
cd apps/backend && rm -f /tmp/f4check.db && DATABASE_URL="sqlite:////tmp/f4check.db" .venv/bin/python -c "
import csv, datetime
from pathlib import Path
from app.db import Base, make_engine, SessionLocal
import app.modules.survey123.models, app.modules.sitreps.models, app.core.report_models, app.core.template_models
Base.metadata.create_all(make_engine('sqlite:////tmp/f4check.db'))
from app.modules.sitreps.ingest import ingest_submission
from app.modules.sitreps.store import create_event
from app.core.registry import ensure_default_modules_registered, get_module

p = Path('/tmp/f4check.csv')
with open(p,'w',newline='') as f:
    w=csv.writer(f); w.writerow(['Row ID','Incident Type','Date of Event'])
    w.writerow(['1','fire','2023-06-27']); w.writerow(['2','flooding_','2023-06-28'])

s = SessionLocal(); CORP='diego_martin_regional_corporati'
e = create_event(s, corporation=CORP, title='Storm', hazard_type='wind', started_at=datetime.datetime(2023,6,27))
for d in (27,28,29):
    ingest_submission(s, corporation=CORP, as_at=datetime.datetime(2023,6,d), event_id=e.id, incidents_path=p)
ensure_default_modules_registered()
facts = get_module('sitreps').run_metric('incident_count', {'corporation':CORP}, s)
print('incident_count:', facts[0].value, '(expect 2)')
print('unique record_ids:', len(set(facts[0].citation.record_ids)), 'of', len(facts[0].citation.record_ids), '(expect equal)')
s.close()
"
```
Expected: `incident_count: 2`, and the record ids all distinct. Before this plan the same filing produced 6.

- [ ] **Step 4: Record the results**

Report each expectation and what actually printed. No commit.

---

## Done when

- `$12,500` parses to `12500`; `"Yes"` is `True`; `"about ten grand"` and `"maybe"` are row errors naming the cell; empty cells remain silent.
- `query_ref` names only applied filters, and `QUERY_PARAMS` cannot drift from the query layer without failing a test.
- `"In May 2500 households were affected"` is flagged; real dates still are not.
- A submission carrying incidents without an event is rejected by both API and CLI; a logs-only submission without an event still succeeds.
- `record_ref` differs across submissions for the same row id.
- Backend suite: **0 failed**.
