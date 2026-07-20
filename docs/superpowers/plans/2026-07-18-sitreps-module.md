# Sitreps Data Module (Incident Ingest) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a corporation's DMU enter their own real-time situation-report incidents as structured data (reusing the existing `Incident` table shape) instead of an LLM ever having to parse free-form sitrep documents, and make that data queryable/citable through the existing metric/citation pipeline exactly like `survey123` data is today.

**Architecture:** A new `sitreps` data module shares the existing `incidents` table with `survey123` (adding one `source` column to distinguish rows), reuses `survey123`'s existing metric-query functions and normalization helpers unchanged, and reuses the existing `DataModule` protocol / citation pipeline verbatim. The only new code is: a CSV ingest path shaped for corp-friendly manual data entry (Google-Sheets-exportable), and a thin `SitrepModule` that calls the same query functions as `Survey123Module` while tagging results with `source="sitreps"`. `app/core/engine.py` is untouched.

**Tech Stack:** FastAPI, SQLAlchemy 2.x, Pydantic v2, Alembic, pytest, Typer (repo: `apps/backend/`).

## Global Constraints

- Python 3.13, SQLAlchemy 2.0 query style, Pydantic v2 — match every existing file in `app/modules/survey123/` and `app/core/`.
- Every test must be network-free.
- No LLM-facing code (`app/core/engine.py`, `app/core/citation_check.py`, `app/core/llm.py`) is touched by this plan — sitrep facts flow through the exact same `Fact`/`Citation`/`FactTable` contract survey123 facts already use, narrated the same way.
- PII must never be stored: names and contact info are dropped at ingest time (never even written to the DB), matching `app/modules/survey123/ingest.py`'s existing `PII_COLUMNS` pattern — not hashed-and-kept, not stored-then-hidden.
- Existing `survey123` behavior must be unchanged for any caller that doesn't know about `source` — every existing test in `tests/test_metrics_helpers.py`, `tests/test_survey123_metrics_dispatch.py`, `tests/test_models.py`, and all `tests/test_metrics_*.py` files must keep passing with zero edits, except where this plan explicitly says otherwise.
- Alembic migration must chain from the actual current head — verify with `.venv/bin/alembic -c alembic.ini heads` before writing the migration (this plan assumes the head is `f3a1c9d7b204`).
- Full backend test suite entry point: `cd apps/backend && .venv/bin/python -m pytest -q`. Current baseline is 212 passing, 0 failures.
- **Explicitly out of scope for this plan** (do not build): a separate corp-preparedness/status-log table, new report templates that consume `sitreps` data, and live Google Sheets API integration. This plan only makes incident-level sitrep data ingestible and queryable — those are natural follow-ups, not part of this increment.

---

## File Structure

**New files:**
- `alembic/versions/b8f2e4a91c7d_add_source_to_incidents.py` — migration
- `app/modules/sitreps/__init__.py` — empty package marker
- `app/modules/sitreps/ingest.py` — sitrep CSV template, row parser, `ingest_sitrep_csv`
- `app/modules/sitreps/module.py` — `SitrepModule`, a `DataModule` delegating to `survey123`'s metric functions
- `fixtures/sample_sitrep_small.csv` — test fixture
- `tests/test_sitreps_ingest.py`
- `tests/test_sitreps_module.py`
- `tests/test_cli_sitreps.py`

**Modified files:**
- `app/modules/survey123/models.py` — add `Incident.source` column
- `app/modules/survey123/metrics.py` — `build_citation` derives `module`/`cid` from `params["source"]` (defaults to `"survey123"`, backward compatible); `apply_common_filters` adds an optional `source` filter
- `app/modules/survey123/module.py` — `Survey123Module.run_metric` injects `params["source"] = "survey123"`
- `tests/test_metrics_helpers.py` — add source-filtering tests, add `source` to `make_incident()` defaults
- `tests/test_survey123_metrics_dispatch.py` — one new assertion confirming citation module
- `app/__init__.py` — register `sitrep_module` alongside `survey123`
- `cli.py` — add `ingest sitreps <corporation> <file>` command
- `tests/test_survey123_module.py` — update `/modules` endpoint test for two registered modules

---

### Task 1: Add `source` column and thread it through the shared query/citation layer

