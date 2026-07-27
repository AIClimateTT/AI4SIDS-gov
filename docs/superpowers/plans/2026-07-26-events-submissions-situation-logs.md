# Events, Submissions and Situation Logs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the corp SITREP data path with corp-owned events, atomic submissions, structured situation logs, and a schema that separates authoritative corp data from raw Survey123 field observation.

**Architecture:** Four new tables (`events`, `submissions`, `sitrep_incidents`, `situation_logs`) hold corp-entered data anchored to a submission. The existing `incidents` table is renamed to `field_observations` and stripped of its `source` column — the table now *is* the source. Metric functions are parameterised on a SQLAlchemy model class instead of a source string, so one implementation serves both tables. CSV ingest collects per-row errors instead of aborting the batch.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2.x (`Mapped`/`mapped_column`), Pydantic v2, Alembic, Typer CLI, pytest.

**Spec:** `docs/superpowers/specs/2026-07-26-corp-sitrep-realignment-design.md`

## Global Constraints

- **No PII is ever written to any table.** `Name of Person` and `Contact Information` are tolerated in uploaded CSVs and dropped at parse time. This is verified by a test, not by inspection.
- **No authentication exists and none is added here.** `corporation` is a plain column and a manual selection. Never introduce a user model, session, or permission check.
- **Corporation values must be canonical.** Use `normalize_corporation()` from `app/modules/survey123/normalize.py`; the fourteen canonical slugs live in `CANONICAL_CORPORATIONS` there.
- **Sitrep incident columns that also exist on Survey123 must use identical names** (`corporation`, `community`, `street`, `incident_type`, `event_date`, `injuries_count`, …). The shared metric core filters by attribute name across both models; a renamed column silently breaks it.
- **Supersession is an explicit lookup-then-upsert**, never a reliance on a unique index. `event_id` is nullable and SQL does not collide NULLs.
- **Alembic revisions chain from `c4e8f1a2b903`** (current head). Every new model module must be imported in `alembic/env.py` or autogenerate will propose dropping its table.
- **Run tests with** `cd apps/backend && .venv/bin/python -m pytest`. Baseline before this plan: 243 passed, 2 failed (`tests/test_llm.py` — pre-existing, caused by leftover debug instrumentation, out of scope here).

---

## File Structure

**Create:**
- `app/modules/sitreps/models.py` — the four new ORM models and their enum tuples.
- `app/modules/sitreps/store.py` — event and submission persistence (create, list, sequence numbering).
- `app/modules/sitreps/parse.py` — pure CSV row parsing for both files, returning row errors.
- `alembic/versions/d1a4b7c92e10_create_events_submissions_logs.py`
- `alembic/versions/e2b5c8d03f21_split_field_observations.py`
- `fixtures/sample_submission_incidents.csv`, `fixtures/sample_submission_logs.csv`
- `tests/test_sitreps_models.py`, `tests/test_sitreps_store.py`, `tests/test_sitreps_parse.py`, `tests/test_sitreps_submission_ingest.py`, `tests/test_metrics_model_param.py`, `tests/test_field_observations_split.py`, `tests/test_api_submissions.py`

**Modify:**
- `app/modules/sitreps/ingest.py` — replaced wholesale by submission orchestration.
- `app/modules/sitreps/module.py` — metrics read `SitrepIncident`.
- `app/modules/survey123/models.py` — `Incident` → `FieldObservation`, table `field_observations`, `source` dropped.
- `app/modules/survey123/metrics.py` — metric functions take a `model` parameter.
- `app/modules/survey123/ingest.py`, `app/modules/survey123/module.py` — follow the rename.
- `app/core/contracts.py` — add `RowErrorInfo` and `SubmissionIngestResult`.
- `app/api/ingest.py`, `app/api/__init__.py`, `app/__init__.py`, `cli.py`, `alembic/env.py`.

---

## Task 1: New sitreps schema

**Files:**
- Create: `apps/backend/app/modules/sitreps/models.py`
- Create: `apps/backend/alembic/versions/d1a4b7c92e10_create_events_submissions_logs.py`
- Modify: `apps/backend/alembic/env.py`
- Test: `apps/backend/tests/test_sitreps_models.py`

**Interfaces:**
- Consumes: `app.db.Base`.
- Produces: `Event`, `Submission`, `SitrepIncident`, `SituationLog` ORM classes; tuples `ALERT_LEVELS`, `HAZARD_TYPES`, `LOG_CATEGORIES`; property `SitrepIncident.record_ref -> str`.

- [ ] **Step 1: Write the failing test**

Create `apps/backend/tests/test_sitreps_models.py`:

```python
from datetime import datetime

from sqlalchemy.orm import sessionmaker

from app.db import Base, make_engine
from app.modules.sitreps.models import (
    ALERT_LEVELS,
    HAZARD_TYPES,
    LOG_CATEGORIES,
    Event,
    SitrepIncident,
    SituationLog,
    Submission,
)


def make_session(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_submission_can_hang_off_an_event(tmp_path):
    session = make_session(tmp_path)
    event = Event(
        corporation="diego_martin_regional_corporati",
        title="Adverse Weather June 2023",
        hazard_type="wind",
        started_at=datetime(2023, 6, 27),
        created_at=datetime(2023, 6, 27),
    )
    session.add(event)
    session.flush()

    submission = Submission(
        corporation="diego_martin_regional_corporati",
        event_id=event.id,
        as_at=datetime(2023, 6, 30, 16, 0),
        alert_level="discontinued",
        present_activity="Adverse Weather Alert",
        situation_overview="Heavy rainfall and high winds affected the Borough.",
        sequence_no=4,
        ingested_at=datetime(2023, 6, 30, 16, 5),
    )
    session.add(submission)
    session.commit()

    stored = session.query(Submission).one()
    assert stored.event_id == event.id
    assert stored.sequence_no == 4
    assert stored.alert_level == "discontinued"


def test_submission_without_an_event_is_allowed(tmp_path):
    session = make_session(tmp_path)
    session.add(
        Submission(
            corporation="siparia_regional_corporation",
            event_id=None,
            as_at=datetime(2024, 1, 5, 9, 0),
            alert_level="none",
            ingested_at=datetime(2024, 1, 5, 9, 1),
        )
    )
    session.commit()

    assert session.query(Submission).one().event_id is None


def test_sitrep_incident_record_ref_is_stable(tmp_path):
    session = make_session(tmp_path)
    session.add(
        Submission(
            corporation="diego_martin_regional_corporati",
            as_at=datetime(2023, 6, 27),
            alert_level="yellow",
            ingested_at=datetime(2023, 6, 27),
        )
    )
    session.flush()
    incident = SitrepIncident(
        submission_id=1,
        corporation="diego_martin_regional_corporati",
        event_id=None,
        row_id="1",
        incident_type="fallen_tree",
        event_date=datetime(2023, 6, 27),
        ingested_at=datetime(2023, 6, 27),
    )
    session.add(incident)
    session.commit()

    assert incident.record_ref == "diego_martin_regional_corporati:-:1"


def test_situation_log_quantity_is_optional(tmp_path):
    session = make_session(tmp_path)
    session.add(
        Submission(
            corporation="tunapuna_piarco_regional_corpor",
            as_at=datetime(2025, 5, 18, 18, 30),
            alert_level="yellow",
            ingested_at=datetime(2025, 5, 18, 18, 30),
        )
    )
    session.flush()
    session.add_all(
        [
            SituationLog(
                submission_id=1,
                category="activity",
                statement="Tree cutting team on stand by",
            ),
            SituationLog(
                submission_id=1,
                category="resource",
                statement="200 sandbags available for distribution",
                item="sandbags",
                quantity=200,
                unit="bags",
                status="available",
            ),
        ]
    )
    session.commit()

    logs = session.query(SituationLog).order_by(SituationLog.id).all()
    assert logs[0].quantity is None
    assert logs[1].quantity == 200


def test_enum_tuples_match_the_spec():
    assert ALERT_LEVELS == ("green", "yellow", "orange", "red", "discontinued", "none")
    assert HAZARD_TYPES == ("flood", "landslide", "wind", "fire", "other")
    assert LOG_CATEGORIES == (
        "resource",
        "personnel",
        "facility",
        "activity",
        "relief_distributed",
        "other",
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend && .venv/bin/python -m pytest tests/test_sitreps_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.modules.sitreps.models'`

- [ ] **Step 3: Write the models**

Create `apps/backend/app/modules/sitreps/models.py`:

