# DMCU Metrics v2 — Detail Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 8 new deterministic Fact-producing metrics to the `survey123` module (response time, flood characteristics, action-taken, insurance coverage, structural damage profile, household demographics, employment impact, island split), ingesting several currently-uncaptured Survey123 columns to support them, and wire all 8 into the two existing report templates so generated reports carry more detail for the LLM to narrate around.

**Architecture:** No new architectural concepts — this extends the existing `survey123` data module exactly like the original 9 metrics (Step 3). Every new metric is a pure function of `(params, session)` returning `list[Fact]`, built from `base_query`/`apply_common_filters`, cited via `build_citation`, and registered in `METRIC_SPECS`/`METRIC_FUNCTIONS`. No changes to `core/engine.py`, `core/citation_check.py`, `core/renderer.py`, or `core/llm.py` — the existing pipeline (assemble Fact Table → LLM narrate → citation check → render) is generic over however many facts a template requests.

**Tech Stack:** Same as the rest of the backend — Python 3.13, SQLAlchemy 2.0, Pydantic v2, Alembic, pytest, uv.

## Global Constraints

- No LLM call anywhere except `core/llm.py`; everything in this plan must be testable without a network (PLAN.md §7).
- Every metric is a pure function of `(params, session)` — no hidden state (PLAN.md §7).
- Categorical breakdowns must include an explicit `"(no X recorded)"` bucket for blanks — never drop rows silently (PLAN.md §7, matches existing `incidents_by_corporation` pattern).
- PII: `PII_COLUMNS` in `apps/backend/app/modules/survey123/ingest.py` is the enforcement list. `"Second Employment Status"` must be added to it — it describes an attribute of the specifically-named (but stripped) "second person," consistent with the other banned second-person fields.
- Never present a sparse field's sum/total without a coverage caveat (`records_reporting` / `records_total` in the breakdown) — matches the existing `estimated_damage_total` convention.
- All commands below run from `apps/backend/` using `uv run ...`.
- Commit after each task's tests pass.

---

## Ground-truth reference (verified against the real 14,942-row export and the current fixture)

Running `ingest_csv` against `apps/backend/fixtures/sample_small.csv` today yields exactly 19 rows matching the default metric scope (`validation_status == "validated"` and `is_duplicate == False`): `GUID-001..005, 009, 010, 011..014, 017, 018, 021, 022, 023, 024, 029, 030`. All new-field test expectations below are computed against these 19 rows after Task 4's fixture patch.

---

### Task 1: Ban "Second Employment Status" as PII

**Files:**
- Modify: `apps/backend/app/modules/survey123/ingest.py:23-31`
- Test: `apps/backend/tests/test_ingest.py`

**Interfaces:**
- Produces: `PII_COLUMNS` gains one more entry; no signature changes.

- [ ] **Step 1: Update the test's expected column list**

In `apps/backend/tests/test_ingest.py`, the `HEADER` list (lines 13-34) already contains `"Second Employment Status"` at line 33 — no change needed there. The existing test `test_ingest_fixture_reports_unmapped_values_and_pii_columns_dropped` (line 123) already asserts `result.pii_columns_dropped == PII_COLUMNS`, so it will automatically cover the new entry once `PII_COLUMNS` is updated in Step 2. No test file change is required for this task — confirm this by reading the file and verifying line 132 does a direct equality check against the imported constant (not a hardcoded list).

- [ ] **Step 2: Add the column to `PII_COLUMNS`**

In `apps/backend/app/modules/survey123/ingest.py`, change:

```python
PII_COLUMNS = [
    "Name of Person",
    "Contact Information",
    "Identification Card Number",
    "Name of Second Person",
    "Second Contact Information",
    "Second Identification Card Number",
    "Please list the names of the occupants and their relation",
]
```

to:

```python
PII_COLUMNS = [
    "Name of Person",
    "Contact Information",
    "Identification Card Number",
    "Name of Second Person",
    "Second Contact Information",
    "Second Identification Card Number",
    "Second Employment Status",
    "Please list the names of the occupants and their relation",
]
```

- [ ] **Step 3: Run the full test suite**

Run: `cd apps/backend && uv run pytest -v`
Expected: all tests pass (this constant is only read, never used to build a CSV row, so nothing else changes behavior).

- [ ] **Step 4: Commit**

```bash
git add apps/backend/app/modules/survey123/ingest.py
git commit -m "survey123: ban Second Employment Status as PII"
```

---

### Task 2: Add new columns to the `Incident` model + migration

**Files:**
- Modify: `apps/backend/app/modules/survey123/models.py`
- Create: `apps/backend/alembic/versions/<generated>_add_property_household_employment_fields.py`

**Interfaces:**
- Produces: 11 new nullable columns on `Incident`: `insured: bool | None`, `island: str | None`, `ownership: str | None`, `property_type: str | None`, `structure_type: str | None`, `household_type: str | None`, `male_occupants: int | None`, `female_occupants: int | None`, `dependents_count: int | None`, `employment_status: str | None`, `employment_sector: str | None`. Task 3 (ingestion) and Tasks 5-7 (metrics) depend on these exact names/types.

- [ ] **Step 1: Add the columns to the model**

In `apps/backend/app/modules/survey123/models.py`, insert this block right after the `officer_position` line (line 70) and before `dedup_hash` (line 72):

```python
    insured: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    island: Mapped[str | None] = mapped_column(String, nullable=True)
    ownership: Mapped[str | None] = mapped_column(String, nullable=True)
    property_type: Mapped[str | None] = mapped_column(String, nullable=True)
    structure_type: Mapped[str | None] = mapped_column(String, nullable=True)
    household_type: Mapped[str | None] = mapped_column(String, nullable=True)
    male_occupants: Mapped[int | None] = mapped_column(Integer, nullable=True)
    female_occupants: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dependents_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    employment_status: Mapped[str | None] = mapped_column(String, nullable=True)
    employment_sector: Mapped[str | None] = mapped_column(String, nullable=True)
```

All imports needed (`Boolean`, `String`, `Integer`, `Mapped`, `mapped_column`) are already present at the top of the file — no import changes needed.

- [ ] **Step 2: Generate the Alembic revision**

Run: `cd apps/backend && uv run alembic revision -m "add property household employment fields to incidents"`
Expected: prints `Generating .../alembic/versions/<hash>_add_property_household_employment_fields.py ...  done`. Note the generated revision id and filename.

- [ ] **Step 3: Fill in the migration body**

Open the generated file. Set `down_revision = '6ae0a692151e'` (the current head, from `create_reports_table`). Replace the empty `upgrade()`/`downgrade()` bodies with:

```python
def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('incidents', sa.Column('insured', sa.Boolean(), nullable=True))
    op.add_column('incidents', sa.Column('island', sa.String(), nullable=True))
    op.add_column('incidents', sa.Column('ownership', sa.String(), nullable=True))
    op.add_column('incidents', sa.Column('property_type', sa.String(), nullable=True))
    op.add_column('incidents', sa.Column('structure_type', sa.String(), nullable=True))
    op.add_column('incidents', sa.Column('household_type', sa.String(), nullable=True))
    op.add_column('incidents', sa.Column('male_occupants', sa.Integer(), nullable=True))
    op.add_column('incidents', sa.Column('female_occupants', sa.Integer(), nullable=True))
    op.add_column('incidents', sa.Column('dependents_count', sa.Integer(), nullable=True))
    op.add_column('incidents', sa.Column('employment_status', sa.String(), nullable=True))
    op.add_column('incidents', sa.Column('employment_sector', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('incidents', 'employment_sector')
    op.drop_column('incidents', 'employment_status')
    op.drop_column('incidents', 'dependents_count')
    op.drop_column('incidents', 'female_occupants')
    op.drop_column('incidents', 'male_occupants')
    op.drop_column('incidents', 'household_type')
    op.drop_column('incidents', 'structure_type')
    op.drop_column('incidents', 'property_type')
    op.drop_column('incidents', 'ownership')
    op.drop_column('incidents', 'island')
    op.drop_column('incidents', 'insured')
```

