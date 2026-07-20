# DB-Backed Versioned Templates + MCP-Pluggable Data Modules Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move report templates out of static YAML files into a versioned DB table (so new report types / added metrics don't require a deploy, and every generated report is traceable to the exact template version that produced it), and introduce an MCP-based abstraction for data modules so a module's metrics can be served either in-process (as today) or by an external MCP server, with zero change to the report engine's calling code either way.

**Architecture:** `Template` (pydantic, `app/core/contracts.py`) stays the single source of truth for template *shape* and validation; only its *storage* changes, from `app/templates/definitions/*.yaml` files loaded into an in-memory dict at startup, to rows in a new `report_templates` table read on demand via `app/core/template_store.py`. Versioning is additive-only (no in-place edits, no exclusion/filtering of metrics at request time — confirmed out of scope for this plan) — each edit creates a new row, `Report.template_version` freezes which one produced a given report. Separately, `app/core/registry.py`'s `DataModule` protocol is left untouched, and a second implementation (`McpDataModule`) is added alongside the existing `Survey123Module` — `assemble_fact_table` keeps calling `module.run_metric(...)` exactly as it does today, so which concrete class is registered under a module name (in-process or MCP-backed) is invisible to the engine.

**Tech Stack:** FastAPI, SQLAlchemy 2.x, Pydantic v2, Alembic, pytest, `mcp` (official Python MCP SDK, new dependency), Typer.

## Global Constraints

