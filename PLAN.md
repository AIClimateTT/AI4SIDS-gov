# PLAN.md — AI4SIDS-Gov: DMCU Modular Reporting System
**Handoff plan for Claude Code. Read fully before writing code.**

---

## 1. What we are building

An on-demand reporting system for the Disaster Management Coordinating Unit (Ministry of Rural Development & Local Government, Trinidad & Tobago). It aggregates verified disaster data and generates minister-ready reports where **every number is computed deterministically and cited to its source** — the LLM only writes prose around pre-computed facts, never calculates or invents figures.

### Core architectural concepts (do not deviate)

1. **Data Module** — a pluggable unit that owns one data source. It knows how to ingest, normalize, and query that source, and exposes named **metrics** (parameterized queries returning cited facts). First module: `survey123`. Future modules (sitreps, WRHA river levels) plug in without touching existing code.

2. **Report Template** — a declarative unit that knows (a) which metrics to request from which data modules, with which parameters, and (b) the prompt used to narrate the resulting fact table. Templates are data, not code — adding/improving a template must not require changing the engine.

3. **Fact Table** — the JSON contract between the deterministic layer and the LLM. Every fact carries: metric name, value, scope (region/window), source reference, as-of timestamp, and a citation id.

4. **Citation Checker** — a deterministic post-generation validator. Every number appearing in the LLM's output must match a value in the fact table; every claim paragraph must carry a citation id. Reports failing the check are flagged, never silently delivered.

5. **Renderer** — turns the validated narrative + fact table into output (markdown first; Word/PDF later).

```
                ┌────────────────────────────────────────────┐
                │              Report Engine                 │
  Template ───▶ │  resolve template → call data modules      │
  + params      │  → build Fact Table → LLM narration        │
                │  → Citation Check → Render                 │
                └───────┬──────────────────────────┬─────────┘
                        │                          │
              ┌─────────▼─────────┐      ┌─────────▼─────────┐
              │  Data Module:     │      │  Data Module:     │
              │  survey123        │      │  sitreps (Phase 2)│
              │  ingest/normalize │      │  WRHA (Phase 2)   │
              │  /metrics         │      └───────────────────┘
              └───────────────────┘
```

