# DMCU Reporting — Step 2: Survey123 Ingestion + Normalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `survey123` data module completely: the `Incident` ORM model + migration, source-value normalization (corporation/incident-type/validation-status/occupants/follow-up), CSV ingestion with mandatory PII stripping and duplicate flagging, `DataModule` registration, and a CLI entry point — so `cli.py ingest survey123 <file>` ingests a real DMCU export end-to-end with zero PII persisted and zero silent data loss.

**Architecture:** Follows `PLAN.md` §4 exactly, relocated under `apps/backend/app/modules/survey123/` (this repo's monorepo convention, same relocation `docs/superpowers/plans/2026-07-14-dmcu-step1-skeleton.md` established for Step 1). This step adds one concrete `DataModule` — proving the Step 1 registry abstraction holds for a real module, not just the `FakeModule` test double. No metrics are added yet (`list_metrics()` returns `[]`) — metrics are Step 3.

**Tech Stack:** Same as Step 1 (Python 3.13, FastAPI, SQLAlchemy 2.0-style, Pydantic v2, pydantic-settings, Alembic, SQLite for tests/dev, PostgreSQL via docker-compose), plus Typer (already installed in Step 1) for the CLI. No new dependencies are required — ingestion is CSV-only via Python's standard library `csv` module (see deviation note below).

## Global Constraints

- Everything in `docs/superpowers/plans/2026-07-14-dmcu-step1-skeleton.md`'s Global Constraints still applies (Python 3.13+, Pydantic v2, SQLAlchemy 2.0-style — no legacy `Query` API, `apps/backend/` location, every metric a pure function of `(params, session)`).
- **PII policy is non-negotiable** (`PLAN.md` §4.2): the following raw source columns must never be written to the database: `Name of Person`, `Contact Information`, `Identification Card Number`, `Name of Second Person`, `Second Contact Information`, `Second Identification Card Number`, `Please list the names of the occupants and their relation`. A unit test must assert the `Incident` model has no columns shaped like these fields.
- Deduplication uses only a salted SHA-256 hash of the ID card number (`dedup_hash`) — never the raw value — per `PLAN.md` §4.2.
- `Address` is reduced to `street` (first comma-segment) + the existing `Community` column — never the full address (`PLAN.md` §4.2).
- Normalization rules (corporation, incident type) live as explicit dicts/sets with an **UNMAPPED fallback that logs and preserves the raw value in a `raw_*` column** — never crash ingestion on a new value, never silently coerce (`PLAN.md` §4.4, §7).
- Ingestion is idempotent by `global_id` (upsert; newer `EditDate` wins) (`PLAN.md` §4.5).
- Duplicate rows are flagged (`is_duplicate = True`), never deleted (`PLAN.md` §4.1).
- **Deviation from `PLAN.md` (confirmed with the project owner):** ingestion is **CSV-only**. All files ingested in this project come from a `csvkit in2csv` conversion of the Survey123 export, never raw `.xlsx`. This drops the `openpyxl`/xlsx-parsing path `PLAN.md` §4.5 mentions — there is no xlsx code to write. The CSV format's actual characteristics (verified against a real 14,942-row export converted with `in2csv`) are: dates are ISO 8601 strings (`"2021-04-21T15:36:49.243000"`), booleans are the strings `"True"`/`"False"` (not `"yes"`/`"no"`), and `in2csv` auto-renames duplicate source headers (`Other Agency` → `Other Agency`, `Other Agency_2`, `Other Agency_3`; `Community` → `Community`, `Community_2`).
- **Deviation from `PLAN.md` (confirmed with the project owner):** the `follow_up_flags` structure uses `further_assessment_required` in place of `PLAN.md`'s `shelter_relocation`, because the real `Follow Up Recommendation` column only ever contains the tokens `Forward_to_Other_Agency`, `Supply_Relief_Items_`, `Further_Assessment_Required_`, `other` — there is no shelter-relocation signal anywhere in the source data.
- **Confirmed with the project owner:** duplicate detection via repeated ID + event-date checks both the current ingest batch **and** rows already persisted in the database from prior ingests (not file-local only).
- Real PII-bearing data (`apps/backend/output.csv`, any `*.raw.csv`) must never be committed — already enforced via `apps/backend/.gitignore` (added this session). The only committed fixture is `apps/backend/fixtures/sample_small.csv` (30 hand-crafted rows, fake PII values only, already created on disk during planning — see Task 3).
- Money: `estimated_damage_cost` stored as `Numeric`/`Decimal`, currency assumed TTD (`PLAN.md` §7).
- Timezone: store UTC (`ingested_at` uses `datetime.now(timezone.utc)`), report in `America/Port_of_Spain` — rendering to local time is a later step's concern (`PLAN.md` §7).
- Definition of done for this plan (`PLAN.md` §6 Step 2, adapted for the CSV-only deviation): `cli.py ingest survey123 <file>` against the real converted export yields ~14,942 rows, 14 corporations mapped + a `(no corporation recorded)` bucket for blanks, the banned-columns test passes, duplicate-marker rows are flagged, and re-ingesting the same file is a no-op.
- **Out of scope for this plan (do not build):** the `POST /ingest/survey123` HTTP endpoint (`PLAN.md` §4.5, §5.5). `PLAN.md`'s own Build Order (§6) puts the API/persistence layer in Step 6 ("full flow via HTTP"); Step 2's deliverable is CLI ingestion only, matching its literal Step 2 bullet ("...CLI ingest").

---

### Task 1: `Incident` ORM model + Alembic migration

**Files:**
- Create: `apps/backend/app/modules/__init__.py`
- Create: `apps/backend/app/modules/survey123/__init__.py`
- Create: `apps/backend/app/modules/survey123/models.py`
- Modify: `apps/backend/alembic/env.py`
- Create: `apps/backend/alembic/versions/<autogenerated>.py` (via `alembic revision --autogenerate` — do not hand-write)
- Create: `apps/backend/tests/test_models.py`

**Interfaces:**
- Consumes: `app.db.Base` (Step 1 Task 2).
- Produces: `app.modules.survey123.models.Incident`, a SQLAlchemy 2.0 `Base` subclass, `__tablename__ = "incidents"`, with exactly these mapped columns (name: type): `id: int` (pk), `global_id: str` (unique), `object_id: int`, `corporation: str | None`, `raw_corporation: str | None`, `community: str | None`, `street: str | None`, `incident_type: str | None`, `raw_incident_type: str | None`, `incident_type_other: str | None`, `incident_summary: str | None`, `event_date: datetime | None`, `event_time: str | None`, `assessment_date: datetime | None`, `creation_date: datetime | None`, `edit_date: datetime | None`, `occupants_count: int | None`, `injuries_occurred: bool`, `injuries_count: int | None`, `deaths_occurred: bool`, `deaths_count: int | None`, `building_damage: str | None`, `crops_livestock: str | None`, `personal_items: str | None`, `furniture_appliances: str | None`, `action_taken: str | None`, `relief_items: str | None`, `shelter: str | None`, `special_needs_occupants: int | None`, `estimated_damage_cost: Decimal | None`, `follow_up: str | None`, `follow_up_flags: dict` (JSON), `validation_status: str`, `is_duplicate: bool`, `duplicate_reason: str | None`, `flood_type: str | None`, `flood_trigger: str | None`, `flood_height: str | None`, `lon: float | None`, `lat: float | None`, `officer_name: str | None`, `officer_position: str | None`, `dedup_hash: str | None`, `source_file: str`, `ingested_at: datetime`. Tasks 3 and 4 construct `Incident(**fields)` using exactly these field names as keyword arguments.
- `raw_corporation`/`raw_incident_type` and `edit_date`/`is_duplicate`/`duplicate_reason`/`dedup_hash`/`source_file`/`ingested_at` are additions beyond `PLAN.md` §4.3's literal field list, required to implement the UNMAPPED-fallback and idempotent-upsert-with-duplicate-flagging behaviors §4.1/§4.4/§4.5 explicitly specify.

- [ ] **Step 1: Write `app/modules/survey123/models.py`**

Create `apps/backend/app/modules/__init__.py` (empty file) and `apps/backend/app/modules/survey123/__init__.py` (empty file).

Create `apps/backend/app/modules/survey123/models.py`:

```python
from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(primary_key=True)
    global_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    object_id: Mapped[int] = mapped_column(Integer)

    corporation: Mapped[str | None] = mapped_column(String, nullable=True)
    raw_corporation: Mapped[str | None] = mapped_column(String, nullable=True)
    community: Mapped[str | None] = mapped_column(String, nullable=True)
    street: Mapped[str | None] = mapped_column(String, nullable=True)

    incident_type: Mapped[str | None] = mapped_column(String, nullable=True)
    raw_incident_type: Mapped[str | None] = mapped_column(String, nullable=True)
    incident_type_other: Mapped[str | None] = mapped_column(String, nullable=True)

    incident_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    event_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    event_time: Mapped[str | None] = mapped_column(String, nullable=True)
    assessment_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    creation_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    edit_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    occupants_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    injuries_occurred: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    injuries_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deaths_occurred: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deaths_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    building_damage: Mapped[str | None] = mapped_column(Text, nullable=True)
    crops_livestock: Mapped[str | None] = mapped_column(Text, nullable=True)
    personal_items: Mapped[str | None] = mapped_column(Text, nullable=True)
    furniture_appliances: Mapped[str | None] = mapped_column(Text, nullable=True)

    action_taken: Mapped[str | None] = mapped_column(String, nullable=True)
    relief_items: Mapped[str | None] = mapped_column(Text, nullable=True)

    shelter: Mapped[str | None] = mapped_column(Text, nullable=True)
    special_needs_occupants: Mapped[int | None] = mapped_column(Integer, nullable=True)

    estimated_damage_cost: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)

    follow_up: Mapped[str | None] = mapped_column(String, nullable=True)
    follow_up_flags: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    validation_status: Mapped[str] = mapped_column(String, nullable=False)

    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    duplicate_reason: Mapped[str | None] = mapped_column(String, nullable=True)

    flood_type: Mapped[str | None] = mapped_column(String, nullable=True)
    flood_trigger: Mapped[str | None] = mapped_column(String, nullable=True)
    flood_height: Mapped[str | None] = mapped_column(String, nullable=True)

    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)

    officer_name: Mapped[str | None] = mapped_column(String, nullable=True)
    officer_position: Mapped[str | None] = mapped_column(String, nullable=True)

    dedup_hash: Mapped[str | None] = mapped_column(String, nullable=True, index=True)

    source_file: Mapped[str] = mapped_column(String, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
```

- [ ] **Step 2: Wire the model into Alembic's autogenerate metadata**

In `apps/backend/alembic/env.py`, add one import so `Incident` registers with `Base.metadata` before `target_metadata = Base.metadata` runs. The line goes immediately after the existing `from app.db import Base`:

```python
from app.config import settings
from app.db import Base
from app.modules.survey123 import models as survey123_models  # noqa: F401
```

Leave the rest of `env.py` (from Step 1) unchanged.

- [ ] **Step 3: Generate the migration**

```bash
cd apps/backend
rm -f dev.db
uv run alembic revision --autogenerate -m "create incidents table"
```

Expected: exits 0, creates one new file under `apps/backend/alembic/versions/` containing an `upgrade()` that creates the `incidents` table with all the columns from Step 1, and a `downgrade()` that drops it. Do not hand-edit this file's column definitions — if autogenerate produces something clearly wrong (wrong type, missing column), that means `models.py` has a mistake; fix `models.py` and regenerate.

- [ ] **Step 4: Verify the migration applies and reverses cleanly**

```bash
cd apps/backend
uv run alembic upgrade head
uv run alembic downgrade base
uv run alembic upgrade head
rm -f dev.db
```

Expected: all three commands exit 0 with no traceback.

- [ ] **Step 5: Write the failing tests**

Create `apps/backend/tests/test_models.py`:

```python
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.db import Base, make_engine
from app.modules.survey123.models import Incident

BANNED_COLUMN_NAMES = {
    "name_of_person",
    "person_name",
    "contact_information",
    "contact_info",
    "identification_card_number",
    "id_card_number",
    "name_of_second_person",
    "second_person_name",
    "second_contact_information",
    "second_contact_info",
    "second_identification_card_number",
    "second_id_card_number",
    "occupant_names",
    "occupant_names_and_relation",
}


def test_incident_model_has_no_pii_columns():
    columns = set(Incident.__table__.columns.keys())
    overlap = columns & BANNED_COLUMN_NAMES

    assert not overlap, f"PII-shaped columns found on Incident model: {overlap}"


def test_incident_round_trips_through_sqlite(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    incident = Incident(
        global_id="GUID-TEST",
        object_id=1,
        corporation="sangre_grande_regional_corporat",
        raw_corporation=None,
        community="Sangre Grande",
        street="Flood Street",
        incident_type="flooding_",
        raw_incident_type=None,
        incident_type_other=None,
        incident_summary="Test incident",
        event_date=datetime(2024, 6, 1, tzinfo=timezone.utc),
        event_time="06:00",
        assessment_date=None,
        creation_date=datetime(2024, 6, 1, tzinfo=timezone.utc),
        edit_date=datetime(2024, 6, 1, tzinfo=timezone.utc),
        occupants_count=3,
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
        follow_up_flags={
            "relief_supplied": False,
            "forwarded_to_agency": False,
            "further_assessment_required": False,
            "other": False,
        },
        validation_status="validated",
        is_duplicate=False,
        duplicate_reason=None,
        flood_type=None,
        flood_trigger=None,
        flood_height=None,
        lon=-61.13,
        lat=10.58,
        officer_name="Kevin Jagassar",
        officer_position="DMU Field Officer",
        dedup_hash=None,
        source_file="test.csv",
        ingested_at=datetime(2024, 6, 1, tzinfo=timezone.utc),
    )
    session.add(incident)
    session.commit()

    fetched = session.execute(select(Incident).where(Incident.global_id == "GUID-TEST")).scalar_one()

    assert fetched.corporation == "sangre_grande_regional_corporat"
    assert fetched.follow_up_flags == {
        "relief_supplied": False,
        "forwarded_to_agency": False,
        "further_assessment_required": False,
        "other": False,
    }
    session.close()
```

- [ ] **Step 6: Run the tests to verify they fail, then pass**

```bash
cd apps/backend
uv run pytest tests/test_models.py -v
```

First run (before Step 1's `models.py` exists) is expected to FAIL with `ModuleNotFoundError`. After completing Steps 1–5, re-run and expect `2 passed`.

- [ ] **Step 7: Run the full suite**

```bash
cd apps/backend
uv run pytest -v
```

Expected: `19 passed` (the 17 from Step 1, plus these 2).

- [ ] **Step 8: Commit**

```bash
git add apps/backend/app/modules/__init__.py apps/backend/app/modules/survey123/__init__.py \
        apps/backend/app/modules/survey123/models.py apps/backend/alembic/env.py \
        apps/backend/alembic/versions/ apps/backend/tests/test_models.py
git commit -m "backend: add Incident model and migration"
```

---

### Task 2: `normalize.py` — value normalization

**Files:**
- Create: `apps/backend/app/modules/survey123/normalize.py`
- Create: `apps/backend/tests/test_normalize.py`

**Interfaces:**
- Produces: `normalize_corporation(raw: str | None) -> tuple[str | None, str | None]` (returns `(corporation, raw_corporation_if_unmapped)`), `normalize_incident_type(raw: str | None) -> tuple[str | None, str | None]` (same shape), `normalize_validation_status(raw: str | None) -> str` (always `"validated"` or `"pending"`), `parse_occupants(household_occupants_raw: str | None, overflow_raw: str | None) -> int | None`, `parse_follow_up_flags(raw: str | None) -> dict[str, bool]` (keys always `relief_supplied`, `forwarded_to_agency`, `further_assessment_required`, `other`). Task 3's `parse_row` imports and calls all five.
- Corporation canonical values were derived from the real 14,942-row export: 14 corporations, each already appearing as a lowercase-truncated slug in the source data (case variants collapse via `.lower()`, no alias table needed). Incident type canonical values are the 8-value controlled vocabulary from `PLAN.md` §4.1, confirmed against the real data.

- [ ] **Step 1: Write the failing tests**

Create `apps/backend/tests/test_normalize.py`:

```python
import logging

from app.modules.survey123.normalize import (
    normalize_corporation,
    normalize_incident_type,
    normalize_validation_status,
    parse_follow_up_flags,
    parse_occupants,
)


def test_normalize_corporation_lowercases_known_variant():
    assert normalize_corporation("Sangre_Grande_Regional_Corporat") == (
        "sangre_grande_regional_corporat",
        None,
    )


def test_normalize_corporation_collapses_case_variant():
    assert normalize_corporation("mayaro_rio_claro_regional_corpo") == (
        "mayaro_rio_claro_regional_corpo",
        None,
    )
    assert normalize_corporation("Mayaro_Rio_Claro_Regional_Corpo") == (
        "mayaro_rio_claro_regional_corpo",
        None,
    )


def test_normalize_corporation_blank_is_none():
    assert normalize_corporation("") == (None, None)
    assert normalize_corporation(None) == (None, None)


def test_normalize_corporation_unmapped_logs_and_preserves_raw(caplog):
    with caplog.at_level(logging.WARNING):
        result = normalize_corporation("Unknown_Corp_Typo")

    assert result == ("unmapped", "Unknown_Corp_Typo")
    assert "Unknown_Corp_Typo" in caplog.text


def test_normalize_incident_type_lowercases_known_value():
    assert normalize_incident_type("Flooding_") == ("flooding_", None)
    assert normalize_incident_type("Over Grown Tree") == ("over grown tree", None)


def test_normalize_incident_type_unmapped_logs_and_preserves_raw(caplog):
    with caplog.at_level(logging.WARNING):
        result = normalize_incident_type("Volcanic_Eruption_Typo")

    assert result == ("unmapped", "Volcanic_Eruption_Typo")
    assert "Volcanic_Eruption_Typo" in caplog.text


def test_normalize_validation_status_validated():
    assert normalize_validation_status("Validated") == "validated"


def test_normalize_validation_status_blank_is_pending():
    assert normalize_validation_status("") == "pending"
    assert normalize_validation_status(None) == "pending"


def test_normalize_validation_status_unexpected_value_defaults_pending(caplog):
    with caplog.at_level(logging.WARNING):
        result = normalize_validation_status("Rejected")

    assert result == "pending"
    assert "Rejected" in caplog.text


def test_parse_occupants_direct_digit():
    assert parse_occupants("3", "") == 3


def test_parse_occupants_blank_is_none():
    assert parse_occupants("", "") is None
    assert parse_occupants(None, None) is None


def test_parse_occupants_other_with_numeric_overflow():
    assert parse_occupants("other", "9") == 9


def test_parse_occupants_other_with_text_overflow():
    assert parse_occupants("other", "12 persons") == 12


def test_parse_occupants_other_with_unparseable_overflow_logs(caplog):
    with caplog.at_level(logging.WARNING):
        result = parse_occupants("other", "many")

    assert result is None
    assert "many" in caplog.text


def test_parse_follow_up_flags_blank_all_false():
    assert parse_follow_up_flags("") == {
        "relief_supplied": False,
        "forwarded_to_agency": False,
        "further_assessment_required": False,
        "other": False,
    }


def test_parse_follow_up_flags_single_token():
    assert parse_follow_up_flags("Supply_Relief_Items_") == {
        "relief_supplied": True,
        "forwarded_to_agency": False,
        "further_assessment_required": False,
        "other": False,
    }


def test_parse_follow_up_flags_multi_token():
    assert parse_follow_up_flags(
        "Supply_Relief_Items_,Forward_to_Other_Agency,Further_Assessment_Required_"
    ) == {
        "relief_supplied": True,
        "forwarded_to_agency": True,
        "further_assessment_required": True,
        "other": False,
    }


def test_parse_follow_up_flags_unmapped_token_logs_and_ignores(caplog):
    with caplog.at_level(logging.WARNING):
        result = parse_follow_up_flags("Some_New_Token_")

    assert result == {
        "relief_supplied": False,
        "forwarded_to_agency": False,
        "further_assessment_required": False,
        "other": False,
    }
    assert "Some_New_Token_" in caplog.text
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd apps/backend
uv run pytest tests/test_normalize.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.modules.survey123.normalize'`.

- [ ] **Step 3: Implement `app/modules/survey123/normalize.py`**

```python
import logging
import re

logger = logging.getLogger(__name__)

CANONICAL_CORPORATIONS = frozenset(
    {
        "san_juan_laventille_regional_co",
        "tunapuna_piarco_regional_corpor",
        "sangre_grande_regional_corporat",
        "penal_debe_regional_corporation",
        "couva_tabaquite_talparo_regiona",
        "mayaro_rio_claro_regional_corpo",
        "siparia_regional_corporation",
        "princes_town_regional_corporati",
        "diego_martin_regional_corporati",
        "san_fernando_city_corporation",
        "chaguanas_borough_corporation",
        "port_of_spain_city_corporation",
        "point_fortin_borough_corporatio",
        "arima_borough_corporation",
    }
)

CANONICAL_INCIDENT_TYPES = frozenset(
    {
        "flooding_",
        "other",
        "landslide",
        "over grown tree",
        "fire",
        "blown_off_roof",
        "fallen_tree",
        "earthquake",
    }
)

FOLLOW_UP_TOKEN_MAP = {
    "Supply_Relief_Items_": "relief_supplied",
    "Forward_to_Other_Agency": "forwarded_to_agency",
    "Further_Assessment_Required_": "further_assessment_required",
    "other": "other",
}

OVERFLOW_PERSONS_RE = re.compile(r"^(\d+)\s*persons?$", re.IGNORECASE)


def normalize_corporation(raw: str | None) -> tuple[str | None, str | None]:
    cleaned = (raw or "").strip()
    if not cleaned:
        return None, None
    lowered = cleaned.lower()
    if lowered in CANONICAL_CORPORATIONS:
        return lowered, None
    logger.warning("unmapped Municipal Boundary value: %r", cleaned)
    return "unmapped", cleaned


def normalize_incident_type(raw: str | None) -> tuple[str | None, str | None]:
    cleaned = (raw or "").strip()
    if not cleaned:
        return None, None
    lowered = cleaned.lower()
    if lowered in CANONICAL_INCIDENT_TYPES:
        return lowered, None
    logger.warning("unmapped Incident Type value: %r", cleaned)
    return "unmapped", cleaned


def normalize_validation_status(raw: str | None) -> str:
    cleaned = (raw or "").strip().lower()
    if cleaned == "validated":
        return "validated"
    if cleaned == "":
        return "pending"
    logger.warning("unexpected Validated/NotValidated value: %r", raw)
    return "pending"


def parse_occupants(household_occupants_raw: str | None, overflow_raw: str | None) -> int | None:
    cleaned = (household_occupants_raw or "").strip()
    if cleaned.isdigit():
        return int(cleaned)
    if cleaned.lower() == "other":
        overflow = (overflow_raw or "").strip()
        if overflow.isdigit():
            return int(overflow)
        match = OVERFLOW_PERSONS_RE.match(overflow)
        if match:
            return int(match.group(1))
        logger.warning("could not parse overflow occupants value: %r", overflow_raw)
        return None
    return None


def parse_follow_up_flags(raw: str | None) -> dict[str, bool]:
    flags = {
        "relief_supplied": False,
        "forwarded_to_agency": False,
        "further_assessment_required": False,
        "other": False,
    }
    cleaned = (raw or "").strip()
    if not cleaned:
        return flags
    for token in cleaned.split(","):
        token = token.strip()
        key = FOLLOW_UP_TOKEN_MAP.get(token)
        if key:
            flags[key] = True
        else:
            logger.warning("unmapped Follow Up Recommendation token: %r", token)
    return flags
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd apps/backend
uv run pytest tests/test_normalize.py -v
```

Expected: `18 passed`.

- [ ] **Step 5: Run the full suite**

```bash
cd apps/backend
uv run pytest -v
```

Expected: `37 passed`.

- [ ] **Step 6: Commit**

```bash
git add apps/backend/app/modules/survey123/normalize.py apps/backend/tests/test_normalize.py
git commit -m "backend: add survey123 value normalization"
```

---

### Task 3: `parse_row` — pure per-row CSV parsing + fixture

**Files:**
- Create: `apps/backend/app/modules/survey123/ingest.py`
- Add (already exists on disk, untracked — just `git add` it, do not modify its contents): `apps/backend/fixtures/sample_small.csv`
- Create: `apps/backend/tests/test_ingest_parse.py`

**Interfaces:**
- Consumes: `normalize_corporation`, `normalize_incident_type`, `normalize_validation_status`, `parse_occupants`, `parse_follow_up_flags` (Task 2).
- Produces: `PII_COLUMNS: list[str]` (the 7 banned source column names, in the exact order used everywhere in this plan), `parse_row(row: dict[str, str], salt: str) -> dict` (pure function: one raw CSV row dict → a dict of `Incident` field values, keyed by exactly the field names from Task 1's `Incident` model, excluding `id`, `is_duplicate`, `duplicate_reason`, `source_file`, `ingested_at` which Task 4's orchestration layer sets), `compute_dedup_hash(id_number_raw: str | None, salt: str) -> str | None`, `is_duplicate_marker(name_raw: str | None, summary_raw: str | None) -> bool`. Task 4 imports and calls all of these plus adds `ingest_csv` to the same file.
- **Note on the fixture:** `apps/backend/fixtures/sample_small.csv` already exists in the working tree (created during planning, using the exact same 78-column header `in2csv` produces, with realistic-but-fake data). It has 30 rows covering: two known corporations (15 rows `sangre_grande_regional_corporat`, 10 rows `san_fernando_city_corporation`), 4 rows with blank corporation, 1 row with an unmapped corporation (`Unknown_Corp_Typo`, `GlobalID=GUID-023`); 9 canonical incident types across the 8-value vocabulary plus 1 unmapped (`Volcanic_Eruption_Typo`, `GlobalID=GUID-024`); 21 `Validated` / 9 blank rows; 2 rows with the literal `"Duplicate entry"` marker in `Name of Person` (`GUID-025`, `GUID-026`); 2 rows sharing the same `Identification Card Number` (`19850315099`) and `Date of Event` without the marker (`GUID-027`, `GUID-028`); 2 rows exercising `Household Occupants=other` with numeric (`GUID-029`, overflow `9`) and text (`GUID-030`, overflow `"12 persons"`) formats in the overflow column. Every `Name of Person`/`Contact Information`/`Identification Card Number` value in the fixture is fake.

- [ ] **Step 1: Write the failing tests**

Create `apps/backend/tests/test_ingest_parse.py`:

```python
import logging

from app.modules.survey123.ingest import is_duplicate_marker, parse_row


def test_parse_row_never_includes_pii_values():
    row = {
        "GlobalID": "GUID-TEST",
        "ObjectID": "1",
        "Name of Person": "Real Name",
        "Contact Information": "8681234567",
        "Identification Card Number": "19900101999",
        "Name of Second Person": "Second Name",
        "Second Contact Information": "8687654321",
        "Second Identification Card Number": "19900101998",
        "Please list the names of the occupants and their relation": "Real Name (self)",
    }

    result = parse_row(row, salt="test-salt")

    serialized = " ".join(str(v) for v in result.values())
    for pii_value in [
        "Real Name",
        "8681234567",
        "19900101999",
        "Second Name",
        "8687654321",
        "19900101998",
    ]:
        assert pii_value not in serialized


def test_parse_row_maps_known_corporation_case_insensitively():
    row = {"GlobalID": "G1", "ObjectID": "1", "Municipal Boundary": "Sangre_Grande_Regional_Corporat"}

    result = parse_row(row, salt="s")

    assert result["corporation"] == "sangre_grande_regional_corporat"
    assert result["raw_corporation"] is None


def test_parse_row_blank_corporation_is_none():
    row = {"GlobalID": "G1", "ObjectID": "1", "Municipal Boundary": ""}

    result = parse_row(row, salt="s")

    assert result["corporation"] is None
    assert result["raw_corporation"] is None


def test_parse_row_unmapped_corporation_preserves_raw(caplog):
    row = {"GlobalID": "G1", "ObjectID": "1", "Municipal Boundary": "Unknown_Corp_Typo"}

    with caplog.at_level(logging.WARNING):
        result = parse_row(row, salt="s")

    assert result["corporation"] == "unmapped"
    assert result["raw_corporation"] == "Unknown_Corp_Typo"
    assert "Unknown_Corp_Typo" in caplog.text


def test_parse_row_occupants_other_with_numeric_overflow():
    row = {
        "GlobalID": "G1",
        "ObjectID": "1",
        "Household Occupants": "other",
        "If more than 6 persons - Household Occupants": "9",
    }

    result = parse_row(row, salt="s")

    assert result["occupants_count"] == 9


def test_parse_row_occupants_other_with_text_overflow():
    row = {
        "GlobalID": "G1",
        "ObjectID": "1",
        "Household Occupants": "other",
        "If more than 6 persons - Household Occupants": "12 persons",
    }

    result = parse_row(row, salt="s")

    assert result["occupants_count"] == 12


def test_parse_row_dedup_hash_stable_for_same_id_and_salt():
    row_a = {"GlobalID": "G1", "ObjectID": "1", "Identification Card Number": "19850315099"}
    row_b = {"GlobalID": "G2", "ObjectID": "2", "Identification Card Number": "19850315099"}

    result_a = parse_row(row_a, salt="fixed-salt")
    result_b = parse_row(row_b, salt="fixed-salt")

    assert result_a["dedup_hash"] == result_b["dedup_hash"]
    assert result_a["dedup_hash"] is not None


def test_parse_row_dedup_hash_none_when_id_blank():
    row = {"GlobalID": "G1", "ObjectID": "1"}

    result = parse_row(row, salt="s")

    assert result["dedup_hash"] is None


def test_parse_row_address_reduces_to_street():
    row = {"GlobalID": "G1", "ObjectID": "1", "Address": "#5 Ramlal Trace, Platanite Trace, Rochard Road"}

    result = parse_row(row, salt="s")

    assert result["street"] == "#5 Ramlal Trace"


def test_is_duplicate_marker_detects_literal_marker():
    assert is_duplicate_marker("Duplicate entry", None) is True
    assert is_duplicate_marker(None, "duplicate entry") is True
    assert is_duplicate_marker("Real Name", "Real summary") is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd apps/backend
uv run pytest tests/test_ingest_parse.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.modules.survey123.ingest'`.

- [ ] **Step 3: Implement `app/modules/survey123/ingest.py` (parsing layer only — orchestration is added in Task 4)**

```python
import hashlib
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation

from app.modules.survey123.normalize import (
    normalize_corporation,
    normalize_incident_type,
    normalize_validation_status,
    parse_follow_up_flags,
    parse_occupants,
)

logger = logging.getLogger(__name__)

PII_COLUMNS = [
    "Name of Person",
    "Contact Information",
    "Identification Card Number",
    "Name of Second Person",
    "Second Contact Information",
    "Second Identification Card Number",
    "Please list the names of the occupants and their relation",
]

DUPLICATE_MARKER = "duplicate entry"


def parse_bool(raw: str | None) -> bool:
    return (raw or "").strip().lower() == "true"


def parse_int(raw: str | None) -> int | None:
    cleaned = (raw or "").strip()
    return int(cleaned) if cleaned.isdigit() else None


def parse_float(raw: str | None) -> float | None:
    cleaned = (raw or "").strip()
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_decimal(raw: str | None) -> Decimal | None:
    cleaned = (raw or "").strip()
    if not cleaned:
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def parse_datetime(raw: str | None) -> datetime | None:
    cleaned = (raw or "").strip()
    if not cleaned:
        return None
    return datetime.fromisoformat(cleaned)


def compute_dedup_hash(id_number_raw: str | None, salt: str) -> str | None:
    cleaned = (id_number_raw or "").strip()
    if not cleaned:
        return None
    return hashlib.sha256((salt + cleaned).encode("utf-8")).hexdigest()


def is_duplicate_marker(name_raw: str | None, summary_raw: str | None) -> bool:
    return (name_raw or "").strip().lower() == DUPLICATE_MARKER or (
        summary_raw or ""
    ).strip().lower() == DUPLICATE_MARKER


def parse_row(row: dict[str, str], salt: str) -> dict:
    corporation, raw_corporation = normalize_corporation(row.get("Municipal Boundary"))
    incident_type, raw_incident_type = normalize_incident_type(row.get("Incident Type"))
    address = (row.get("Address") or "").strip()
    street = address.split(",")[0].strip() if address else None

    return {
        "global_id": row["GlobalID"].strip(),
        "object_id": int(row["ObjectID"]),
        "corporation": corporation,
        "raw_corporation": raw_corporation,
        "community": (row.get("Community") or "").strip() or None,
        "street": street or None,
        "incident_type": incident_type,
        "raw_incident_type": raw_incident_type,
        "incident_type_other": (row.get("Other - Incident Type") or "").strip() or None,
        "incident_summary": (row.get("Incident Summary") or "").strip() or None,
        "event_date": parse_datetime(row.get("Date of Event")),
        "event_time": (row.get("Time of Event") or "").strip() or None,
        "assessment_date": parse_datetime(row.get("Assessment Date")),
        "creation_date": parse_datetime(row.get("CreationDate")),
        "edit_date": parse_datetime(row.get("EditDate")),
        "occupants_count": parse_occupants(
            row.get("Household Occupants"), row.get("If more than 6 persons - Household Occupants")
        ),
        "injuries_occurred": parse_bool(row.get("Did any injuries occur?")),
        "injuries_count": parse_int(row.get("Injuries")),
        "deaths_occurred": parse_bool(row.get("Did any deaths occur?")),
        "deaths_count": parse_int(row.get("Deaths")),
        "building_damage": (row.get("Building Damage") or "").strip() or None,
        "crops_livestock": (row.get("Crops and Livestock") or "").strip() or None,
        "personal_items": (row.get("Personal Items") or "").strip() or None,
        "furniture_appliances": (row.get("Furniture and Appliances") or "").strip() or None,
        "action_taken": (row.get("Action Taken") or "").strip() or None,
        "relief_items": (row.get("Relief Items") or "").strip() or None,
        "shelter": (row.get("Shelter") or "").strip() or None,
        "special_needs_occupants": parse_int(row.get("Please indicate the number of special needs occupants")),
        "estimated_damage_cost": parse_decimal(row.get("Estimate Cost of Damage")),
        "follow_up": (row.get("Follow Up Recommendation") or "").strip() or None,
        "follow_up_flags": parse_follow_up_flags(row.get("Follow Up Recommendation")),
        "validation_status": normalize_validation_status(row.get("Validated/NotValidated")),
        "flood_type": (row.get("Flood Type") or "").strip() or None,
        "flood_trigger": (row.get("Flood Trigger") or "").strip() or None,
        "flood_height": (row.get("Flood Height") or "").strip() or None,
        "lon": parse_float(row.get("x")),
        "lat": parse_float(row.get("y")),
        "officer_name": (row.get("Name of Officer") or "").strip() or None,
        "officer_position": (row.get("Position") or "").strip() or None,
        "dedup_hash": compute_dedup_hash(row.get("Identification Card Number"), salt),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd apps/backend
uv run pytest tests/test_ingest_parse.py -v
```

Expected: `10 passed`.

- [ ] **Step 5: Add and verify the fixture**

```bash
cd apps/backend
python3 -c "
import csv
with open('fixtures/sample_small.csv', newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    rows = list(reader)
assert len(rows) == 30, len(rows)
assert len(reader.fieldnames) == 78, len(reader.fieldnames)
print('fixture OK:', len(rows), 'rows,', len(reader.fieldnames), 'columns')
"
```

Expected: `fixture OK: 30 rows, 78 columns`. If this fails, stop and report BLOCKED — do not regenerate or edit the fixture; it was hand-verified during planning and every downstream task's expected numbers depend on it exactly as-is.

- [ ] **Step 6: Run the full suite**

```bash
cd apps/backend
uv run pytest -v
```

Expected: `47 passed`.

- [ ] **Step 7: Commit**

```bash
git add apps/backend/app/modules/survey123/ingest.py apps/backend/fixtures/sample_small.csv \
        apps/backend/tests/test_ingest_parse.py
git commit -m "backend: add survey123 row parsing and fixture data"
```

---

### Task 4: `ingest_csv` orchestration — DB upsert, duplicate detection, `IngestResult`

**Files:**
- Modify: `apps/backend/app/modules/survey123/ingest.py` (append orchestration on top of Task 3's parsing layer)
- Modify: `apps/backend/app/config.py`
- Modify: `apps/backend/tests/test_config.py`
- Create: `apps/backend/tests/test_ingest.py`

**Interfaces:**
- Consumes: `Incident` (Task 1), `parse_row`/`is_duplicate_marker`/`PII_COLUMNS` (Task 3), `IngestResult` (Step 1 Task 3).
- Produces: `ingest_csv(file_path: Path, session: Session, salt: str) -> IngestResult`. Task 5's `Survey123Module.ingest()` calls this. Adds `Settings.dedup_salt: str` (default `"dev-salt-change-in-production"`, env var `DEDUP_SALT`) to `app.config.Settings`.
- Duplicate-detection priority per row (first match wins, recorded in `duplicate_reason`): literal `"Duplicate entry"` marker in raw `Name of Person` or `Incident Summary` (`duplicate_reason="marker"`) → repeated `(dedup_hash, event_date)` within the current file being ingested (`duplicate_reason="repeated_id_date"`, **every** row in the group is flagged — there is no "keep the first as canonical" exemption, since we can't be sure which of two same-ID-same-date submissions is the real one) → repeated `(dedup_hash, event_date)` against rows already committed in the database from a prior ingest, excluding the row's own `global_id` (`duplicate_reason="repeated_id_date"`).
- Upsert priority: unmatched `global_id` → insert. Matched `global_id` with a strictly newer incoming `edit_date` than the stored one → update all fields. Matched `global_id` with an equal or older (or missing) incoming `edit_date` → no write (this is what makes re-ingesting an unchanged file a true no-op: `rows_updated` does not increment).

- [ ] **Step 1: Add `dedup_salt` to `Settings`**

Replace `apps/backend/app/config.py` with:

```python
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./dev.db"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-5"
    report_timezone: str = "America/Port_of_Spain"
    app_env: str = "development"
    dedup_salt: str = "dev-salt-change-in-production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
```

Replace `apps/backend/tests/test_config.py` with:

```python
from app.config import Settings


def test_settings_defaults(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
    monkeypatch.delenv("REPORT_TIMEZONE", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("DEDUP_SALT", raising=False)

    settings = Settings(_env_file=None)

    assert settings.database_url == "sqlite:///./dev.db"
    assert settings.anthropic_api_key is None
    assert settings.anthropic_model == "claude-sonnet-5"
    assert settings.report_timezone == "America/Port_of_Spain"
    assert settings.app_env == "development"
    assert settings.dedup_salt == "dev-salt-change-in-production"


def test_settings_env_override(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@localhost:5432/dmcu")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-123")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DEDUP_SALT", "prod-salt-xyz")

    settings = Settings(_env_file=None)

    assert settings.database_url == "postgresql+psycopg://user:pass@localhost:5432/dmcu"
    assert settings.anthropic_api_key == "sk-test-123"
    assert settings.app_env == "production"
    assert settings.dedup_salt == "prod-salt-xyz"
```

- [ ] **Step 2: Run the config tests**

```bash
cd apps/backend
uv run pytest tests/test_config.py -v
```

Expected: `2 passed`.

- [ ] **Step 3: Write the failing orchestration tests**

Create `apps/backend/tests/test_ingest.py`:

```python
import csv
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.db import Base, make_engine
from app.modules.survey123.ingest import PII_COLUMNS, ingest_csv
from app.modules.survey123.models import Incident

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "sample_small.csv"

HEADER = [
    "ObjectID", "GlobalID", "CreationDate", "Creator", "EditDate", "Editor", "Name of Officer",
    "Position", "Organisation", "Other - Organisation", "Date of Event", "Time of Event",
    "Name of Person", "Contact Information", "Address", "Community", "Municipal Boundary",
    "Incident Type", "Other - Incident Type", "Incident Summary", "Household Occupants",
    "If more than 6 persons - Household Occupants", "Did any injuries occur?", "Injuries",
    "Type of Injuries", "Did any deaths occur?", "Deaths", "Building Damage",
    "Crops and Livestock", "Personal Items", "Furniture and Appliances", "Action Taken",
    "Relief Items", "Other Agency", "Shelter", "Are there any special needs occupants?",
    "Please indicate the number of special needs occupants", "Estimate Cost of Damage",
    "Identification Card Type", "Other - Identification Card Type", "Identification Card Number",
    "Follow Up Recommendation", "Other - Follow Up Recommendation", "Assessment Date",
    "Is the property insured?", "Island", "District", "Ownership", "Property Type",
    "Structure Type", "Other - Structure Type", "Age of Structure (years)", "Type of Household",
    "Number of Male Occupants", "Number of Female Occupants", "What are the age groups of occupants?",
    "Are there any dependents in the household", "Number of Dependents", "Validated/NotValidated",
    "Please list the names of the occupants and their relation", "Employment Status",
    "Employment Sector", "Other - Employment Sector", "Flood Type", "Flood Trigger",
    "Other - Flood Trigger", "Flood Height", "Other Agency_2", "Community_2", "Other - Community",
    "Other Agency_3", "Other - Other Agency", "Name of Second Person", "Second Contact Information",
    "Second Identification Card Number", "Second Employment Status", "x", "y",
]


def make_session(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


def write_csv(path: Path, rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=HEADER)
        writer.writeheader()
        for r in rows:
            full_row = {h: "" for h in HEADER}
            full_row.update(r)
            writer.writerow(full_row)


def test_ingest_fixture_yields_expected_row_count_and_corporation_breakdown(tmp_path):
    session = make_session(tmp_path)

    result = ingest_csv(FIXTURE_PATH, session, salt="test-salt")

    assert result.rows_read == 30
    assert result.rows_inserted == 30
    assert result.rows_updated == 0

    def count_corp(value):
        return len(session.execute(select(Incident).where(Incident.corporation == value)).scalars().all())

    assert count_corp("sangre_grande_regional_corporat") == 15
    assert count_corp("san_fernando_city_corporation") == 10
    assert count_corp("unmapped") == 1
    assert len(session.execute(select(Incident).where(Incident.corporation.is_(None))).scalars().all()) == 4


def test_ingest_fixture_incident_type_breakdown(tmp_path):
    session = make_session(tmp_path)
    ingest_csv(FIXTURE_PATH, session, salt="test-salt")

    def count_type(value):
        return len(session.execute(select(Incident).where(Incident.incident_type == value)).scalars().all())

    assert count_type("flooding_") == 9
    assert count_type("fire") == 6
    assert count_type("other") == 2
    assert count_type("landslide") == 4
    assert count_type("blown_off_roof") == 2
    assert count_type("fallen_tree") == 2
    assert count_type("earthquake") == 2
    assert count_type("over grown tree") == 2
    assert count_type("unmapped") == 1


def test_ingest_fixture_validation_status_breakdown(tmp_path):
    session = make_session(tmp_path)
    ingest_csv(FIXTURE_PATH, session, salt="test-salt")

    validated = session.execute(select(Incident).where(Incident.validation_status == "validated")).scalars().all()
    pending = session.execute(select(Incident).where(Incident.validation_status == "pending")).scalars().all()

    assert len(validated) == 21
    assert len(pending) == 9


def test_ingest_fixture_flags_duplicate_marker_and_repeated_id_date(tmp_path):
    session = make_session(tmp_path)

    result = ingest_csv(FIXTURE_PATH, session, salt="test-salt")

    assert result.duplicates_flagged == 4

    marker_rows = session.execute(
        select(Incident).where(Incident.global_id.in_(["GUID-025", "GUID-026"]))
    ).scalars().all()
    for r in marker_rows:
        assert r.is_duplicate is True
        assert r.duplicate_reason == "marker"

    repeated_rows = session.execute(
        select(Incident).where(Incident.global_id.in_(["GUID-027", "GUID-028"]))
    ).scalars().all()
    for r in repeated_rows:
        assert r.is_duplicate is True
        assert r.duplicate_reason == "repeated_id_date"


def test_ingest_fixture_reports_unmapped_values_and_pii_columns_dropped(tmp_path):
    session = make_session(tmp_path)

    result = ingest_csv(FIXTURE_PATH, session, salt="test-salt")

    assert result.unmapped_values == {
        "Municipal Boundary": ["Unknown_Corp_Typo"],
        "Incident Type": ["Volcanic_Eruption_Typo"],
    }
    assert result.pii_columns_dropped == PII_COLUMNS


def test_ingest_fixture_no_pii_value_persisted_anywhere(tmp_path):
    session = make_session(tmp_path)
    ingest_csv(FIXTURE_PATH, session, salt="test-salt")

    all_incidents = session.execute(select(Incident)).scalars().all()
    serialized = " ".join(
        str(getattr(incident, col.name)) for incident in all_incidents for col in Incident.__table__.columns
    )
    for pii_value in ["Fake Person 1", "8685550001", "19800101001", "Real Person 27"]:
        assert pii_value not in serialized


def test_reingesting_same_file_is_a_no_op(tmp_path):
    session = make_session(tmp_path)

    first = ingest_csv(FIXTURE_PATH, session, salt="test-salt")
    second = ingest_csv(FIXTURE_PATH, session, salt="test-salt")

    assert first.rows_inserted == 30
    assert second.rows_inserted == 0
    assert second.rows_updated == 0
    assert second.rows_read == 30


def test_cross_ingest_duplicate_detected_against_already_persisted_rows(tmp_path):
    session = make_session(tmp_path)
    ingest_csv(FIXTURE_PATH, session, salt="test-salt")

    second_file = tmp_path / "second_batch.csv"
    write_csv(
        second_file,
        [
            {
                "ObjectID": "99",
                "GlobalID": "GUID-099",
                "CreationDate": "2024-07-05T09:00:00",
                "EditDate": "2024-07-05T09:00:00",
                "Date of Event": "2024-06-27T00:00:00",
                "Name of Person": "Another Real Person",
                "Municipal Boundary": "san_fernando_city_corporation",
                "Incident Type": "Flooding_",
                "Identification Card Number": "19850315099",
                "Validated/NotValidated": "Validated",
            }
        ],
    )

    result = ingest_csv(second_file, session, salt="test-salt")

    assert result.rows_inserted == 1
    assert result.duplicates_flagged == 1

    new_row = session.execute(select(Incident).where(Incident.global_id == "GUID-099")).scalar_one()
    assert new_row.is_duplicate is True
    assert new_row.duplicate_reason == "repeated_id_date"
```

- [ ] **Step 4: Run tests to verify they fail**

```bash
cd apps/backend
uv run pytest tests/test_ingest.py -v
```

Expected: FAIL — `ImportError: cannot import name 'ingest_csv' from 'app.modules.survey123.ingest'`.

- [ ] **Step 5: Append `ingest_csv` to `app/modules/survey123/ingest.py`**

Add these imports to the top of `apps/backend/app/modules/survey123/ingest.py` (alongside the existing ones from Task 3):

```python
import csv
from datetime import timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.contracts import IngestResult
from app.modules.survey123.models import Incident
```

Append this function at the end of the file:

```python
def ingest_csv(file_path: Path, session: Session, salt: str) -> IngestResult:
    with open(file_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        raw_rows = list(reader)

    parsed = [(raw, parse_row(raw, salt)) for raw in raw_rows]

    batch_groups: dict[tuple[str, datetime], list[int]] = {}
    for idx, (_raw, fields) in enumerate(parsed):
        if fields["dedup_hash"] is not None and fields["event_date"] is not None:
            key = (fields["dedup_hash"], fields["event_date"])
            batch_groups.setdefault(key, []).append(idx)

    in_batch_duplicate_indices: set[int] = set()
    for indices in batch_groups.values():
        if len(indices) > 1:
            in_batch_duplicate_indices.update(indices)

    rows_read = 0
    rows_inserted = 0
    rows_updated = 0
    duplicates_flagged = 0
    unmapped_values: dict[str, list[str]] = {}

    for idx, (raw, fields) in enumerate(parsed):
        rows_read += 1

        if fields["raw_corporation"]:
            values = unmapped_values.setdefault("Municipal Boundary", [])
            if fields["raw_corporation"] not in values:
                values.append(fields["raw_corporation"])
        if fields["raw_incident_type"]:
            values = unmapped_values.setdefault("Incident Type", [])
            if fields["raw_incident_type"] not in values:
                values.append(fields["raw_incident_type"])

        is_duplicate = False
        duplicate_reason: str | None = None

        if is_duplicate_marker(raw.get("Name of Person"), raw.get("Incident Summary")):
            is_duplicate = True
            duplicate_reason = "marker"
        elif idx in in_batch_duplicate_indices:
            is_duplicate = True
            duplicate_reason = "repeated_id_date"
        elif fields["dedup_hash"] is not None and fields["event_date"] is not None:
            existing_match = (
                session.execute(
                    select(Incident).where(
                        Incident.dedup_hash == fields["dedup_hash"],
                        Incident.event_date == fields["event_date"],
                        Incident.global_id != fields["global_id"],
                    )
                )
                .scalars()
                .first()
            )
            if existing_match is not None:
                is_duplicate = True
                duplicate_reason = "repeated_id_date"

        if is_duplicate:
            duplicates_flagged += 1

        existing = (
            session.execute(select(Incident).where(Incident.global_id == fields["global_id"]))
            .scalars()
            .first()
        )

        if existing is None:
            incident = Incident(
                **fields,
                is_duplicate=is_duplicate,
                duplicate_reason=duplicate_reason,
                source_file=str(file_path),
                ingested_at=datetime.now(timezone.utc),
            )
            session.add(incident)
            rows_inserted += 1
        else:
            incoming_edit_date = fields["edit_date"]
            if incoming_edit_date is not None and (
                existing.edit_date is None or incoming_edit_date > existing.edit_date
            ):
                for key, value in fields.items():
                    setattr(existing, key, value)
                existing.is_duplicate = is_duplicate
                existing.duplicate_reason = duplicate_reason
                existing.source_file = str(file_path)
                existing.ingested_at = datetime.now(timezone.utc)
                rows_updated += 1

    session.commit()

    return IngestResult(
        rows_read=rows_read,
        rows_inserted=rows_inserted,
        rows_updated=rows_updated,
        duplicates_flagged=duplicates_flagged,
        unmapped_values=unmapped_values,
        pii_columns_dropped=list(PII_COLUMNS),
    )
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
cd apps/backend
uv run pytest tests/test_ingest.py -v
```

Expected: `8 passed`.

- [ ] **Step 7: Run the full suite**

```bash
cd apps/backend
uv run pytest -v
```

Expected: `55 passed` (47 from before Task 4, plus 8 new `test_ingest.py` tests; `test_config.py` is replaced in place with the same 2 tests extended, so it contributes no net change).

- [ ] **Step 8: Commit**

```bash
git add apps/backend/app/modules/survey123/ingest.py apps/backend/app/config.py \
        apps/backend/tests/test_config.py apps/backend/tests/test_ingest.py
git commit -m "backend: add survey123 ingest orchestration with dedup and upsert"
```

---

### Task 5: `DataModule` registration

**Files:**
- Create: `apps/backend/app/modules/survey123/module.py`
- Modify: `apps/backend/app/main.py`
- Create: `apps/backend/tests/test_survey123_module.py`

**Interfaces:**
- Consumes: `DataModule` Protocol (Step 1 Task 4), `ingest_csv` (Task 4), `Settings.dedup_salt` (Task 4), `Fact`/`IngestResult`/`MetricSpec` (Step 1 Task 3).
- Produces: `app.modules.survey123.module.Survey123Module` (a `DataModule`-conforming class, `name = "survey123"`), module-level `survey123_module = Survey123Module()`. `app.main.create_app()` now registers it. Task 6's CLI imports `survey123_module` directly.

- [ ] **Step 1: Write the failing tests**

Create `apps/backend/tests/test_survey123_module.py`:

```python
import pytest
from fastapi.testclient import TestClient

from app.core.registry import get_module, reset_registry
from app.main import create_app
from app.modules.survey123.module import survey123_module


@pytest.fixture(autouse=True)
def _clean_registry():
    reset_registry()
    yield
    reset_registry()


def test_survey123_module_has_correct_name():
    assert survey123_module.name == "survey123"


def test_survey123_module_list_metrics_is_empty():
    assert survey123_module.list_metrics() == []


def test_survey123_module_run_metric_raises_for_unknown_metric():
    with pytest.raises(ValueError, match="incident_count"):
        survey123_module.run_metric("incident_count", {}, session=None)


def test_create_app_registers_survey123_module():
    create_app()

    assert get_module("survey123") is survey123_module


def test_modules_endpoint_includes_survey123_after_create_app():
    app = create_app()
    client = TestClient(app)

    response = client.get("/modules")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["name"] == "survey123"
    assert body[0]["metrics"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd apps/backend
uv run pytest tests/test_survey123_module.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.modules.survey123.module'`.

- [ ] **Step 3: Implement `app/modules/survey123/module.py`**

```python
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.core.contracts import Fact, IngestResult, MetricSpec
from app.modules.survey123.ingest import ingest_csv


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
        return []

    def run_metric(self, name: str, params: dict, session: Session) -> list[Fact]:
        raise ValueError(f"unknown metric for survey123: {name}")


survey123_module = Survey123Module()
```

- [ ] **Step 4: Wire registration into `app/main.py`**

Replace `apps/backend/app/main.py` with:

```python
from fastapi import FastAPI

from app.api.meta import router as meta_router
from app.core.registry import register_module
from app.modules.survey123.module import survey123_module


def create_app() -> FastAPI:
    app = FastAPI(title="DMCU Reporting API")
    app.include_router(meta_router)
    register_module(survey123_module)
    return app


app = create_app()
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd apps/backend
uv run pytest tests/test_survey123_module.py -v
```

Expected: `5 passed`.

- [ ] **Step 6: Run the full suite**

```bash
cd apps/backend
uv run pytest -v
```

Expected: `60 passed`.

- [ ] **Step 7: Commit**

```bash
git add apps/backend/app/modules/survey123/module.py apps/backend/app/main.py \
        apps/backend/tests/test_survey123_module.py
git commit -m "backend: register survey123 as a DataModule"
```

---

### Task 6: CLI — `cli.py ingest survey123 <file>`

**Files:**
- Create: `apps/backend/cli.py`
- Create: `apps/backend/tests/test_cli.py`

**Interfaces:**
- Consumes: `register_module`/`get_module`/`reset_registry` (Step 1 Task 4), `survey123_module` (Task 5).
- Produces: `apps/backend/cli.py`'s module-level `app` (a `typer.Typer()` instance). Must support exactly the invocation `uv run python cli.py ingest survey123 <file_path>` — a plain single-command Typer app collapses the `ingest` subcommand name away (verified during planning: a lone `@app.command()` gets invoked without its name), so `ingest` must be a nested `typer.Typer()` added via `app.add_typer(ingest_app, name="ingest")` with `survey123` as a command inside it. This structure also gives future data modules (sitreps, WRHA — out of scope here) a natural place to add their own `ingest <module>` subcommand later.

- [ ] **Step 1: Write the failing tests**

Create `apps/backend/tests/test_cli.py`:

```python
from pathlib import Path

from typer.testing import CliRunner

from app.core.registry import reset_registry
from app.db import Base, engine as db_engine
from cli import app

runner = CliRunner()

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "sample_small.csv"
DEV_DB_PATH = Path(__file__).parent.parent / "dev.db"


def test_ingest_survey123_command_reports_summary():
    reset_registry()
    if DEV_DB_PATH.exists():
        DEV_DB_PATH.unlink()
    Base.metadata.create_all(db_engine)

    try:
        result = runner.invoke(app, ["ingest", "survey123", str(FIXTURE_PATH)])

        assert result.exit_code == 0, result.stdout
        assert "rows_read=30" in result.stdout
        assert "rows_inserted=30" in result.stdout
        assert "duplicates_flagged=4" in result.stdout
    finally:
        reset_registry()
        if DEV_DB_PATH.exists():
            DEV_DB_PATH.unlink()


def test_ingest_unknown_module_errors():
    reset_registry()

    result = runner.invoke(app, ["ingest", "not_a_real_module", str(FIXTURE_PATH)])

    assert result.exit_code == 2
    reset_registry()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd apps/backend
uv run pytest tests/test_cli.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'cli'` (this is expected: `pyproject.toml`'s `pythonpath = ["."]` from Step 1 makes `apps/backend/` importable as a root, so `cli.py` at that root is reachable as top-level module `cli` once it exists).

- [ ] **Step 3: Implement `apps/backend/cli.py`**

```python
from pathlib import Path

import typer

from app.core.registry import get_module, register_module
from app.modules.survey123.module import survey123_module

app = typer.Typer()
ingest_app = typer.Typer()
app.add_typer(ingest_app, name="ingest")


@ingest_app.command("survey123")
def ingest_survey123(file_path: Path) -> None:
    if get_module("survey123") is None:
        register_module(survey123_module)

    result = get_module("survey123").ingest(file_path)

    typer.echo(f"rows_read={result.rows_read}")
    typer.echo(f"rows_inserted={result.rows_inserted}")
    typer.echo(f"rows_updated={result.rows_updated}")
    typer.echo(f"duplicates_flagged={result.duplicates_flagged}")
    typer.echo(f"unmapped_values={result.unmapped_values}")
    typer.echo(f"pii_columns_dropped={result.pii_columns_dropped}")


if __name__ == "__main__":
    app()
```

`ingest_app` is the only place `survey123` (or any future module) gets wired up as a subcommand of `ingest`. Calling `cli.py ingest <anything-else> <file>` hits Click's own "No such command" handling on the `ingest_app` group and exits with code `2` (verified during planning — this is Click's built-in group-dispatch behavior, not custom code) — `test_ingest_unknown_module_errors` asserts exactly that exit code. Do not add a second, top-level `@app.command() def ingest(...)` — it would collide by name with `add_typer(ingest_app, name="ingest")`.

- [ ] **Step 4: Verify the exact CLI invocation shape**

```bash
cd apps/backend
uv run python cli.py ingest survey123 --help
```

Expected: exits 0, shows help text for the `survey123` subcommand (confirms `ingest` did not collapse away as a bare command name).

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd apps/backend
uv run pytest tests/test_cli.py -v
```

Expected: `2 passed`.

- [ ] **Step 6: Run the full suite**

```bash
cd apps/backend
uv run pytest -v
```

Expected: `62 passed`.

- [ ] **Step 7: Commit**

```bash
git add apps/backend/cli.py apps/backend/tests/test_cli.py
git commit -m "backend: add CLI ingest command for survey123"
```

---

## Definition of Done (matches `PLAN.md` §6 Step 2, adapted for the CSV-only deviation)

- [ ] `cd apps/backend && uv run pytest -v` — all 71 tests pass, 0 failures.
- [ ] Banned-PII-columns test (`test_incident_model_has_no_pii_columns`) passes.
- [ ] Duplicate-marker rows are flagged (`test_ingest_fixture_flags_duplicate_marker_and_repeated_id_date`).
- [ ] Re-ingesting the same file is a no-op (`test_reingesting_same_file_is_a_no_op`).
- [ ] **Manual verification against the real export** (do not commit `output.csv` — it is git-ignored):
  ```bash
  cd apps/backend
  rm -f dev.db
  uv run alembic upgrade head
  uv run python cli.py ingest survey123 output.csv
  ```
  Expected: `rows_read=14942`, 14 distinct corporation values plus a `(no corporation recorded)` bucket (query `SELECT corporation, COUNT(*) FROM incidents GROUP BY corporation;` against `dev.db` to confirm — corporation values should be exactly the 14 canonical slugs from `normalize.py` plus `NULL` for blanks; `unmapped` should NOT appear for this real file, since every real corporation value collapses to a canonical slug). Then `rm -f dev.db` again to avoid leaving real PII in a local database file.