**Files:**
- Create: `alembic/versions/b8f2e4a91c7d_add_source_to_incidents.py`
- Modify: `app/modules/survey123/models.py`, `app/modules/survey123/metrics.py`, `app/modules/survey123/module.py`
- Test: `tests/test_metrics_helpers.py`, `tests/test_survey123_metrics_dispatch.py`

**Interfaces:**
- Produces: `Incident.source: str` (default `"survey123"`), `build_citation(metric_name, index, params, global_ids, description)` now derives `module`/`cid` from `params.get("source", "survey123")` — same signature, same default behavior when `params` has no `"source"` key. `apply_common_filters`/`base_query` respect an optional `params["source"]` filter. Task 3 relies on this to isolate `sitreps` rows from `survey123` rows in the same table.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_metrics_helpers.py`, updating `make_incident()`'s defaults dict (add one line) and adding four new tests:

```python
def make_incident(**overrides) -> Incident:
    defaults = dict(
        global_id="GUID-DEFAULT",
        object_id=1,
        corporation="sangre_grande_regional_corporat",
        raw_corporation=None,
        community="Sangre Grande",
        street="Test Street",
        incident_type="flooding_",
        raw_incident_type=None,
        incident_type_other=None,
        incident_summary=None,
        event_date=datetime(2024, 6, 1),
        event_time=None,
        assessment_date=None,
        creation_date=datetime(2024, 6, 1),
        edit_date=datetime(2024, 6, 1),
        occupants_count=None,
        injuries_occurred=False,
        injuries_count=None,
        deaths_occurred=False,
        deaths_count=None,
        building_damage=None,
        crops_livestock=None,
        personal_items=None,
        furniture_appliances=None,
        action_taken="action_taken",
        relief_items=None,
        shelter=None,
        special_needs_occupants=None,
        estimated_damage_cost=None,
        follow_up=None,
        follow_up_flags={"relief_supplied": False, "forwarded_to_agency": False, "further_assessment_required": False, "other": False},
        validation_status="validated",
        is_duplicate=False,
        duplicate_reason=None,
        flood_type=None,
        flood_trigger=None,
        flood_height=None,
        lon=None,
        lat=None,
        officer_name=None,
        officer_position=None,
        dedup_hash=None,
        source="survey123",
        source_file="test.csv",
        ingested_at=datetime(2024, 6, 1),
    )
    defaults.update(overrides)
    return Incident(**defaults)


def test_apply_common_filters_filters_by_source(tmp_path):
    session = make_session(tmp_path)
    session.add(make_incident(global_id="G1", source="survey123"))
    session.add(make_incident(global_id="G2", source="sitreps"))
    session.commit()

    rows = session.execute(base_query({"source": "sitreps"})).scalars().all()

    assert [r.global_id for r in rows] == ["G2"]


def test_base_query_without_source_param_includes_all_sources(tmp_path):
    session = make_session(tmp_path)
    session.add(make_incident(global_id="G1", source="survey123"))
    session.add(make_incident(global_id="G2", source="sitreps"))
    session.commit()

    rows = session.execute(base_query({})).scalars().all()

    assert sorted(r.global_id for r in rows) == ["G1", "G2"]


def test_build_citation_defaults_module_to_survey123_when_no_source_param():
    citation = build_citation("incident_count", 0, {}, ["GUID-1"], "test description")

    assert citation.module == "survey123"
    assert citation.cid == "survey123-incident_count-0"


def test_build_citation_uses_source_param_for_module_and_cid():
    citation = build_citation("incident_count", 0, {"source": "sitreps"}, ["GUID-1"], "test description")

    assert citation.module == "sitreps"
    assert citation.cid == "sitreps-incident_count-0"