```python
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

ALERT_LEVELS = ("green", "yellow", "orange", "red", "discontinued", "none")
HAZARD_TYPES = ("flood", "landslide", "wind", "fire", "other")
LOG_CATEGORIES = (
    "resource",
    "personnel",
    "facility",
    "activity",
    "relief_distributed",
    "other",
)
LOG_STATUSES = (
    "available",
    "prepositioned",
    "in_stock",
    "inspected",
    "on_standby",
    "ongoing",
    "completed",
    "procuring",
)


class Event(Base):
    """A hazard event owned by one corporation and reused across submissions."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    corporation: Mapped[str] = mapped_column(String, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    hazard_type: Mapped[str] = mapped_column(String, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class Submission(Base):
    """One corp upload: who, as-at when, under what alert state."""

    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    corporation: Mapped[str] = mapped_column(String, nullable=False, index=True)
    event_id: Mapped[int | None] = mapped_column(
        ForeignKey("events.id"), nullable=True, index=True
    )
    as_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    alert_level: Mapped[str] = mapped_column(String, nullable=False, default="none")
    present_activity: Mapped[str | None] = mapped_column(Text, nullable=True)
    situation_overview: Mapped[str | None] = mapped_column(Text, nullable=True)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    source_file: Mapped[str | None] = mapped_column(String, nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class SitrepIncident(Base):
    """Corp-entered incident. Authoritative. Column names mirror FieldObservation
    wherever the shared metric core filters on them."""

    __tablename__ = "sitrep_incidents"
    __table_args__ = (
        UniqueConstraint(
            "corporation", "event_id", "row_id", name="uq_sitrep_incident_corp_event_row"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int] = mapped_column(
        ForeignKey("submissions.id"), nullable=False, index=True
    )
    corporation: Mapped[str] = mapped_column(String, nullable=False, index=True)
    event_id: Mapped[int | None] = mapped_column(
        ForeignKey("events.id"), nullable=True, index=True
    )
    row_id: Mapped[str] = mapped_column(String, nullable=False)

    community: Mapped[str | None] = mapped_column(String, nullable=True)
    street: Mapped[str | None] = mapped_column(String, nullable=True)

    incident_type: Mapped[str | None] = mapped_column(String, nullable=True)
    raw_incident_type: Mapped[str | None] = mapped_column(String, nullable=True)
    incident_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    event_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    injuries_occurred: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    injuries_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deaths_occurred: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deaths_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    building_damage: Mapped[str | None] = mapped_column(Text, nullable=True)
    special_needs_occupants: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_damage_cost: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)

    action_taken: Mapped[str | None] = mapped_column(Text, nullable=True)
    follow_up_flags: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    ingested_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    @property
    def record_ref(self) -> str:
        return f"{self.corporation}:{self.event_id or '-'}:{self.row_id}"


class SituationLog(Base):
    """Operational or preparedness state as at one submission. Never upserted."""

    __tablename__ = "situation_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int] = mapped_column(
        ForeignKey("submissions.id"), nullable=False, index=True
    )
    category: Mapped[str] = mapped_column(String, nullable=False, index=True)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    item: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    quantity: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    unit: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str | None] = mapped_column(String, nullable=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/backend && .venv/bin/python -m pytest tests/test_sitreps_models.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Register the models with Alembic**

In `apps/backend/alembic/env.py`, add below the existing model imports:

```python
from app.modules.sitreps import models as sitreps_models  # noqa: F401
```

- [ ] **Step 6: Write the migration**

Create `apps/backend/alembic/versions/d1a4b7c92e10_create_events_submissions_logs.py`:

```python
"""create events, submissions, sitrep_incidents, situation_logs

Revision ID: d1a4b7c92e10
Revises: c4e8f1a2b903
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d1a4b7c92e10"
down_revision: Union[str, Sequence[str], None] = "c4e8f1a2b903"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("corporation", sa.String(), nullable=False, index=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("hazard_type", sa.String(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "submissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("corporation", sa.String(), nullable=False, index=True),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id"), nullable=True, index=True),
        sa.Column("as_at", sa.DateTime(), nullable=False, index=True),
        sa.Column("alert_level", sa.String(), nullable=False, server_default="none"),
        sa.Column("present_activity", sa.Text(), nullable=True),
        sa.Column("situation_overview", sa.Text(), nullable=True),
        sa.Column("sequence_no", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("source_file", sa.String(), nullable=True),
        sa.Column("ingested_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "sitrep_incidents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("submission_id", sa.Integer(), sa.ForeignKey("submissions.id"), nullable=False, index=True),
        sa.Column("corporation", sa.String(), nullable=False, index=True),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id"), nullable=True, index=True),
        sa.Column("row_id", sa.String(), nullable=False),
        sa.Column("community", sa.String(), nullable=True),
        sa.Column("street", sa.String(), nullable=True),
        sa.Column("incident_type", sa.String(), nullable=True),
        sa.Column("raw_incident_type", sa.String(), nullable=True),
        sa.Column("incident_summary", sa.Text(), nullable=True),
        sa.Column("event_date", sa.DateTime(), nullable=True),
        sa.Column("injuries_occurred", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("injuries_count", sa.Integer(), nullable=True),
        sa.Column("deaths_occurred", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deaths_count", sa.Integer(), nullable=True),
        sa.Column("building_damage", sa.Text(), nullable=True),
        sa.Column("special_needs_occupants", sa.Integer(), nullable=True),
        sa.Column("estimated_damage_cost", sa.Numeric(), nullable=True),
        sa.Column("action_taken", sa.Text(), nullable=True),
        sa.Column("follow_up_flags", sa.JSON(), nullable=False),
        sa.Column("ingested_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "corporation", "event_id", "row_id", name="uq_sitrep_incident_corp_event_row"
        ),
    )
    op.create_table(
        "situation_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("submission_id", sa.Integer(), sa.ForeignKey("submissions.id"), nullable=False, index=True),
        sa.Column("category", sa.String(), nullable=False, index=True),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("item", sa.String(), nullable=True, index=True),
        sa.Column("quantity", sa.Numeric(), nullable=True),
        sa.Column("unit", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("situation_logs")
    op.drop_table("sitrep_incidents")
    op.drop_table("submissions")
    op.drop_table("events")
```

- [ ] **Step 7: Verify the migration applies cleanly**

Run: `cd apps/backend && rm -f /tmp/mig_check.db && DATABASE_URL=sqlite:////tmp/mig_check.db .venv/bin/python -m alembic upgrade head`
Expected: no error, ends at `d1a4b7c92e10`.

Then confirm autogenerate sees no drift:
Run: `cd apps/backend && DATABASE_URL=sqlite:////tmp/mig_check.db .venv/bin/python -m alembic check`
Expected: "No new upgrade operations detected."

- [ ] **Step 8: Commit**

```bash
cd apps/backend
git add app/modules/sitreps/models.py alembic/versions/d1a4b7c92e10_create_events_submissions_logs.py alembic/env.py tests/test_sitreps_models.py
git commit -m "sitreps: add events, submissions, sitrep_incidents and situation_logs"
```

---

## Task 2: Event and submission store

**Files:**
- Create: `apps/backend/app/modules/sitreps/store.py`
- Test: `apps/backend/tests/test_sitreps_store.py`

**Interfaces:**
- Consumes: `Event`, `Submission` from Task 1.
- Produces:
  - `create_event(session, *, corporation, title, hazard_type, started_at, ended_at=None) -> Event`
  - `list_events(session, corporation) -> list[Event]`
  - `get_event(session, event_id) -> Event | None`
  - `next_sequence_no(session, corporation, event_id) -> int`
  - `create_submission(session, *, corporation, as_at, event_id=None, alert_level="none", present_activity=None, situation_overview=None, source_file=None) -> Submission`
  - `latest_submission(session, corporation, event_id=None) -> Submission | None`

- [ ] **Step 1: Write the failing test**

Create `apps/backend/tests/test_sitreps_store.py`:

```python
from datetime import datetime

from sqlalchemy.orm import sessionmaker

from app.db import Base, make_engine
from app.modules.sitreps.store import (
    create_event,
    create_submission,
    get_event,
    latest_submission,
    list_events,
    next_sequence_no,
)

CORP = "diego_martin_regional_corporati"
OTHER_CORP = "siparia_regional_corporation"


def make_session(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_create_event_returns_a_persisted_event(tmp_path):
    session = make_session(tmp_path)

    event = create_event(
        session,
        corporation=CORP,
        title="Adverse Weather June 2023",
        hazard_type="wind",
        started_at=datetime(2023, 6, 27),
    )

    assert event.id is not None
    assert event.ended_at is None
    assert get_event(session, event.id).title == "Adverse Weather June 2023"


def test_list_events_is_scoped_to_one_corporation(tmp_path):
    session = make_session(tmp_path)
    create_event(
        session, corporation=CORP, title="Mine", hazard_type="flood",
        started_at=datetime(2023, 6, 27),
    )
    create_event(
        session, corporation=OTHER_CORP, title="Theirs", hazard_type="flood",
        started_at=datetime(2023, 6, 27),
    )

    titles = [e.title for e in list_events(session, CORP)]
    assert titles == ["Mine"]


def test_sequence_no_increments_per_event(tmp_path):
    session = make_session(tmp_path)
    event = create_event(
        session, corporation=CORP, title="Storm", hazard_type="wind",
        started_at=datetime(2023, 6, 27),
    )

    first = create_submission(
        session, corporation=CORP, as_at=datetime(2023, 6, 27, 9), event_id=event.id
    )
    second = create_submission(
        session, corporation=CORP, as_at=datetime(2023, 6, 28, 9), event_id=event.id
    )

    assert first.sequence_no == 1
    assert second.sequence_no == 2
    assert next_sequence_no(session, CORP, event.id) == 3


def test_event_less_submissions_always_start_at_one(tmp_path):
    session = make_session(tmp_path)

    first = create_submission(session, corporation=CORP, as_at=datetime(2024, 1, 5, 9))
    second = create_submission(session, corporation=CORP, as_at=datetime(2024, 1, 6, 9))

    assert first.sequence_no == 1
    assert second.sequence_no == 1


def test_latest_submission_picks_the_newest_as_at(tmp_path):
    session = make_session(tmp_path)
    event = create_event(
        session, corporation=CORP, title="Storm", hazard_type="wind",
        started_at=datetime(2023, 6, 27),
    )
    create_submission(
        session, corporation=CORP, as_at=datetime(2023, 6, 27, 9), event_id=event.id,
        alert_level="yellow",
    )
    create_submission(
        session, corporation=CORP, as_at=datetime(2023, 6, 30, 16), event_id=event.id,
        alert_level="discontinued",
    )

    assert latest_submission(session, CORP, event.id).alert_level == "discontinued"


def test_latest_submission_returns_none_when_corp_has_not_reported(tmp_path):
    session = make_session(tmp_path)

    assert latest_submission(session, CORP) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend && .venv/bin/python -m pytest tests/test_sitreps_store.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.modules.sitreps.store'`

- [ ] **Step 3: Write the store**

Create `apps/backend/app/modules/sitreps/store.py`:

```python
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.sitreps.models import Event, Submission


def create_event(
    session: Session,
    *,
    corporation: str,
    title: str,
    hazard_type: str,
    started_at: datetime,
    ended_at: datetime | None = None,
) -> Event:
    event = Event(
        corporation=corporation,
        title=title,
        hazard_type=hazard_type,
        started_at=started_at,
        ended_at=ended_at,
        created_at=datetime.now(timezone.utc),
    )
    session.add(event)
    session.commit()
    return event


def get_event(session: Session, event_id: int) -> Event | None:
    return session.get(Event, event_id)


def list_events(session: Session, corporation: str) -> list[Event]:
    stmt = (
        select(Event)
        .where(Event.corporation == corporation)
        .order_by(Event.started_at.desc(), Event.id.desc())
    )
    return list(session.scalars(stmt).all())


def next_sequence_no(session: Session, corporation: str, event_id: int | None) -> int:
    # A submission with no event is standalone: it never accumulates a sequence,
    # so "Situation Report #N" numbering only exists within an event.
    if event_id is None:
        return 1
    current = session.scalar(
        select(func.max(Submission.sequence_no)).where(
            Submission.corporation == corporation,
            Submission.event_id == event_id,
        )
    )
    return (current or 0) + 1


def create_submission(
    session: Session,
    *,
    corporation: str,
    as_at: datetime,
    event_id: int | None = None,
    alert_level: str = "none",
    present_activity: str | None = None,
    situation_overview: str | None = None,
    source_file: str | None = None,
) -> Submission:
    submission = Submission(
        corporation=corporation,
        event_id=event_id,
        as_at=as_at,
        alert_level=alert_level,
        present_activity=present_activity,
        situation_overview=situation_overview,
        sequence_no=next_sequence_no(session, corporation, event_id),
        source_file=source_file,
        ingested_at=datetime.now(timezone.utc),
    )
    session.add(submission)
    session.commit()
    return submission


def latest_submission(
    session: Session, corporation: str, event_id: int | None = None
) -> Submission | None:
    stmt = select(Submission).where(Submission.corporation == corporation)
    if event_id is not None:
        stmt = stmt.where(Submission.event_id == event_id)
    stmt = stmt.order_by(Submission.as_at.desc(), Submission.id.desc()).limit(1)
    return session.scalars(stmt).first()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/backend && .venv/bin/python -m pytest tests/test_sitreps_store.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
cd apps/backend
git add app/modules/sitreps/store.py tests/test_sitreps_store.py
git commit -m "sitreps: add event and submission store with per-event sequence numbering"
```

---

## Task 3: Incident CSV row parsing with row-level errors

**Files:**
- Create: `apps/backend/app/modules/sitreps/parse.py`
- Create: `apps/backend/fixtures/sample_submission_incidents.csv`
- Test: `apps/backend/tests/test_sitreps_parse.py`

**Interfaces:**
- Consumes: `parse_bool`, `parse_int`, `parse_decimal`, `parse_datetime` from `app.modules.survey123.ingest`; `normalize_incident_type` from `app.modules.survey123.normalize`.
- Produces:
  - `RowError` dataclass with fields `row_number: int`, `reason: str`
  - `INCIDENT_PII_COLUMNS: list[str]`
  - `parse_incident_row(row: dict[str, str], row_number: int) -> tuple[dict | None, RowError | None]`

- [ ] **Step 1: Write the fixture**

Create `apps/backend/fixtures/sample_submission_incidents.csv`. Note it carries the PII columns on purpose — real corp spreadsheets do, and the test proves they are dropped.

```csv
Row ID,Community,Street,Incident Type,Date of Event,Incident Summary,Name of Person,Contact Information,Injuries Occurred,Injuries Count,Deaths Occurred,Deaths Count,Building Damage,Special Needs Occupants,Estimated Damage Cost,Action Taken,Relief Supplied,Forwarded To Agency,Further Assessment Required,Other Follow Up
1,Petit Valley,Cameron Road,fallen_tree,2023-06-27,Fallen tree on home.,Velma Cupidore,793-9056,False,,False,,Branch damaged metal sheet.,,,DMU removed fallen tree.,True,False,False,False
2,Maraval,Saddle Road,blown_off_roof,2023-06-27,Leaking roof causing rainwater inundation.,Juliet Henderson,681-4001,False,,False,,Minor holes in roof,,1500,Tarpaulin issued 20 x 30.,True,True,False,False
3,Diamond Vale,Opal Gardens,landslide,2023-06-28,Landslide across access road.,Simone Beard,493-8022,True,1,False,,Retaining wall collapsed,2,25000,Assessment complete.,False,True,True,False
```

- [ ] **Step 2: Write the failing test**

Create `apps/backend/tests/test_sitreps_parse.py`:

```python
import csv
from datetime import datetime
from pathlib import Path

from app.modules.sitreps.parse import (
    INCIDENT_PII_COLUMNS,
    RowError,
    parse_incident_row,
)

FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample_submission_incidents.csv"


def read_fixture_rows() -> list[dict[str, str]]:
    with open(FIXTURE, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_parses_a_well_formed_row():
    row = read_fixture_rows()[0]

    fields, error = parse_incident_row(row, 1)

    assert error is None
    assert fields["row_id"] == "1"
    assert fields["community"] == "Petit Valley"
    assert fields["street"] == "Cameron Road"
    assert fields["incident_type"] == "fallen_tree"
    assert fields["event_date"] == datetime(2023, 6, 27)
    assert fields["action_taken"] == "DMU removed fallen tree."
    assert fields["follow_up_flags"] == {
        "relief_supplied": True,
        "forwarded_to_agency": False,
        "further_assessment_required": False,
        "other": False,
    }


def test_never_returns_pii_fields():
    rows = read_fixture_rows()

    for number, row in enumerate(rows, start=1):
        fields, error = parse_incident_row(row, number)
        assert error is None
        for key, value in fields.items():
            assert "Cupidore" not in str(value)
            assert "793-9056" not in str(value)
    assert INCIDENT_PII_COLUMNS == ["Name of Person", "Contact Information"]


def test_parses_counts_and_costs():
    row = read_fixture_rows()[2]

    fields, error = parse_incident_row(row, 3)

    assert error is None
    assert fields["injuries_occurred"] is True
    assert fields["injuries_count"] == 1
    assert fields["special_needs_occupants"] == 2
    assert int(fields["estimated_damage_cost"]) == 25000


def test_missing_row_id_is_a_row_error_not_an_exception():
    row = dict(read_fixture_rows()[0])
    row["Row ID"] = "  "

    fields, error = parse_incident_row(row, 7)

    assert fields is None
    assert error == RowError(row_number=7, reason="Row ID is required")


def test_non_numeric_row_id_is_accepted():
    # Corps number rows as "1a" / "12b" when they split an incident. This must
    # not be an error; the old int() coercion was the bug that aborted batches.
    row = dict(read_fixture_rows()[0])
    row["Row ID"] = "12b"

    fields, error = parse_incident_row(row, 1)

    assert error is None
    assert fields["row_id"] == "12b"


def test_missing_date_of_event_is_a_row_error():
    row = dict(read_fixture_rows()[0])
    row["Date of Event"] = ""

    fields, error = parse_incident_row(row, 4)

    assert fields is None
    assert error == RowError(row_number=4, reason="Date of Event is required")


def test_unparseable_date_of_event_is_a_row_error():
    row = dict(read_fixture_rows()[0])
    row["Date of Event"] = "27/06/2023"

    fields, error = parse_incident_row(row, 5)

    assert fields is None
    assert error == RowError(
        row_number=5, reason="Date of Event is not an ISO date: '27/06/2023'"
    )


def test_unmapped_incident_type_falls_through_to_raw():
    row = dict(read_fixture_rows()[0])
    row["Incident Type"] = "Roofing Damages"

    fields, error = parse_incident_row(row, 1)

    assert error is None
    assert fields["raw_incident_type"] == "Roofing Damages"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd apps/backend && .venv/bin/python -m pytest tests/test_sitreps_parse.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.modules.sitreps.parse'`

- [ ] **Step 4: Write the parser**

Create `apps/backend/app/modules/sitreps/parse.py`:

```python
from dataclasses import dataclass
from datetime import datetime

from app.modules.survey123.ingest import parse_bool, parse_decimal, parse_int
from app.modules.survey123.normalize import normalize_incident_type

INCIDENT_PII_COLUMNS = ["Name of Person", "Contact Information"]


@dataclass(frozen=True)
class RowError:
    row_number: int
    reason: str


def _clean(raw: str | None) -> str | None:
    cleaned = (raw or "").strip()
    return cleaned or None


def parse_incident_row(
    row: dict[str, str], row_number: int
) -> tuple[dict | None, RowError | None]:
    """Parse one incidents.csv row.

    Returns (fields, None) on success or (None, RowError) on a rejectable row.
    Never raises for bad data — a malformed row must not abort the batch, since
    corps author these spreadsheets by hand.
    """
    row_id = _clean(row.get("Row ID"))
    if row_id is None:
        return None, RowError(row_number=row_number, reason="Row ID is required")

    raw_date = _clean(row.get("Date of Event"))
    if raw_date is None:
        return None, RowError(row_number=row_number, reason="Date of Event is required")
    try:
        event_date = datetime.fromisoformat(raw_date)
    except ValueError:
        return None, RowError(
            row_number=row_number,
            reason=f"Date of Event is not an ISO date: {raw_date!r}",
        )

    incident_type, raw_incident_type = normalize_incident_type(row.get("Incident Type"))

    return (
        {
            "row_id": row_id,
            "community": _clean(row.get("Community")),
            "street": _clean(row.get("Street")),
            "incident_type": incident_type,
            "raw_incident_type": raw_incident_type,
            "incident_summary": _clean(row.get("Incident Summary")),
            "event_date": event_date,
            "injuries_occurred": parse_bool(row.get("Injuries Occurred")),
            "injuries_count": parse_int(row.get("Injuries Count")),
            "deaths_occurred": parse_bool(row.get("Deaths Occurred")),
            "deaths_count": parse_int(row.get("Deaths Count")),
            "building_damage": _clean(row.get("Building Damage")),
            "special_needs_occupants": parse_int(row.get("Special Needs Occupants")),
            "estimated_damage_cost": parse_decimal(row.get("Estimated Damage Cost")),
            "action_taken": _clean(row.get("Action Taken")),
            "follow_up_flags": {
                "relief_supplied": parse_bool(row.get("Relief Supplied")),
                "forwarded_to_agency": parse_bool(row.get("Forwarded To Agency")),
                "further_assessment_required": parse_bool(
                    row.get("Further Assessment Required")
                ),
                "other": parse_bool(row.get("Other Follow Up")),
            },
        },
        None,
    )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd apps/backend && .venv/bin/python -m pytest tests/test_sitreps_parse.py -v`
Expected: PASS (8 tests)

- [ ] **Step 6: Commit**

```bash
cd apps/backend
git add app/modules/sitreps/parse.py fixtures/sample_submission_incidents.csv tests/test_sitreps_parse.py
git commit -m "sitreps: parse incident rows with row-level errors instead of aborting the batch"
```

---

## Task 4: Situation log CSV row parsing

**Files:**
- Modify: `apps/backend/app/modules/sitreps/parse.py`
- Create: `apps/backend/fixtures/sample_submission_logs.csv`
- Modify: `apps/backend/tests/test_sitreps_parse.py`

**Interfaces:**
- Consumes: `RowError`, `_clean` from Task 3; `LOG_CATEGORIES`, `LOG_STATUSES` from Task 1.
- Produces: `parse_log_row(row: dict[str, str], row_number: int) -> tuple[dict | None, RowError | None]`

- [ ] **Step 1: Write the fixture**

Create `apps/backend/fixtures/sample_submission_logs.csv`:

```csv
Category,Statement,Item,Quantity,Unit,Status
activity,Tree cutting team on stand by,,,,on_standby
resource,200 sandbags available for distribution,sandbags,200,bags,available
facility,22 facilities were inspected and recommended as emergency shelters,shelters,22,facilities,inspected
personnel,Informed CEO Engineer and PMOH,,,,completed
relief_distributed,Tarpaulins issued to affected residents,tarpaulins,18,units,completed
```

- [ ] **Step 2: Write the failing test**

Append to `apps/backend/tests/test_sitreps_parse.py`:

```python
from app.modules.sitreps.parse import parse_log_row

LOGS_FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample_submission_logs.csv"


def read_log_rows() -> list[dict[str, str]]:
    with open(LOGS_FIXTURE, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_parses_a_log_row_with_no_quantity():
    fields, error = parse_log_row(read_log_rows()[0], 1)

    assert error is None
    assert fields["category"] == "activity"
    assert fields["statement"] == "Tree cutting team on stand by"
    assert fields["item"] is None
    assert fields["quantity"] is None
    assert fields["status"] == "on_standby"


def test_parses_a_log_row_with_a_quantity():
    fields, error = parse_log_row(read_log_rows()[1], 2)

    assert error is None
    assert fields["item"] == "sandbags"
    assert fields["quantity"] == 200
    assert fields["unit"] == "bags"


def test_missing_statement_is_a_row_error():
    row = dict(read_log_rows()[0])
    row["Statement"] = ""

    fields, error = parse_log_row(row, 3)

    assert fields is None
    assert error == RowError(row_number=3, reason="Statement is required")


def test_unknown_category_is_a_row_error():
    row = dict(read_log_rows()[0])
    row["Category"] = "logistics"

    fields, error = parse_log_row(row, 4)

    assert fields is None
    assert error.row_number == 4
    assert "logistics" in error.reason


def test_unparseable_quantity_is_a_row_error_not_a_silent_none():
    # A quantity that silently became None would drop a citable figure from the
    # report with no trace. That is the exact failure this system exists to stop.
    row = dict(read_log_rows()[1])
    row["Quantity"] = "about 200"

    fields, error = parse_log_row(row, 5)

    assert fields is None
    assert error == RowError(
        row_number=5, reason="Quantity is not a number: 'about 200'"
    )


def test_unknown_status_is_a_row_error():
    row = dict(read_log_rows()[0])
    row["Status"] = "maybe"

    fields, error = parse_log_row(row, 6)

    assert fields is None
    assert error.row_number == 6
    assert "maybe" in error.reason
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd apps/backend && .venv/bin/python -m pytest tests/test_sitreps_parse.py -v -k log`
Expected: FAIL — `ImportError: cannot import name 'parse_log_row'`

- [ ] **Step 4: Add the log parser**

Append to `apps/backend/app/modules/sitreps/parse.py`, and add `from app.modules.sitreps.models import LOG_CATEGORIES, LOG_STATUSES` to its imports:

```python
def parse_log_row(
    row: dict[str, str], row_number: int
) -> tuple[dict | None, RowError | None]:
    """Parse one logs.csv row.

    A log is a prose statement, optionally carrying a structured quantity. Any
    number the report later states must come from the quantity column, so an
    unparseable quantity is rejected rather than silently nulled.
    """
    statement = _clean(row.get("Statement"))
    if statement is None:
        return None, RowError(row_number=row_number, reason="Statement is required")

    category = (_clean(row.get("Category")) or "other").lower()
    if category not in LOG_CATEGORIES:
        return None, RowError(
            row_number=row_number,
            reason=f"Category {category!r} is not one of {', '.join(LOG_CATEGORIES)}",
        )

    quantity: float | None = None
    raw_quantity = _clean(row.get("Quantity"))
    if raw_quantity is not None:
        try:
            quantity = float(raw_quantity)
        except ValueError:
            return None, RowError(
                row_number=row_number,
                reason=f"Quantity is not a number: {raw_quantity!r}",
            )

    status = _clean(row.get("Status"))
    if status is not None and status.lower() not in LOG_STATUSES:
        return None, RowError(
            row_number=row_number,
            reason=f"Status {status!r} is not one of {', '.join(LOG_STATUSES)}",
        )

    return (
        {
            "category": category,
            "statement": statement,
            "item": _clean(row.get("Item")),
            "quantity": quantity,
            "unit": _clean(row.get("Unit")),
            "status": status.lower() if status else None,
        },
        None,
    )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd apps/backend && .venv/bin/python -m pytest tests/test_sitreps_parse.py -v`
Expected: PASS (14 tests)

- [ ] **Step 6: Commit**

```bash
cd apps/backend
git add app/modules/sitreps/parse.py fixtures/sample_submission_logs.csv tests/test_sitreps_parse.py
git commit -m "sitreps: parse situation log rows, rejecting unparseable quantities"
```

---

## Task 5: Atomic submission ingest

**Files:**
- Modify: `apps/backend/app/core/contracts.py`
- Rewrite: `apps/backend/app/modules/sitreps/ingest.py`
- Delete: `apps/backend/tests/test_sitreps_ingest.py` (tests the removed `ingest_sitrep_csv`)
- Test: `apps/backend/tests/test_sitreps_submission_ingest.py`

**Interfaces:**
- Consumes: Task 2 store functions, Task 3/4 parsers, Task 1 models.
- Produces:
  - `RowErrorInfo(BaseModel)` with `file: str`, `row_number: int`, `reason: str`
  - `SubmissionIngestResult(BaseModel)` with `submission_id: int`, `sequence_no: int`, `incidents_read: int`, `incidents_inserted: int`, `incidents_updated: int`, `logs_read: int`, `logs_inserted: int`, `row_errors: list[RowErrorInfo]`, `unmapped_values: dict[str, list[str]]`, `pii_columns_dropped: list[str]`
  - `ingest_submission(session, *, corporation, as_at, event_id=None, alert_level="none", present_activity=None, situation_overview=None, incidents_path=None, logs_path=None) -> SubmissionIngestResult`

- [ ] **Step 1: Add the result contracts**

Append to `apps/backend/app/core/contracts.py`:

```python
class RowErrorInfo(BaseModel):
    file: Literal["incidents", "logs"]
    row_number: int
    reason: str


class SubmissionIngestResult(BaseModel):
    submission_id: int
    sequence_no: int
    incidents_read: int
    incidents_inserted: int
    incidents_updated: int
    logs_read: int
    logs_inserted: int
    row_errors: list[RowErrorInfo]
    unmapped_values: dict[str, list[str]]
    pii_columns_dropped: list[str]
```

- [ ] **Step 2: Write the failing test**

Create `apps/backend/tests/test_sitreps_submission_ingest.py`:

```python
import csv
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import sessionmaker

from app.db import Base, make_engine
from app.modules.sitreps.ingest import ingest_submission
from app.modules.sitreps.models import SitrepIncident, SituationLog, Submission
from app.modules.sitreps.store import create_event

INCIDENTS = Path(__file__).parent.parent / "fixtures" / "sample_submission_incidents.csv"
LOGS = Path(__file__).parent.parent / "fixtures" / "sample_submission_logs.csv"
CORP = "diego_martin_regional_corporati"


def make_session(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def write_csv(tmp_path, name, header, rows):
    path = Path(tmp_path) / name
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
    return path


def test_ingests_both_files_under_one_submission(tmp_path):
    session = make_session(tmp_path)

    result = ingest_submission(
        session,
        corporation=CORP,
        as_at=datetime(2023, 6, 30, 16, 0),
        alert_level="discontinued",
        present_activity="Adverse Weather Alert",
        situation_overview="Heavy rainfall affected the Borough.",
        incidents_path=INCIDENTS,
        logs_path=LOGS,
    )

    assert result.incidents_read == 3
    assert result.incidents_inserted == 3
    assert result.logs_read == 5
    assert result.logs_inserted == 5
    assert result.row_errors == []

    submission = session.query(Submission).one()
    assert submission.id == result.submission_id
    assert submission.situation_overview == "Heavy rainfall affected the Borough."
    assert session.query(SitrepIncident).count() == 3
    assert session.query(SituationLog).count() == 5


def test_either_file_may_be_omitted(tmp_path):
    session = make_session(tmp_path)

    result = ingest_submission(
        session, corporation=CORP, as_at=datetime(2023, 5, 5, 15, 0), logs_path=LOGS
    )

    assert result.incidents_read == 0
    assert result.logs_read == 5
    assert session.query(SitrepIncident).count() == 0


def test_never_writes_pii(tmp_path):
    session = make_session(tmp_path)

    result = ingest_submission(
        session, corporation=CORP, as_at=datetime(2023, 6, 30), incidents_path=INCIDENTS
    )

    assert result.pii_columns_dropped == ["Name of Person", "Contact Information"]
    for incident in session.query(SitrepIncident).all():
        for value in vars(incident).values():
            assert "Cupidore" not in str(value)
            assert "793-9056" not in str(value)


def test_bad_rows_are_reported_and_good_rows_still_land(tmp_path):
    session = make_session(tmp_path)
    path = write_csv(
        tmp_path,
        "mixed.csv",
        ["Row ID", "Incident Type", "Date of Event", "Community"],
        [
            ["1", "fallen_tree", "2023-06-27", "Petit Valley"],
            ["", "landslide", "2023-06-27", "Maraval"],
            ["3", "flooding_", "27/06/2023", "Paramin"],
            ["4", "fire", "2023-06-28", "Diamond Vale"],
        ],
    )

    result = ingest_submission(
        session, corporation=CORP, as_at=datetime(2023, 6, 30), incidents_path=path
    )

    assert result.incidents_read == 4
    assert result.incidents_inserted == 2
    assert [(e.row_number, e.file) for e in result.row_errors] == [
        (2, "incidents"),
        (3, "incidents"),
    ]
    assert session.query(SitrepIncident).count() == 2


def test_reuploading_a_cumulative_table_supersedes_rather_than_duplicates(tmp_path):
    session = make_session(tmp_path)
    event = create_event(
        session, corporation=CORP, title="Storm", hazard_type="wind",
        started_at=datetime(2023, 6, 27),
    )
    header = ["Row ID", "Incident Type", "Date of Event", "Incident Summary"]

    first = write_csv(
        tmp_path, "first.csv", header,
        [["1", "fallen_tree", "2023-06-27", "Original summary"]],
    )
    ingest_submission(
        session, corporation=CORP, as_at=datetime(2023, 6, 27), event_id=event.id,
        incidents_path=first,
    )

    second = write_csv(
        tmp_path, "second.csv", header,
        [
            ["1", "fallen_tree", "2023-06-27", "Corrected summary"],
            ["2", "landslide", "2023-06-28", "New row"],
        ],
    )
    result = ingest_submission(
        session, corporation=CORP, as_at=datetime(2023, 6, 28), event_id=event.id,
        incidents_path=second,
    )

    assert result.incidents_inserted == 1
    assert result.incidents_updated == 1
    assert session.query(SitrepIncident).count() == 2
    row_one = (
        session.query(SitrepIncident).filter(SitrepIncident.row_id == "1").one()
    )
    assert row_one.incident_summary == "Corrected summary"


def test_event_less_submissions_do_not_supersede_each_other(tmp_path):
    session = make_session(tmp_path)
    header = ["Row ID", "Incident Type", "Date of Event"]
    path = write_csv(tmp_path, "routine.csv", header, [["1", "fire", "2024-01-05"]])

    ingest_submission(session, corporation=CORP, as_at=datetime(2024, 1, 5), incidents_path=path)
    ingest_submission(session, corporation=CORP, as_at=datetime(2024, 1, 6), incidents_path=path)

    assert session.query(SitrepIncident).count() == 2


def test_logs_are_never_superseded(tmp_path):
    session = make_session(tmp_path)
    event = create_event(
        session, corporation=CORP, title="Storm", hazard_type="wind",
        started_at=datetime(2023, 6, 27),
    )

    ingest_submission(
        session, corporation=CORP, as_at=datetime(2023, 6, 27), event_id=event.id,
        logs_path=LOGS,
    )
    ingest_submission(
        session, corporation=CORP, as_at=datetime(2023, 6, 28), event_id=event.id,
        logs_path=LOGS,
    )

    assert session.query(SituationLog).count() == 10
    assert session.query(Submission).count() == 2


def test_sequence_no_is_returned_for_report_numbering(tmp_path):
    session = make_session(tmp_path)
    event = create_event(
        session, corporation=CORP, title="Storm", hazard_type="wind",
        started_at=datetime(2023, 6, 27),
    )

    ingest_submission(session, corporation=CORP, as_at=datetime(2023, 6, 27), event_id=event.id)
    second = ingest_submission(
        session, corporation=CORP, as_at=datetime(2023, 6, 28), event_id=event.id
    )

    assert second.sequence_no == 2
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd apps/backend && .venv/bin/python -m pytest tests/test_sitreps_submission_ingest.py -v`
Expected: FAIL — `ImportError: cannot import name 'ingest_submission'`

- [ ] **Step 4: Rewrite the ingest module**

Replace the entire contents of `apps/backend/app/modules/sitreps/ingest.py`:

```python
import csv
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.contracts import RowErrorInfo, SubmissionIngestResult
from app.modules.sitreps.models import SitrepIncident, SituationLog
from app.modules.sitreps.models import Submission
from app.modules.sitreps.parse import (
    INCIDENT_PII_COLUMNS,
    parse_incident_row,
    parse_log_row,
)
from app.modules.sitreps.store import next_sequence_no


def _read_rows(path: Path) -> list[dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def ingest_submission(
    session: Session,
    *,
    corporation: str,
    as_at: datetime,
    event_id: int | None = None,
    alert_level: str = "none",
    present_activity: str | None = None,
    situation_overview: str | None = None,
    incidents_path: Path | None = None,
    logs_path: Path | None = None,
) -> SubmissionIngestResult:
    """Create one submission and load its incident and log rows.

    Both files are parsed in full before anything is written, and the submission
    plus all of its child rows commit in a single transaction, so a submission
    never lands half-populated. Individual bad rows are collected and reported;
    they do not abort the batch.
    """
    incident_rows = _read_rows(incidents_path) if incidents_path else []
    log_rows = _read_rows(logs_path) if logs_path else []

    row_errors: list[RowErrorInfo] = []
    unmapped_values: dict[str, list[str]] = {}

    parsed_incidents: list[dict] = []
    for number, raw in enumerate(incident_rows, start=1):
        fields, error = parse_incident_row(raw, number)
        if error is not None:
            row_errors.append(
                RowErrorInfo(file="incidents", row_number=error.row_number, reason=error.reason)
            )
            continue
        if fields["raw_incident_type"]:
            values = unmapped_values.setdefault("Incident Type", [])
            if fields["raw_incident_type"] not in values:
                values.append(fields["raw_incident_type"])
        parsed_incidents.append(fields)

    parsed_logs: list[dict] = []
    for number, raw in enumerate(log_rows, start=1):
        fields, error = parse_log_row(raw, number)
        if error is not None:
            row_errors.append(
                RowErrorInfo(file="logs", row_number=error.row_number, reason=error.reason)
            )
            continue
        parsed_logs.append(fields)

    source_file = str(incidents_path or logs_path) if (incidents_path or logs_path) else None

    # Build the Submission inline and flush (not store.create_submission, which
    # commits): the submission and its child rows must land in ONE transaction,
    # or a failure mid-write leaves an orphaned submission with no rows behind it.
    # flush() assigns submission.id without ending the transaction.
    submission = Submission(
        corporation=corporation,
        event_id=event_id,
        as_at=as_at,
        alert_level=alert_level,
        present_activity=present_activity,
        situation_overview=situation_overview,
        sequence_no=next_sequence_no(session, corporation, event_id),
        source_file=source_file,
        ingested_at=datetime.now(timezone.utc),
    )
    session.add(submission)
    session.flush()

    inserted = 0
    updated = 0
    now = datetime.now(timezone.utc)

    for fields in parsed_incidents:
        existing = None
        # Explicit lookup rather than relying on the unique index: event_id is
        # nullable, and SQL does not collide NULLs, so an event-less submission
        # is standalone by design rather than by accident of the constraint.
        if event_id is not None:
            existing = session.scalars(
                select(SitrepIncident).where(
                    SitrepIncident.corporation == corporation,
                    SitrepIncident.event_id == event_id,
                    SitrepIncident.row_id == fields["row_id"],
                )
            ).first()

        if existing is None:
            session.add(
                SitrepIncident(
                    **fields,
                    submission_id=submission.id,
                    corporation=corporation,
                    event_id=event_id,
                    ingested_at=now,
                )
            )
            inserted += 1
        else:
            for key, value in fields.items():
                setattr(existing, key, value)
            existing.submission_id = submission.id
            existing.ingested_at = now
            updated += 1

    for fields in parsed_logs:
        session.add(SituationLog(**fields, submission_id=submission.id))

    session.commit()

    return SubmissionIngestResult(
        submission_id=submission.id,
        sequence_no=submission.sequence_no,
        incidents_read=len(incident_rows),
        incidents_inserted=inserted,
        incidents_updated=updated,
        logs_read=len(log_rows),
        logs_inserted=len(parsed_logs),
        row_errors=row_errors,
        unmapped_values=unmapped_values,
        pii_columns_dropped=list(INCIDENT_PII_COLUMNS),
    )
```

- [ ] **Step 5: Retire every caller of the removed `ingest_sitrep_csv`**

Deleting the function orphans four call sites. They must go in this task — a task that leaves the suite uncollectable is not done.

**a. `apps/backend/app/api/ingest.py`** — delete the `from app.modules.sitreps.ingest import ingest_sitrep_csv` import, the `corporation` form parameter, and the `if module_name == "sitreps":` ingest branch. Replace with an explicit rejection placed immediately after the `get_module` lookup, before the file is read. FastAPI does not translate `NotImplementedError` into a status code, so returning 400 here is what keeps this a clean error rather than an unhandled 500:

```python
    if module_name == "sitreps":
        raise HTTPException(
            status_code=400,
            detail=(
                "sitreps data arrives as a submission; "
                "POST /submissions with a corporation, an as-at time and up to two CSVs"
            ),
        )
```

**b. `apps/backend/cli.py`** — delete the `from app.modules.sitreps.ingest import ingest_sitrep_csv` import and the whole `@ingest_app.command("sitreps")` / `ingest_sitreps` function. Task 8 adds the replacement `submissions` command.

**c. `apps/backend/tests/test_cli_sitreps.py`** — `git rm` it. It tests only the CLI command just removed; Task 8 adds its replacement.

**d. `apps/backend/tests/test_sitreps_module.py`** — delete the two tests that seed data through `ingest_sitrep_csv` (`test_sitrep_module_run_metric_*` and `test_survey123_module_run_metric_only_counts_survey123_rows_when_sitreps_also_present`) along with the now-unused import and fixture constants. Keep the tests that need no data: module name, `list_metrics`, and the `NotImplementedError` on `ingest`.

> Why this coverage gap is acceptable and temporary: sitrep rows now land in `sitrep_incidents`, but the metric functions still read the `Incident` model until Task 7. So the cross-source isolation those two tests proved genuinely cannot hold between here and Task 7. Task 7's `tests/test_field_observations_split.py::test_sitrep_module_never_sees_field_observations` restores exactly that coverage against the new schema. Do not attempt to keep them passing in between.

- [ ] **Step 6: Delete the superseded test file**

```bash
cd apps/backend && git rm tests/test_sitreps_ingest.py tests/test_cli_sitreps.py
```

- [ ] **Step 7: Run the new tests, then the full suite**

Run: `cd apps/backend && .venv/bin/python -m pytest tests/test_sitreps_submission_ingest.py -v`
Expected: PASS (8 tests)

Run: `cd apps/backend && .venv/bin/python -m pytest -q`
Expected: no collection errors. The passing count drops by the removed tests and rises by the 8 new ones — state the arithmetic explicitly in the report so nothing is lost silently. The 2 `tests/test_llm.py` failures remain.

- [ ] **Step 8: Commit**

```bash
cd apps/backend
git add -A app/core/contracts.py app/modules/sitreps/ingest.py app/api/ingest.py cli.py tests/
git commit -m "sitreps: replace CSV ingest with atomic submission ingest and row-level errors"
```

---

## Task 6: Parameterise the metric core on a model class

This task changes no schema. It is a mechanical refactor that makes Task 7 small.

**Files:**
- Modify: `apps/backend/app/modules/survey123/metrics.py`
- Test: `apps/backend/tests/test_metrics_model_param.py`

**Interfaces:**
- Consumes: `Incident` (still named that until Task 7).
- Produces: every function in `METRIC_FUNCTIONS` gains a third parameter `model` defaulting to `Incident`; `apply_common_filters(stmt, params, model=Incident)`; `base_query(params, model=Incident)`; `column_exists(model, name) -> bool`; `record_ref_of(row) -> str`.

- [ ] **Step 1: Write the failing test**

Create `apps/backend/tests/test_metrics_model_param.py`:

```python
import inspect

from app.modules.survey123.metrics import (
    METRIC_FUNCTIONS,
    base_query,
    column_exists,
)
from app.modules.survey123.models import Incident


def test_every_metric_accepts_a_model_parameter():
    for name, fn in METRIC_FUNCTIONS.items():
        params = list(inspect.signature(fn).parameters)
        assert params[:3] == ["params", "session", "model"], (
            f"{name} does not take (params, session, model)"
        )


def test_model_defaults_to_incident_so_existing_callers_are_unaffected():
    for name, fn in METRIC_FUNCTIONS.items():
        default = inspect.signature(fn).parameters["model"].default
        assert default is Incident, f"{name} has the wrong default model"


def test_column_exists_reports_real_columns_only():
    assert column_exists(Incident, "validation_status") is True
    assert column_exists(Incident, "is_duplicate") is True
    assert column_exists(Incident, "not_a_column") is False


def test_base_query_selects_from_the_given_model():
    stmt = base_query({}, Incident)

    assert "incidents" in str(stmt)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend && .venv/bin/python -m pytest tests/test_metrics_model_param.py -v`
Expected: FAIL — `ImportError: cannot import name 'column_exists'`

- [ ] **Step 3: Refactor the metric core**

In `apps/backend/app/modules/survey123/metrics.py`, add these helpers just above `apply_common_filters`:

```python
def column_exists(model, name: str) -> bool:
    """True only for real mapped columns. Deliberately not hasattr(): a Python
    property named like a column would pass hasattr and then blow up in SQL."""
    return name in model.__table__.columns


def record_ref_of(row) -> str:
    """Stable per-row identifier for citations, across both incident models."""
    return getattr(row, "global_id", None) or row.record_ref
```

Replace `apply_common_filters` and `base_query` with:

```python
def apply_common_filters(stmt: Select, params: dict, model=Incident) -> Select:
    if params.get("source") is not None and column_exists(model, "source"):
        stmt = stmt.where(model.source == params["source"])
    if params.get("corporation") is not None:
        stmt = stmt.where(model.corporation == params["corporation"])
    if params.get("community") is not None:
        stmt = stmt.where(model.community == params["community"])
    date_from = parse_date_param(params.get("date_from"))
    if date_from is not None:
        stmt = stmt.where(model.event_date >= date_from)
    date_to = parse_date_param(params.get("date_to"))
    if date_to is not None:
        # date_to arrives as a date-only ISO string (e.g. "2024-06-30"), which
        # parse_date_param parses to midnight. Real event_date values carry a
        # time of day, so "<= midnight" would silently exclude every incident
        # that occurred later that same day. Compare against the start of the
        # NEXT day instead, so date_to is inclusive of the whole day.
        stmt = stmt.where(model.event_date < date_to + timedelta(days=1))
    return stmt


def base_query(params: dict, model=Incident) -> Select:
    stmt = select(model)
    if column_exists(model, "is_duplicate"):
        stmt = stmt.where(model.is_duplicate.is_(False))
    stmt = apply_common_filters(stmt, params, model)
    if column_exists(model, "validation_status") and not params.get("include_pending", False):
        stmt = stmt.where(model.validation_status == "validated")
    return stmt
```

Then update every metric function. Each one changes its signature from
`def name(params: dict, session: Session) -> list[Fact]:` to
`def name(params: dict, session: Session, model=Incident) -> list[Fact]:`,
passes `model` into `base_query(params, model)`, replaces `r.global_id` with `record_ref_of(r)`, and replaces any direct `Incident.` reference in a query with `model.`.

Where a metric reads `r.validation_status` for `determine_verification`, use
`getattr(r, "validation_status", "validated")` — corp SITREP rows are
authoritative by definition and carry no validation column.

Worked example for `incident_count`:

```python
def incident_count(params: dict, session: Session, model=Incident) -> list[Fact]:
    rows = session.execute(base_query(params, model)).scalars().all()

    breakdown: dict[str, int] = {}
    for r in rows:
        key = r.incident_type or "(no incident type recorded)"
        breakdown[key] = breakdown.get(key, 0) + 1

    global_ids = [record_ref_of(r) for r in rows]
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
            verification=determine_verification(
                [getattr(r, "validation_status", "validated") for r in rows]
            ),
            citation=citation,
        )
    ]
```

Apply the same three changes to `incidents_by_corporation`, `homes_affected_count`, `casualty_summary`, `street_level_tally`, `relief_actions_summary`, `special_needs_count`, `estimated_damage_total`, and `data_coverage`.

`data_coverage` additionally reads `is_duplicate` and `validation_status` directly. Guard it:

```python
def data_coverage(params: dict, session: Session, model=Incident) -> list[Fact]:
    if not column_exists(model, "validation_status"):
        # Corp SITREP rows are human-verified by definition, so validation
        # coverage is not a meaningful measure for them.
        return []
    ...
```

**`data_coverage` must NOT be switched to `base_query`.** It deliberately calls
`apply_common_filters(select(model), params, model)` so that it counts duplicate
and pending rows — counting them is the entire point of a coverage metric, and
its own `MetricSpec` says so ("Spans all rows including pending and flagged
duplicates by design"). Routing it through `base_query` would silently change
its answer, because `base_query` filters both out. Thread `model` through its
existing `apply_common_filters` call and leave the rest of its body alone.

- [ ] **Step 4: Run the new test and the full metric suite**

Run: `cd apps/backend && .venv/bin/python -m pytest tests/test_metrics_model_param.py tests/test_metrics_helpers.py tests/test_metrics_incident_count.py tests/test_metrics_homes_and_casualties.py tests/test_metrics_street_and_relief.py tests/test_metrics_needs_damage_coverage.py tests/test_survey123_metrics_dispatch.py -v`
Expected: PASS — all existing metric tests still pass unchanged, plus 4 new.

- [ ] **Step 5: Run the whole suite to confirm nothing else moved**

Run: `cd apps/backend && .venv/bin/python -m pytest -q`
Expected: 2 failed (the pre-existing `tests/test_llm.py` failures), everything else passing.

- [ ] **Step 6: Commit**

```bash
cd apps/backend
git add app/modules/survey123/metrics.py tests/test_metrics_model_param.py
git commit -m "metrics: parameterise the query core on a model class"
```

---

## Task 7: Split field_observations from sitrep_incidents

**Files:**
- Modify: `apps/backend/app/modules/survey123/models.py`, `ingest.py`, `module.py`, `metrics.py`
- Modify: `apps/backend/app/modules/sitreps/module.py`
- Modify: `apps/backend/app/mcp_server/survey123_server.py`
- Create: `apps/backend/alembic/versions/e2b5c8d03f21_split_field_observations.py`
- Test: `apps/backend/tests/test_field_observations_split.py`
- Modify: every test importing `Incident` (see Step 4)

**Interfaces:**
- Consumes: everything from Tasks 1–6.
- Produces: `FieldObservation` (table `field_observations`, no `source` column); `SitrepModule.run_metric` dispatching on `SitrepIncident`.

- [ ] **Step 1: Write the failing test**

Create `apps/backend/tests/test_field_observations_split.py`:

```python
from datetime import datetime

from sqlalchemy.orm import sessionmaker

from app.core.registry import get_module, reset_registry, ensure_default_modules_registered
from app.db import Base, make_engine
from app.modules.sitreps.ingest import ingest_submission
from app.modules.survey123.models import FieldObservation

CORP = "diego_martin_regional_corporati"


def make_session(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_field_observation_has_no_source_column():
    assert "source" not in FieldObservation.__table__.columns
    assert FieldObservation.__tablename__ == "field_observations"


def test_sitrep_module_never_sees_field_observations(tmp_path):
    import csv
    from pathlib import Path

    session = make_session(tmp_path)
    session.add(
        FieldObservation(
            global_id="gid-1",
            object_id=1,
            corporation=CORP,
            incident_type="fire",
            event_date=datetime(2023, 6, 27),
            validation_status="validated",
            follow_up_flags={},
            source_file="x.csv",
            ingested_at=datetime(2023, 6, 27),
        )
    )
    session.commit()

    path = Path(tmp_path) / "inc.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Row ID", "Incident Type", "Date of Event"])
        writer.writerow(["1", "landslide", "2023-06-27"])
    ingest_submission(
        session, corporation=CORP, as_at=datetime(2023, 6, 27), incidents_path=path
    )

    reset_registry()
    ensure_default_modules_registered()

    sitreps = get_module("sitreps").run_metric(
        "incident_count", {"corporation": CORP}, session
    )
    survey123 = get_module("survey123").run_metric(
        "incident_count", {"corporation": CORP}, session
    )

    assert sitreps[0].value == 1
    assert sitreps[0].breakdown == {"landslide": 1}
    assert survey123[0].value == 1
    assert survey123[0].breakdown == {"fire": 1}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend && .venv/bin/python -m pytest tests/test_field_observations_split.py -v`
Expected: FAIL — `ImportError: cannot import name 'FieldObservation'`

- [ ] **Step 3: Rename the model and drop `source`**

In `apps/backend/app/modules/survey123/models.py`:
- Rename `class Incident(Base)` to `class FieldObservation(Base)`.
- Change `__tablename__ = "incidents"` to `__tablename__ = "field_observations"`.
- Delete the `source` column line entirely.
- Add at the end of the class:

```python
    @property
    def record_ref(self) -> str:
        return self.global_id
```

- [ ] **Step 4: Update every reference**

Run this to find them all:

```bash
cd apps/backend && grep -rn "\bIncident\b" app tests --include=*.py
```

Update each: `app/modules/survey123/ingest.py`, `app/modules/survey123/metrics.py` (including the `model=Incident` defaults from Task 6 → `model=FieldObservation`), and the test files `test_ingest.py`, `test_models.py`, `test_metrics_*.py`, `test_survey123_module.py`, `test_survey123_metrics_dispatch.py`, `test_db.py`.

In `app/modules/survey123/module.py`, drop the injected source:

```python
    def run_metric(self, name: str, params: dict, session: Session) -> list[Fact]:
        fn = METRIC_FUNCTIONS.get(name)
        if fn is None:
            raise ValueError(f"unknown metric for survey123: {name}")
        return fn(params, session, FieldObservation)
```

In `app/mcp_server/survey123_server.py`, line 16, change `metric_fn(params, session)` to `metric_fn(params, session, FieldObservation)` and add the import.

- [ ] **Step 5: Point the sitreps module at SitrepIncident**

Replace `run_metric` in `apps/backend/app/modules/sitreps/module.py`:

```python
    def run_metric(self, name: str, params: dict, session: Session) -> list[Fact]:
        fn = METRIC_FUNCTIONS.get(name)
        if fn is None:
            raise ValueError(f"unknown metric for sitreps: {name}")
        return fn(params, session, SitrepIncident)
```

Add `from app.modules.sitreps.models import SitrepIncident` to its imports, and replace the `ingest` method body:

```python
    def ingest(self, file_path: Path) -> IngestResult:
        raise NotImplementedError(
            "sitreps data arrives as a submission (corporation, as-at time and "
            "up to two CSVs); use POST /submissions or the 'submissions create' "
            "CLI command instead"
        )
```

- [ ] **Step 6: Write the migration**

Create `apps/backend/alembic/versions/e2b5c8d03f21_split_field_observations.py`:

```python
"""rename incidents to field_observations and move sitrep rows out

