# DMCU Reporting — Step 3: Survey123 Metrics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement all 9 `PLAN.md` §4.4 metrics for the `survey123` module as pure functions of `(params, session)` returning cited `Fact`s, and wire them into `Survey123Module.list_metrics()`/`run_metric()` so the registry (Step 1) and the module (Step 2) are finally fully connected end-to-end.

**Architecture:** `app/modules/survey123/metrics.py` holds shared query-building/citation helpers plus the 9 metric functions, built incrementally across this plan's tasks (same pattern Step 2 used for `ingest.py`: one file, extended task by task, never restructured). Every metric excludes `is_duplicate=True` rows by default (`PLAN.md` §4.1) and only counts `validation_status="validated"` rows unless `include_pending=True` is passed — **two metrics are deliberate, documented exceptions** to that second rule (see Global Constraints).

**Tech Stack:** Same as Steps 1–2 (Python 3.13, SQLAlchemy 2.0-style, Pydantic v2). No new dependencies.

## Global Constraints

- Everything in Steps 1–2's plans still applies (SQLAlchemy 2.0 style only, `apps/backend/` location, PII policy).
- Every metric is a pure function of `(params, session)` — no hidden state (`PLAN.md` §7). All 9 metric functions have the signature `(params: dict, session: Session) -> list[Fact]`.
- Shared params contract across all 9 metrics (`PLAN.md` §4.4): `{corporation?: str, community?: str, date_from?: str, date_to?: str, include_pending?: bool = False}`. `date_from`/`date_to` arrive as ISO date strings (e.g. `"2024-06-15"`) and are parsed via `datetime.fromisoformat`.
- **Default filtering rule (applies to 7 of 9 metrics):** exclude `is_duplicate=True` rows always; include only `validation_status="validated"` rows unless `include_pending=True`.
- **Exception 1 — `homes_affected_count`:** `PLAN.md` §4.4 explicitly requires this metric's shape to be "breakdown validated vs pending" — meaning the breakdown must always show the true validated/pending split regardless of `include_pending`, while the headline `value` still respects the toggle (validated-only by default, validated+pending when `include_pending=True`).
- **Exception 2 — `data_coverage`:** its entire purpose is reporting `% validated` and `% duplicates flagged` per corporation (`PLAN.md` §4.4) — computing that requires seeing ALL rows (both validation statuses AND flagged duplicates). This metric does not apply the duplicate-exclusion or validated-only filters at all; `include_pending` has no effect on it.
- `incidents_by_corporation` and `data_coverage` must include a `(no corporation recorded)` bucket for blank-corporation rows (`PLAN.md` §4.4 point 2, and Step 3's DoD in `PLAN.md` §6: "blank-corporation bucket appears").
- Citation `record_ids` are capped at 200 contributing `GlobalID`s; above that cap, `record_ids` is `None` (count + `query_ref` remain the only trace) — `PLAN.md` §4.4: "contributing record GlobalIDs (capped at 200 ids; above that, count + query_ref only)".
- No citation-id-sequencing engine exists yet (that's `PLAN.md` §5.4, a later step) — each metric function assigns its own locally-deterministic `cid` (`f"survey123-{metric_name}-{index}"`, `index` being the 0-based position within that metric call's returned `Fact` list). A future engine may relabel these when assembling a `FactTable`; that is out of scope here.
- All expected values in this plan's tests were computed by actually running the metric logic against the real `apps/backend/fixtures/sample_small.csv` fixture (30 rows, from Step 2) during planning — not hand-derived arithmetic. Trust them exactly as given.
- Definition of done for this plan (`PLAN.md` §6 Step 3): every metric returns correctly cited `Facts`; `include_pending` toggles verification handling; the blank-corporation bucket appears; all tests pass.

---

### Task 1: Shared metric helpers

**Files:**
- Create: `apps/backend/app/modules/survey123/metrics.py`
- Create: `apps/backend/tests/test_metrics_helpers.py`

**Interfaces:**
- Consumes: `app.modules.survey123.models.Incident` (Step 2), `app.core.contracts.Citation`/`Fact` (Step 1).
- Produces (all in `app.modules.survey123.metrics`): `parse_date_param(value: str | datetime | None) -> datetime | None`, `build_window_label(date_from, date_to) -> str`, `build_scope(params: dict, **extra: str) -> dict[str, str]`, `build_query_ref(metric_name: str, params: dict) -> str`, `determine_verification(statuses: list[str]) -> Literal["validated", "pending", "mixed", "n/a"]`, `build_citation(metric_name: str, index: int, params: dict, global_ids: list[str], description: str) -> Citation`, `apply_common_filters(stmt: Select, params: dict) -> Select` (corporation/community/date-range filters — `date_to` is treated as inclusive of the whole day, not just midnight, since real `event_date` values carry a time of day), `base_query(params: dict) -> Select` (`apply_common_filters` plus duplicate-exclusion and validated-only-unless-`include_pending`). Tasks 2–5 import and call all of these; Task 5's `data_coverage` calls `apply_common_filters` directly (not `base_query`, per the Global Constraints exception) so it still gets the shared corporation/community/date-range logic without the duplicate/validation filtering `base_query` adds on top — this shares the date-boundary fix between both query paths instead of duplicating it.

- [ ] **Step 1: Write the failing tests**

Create `apps/backend/tests/test_metrics_helpers.py`:

```python
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.db import Base, make_engine
from app.modules.survey123.metrics import (
    base_query,
    build_citation,
    build_query_ref,
    build_scope,
    build_window_label,
    determine_verification,
    parse_date_param,
)
from app.modules.survey123.models import Incident


def test_parse_date_param_none_is_none():
    assert parse_date_param(None) is None


def test_parse_date_param_string_parses_to_datetime():
    assert parse_date_param("2024-06-15") == datetime(2024, 6, 15)


def test_parse_date_param_datetime_passes_through():
    dt = datetime(2024, 6, 15, 12, 30)
    assert parse_date_param(dt) is dt


def test_build_window_label_no_dates_is_all():
    assert build_window_label(None, None) == "all"


def test_build_window_label_from_only():
    assert build_window_label("2024-06-15", None) == "2024-06-15..latest"


def test_build_window_label_both_dates():
    assert build_window_label("2024-06-01", "2024-06-30") == "2024-06-01..2024-06-30"


def test_build_scope_defaults_to_all():
    assert build_scope({}) == {"corporation": "all", "community": "all", "window": "all"}


def test_build_scope_reflects_filters():
    scope = build_scope({"corporation": "sangre_grande_regional_corporat", "community": "Sangre Grande", "date_from": "2024-06-01"})
    assert scope == {
        "corporation": "sangre_grande_regional_corporat",
        "community": "Sangre Grande",
        "window": "2024-06-01..latest",
    }


def test_build_scope_extra_kwargs_override():
    scope = build_scope({}, category="injuries")
    assert scope["category"] == "injuries"
    assert scope["corporation"] == "all"


def test_build_query_ref_is_deterministic_and_excludes_none_values():
    ref_a = build_query_ref("incident_count", {"corporation": "sangre_grande_regional_corporat", "community": None, "date_from": None, "date_to": None, "include_pending": False})
    ref_b = build_query_ref("incident_count", {"corporation": "sangre_grande_regional_corporat"})
    assert ref_a == ref_b
    assert "community" not in ref_a


def test_build_query_ref_differs_for_different_params():
    ref_a = build_query_ref("incident_count", {"corporation": "sangre_grande_regional_corporat"})
    ref_b = build_query_ref("incident_count", {"corporation": "san_fernando_city_corporation"})
    assert ref_a != ref_b


def test_determine_verification_all_validated():
    assert determine_verification(["validated", "validated"]) == "validated"


def test_determine_verification_all_pending():
    assert determine_verification(["pending", "pending"]) == "pending"


def test_determine_verification_mixed():
    assert determine_verification(["validated", "pending"]) == "mixed"


def test_determine_verification_empty_is_na():
    assert determine_verification([]) == "n/a"


def test_build_citation_keeps_record_ids_at_or_below_200():
    global_ids = [f"GUID-{i:04d}" for i in range(200)]

    citation = build_citation("incident_count", 0, {}, global_ids, "test description")

    assert citation.record_ids is not None
    assert len(citation.record_ids) == 200
    assert citation.cid == "survey123-incident_count-0"
    assert citation.module == "survey123"
    assert citation.description == "test description"


def test_build_citation_caps_record_ids_above_200():
    global_ids = [f"GUID-{i:04d}" for i in range(250)]

    citation = build_citation("incident_count", 0, {}, global_ids, "test description")

    assert citation.record_ids is None


def make_session(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


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
        action_taken=None,
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
        source_file="test.csv",
        ingested_at=datetime(2024, 6, 1),
    )
    defaults.update(overrides)
    return Incident(**defaults)


def test_base_query_excludes_duplicates(tmp_path):
    session = make_session(tmp_path)
    session.add(make_incident(global_id="G1", is_duplicate=False))
    session.add(make_incident(global_id="G2", is_duplicate=True))
    session.commit()

    rows = session.execute(base_query({})).scalars().all()

    assert [r.global_id for r in rows] == ["G1"]


def test_base_query_excludes_pending_by_default(tmp_path):
    session = make_session(tmp_path)
    session.add(make_incident(global_id="G1", validation_status="validated"))
    session.add(make_incident(global_id="G2", validation_status="pending"))
    session.commit()

    rows = session.execute(base_query({})).scalars().all()

    assert [r.global_id for r in rows] == ["G1"]


def test_base_query_include_pending_true_includes_both(tmp_path):
    session = make_session(tmp_path)
    session.add(make_incident(global_id="G1", validation_status="validated"))
    session.add(make_incident(global_id="G2", validation_status="pending"))
    session.commit()

    rows = session.execute(base_query({"include_pending": True})).scalars().all()

    assert sorted(r.global_id for r in rows) == ["G1", "G2"]


def test_base_query_filters_by_corporation(tmp_path):
    session = make_session(tmp_path)
    session.add(make_incident(global_id="G1", corporation="sangre_grande_regional_corporat"))
    session.add(make_incident(global_id="G2", corporation="san_fernando_city_corporation"))
    session.commit()

    rows = session.execute(base_query({"corporation": "san_fernando_city_corporation"})).scalars().all()

    assert [r.global_id for r in rows] == ["G2"]


def test_base_query_filters_by_date_range(tmp_path):
    session = make_session(tmp_path)
    session.add(make_incident(global_id="G1", event_date=datetime(2024, 6, 1)))
    session.add(make_incident(global_id="G2", event_date=datetime(2024, 6, 20)))
    session.commit()

    rows = session.execute(base_query({"date_from": "2024-06-10"})).scalars().all()

    assert [r.global_id for r in rows] == ["G2"]


def test_base_query_date_to_is_inclusive_of_the_whole_day(tmp_path):
    # Real Survey123 exports carry a time of day on event_date (e.g. 14:35:00),
    # not just midnight — a naive `event_date <= date_to` (parsed to midnight)
    # would silently drop every incident that happened later on the last day
    # of the window. This locks in that date_to must include the whole day.
    session = make_session(tmp_path)
    session.add(make_incident(global_id="G1", event_date=datetime(2024, 6, 30, 14, 35, 0)))
    session.add(make_incident(global_id="G2", event_date=datetime(2024, 7, 1, 0, 0, 0)))
    session.commit()

    rows = session.execute(base_query({"date_to": "2024-06-30"})).scalars().all()

    assert [r.global_id for r in rows] == ["G1"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd apps/backend
uv run pytest tests/test_metrics_helpers.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.modules.survey123.metrics'`.

- [ ] **Step 3: Implement `app/modules/survey123/metrics.py`**

```python
from datetime import datetime, timedelta
from typing import Literal

from sqlalchemy import Select, select

from app.core.contracts import Citation
from app.modules.survey123.models import Incident


def parse_date_param(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)


def build_window_label(date_from: str | None, date_to: str | None) -> str:
    if date_from is None and date_to is None:
        return "all"
    from_label = date_from or "earliest"
    to_label = date_to or "latest"
    return f"{from_label}..{to_label}"


def build_scope(params: dict, **extra: str) -> dict[str, str]:
    scope = {
        "corporation": params.get("corporation") or "all",
        "community": params.get("community") or "all",
        "window": build_window_label(params.get("date_from"), params.get("date_to")),
    }
    scope.update(extra)
    return scope


def build_query_ref(metric_name: str, params: dict) -> str:
    parts = [f"{k}={v}" for k, v in sorted(params.items()) if v is not None and v is not False]
    return f"{metric_name}(" + ", ".join(parts) + ")"


def determine_verification(statuses: list[str]) -> Literal["validated", "pending", "mixed", "n/a"]:
    unique = set(statuses)
    if not unique:
        return "n/a"
    if unique == {"validated"}:
        return "validated"
    if unique == {"pending"}:
        return "pending"
    return "mixed"


def build_citation(metric_name: str, index: int, params: dict, global_ids: list[str], description: str) -> Citation:
    ordered = sorted(global_ids)
    record_ids = ordered[:200] if len(ordered) <= 200 else None
    return Citation(
        cid=f"survey123-{metric_name}-{index}",
        module="survey123",
        description=description,
        query_ref=build_query_ref(metric_name, params),
        record_ids=record_ids,
        as_of=datetime.now(),
    )


def apply_common_filters(stmt: Select, params: dict) -> Select:
    if params.get("corporation") is not None:
        stmt = stmt.where(Incident.corporation == params["corporation"])
    if params.get("community") is not None:
        stmt = stmt.where(Incident.community == params["community"])
    date_from = parse_date_param(params.get("date_from"))
    if date_from is not None:
        stmt = stmt.where(Incident.event_date >= date_from)
    date_to = parse_date_param(params.get("date_to"))
    if date_to is not None:
        # date_to arrives as a date-only ISO string (e.g. "2024-06-30"), which
        # parse_date_param parses to midnight. Real event_date values carry a
        # time of day, so "<= midnight" would silently exclude every incident
        # that occurred later that same day. Compare against the start of the
        # NEXT day instead, so date_to is inclusive of the whole day.
        stmt = stmt.where(Incident.event_date < date_to + timedelta(days=1))
    return stmt


def base_query(params: dict) -> Select:
    stmt = select(Incident).where(Incident.is_duplicate.is_(False))
    stmt = apply_common_filters(stmt, params)
    if not params.get("include_pending", False):
        stmt = stmt.where(Incident.validation_status == "validated")
    return stmt
```

**Note on `as_of`:** use `datetime.now()` (naive, local process time) here — this matches the naive `datetime` columns already used throughout `Incident` (Step 2 stores `event_date`/`creation_date`/etc. as naive `DateTime`, not timezone-aware) and Step 1's `Fact`/`Citation` contracts, which declare `as_of: datetime` without a timezone constraint. Do not introduce `timezone.utc` here — it would make `Citation.as_of` inconsistent with every other datetime in this codebase.

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd apps/backend
uv run pytest tests/test_metrics_helpers.py -v
```

Expected: `23 passed`.

- [ ] **Step 5: Run the full suite**

```bash
cd apps/backend
uv run pytest -v
```

Expected: `85 passed`.

- [ ] **Step 6: Commit**

```bash
git add apps/backend/app/modules/survey123/metrics.py apps/backend/tests/test_metrics_helpers.py
git commit -m "backend: add survey123 metric query/citation helpers"
```

---

### Task 2: `incident_count` and `incidents_by_corporation`

**Files:**
- Modify: `apps/backend/app/modules/survey123/metrics.py` (append)
- Create: `apps/backend/tests/test_metrics_incident_count.py`

**Interfaces:**
- Consumes: `base_query`, `build_scope`, `build_citation`, `determine_verification` (Task 1); `Fact` (Step 1).
- Produces: `incident_count(params: dict, session: Session) -> list[Fact]` (always returns exactly 1 `Fact`), `incidents_by_corporation(params: dict, session: Session) -> list[Fact]` (always returns exactly 1 `Fact`, with a `(no corporation recorded)` breakdown bucket for blanks). Task 6 registers both in `METRIC_FUNCTIONS`.
- All expected values below were computed by actually running this exact logic against `apps/backend/fixtures/sample_small.csv` during planning.

- [ ] **Step 1: Write the failing tests**

Create `apps/backend/tests/test_metrics_incident_count.py`:

```python
from pathlib import Path

from sqlalchemy.orm import sessionmaker

from app.db import Base, make_engine
from app.modules.survey123.ingest import ingest_csv
from app.modules.survey123.metrics import incident_count, incidents_by_corporation

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "sample_small.csv"


def make_session(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    ingest_csv(FIXTURE_PATH, session, salt="test-salt")
    return session


def test_incident_count_default_validated_only(tmp_path):
    session = make_session(tmp_path)

    facts = incident_count({}, session)

    assert len(facts) == 1
    fact = facts[0]
    assert fact.metric == "incident_count"
    assert fact.value == 19
    assert fact.unit == "incidents"
    assert fact.breakdown == {
        "flooding_": 7,
        "other": 2,
        "landslide": 4,
        "fallen_tree": 2,
        "over grown tree": 2,
        "fire": 1,
        "unmapped": 1,
    }
    assert fact.verification == "validated"
    assert fact.citation.cid == "survey123-incident_count-0"
    assert fact.citation.record_ids is not None
    assert len(fact.citation.record_ids) == 19


def test_incident_count_include_pending_widens_result(tmp_path):
    session = make_session(tmp_path)

    facts = incident_count({"include_pending": True}, session)

    fact = facts[0]
    assert fact.value == 26
    assert fact.breakdown == {
        "flooding_": 7,
        "fire": 4,
        "other": 2,
        "landslide": 4,
        "blown_off_roof": 2,
        "fallen_tree": 2,
        "earthquake": 2,
        "over grown tree": 2,
        "unmapped": 1,
    }
    assert fact.verification == "mixed"


def test_incident_count_filters_by_corporation(tmp_path):
    session = make_session(tmp_path)

    facts = incident_count({"corporation": "sangre_grande_regional_corporat"}, session)

    fact = facts[0]
    assert fact.value == 10
    assert fact.breakdown == {"flooding_": 7, "other": 2, "unmapped": 1}
    assert fact.scope["corporation"] == "sangre_grande_regional_corporat"


def test_incident_count_filters_by_community(tmp_path):
    session = make_session(tmp_path)

    facts = incident_count({"community": "San Fernando"}, session)

    fact = facts[0]
    assert fact.value == 6
    assert fact.breakdown == {"landslide": 4, "fallen_tree": 2}


def test_incident_count_filters_by_date_from(tmp_path):
    session = make_session(tmp_path)

    facts = incident_count({"date_from": "2024-06-15"}, session)

    fact = facts[0]
    assert fact.value == 8
    assert fact.scope["window"] == "2024-06-15..latest"


def test_incidents_by_corporation_default_includes_blank_bucket(tmp_path):
    session = make_session(tmp_path)

    facts = incidents_by_corporation({}, session)

    assert len(facts) == 1
    fact = facts[0]
    assert fact.metric == "incidents_by_corporation"
    assert fact.value == 19
    assert fact.breakdown == {
        "sangre_grande_regional_corporat": 10,
        "san_fernando_city_corporation": 6,
        "(no corporation recorded)": 2,
        "unmapped": 1,
    }
    assert fact.verification == "validated"


def test_incidents_by_corporation_include_pending_widens_blank_bucket(tmp_path):
    session = make_session(tmp_path)

    facts = incidents_by_corporation({"include_pending": True}, session)

    fact = facts[0]
    assert fact.value == 26
    assert fact.breakdown == {
        "sangre_grande_regional_corporat": 13,
        "san_fernando_city_corporation": 8,
        "(no corporation recorded)": 4,
        "unmapped": 1,
    }
    assert fact.verification == "mixed"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd apps/backend
uv run pytest tests/test_metrics_incident_count.py -v
```

Expected: FAIL — `ImportError: cannot import name 'incident_count' from 'app.modules.survey123.metrics'`.

- [ ] **Step 3: Append to `app/modules/survey123/metrics.py`**

Add these imports to the top of the file (alongside the existing ones from Task 1):

```python
from sqlalchemy.orm import Session

from app.core.contracts import Fact
```

Append at the end of the file:

```python
def incident_count(params: dict, session: Session) -> list[Fact]:
    rows = session.execute(base_query(params)).scalars().all()

    breakdown: dict[str, int] = {}
    for r in rows:
        key = r.incident_type or "(no incident type recorded)"
        breakdown[key] = breakdown.get(key, 0) + 1

    global_ids = [r.global_id for r in rows]
    citation = build_citation(
        "incident_count",
        0,
        params,
        global_ids,
        f"Survey123 incident count, {build_window_label(params.get('date_from'), params.get('date_to'))}",
    )

    return [
        Fact(
            metric="incident_count",
            value=len(rows),
            unit="incidents",
            scope=build_scope(params),
            breakdown=breakdown or None,
            verification=determine_verification([r.validation_status for r in rows]),
            citation=citation,
        )
    ]


def incidents_by_corporation(params: dict, session: Session) -> list[Fact]:
    rows = session.execute(base_query(params)).scalars().all()

    breakdown: dict[str, int] = {}
    for r in rows:
        key = r.corporation or "(no corporation recorded)"
        breakdown[key] = breakdown.get(key, 0) + 1

    global_ids = [r.global_id for r in rows]
    citation = build_citation(
        "incidents_by_corporation",
        0,
        params,
        global_ids,
        f"Survey123 incidents by corporation, {build_window_label(params.get('date_from'), params.get('date_to'))}",
    )

    return [
        Fact(
            metric="incidents_by_corporation",
            value=len(rows),
            unit="incidents",
            scope=build_scope(params),
            breakdown=breakdown or None,
            verification=determine_verification([r.validation_status for r in rows]),
            citation=citation,
        )
    ]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd apps/backend
uv run pytest tests/test_metrics_incident_count.py -v
```

Expected: `7 passed`.

- [ ] **Step 5: Run the full suite**

```bash
cd apps/backend
uv run pytest -v
```

Expected: `92 passed`.

- [ ] **Step 6: Commit**

```bash
git add apps/backend/app/modules/survey123/metrics.py apps/backend/tests/test_metrics_incident_count.py
git commit -m "backend: add incident_count and incidents_by_corporation metrics"
```

---

### Task 3: `homes_affected_count` and `casualty_summary`

**Files:**
- Modify: `apps/backend/app/modules/survey123/metrics.py` (append)
- Create: `apps/backend/tests/test_metrics_homes_and_casualties.py`

**Interfaces:**
- Consumes: `base_query`, `build_scope`, `build_citation`, `determine_verification` (Task 1).
- Produces: `homes_affected_count(params, session) -> list[Fact]` (1 `Fact`; breakdown always shows both `validated`/`pending` counts regardless of `include_pending`, per the Global Constraints exception), `casualty_summary(params, session) -> list[Fact]` (always exactly 2 `Fact`s: one `scope={"category": "injuries", ...}`, one `scope={"category": "deaths", ...}` — kept separate because conflating an injury count and a death count into one number would misrepresent the report).
- A row counts as "home affected" when `building_damage` is non-empty (after stripping whitespace) OR `incident_type` is one of `{"flooding_", "fire", "blown_off_roof"}` — this is `PLAN.md` §4.4 point 3, verbatim.

- [ ] **Step 1: Write the failing tests**

Create `apps/backend/tests/test_metrics_homes_and_casualties.py`:

```python
from pathlib import Path

from sqlalchemy.orm import sessionmaker

from app.db import Base, make_engine
from app.modules.survey123.ingest import ingest_csv
from app.modules.survey123.metrics import casualty_summary, homes_affected_count

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "sample_small.csv"


def make_session(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    ingest_csv(FIXTURE_PATH, session, salt="test-salt")
    return session


def test_homes_affected_count_default_is_validated_only_value_with_full_breakdown(tmp_path):
    session = make_session(tmp_path)

    facts = homes_affected_count({}, session)

    assert len(facts) == 1
    fact = facts[0]
    assert fact.metric == "homes_affected_count"
    assert fact.value == 12
    assert fact.breakdown == {"validated": 12, "pending": 7}
    assert fact.verification == "validated"
    assert len(fact.citation.record_ids) == 12


def test_homes_affected_count_include_pending_widens_value_but_not_breakdown(tmp_path):
    session = make_session(tmp_path)

    facts = homes_affected_count({"include_pending": True}, session)

    fact = facts[0]
    assert fact.value == 19
    assert fact.breakdown == {"validated": 12, "pending": 7}
    assert fact.verification == "mixed"
    assert len(fact.citation.record_ids) == 19


def test_casualty_summary_default_returns_injuries_and_deaths_facts(tmp_path):
    session = make_session(tmp_path)

    facts = casualty_summary({}, session)

    assert len(facts) == 2
    injuries, deaths = facts
    assert injuries.metric == "casualty_summary"
    assert injuries.scope["category"] == "injuries"
    assert injuries.value == 2
    assert injuries.unit == "persons"
    assert injuries.breakdown is None
    assert injuries.citation.cid == "survey123-casualty_summary-0"

    assert deaths.scope["category"] == "deaths"
    assert deaths.value == 1
    assert deaths.citation.cid == "survey123-casualty_summary-1"


def test_casualty_summary_include_pending_widens_injuries_not_deaths(tmp_path):
    session = make_session(tmp_path)

    facts = casualty_summary({"include_pending": True}, session)

    injuries, deaths = facts
    assert injuries.value == 3
    assert injuries.verification == "mixed"
    assert deaths.value == 1
    assert deaths.verification == "validated"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd apps/backend
uv run pytest tests/test_metrics_homes_and_casualties.py -v
```

Expected: FAIL — `ImportError: cannot import name 'homes_affected_count' from 'app.modules.survey123.metrics'`.

- [ ] **Step 3: Append to `app/modules/survey123/metrics.py`**

```python
HOME_AFFECTING_INCIDENT_TYPES = {"flooding_", "fire", "blown_off_roof"}


def homes_affected_count(params: dict, session: Session) -> list[Fact]:
    full_params = dict(params)
    full_params["include_pending"] = True
    rows = session.execute(base_query(full_params)).scalars().all()

    affected = [
        r for r in rows if (r.building_damage or "").strip() or r.incident_type in HOME_AFFECTING_INCIDENT_TYPES
    ]

    breakdown = {"validated": 0, "pending": 0}
    for r in affected:
        if r.validation_status in breakdown:
            breakdown[r.validation_status] += 1

    include_pending = bool(params.get("include_pending", False))
    contributing = affected if include_pending else [r for r in affected if r.validation_status == "validated"]

    global_ids = [r.global_id for r in contributing]
    citation = build_citation(
        "homes_affected_count",
        0,
        params,
        global_ids,
        f"Survey123 homes affected, {build_window_label(params.get('date_from'), params.get('date_to'))}",
    )

    return [
        Fact(
            metric="homes_affected_count",
            value=len(contributing),
            unit="incidents",
            scope=build_scope(params),
            breakdown=breakdown,
            verification=determine_verification([r.validation_status for r in contributing]),
            citation=citation,
        )
    ]


def casualty_summary(params: dict, session: Session) -> list[Fact]:
    rows = session.execute(base_query(params)).scalars().all()

    injury_rows = [r for r in rows if (r.injuries_count or 0) > 0]
    death_rows = [r for r in rows if (r.deaths_count or 0) > 0]

    injuries_citation = build_citation(
        "casualty_summary",
        0,
        params,
        [r.global_id for r in injury_rows],
        f"Survey123 injuries, {build_window_label(params.get('date_from'), params.get('date_to'))}",
    )
    deaths_citation = build_citation(
        "casualty_summary",
        1,
        params,
        [r.global_id for r in death_rows],
        f"Survey123 deaths, {build_window_label(params.get('date_from'), params.get('date_to'))}",
    )

    return [
        Fact(
            metric="casualty_summary",
            value=sum(r.injuries_count or 0 for r in rows),
            unit="persons",
            scope=build_scope(params, category="injuries"),
            breakdown=None,
            verification=determine_verification([r.validation_status for r in injury_rows]),
            citation=injuries_citation,
        ),
        Fact(
            metric="casualty_summary",
            value=sum(r.deaths_count or 0 for r in rows),
            unit="persons",
            scope=build_scope(params, category="deaths"),
            breakdown=None,
            verification=determine_verification([r.validation_status for r in death_rows]),
            citation=deaths_citation,
        ),
    ]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd apps/backend
uv run pytest tests/test_metrics_homes_and_casualties.py -v
```

Expected: `4 passed`.

- [ ] **Step 5: Run the full suite**

```bash
cd apps/backend
uv run pytest -v
```

Expected: `96 passed`.

- [ ] **Step 6: Commit**

```bash
git add apps/backend/app/modules/survey123/metrics.py apps/backend/tests/test_metrics_homes_and_casualties.py
git commit -m "backend: add homes_affected_count and casualty_summary metrics"
```

---

### Task 4: `street_level_tally` and `relief_actions_summary`

**Files:**
- Modify: `apps/backend/app/modules/survey123/metrics.py` (append)
- Create: `apps/backend/tests/test_metrics_street_and_relief.py`

**Interfaces:**
- Consumes: `base_query`, `build_scope`, `build_citation`, `determine_verification` (Task 1).
- Produces: `street_level_tally(params, session) -> list[Fact]` (1 `Fact`; breakdown keyed by `f"{community} / {street}"`, `"(unknown community)"`/`"(unknown street)"` placeholders for blanks), `relief_actions_summary(params, session) -> list[Fact]` (1 `Fact`; breakdown is always the 4 fixed keys `relief_supplied`, `forwarded_to_agency`, `further_assessment_required`, `other` — note this uses the corrected flag names from Step 2, not `PLAN.md`'s original `shelter_relocation`; `value` is the count of DISTINCT incidents with at least one flag `True`, not the sum of the breakdown values, since one incident can carry multiple flags simultaneously).

- [ ] **Step 1: Write the failing tests**

Create `apps/backend/tests/test_metrics_street_and_relief.py`:

```python
from pathlib import Path

from sqlalchemy.orm import sessionmaker

from app.db import Base, make_engine
from app.modules.survey123.ingest import ingest_csv
from app.modules.survey123.metrics import relief_actions_summary, street_level_tally

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "sample_small.csv"


def make_session(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    ingest_csv(FIXTURE_PATH, session, salt="test-salt")
    return session


def test_street_level_tally_within_corporation(tmp_path):
    session = make_session(tmp_path)

    facts = street_level_tally({"corporation": "sangre_grande_regional_corporat"}, session)

    assert len(facts) == 1
    fact = facts[0]
    assert fact.metric == "street_level_tally"
    assert fact.value == 10
    assert fact.breakdown == {
        "Sangre Grande / 1 Flood Street": 1,
        "Sangre Grande / 2 Flood Street": 1,
        "Sangre Grande / 3 Flood Street": 1,
        "Sangre Grande / 4 Flood Street": 1,
        "Sangre Grande / 5 Flood Street": 1,
        "Sangre Grande / 9 Sinkhole Road": 1,
        "Sangre Grande / 10 Sinkhole Road": 1,
        "Sangre Grande / 24 Volcano Trace": 1,
        "Sangre Grande / 29 Big Family Trace": 1,
        "Sangre Grande / 30 Big Family Trace": 1,
    }
    assert fact.scope["corporation"] == "sangre_grande_regional_corporat"


def test_relief_actions_summary_default_counts_distinct_incidents_and_flags(tmp_path):
    session = make_session(tmp_path)

    facts = relief_actions_summary({}, session)

    assert len(facts) == 1
    fact = facts[0]
    assert fact.metric == "relief_actions_summary"
    assert fact.value == 16
    assert fact.breakdown == {
        "relief_supplied": 7,
        "forwarded_to_agency": 9,
        "further_assessment_required": 5,
        "other": 4,
    }
    assert fact.verification == "validated"
    assert len(fact.citation.record_ids) == 16


def test_relief_actions_summary_include_pending_widens_result(tmp_path):
    session = make_session(tmp_path)

    facts = relief_actions_summary({"include_pending": True}, session)

    fact = facts[0]
    assert fact.value == 21
    assert fact.breakdown == {
        "relief_supplied": 9,
        "forwarded_to_agency": 12,
        "further_assessment_required": 5,
        "other": 4,
    }
    assert fact.verification == "mixed"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd apps/backend
uv run pytest tests/test_metrics_street_and_relief.py -v
```

Expected: FAIL — `ImportError: cannot import name 'street_level_tally' from 'app.modules.survey123.metrics'`.

- [ ] **Step 3: Append to `app/modules/survey123/metrics.py`**

```python
FOLLOW_UP_FLAG_KEYS = ["relief_supplied", "forwarded_to_agency", "further_assessment_required", "other"]


def street_level_tally(params: dict, session: Session) -> list[Fact]:
    rows = session.execute(base_query(params)).scalars().all()

    breakdown: dict[str, int] = {}
    for r in rows:
        community = r.community or "(unknown community)"
        street = r.street or "(unknown street)"
        key = f"{community} / {street}"
        breakdown[key] = breakdown.get(key, 0) + 1

    global_ids = [r.global_id for r in rows]
    citation = build_citation(
        "street_level_tally",
        0,
        params,
        global_ids,
        f"Survey123 street-level tally, {build_window_label(params.get('date_from'), params.get('date_to'))}",
    )

    return [
        Fact(
            metric="street_level_tally",
            value=len(rows),
            unit="incidents",
            scope=build_scope(params),
            breakdown=breakdown or None,
            verification=determine_verification([r.validation_status for r in rows]),
            citation=citation,
        )
    ]


def relief_actions_summary(params: dict, session: Session) -> list[Fact]:
    rows = session.execute(base_query(params)).scalars().all()

    breakdown = {key: 0 for key in FOLLOW_UP_FLAG_KEYS}
    contributing_ids: set[str] = set()
    for r in rows:
        flags = r.follow_up_flags or {}
        any_flag = False
        for key in FOLLOW_UP_FLAG_KEYS:
            if flags.get(key):
                breakdown[key] += 1
                any_flag = True
        if any_flag:
            contributing_ids.add(r.global_id)

    global_ids = sorted(contributing_ids)
    contributing_rows = [r for r in rows if r.global_id in contributing_ids]
    citation = build_citation(
        "relief_actions_summary",
        0,
        params,
        global_ids,
        f"Survey123 relief actions, {build_window_label(params.get('date_from'), params.get('date_to'))}",
    )

    return [
        Fact(
            metric="relief_actions_summary",
            value=len(contributing_ids),
            unit="incidents",
            scope=build_scope(params),
            breakdown=breakdown,
            verification=determine_verification([r.validation_status for r in contributing_rows]),
            citation=citation,
        )
    ]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd apps/backend
uv run pytest tests/test_metrics_street_and_relief.py -v
```

Expected: `3 passed`.

- [ ] **Step 5: Run the full suite**

```bash
cd apps/backend
uv run pytest -v
```

Expected: `99 passed`.

- [ ] **Step 6: Commit**

```bash
git add apps/backend/app/modules/survey123/metrics.py apps/backend/tests/test_metrics_street_and_relief.py
git commit -m "backend: add street_level_tally and relief_actions_summary metrics"
```

---

### Task 5: `special_needs_count`, `estimated_damage_total`, and `data_coverage`

**Files:**
- Modify: `apps/backend/app/modules/survey123/metrics.py` (append)
- Create: `apps/backend/tests/test_metrics_needs_damage_coverage.py`

**Interfaces:**
- Consumes: `base_query`, `build_scope`, `build_citation`, `determine_verification`, `parse_date_param` (Task 1).
- Produces: `special_needs_count(params, session) -> list[Fact]` (1 `Fact`, `value` = sum of `special_needs_occupants`), `estimated_damage_total(params, session) -> list[Fact]` (1 `Fact`, `value` = sum of `estimated_damage_cost` as `float`, `breakdown={"records_reporting_cost": N, "records_total": M}` — the coverage caveat `PLAN.md` §4.4 point 8 requires, encoded as structured data rather than prose so the narration layer builds the caveat sentence, not the metric), `data_coverage(params, session) -> list[Fact]` (**one `Fact` per distinct corporation appearing in the filtered — but NOT duplicate/validation-status-filtered — row set**, sorted by corporation label; `value` = record count, `breakdown={"pct_validated": float, "pct_duplicates": float}` each rounded to 1 decimal place, `verification="n/a"` always, latest-record timestamp goes into the citation `description` text rather than a numeric field since `Fact.breakdown` values must be `int | float`).

- [ ] **Step 1: Write the failing tests**

Create `apps/backend/tests/test_metrics_needs_damage_coverage.py`:

```python
from pathlib import Path

from sqlalchemy.orm import sessionmaker

from app.db import Base, make_engine
from app.modules.survey123.ingest import ingest_csv
from app.modules.survey123.metrics import data_coverage, estimated_damage_total, special_needs_count

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "sample_small.csv"


def make_session(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    ingest_csv(FIXTURE_PATH, session, salt="test-salt")
    return session


def test_special_needs_count_default(tmp_path):
    session = make_session(tmp_path)

    facts = special_needs_count({}, session)

    assert len(facts) == 1
    fact = facts[0]
    assert fact.metric == "special_needs_count"
    assert fact.value == 2
    assert fact.unit == "persons"
    assert fact.breakdown is None


def test_special_needs_count_include_pending(tmp_path):
    session = make_session(tmp_path)

    facts = special_needs_count({"include_pending": True}, session)

    assert facts[0].value == 4


def test_estimated_damage_total_default_reports_coverage(tmp_path):
    session = make_session(tmp_path)

    facts = estimated_damage_total({}, session)

    assert len(facts) == 1
    fact = facts[0]
    assert fact.metric == "estimated_damage_total"
    assert fact.value == 98000.0
    assert fact.unit == "TTD"
    assert fact.breakdown == {"records_reporting_cost": 5, "records_total": 19}


def test_estimated_damage_total_include_pending_widens_denominator_only(tmp_path):
    session = make_session(tmp_path)

    facts = estimated_damage_total({"include_pending": True}, session)

    fact = facts[0]
    assert fact.value == 98000.0
    assert fact.breakdown == {"records_reporting_cost": 5, "records_total": 26}


def test_data_coverage_returns_one_fact_per_corporation_including_blank_bucket(tmp_path):
    session = make_session(tmp_path)

    facts = data_coverage({}, session)

    assert len(facts) == 4
    by_scope_corp = {f.scope["corporation"]: f for f in facts}

    assert by_scope_corp["(no corporation recorded)"].value == 4
    assert by_scope_corp["(no corporation recorded)"].breakdown == {"pct_validated": 50.0, "pct_duplicates": 0.0}

    assert by_scope_corp["san_fernando_city_corporation"].value == 10
    assert by_scope_corp["san_fernando_city_corporation"].breakdown == {"pct_validated": 80.0, "pct_duplicates": 20.0}

    assert by_scope_corp["sangre_grande_regional_corporat"].value == 15
    assert by_scope_corp["sangre_grande_regional_corporat"].breakdown == {"pct_validated": 66.7, "pct_duplicates": 13.3}

    assert by_scope_corp["unmapped"].value == 1
    assert by_scope_corp["unmapped"].breakdown == {"pct_validated": 100.0, "pct_duplicates": 0.0}

    for fact in facts:
        assert fact.metric == "data_coverage"
        assert fact.unit == "records"
        assert fact.verification == "n/a"


def test_data_coverage_includes_pending_and_duplicates_by_design(tmp_path):
    session = make_session(tmp_path)

    facts = data_coverage({}, session)
    total_records = sum(f.value for f in facts)

    assert total_records == 30
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd apps/backend
uv run pytest tests/test_metrics_needs_damage_coverage.py -v
```

Expected: FAIL — `ImportError: cannot import name 'special_needs_count' from 'app.modules.survey123.metrics'`.

- [ ] **Step 3: Append to `app/modules/survey123/metrics.py`**

Add this import to the top of the file (alongside the existing ones). Note `select` is already imported by Task 1 (`from sqlalchemy import Select, select`) — only `Decimal` is new here:

```python
from decimal import Decimal
```

Append at the end of the file:

```python
def special_needs_count(params: dict, session: Session) -> list[Fact]:
    rows = session.execute(base_query(params)).scalars().all()
    contributing = [r for r in rows if (r.special_needs_occupants or 0) > 0]

    global_ids = [r.global_id for r in contributing]
    citation = build_citation(
        "special_needs_count",
        0,
        params,
        global_ids,
        f"Survey123 special needs occupants, {build_window_label(params.get('date_from'), params.get('date_to'))}",
    )

    return [
        Fact(
            metric="special_needs_count",
            value=sum(r.special_needs_occupants or 0 for r in rows),
            unit="persons",
            scope=build_scope(params),
            breakdown=None,
            verification=determine_verification([r.validation_status for r in contributing]),
            citation=citation,
        )
    ]


def estimated_damage_total(params: dict, session: Session) -> list[Fact]:
    rows = session.execute(base_query(params)).scalars().all()
    with_cost = [r for r in rows if r.estimated_damage_cost is not None]

    total = sum((r.estimated_damage_cost for r in with_cost), start=Decimal("0"))
    global_ids = [r.global_id for r in with_cost]
    citation = build_citation(
        "estimated_damage_total",
        0,
        params,
        global_ids,
        f"Survey123 estimated damage cost, {build_window_label(params.get('date_from'), params.get('date_to'))}",
    )

    return [
        Fact(
            metric="estimated_damage_total",
            value=float(total),
            unit="TTD",
            scope=build_scope(params),
            breakdown={"records_reporting_cost": len(with_cost), "records_total": len(rows)},
            verification=determine_verification([r.validation_status for r in with_cost]),
            citation=citation,
        )
    ]


def data_coverage(params: dict, session: Session) -> list[Fact]:
    stmt = apply_common_filters(select(Incident), params)

    rows = session.execute(stmt).scalars().all()

    by_corp: dict[str, list[Incident]] = {}
    for r in rows:
        key = r.corporation or "(no corporation recorded)"
        by_corp.setdefault(key, []).append(r)

    facts: list[Fact] = []
    for index, (corp_label, corp_rows) in enumerate(sorted(by_corp.items())):
        n = len(corp_rows)
        pct_validated = round(100.0 * sum(1 for r in corp_rows if r.validation_status == "validated") / n, 1)
        pct_duplicates = round(100.0 * sum(1 for r in corp_rows if r.is_duplicate) / n, 1)
        latest = max((r.creation_date for r in corp_rows if r.creation_date is not None), default=None)
        latest_label = latest.isoformat() if latest is not None else "unknown"
        global_ids = [r.global_id for r in corp_rows]
        citation = build_citation(
            "data_coverage",
            index,
            params,
            global_ids,
            f"Survey123 data coverage for {corp_label}, latest record as of {latest_label}",
        )
        facts.append(
            Fact(
                metric="data_coverage",
                value=n,
                unit="records",
                scope=build_scope(params, corporation=corp_label),
                breakdown={"pct_validated": pct_validated, "pct_duplicates": pct_duplicates},
                verification="n/a",
                citation=citation,
            )
        )
    return facts
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd apps/backend
uv run pytest tests/test_metrics_needs_damage_coverage.py -v
```

Expected: `6 passed`.

- [ ] **Step 5: Run the full suite**

```bash
cd apps/backend
uv run pytest -v
```

Expected: `105 passed`.

- [ ] **Step 6: Commit**

```bash
git add apps/backend/app/modules/survey123/metrics.py apps/backend/tests/test_metrics_needs_damage_coverage.py
git commit -m "backend: add special_needs_count, estimated_damage_total, and data_coverage metrics"
```

---

### Task 6: Wire metrics into `Survey123Module`

**Files:**
- Modify: `apps/backend/app/modules/survey123/metrics.py` (append `METRIC_SPECS` and `METRIC_FUNCTIONS`)
- Modify: `apps/backend/app/modules/survey123/module.py`
- Create: `apps/backend/tests/test_survey123_metrics_dispatch.py`

**Interfaces:**
- Consumes: all 9 metric functions (Tasks 2–5), `MetricSpec` (Step 1).
- Produces: `METRIC_PARAMS_SCHEMA: dict` (JSON-schema shape shared by all 9 metrics), `METRIC_SPECS: list[MetricSpec]` (9 entries), `METRIC_FUNCTIONS: dict[str, Callable[[dict, Session], list[Fact]]]` (9 entries, keyed by metric name). `Survey123Module.list_metrics()` now returns `METRIC_SPECS`; `Survey123Module.run_metric(name, params, session)` now dispatches through `METRIC_FUNCTIONS`, still raising `ValueError` for any name not in that dict.

- [ ] **Step 1: Write the failing tests**

Create `apps/backend/tests/test_survey123_metrics_dispatch.py`:

```python
from pathlib import Path

import pytest
from sqlalchemy.orm import sessionmaker

from app.db import Base, make_engine
from app.modules.survey123.ingest import ingest_csv
from app.modules.survey123.module import survey123_module

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "sample_small.csv"

EXPECTED_METRIC_NAMES = {
    "incident_count",
    "incidents_by_corporation",
    "homes_affected_count",
    "casualty_summary",
    "street_level_tally",
    "relief_actions_summary",
    "special_needs_count",
    "estimated_damage_total",
    "data_coverage",
}


def make_session(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    ingest_csv(FIXTURE_PATH, session, salt="test-salt")
    return session


def test_list_metrics_returns_all_nine_with_correct_names():
    specs = survey123_module.list_metrics()

    assert {spec.name for spec in specs} == EXPECTED_METRIC_NAMES
    assert len(specs) == 9
    for spec in specs:
        assert spec.module == "survey123"
        assert spec.params_schema["type"] == "object"


def test_run_metric_dispatches_to_incident_count(tmp_path):
    session = make_session(tmp_path)

    facts = survey123_module.run_metric("incident_count", {}, session)

    assert len(facts) == 1
    assert facts[0].value == 19


def test_run_metric_dispatches_to_data_coverage_multi_fact(tmp_path):
    session = make_session(tmp_path)

    facts = survey123_module.run_metric("data_coverage", {}, session)

    assert len(facts) == 4


def test_run_metric_still_raises_for_unknown_metric(tmp_path):
    session = make_session(tmp_path)

    with pytest.raises(ValueError, match="not_a_real_metric"):
        survey123_module.run_metric("not_a_real_metric", {}, session)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd apps/backend
uv run pytest tests/test_survey123_metrics_dispatch.py -v
```

Expected: FAIL — `test_list_metrics_returns_all_nine_with_correct_names` fails with `assert set() == {...}` (currently `list_metrics()` returns `[]`).

- [ ] **Step 3: Append `METRIC_PARAMS_SCHEMA`, `METRIC_SPECS`, `METRIC_FUNCTIONS` to `app/modules/survey123/metrics.py`**

Add this import to the top of the file (alongside the existing ones):

```python
from app.core.contracts import MetricSpec
```

Append at the end of the file:

```python
METRIC_PARAMS_SCHEMA = {
    "type": "object",
    "properties": {
        "corporation": {"type": "string"},
        "community": {"type": "string"},
        "date_from": {"type": "string", "format": "date"},
        "date_to": {"type": "string", "format": "date"},
        "include_pending": {"type": "boolean", "default": False},
    },
}

METRIC_SPECS: list[MetricSpec] = [
    MetricSpec(
        name="incident_count",
        description="Total incidents, breakdown by incident_type.",
        params_schema=METRIC_PARAMS_SCHEMA,
        module="survey123",
    ),
    MetricSpec(
        name="incidents_by_corporation",
        description="Counts per corporation, including a (no corporation recorded) bucket for blanks.",
        params_schema=METRIC_PARAMS_SCHEMA,
        module="survey123",
    ),
    MetricSpec(
        name="homes_affected_count",
        description=(
            "Incidents where building damage text is non-empty OR incident_type is flooding_, fire, "
            "or blown_off_roof; breakdown validated vs pending."
        ),
        params_schema=METRIC_PARAMS_SCHEMA,
        module="survey123",
    ),
    MetricSpec(
        name="casualty_summary",
        description="Injuries and deaths totals, reported as two separate citable facts.",
        params_schema=METRIC_PARAMS_SCHEMA,
        module="survey123",
    ),
    MetricSpec(
        name="street_level_tally",
        description="Incidents grouped by community and street.",
        params_schema=METRIC_PARAMS_SCHEMA,
        module="survey123",
    ),
    MetricSpec(
        name="relief_actions_summary",
        description=(
            "Counts of follow-up actions taken: relief supplied, forwarded to agency, "
            "further assessment required, other."
        ),
        params_schema=METRIC_PARAMS_SCHEMA,
        module="survey123",
    ),
    MetricSpec(
        name="special_needs_count",
        description="Sum of special needs occupants.",
        params_schema=METRIC_PARAMS_SCHEMA,
        module="survey123",
    ),
    MetricSpec(
        name="estimated_damage_total",
        description=(
            "Sum of estimated damage cost where present, with an explicit coverage caveat "
            "(N of M records reporting a cost estimate) — this field is sparsely filled and "
            "must never be presented as a complete total."
        ),
        params_schema=METRIC_PARAMS_SCHEMA,
        module="survey123",
    ),
    MetricSpec(
        name="data_coverage",
        description=(
            "Per-corporation record count, % validated, % duplicates flagged, and latest record "
            "timestamp. Spans all rows including pending and flagged duplicates by design."
        ),
        params_schema=METRIC_PARAMS_SCHEMA,
        module="survey123",
    ),
]

METRIC_FUNCTIONS = {
    "incident_count": incident_count,
    "incidents_by_corporation": incidents_by_corporation,
    "homes_affected_count": homes_affected_count,
    "casualty_summary": casualty_summary,
    "street_level_tally": street_level_tally,
    "relief_actions_summary": relief_actions_summary,
    "special_needs_count": special_needs_count,
    "estimated_damage_total": estimated_damage_total,
    "data_coverage": data_coverage,
}
```

- [ ] **Step 4: Update `app/modules/survey123/module.py`**

Replace `apps/backend/app/modules/survey123/module.py` with:

```python
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.core.contracts import Fact, IngestResult, MetricSpec
from app.modules.survey123.ingest import ingest_csv
from app.modules.survey123.metrics import METRIC_FUNCTIONS, METRIC_SPECS


class Survey123Module:
    name = "survey123"

    def ingest(self, file_path: Path) -> IngestResult:
        from app.db import SessionLocal

        session = SessionLocal()
        try:
            return ingest_csv(file_path, session, settings.dedup_salt)
        finally:
            session.close()

    def list_metrics(self) -> list[MetricSpec]:
        return METRIC_SPECS

    def run_metric(self, name: str, params: dict, session: Session) -> list[Fact]:
        fn = METRIC_FUNCTIONS.get(name)
        if fn is None:
            raise ValueError(f"unknown metric for survey123: {name}")
        return fn(params, session)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd apps/backend
uv run pytest tests/test_survey123_metrics_dispatch.py -v
```

Expected: `4 passed`.

- [ ] **Step 6: Run the full suite**

```bash
cd apps/backend
uv run pytest -v
```

Expected: `109 passed`.

- [ ] **Step 7: Manual verification against the real export**

```bash
cd apps/backend
rm -f dev.db
uv run alembic upgrade head
uv run python cli.py ingest survey123 output.csv
uv run python3 -c "
from sqlalchemy.orm import sessionmaker
from app.db import engine
from app.modules.survey123.metrics import incident_count, incidents_by_corporation
Session = sessionmaker(bind=engine)
session = Session()
facts = incidents_by_corporation({}, session)
print(facts[0].value, facts[0].breakdown)
"
rm -f dev.db
```

Expected: `incidents_by_corporation` returns a breakdown with 14 canonical corporation keys plus a `(no corporation recorded)` bucket, and the value roughly matches the validated-only subset of the ~14,942-row export. Clean up `dev.db` afterward — it now contains real PII-adjacent data derived from `output.csv`.

- [ ] **Step 8: Commit**

```bash
git add apps/backend/app/modules/survey123/metrics.py apps/backend/app/modules/survey123/module.py \
        apps/backend/tests/test_survey123_metrics_dispatch.py
git commit -m "backend: wire all 9 survey123 metrics into DataModule dispatch"
```

---

## Definition of Done (matches `PLAN.md` §6 Step 3)

- [ ] `cd apps/backend && uv run pytest -v` — all 108 tests pass, 0 failures.
- [ ] Every metric returns correctly cited `Fact`s (`build_citation`'s `record_ids` cap, `query_ref` reproducibility, and per-metric `verification` labeling all covered by tests).
- [ ] `include_pending` toggles verification handling (`test_incident_count_include_pending_widens_result`, `test_homes_affected_count_include_pending_widens_value_but_not_breakdown`, etc.).
- [ ] Blank-corporation bucket appears (`test_incidents_by_corporation_default_includes_blank_bucket`, `test_data_coverage_returns_one_fact_per_corporation_including_blank_bucket`).
- [ ] `GET /modules` (Step 1/2) now shows `survey123` with all 9 metrics listed — verify with `cd apps/backend && uv run pytest tests/test_survey123_module.py tests/test_survey123_metrics_dispatch.py -v`.