```

Add to `tests/test_survey123_metrics_dispatch.py` (after `test_run_metric_dispatches_to_incident_count`):

```python
def test_run_metric_tags_citation_module_as_survey123(tmp_path):
    session = make_session(tmp_path)

    facts = survey123_module.run_metric("incident_count", {}, session)

    assert facts[0].citation.module == "survey123"
    assert facts[0].citation.cid == "survey123-incident_count-0"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_metrics_helpers.py tests/test_survey123_metrics_dispatch.py -v`
Expected: FAIL — `TypeError: 'source' is an invalid keyword argument for Incident` (column doesn't exist yet) and `AssertionError` on the two `build_citation` tests (cid still hardcoded to `survey123-...` regardless of params, which happens to already pass for the default test but fails for `test_build_citation_uses_source_param_for_module_and_cid` since nothing reads `params["source"]` yet).

- [ ] **Step 3: Implement**

Verify the current migration head first:

Run: `.venv/bin/alembic -c alembic.ini heads`
Expected: `f3a1c9d7b204 (head)` — if different, use the actual head as `down_revision` below instead.

Create `alembic/versions/b8f2e4a91c7d_add_source_to_incidents.py`:

```python
"""add source to incidents

Revision ID: b8f2e4a91c7d
Revises: f3a1c9d7b204
Create Date: 2026-07-18 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b8f2e4a91c7d'
down_revision: Union[str, Sequence[str], None] = 'f3a1c9d7b204'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('incidents', sa.Column('source', sa.String(), nullable=False, server_default='survey123'))
    op.alter_column('incidents', 'source', server_default=None)


def downgrade() -> None:
    op.drop_column('incidents', 'source')
```

In `app/modules/survey123/models.py`, add the `source` column right after `object_id` (line 15):

```python
    id: Mapped[int] = mapped_column(primary_key=True)
    global_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    object_id: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String, nullable=False, default="survey123")
```

(The Python-side `default="survey123"` mirrors the existing `is_duplicate`/`injuries_occurred` pattern in this same model — it means any `Incident(...)` construction that omits `source` still works unchanged, matching the migration's `server_default`.)

In `app/modules/survey123/metrics.py`, update `build_citation` (currently hardcodes `module="survey123"` and `cid=f"survey123-{metric_name}-{index}"`):

```python
def build_citation(metric_name: str, index: int, params: dict, global_ids: list[str], description: str) -> Citation:
    module = params.get("source", "survey123")
    ordered = sorted(global_ids)
    record_ids = ordered[:200] if len(ordered) <= 200 else None
    return Citation(
        cid=f"{module}-{metric_name}-{index}",
        module=module,
        description=description,
        query_ref=build_query_ref(metric_name, params),
        record_ids=record_ids,
        as_of=datetime.now(),
    )
```

Update `apply_common_filters` to add the optional source filter (add this as the first check, before the existing `corporation` check):

```python
def apply_common_filters(stmt: Select, params: dict) -> Select:
    if params.get("source") is not None:
        stmt = stmt.where(Incident.source == params["source"])
    if params.get("corporation") is not None:
        stmt = stmt.where(Incident.corporation == params["corporation"])
    if params.get("community") is not None:
        stmt = stmt.where(Incident.community == params["community"])
    date_from = parse_date_param(params.get("date_from"))
    if date_from is not None:
        stmt = stmt.where(Incident.event_date >= date_from)
    date_to = parse_date_param(params.get("date_to"))
    if date_to is not None:
        stmt = stmt.where(Incident.event_date < date_to + timedelta(days=1))
    return stmt
```

In `app/modules/survey123/module.py`, update `run_metric` to inject the source (this fixes a latent bug: once `sitreps` rows exist in the same table, `survey123`'s own metrics must not silently include them):

```python
    def run_metric(self, name: str, params: dict, session: Session) -> list[Fact]:
        fn = METRIC_FUNCTIONS.get(name)
        if fn is None:
            raise ValueError(f"unknown metric for survey123: {name}")
        return fn({**params, "source": "survey123"}, session)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_metrics_helpers.py tests/test_survey123_metrics_dispatch.py tests/test_models.py -v`
Expected: PASS. Then run the full suite to confirm zero regressions:

Run: `.venv/bin/python -m pytest -q`
Expected: `216 passed` (212 baseline + 4 new tests in `test_metrics_helpers.py` + 1 new in `test_survey123_metrics_dispatch.py` = 217 — verify the exact count from your own run; the important bar is zero failures, not matching this number exactly if a prior count differs).

- [ ] **Step 5: Commit**

```bash
git add alembic/versions/b8f2e4a91c7d_add_source_to_incidents.py app/modules/survey123/models.py app/modules/survey123/metrics.py app/modules/survey123/module.py tests/test_metrics_helpers.py tests/test_survey123_metrics_dispatch.py
git commit -m "survey123: add source column and thread it through citations/filters, backward compatible"
```

---

### Task 2: Sitrep CSV ingest

**Files:**
- Create: `app/modules/sitreps/__init__.py`
- Create: `app/modules/sitreps/ingest.py`
- Create: `fixtures/sample_sitrep_small.csv`
- Test: `tests/test_sitreps_ingest.py`

**Interfaces:**
- Consumes: `app.modules.survey123.ingest.parse_bool`, `parse_int`, `parse_decimal`, `parse_datetime` (existing pure functions), `app.modules.survey123.normalize.normalize_corporation`, `normalize_incident_type` (existing pure functions), `app.modules.survey123.models.Incident` (Task 1's `source` column).
- Produces: `ingest_sitrep_csv(file_path: Path, corporation_raw: str, session: Session) -> IngestResult`, `PII_COLUMNS_SITREPS: list[str]` — Task 4's CLI command calls `ingest_sitrep_csv` by this exact name/signature.

- [ ] **Step 1: Write the failing tests**

Create `fixtures/sample_sitrep_small.csv`:

```csv
Row ID,Community,Street,Incident Type,Date of Event,Incident Summary,Name of Person,Contact Information,Injuries Occurred,Injuries Count,Deaths Occurred,Deaths Count,Building Damage,Special Needs Occupants,Estimated Damage Cost,Action Taken,Relief Supplied,Forwarded To Agency,Further Assessment Required,Other Follow Up,Officer Name,Officer Position
1,Petit Valley,Cameron Road,blown_off_roof,2023-06-27,Fallen tree damaged roof.,Velma Cupidore,793-9056,False,,False,,Branch damaged metal sheet.,,,DMU responded and removed fallen tree.,True,False,False,False,J. Baptiste,DMU Field Officer
2,Maraval,Saddle Road,blown_off_roof,2023-06-27,Leaking roof causing rainwater inundation.,Juliet Henderson,681-4001,False,,False,,Minor holes in roof.,,,Tarpaulin issued.,True,False,False,False,J. Baptiste,DMU Field Officer
3,Diamond Vale,Opal Gardens,fire,2023-06-27,Small kitchen fire contained.,Simone Beard,493-8022,True,1,False,,Minor smoke damage.,,500,Assessment complete.,False,True,False,False,J. Baptiste,DMU Field Officer
```

Create `tests/test_sitreps_ingest.py`:

```python
from pathlib import Path

from sqlalchemy.orm import sessionmaker

from app.db import Base, make_engine
from app.modules.survey123.models import Incident
from app.modules.sitreps.ingest import PII_COLUMNS_SITREPS, ingest_sitrep_csv

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "sample_sitrep_small.csv"
CORPORATION = "diego_martin_regional_corporati"


def make_session(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


def test_ingest_sitrep_csv_reads_all_rows(tmp_path):
    session = make_session(tmp_path)

    result = ingest_sitrep_csv(FIXTURE_PATH, CORPORATION, session)

    assert result.rows_read == 3
    assert result.rows_inserted == 3
    assert result.rows_updated == 0
    assert result.pii_columns_dropped == PII_COLUMNS_SITREPS


def test_ingest_sitrep_csv_tags_rows_with_sitreps_source(tmp_path):
    session = make_session(tmp_path)

    ingest_sitrep_csv(FIXTURE_PATH, CORPORATION, session)

    rows = session.query(Incident).all()
    assert len(rows) == 3
    assert all(r.source == "sitreps" for r in rows)


def test_ingest_sitrep_csv_normalizes_corporation(tmp_path):
    session = make_session(tmp_path)

    ingest_sitrep_csv(FIXTURE_PATH, CORPORATION, session)

    rows = session.query(Incident).all()
    assert all(r.corporation == CORPORATION for r in rows)


def test_ingest_sitrep_csv_flags_unmapped_corporation(tmp_path):
    session = make_session(tmp_path)

    result = ingest_sitrep_csv(FIXTURE_PATH, "Not A Real Corporation", session)

    assert result.unmapped_values["Corporation"] == ["Not A Real Corporation"]
    rows = session.query(Incident).all()
    assert all(r.corporation == "unmapped" for r in rows)


def test_ingest_sitrep_csv_drops_pii_never_stores_it(tmp_path):
    session = make_session(tmp_path)

    ingest_sitrep_csv(FIXTURE_PATH, CORPORATION, session)

    columns = set(Incident.__table__.columns.keys())
    assert "name_of_person" not in columns
    assert "contact_information" not in columns
    row = session.query(Incident).filter_by(global_id=f"sitreps-{CORPORATION}-1").one()
    assert "Velma Cupidore" not in (row.incident_summary or "")
    assert "793-9056" not in (row.incident_summary or "")


def test_ingest_sitrep_csv_marks_validated_and_not_duplicate(tmp_path):
    session = make_session(tmp_path)

    ingest_sitrep_csv(FIXTURE_PATH, CORPORATION, session)

    rows = session.query(Incident).all()
    assert all(r.validation_status == "validated" for r in rows)
    assert all(r.is_duplicate is False for r in rows)


def test_ingest_sitrep_csv_is_idempotent_on_reingest(tmp_path):
    session = make_session(tmp_path)
    ingest_sitrep_csv(FIXTURE_PATH, CORPORATION, session)

    result = ingest_sitrep_csv(FIXTURE_PATH, CORPORATION, session)

    assert result.rows_inserted == 0
    assert result.rows_updated == 3
    assert session.query(Incident).count() == 3


def test_ingest_sitrep_csv_parses_incident_type_and_damage_fields(tmp_path):
    session = make_session(tmp_path)

    ingest_sitrep_csv(FIXTURE_PATH, CORPORATION, session)

    fire_row = session.query(Incident).filter_by(global_id=f"sitreps-{CORPORATION}-3").one()
    assert fire_row.incident_type == "fire"
    assert fire_row.injuries_occurred is True
    assert fire_row.injuries_count == 1
    assert float(fire_row.estimated_damage_cost) == 500.0
    assert fire_row.follow_up_flags == {
        "relief_supplied": False,
        "forwarded_to_agency": True,
        "further_assessment_required": False,
        "other": False,
    }
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_sitreps_ingest.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.modules.sitreps'`.

- [ ] **Step 3: Implement**

Create `app/modules/sitreps/__init__.py` (empty).

Create `app/modules/sitreps/ingest.py`:

```python
import csv
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.contracts import IngestResult
from app.modules.survey123.ingest import parse_bool, parse_datetime, parse_decimal, parse_int
from app.modules.survey123.models import Incident
from app.modules.survey123.normalize import normalize_corporation, normalize_incident_type

PII_COLUMNS_SITREPS = ["Name of Person", "Contact Information"]


def parse_sitrep_row(row: dict[str, str], corporation: str) -> dict:
    incident_type, raw_incident_type = normalize_incident_type(row.get("Incident Type"))
    row_id = (row.get("Row ID") or "").strip()

    return {
        "global_id": f"sitreps-{corporation}-{row_id}",
        "object_id": int(row_id),
        "corporation": corporation,
        "raw_corporation": None,
        "community": (row.get("Community") or "").strip() or None,
        "street": (row.get("Street") or "").strip() or None,
        "incident_type": incident_type,
        "raw_incident_type": raw_incident_type,
        "incident_type_other": None,
        "incident_summary": (row.get("Incident Summary") or "").strip() or None,
        "event_date": parse_datetime(row.get("Date of Event")),
        "event_time": None,
        "assessment_date": None,
        "creation_date": datetime.now(timezone.utc),
        "edit_date": None,
        "occupants_count": None,
        "injuries_occurred": parse_bool(row.get("Injuries Occurred")),
        "injuries_count": parse_int(row.get("Injuries Count")),
        "deaths_occurred": parse_bool(row.get("Deaths Occurred")),
        "deaths_count": parse_int(row.get("Deaths Count")),
        "building_damage": (row.get("Building Damage") or "").strip() or None,
        "crops_livestock": None,
        "personal_items": None,
        "furniture_appliances": None,
        "action_taken": (row.get("Action Taken") or "").strip() or None,
        "relief_items": None,
        "shelter": None,
        "special_needs_occupants": parse_int(row.get("Special Needs Occupants")),
        "estimated_damage_cost": parse_decimal(row.get("Estimated Damage Cost")),
        "follow_up": None,
        "follow_up_flags": {
            "relief_supplied": parse_bool(row.get("Relief Supplied")),
            "forwarded_to_agency": parse_bool(row.get("Forwarded To Agency")),
            "further_assessment_required": parse_bool(row.get("Further Assessment Required")),
            "other": parse_bool(row.get("Other Follow Up")),
        },
        "validation_status": "validated",
        "flood_type": None,
        "flood_trigger": None,
        "flood_height": None,
        "lon": None,
        "lat": None,
        "officer_name": (row.get("Officer Name") or "").strip() or None,
        "officer_position": (row.get("Officer Position") or "").strip() or None,
        "dedup_hash": None,
        "source": "sitreps",
    }


def ingest_sitrep_csv(file_path: Path, corporation_raw: str, session: Session) -> IngestResult:
    corporation, raw_corporation = normalize_corporation(corporation_raw)
    corporation = corporation or "unmapped"

    with open(file_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        raw_rows = list(reader)

    unmapped_values: dict[str, list[str]] = {}
    if raw_corporation:
        unmapped_values["Corporation"] = [raw_corporation]

    rows_read = 0
    rows_inserted = 0
    rows_updated = 0

    for raw in raw_rows:
        rows_read += 1
        fields = parse_sitrep_row(raw, corporation)

        if fields["raw_incident_type"]:
            values = unmapped_values.setdefault("Incident Type", [])
            if fields["raw_incident_type"] not in values:
                values.append(fields["raw_incident_type"])

        existing = (
            session.execute(select(Incident).where(Incident.global_id == fields["global_id"]))
            .scalars()
            .first()
        )

        if existing is None:
            incident = Incident(
                **fields,
                is_duplicate=False,
                duplicate_reason=None,
                source_file=str(file_path),
                ingested_at=datetime.now(timezone.utc),
            )
            session.add(incident)
            rows_inserted += 1
        else:
            for key, value in fields.items():
                setattr(existing, key, value)
            existing.source_file = str(file_path)
            existing.ingested_at = datetime.now(timezone.utc)
            rows_updated += 1

    session.commit()

    return IngestResult(
        rows_read=rows_read,
        rows_inserted=rows_inserted,
        rows_updated=rows_updated,
        duplicates_flagged=0,
        unmapped_values=unmapped_values,
        pii_columns_dropped=list(PII_COLUMNS_SITREPS),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_sitreps_ingest.py -v`
Expected: PASS (8/8).

- [ ] **Step 5: Commit**

```bash
git add app/modules/sitreps/__init__.py app/modules/sitreps/ingest.py fixtures/sample_sitrep_small.csv tests/test_sitreps_ingest.py
git commit -m "sitreps: add CSV ingest for corp-entered incidents, reusing the shared Incident shape"
```

---

### Task 3: `SitrepModule` — a `DataModule` delegating to survey123's metric functions

**Files:**
- Create: `app/modules/sitreps/module.py`
- Test: `tests/test_sitreps_module.py`

**Interfaces:**
- Consumes: `app.modules.survey123.metrics.METRIC_FUNCTIONS`, `METRIC_SPECS` (Task 1's source-aware versions), `app.modules.sitreps.ingest.ingest_sitrep_csv` (Task 2).
- Produces: `sitrep_module: SitrepModule` (singleton, `.name == "sitreps"`) conforming to `DataModule` (`app/core/registry.py`) — Task 4 registers this in `app/__init__.py`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_sitreps_module.py`:

```python
from pathlib import Path

import pytest
from sqlalchemy.orm import sessionmaker

from app.db import Base, make_engine
from app.modules.sitreps.ingest import ingest_sitrep_csv
from app.modules.sitreps.module import sitrep_module
from app.modules.survey123.ingest import ingest_csv
from app.modules.survey123.module import survey123_module

SITREP_FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample_sitrep_small.csv"
SURVEY123_FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample_small.csv"
CORPORATION = "diego_martin_regional_corporati"


def make_session(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


def test_sitrep_module_has_correct_name():
    assert sitrep_module.name == "sitreps"


def test_sitrep_module_ingest_raises_not_implemented():
    with pytest.raises(NotImplementedError, match="sitreps"):
        sitrep_module.ingest(SITREP_FIXTURE)


def test_sitrep_module_list_metrics_reports_module_as_sitreps():
    specs = sitrep_module.list_metrics()

    assert len(specs) == 9
    assert all(spec.module == "sitreps" for spec in specs)
    assert {spec.name for spec in specs} == {spec.name for spec in survey123_module.list_metrics()}


def test_sitrep_module_run_metric_only_counts_sitrep_rows(tmp_path):
    session = make_session(tmp_path)
    ingest_csv(SURVEY123_FIXTURE, session, salt="test-salt")
    ingest_sitrep_csv(SITREP_FIXTURE, CORPORATION, session)

    facts = sitrep_module.run_metric("incident_count", {}, session)

    assert facts[0].value == 3
    assert facts[0].citation.module == "sitreps"
    assert facts[0].citation.cid == "sitreps-incident_count-0"


def test_survey123_module_run_metric_only_counts_survey123_rows_when_sitreps_also_present(tmp_path):
    session = make_session(tmp_path)
    ingest_csv(SURVEY123_FIXTURE, session, salt="test-salt")
    ingest_sitrep_csv(SITREP_FIXTURE, CORPORATION, session)

    facts = survey123_module.run_metric("incident_count", {}, session)

    assert facts[0].value == 19
    assert facts[0].citation.module == "survey123"


def test_sitrep_module_run_metric_raises_for_unknown_metric(tmp_path):
    session = make_session(tmp_path)

    with pytest.raises(ValueError, match="not_a_real_metric"):
        sitrep_module.run_metric("not_a_real_metric", {}, session)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_sitreps_module.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.modules.sitreps.module'`.

- [ ] **Step 3: Implement**

Create `app/modules/sitreps/module.py`:

```python
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.contracts import Fact, IngestResult, MetricSpec
from app.modules.survey123.metrics import METRIC_FUNCTIONS, METRIC_SPECS


class SitrepModule:
    name = "sitreps"

    def ingest(self, file_path: Path) -> IngestResult:
        raise NotImplementedError(
            "sitreps ingestion requires a corporation argument; use the "
            "'ingest sitreps <corporation> <file>' CLI command instead"
        )

    def list_metrics(self) -> list[MetricSpec]:
        return [spec.model_copy(update={"module": "sitreps"}) for spec in METRIC_SPECS]

    def run_metric(self, name: str, params: dict, session: Session) -> list[Fact]:
        fn = METRIC_FUNCTIONS.get(name)
        if fn is None:
            raise ValueError(f"unknown metric for sitreps: {name}")
        return fn({**params, "source": "sitreps"}, session)


sitrep_module = SitrepModule()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_sitreps_module.py -v`
Expected: PASS (6/6). This is the key correctness proof of the whole plan — `test_sitrep_module_run_metric_only_counts_sitrep_rows` and `test_survey123_module_run_metric_only_counts_survey123_rows_when_sitreps_also_present` prove the two sources stay isolated in the shared table.

- [ ] **Step 5: Commit**

```bash
git add app/modules/sitreps/module.py tests/test_sitreps_module.py
git commit -m "sitreps: add SitrepModule, delegating to survey123's metric functions with source=sitreps"
```

---

### Task 4: Wire `sitreps` into the CLI and app registration

**Files:**
- Modify: `cli.py`, `app/__init__.py`, `tests/test_survey123_module.py`
- Test: `tests/test_cli_sitreps.py`

**Interfaces:**
- Consumes: `ingest_sitrep_csv` (Task 2), `sitrep_module` (Task 3).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_cli_sitreps.py`:

```python
from pathlib import Path

from typer.testing import CliRunner

from app.core.registry import reset_registry
from app.db import Base, engine as db_engine
from cli import app

runner = CliRunner()

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "sample_sitrep_small.csv"
DEV_DB_PATH = Path(__file__).parent.parent / "dev.db"


def _reset_state():
    reset_registry()
    db_engine.dispose()
    if DEV_DB_PATH.exists():
        DEV_DB_PATH.unlink()


def test_ingest_sitreps_command_reports_summary():
    _reset_state()
    Base.metadata.create_all(db_engine)

    try:
        result = runner.invoke(
            app, ["ingest", "sitreps", "diego_martin_regional_corporati", str(FIXTURE_PATH)]
        )

        assert result.exit_code == 0, result.stdout
        assert "rows_read=3" in result.stdout
        assert "rows_inserted=3" in result.stdout
        assert "pii_columns_dropped=" in result.stdout
    finally:
        _reset_state()


def test_ingest_sitreps_command_flags_unmapped_corporation():
    _reset_state()
    Base.metadata.create_all(db_engine)

    try:
        result = runner.invoke(app, ["ingest", "sitreps", "Not A Real Corp", str(FIXTURE_PATH)])

        assert result.exit_code == 0, result.stdout
        assert "Not A Real Corp" in result.stdout
    finally:
        _reset_state()
```

Update `tests/test_survey123_module.py`'s `test_modules_endpoint_includes_survey123_after_create_app` (it currently asserts exactly one module is registered — this must change now that `sitreps` is also registered by `create_app()`):

```python
def test_modules_endpoint_includes_survey123_after_create_app():
    app = create_app()
    client = TestClient(app)

    response = client.get("/modules")

    assert response.status_code == 200
    body = response.json()
    assert {m["name"] for m in body} == {"survey123", "sitreps"}
    survey123_entry = next(m for m in body if m["name"] == "survey123")
    assert len(survey123_entry["metrics"]) == 9
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_cli_sitreps.py tests/test_survey123_module.py -v`
Expected: FAIL — `Error: No such command 'sitreps'` for the CLI tests, and `AssertionError: {'survey123'} != {'survey123', 'sitreps'}` for the updated `test_modules_endpoint_includes_survey123_after_create_app`.

- [ ] **Step 3: Implement**

In `cli.py`, add the import (alongside the existing `app.modules.survey123.module` import) and a new command in `ingest_app`:

```python
from app.modules.sitreps.ingest import ingest_sitrep_csv
from app.modules.sitreps.module import sitrep_module
```

```python
@ingest_app.command("sitreps")
def ingest_sitreps(corporation: str, file_path: Path) -> None:
    session = SessionLocal()
    try:
        result = ingest_sitrep_csv(file_path, corporation, session)
    finally:
        session.close()

    typer.echo(f"rows_read={result.rows_read}")
    typer.echo(f"rows_inserted={result.rows_inserted}")
    typer.echo(f"rows_updated={result.rows_updated}")
    typer.echo(f"unmapped_values={result.unmapped_values}")
    typer.echo(f"pii_columns_dropped={result.pii_columns_dropped}")
```

In `app/__init__.py`, register `sitrep_module` alongside `survey123`:

```python
from fastapi import FastAPI

from app.api.ingest import router as ingest_router
from app.api.meta import router as meta_router
from app.api.reports import router as reports_router
from app.core.registry import register_module
from app.modules.sitreps.module import sitrep_module
from app.modules.survey123.module import get_survey123_module


def create_app() -> FastAPI:
    app = FastAPI(title="DMCU Reporting API")
    app.include_router(meta_router)
    app.include_router(reports_router)
    app.include_router(ingest_router)
    register_module(get_survey123_module())
    register_module(sitrep_module)
    return app


app = create_app()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_cli_sitreps.py tests/test_survey123_module.py -v`
Expected: PASS. Then run the full suite:

Run: `.venv/bin/python -m pytest -q`
Expected: all tests passing, zero regressions (baseline count from Task 1's end + this task's new tests).

- [ ] **Step 5: Commit**

```bash
git add cli.py app/__init__.py tests/test_cli_sitreps.py tests/test_survey123_module.py
git commit -m "sitreps: wire sitreps ingest into the CLI and register the module alongside survey123"
```

---

## Self-Review

**Spec coverage:** Incident-shape reuse (confirmed decision) → Tasks 1-3, no new model file, shared `Incident` table. Corp-friendly manual entry / Google-Sheets-exportable CSV → Task 2. PII dropped, never stored → Task 2 (`PII_COLUMNS_SITREPS`, verified by `test_ingest_sitrep_csv_drops_pii_never_stores_it`). Real-time/authoritative corp data marked validated immediately (no separate validation workflow, unlike survey123's citizen-submission pending state) → Task 2 (`"validation_status": "validated"` unconditionally). Citations must distinguish real-time corp data from lagged survey123 data → Task 1 (`build_citation`'s `module` field). Explicitly deferred: status/preparedness log table, new report templates, live Sheets API — stated in Global Constraints, not attempted.

**Placeholder scan:** no TBD/TODO; every step has complete code; `SitrepModule.ingest`'s `NotImplementedError` is a deliberate, documented design choice (mirrors `McpDataModule.ingest`'s existing precedent), not a stub.

**Type consistency:** `ingest_sitrep_csv(file_path, corporation_raw, session) -> IngestResult` matches between Task 2's definition and Task 4's CLI call site. `sitrep_module`/`SitrepModule` naming matches between Task 3's definition and Task 4's import. `build_citation`'s signature is unchanged across all call sites (no caller needed edits) — verified by checking every existing metric function in `metrics.py` still calls it the same way.

---

Plan complete and saved to `docs/superpowers/plans/2026-07-18-sitreps-module.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