Revision ID: e2b5c8d03f21
Revises: d1a4b7c92e10
"""

from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e2b5c8d03f21"
down_revision: Union[str, Sequence[str], None] = "d1a4b7c92e10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.rename_table("incidents", "field_observations")

    # Move any existing sitrep-sourced rows into their own table under one
    # synthetic backfill submission per corporation. These predate events, so
    # they carry no event and alert_level 'none'.
    connection = op.get_bind()
    # A Python datetime, not sa.func.now(): a SQL function cannot be passed as a
    # bound parameter value.
    now = datetime.now(timezone.utc)
    corporations = [
        r[0]
        for r in connection.execute(
            sa.text(
                "SELECT DISTINCT corporation FROM field_observations "
                "WHERE source = 'sitreps' AND corporation IS NOT NULL"
            )
        )
    ]
    for corporation in corporations:
        connection.execute(
            sa.text(
                "INSERT INTO submissions "
                "(corporation, event_id, as_at, alert_level, sequence_no, source_file, ingested_at) "
                "VALUES (:corp, NULL, :now, 'none', 1, 'backfill', :now)"
            ),
            {"corp": corporation, "now": now},
        )
        submission_id = connection.execute(
            sa.text(
                "SELECT id FROM submissions WHERE corporation = :corp "
                "AND source_file = 'backfill' ORDER BY id DESC LIMIT 1"
            ),
            {"corp": corporation},
        ).scalar()
        connection.execute(
            sa.text(
                "INSERT INTO sitrep_incidents "
                "(submission_id, corporation, event_id, row_id, community, street, "
                " incident_type, raw_incident_type, incident_summary, event_date, "
                " injuries_occurred, injuries_count, deaths_occurred, deaths_count, "
                " building_damage, special_needs_occupants, estimated_damage_cost, "
                " action_taken, follow_up_flags, ingested_at) "
                "SELECT :sid, corporation, NULL, CAST(object_id AS VARCHAR), community, street, "
                " incident_type, raw_incident_type, incident_summary, event_date, "
                " injuries_occurred, injuries_count, deaths_occurred, deaths_count, "
                " building_damage, special_needs_occupants, estimated_damage_cost, "
                " action_taken, follow_up_flags, ingested_at "
                "FROM field_observations WHERE source = 'sitreps' AND corporation = :corp"
            ),
            {"sid": submission_id, "corp": corporation},
        )

    connection.execute(sa.text("DELETE FROM field_observations WHERE source = 'sitreps'"))

    # batch_alter_table so this works on SQLite (which needs a table rebuild for
    # DROP COLUMN on older versions) as well as Postgres.
    with op.batch_alter_table("field_observations") as batch:
        batch.drop_column("source")


def downgrade() -> None:
    with op.batch_alter_table("field_observations") as batch:
        batch.add_column(
            sa.Column("source", sa.String(), nullable=False, server_default="survey123")
        )
    op.rename_table("field_observations", "incidents")
```

- [ ] **Step 7: Run the full suite**

Run: `cd apps/backend && .venv/bin/python -m pytest -q`
Expected: 2 failed (pre-existing `tests/test_llm.py`), everything else passing.

- [ ] **Step 8: Verify the migration chain end to end**

Run: `cd apps/backend && rm -f /tmp/mig_check.db && DATABASE_URL=sqlite:////tmp/mig_check.db .venv/bin/python -m alembic upgrade head && DATABASE_URL=sqlite:////tmp/mig_check.db .venv/bin/python -m alembic check`
Expected: upgrade succeeds to `e2b5c8d03f21`; check reports "No new upgrade operations detected."

- [ ] **Step 9: Commit**

```bash
cd apps/backend
git add -A app alembic tests
git commit -m "schema: split field_observations from sitrep_incidents"
```

---

## Task 8: Submission and event API and CLI

**Files:**
- Create: `apps/backend/app/api/submissions.py`
- Modify: `apps/backend/app/api/ingest.py`, `apps/backend/app/__init__.py`, `apps/backend/cli.py`
- Test: `apps/backend/tests/test_api_submissions.py`
- Modify: `apps/backend/tests/test_api_ingest.py`, `apps/backend/tests/test_cli_sitreps.py`

**Interfaces:**
- Consumes: Task 2 store, Task 5 `ingest_submission`.
- Produces: `POST /events`, `GET /events?corporation=`, `POST /submissions` (multipart), CLI `submissions create`.

- [ ] **Step 1: Write the failing test**

Create `apps/backend/tests/test_api_submissions.py`:

```python
import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import create_app
from app.core.registry import reset_registry
from app.db import Base, engine

CORP = "diego_martin_regional_corporati"
DEV_DB_PATH = Path(__file__).parent.parent / "dev.db"


# Mirrors the convention already used by tests/test_api_ingest.py and
# tests/test_api_overview.py — a per-test clean DB and registry, so API tests
# do not leak state into each other regardless of ordering.
@pytest.fixture(autouse=True)
def _clean_registry():
    reset_registry()
    engine.dispose()
    if DEV_DB_PATH.exists():
        DEV_DB_PATH.unlink()
    yield
    reset_registry()
    engine.dispose()
    if DEV_DB_PATH.exists():
        DEV_DB_PATH.unlink()


def client() -> TestClient:
    import app.modules.sitreps.models  # noqa: F401
    import app.modules.survey123.models  # noqa: F401

    Base.metadata.create_all(engine)
    return TestClient(create_app())


def test_create_and_list_events():
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
    assert created.status_code == 201
    event_id = created.json()["id"]

    listed = c.get("/events", params={"corporation": CORP})
    assert listed.status_code == 200
    assert [e["id"] for e in listed.json()] == [event_id]


def test_events_are_scoped_by_corporation():
    c = client()
    c.post(
        "/events",
        json={
            "corporation": "siparia_regional_corporation",
            "title": "Theirs",
            "hazard_type": "flood",
            "started_at": "2023-06-27T00:00:00",
        },
    )

    listed = c.get("/events", params={"corporation": "arima_borough_corporation"})
    assert listed.json() == []


def test_post_submission_with_both_files():
    c = client()
    incidents = "Row ID,Incident Type,Date of Event\n1,fallen_tree,2023-06-27\n"
    logs = "Category,Statement,Item,Quantity,Unit,Status\nresource,200 sandbags available,sandbags,200,bags,available\n"

    response = c.post(
        "/submissions",
        data={
            "corporation": CORP,
            "as_at": "2023-06-30T16:00:00",
            "alert_level": "discontinued",
            "present_activity": "Adverse Weather Alert",
            "situation_overview": "Heavy rainfall affected the Borough.",
        },
        files={
            "incidents_file": ("incidents.csv", io.BytesIO(incidents.encode()), "text/csv"),
            "logs_file": ("logs.csv", io.BytesIO(logs.encode()), "text/csv"),
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["incidents_inserted"] == 1
    assert body["logs_inserted"] == 1
    assert body["row_errors"] == []
    assert body["pii_columns_dropped"] == ["Name of Person", "Contact Information"]


def test_post_submission_reports_row_errors_without_failing():
    c = client()
    incidents = "Row ID,Incident Type,Date of Event\n,landslide,2023-06-27\n2,fire,2023-06-28\n"

    response = c.post(
        "/submissions",
        data={"corporation": CORP, "as_at": "2023-07-01T09:00:00"},
        files={"incidents_file": ("incidents.csv", io.BytesIO(incidents.encode()), "text/csv")},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["incidents_inserted"] == 1
    assert body["row_errors"] == [
        {"file": "incidents", "row_number": 1, "reason": "Row ID is required"}
    ]


def test_post_submission_rejects_an_unknown_corporation():
    c = client()

    response = c.post(
        "/submissions",
        data={"corporation": "not_a_corporation", "as_at": "2023-07-01T09:00:00"},
    )

    assert response.status_code == 400
    assert "corporation" in response.json()["detail"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend && .venv/bin/python -m pytest tests/test_api_submissions.py -v`
Expected: FAIL — 404 on `/events`, since the router does not exist.

- [ ] **Step 3: Write the API**

Create `apps/backend/app/api/submissions.py`:

```python
import tempfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.contracts import SubmissionIngestResult
from app.db import get_session
from app.modules.sitreps.ingest import ingest_submission
from app.modules.sitreps.models import ALERT_LEVELS, HAZARD_TYPES
from app.modules.sitreps.store import create_event, get_event, list_events
from app.modules.survey123.normalize import CANONICAL_CORPORATIONS

router = APIRouter()


class CreateEventRequest(BaseModel):
    corporation: str
    title: str
    hazard_type: str
    started_at: datetime
    ended_at: datetime | None = None


class EventSummary(BaseModel):
    id: int
    corporation: str
    title: str
    hazard_type: str
    started_at: datetime
    ended_at: datetime | None


def _require_corporation(corporation: str) -> str:
    if corporation not in CANONICAL_CORPORATIONS:
        raise HTTPException(
            status_code=400, detail=f"unknown corporation: {corporation}"
        )
    return corporation


@router.post("/events", response_model=EventSummary, status_code=201)
def post_event(
    request: CreateEventRequest, session: Session = Depends(get_session)
) -> EventSummary:
    _require_corporation(request.corporation)
    if request.hazard_type not in HAZARD_TYPES:
        raise HTTPException(
            status_code=400, detail=f"unknown hazard_type: {request.hazard_type}"
        )
    event = create_event(
        session,
        corporation=request.corporation,
        title=request.title,
        hazard_type=request.hazard_type,
        started_at=request.started_at,
        ended_at=request.ended_at,
    )
    return EventSummary.model_validate(event, from_attributes=True)


@router.get("/events", response_model=list[EventSummary])
def get_events(
    corporation: str, session: Session = Depends(get_session)
) -> list[EventSummary]:
    return [
        EventSummary.model_validate(e, from_attributes=True)
        for e in list_events(session, corporation)
    ]


async def _spool(upload: UploadFile | None) -> Path | None:
    if upload is None:
        return None
    contents = await upload.read()
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
        tmp.write(contents)
        return Path(tmp.name)


@router.post("/submissions", response_model=SubmissionIngestResult, status_code=201)
async def post_submission(
    corporation: str = Form(...),
    as_at: datetime = Form(...),
    event_id: int | None = Form(None),
    alert_level: str = Form("none"),
    present_activity: str | None = Form(None),
    situation_overview: str | None = Form(None),
    incidents_file: UploadFile | None = None,
    logs_file: UploadFile | None = None,
    session: Session = Depends(get_session),
) -> SubmissionIngestResult:
    _require_corporation(corporation)
    if alert_level not in ALERT_LEVELS:
        raise HTTPException(status_code=400, detail=f"unknown alert_level: {alert_level}")
    if event_id is not None:
        event = get_event(session, event_id)
        if event is None or event.corporation != corporation:
            raise HTTPException(
                status_code=404, detail=f"event not found for this corporation: {event_id}"
            )

    incidents_path = await _spool(incidents_file)
    logs_path = await _spool(logs_file)
    try:
        return ingest_submission(
            session,
            corporation=corporation,
            as_at=as_at,
            event_id=event_id,
            alert_level=alert_level,
            present_activity=present_activity,
            situation_overview=situation_overview,
            incidents_path=incidents_path,
            logs_path=logs_path,
        )
    finally:
        for path in (incidents_path, logs_path):
            if path is not None:
                path.unlink(missing_ok=True)
```

- [ ] **Step 4: Register the router**

In `apps/backend/app/__init__.py`, add the import and include it after `ingest_router`:

```python
from app.api.submissions import router as submissions_router
```

```python
    app.include_router(submissions_router)
```

- [ ] **Step 5: Cover the retired /ingest sitreps path**

Task 5 already removed the sitreps branch from `apps/backend/app/api/ingest.py` and replaced it with an explicit 400. Verify that is still in place, then update `tests/test_api_ingest.py`: drop the sitreps-corporation case and assert `POST /ingest/sitreps` returns 400 with a body pointing at `/submissions`. Follow the file's existing `_clean_registry` autouse-fixture convention — do not introduce `setup_module`.

- [ ] **Step 6: Add the CLI command**

In `apps/backend/cli.py`, replace the `ingest sitreps` command with:

Typer needs `Optional[...]` for nullable options — a bare `Path = None` is a type error it will not accept. Add `from typing import Optional` to `cli.py`'s imports.

```python
@app.command("submissions")
def create_submission_command(
    corporation: str,
    as_at: str,
    incidents: Optional[Path] = None,
    logs: Optional[Path] = None,
    event_id: Optional[int] = None,
    alert_level: str = "none",
) -> None:
    from datetime import datetime

    from app.db import SessionLocal
    from app.modules.sitreps.ingest import ingest_submission

    session = SessionLocal()
    try:
        result = ingest_submission(
            session,
            corporation=corporation,
            as_at=datetime.fromisoformat(as_at),
            event_id=event_id,
            alert_level=alert_level,
            incidents_path=incidents,
            logs_path=logs,
        )
    finally:
        session.close()

    typer.echo(result.model_dump_json(indent=2))
```

Task 5 deleted `tests/test_cli_sitreps.py` along with the command it tested. Create `tests/test_cli_submissions.py` in its place, invoking `submissions` with the new fixture files and asserting on `incidents_inserted` and `logs_inserted`.

- [ ] **Step 7: Run the full suite**

Run: `cd apps/backend && .venv/bin/python -m pytest -q`
Expected: 2 failed (pre-existing `tests/test_llm.py`), everything else passing.

- [ ] **Step 8: Commit**

```bash
cd apps/backend
git add -A app cli.py tests
git commit -m "api: add event and submission endpoints, retire the sitreps CSV ingest path"
```

---

## Done when

- `POST /events` and `GET /events?corporation=` create and list corp-owned events.
- `POST /submissions` accepts a corporation, an as-at time, an optional event, an alert level, prose fields, and up to two CSVs, landing atomically.
- A malformed row is reported with its row number and reason while every valid row still lands.
- Re-uploading a cumulative incident table under the same event supersedes rather than duplicates; without an event it does not.
- Situation logs accumulate per submission and are never superseded.
- `field_observations` holds only Survey123 rows and has no `source` column; `sitrep_incidents` holds only corp rows.
- Each module's metrics see only their own table.
- No PII reaches any table.
- Suite is green apart from the two pre-existing `tests/test_llm.py` failures.