- Python 3.13, repo root for all commands is `apps/backend/`.
- SQLAlchemy 2.0 query style (`select(...)`, `session.execute(...).scalars()`), matching every existing file in `app/core/`.
- Pydantic v2 (`model_validate`, `model_dump`, `model_copy(update=...)`).
- Alembic migrations must chain from the current head revision `6ae0a692151e` (`create_reports_table`) — verify with `alembic heads` before adding a new revision.
- Per `PLAN.md` and the existing test suite (see `tests/test_cli_generate.py`'s comment on `FakeLLMClient`), every test in this plan must be network-free — never exercise `OllamaLLMClient` or a real Ollama server.
- Every number in a generated report must still trace to a `Fact`/`Citation` in the `FactTable`; nothing in this plan changes `app/core/citation_check.py` or the "LLM writes prose only" contract.
- No exclusion/filtering of `data_requirements` at request time, and no LLM-driven selection of which metrics to run — both explicitly ruled out during planning. Template evolution is additive-version-only.
- Dependency changes go in `apps/backend/pyproject.toml`; install with `uv sync` (this project uses `uv`, evidenced by `uv.lock`-style dependency pinning in `pyproject.toml`).

---

## File Structure

**New files:**
- `alembic/versions/a7d3f8e91c42_add_template_version_to_reports.py` — migration
- `alembic/versions/f3a1c9d7b204_create_report_templates_table.py` — migration
- `app/core/template_models.py` — `TemplateRecord` SQLAlchemy model
- `app/core/template_store.py` — versioned template CRUD/read functions
- `app/mcp_server/__init__.py` — empty package marker
- `app/mcp_server/survey123_server.py` — reference MCP server wrapping `survey123` metrics
- `app/core/mcp_module.py` — `McpDataModule`, a `DataModule`-conforming MCP client adapter
- `tests/test_template_store.py`
- `tests/test_cli_templates.py`
- `tests/test_mcp_data_module.py`

**Modified files:**
- `app/core/contracts.py` — add `Template.version`, `FactTable.template_version`
- `app/core/engine.py` — stamp `template_version` through `assemble_fact_table`/`generate_report`/`GeneratedReport`
- `app/core/report_models.py` — add `Report.template_version` column
- `app/core/report_store.py` — persist `template_version`
- `app/core/registry.py` — remove template registry (superseded by `template_store.py`); module registry untouched
- `app/api/meta.py` — `GET /templates` reads from `template_store`, response includes `version`
- `app/api/reports.py` — `POST /reports` / `GET /reports/{id}` use `template_store`, response includes `template_version`
- `app/main.py` — drop YAML-loading startup code
- `cli.py` — add `templates import` / `templates import-all` commands; `generate`/`list-templates` read from `template_store`
- `app/modules/survey123/module.py` — add `get_survey123_module()` transport-switch factory
- `app/config.py` — add `survey123_transport` setting
- `pyproject.toml` — add `mcp` dependency
- Test updates: `tests/test_contracts.py`, `tests/test_engine_assembly.py`, `tests/test_engine_generate.py`, `tests/test_report_store.py`, `tests/test_api_reports.py`, `tests/test_api_templates.py`, `tests/test_survey123_module.py`, `tests/test_cli.py`, `tests/test_cli_generate.py`, `tests/test_template_loader.py`
- Deleted: `tests/test_template_registry.py` (superseded by `tests/test_template_store.py`)

---

### Task 1: Thread template version through contracts and the engine

**Files:**
- Modify: `app/core/contracts.py:72-79` (`Template`), `app/core/contracts.py:26-32` (`FactTable`)
- Modify: `app/core/engine.py:56-63` (`assemble_fact_table`), `app/core/engine.py:66-74` (`GeneratedReport`), `app/core/engine.py:101-110` (`generate_report`)
- Test: `tests/test_template_loader.py`, `tests/test_contracts.py`, `tests/test_engine_assembly.py`, `tests/test_engine_generate.py`

**Interfaces:**
- Produces: `Template.version: int` (default `1`), `FactTable.template_version: int` (default `1`), `GeneratedReport.template_version: int` (default `1`) — later tasks (2, 3) rely on all three existing.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_template_loader.py` (after `test_template_validates_from_dict`):

```python
def test_template_version_defaults_to_one():
    template = Template.model_validate(make_minimal_template_dict())

    assert template.version == 1


def test_template_version_can_be_set_explicitly():
    raw = make_minimal_template_dict()
    raw["version"] = 3

    template = Template.model_validate(raw)

    assert template.version == 3
```

Add to `tests/test_contracts.py` (after `test_fact_table_collects_facts_and_gaps`):

```python
def test_fact_table_template_version_defaults_to_one():
    table = FactTable(
        request_id="req-001",
        template="minister_regional_comparison",
        params={},
        generated_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        facts=[],
        gaps=[],
    )

    assert table.template_version == 1
```

In `tests/test_engine_assembly.py`, extend `test_assemble_fact_table_calls_all_data_requirements_and_renumbers_citations`:

```python
def test_assemble_fact_table_calls_all_data_requirements_and_renumbers_citations(tmp_path):
    session = make_session(tmp_path)
    template = make_minister_template().model_copy(update={"version": 4})

    fact_table = assemble_fact_table(
        template, {"date_from": "2024-06-01", "date_to": "2024-06-30"}, session, "req-1"
    )

    assert fact_table.request_id == "req-1"
    assert fact_table.template == "minister_regional_comparison"
    assert fact_table.template_version == 4
    assert len(fact_table.facts) == 8
    assert [f.citation.cid for f in fact_table.facts] == [f"C{i:03d}" for i in range(1, 9)]
```

In `tests/test_engine_generate.py`, extend `test_generate_report_with_auto_narrative_fake_client_passes`:

```python
def test_generate_report_with_auto_narrative_fake_client_passes(tmp_path):
    session = make_session(tmp_path)
    template = make_minister_template().model_copy(update={"version": 2})

    report = generate_report(
        template, {"date_from": "2024-06-01", "date_to": "2024-06-30"}, session, FakeLLMClient()
    )

    assert report.status == "ok"
    assert report.violations == []
    assert report.template_version == 2
    assert report.fact_table.template_version == 2
    assert "# Regional Comparison Briefing" in report.markdown
    assert "## Citation Appendix" in report.markdown
    assert report.request_id
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_template_loader.py tests/test_contracts.py tests/test_engine_assembly.py tests/test_engine_generate.py -v`
Expected: FAIL — `AttributeError`/`assert 1 == 4` style failures, since `version`/`template_version` don't exist yet.

- [ ] **Step 3: Implement**

In `app/core/contracts.py`, update `Template` (lines 72-79):

```python
class Template(BaseModel):
    name: str
    version: int = 1
    title: str
    description: str
    params: list[TemplateParam]
    data_requirements: list[DataRequirement]
    narration: NarrationConfig
    render: RenderConfig
```

Update `FactTable` (lines 26-32):

```python
class FactTable(BaseModel):
    request_id: str
    template: str
    template_version: int = 1
    params: dict
    generated_at: datetime
    facts: list[Fact]
    gaps: list[str]
```

In `app/core/engine.py`, update `assemble_fact_table`'s `FactTable(...)` construction (lines 56-63):

```python
    return FactTable(
        request_id=request_id,
        template=template.name,
        template_version=template.version,
        params=params,
        generated_at=datetime.now(timezone.utc),
        facts=renumbered,
        gaps=gaps,
    )
```

Update `GeneratedReport` (lines 66-74):

```python
class GeneratedReport(BaseModel):
    request_id: str
    template: str
    template_version: int = 1
    params: dict
    fact_table: FactTable
    narrative: str
    status: Literal["ok", "needs_review"]
    violations: list[CitationViolation]
    markdown: str
```

Update `generate_report`'s `GeneratedReport(...)` construction (lines 101-110):

```python
    return GeneratedReport(
        request_id=request_id,
        template=template.name,
        template_version=template.version,
        params=params,
        fact_table=fact_table,
        narrative=narrative,
        status=status,
        violations=result.violations,
        markdown=markdown,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_template_loader.py tests/test_contracts.py tests/test_engine_assembly.py tests/test_engine_generate.py tests/test_renderer.py tests/test_report_store.py -v`
Expected: PASS (the last two are included to confirm the new default fields don't break existing `Template`/`FactTable`/`GeneratedReport` construction sites that don't pass `version`/`template_version`).

- [ ] **Step 5: Commit**

```bash
git add app/core/contracts.py app/core/engine.py tests/test_template_loader.py tests/test_contracts.py tests/test_engine_assembly.py tests/test_engine_generate.py
git commit -m "engine: thread template_version through FactTable and GeneratedReport"
```

---

### Task 2: Add `Report.template_version` column + migration

**Files:**
- Create: `alembic/versions/a7d3f8e91c42_add_template_version_to_reports.py`
- Modify: `app/core/report_models.py:1-21`, `app/core/report_store.py:9-23`, `app/api/reports.py`
- Test: `tests/test_report_store.py`, `tests/test_api_reports.py`

**Interfaces:**
- Consumes: `GeneratedReport.template_version: int` (Task 1)
- Produces: `Report.template_version: int` column; `ReportDetail.template_version: int` in the `GET /reports/{id}` response — later tasks don't depend on this directly, but it completes the reproducibility chain this plan is for.

- [ ] **Step 1: Write the failing tests**

In `tests/test_report_store.py`, change `make_generated_report` to accept and thread the field, and add two new tests:

```python
def make_generated_report(status="ok", violations=None, template_version=1) -> GeneratedReport:
    citation = Citation(
        cid="C001",
        module="survey123",
        description="test",
        query_ref="incident_count()",
        record_ids=["GUID-1"],
        as_of=datetime(2024, 7, 1, tzinfo=timezone.utc),
    )
    fact = Fact(
        metric="incident_count",
        value=19,
        unit="incidents",
        scope={"corporation": "all"},
        breakdown=None,
        verification="validated",
        citation=citation,
    )
    fact_table = FactTable(
        request_id="req-1",
        template="minister_regional_comparison",
        template_version=template_version,
        params={"date_from": "2024-06-01", "date_to": "2024-06-30"},
        generated_at=datetime(2024, 7, 1, tzinfo=timezone.utc),
        facts=[fact],
        gaps=[],
    )
    return GeneratedReport(
        request_id="req-1",
        template="minister_regional_comparison",
        template_version=template_version,
        params={"date_from": "2024-06-01", "date_to": "2024-06-30"},
        fact_table=fact_table,
        narrative="There were 19 incidents recorded [C001].",
        status=status,
        violations=violations or [],
        markdown="# Test Report\n\nThere were 19 incidents recorded [C001].",
    )


def test_save_report_persists_default_template_version(tmp_path):
    session = make_session(tmp_path)
    report = make_generated_report()

    saved = save_report(report, session)

    assert saved.template_version == 1


def test_save_report_persists_explicit_template_version(tmp_path):
    session = make_session(tmp_path)
    report = make_generated_report(template_version=3)

    saved = save_report(report, session)

    assert saved.template_version == 3
```

In `tests/test_api_reports.py`, extend `test_get_reports_by_id_returns_full_detail`:

```python
def test_get_reports_by_id_returns_full_detail(monkeypatch):
    client = make_client(monkeypatch)
    _ingest_fixture()

    create_response = client.post(
        "/reports",
        json={
            "template": "minister_regional_comparison",
            "params": {"date_from": "2024-06-01", "date_to": "2024-06-30"},
        },
    )
    report_id = create_response.json()["id"]

    response = client.get(f"/reports/{report_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == report_id
    assert body["template"] == "minister_regional_comparison"
    assert body["template_version"] == 1
    assert "facts" in body["fact_table"]
    assert isinstance(body["violations"], list)
```

(This test won't pass until Task 4 wires `/reports` to `template_store` and templates are seeded — leave it failing/skipped for now and revisit; see Task 4 Step 4 which re-runs this exact test.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_report_store.py -v`
Expected: FAIL — `AttributeError: 'Report' object has no attribute 'template_version'`.

(Skip running `test_api_reports.py` here — it depends on Task 4's wiring and will fail for unrelated reasons until then.)

- [ ] **Step 3: Implement**

Create `alembic/versions/a7d3f8e91c42_add_template_version_to_reports.py`:

```python
"""add template_version to reports

Revision ID: a7d3f8e91c42
Revises: 6ae0a692151e
Create Date: 2026-07-16 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a7d3f8e91c42'
down_revision: Union[str, Sequence[str], None] = '6ae0a692151e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('reports', sa.Column('template_version', sa.Integer(), nullable=False, server_default='1'))
    op.alter_column('reports', 'template_version', server_default=None)


def downgrade() -> None:
    op.drop_column('reports', 'template_version')
```

Update `app/core/report_models.py`:

```python
from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    template: Mapped[str] = mapped_column(String, nullable=False)
    template_version: Mapped[int] = mapped_column(Integer, nullable=False)
    params: Mapped[dict] = mapped_column(JSON, nullable=False)
    fact_table: Mapped[dict] = mapped_column(JSON, nullable=False)
    narrative: Mapped[str] = mapped_column(Text, nullable=False)
    markdown: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    violations: Mapped[list] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
```

Update `app/core/report_store.py`'s `save_report`:

```python
def save_report(report: GeneratedReport, session: Session) -> Report:
    db_report = Report(
        id=report.request_id,
        template=report.template,
        template_version=report.template_version,
        params=report.params,
        fact_table=report.fact_table.model_dump(mode="json"),
        narrative=report.narrative,
        markdown=report.markdown,
        status=report.status,
        violations=[v.model_dump() for v in report.violations],
        created_at=datetime.now(timezone.utc),
    )
    session.add(db_report)
    session.commit()
    return db_report
```

In `app/api/reports.py`, add `template_version` to `ReportDetail` and populate it:

```python
class ReportDetail(BaseModel):
    id: str
    template: str
    template_version: int
    params: dict
    fact_table: dict
    narrative: str
    markdown: str
    status: str
    violations: list


@router.get("/reports/{report_id}", response_model=ReportDetail)
def read_report(report_id: str, session: Session = Depends(get_session)) -> ReportDetail:
    db_report = get_report(report_id, session)
    if db_report is None:
        raise HTTPException(status_code=404, detail=f"report not found: {report_id}")

    return ReportDetail(
        id=db_report.id,
        template=db_report.template,
        template_version=db_report.template_version,
        params=db_report.params,
        fact_table=db_report.fact_table,
        narrative=db_report.narrative,
        markdown=db_report.markdown,
        status=db_report.status,
        violations=db_report.violations,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_report_store.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add alembic/versions/a7d3f8e91c42_add_template_version_to_reports.py app/core/report_models.py app/core/report_store.py app/api/reports.py tests/test_report_store.py tests/test_api_reports.py
git commit -m "reports: persist and expose template_version for reproducibility"
```

---

### Task 3: `TemplateRecord` model, migration, and `template_store.py`

**Files:**
- Create: `alembic/versions/f3a1c9d7b204_create_report_templates_table.py`
- Create: `app/core/template_models.py`
- Create: `app/core/template_store.py`
- Test: `tests/test_template_store.py`

**Interfaces:**
- Consumes: `Template` (contracts.py, Task 1's `version` field), `load_templates_from_directory` (`app/templates/loader.py`)
- Produces: `create_template_version(template: Template, session: Session) -> Template`, `get_latest_template_version(name: str, session: Session) -> Template | None`, `get_template_version(name: str, version: int, session: Session) -> Template | None`, `list_latest_templates(session: Session) -> list[Template]`, `import_template_directory(directory: Path, session: Session) -> list[Template]` — Tasks 4 and 5 call these by these exact names.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_template_store.py`:

```python
from sqlalchemy.orm import sessionmaker

from app.core.contracts import DataRequirement, NarrationConfig, RenderConfig, Template, TemplateParam
from app.core.template_store import (
    create_template_version,
    get_latest_template_version,
    get_template_version,
    list_latest_templates,
)
from app.db import Base, make_engine


def make_session(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


def make_template(name="single_region_report", **overrides) -> Template:
    defaults = dict(
        name=name,
        title="Single Region Deep Dive",
        description="test",
        params=[TemplateParam(name="corporation", required=True)],
        data_requirements=[DataRequirement(module="survey123", metric="incident_count")],
        narration=NarrationConfig(system_prompt="p", output_sections=["headline"]),
        render=RenderConfig(),
    )
    defaults.update(overrides)
    return Template(**defaults)


def test_create_template_version_starts_at_one(tmp_path):
    session = make_session(tmp_path)

    stored = create_template_version(make_template(), session)

    assert stored.version == 1


def test_create_template_version_increments_for_same_name(tmp_path):
    session = make_session(tmp_path)
    create_template_version(make_template(), session)

    stored = create_template_version(make_template(title="Updated title"), session)

    assert stored.version == 2
    assert stored.title == "Updated title"


def test_create_template_version_is_independent_per_name(tmp_path):
    session = make_session(tmp_path)
    create_template_version(make_template(name="template_a"), session)

    stored = create_template_version(make_template(name="template_b"), session)

    assert stored.version == 1


def test_get_latest_template_version_returns_highest_version(tmp_path):
    session = make_session(tmp_path)
    create_template_version(make_template(), session)
    create_template_version(make_template(title="v2 title"), session)

    latest = get_latest_template_version("single_region_report", session)

    assert latest is not None
    assert latest.version == 2
    assert latest.title == "v2 title"


def test_get_latest_template_version_returns_none_for_unknown_name(tmp_path):
    session = make_session(tmp_path)

    assert get_latest_template_version("does_not_exist", session) is None


def test_get_template_version_returns_frozen_historical_version(tmp_path):
    session = make_session(tmp_path)
    create_template_version(make_template(), session)
    create_template_version(make_template(title="v2 title"), session)

    v1 = get_template_version("single_region_report", 1, session)

    assert v1 is not None
    assert v1.title == "Single Region Deep Dive"


def test_list_latest_templates_returns_one_entry_per_name_at_highest_version(tmp_path):
    session = make_session(tmp_path)
    create_template_version(make_template(name="template_a"), session)
    create_template_version(make_template(name="template_a", title="a v2"), session)
    create_template_version(make_template(name="template_b"), session)

    templates = list_latest_templates(session)

    assert [(t.name, t.version, t.title) for t in templates] == [
        ("template_a", 2, "a v2"),
        ("template_b", 1, "Single Region Deep Dive"),
    ]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_template_store.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.template_store'`.

- [ ] **Step 3: Implement**

Create `alembic/versions/f3a1c9d7b204_create_report_templates_table.py`:

```python
"""create report_templates table

Revision ID: f3a1c9d7b204
Revises: a7d3f8e91c42
Create Date: 2026-07-16 10:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f3a1c9d7b204'
down_revision: Union[str, Sequence[str], None] = 'a7d3f8e91c42'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('report_templates',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(), nullable=False),
    sa.Column('description', sa.String(), nullable=False),
    sa.Column('params', sa.JSON(), nullable=False),
    sa.Column('data_requirements', sa.JSON(), nullable=False),
    sa.Column('narration', sa.JSON(), nullable=False),
    sa.Column('render', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name', 'version', name='uq_report_templates_name_version'),
    )


def downgrade() -> None:
    op.drop_table('report_templates')
```

Create `app/core/template_models.py`:

```python
from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class TemplateRecord(Base):
    __tablename__ = "report_templates"
    __table_args__ = (UniqueConstraint("name", "version", name="uq_report_templates_name_version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    params: Mapped[list] = mapped_column(JSON, nullable=False)
    data_requirements: Mapped[list] = mapped_column(JSON, nullable=False)
    narration: Mapped[dict] = mapped_column(JSON, nullable=False)
    render: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
```

Create `app/core/template_store.py`:

```python
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.contracts import Template
from app.core.template_models import TemplateRecord
from app.templates.loader import load_templates_from_directory


def _to_template(record: TemplateRecord) -> Template:
    return Template.model_validate(
        {
            "name": record.name,
            "version": record.version,
            "title": record.title,
            "description": record.description,
            "params": record.params,
            "data_requirements": record.data_requirements,
            "narration": record.narration,
            "render": record.render,
        }
    )


def create_template_version(template: Template, session: Session) -> Template:
    latest_version = session.execute(
        select(func.max(TemplateRecord.version)).where(TemplateRecord.name == template.name)
    ).scalar()
    next_version = (latest_version or 0) + 1

    record = TemplateRecord(
        name=template.name,
        version=next_version,
        title=template.title,
        description=template.description,
        params=[p.model_dump() for p in template.params],
        data_requirements=[d.model_dump() for d in template.data_requirements],
        narration=template.narration.model_dump(),
        render=template.render.model_dump(),
        created_at=datetime.now(timezone.utc),
    )
    session.add(record)
    session.commit()
    return _to_template(record)


def get_latest_template_version(name: str, session: Session) -> Template | None:
    record = (
        session.execute(
            select(TemplateRecord).where(TemplateRecord.name == name).order_by(TemplateRecord.version.desc())
        )
        .scalars()
        .first()
    )
    return _to_template(record) if record else None


def get_template_version(name: str, version: int, session: Session) -> Template | None:
    record = (
        session.execute(
            select(TemplateRecord).where(TemplateRecord.name == name, TemplateRecord.version == version)
        )
        .scalars()
        .first()
    )
    return _to_template(record) if record else None


def list_latest_templates(session: Session) -> list[Template]:
    subquery = (
        select(TemplateRecord.name, func.max(TemplateRecord.version).label("max_version"))
        .group_by(TemplateRecord.name)
        .subquery()
    )
    records = (
        session.execute(
            select(TemplateRecord).join(
                subquery,
                (TemplateRecord.name == subquery.c.name) & (TemplateRecord.version == subquery.c.max_version),
            )
        )
        .scalars()
        .all()
    )
    return [_to_template(r) for r in sorted(records, key=lambda r: r.name)]


def import_template_directory(directory: Path, session: Session) -> list[Template]:
    return [create_template_version(template, session) for template in load_templates_from_directory(directory)]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_template_store.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add alembic/versions/f3a1c9d7b204_create_report_templates_table.py app/core/template_models.py app/core/template_store.py tests/test_template_store.py
git commit -m "templates: add versioned DB storage alongside the Template contract"
```

---

### Task 4: Wire `template_store` into the API/CLI and retire the in-memory template registry

**Files:**
- Modify: `app/core/registry.py:1-58` (remove template bits, keep module bits)
- Modify: `app/api/meta.py`, `app/api/reports.py`, `app/main.py`
- Modify: `tests/test_api_templates.py`, `tests/test_api_reports.py`, `tests/test_survey123_module.py`, `tests/test_meta_api.py` (no `reset_template_registry` there — verify), `tests/test_cli.py`
- Delete: `tests/test_template_registry.py`

**Interfaces:**
- Consumes: `template_store.get_latest_template_version`, `template_store.list_latest_templates`, `template_store.import_template_directory` (Task 3)
- Produces: `/templates` and `/reports` now require a DB session with the `report_templates` table migrated and at least one template imported — Task 5's CLI import command is how that happens outside of tests.

- [ ] **Step 1: Write the failing tests**

Rewrite `tests/test_api_templates.py`:

```python
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.registry import reset_registry
from app.core.template_store import import_template_directory
from app.db import Base, engine as db_engine
from app.main import create_app

TEMPLATES_DIR = Path(__file__).parent.parent / "app" / "templates" / "definitions"
DEV_DB_PATH = Path(__file__).parent.parent / "dev.db"


@pytest.fixture(autouse=True)
def _clean_state():
    reset_registry()
    db_engine.dispose()
    if DEV_DB_PATH.exists():
        DEV_DB_PATH.unlink()
    yield
    reset_registry()
    db_engine.dispose()
    if DEV_DB_PATH.exists():
        DEV_DB_PATH.unlink()


def make_client() -> TestClient:
    from sqlalchemy.orm import sessionmaker

    Base.metadata.create_all(db_engine)
    Session = sessionmaker(bind=db_engine)
    session = Session()
    import_template_directory(TEMPLATES_DIR, session)
    session.close()

    app = create_app()
    return TestClient(app)


def test_get_templates_returns_both_real_templates():
    client = make_client()

    response = client.get("/templates")

    assert response.status_code == 200
    body = response.json()
    names = {t["name"] for t in body}
    assert names == {"minister_regional_comparison", "single_region_report"}
    assert all(t["version"] == 1 for t in body)


def test_get_templates_includes_params_with_required_flags():
    client = make_client()

    response = client.get("/templates")

    body = response.json()
    minister = next(t for t in body if t["name"] == "minister_regional_comparison")
    param_names = {p["name"] for p in minister["params"]}
    assert param_names == {"date_from", "date_to"}
    assert all(p["required"] for p in minister["params"])
```

In `tests/test_api_reports.py`, add DB template seeding to `make_client`:

```python
def make_client(monkeypatch) -> TestClient:
    from sqlalchemy.orm import sessionmaker

    from app.core.template_store import import_template_directory

    monkeypatch.setattr("app.core.llm.settings.llm_provider", "fake")
    Base.metadata.create_all(db_engine)
    Session = sessionmaker(bind=db_engine)
    session = Session()
    import_template_directory(TEMPLATES_DIR, session)
    session.close()
    app = create_app()
    return TestClient(app)
```

and add `TEMPLATES_DIR = Path(__file__).parent.parent / "app" / "templates" / "definitions"` near the top, next to `FIXTURE_PATH`. Also drop `reset_template_registry` from the import and fixture (`from app.core.registry import reset_registry` only), since Task 4 removes that function.

In `tests/test_survey123_module.py`, drop `reset_template_registry` from the import and the fixture body (keep `reset_registry`).

In `tests/test_cli.py`, no change needed (it only imports `reset_registry`, already confirmed by re-reading the file).

Delete `tests/test_template_registry.py`:

```bash
git rm tests/test_template_registry.py
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_api_templates.py tests/test_api_reports.py tests/test_survey123_module.py -v`
Expected: FAIL — `ImportError: cannot import name 'reset_template_registry'` (not removed yet) or 404s from `/templates`/`/reports` (nothing seeded/wired yet).

- [ ] **Step 3: Implement**

Update `app/core/registry.py` (remove all `Template`/`_templates` content, keep module registry only):

```python
from pathlib import Path
from typing import Protocol

from sqlalchemy.orm import Session

from app.core.contracts import Fact, IngestResult, MetricSpec


class DataModule(Protocol):
    name: str

    def ingest(self, file_path: Path) -> IngestResult: ...

    def list_metrics(self) -> list[MetricSpec]: ...

    def run_metric(self, name: str, params: dict, session: Session) -> list[Fact]: ...


_modules: dict[str, DataModule] = {}


def register_module(module: DataModule) -> None:
    if module.name in _modules:
        raise ValueError(f"data module already registered: {module.name}")
    _modules[module.name] = module


def get_module(name: str) -> DataModule | None:
    return _modules.get(name)


def list_modules() -> list[DataModule]:
    return list(_modules.values())


def reset_registry() -> None:
    _modules.clear()
```

Update `app/api/meta.py`:

```python
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.contracts import MetricSpec
from app.core.registry import list_modules
from app.core.template_store import list_latest_templates
from app.db import get_session

router = APIRouter()


class ModuleInfo(BaseModel):
    name: str
    metrics: list[MetricSpec]


@router.get("/modules", response_model=list[ModuleInfo])
def get_modules() -> list[ModuleInfo]:
    return [ModuleInfo(name=module.name, metrics=module.list_metrics()) for module in list_modules()]


class TemplateParamInfo(BaseModel):
    name: str
    required: bool


class TemplateInfo(BaseModel):
    name: str
    version: int
    title: str
    description: str
    params: list[TemplateParamInfo]


@router.get("/templates", response_model=list[TemplateInfo])
def get_templates(session: Session = Depends(get_session)) -> list[TemplateInfo]:
    return [
        TemplateInfo(
            name=t.name,
            version=t.version,
            title=t.title,
            description=t.description,
            params=[TemplateParamInfo(name=p.name, required=p.required) for p in t.params],
        )
        for t in list_latest_templates(session)
    ]
```

Update `app/api/reports.py`'s `create_report` to use `template_store`:

```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.engine import generate_report
from app.core.llm import get_default_llm_client
from app.core.report_store import get_report, save_report
from app.core.template_store import get_latest_template_version
from app.db import get_session

router = APIRouter()


class GenerateReportRequest(BaseModel):
    template: str
    params: dict


class GenerateReportResponse(BaseModel):
    id: str
    status: str
    markdown: str


@router.post("/reports", response_model=GenerateReportResponse)
def create_report(
    request: GenerateReportRequest, session: Session = Depends(get_session)
) -> GenerateReportResponse:
    template = get_latest_template_version(request.template, session)
    if template is None:
        raise HTTPException(status_code=404, detail=f"unknown template: {request.template}")

    try:
        report = generate_report(template, request.params, session, get_default_llm_client())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    save_report(report, session)

    return GenerateReportResponse(id=report.request_id, status=report.status, markdown=report.markdown)
```

(Leave the `ReportDetail`/`read_report` section exactly as Task 2 left it.)

Update `app/main.py`:

```python
from fastapi import FastAPI

from app.api.ingest import router as ingest_router
from app.api.meta import router as meta_router
from app.api.reports import router as reports_router
from app.core.registry import register_module
from app.modules.survey123.module import survey123_module


def create_app() -> FastAPI:
    app = FastAPI(title="DMCU Reporting API")
    app.include_router(meta_router)
    app.include_router(reports_router)
    app.include_router(ingest_router)
    register_module(survey123_module)
    return app


app = create_app()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_api_templates.py tests/test_api_reports.py tests/test_survey123_module.py tests/test_meta_api.py tests/test_cli.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/core/registry.py app/api/meta.py app/api/reports.py app/main.py tests/test_api_templates.py tests/test_api_reports.py tests/test_survey123_module.py
git commit -m "api: read templates from the DB-backed template_store, retire the in-memory template registry"
```

---

### Task 5: CLI `templates import` / `templates import-all` commands

**Files:**
- Modify: `cli.py`
- Test: `tests/test_cli_templates.py`, `tests/test_cli_generate.py`

**Interfaces:**
- Consumes: `template_store.create_template_version`, `template_store.import_template_directory`, `template_store.get_latest_template_version`, `template_store.list_latest_templates` (Task 3), `app.templates.loader.load_template`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_cli_templates.py`:

```python
from pathlib import Path

from typer.testing import CliRunner

from app.core.registry import reset_registry
from app.db import Base, engine as db_engine
from cli import app

runner = CliRunner()

TEMPLATES_DIR = Path(__file__).parent.parent / "app" / "templates" / "definitions"
DEV_DB_PATH = Path(__file__).parent.parent / "dev.db"


def _reset_state():
    reset_registry()
    db_engine.dispose()
    if DEV_DB_PATH.exists():
        DEV_DB_PATH.unlink()


def test_import_template_command_reports_version_one():
    _reset_state()
    Base.metadata.create_all(db_engine)

    try:
        result = runner.invoke(
            app, ["templates", "import", str(TEMPLATES_DIR / "single_region_report.yaml")]
        )

        assert result.exit_code == 0, result.stdout
        assert "single_region_report" in result.stdout
        assert "version 1" in result.stdout
    finally:
        _reset_state()


def test_import_template_command_twice_increments_version():
    _reset_state()
    Base.metadata.create_all(db_engine)

    try:
        runner.invoke(app, ["templates", "import", str(TEMPLATES_DIR / "single_region_report.yaml")])
        result = runner.invoke(
            app, ["templates", "import", str(TEMPLATES_DIR / "single_region_report.yaml")]
        )

        assert result.exit_code == 0, result.stdout
        assert "version 2" in result.stdout
    finally:
        _reset_state()


def test_import_all_command_imports_both_default_templates():
    _reset_state()
    Base.metadata.create_all(db_engine)

    try:
        result = runner.invoke(app, ["templates", "import-all", str(TEMPLATES_DIR)])

        assert result.exit_code == 0, result.stdout
        assert "minister_regional_comparison" in result.stdout
        assert "single_region_report" in result.stdout
    finally:
        _reset_state()
```

Update `tests/test_cli_generate.py`'s `test_list_templates_shows_both_real_templates` and `test_generate_minister_regional_comparison_produces_markdown_report` to seed via the new import command instead of relying on startup auto-load:

```python
def test_list_templates_shows_both_real_templates():
    _reset_state()
    Base.metadata.create_all(db_engine)

    try:
        runner.invoke(app, ["templates", "import-all", str(Path(__file__).parent.parent / "app" / "templates" / "definitions")])

        result = runner.invoke(app, ["list-templates"])

        assert result.exit_code == 0, result.stdout
        assert "minister_regional_comparison" in result.stdout
        assert "single_region_report" in result.stdout
    finally:
        _reset_state()
```

```python
def test_generate_minister_regional_comparison_produces_markdown_report(monkeypatch):
    monkeypatch.setattr(llm_module.settings, "llm_provider", "fake")

    _reset_state()
    Base.metadata.create_all(db_engine)

    try:
        runner.invoke(app, ["templates", "import-all", str(Path(__file__).parent.parent / "app" / "templates" / "definitions")])

        ingest_result = runner.invoke(app, ["ingest", "survey123", str(FIXTURE_PATH)])
        assert ingest_result.exit_code == 0, ingest_result.stdout

        result = runner.invoke(
            app,
            [
                "generate",
                "minister_regional_comparison",
                "--date-from",
                "2024-06-01",
                "--date-to",
                "2024-06-30",
            ],
        )

        assert result.exit_code == 0, result.stdout
        assert "# " in result.stdout
        assert "## Citation Appendix" in result.stdout
    finally:
        _reset_state()
```

`test_generate_missing_required_param_errors` and `test_generate_unknown_template_errors` need the same `templates import-all` call inserted before the `generate` invocation for the first (it needs the template to exist to reach the "missing param" error rather than "unknown template"); the second intentionally tests an unimported/unknown name, so it's unaffected.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli_templates.py -v`
Expected: FAIL — `No such command 'templates'`.

- [ ] **Step 3: Implement**

Update `cli.py`:

```python
from pathlib import Path

import typer
from sqlalchemy.orm import Session

from app.core.engine import generate_report
from app.core.llm import get_default_llm_client
from app.core.registry import get_module, register_module
from app.core.template_store import (
    create_template_version,
    get_latest_template_version,
    import_template_directory,
    list_latest_templates,
)
from app.db import SessionLocal
from app.modules.survey123.module import survey123_module
from app.templates.loader import load_template

app = typer.Typer()
ingest_app = typer.Typer()
templates_app = typer.Typer()
app.add_typer(ingest_app, name="ingest")
app.add_typer(templates_app, name="templates")


def _ensure_survey123_registered() -> None:
    if get_module("survey123") is None:
        register_module(survey123_module)


@ingest_app.command("survey123")
def ingest_survey123(file_path: Path) -> None:
    result = survey123_module.ingest(file_path)

    typer.echo(f"rows_read={result.rows_read}")
    typer.echo(f"rows_inserted={result.rows_inserted}")
    typer.echo(f"rows_updated={result.rows_updated}")
    typer.echo(f"duplicates_flagged={result.duplicates_flagged}")
    typer.echo(f"unmapped_values={result.unmapped_values}")
    typer.echo(f"pii_columns_dropped={result.pii_columns_dropped}")


@templates_app.command("import")
def import_template(yaml_path: Path) -> None:
    template = load_template(yaml_path)
    session: Session = SessionLocal()
    try:
        stored = create_template_version(template, session)
    finally:
        session.close()
    typer.echo(f"imported {stored.name} as version {stored.version}")


@templates_app.command("import-all")
def import_all_templates(directory: Path) -> None:
    session: Session = SessionLocal()
    try:
        stored = import_template_directory(directory, session)
    finally:
        session.close()
    for template in stored:
        typer.echo(f"imported {template.name} as version {template.version}")


@app.command("list-templates")
def list_templates_command() -> None:
    session = SessionLocal()
    try:
        templates = list_latest_templates(session)
    finally:
        session.close()
    for template in templates:
        typer.echo(f"{template.name} (v{template.version}): {template.title}")


@app.command()
def generate(
    template_name: str,
    date_from: str = typer.Option(None, "--date-from"),
    date_to: str = typer.Option(None, "--date-to"),
    corporation: str = typer.Option(None, "--corporation"),
    community: str = typer.Option(None, "--community"),
) -> None:
    _ensure_survey123_registered()
    session = SessionLocal()
    try:
        template = get_latest_template_version(template_name, session)
        if template is None:
            typer.echo(f"unknown template: {template_name}", err=True)
            raise typer.Exit(code=1)

        params = {
            "date_from": date_from,
            "date_to": date_to,
            "corporation": corporation,
            "community": community,
        }

        try:
            report = generate_report(template, params, session, get_default_llm_client())
        except ValueError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1) from exc
    finally:
        session.close()

    typer.echo(report.markdown)
    typer.echo(f"status: {report.status}", err=True)
    if report.violations:
        typer.echo(f"violations: {len(report.violations)}", err=True)


if __name__ == "__main__":
    app()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli_templates.py tests/test_cli_generate.py tests/test_cli.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add cli.py tests/test_cli_templates.py tests/test_cli_generate.py
git commit -m "cli: add templates import/import-all commands, backed by template_store"
```

---

### Task 6: Reference MCP server exposing `survey123` metrics

**Files:**
- Modify: `pyproject.toml` (add `mcp` dependency)
- Create: `app/mcp_server/__init__.py`
- Create: `app/mcp_server/survey123_server.py`

**Interfaces:**
- Consumes: `app.modules.survey123.metrics.METRIC_FUNCTIONS`, `METRIC_SPECS`, `app.db.SessionLocal`
- Produces: a stdio-runnable MCP server (`python -m app.mcp_server.survey123_server`) exposing one MCP tool per `survey123` metric, each returning a JSON-encoded `list[Fact]` as text content — Task 7's client adapter connects to this exact module path.

- [ ] **Step 1: Add the dependency**

In `pyproject.toml`, add to `dependencies`:

```toml
    "mcp>=1.9.0",
```

Run: `uv sync`
Expected: `mcp` installs cleanly alongside existing dependencies.

- [ ] **Step 2: Implement the server**

Create `app/mcp_server/__init__.py` (empty).

Create `app/mcp_server/survey123_server.py`:

```python
import json

from mcp.server.fastmcp import FastMCP

from app.core.contracts import Fact
from app.db import SessionLocal
from app.modules.survey123.metrics import METRIC_FUNCTIONS, METRIC_SPECS

mcp_app = FastMCP("survey123")


def _make_tool(metric_fn):
    def tool(params: dict) -> str:
        session = SessionLocal()
        try:
            facts: list[Fact] = metric_fn(params, session)
        finally:
            session.close()
        return json.dumps([f.model_dump(mode="json") for f in facts])

    return tool


for _spec in METRIC_SPECS:
    mcp_app.add_tool(_make_tool(METRIC_FUNCTIONS[_spec.name]), name=_spec.name, description=_spec.description)


if __name__ == "__main__":
    mcp_app.run()
```

**Note for the implementing engineer:** `FastMCP.add_tool`'s exact keyword names are current as of `mcp>=1.9`. If `uv sync` pulls a version whose API differs, run `python -c "from mcp.server.fastmcp import FastMCP; help(FastMCP.add_tool)"` and adjust the call accordingly — the behavior needed is "register a callable as a tool under an explicit name and description," which every 1.x release of this SDK supports in some form.

- [ ] **Step 3: Verify the server starts and lists tools**

Run: `cd apps/backend && timeout 5 python -m app.mcp_server.survey123_server` (or run it and Ctrl-C after confirming no import errors)
Expected: process starts and blocks on stdio (waiting for a client) without raising an exception — this only sanity-checks imports; the real behavioral test is Task 7's `test_mcp_data_module.py`, which drives this server through a real client.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml app/mcp_server/__init__.py app/mcp_server/survey123_server.py
git commit -m "mcp: add a reference MCP server exposing survey123 metrics as tools"
```

---

### Task 7: `McpDataModule` — MCP client adapter conforming to `DataModule`

**Files:**
- Create: `app/core/mcp_module.py`
- Test: `tests/test_mcp_data_module.py`

**Interfaces:**
- Consumes: `app.mcp_server.survey123_server` (Task 6, spawned as a subprocess), the `DataModule` protocol (`app/core/registry.py`)
- Produces: `McpDataModule(name, command, args, env=None)` — a `DataModule`-conforming class with `.name`, `.ingest()`, `.list_metrics()`, `.run_metric(name, params, session)`. Task 8 registers this in place of (or alongside) `Survey123Module`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_mcp_data_module.py`:

```python
import os
import sys
from pathlib import Path

from sqlalchemy.orm import sessionmaker

from app.core.mcp_module import McpDataModule
from app.db import Base, make_engine
from app.modules.survey123.ingest import ingest_csv
from app.modules.survey123.module import survey123_module

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "sample_small.csv"
BACKEND_ROOT = Path(__file__).parent.parent


def make_session(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    ingest_csv(FIXTURE_PATH, session, salt="test-salt")
    return session


def make_mcp_module(tmp_path) -> McpDataModule:
    env = dict(os.environ)
    env["DATABASE_URL"] = f"sqlite:///{tmp_path}/test.db"
    env["PYTHONPATH"] = str(BACKEND_ROOT)
    return McpDataModule(
        name="survey123",
        command=sys.executable,
        args=["-m", "app.mcp_server.survey123_server"],
        env=env,
    )


def test_mcp_module_list_metrics_matches_survey123_specs(tmp_path):
    make_session(tmp_path)
    module = make_mcp_module(tmp_path)

    specs = module.list_metrics()

    assert {s.name for s in specs} == {s.name for s in survey123_module.list_metrics()}


def test_mcp_module_run_metric_matches_inprocess_result(tmp_path):
    session = make_session(tmp_path)
    params = {"date_from": "2024-06-01", "date_to": "2024-06-30"}
    expected = survey123_module.run_metric("incident_count", params, session)
    module = make_mcp_module(tmp_path)

    facts = module.run_metric("incident_count", params, session=None)

    assert len(facts) == len(expected)
    assert facts[0].metric == expected[0].metric
    assert facts[0].value == expected[0].value
    assert facts[0].breakdown == expected[0].breakdown


def test_mcp_module_run_metric_returns_zero_count_for_no_matching_rows(tmp_path):
    make_session(tmp_path)
    module = make_mcp_module(tmp_path)

    facts = module.run_metric(
        "incident_count",
        {"corporation": "port_of_spain_city_corporation", "date_from": "2099-01-01", "date_to": "2099-01-02"},
        session=None,
    )

    assert len(facts) == 1
    assert facts[0].value == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_mcp_data_module.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.mcp_module'`.

- [ ] **Step 3: Implement**

Create `app/core/mcp_module.py`:

```python
import asyncio
import json
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from sqlalchemy.orm import Session

from app.core.contracts import Fact, IngestResult, MetricSpec


class McpDataModule:
    def __init__(self, name: str, command: str, args: list[str], env: dict[str, str] | None = None):
        self.name = name
        self._server_params = StdioServerParameters(command=command, args=args, env=env)

    def ingest(self, file_path: Path) -> IngestResult:
        raise NotImplementedError(f"{self.name} runs externally over MCP; ingest via that system directly")

    def list_metrics(self) -> list[MetricSpec]:
        tools = asyncio.run(self._list_tools())
        return [
            MetricSpec(
                name=tool.name,
                description=tool.description or "",
                params_schema=tool.inputSchema,
                module=self.name,
            )
            for tool in tools
        ]

    def run_metric(self, name: str, params: dict, session: Session) -> list[Fact]:
        raw = asyncio.run(self._call_tool(name, params))
        return [Fact.model_validate(item) for item in json.loads(raw)]

    async def _list_tools(self):
        async with stdio_client(self._server_params) as (read, write):
            async with ClientSession(read, write) as client_session:
                await client_session.initialize()
                result = await client_session.list_tools()
                return result.tools

    async def _call_tool(self, name: str, params: dict) -> str:
        async with stdio_client(self._server_params) as (read, write):
            async with ClientSession(read, write) as client_session:
                await client_session.initialize()
                result = await client_session.call_tool(name, arguments={"params": params})
                if result.isError:
                    detail = result.content[0].text if result.content else "unknown MCP error"
                    raise ValueError(f"MCP tool {name!r} on module {self.name!r} failed: {detail}")
                return result.content[0].text
```

**Note for the implementing engineer:** the exact shape of `CallToolResult` (`.content`, `.isError`) and `ClientSession`/`stdio_client` signatures are current as of `mcp>=1.9`; if the installed version differs, adjust `_list_tools`/`_call_tool` to match — the contract this class must uphold is "no session-layer or transport detail leaks past `run_metric`/`list_metrics`," so any adjustment stays internal to this file.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_mcp_data_module.py -v`
Expected: PASS (this spawns a real subprocess per call — expect these tests to be visibly slower than the rest of the suite; that's expected for this task, not a bug)

- [ ] **Step 5: Commit**

```bash
git add app/core/mcp_module.py tests/test_mcp_data_module.py
git commit -m "mcp: add McpDataModule, an MCP client adapter conforming to DataModule"
```

---

### Task 8: Transport switch — register `survey123` in-process or over MCP

**Files:**
- Modify: `app/config.py`
- Modify: `app/modules/survey123/module.py`
- Modify: `app/main.py`, `cli.py`
- Test: `tests/test_survey123_module.py`

**Interfaces:**
- Consumes: `McpDataModule` (Task 7)
- Produces: `get_survey123_module() -> DataModule` — returns `survey123_module` when `settings.survey123_transport == "inprocess"` (default, unchanged behavior) or an `McpDataModule` pointed at `app.mcp_server.survey123_server` when `"mcp"`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_survey123_module.py`:

```python
def test_get_survey123_module_returns_inprocess_singleton_by_default(monkeypatch):
    from app.modules.survey123.module import get_survey123_module

    monkeypatch.setattr("app.modules.survey123.module.settings.survey123_transport", "inprocess")

    assert get_survey123_module() is survey123_module


def test_get_survey123_module_returns_mcp_adapter_when_configured(monkeypatch):
    from app.core.mcp_module import McpDataModule
    from app.modules.survey123.module import get_survey123_module

    monkeypatch.setattr("app.modules.survey123.module.settings.survey123_transport", "mcp")

    module = get_survey123_module()

    assert isinstance(module, McpDataModule)
    assert module.name == "survey123"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_survey123_module.py -v`
Expected: FAIL — `ImportError: cannot import name 'get_survey123_module'`.

- [ ] **Step 3: Implement**

In `app/config.py`, add the new setting:

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./dev.db"
    llm_provider: Literal["fake", "ollama"] = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "gemma3:4b"
    report_timezone: str = "America/Port_of_Spain"
    app_env: str = "development"
    dedup_salt: str = "dev-salt-change-in-production"
    survey123_transport: Literal["inprocess", "mcp"] = "inprocess"
```

Update `app/modules/survey123/module.py`:

```python
import sys
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.core.contracts import Fact, IngestResult, MetricSpec
from app.core.mcp_module import McpDataModule
from app.core.registry import DataModule
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


survey123_module = Survey123Module()


def get_survey123_module() -> DataModule:
    if settings.survey123_transport == "mcp":
        return McpDataModule(
            name="survey123",
            command=sys.executable,
            args=["-m", "app.mcp_server.survey123_server"],
        )
    return survey123_module
```

Update `app/main.py`'s `create_app()`:

```python
from app.modules.survey123.module import get_survey123_module

...

    register_module(get_survey123_module())
```

Update `cli.py`'s `_ensure_survey123_registered`:

```python
from app.modules.survey123.module import get_survey123_module, survey123_module


def _ensure_survey123_registered() -> None:
    if get_module("survey123") is None:
        register_module(get_survey123_module())
```

(Leave `ingest_survey123` calling `survey123_module.ingest(file_path)` directly, unchanged from Task 5 — ingestion isn't part of the transport switch, since `McpDataModule.ingest` intentionally raises `NotImplementedError`.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/ -v`
Expected: full suite PASS.

- [ ] **Step 5: Commit**

```bash
git add app/config.py app/modules/survey123/module.py app/main.py cli.py tests/test_survey123_module.py
git commit -m "modules: add survey123_transport switch between in-process and MCP-backed data modules"
```

---

## Self-Review

**Spec coverage:**
- DB-backed, versioned templates, additive-only, no exclusion/filtering → Tasks 1, 2, 3, 4, 5.
- `Report` traceable to the exact template version that produced it → Task 2.
- Templates authored as YAML then imported (keeps the existing authoring workflow, adds versioning on top) → Task 5.
- MCP abstraction where calls still run as function calls in-app, modules pluggable internal/external → Tasks 6, 7, 8 (note in particular that `app/core/engine.py`'s `assemble_fact_table` is untouched by Tasks 6-8 — that's the point: the abstraction lives entirely behind `DataModule`, not in the engine).
- No LLM-driven query/tool selection anywhere in this plan — confirmed: `McpDataModule` is called by the deterministic engine via the exact same `data_requirements`-driven loop as `Survey123Module`, never by the LLM.

**Placeholder scan:** no TBD/TODO markers; every step has complete, runnable code; `McpDataModule.ingest`'s `NotImplementedError` is a deliberate, justified design choice (documented inline), not a stub for unfinished work.

**Type consistency:** `Template.version`, `FactTable.template_version`, `GeneratedReport.template_version` all `int`, default `1`, used consistently from Task 1 through Task 5. `template_store` functions' names/signatures (`create_template_version`, `get_latest_template_version`, `get_template_version`, `list_latest_templates`, `import_template_directory`) match exactly between Task 3's definition and Tasks 4/5's call sites. `McpDataModule`'s constructor signature (`name, command, args, env=None`) matches between Task 7's definition and Task 8's call site.

---

Plan complete and saved to `docs/superpowers/plans/2026-07-16-db-templates-and-mcp-modules.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