- [ ] **Step 4: Verify the migration applies cleanly against a throwaway SQLite DB**

Run:
```bash
cd apps/backend
rm -f /tmp/migration_check.db
DATABASE_URL=sqlite:////tmp/migration_check.db uv run alembic upgrade head
DATABASE_URL=sqlite:////tmp/migration_check.db uv run alembic downgrade -1
DATABASE_URL=sqlite:////tmp/migration_check.db uv run alembic upgrade head
rm -f /tmp/migration_check.db
```
Expected: all three commands exit 0 with no errors — confirms upgrade, downgrade, and re-upgrade all work.

- [ ] **Step 5: Run the full test suite**

Run: `cd apps/backend && uv run pytest -v`
Expected: all tests pass (tests use `Base.metadata.create_all`, not the migration, so this just confirms the model change alone doesn't break anything).

- [ ] **Step 6: Commit**

```bash
git add apps/backend/app/modules/survey123/models.py apps/backend/alembic/versions/
git commit -m "survey123: add insured, island, ownership, property/structure type, household demographics, and employment columns to Incident"
```

---

### Task 3: Ingest the new fields

**Files:**
- Modify: `apps/backend/app/modules/survey123/ingest.py`
- Create: `apps/backend/tests/test_ingest_extended_fields.py`

**Interfaces:**
- Consumes: `Incident` columns from Task 2.
- Produces: `parse_row(row, salt)` now includes the 11 new keys; new helper `parse_bool_or_none(raw: str | None) -> bool | None`.

- [ ] **Step 1: Write the failing test**

Create `apps/backend/tests/test_ingest_extended_fields.py`:

```python
import csv
from pathlib import Path

from app.modules.survey123.ingest import parse_row

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


def make_row(overrides: dict) -> dict:
    row = {h: "" for h in HEADER}
    row.update(overrides)
    return row


def test_parse_row_extracts_all_new_fields_when_populated():
    row = make_row({
        "GlobalID": "GUID-X", "ObjectID": "1",
        "Is the property insured?": "True",
        "Island": "Trinidad",
        "Ownership": "Owner",
        "Property Type": "Home",
        "Structure Type": "Concrete",
        "Type of Household": "Single Family",
        "Number of Male Occupants": "2",
        "Number of Female Occupants": "3",
        "Number of Dependents": "1",
        "Employment Status": "Employed",
        "Employment Sector": "Government",
    })

    fields = parse_row(row, salt="test-salt")

    assert fields["insured"] is True
    assert fields["island"] == "Trinidad"
    assert fields["ownership"] == "Owner"
    assert fields["property_type"] == "Home"
    assert fields["structure_type"] == "Concrete"
    assert fields["household_type"] == "Single Family"
    assert fields["male_occupants"] == 2
    assert fields["female_occupants"] == 3
    assert fields["dependents_count"] == 1
    assert fields["employment_status"] == "Employed"
    assert fields["employment_sector"] == "Government"


def test_parse_row_new_fields_are_none_when_blank():
    row = make_row({"GlobalID": "GUID-Y", "ObjectID": "2"})

    fields = parse_row(row, salt="test-salt")

    assert fields["insured"] is None
    assert fields["island"] is None
    assert fields["ownership"] is None
    assert fields["property_type"] is None
    assert fields["structure_type"] is None
    assert fields["household_type"] is None
    assert fields["male_occupants"] is None
    assert fields["female_occupants"] is None
    assert fields["dependents_count"] is None
    assert fields["employment_status"] is None
    assert fields["employment_sector"] is None


def test_parse_row_insured_false_is_distinct_from_not_recorded():
    row = make_row({
        "GlobalID": "GUID-Z", "ObjectID": "3",
        "Is the property insured?": "False",
    })

    fields = parse_row(row, salt="test-salt")

    assert fields["insured"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend && uv run pytest tests/test_ingest_extended_fields.py -v`
Expected: FAIL with `KeyError: 'insured'` (or similar) — `parse_row` doesn't produce these keys yet.

- [ ] **Step 3: Add the `parse_bool_or_none` helper**

In `apps/backend/app/modules/survey123/ingest.py`, add this function right after `parse_bool` (after line 37):

```python
def parse_bool_or_none(raw: str | None) -> bool | None:
    cleaned = (raw or "").strip()
    if not cleaned:
        return None
    return cleaned.lower() == "true"
```

- [ ] **Step 4: Extend `parse_row` to populate the new fields**

In `apps/backend/app/modules/survey123/ingest.py`, in the `parse_row` function's returned dict (currently ending with `"dedup_hash": compute_dedup_hash(...)` at line 133), add these keys right before the closing `}`:

```python
        "insured": parse_bool_or_none(row.get("Is the property insured?")),
        "island": (row.get("Island") or "").strip() or None,
        "ownership": (row.get("Ownership") or "").strip() or None,
        "property_type": (row.get("Property Type") or "").strip() or None,
        "structure_type": (row.get("Structure Type") or "").strip() or None,
        "household_type": (row.get("Type of Household") or "").strip() or None,
        "male_occupants": parse_int(row.get("Number of Male Occupants")),
        "female_occupants": parse_int(row.get("Number of Female Occupants")),
        "dependents_count": parse_int(row.get("Number of Dependents")),
        "employment_status": (row.get("Employment Status") or "").strip() or None,
        "employment_sector": (row.get("Employment Sector") or "").strip() or None,
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd apps/backend && uv run pytest tests/test_ingest_extended_fields.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Run the full test suite**

Run: `cd apps/backend && uv run pytest -v`
Expected: all tests pass — `Incident(**fields, ...)` in `ingest_csv` accepts the new keys automatically since Task 2 added matching columns.

- [ ] **Step 7: Commit**

```bash
git add apps/backend/app/modules/survey123/ingest.py apps/backend/tests/test_ingest_extended_fields.py
git commit -m "survey123: ingest insured, island, ownership, property/structure type, household demographics, and employment fields"
```

---

### Task 4: Extend `sample_small.csv` with new-field test data

**Files:**
- Modify: `apps/backend/fixtures/sample_small.csv` (data patch, via a one-time script)
- Test: extend `apps/backend/tests/test_ingest.py`

**Interfaces:**
- Produces: specific new-field values on 19 existing fixture rows (see table below), which Tasks 5-7's metric tests depend on for their expected aggregate values. No existing column value in the fixture changes — only currently-blank cells in the 11 new columns (plus `Assessment Date` on 2 rows that are already blank) are filled in.

**New-field values by GlobalID** (any field/row not listed stays blank):

| GlobalID | insured | island | ownership | property_type | structure_type | household_type | male | female | dependents | employment_status | employment_sector | flood_type | flood_trigger | assessment_date |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| GUID-001 | True | Trinidad | Owner | Home | Concrete | Single Family | 1 | 0 | 0 | Employed | Agriculture and Fisheries | Flash Flooding | Hurricane/Tropical Storm | *(unchanged)* |
| GUID-002 | True | Trinidad | Owner | Home | Concrete | Single Family | 1 | 1 | 1 | Unemployed | | Flash Flooding | Hurricane/Tropical Storm | *(unchanged)* |
| GUID-003 | False | Trinidad | Renter | Home | Wood | | | | | Retired | | Flash Flooding | Adverse Weather | *(unchanged)* |
| GUID-004 | False | Trinidad | Renter | Home | Wood | Multi-Family | 2 | 2 | 1 | | | Riverine Flooding | Hurricane/Tropical Storm | *(unchanged)* |
| GUID-005 | False | Trinidad | | | | | | | | | | Riverine Flooding | Adverse Weather | *(unchanged)* |
| GUID-009 | | Trinidad | | | | | | | | | | | | *(unchanged, blank)* |
| GUID-010 | | Trinidad | | | | | | | | | | | | *(unchanged, blank)* |
| GUID-011 | True | Trinidad | Owner | Home | Concrete | Single Family | 2 | 2 | 0 | Self Employed | | | | *(unchanged)* |
| GUID-012 | True | Trinidad | Owner | Home | Concrete | | | | | Employed | Government | | | *(unchanged)* |
| GUID-013 | False | Trinidad | Renter | Home | Wood | Apartment | 1 | 3 | 2 | | | | | *(unchanged)* |
| GUID-014 | False | Trinidad | | | | | | | | | | | | *(unchanged)* |
| GUID-017 | True | Trinidad | Owner | Home | Wood | Single Family | 1 | 1 | 0 | Unemployed | | | | *(unchanged)* |
| GUID-018 | False | Trinidad | Leased | Home | | | | | | | | | | *(unchanged)* |
| GUID-021 | False | Tobago | | | | Multi-Family | 3 | 2 | 1 | | | | | **2024-06-21T15:00:00** |
| GUID-022 | | Tobago | | | | | | | | | | | | *(unchanged, blank)* |
| GUID-023 | | | | | | | | | | Employed | Trade | | | *(unchanged, blank)* |
| GUID-024 | | | | | | | | | | | | | | **2024-07-05T00:00:00** |
| GUID-029 | True | Trinidad | | Business | | Single Family | 4 | 5 | 3 | Retired | | Coastal Flooding | | *(unchanged, blank)* |
| GUID-030 | True | Trinidad | | Business | | Single Family | 6 | 6 | 2 | | | | | *(unchanged)* |

- [ ] **Step 1: Write and run the one-time patch script**

Create a temporary script at `apps/backend/_patch_fixture_v2.py`:

```python
import csv
from pathlib import Path

FIXTURE = Path("fixtures/sample_small.csv")

UPDATES = {
    "GUID-001": {"Is the property insured?": "True", "Island": "Trinidad", "Ownership": "Owner",
                 "Property Type": "Home", "Structure Type": "Concrete", "Type of Household": "Single Family",
                 "Number of Male Occupants": "1", "Number of Female Occupants": "0", "Number of Dependents": "0",
                 "Employment Status": "Employed", "Employment Sector": "Agriculture and Fisheries",
                 "Flood Type": "Flash Flooding", "Flood Trigger": "Hurricane/Tropical Storm"},
    "GUID-002": {"Is the property insured?": "True", "Island": "Trinidad", "Ownership": "Owner",
                 "Property Type": "Home", "Structure Type": "Concrete", "Type of Household": "Single Family",
                 "Number of Male Occupants": "1", "Number of Female Occupants": "1", "Number of Dependents": "1",
                 "Employment Status": "Unemployed", "Flood Type": "Flash Flooding",
                 "Flood Trigger": "Hurricane/Tropical Storm"},
    "GUID-003": {"Is the property insured?": "False", "Island": "Trinidad", "Ownership": "Renter",
                 "Property Type": "Home", "Structure Type": "Wood", "Employment Status": "Retired",
                 "Flood Type": "Flash Flooding", "Flood Trigger": "Adverse Weather"},
    "GUID-004": {"Is the property insured?": "False", "Island": "Trinidad", "Ownership": "Renter",
                 "Property Type": "Home", "Structure Type": "Wood", "Type of Household": "Multi-Family",
                 "Number of Male Occupants": "2", "Number of Female Occupants": "2", "Number of Dependents": "1",
                 "Flood Type": "Riverine Flooding", "Flood Trigger": "Hurricane/Tropical Storm"},
    "GUID-005": {"Is the property insured?": "False", "Island": "Trinidad",
                 "Flood Type": "Riverine Flooding", "Flood Trigger": "Adverse Weather"},
    "GUID-009": {"Island": "Trinidad"},
    "GUID-010": {"Island": "Trinidad"},
    "GUID-011": {"Is the property insured?": "True", "Island": "Trinidad", "Ownership": "Owner",
                 "Property Type": "Home", "Structure Type": "Concrete", "Type of Household": "Single Family",
                 "Number of Male Occupants": "2", "Number of Female Occupants": "2", "Number of Dependents": "0",
                 "Employment Status": "Self Employed"},
    "GUID-012": {"Is the property insured?": "True", "Island": "Trinidad", "Ownership": "Owner",
                 "Property Type": "Home", "Structure Type": "Concrete",
                 "Employment Status": "Employed", "Employment Sector": "Government"},
    "GUID-013": {"Is the property insured?": "False", "Island": "Trinidad", "Ownership": "Renter",
                 "Property Type": "Home", "Structure Type": "Wood", "Type of Household": "Apartment",
                 "Number of Male Occupants": "1", "Number of Female Occupants": "3", "Number of Dependents": "2"},
    "GUID-014": {"Is the property insured?": "False", "Island": "Trinidad"},
    "GUID-017": {"Is the property insured?": "True", "Island": "Trinidad", "Ownership": "Owner",
                 "Property Type": "Home", "Structure Type": "Wood", "Type of Household": "Single Family",
                 "Number of Male Occupants": "1", "Number of Female Occupants": "1", "Number of Dependents": "0",
                 "Employment Status": "Unemployed"},
    "GUID-018": {"Is the property insured?": "False", "Island": "Trinidad",
                 "Ownership": "Leased", "Property Type": "Home"},
    "GUID-021": {"Is the property insured?": "False", "Island": "Tobago", "Type of Household": "Multi-Family",
                 "Number of Male Occupants": "3", "Number of Female Occupants": "2", "Number of Dependents": "1",
                 "Assessment Date": "2024-06-21T15:00:00"},
    "GUID-022": {"Island": "Tobago"},
    "GUID-023": {"Employment Status": "Employed", "Employment Sector": "Trade"},
    "GUID-024": {"Assessment Date": "2024-07-05T00:00:00"},
    "GUID-029": {"Is the property insured?": "True", "Island": "Trinidad", "Property Type": "Business",
                 "Type of Household": "Single Family", "Number of Male Occupants": "4",
                 "Number of Female Occupants": "5", "Number of Dependents": "3",
                 "Employment Status": "Retired", "Flood Type": "Coastal Flooding"},
    "GUID-030": {"Is the property insured?": "True", "Island": "Trinidad", "Property Type": "Business",
                 "Type of Household": "Single Family", "Number of Male Occupants": "6",
                 "Number of Female Occupants": "6", "Number of Dependents": "2"},
}

with open(FIXTURE, newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    rows = list(reader)

changed = 0
for row in rows:
    updates = UPDATES.get(row["GlobalID"])
    if updates:
        row.update(updates)
        changed += 1

assert changed == len(UPDATES), f"expected to patch {len(UPDATES)} rows, patched {changed}"

with open(FIXTURE, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print(f"patched {changed} rows")
```

Run: `cd apps/backend && uv run python _patch_fixture_v2.py`
Expected: prints `patched 19 rows`.

- [ ] **Step 2: Delete the one-time script**

```bash
cd apps/backend && rm _patch_fixture_v2.py
```

- [ ] **Step 3: Run the existing full test suite to confirm no regression**

Run: `cd apps/backend && uv run pytest -v`
Expected: all existing tests still pass unchanged — you only filled in previously-blank cells, so every existing assertion (row counts, corporation/incident-type/validation breakdowns, duplicate flags, PII checks) is unaffected.

- [ ] **Step 4: Write a test locking in the new fixture values**

Add to `apps/backend/tests/test_ingest.py` (after `test_ingest_fixture_no_pii_value_persisted_anywhere`):

```python
def test_ingest_fixture_extended_field_values(tmp_path):
    session = make_session(tmp_path)
    ingest_csv(FIXTURE_PATH, session, salt="test-salt")

    def get(global_id):
        return session.execute(
            select(Incident).where(Incident.global_id == global_id)
        ).scalars().one()

    guid_001 = get("GUID-001")
    assert guid_001.insured is True
    assert guid_001.island == "Trinidad"
    assert guid_001.ownership == "Owner"
    assert guid_001.property_type == "Home"
    assert guid_001.structure_type == "Concrete"
    assert guid_001.household_type == "Single Family"
    assert guid_001.male_occupants == 1
    assert guid_001.female_occupants == 0
    assert guid_001.dependents_count == 0
    assert guid_001.employment_status == "Employed"
    assert guid_001.employment_sector == "Agriculture and Fisheries"
    assert guid_001.flood_type == "Flash Flooding"
    assert guid_001.flood_trigger == "Hurricane/Tropical Storm"

    guid_013 = get("GUID-013")
    assert guid_013.male_occupants == 1
    assert guid_013.female_occupants == 3
    assert guid_013.dependents_count == 2
    assert guid_013.household_type == "Apartment"

    guid_021 = get("GUID-021")
    assert guid_021.island == "Tobago"
    assert guid_021.insured is False
    assert guid_021.assessment_date.isoformat() == "2024-06-21T15:00:00"

    guid_024 = get("GUID-024")
    assert guid_024.assessment_date.isoformat() == "2024-07-05T00:00:00"

    guid_003 = get("GUID-003")
    assert guid_003.insured is False
    assert guid_003.male_occupants is None
    assert guid_003.household_type is None
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd apps/backend && uv run pytest tests/test_ingest.py -v`
Expected: PASS, including the new `test_ingest_fixture_extended_field_values`.

- [ ] **Step 6: Commit**

```bash
git add apps/backend/fixtures/sample_small.csv apps/backend/tests/test_ingest.py
git commit -m "fixtures: populate new property, household, and employment fields on 19 sample rows"
```

---

### Task 5: Metrics — `response_time_summary`, `action_summary`, `island_breakdown`

**Files:**
- Modify: `apps/backend/app/modules/survey123/metrics.py`
- Create: `apps/backend/tests/test_metrics_response_action_island.py`

**Interfaces:**
- Consumes: `base_query(params)`, `build_citation`, `build_scope`, `build_window_label`, `determine_verification` (all already in `metrics.py`); `Incident.assessment_date`, `Incident.event_date`, `Incident.action_taken`, `Incident.island` (from Tasks 2-4).
- Produces: `response_time_summary(params, session) -> list[Fact]`, `action_summary(params, session) -> list[Fact]`, `island_breakdown(params, session) -> list[Fact]`, each registered in `METRIC_SPECS` and `METRIC_FUNCTIONS`.

- [ ] **Step 1: Write the failing tests**

Create `apps/backend/tests/test_metrics_response_action_island.py`:

```python
from pathlib import Path

from sqlalchemy.orm import sessionmaker

from app.db import Base, make_engine
from app.modules.survey123.ingest import ingest_csv
from app.modules.survey123.metrics import action_summary, island_breakdown, response_time_summary

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "sample_small.csv"


def make_session(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    ingest_csv(FIXTURE_PATH, session, salt="test-salt")
    return session


def test_response_time_summary_average_and_buckets(tmp_path):
    session = make_session(tmp_path)

    facts = response_time_summary({}, session)

    assert len(facts) == 1
    fact = facts[0]
    assert fact.metric == "response_time_summary"
    assert fact.unit == "days"
    assert fact.value == 1.6
    assert fact.breakdown == {
        "same_day": 1,
        "1_3_days": 12,
        "4_7_days": 0,
        "8_plus_days": 1,
        "records_reporting": 14,
        "records_total": 19,
    }
    assert fact.citation.cid == "survey123-response_time_summary-0"


def test_action_summary_counts_taken_vs_not(tmp_path):
    session = make_session(tmp_path)

    facts = action_summary({}, session)

    assert len(facts) == 1
    fact = facts[0]
    assert fact.metric == "action_summary"
    assert fact.value == 14
    assert fact.breakdown == {"action_taken": 14, "no_action_taken": 5, "(no action recorded)": 0}


def test_island_breakdown_includes_no_island_recorded_bucket(tmp_path):
    session = make_session(tmp_path)

    facts = island_breakdown({}, session)

    assert len(facts) == 1
    fact = facts[0]
    assert fact.metric == "island_breakdown"
    assert fact.value == 19
    assert fact.breakdown == {"Trinidad": 15, "Tobago": 2, "(no island recorded)": 2}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend && uv run pytest tests/test_metrics_response_action_island.py -v`
Expected: FAIL with `ImportError: cannot import name 'response_time_summary'`.

- [ ] **Step 3: Implement the three metric functions**

In `apps/backend/app/modules/survey123/metrics.py`, add this block after `data_coverage` (after line 401, before `METRIC_PARAMS_SCHEMA`):

```python
def response_time_summary(params: dict, session: Session) -> list[Fact]:
    rows = session.execute(base_query(params)).scalars().all()
    reporting = [r for r in rows if r.assessment_date is not None and r.event_date is not None]

    def bucket(days: int) -> str:
        if days <= 0:
            return "same_day"
        if days <= 3:
            return "1_3_days"
        if days <= 7:
            return "4_7_days"
        return "8_plus_days"

    breakdown = {"same_day": 0, "1_3_days": 0, "4_7_days": 0, "8_plus_days": 0}
    lags = []
    for r in reporting:
        days = (r.assessment_date - r.event_date).days
        lags.append(days)
        breakdown[bucket(days)] += 1
    breakdown["records_reporting"] = len(reporting)
    breakdown["records_total"] = len(rows)

    avg_days = round(sum(lags) / len(lags), 1) if lags else 0.0

    global_ids = [r.global_id for r in reporting]
    citation = build_citation(
        "response_time_summary",
        0,
        params,
        global_ids,
        f"Survey123 response time (event to assessment), {build_window_label(params.get('date_from'), params.get('date_to'))}",
    )

    return [
        Fact(
            metric="response_time_summary",
            value=avg_days,
            unit="days",
            scope=build_scope(params),
            breakdown=breakdown,
            verification=determine_verification([r.validation_status for r in reporting]),
            citation=citation,
        )
    ]


def action_summary(params: dict, session: Session) -> list[Fact]:
    rows = session.execute(base_query(params)).scalars().all()

    breakdown = {"action_taken": 0, "no_action_taken": 0, "(no action recorded)": 0}
    for r in rows:
        key = r.action_taken if r.action_taken in ("action_taken", "no_action_taken") else "(no action recorded)"
        breakdown[key] += 1

    global_ids = [r.global_id for r in rows]
    citation = build_citation(
        "action_summary",
        0,
        params,
        global_ids,
        f"Survey123 action-taken summary, {build_window_label(params.get('date_from'), params.get('date_to'))}",
    )

    return [
        Fact(
            metric="action_summary",
            value=breakdown["action_taken"],
            unit="incidents",
            scope=build_scope(params),
            breakdown=breakdown,
            verification=determine_verification([r.validation_status for r in rows]),
            citation=citation,
        )
    ]


def island_breakdown(params: dict, session: Session) -> list[Fact]:
    rows = session.execute(base_query(params)).scalars().all()

    breakdown: dict[str, int] = {}
    for r in rows:
        key = r.island or "(no island recorded)"
        breakdown[key] = breakdown.get(key, 0) + 1

    global_ids = [r.global_id for r in rows]
    citation = build_citation(
        "island_breakdown",
        0,
        params,
        global_ids,
        f"Survey123 island breakdown, {build_window_label(params.get('date_from'), params.get('date_to'))}",
    )

    return [
        Fact(
            metric="island_breakdown",
            value=len(rows),
            unit="incidents",
            scope=build_scope(params),
            breakdown=breakdown,
            verification=determine_verification([r.validation_status for r in rows]),
            citation=citation,
        )
    ]
```

- [ ] **Step 4: Register the new metrics**

In `apps/backend/app/modules/survey123/metrics.py`, add to `METRIC_SPECS` (after the `data_coverage` entry, before the closing `]`):

```python
    MetricSpec(
        name="response_time_summary",
        description="Average days from event to assessment, bucketed same-day/1-3d/4-7d/8+d, with a coverage caveat.",
        params_schema=METRIC_PARAMS_SCHEMA,
        module="survey123",
    ),
    MetricSpec(
        name="action_summary",
        description="Count of incidents where action was/was not taken.",
        params_schema=METRIC_PARAMS_SCHEMA,
        module="survey123",
    ),
    MetricSpec(
        name="island_breakdown",
        description="Counts per island (Trinidad/Tobago), including a (no island recorded) bucket for blanks.",
        params_schema=METRIC_PARAMS_SCHEMA,
        module="survey123",
    ),
```

And add to `METRIC_FUNCTIONS`:

```python
    "response_time_summary": response_time_summary,
    "action_summary": action_summary,
    "island_breakdown": island_breakdown,
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd apps/backend && uv run pytest tests/test_metrics_response_action_island.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Run the full test suite**

Run: `cd apps/backend && uv run pytest -v`
Expected: all pass. Note `test_survey123_metrics_dispatch.py`'s `test_list_metrics_returns_all_nine_with_correct_names` will now see 12 metrics instead of 9 and its hardcoded `len(specs) == 9` / `EXPECTED_METRIC_NAMES` set will fail — this is expected and gets fixed in Task 7 once all 8 new metrics exist. Confirm the *only* failures are in `test_survey123_metrics_dispatch.py`.

- [ ] **Step 7: Commit**

```bash
git add apps/backend/app/modules/survey123/metrics.py apps/backend/tests/test_metrics_response_action_island.py
git commit -m "survey123: add response_time_summary, action_summary, island_breakdown metrics"
```

---

### Task 6: Metrics — `flood_characteristics`, `insurance_coverage`

**Files:**
- Modify: `apps/backend/app/modules/survey123/metrics.py`
- Create: `apps/backend/tests/test_metrics_flood_insurance.py`

**Interfaces:**
- Consumes: same shared helpers as Task 5; `Incident.flood_type`, `Incident.flood_trigger` (already existed, unused until now), `Incident.insured` (from Task 2).
- Produces: `flood_characteristics(params, session) -> list[Fact]` (2 facts), `insurance_coverage(params, session) -> list[Fact]` (1 fact), registered in `METRIC_SPECS`/`METRIC_FUNCTIONS`.

- [ ] **Step 1: Write the failing tests**

Create `apps/backend/tests/test_metrics_flood_insurance.py`:

```python
from pathlib import Path

from sqlalchemy.orm import sessionmaker

from app.db import Base, make_engine
from app.modules.survey123.ingest import ingest_csv
from app.modules.survey123.metrics import flood_characteristics, insurance_coverage

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "sample_small.csv"


def make_session(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    ingest_csv(FIXTURE_PATH, session, salt="test-salt")
    return session


def test_flood_characteristics_returns_type_and_trigger_facts(tmp_path):
    session = make_session(tmp_path)

    facts = flood_characteristics({}, session)

    assert len(facts) == 2
    type_fact, trigger_fact = facts
    assert type_fact.scope["category"] == "flood_type"
    assert type_fact.value == 19
    assert type_fact.breakdown == {
        "Flash Flooding": 3,
        "Riverine Flooding": 2,
        "Coastal Flooding": 1,
        "(no flood type recorded)": 13,
    }
    assert trigger_fact.scope["category"] == "flood_trigger"
    assert trigger_fact.value == 19
    assert trigger_fact.breakdown == {
        "Hurricane/Tropical Storm": 3,
        "Adverse Weather": 2,
        "(no flood trigger recorded)": 14,
    }


def test_insurance_coverage_percent_and_caveat(tmp_path):
    session = make_session(tmp_path)

    facts = insurance_coverage({}, session)

    assert len(facts) == 1
    fact = facts[0]
    assert fact.metric == "insurance_coverage"
    assert fact.unit == "%"
    assert fact.value == 50.0
    assert fact.breakdown == {
        "insured": 7,
        "not_insured": 7,
        "records_reporting": 14,
        "records_total": 19,
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend && uv run pytest tests/test_metrics_flood_insurance.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement the two metric functions**

In `apps/backend/app/modules/survey123/metrics.py`, add after the block from Task 5 (still before `METRIC_PARAMS_SCHEMA`):

```python
def flood_characteristics(params: dict, session: Session) -> list[Fact]:
    rows = session.execute(base_query(params)).scalars().all()

    type_breakdown: dict[str, int] = {}
    trigger_breakdown: dict[str, int] = {}
    for r in rows:
        type_key = r.flood_type or "(no flood type recorded)"
        type_breakdown[type_key] = type_breakdown.get(type_key, 0) + 1
        trigger_key = r.flood_trigger or "(no flood trigger recorded)"
        trigger_breakdown[trigger_key] = trigger_breakdown.get(trigger_key, 0) + 1

    global_ids = [r.global_id for r in rows]
    verification = determine_verification([r.validation_status for r in rows])
    type_citation = build_citation(
        "flood_characteristics", 0, params, global_ids,
        f"Survey123 flood type breakdown, {build_window_label(params.get('date_from'), params.get('date_to'))}",
    )
    trigger_citation = build_citation(
        "flood_characteristics", 1, params, global_ids,
        f"Survey123 flood trigger breakdown, {build_window_label(params.get('date_from'), params.get('date_to'))}",
    )

    return [
        Fact(
            metric="flood_characteristics", value=len(rows), unit="incidents",
            scope=build_scope(params, category="flood_type"), breakdown=type_breakdown,
            verification=verification, citation=type_citation,
        ),
        Fact(
            metric="flood_characteristics", value=len(rows), unit="incidents",
            scope=build_scope(params, category="flood_trigger"), breakdown=trigger_breakdown,
            verification=verification, citation=trigger_citation,
        ),
    ]


def insurance_coverage(params: dict, session: Session) -> list[Fact]:
    rows = session.execute(base_query(params)).scalars().all()
    reporting = [r for r in rows if r.insured is not None]
    insured_count = sum(1 for r in reporting if r.insured)
    not_insured_count = len(reporting) - insured_count
    pct_insured = round(100.0 * insured_count / len(reporting), 1) if reporting else 0.0

    global_ids = [r.global_id for r in reporting]
    citation = build_citation(
        "insurance_coverage", 0, params, global_ids,
        f"Survey123 insurance coverage, {build_window_label(params.get('date_from'), params.get('date_to'))}",
    )

    return [
        Fact(
            metric="insurance_coverage",
            value=pct_insured,
            unit="%",
            scope=build_scope(params),
            breakdown={
                "insured": insured_count,
                "not_insured": not_insured_count,
                "records_reporting": len(reporting),
                "records_total": len(rows),
            },
            verification=determine_verification([r.validation_status for r in reporting]),
            citation=citation,
        )
    ]
```

- [ ] **Step 4: Register the new metrics**

Add to `METRIC_SPECS`:

```python
    MetricSpec(
        name="flood_characteristics",
        description="Breakdown by flood type and flood trigger, each with a (not recorded) bucket. Two facts.",
        params_schema=METRIC_PARAMS_SCHEMA,
        module="survey123",
    ),
    MetricSpec(
        name="insurance_coverage",
        description="Percent of properties insured among those reporting insurance status, with a coverage caveat.",
        params_schema=METRIC_PARAMS_SCHEMA,
        module="survey123",
    ),
```

Add to `METRIC_FUNCTIONS`:

```python
    "flood_characteristics": flood_characteristics,
    "insurance_coverage": insurance_coverage,
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd apps/backend && uv run pytest tests/test_metrics_flood_insurance.py -v`
Expected: PASS (2 tests).

- [ ] **Step 6: Run the full test suite**

Run: `cd apps/backend && uv run pytest -v`
Expected: same state as Task 5 — only `test_survey123_metrics_dispatch.py` fails, on count/name assertions.

- [ ] **Step 7: Commit**

```bash
git add apps/backend/app/modules/survey123/metrics.py apps/backend/tests/test_metrics_flood_insurance.py
git commit -m "survey123: add flood_characteristics, insurance_coverage metrics"
```

---

### Task 7: Metrics — `structural_damage_profile`, `household_demographics_summary`, `employment_impact_summary` + fix dispatch test

**Files:**
- Modify: `apps/backend/app/modules/survey123/metrics.py`
- Modify: `apps/backend/tests/test_survey123_metrics_dispatch.py`
- Create: `apps/backend/tests/test_metrics_structure_household_employment.py`

**Interfaces:**
- Consumes: same shared helpers; `Incident.ownership`, `Incident.property_type`, `Incident.structure_type`, `Incident.male_occupants`, `Incident.female_occupants`, `Incident.dependents_count`, `Incident.household_type`, `Incident.employment_status`, `Incident.employment_sector` (all from Task 2).
- Produces: `structural_damage_profile` (3 facts), `household_demographics_summary` (3 facts), `employment_impact_summary` (2 facts) — bringing the total registered metric count to 17.

- [ ] **Step 1: Write the failing tests**

Create `apps/backend/tests/test_metrics_structure_household_employment.py`:

```python
from pathlib import Path

from sqlalchemy.orm import sessionmaker

from app.db import Base, make_engine
from app.modules.survey123.ingest import ingest_csv
from app.modules.survey123.metrics import (
    employment_impact_summary,
    household_demographics_summary,
    structural_damage_profile,
)

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "sample_small.csv"


def make_session(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    ingest_csv(FIXTURE_PATH, session, salt="test-salt")
    return session


def test_structural_damage_profile_returns_three_breakdowns(tmp_path):
    session = make_session(tmp_path)

    facts = structural_damage_profile({}, session)

    assert len(facts) == 3
    ownership, property_type, structure_type = facts
    assert ownership.scope["category"] == "ownership"
    assert ownership.breakdown == {"Owner": 5, "Renter": 3, "Leased": 1, "(no ownership recorded)": 10}
    assert property_type.scope["category"] == "property_type"
    assert property_type.breakdown == {"Home": 9, "Business": 2, "(no property type recorded)": 8}
    assert structure_type.scope["category"] == "structure_type"
    assert structure_type.breakdown == {"Concrete": 4, "Wood": 4, "(no structure type recorded)": 11}


def test_household_demographics_summary_returns_three_facts(tmp_path):
    session = make_session(tmp_path)

    facts = household_demographics_summary({}, session)

    assert len(facts) == 3
    occupants, dependents, household_type = facts

    assert occupants.scope["category"] == "occupants"
    assert occupants.value == 43
    assert occupants.breakdown == {"male": 21, "female": 22, "records_reporting": 9, "records_total": 19}

    assert dependents.scope["category"] == "dependents"
    assert dependents.value == 10
    assert dependents.breakdown == {"records_reporting": 9, "records_total": 19}

    assert household_type.scope["category"] == "household_type"
    assert household_type.value == 19
    assert household_type.breakdown == {
        "Single Family": 6,
        "Multi-Family": 2,
        "Apartment": 1,
        "(no household type recorded)": 10,
    }


def test_employment_impact_summary_returns_status_and_sector(tmp_path):
    session = make_session(tmp_path)

    facts = employment_impact_summary({}, session)

    assert len(facts) == 2
    status, sector = facts
    assert status.scope["category"] == "employment_status"
    assert status.breakdown == {
        "Employed": 3,
        "Unemployed": 2,
        "Retired": 2,
        "Self Employed": 1,
        "(no employment status recorded)": 11,
    }
    assert sector.scope["category"] == "employment_sector"
    assert sector.breakdown == {
        "Agriculture and Fisheries": 1,
        "Government": 1,
        "Trade": 1,
        "(no employment sector recorded)": 16,
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend && uv run pytest tests/test_metrics_structure_household_employment.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement the three metric functions**

In `apps/backend/app/modules/survey123/metrics.py`, add after the block from Task 6:

```python
def structural_damage_profile(params: dict, session: Session) -> list[Fact]:
    rows = session.execute(base_query(params)).scalars().all()

    def tally(attr: str, missing_label: str) -> dict[str, int]:
        breakdown: dict[str, int] = {}
        for r in rows:
            key = getattr(r, attr) or missing_label
            breakdown[key] = breakdown.get(key, 0) + 1
        return breakdown

    ownership_breakdown = tally("ownership", "(no ownership recorded)")
    property_type_breakdown = tally("property_type", "(no property type recorded)")
    structure_type_breakdown = tally("structure_type", "(no structure type recorded)")

    global_ids = [r.global_id for r in rows]
    verification = determine_verification([r.validation_status for r in rows])
    ownership_citation = build_citation(
        "structural_damage_profile", 0, params, global_ids,
        f"Survey123 ownership breakdown, {build_window_label(params.get('date_from'), params.get('date_to'))}",
    )
    property_citation = build_citation(
        "structural_damage_profile", 1, params, global_ids,
        f"Survey123 property type breakdown, {build_window_label(params.get('date_from'), params.get('date_to'))}",
    )
    structure_citation = build_citation(
        "structural_damage_profile", 2, params, global_ids,
        f"Survey123 structure type breakdown, {build_window_label(params.get('date_from'), params.get('date_to'))}",
    )

    return [
        Fact(
            metric="structural_damage_profile", value=len(rows), unit="incidents",
            scope=build_scope(params, category="ownership"), breakdown=ownership_breakdown,
            verification=verification, citation=ownership_citation,
        ),
        Fact(
            metric="structural_damage_profile", value=len(rows), unit="incidents",
            scope=build_scope(params, category="property_type"), breakdown=property_type_breakdown,
            verification=verification, citation=property_citation,
        ),
        Fact(
            metric="structural_damage_profile", value=len(rows), unit="incidents",
            scope=build_scope(params, category="structure_type"), breakdown=structure_type_breakdown,
            verification=verification, citation=structure_citation,
        ),
    ]


def household_demographics_summary(params: dict, session: Session) -> list[Fact]:
    rows = session.execute(base_query(params)).scalars().all()
    occupant_rows = [r for r in rows if r.male_occupants is not None or r.female_occupants is not None]
    dependents_rows = [r for r in rows if r.dependents_count is not None]

    total_male = sum(r.male_occupants or 0 for r in occupant_rows)
    total_female = sum(r.female_occupants or 0 for r in occupant_rows)
    total_dependents = sum(r.dependents_count or 0 for r in dependents_rows)

    household_type_breakdown: dict[str, int] = {}
    for r in rows:
        key = r.household_type or "(no household type recorded)"
        household_type_breakdown[key] = household_type_breakdown.get(key, 0) + 1

    occupant_citation = build_citation(
        "household_demographics_summary", 0, params, [r.global_id for r in occupant_rows],
        f"Survey123 occupant demographics, {build_window_label(params.get('date_from'), params.get('date_to'))}",
    )
    dependents_citation = build_citation(
        "household_demographics_summary", 1, params, [r.global_id for r in dependents_rows],
        f"Survey123 dependents count, {build_window_label(params.get('date_from'), params.get('date_to'))}",
    )
    household_type_citation = build_citation(
        "household_demographics_summary", 2, params, [r.global_id for r in rows],
        f"Survey123 household type breakdown, {build_window_label(params.get('date_from'), params.get('date_to'))}",
    )

    return [
        Fact(
            metric="household_demographics_summary", value=total_male + total_female, unit="persons",
            scope=build_scope(params, category="occupants"),
            breakdown={
                "male": total_male, "female": total_female,
                "records_reporting": len(occupant_rows), "records_total": len(rows),
            },
            verification=determine_verification([r.validation_status for r in occupant_rows]),
            citation=occupant_citation,
        ),
        Fact(
            metric="household_demographics_summary", value=total_dependents, unit="persons",
            scope=build_scope(params, category="dependents"),
            breakdown={"records_reporting": len(dependents_rows), "records_total": len(rows)},
            verification=determine_verification([r.validation_status for r in dependents_rows]),
            citation=dependents_citation,
        ),
        Fact(
            metric="household_demographics_summary", value=len(rows), unit="incidents",
            scope=build_scope(params, category="household_type"), breakdown=household_type_breakdown,
            verification=determine_verification([r.validation_status for r in rows]),
            citation=household_type_citation,
        ),
    ]


def employment_impact_summary(params: dict, session: Session) -> list[Fact]:
    rows = session.execute(base_query(params)).scalars().all()

    status_breakdown: dict[str, int] = {}
    sector_breakdown: dict[str, int] = {}
    for r in rows:
        status_key = r.employment_status or "(no employment status recorded)"
        status_breakdown[status_key] = status_breakdown.get(status_key, 0) + 1
        sector_key = r.employment_sector or "(no employment sector recorded)"
        sector_breakdown[sector_key] = sector_breakdown.get(sector_key, 0) + 1

    global_ids = [r.global_id for r in rows]
    verification = determine_verification([r.validation_status for r in rows])
    status_citation = build_citation(
        "employment_impact_summary", 0, params, global_ids,
        f"Survey123 employment status breakdown, {build_window_label(params.get('date_from'), params.get('date_to'))}",
    )
    sector_citation = build_citation(
        "employment_impact_summary", 1, params, global_ids,
        f"Survey123 employment sector breakdown, {build_window_label(params.get('date_from'), params.get('date_to'))}",
    )

    return [
        Fact(
            metric="employment_impact_summary", value=len(rows), unit="incidents",
            scope=build_scope(params, category="employment_status"), breakdown=status_breakdown,
            verification=verification, citation=status_citation,
        ),
        Fact(
            metric="employment_impact_summary", value=len(rows), unit="incidents",
            scope=build_scope(params, category="employment_sector"), breakdown=sector_breakdown,
            verification=verification, citation=sector_citation,
        ),
    ]
```

- [ ] **Step 4: Register the new metrics**

Add to `METRIC_SPECS`:

```python
    MetricSpec(
        name="structural_damage_profile",
        description="Breakdown by ownership, property type, and structure type, each with a (not recorded) bucket. Three facts.",
        params_schema=METRIC_PARAMS_SCHEMA,
        module="survey123",
    ),
    MetricSpec(
        name="household_demographics_summary",
        description="Total male/female occupants, total dependents, and household-type breakdown, each with a coverage caveat. Three facts.",
        params_schema=METRIC_PARAMS_SCHEMA,
        module="survey123",
    ),
    MetricSpec(
        name="employment_impact_summary",
        description="Breakdown by employment status and employment sector, each with a (not recorded) bucket. Two facts.",
        params_schema=METRIC_PARAMS_SCHEMA,
        module="survey123",
    ),
```

Add to `METRIC_FUNCTIONS`:

```python
    "structural_damage_profile": structural_damage_profile,
    "household_demographics_summary": household_demographics_summary,
    "employment_impact_summary": employment_impact_summary,
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd apps/backend && uv run pytest tests/test_metrics_structure_household_employment.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Fix `test_survey123_metrics_dispatch.py`**

In `apps/backend/tests/test_survey123_metrics_dispatch.py`, replace `EXPECTED_METRIC_NAMES` (lines 12-22) with:

```python
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
    "response_time_summary",
    "action_summary",
    "island_breakdown",
    "flood_characteristics",
    "insurance_coverage",
    "structural_damage_profile",
    "household_demographics_summary",
    "employment_impact_summary",
}
```

And update the assertion:

```python
def test_list_metrics_returns_all_seventeen_with_correct_names():
    specs = survey123_module.list_metrics()

    assert {spec.name for spec in specs} == EXPECTED_METRIC_NAMES
    assert len(specs) == 17
    for spec in specs:
        assert spec.module == "survey123"
        assert spec.params_schema["type"] == "object"
```

(rename the function from `test_list_metrics_returns_all_nine_with_correct_names`).

Also update `test_run_metric_dispatches_to_incident_count` — `incident_count` value is unaffected by this plan (`incident_count` doesn't touch any new column), so it stays `assert facts[0].value == 19` unchanged. `test_run_metric_dispatches_to_data_coverage_multi_fact` also stays unchanged (`data_coverage` wasn't modified).

- [ ] **Step 7: Run the full test suite**

Run: `cd apps/backend && uv run pytest -v`
Expected: all tests pass, zero failures.

- [ ] **Step 8: Commit**

```bash
git add apps/backend/app/modules/survey123/metrics.py apps/backend/tests/test_metrics_structure_household_employment.py apps/backend/tests/test_survey123_metrics_dispatch.py
git commit -m "survey123: add structural_damage_profile, household_demographics_summary, employment_impact_summary metrics; update dispatch test to 17 metrics"
```

---

### Task 8: Wire the 8 new metrics into both templates and verify end-to-end

**Files:**
- Modify: `apps/backend/app/templates/definitions/minister_regional_comparison.yaml`
- Modify: `apps/backend/app/templates/definitions/single_region_report.yaml`
- Test: existing `apps/backend/tests/test_cli_generate.py`, `apps/backend/tests/test_api_reports.py`, `apps/backend/tests/test_engine*.py` (no code changes expected, just re-run)

**Interfaces:**
- Consumes: all 17 metrics now in `METRIC_FUNCTIONS`; `Template` schema (unchanged) from `app/core/contracts.py`.
- Produces: two richer templates. No engine, renderer, or citation-checker code changes — `core/renderer.py` already renders any fact with a `breakdown` as a markdown table generically, and `core/citation_check.py` validates against however many facts are in the table.

- [ ] **Step 1: Add 3 new data_requirements to `minister_regional_comparison.yaml`**

In `apps/backend/app/templates/definitions/minister_regional_comparison.yaml`, after the existing `data_coverage` entry (line 24), add:

```yaml
  - module: survey123
    metric: response_time_summary
    params: { date_from: "{date_from}", date_to: "{date_to}" }
  - module: survey123
    metric: action_summary
    params: { date_from: "{date_from}", date_to: "{date_to}" }
  - module: survey123
    metric: island_breakdown
    params: { date_from: "{date_from}", date_to: "{date_to}" }
```

- [ ] **Step 2: Update `minister_regional_comparison.yaml`'s narration section**

Replace the `narration:` block with:

```yaml
narration:
  system_prompt: |
    You are drafting a one-page briefing for a government minister in Trinidad
    and Tobago's Disaster Management Coordinating Unit.

    RULES (absolute):
    - Use ONLY numbers present in the fact table you are given as JSON. Never
      compute, sum, estimate, or round a number that is not already present.
    - Every sentence containing a figure must end with its citation marker,
      e.g. [C001]. Citation markers look like C001, C002, etc.
    - Distinguish validated vs pending figures exactly as labeled in the fact
      table's "verification" field.
    - Infrastructure impact leads the briefing; casualties are stated once,
      factually, without embellishment.
    - Mention the average response time (event to assessment) and the split
      of action-taken vs no-action-taken incidents as part of the operational
      picture, citing their facts.
    - If the island breakdown fact shows activity on both Trinidad and Tobago,
      note the split briefly.
    - The whole briefing must fit on one page — be concise.
  output_sections: [headline, regional_comparison, response_and_actions, island_split, data_gaps]
```

- [ ] **Step 3: Add 7 new data_requirements to `single_region_report.yaml`**

In `apps/backend/app/templates/definitions/single_region_report.yaml`, after the existing `data_coverage` entry (line 34), add:

```yaml
  - module: survey123
    metric: response_time_summary
    params: { corporation: "{corporation}", community: "{community}", date_from: "{date_from}", date_to: "{date_to}" }
  - module: survey123
    metric: flood_characteristics
    params: { corporation: "{corporation}", community: "{community}", date_from: "{date_from}", date_to: "{date_to}" }
  - module: survey123
    metric: action_summary
    params: { corporation: "{corporation}", community: "{community}", date_from: "{date_from}", date_to: "{date_to}" }
  - module: survey123
    metric: insurance_coverage
    params: { corporation: "{corporation}", community: "{community}", date_from: "{date_from}", date_to: "{date_to}" }
  - module: survey123
    metric: structural_damage_profile
    params: { corporation: "{corporation}", community: "{community}", date_from: "{date_from}", date_to: "{date_to}" }
  - module: survey123
    metric: household_demographics_summary
    params: { corporation: "{corporation}", community: "{community}", date_from: "{date_from}", date_to: "{date_to}" }
  - module: survey123
    metric: employment_impact_summary
    params: { corporation: "{corporation}", community: "{community}", date_from: "{date_from}", date_to: "{date_to}" }
```

- [ ] **Step 4: Update `single_region_report.yaml`'s narration section**

Replace the `narration:` block with:

```yaml
narration:
  system_prompt: |
    You are drafting a region-level deep-dive report for a government minister
    in Trinidad and Tobago's Disaster Management Coordinating Unit.

    RULES (absolute):
    - Use ONLY numbers present in the fact table you are given as JSON. Never
      compute, sum, estimate, or round a number that is not already present.
    - Every sentence containing a figure must end with its citation marker,
      e.g. [C001]. Citation markers look like C001, C002, etc.
    - The estimated damage total and the insurance coverage percentage both
      carry a coverage caveat (N of M records reporting) — state each
      plainly, never as a complete total.
    - Household demographics (occupants, dependents) also carry a coverage
      caveat — state the number of records reporting alongside the totals.
    - Cover flood characteristics, structural damage profile (ownership,
      property type, structure type), and employment impact only when their
      fact table entries have non-trivial data (i.e. more than just the
      "(not recorded)" bucket) — do not pad the report with empty sections.
    - If the fact table lists gaps, state them plainly in a Data Gaps section.
  output_sections: [headline, streets, response_and_actions, flood_and_structure, household_and_employment, damage_and_insurance_caveat, data_gaps]
```

- [ ] **Step 5: Run the full test suite**

Run: `cd apps/backend && uv run pytest -v`
Expected: all tests pass. `test_cli_generate.py`'s `test_generate_minister_regional_comparison_produces_markdown_report` and `test_api_reports.py`'s report-generation tests still just assert `"# "` and `"## Citation Appendix"` are present in the output — those remain true regardless of how many facts are pulled, so no test code changes are needed. The `FakeLLMClient._auto_narrative` (in `app/core/llm.py`) iterates generically over `data["facts"]`, so it automatically produces one guaranteed-passing sentence per new fact — no test fixture or fake-client change needed.

- [ ] **Step 6: Manually verify against the fixture via the CLI**

Run:
```bash
cd apps/backend
rm -f dev.db
uv run python -c "
from app.db import Base, engine
from app.core.registry import reset_registry, reset_template_registry
reset_registry(); reset_template_registry()
Base.metadata.create_all(engine)
"
uv run python cli.py ingest survey123 fixtures/sample_small.csv
uv run python cli.py generate minister_regional_comparison --date-from 2024-06-01 --date-to 2024-06-30
uv run python cli.py generate single_region_report --corporation sangre_grande_regional_corporat --date-from 2024-06-01 --date-to 2024-06-30
rm -f dev.db
```
Expected: both commands print a markdown report with a `## Data Tables` section containing entries for the new metrics (e.g. `response_time_summary`, `island_breakdown` for the minister report; `flood_characteristics`, `insurance_coverage`, `structural_damage_profile`, `household_demographics_summary`, `employment_impact_summary` for the single-region report), and a `## Citation Appendix` listing all of them. This uses the `fake` LLM provider by default in the CLI's test-safe path — confirm the report's `status` line (printed by the CLI) is not silently swallowed; read the actual output.

- [ ] **Step 7: Manually verify against real Ollama (optional but recommended, matches Step 6's precedent)**

If a local Ollama server with the configured model (see `apps/backend/app/config.py`'s `ollama_model` default) is running, re-run Step 6's two `generate` commands with `LLM_PROVIDER=ollama` set (or via `.env`) instead of relying on the fake client, and read the actual narrative output to confirm the model handles the larger fact table (up to 14 facts for `single_region_report`) without degrading citation-check pass rate. If it fails citation checks more often than before, note this in the commit message or a follow-up — no code change is required by this plan for that outcome, but it should be visible to whoever reviews this before merge.

- [ ] **Step 8: Commit**

```bash
git add apps/backend/app/templates/definitions/minister_regional_comparison.yaml apps/backend/app/templates/definitions/single_region_report.yaml
git commit -m "templates: wire response time, flood, action, insurance, structural, household, employment, and island metrics into both templates"
```

---

## Explicitly out of scope for this plan

- **`other_agency_involvement`** — the raw data (`Other Agency`, `Other Agency_2`, `Other Agency_3` columns) has the same agencies spelled multiple inconsistent ways ("NCSH" / "National commission for self help" / "Self-help"...). Building a clean breakdown needs a hand-built typo-normalization map, analogous to Step 2's corporation-name mapping — a follow-up plan, not a quick add.
- **`District`** — only 1 non-blank value across all 14,942 real rows. Not usable.
- **Age-groups breakdown** (`What are the age groups of occupants?`) — multi-select with an ambiguous label (`<60_Years`) that needs a normalization decision before it can be trusted; excluded per the earlier PII/scope discussion.
- **Age of Structure (years)** average — dropped to keep `structural_damage_profile` to 3 facts instead of 4; can be added later following the exact `estimated_damage_total` coverage-caveat pattern if wanted.
- Charts, word clouds, or any visual output — this plan produces Facts only, for the LLM to narrate around, per explicit instruction.