### Stack
- Python 3.11+, FastAPI, SQLAlchemy 2.x, Pydantic v2, Postgres (SQLite acceptable for local dev), Alembic for migrations.
- LLM calls via the Anthropic API (model configurable via env; keep the client behind an interface so it's swappable).
- React/TypeScript front-end is Phase 2 — MVP is API + CLI + markdown output.
- Deployment target: Dokploy (Dockerfile + docker-compose required).

---

## 2. Repository structure

```
ai4sids-reporting/
├── PLAN.md                        # this file
├── pyproject.toml
├── docker-compose.yml
├── Dockerfile
├── alembic/
├── app/
│   ├── main.py                    # FastAPI app factory
│   ├── config.py                  # pydantic-settings; env-driven
│   ├── db.py                      # engine/session
│   ├── core/
│   │   ├── registry.py            # DataModule + Template registries
│   │   ├── contracts.py           # Fact, FactTable, MetricSpec, Citation (Pydantic)
│   │   ├── engine.py              # report generation orchestrator
│   │   ├── citation_check.py      # deterministic number/citation validator
│   │   ├── llm.py                 # LLM client interface + Anthropic impl
│   │   └── renderer.py            # markdown renderer (docx later)
│   ├── modules/
│   │   └── survey123/
│   │       ├── module.py          # implements DataModule protocol
│   │       ├── models.py          # SQLAlchemy: Incident
│   │       ├── ingest.py          # xlsx/csv → normalized rows (PII stripped)
│   │       ├── normalize.py       # value mappings (corporations, incident types)
│   │       └── metrics.py         # named metric queries
│   ├── templates/
│   │   ├── loader.py              # loads YAML template definitions
│   │   └── definitions/
│   │       ├── minister_regional_comparison.yaml
│   │       └── single_region_report.yaml
│   └── api/
│       ├── reports.py             # POST /reports, GET /reports/{id}
│       ├── ingest.py              # POST /ingest/{module}
│       └── meta.py                # GET /templates, GET /modules, GET /metrics
├── cli.py                         # typer CLI: ingest, generate, list-templates
└── tests/
    ├── test_normalize.py
    ├── test_metrics.py
    ├── test_citation_check.py
    └── test_engine.py
```

---

## 3. Core contracts (write these first — everything depends on them)

`app/core/contracts.py`:

```python
class Citation(BaseModel):
    cid: str                      # "S123-001" — stable within one fact table
    module: str                   # "survey123"
    description: str              # human-readable source description
    query_ref: str                # metric name + params, reproducible
    record_ids: list[str] | None  # underlying GlobalIDs/ObjectIDs when applicable
    as_of: datetime

class Fact(BaseModel):
    metric: str                   # "homes_damaged_count"
    value: int | float | str
    unit: str | None
    scope: dict[str, str]         # {"corporation": "sangre_grande", "window": "..."}
    breakdown: dict[str, int | float] | None   # e.g. per-incident-type split
    verification: Literal["validated", "pending", "mixed", "n/a"]
    citation: Citation

class FactTable(BaseModel):
    request_id: str
    template: str
    params: dict
    generated_at: datetime
    facts: list[Fact]
    gaps: list[str]               # explicit "no data for X" notes — never omit silently

class MetricSpec(BaseModel):
    name: str
    description: str
    params_schema: dict           # JSON schema of accepted params
    module: str
```

`app/core/registry.py` — a `DataModule` Protocol:

```python
class DataModule(Protocol):
    name: str
    def ingest(self, file_path: Path) -> IngestResult: ...
    def list_metrics(self) -> list[MetricSpec]: ...
    def run_metric(self, name: str, params: dict, session: Session) -> list[Fact]: ...
```

Modules self-register via a simple registry dict at import time. The engine only ever talks to the registry — it must have zero knowledge of Survey123 specifics.

---

## 4. Data Module: survey123 (build this completely before anything else)

### 4.1 Source data reality (verified against the real export, 14,942 rows, 78 cols)

- Sheet `survey_0`; key columns: ObjectID, GlobalID, CreationDate, Organisation, Date of Event, Community, Municipal Boundary, Incident Type (+ Other), Incident Summary, injuries/deaths flags and counts, Building Damage, Crops and Livestock, Personal Items, Furniture and Appliances, Action Taken, Relief Items, Shelter, Estimate Cost of Damage, Follow Up Recommendation, Validated/NotValidated, Flood Type/Trigger/Height, x/y (lon/lat).
- `Municipal Boundary` has 15 variants: the 14 corporations (names truncated at ~31 chars, mixed case in raw data — lowercase before mapping) plus **594 blank rows**. Blanks must be retained with `corporation = None` and surfaced as a data gap, not dropped.
- `Incident Type` controlled vocab (lowercased): `flooding_`, `other`, `landslide`, `over grown tree`, `fire`, `blown_off_roof`, `fallen_tree`, `earthquake`. When `other`, the real type is free text in `Other - Incident Type`.
- `Validated/NotValidated`: `Validated` (14,108) or blank (834). Treat blank as `pending`.
- Duplicate rows exist where officers typed literal "Duplicate entry" into name/summary fields — detect via that marker AND via repeated `Identification Card Number` + same event date, and flag (not delete) with `is_duplicate = True`; all metrics exclude flagged duplicates by default.

### 4.2 PII policy — enforce at ingestion, non-negotiable

The export contains national ID numbers, names, phone numbers, addresses, and occupant name lists. **The following source columns are NEVER written to the database**: Name of Person, Contact Information, Identification Card Number (all variants), Name of Second Person, Second Contact Information, Second Identification Card Number, "Please list the names of the occupants and their relation".
- For deduplication, store only a salted SHA-256 hash of the ID number (`dedup_hash`), never the raw value.
- `Address` is reduced to `street` (first comma-segment) + `community` — enough for "houses flooded on street X" tallies without storing full home addresses.
- Officer name/position may be stored (work context).
- Write a unit test asserting the Incident model has no columns for the banned fields.

### 4.3 Normalized model (`incidents` table)

```
id (pk), global_id (unique), object_id,
corporation (enum of 14 canonical slugs, nullable),
community, street,
incident_type (canonical enum), incident_type_other,
incident_summary,
event_date, event_time, assessment_date, creation_date,
occupants_count (int, parse 'other' + overflow column),
injuries_occurred (bool), injuries_count, deaths_occurred (bool), deaths_count,
building_damage, crops_livestock, personal_items, furniture_appliances,   # free text, kept for narration context ONLY, never counted from
action_taken (enum-ish), relief_items (free text),
shelter, special_needs_occupants (int),
estimated_damage_cost (numeric, nullable),
follow_up (raw multi-select string) + follow_up_flags (parsed booleans: relief_supplied, forwarded_to_agency, shelter_relocation, other),
validation_status (validated | pending),
is_duplicate (bool), duplicate_reason,
flood_type, flood_trigger, flood_height,
lon, lat,
officer_name, officer_position,
dedup_hash,
source_file, ingested_at
```

Normalization rules live in `normalize.py` as explicit dicts (corporation slug map, incident-type map) with an `UNMAPPED` fallback that logs and preserves the raw value in a `raw_*` column — never crash ingestion on a new value, never silently coerce.

### 4.4 Metrics to implement (v1)

All metrics accept `{corporation?, community?, date_from?, date_to?, include_pending?: bool=false}` and return Facts with verification labels. Every Fact's citation includes the reproducible query_ref and the contributing record GlobalIDs (capped at 200 ids; above that, count + query_ref only).

1. `incident_count` — total incidents, breakdown by incident_type.
2. `incidents_by_corporation` — counts per corporation (the backbone of the comparison template). Must include a `(no corporation recorded)` bucket when blanks exist in the window.
3. `homes_affected_count` — incidents where building damage text is non-empty OR incident_type in {flooding_, fire, blown_off_roof}; breakdown validated vs pending.
4. `casualty_summary` — injuries_count sum, deaths_count sum. (Reports are infrastructure-first per the ministry, but ministers must never be blindsided on casualties — always computed, template decides placement.)
5. `street_level_tally` — incidents grouped by community + street within a corporation (the "houses flooded on a specific street" ask).
6. `relief_actions_summary` — counts of follow_up_flags (relief supplied / forwarded to agency / shelter relocation) — this is the "what is being done" content the minister needs.
7. `special_needs_count` — sum of special_needs_occupants.
8. `estimated_damage_total` — sum of estimated_damage_cost where present, WITH explicit coverage note ("based on N of M records reporting a cost estimate") — this field is sparsely filled and must never be presented as a complete total.
9. `data_coverage` — per corporation: record count, % validated, % duplicates flagged, latest record timestamp. Used by every template's data-quality footer.

### 4.5 Ingestion

`POST /ingest/survey123` (multipart xlsx/csv) and `cli.py ingest survey123 <file>`. Idempotent by `global_id` (upsert; newer EditDate wins). Returns IngestResult: rows read, inserted, updated, duplicates flagged, unmapped values encountered, PII columns dropped (assert list matches policy).

---

## 5. Report Templates

Templates are YAML files. The loader validates them against a Pydantic schema at startup; a bad template fails fast with a clear error.

### 5.1 Template schema

```yaml
name: string (unique)
title: string
description: string
params:                    # what the caller must/can supply
  - name: date_from
    required: true
  - name: date_to
    required: true
  - name: corporation      # only for single-region template
    required: true
data_requirements:         # ordered list of metric calls
  - module: survey123
    metric: incidents_by_corporation
    params: { date_from: "{date_from}", date_to: "{date_to}" }
  - module: survey123
    metric: relief_actions_summary
    params: { ... }
narration:
  system_prompt: |
    You are drafting a briefing for a government minister...
    RULES (absolute):
    - Use ONLY numbers present in the fact table. Never compute, sum, or estimate.
    - Every sentence containing a figure ends with its citation marker, e.g. [S123-003].
    - Distinguish validated vs pending figures exactly as labeled.
    - If the fact table lists gaps, state them plainly in a Data Gaps section.
    - Infrastructure impact leads; casualties stated once, factually.
    - Bite-sized: the whole briefing fits on one page.
  output_sections: [headline, regional_comparison, actions_taken, data_gaps]
render:
  format: markdown
  include_citation_appendix: true
```

### 5.2 Template 1: `minister_regional_comparison`
Params: date window. Pulls `incidents_by_corporation`, `homes_affected_count` (per corporation via breakdown), `relief_actions_summary`, `casualty_summary`, `data_coverage`. Output: one-page briefing — headline national numbers, a per-corporation comparison table (rendered from facts by the renderer, NOT written by the LLM — tables of numbers are deterministic output), short narrative on the 2–3 most-affected regions, actions-taken summary, data-gaps footer, citation appendix.

### 5.3 Template 2: `single_region_report`
Params: corporation (+ optional community), date window. Pulls `incident_count`, `street_level_tally`, `homes_affected_count`, `relief_actions_summary`, `special_needs_count`, `estimated_damage_total`, `data_coverage`. Output: region deep-dive — incident breakdown, worst-affected streets/communities, relief actions, damage-cost coverage caveat, citation appendix.

### 5.4 Engine flow (`core/engine.py`)

1. Load template, validate params.
2. Execute data_requirements in order against the registry → assemble FactTable (assign citation ids sequentially; collect gaps).
3. Render deterministic components (comparison table, citation appendix) directly from FactTable.
4. Call LLM with system_prompt + FactTable JSON → narrative sections.
5. Run citation_check on narrative:
   - extract every numeric token (handle "14,942", "2 hours", percentages; ignore citation markers and dates matching the requested window),
   - each must equal a fact value or breakdown value in the table,
   - each figure-bearing sentence must contain a `[cid]` present in the table.
   Failure → retry narration once with the violations appended to the prompt; second failure → return report with status `needs_review` and the violation list attached. Never raise the failure away.
6. Persist report (params, fact table, narrative, status, violations) — reports must be reproducible and auditable.
7. Render markdown; return report id + content.

### 5.5 API surface (MVP)

```
POST /ingest/survey123
GET  /modules                     # registered modules + their metrics
GET  /templates                   # available templates + params schema
POST /reports {template, params}  # generate; returns report id + markdown + status
GET  /reports/{id}                # retrieve, incl. fact table + violations
```

---

## 6. Build order (work in this exact sequence; each step has a definition of done)

**Step 1 — Skeleton + contracts.** Repo scaffold, config, db, contracts.py, registry.py, empty FastAPI app, docker-compose with Postgres. DoD: `pytest` runs, app boots, `/modules` returns [].

**Step 2 — survey123 ingestion + normalization.** models, alembic migration, normalize maps, ingest with PII stripping + dedup flagging, CLI ingest. DoD: ingesting the real sample file yields ~14,942 rows, 14 corporations mapped + null bucket, banned-columns test passes, duplicate-marker rows flagged, re-ingest is a no-op.

**Step 3 — metrics.** All 9 metrics with tests using a small fixture dataset with known expected counts (hand-computed). DoD: every metric returns correctly cited Facts; `include_pending` toggles verification handling; blank-corporation bucket appears.

**Step 4 — citation checker.** Pure function, heavily tested: passing case, invented-number case, missing-citation case, formatted numbers, percentages. DoD: test suite covers all listed cases.

**Step 5 — engine + templates.** Loader, both YAML templates, engine flow incl. retry logic, LLM client (with a fake/stub client for tests so the whole engine is testable offline). DoD: `cli.py generate minister_regional_comparison --date-from ... --date-to ...` against ingested sample data produces a complete markdown report with citation appendix; a deliberately-corrupted fake LLM output is caught and flagged `needs_review`.

**Step 6 — API + persistence + Docker.** Report storage, endpoints, Dockerfile. DoD: full flow via HTTP; container builds and runs via compose.

**Step 7 (buffer / stretch)** — docx rendering of reports (use python-docx), simple React review page. Only if Steps 1–6 are green.

Out of scope for this build (do not start): sitreps module, WRHA module, live ArcGIS integration, auth beyond a single API key, notifications. The architecture must make these trivially addable — that's the test of the module design, not a reason to build them now.

---

## 7. Conventions & guardrails for the implementing agent

- Pydantic v2 everywhere at boundaries; SQLAlchemy 2.0 style (no legacy Query API).
- No LLM call anywhere except `core/llm.py`; everything else must be testable without a network.
- Every metric is a pure function of (params, session) — no hidden state.
- Log unmapped/unexpected source values; never drop rows silently. "gaps" in the FactTable is the mechanism for surfacing absence.
- Money: `estimated_damage_cost` stored as Numeric, currency assumed TTD, always reported with coverage caveat.
- Timezone: store UTC, report in America/Port_of_Spain.
- Seed a `fixtures/sample_small.csv` (~30 hand-crafted rows with known totals) for tests; the real export is for manual verification only and must not be committed.
- Commit after each Step's DoD passes.
