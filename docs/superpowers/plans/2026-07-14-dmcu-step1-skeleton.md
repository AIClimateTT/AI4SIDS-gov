# DMCU Reporting — Step 1: Skeleton + Contracts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the skeleton of the DMCU reporting backend inside `apps/backend`: env-driven config, DB engine/session, the core Pydantic contracts (`Citation`, `Fact`, `FactTable`, `MetricSpec`, `IngestResult`), the `DataModule` registry, a booting FastAPI app exposing `GET /modules`, and the Docker/Alembic scaffolding — with zero data modules registered yet.

**Architecture:** Follows `PLAN.md` §2–3 exactly, relocated under `apps/backend/app/` instead of a fresh repo root (this repo is already an `apps/` monorepo — `apps/backend` is the existing empty scaffold chosen for this build; `apps/AI4SIDS-GOV` is a separate pre-existing prototype and is out of scope). The engine will only ever talk to `app/core/registry.py`; no module-specific code exists yet, which is what proves the registry abstraction is real.

**Tech Stack:** Python >=3.13 (uv-managed), FastAPI, SQLAlchemy 2.0-style, Pydantic v2, pydantic-settings, Alembic, PostgreSQL (docker-compose) / SQLite (local dev + tests), pytest, httpx (TestClient transport).

## Global Constraints

- Python 3.13+ (`apps/backend/pyproject.toml` already pins `requires-python = ">=3.13"` — keep it).
- Stack per `PLAN.md` §1: FastAPI, SQLAlchemy 2.x, Pydantic v2, Postgres (SQLite acceptable for local dev), Alembic for migrations.
- Pydantic v2 everywhere at boundaries; SQLAlchemy 2.0 style — no legacy `Query` API (`PLAN.md` §7).
- LLM calls via the Anthropic API only, model configurable via env, behind a swappable client interface; no LLM call anywhere outside `app/core/llm.py` (`PLAN.md` §1, §7). No LLM code is written in this plan — this constraint governs where the `anthropic_model` config field may later be consumed.
- Timezone: store UTC, report in `America/Port_of_Spain` (`PLAN.md` §7).
- Deployment target is Dokploy: Dockerfile + docker-compose are required deliverables, not optional (`PLAN.md` §1).
- Every metric is a pure function of `(params, session)` — no hidden state (`PLAN.md` §7). The `DataModule.run_metric` signature defined in this plan must match that shape exactly since later steps depend on it.
- Backend lives at `apps/backend/`, with the `app/` package structure from `PLAN.md` §2 nested under it (i.e. `apps/backend/app/core/contracts.py`, not `app/core/contracts.py` at repo root).
- Definition of done for this plan (`PLAN.md` §6 Step 1): `pytest` runs green, the FastAPI app boots, `GET /modules` returns `[]`.

---

### Task 1: Backend dependencies, `.gitignore`, and env-driven config

**Files:**
- Modify: `apps/backend/pyproject.toml`
- Delete: `apps/backend/main.py` (stale `uv init` stub — superseded by `app/main.py` in Task 5; nothing references it)
- Create: `apps/backend/.gitignore`
- Create: `apps/backend/app/__init__.py`
- Create: `apps/backend/app/config.py`
- Create: `apps/backend/tests/test_config.py`

**Interfaces:**
- Produces: `app.config.Settings` (pydantic-settings `BaseSettings` subclass) with fields `database_url: str`, `anthropic_api_key: str | None`, `anthropic_model: str`, `report_timezone: str`, `app_env: str`. Produces `app.config.get_settings() -> Settings` (cached) and module-level `app.config.settings` (a `Settings` instance). Later tasks (`db.py`, `alembic/env.py`) import `settings.database_url`.

- [ ] **Step 1: Add runtime and dev dependencies with uv**

Run from `apps/backend/`:

```bash
cd apps/backend
uv add fastapi "sqlalchemy>=2.0" "pydantic>=2.0" pydantic-settings "uvicorn[standard]" alembic "psycopg[binary]" typer
uv add --dev pytest httpx
```

Expected: both commands exit 0; `pyproject.toml` now lists these under `[project.dependencies]` / `[dependency-groups.dev]` (uv's default dev-group key — accept whatever section name `uv add --dev` creates); a `uv.lock` file is created in `apps/backend/`.

- [ ] **Step 2: Remove the stale `uv init` stub**

```bash
rm apps/backend/main.py
```

- [ ] **Step 3: Add `apps/backend/.gitignore`**

```
__pycache__/
*.pyc
.venv/
dev.db
.env
```

- [ ] **Step 4: Add pytest config to `pyproject.toml`**

Append to `apps/backend/pyproject.toml`:

```toml
[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

- [ ] **Step 5: Write the failing test for config defaults and env overrides**

Create `apps/backend/tests/test_config.py`:

```python
from app.config import Settings


def test_settings_defaults(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
    monkeypatch.delenv("REPORT_TIMEZONE", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)

    settings = Settings(_env_file=None)

    assert settings.database_url == "sqlite:///./dev.db"
    assert settings.anthropic_api_key is None
    assert settings.anthropic_model == "claude-sonnet-5"
    assert settings.report_timezone == "America/Port_of_Spain"
    assert settings.app_env == "development"


def test_settings_env_override(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@localhost:5432/dmcu")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-123")
    monkeypatch.setenv("APP_ENV", "production")

    settings = Settings(_env_file=None)

    assert settings.database_url == "postgresql+psycopg://user:pass@localhost:5432/dmcu"
    assert settings.anthropic_api_key == "sk-test-123"
    assert settings.app_env == "production"
```

- [ ] **Step 6: Run the test to verify it fails**

```bash
cd apps/backend
uv run pytest tests/test_config.py -v
```

Expected: FAIL / ERROR — `ModuleNotFoundError: No module named 'app'` (or `app.config` does not exist).

- [ ] **Step 7: Implement `app/config.py`**

Create `apps/backend/app/__init__.py` (empty file).

Create `apps/backend/app/config.py`:

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


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
```

- [ ] **Step 8: Run the test to verify it passes**

```bash
cd apps/backend
uv run pytest tests/test_config.py -v
```

Expected: `2 passed`.

- [ ] **Step 9: Commit**

```bash
git add apps/backend/pyproject.toml apps/backend/uv.lock apps/backend/.gitignore \
        apps/backend/app/__init__.py apps/backend/app/config.py apps/backend/tests/test_config.py
git rm apps/backend/main.py
git commit -m "backend: scaffold deps and env-driven config"
```

---

### Task 2: DB engine and session

**Files:**
- Create: `apps/backend/app/db.py`
- Create: `apps/backend/tests/test_db.py`

**Interfaces:**
- Consumes: `app.config.settings.database_url` (Task 1).
- Produces: `app.db.Base` (SQLAlchemy 2.0 `DeclarativeBase` subclass — all future ORM models inherit from this), `app.db.make_engine(url: str) -> Engine`, module-level `app.db.engine` (built from `settings.database_url`), `app.db.SessionLocal` (sessionmaker bound to `engine`), `app.db.get_session()` (generator yielding a `Session`, for use as a FastAPI dependency). Later tasks (Alembic env, and every future data module) import `Base` and `get_session`.

- [ ] **Step 1: Write the failing test**

Create `apps/backend/tests/test_db.py`:

```python
from sqlalchemy import text

from app.db import make_engine


def test_make_engine_connects_and_executes():
    engine = make_engine("sqlite:///:memory:")

    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        assert result.scalar() == 1


def test_make_engine_returns_engine_for_postgres_url_without_connecting():
    engine = make_engine("postgresql+psycopg://user:pass@localhost:5432/dmcu")

    assert engine.url.drivername == "postgresql+psycopg"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd apps/backend
uv run pytest tests/test_db.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.db'`.

- [ ] **Step 3: Implement `app/db.py`**

```python
from collections.abc import Generator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


def make_engine(url: str) -> Engine:
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args)


engine = make_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd apps/backend
uv run pytest tests/test_db.py -v
```

Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add apps/backend/app/db.py apps/backend/tests/test_db.py
git commit -m "backend: add SQLAlchemy engine/session module"
```

---

### Task 3: Core contracts (`Citation`, `Fact`, `FactTable`, `MetricSpec`, `IngestResult`)

**Files:**
- Create: `apps/backend/app/core/__init__.py`
- Create: `apps/backend/app/core/contracts.py`
- Create: `apps/backend/tests/test_contracts.py`

**Interfaces:**
- Produces (all Pydantic v2 `BaseModel`s, importable from `app.core.contracts`):
  - `Citation(cid: str, module: str, description: str, query_ref: str, record_ids: list[str] | None, as_of: datetime)`
  - `Fact(metric: str, value: int | float | str, unit: str | None, scope: dict[str, str], breakdown: dict[str, int | float] | None, verification: Literal["validated", "pending", "mixed", "n/a"], citation: Citation)`
  - `FactTable(request_id: str, template: str, params: dict, generated_at: datetime, facts: list[Fact], gaps: list[str])`
  - `MetricSpec(name: str, description: str, params_schema: dict, module: str)`
  - `IngestResult(rows_read: int, rows_inserted: int, rows_updated: int, duplicates_flagged: int, unmapped_values: dict[str, list[str]], pii_columns_dropped: list[str])`
- These five models are consumed by Task 4 (`registry.py`'s `DataModule` Protocol uses `MetricSpec`, `Fact`, `IngestResult`) and Task 5 (`api/meta.py` serializes `MetricSpec` in responses).

- [ ] **Step 1: Write the failing tests**

Create `apps/backend/tests/test_contracts.py`:

```python
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.core.contracts import Citation, Fact, FactTable, IngestResult, MetricSpec


def make_citation(**overrides) -> Citation:
    defaults = dict(
        cid="S123-001",
        module="survey123",
        description="Survey123 incidents, Sangre Grande, 2026-01-01 to 2026-01-31",
        query_ref="incidents_by_corporation(corporation=sangre_grande, date_from=2026-01-01, date_to=2026-01-31)",
        record_ids=["GUID-1", "GUID-2"],
        as_of=datetime(2026, 2, 1, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return Citation(**defaults)


def test_citation_round_trips_through_json():
    citation = make_citation()

    restored = Citation.model_validate_json(citation.model_dump_json())

    assert restored == citation


def test_citation_allows_null_record_ids_above_cap():
    citation = make_citation(record_ids=None)

    assert citation.record_ids is None


def test_fact_accepts_validated_verification_and_nested_citation():
    fact = Fact(
        metric="homes_affected_count",
        value=42,
        unit="incidents",
        scope={"corporation": "sangre_grande", "window": "2026-01-01..2026-01-31"},
        breakdown={"validated": 40, "pending": 2},
        verification="validated",
        citation=make_citation(),
    )

    assert fact.citation.cid == "S123-001"
    assert fact.breakdown == {"validated": 40, "pending": 2}


def test_fact_rejects_invalid_verification_literal():
    with pytest.raises(ValidationError):
        Fact(
            metric="homes_affected_count",
            value=42,
            unit=None,
            scope={},
            breakdown=None,
            verification="confirmed",
            citation=make_citation(),
        )


def test_fact_table_collects_facts_and_gaps():
    table = FactTable(
        request_id="req-001",
        template="minister_regional_comparison",
        params={"date_from": "2026-01-01", "date_to": "2026-01-31"},
        generated_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        facts=[
            Fact(
                metric="homes_affected_count",
                value=42,
                unit="incidents",
                scope={"corporation": "sangre_grande"},
                breakdown=None,
                verification="validated",
                citation=make_citation(),
            )
        ],
        gaps=["No data for Tobago corporations in this window"],
    )

    assert len(table.facts) == 1
    assert table.gaps == ["No data for Tobago corporations in this window"]


def test_metric_spec_carries_params_schema():
    spec = MetricSpec(
        name="incidents_by_corporation",
        description="Counts per corporation, including the (no corporation recorded) bucket",
        params_schema={
            "type": "object",
            "properties": {
                "date_from": {"type": "string", "format": "date"},
                "date_to": {"type": "string", "format": "date"},
            },
        },
        module="survey123",
    )

    assert spec.module == "survey123"
    assert spec.params_schema["type"] == "object"


def test_ingest_result_reports_unmapped_values_and_dropped_pii_columns():
    result = IngestResult(
        rows_read=14942,
        rows_inserted=14942,
        rows_updated=0,
        duplicates_flagged=17,
        unmapped_values={"Municipal Boundary": ["Unknown_Corp_Typo"]},
        pii_columns_dropped=[
            "Name of Person",
            "Contact Information",
            "Identification Card Number",
            "Name of Second Person",
            "Second Contact Information",
            "Second Identification Card Number",
            "Please list the names of the occupants and their relation",
        ],
    )

    assert result.rows_read == 14942
    assert "Identification Card Number" in result.pii_columns_dropped
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd apps/backend
uv run pytest tests/test_contracts.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.core'`.

- [ ] **Step 3: Implement `app/core/contracts.py`**

Create `apps/backend/app/core/__init__.py` (empty file).

Create `apps/backend/app/core/contracts.py`:

```python
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class Citation(BaseModel):
    cid: str
    module: str
    description: str
    query_ref: str
    record_ids: list[str] | None
    as_of: datetime


class Fact(BaseModel):
    metric: str
    value: int | float | str
    unit: str | None
    scope: dict[str, str]
    breakdown: dict[str, int | float] | None
    verification: Literal["validated", "pending", "mixed", "n/a"]
    citation: Citation


class FactTable(BaseModel):
    request_id: str
    template: str
    params: dict
    generated_at: datetime
    facts: list[Fact]
    gaps: list[str]


class MetricSpec(BaseModel):
    name: str
    description: str
    params_schema: dict
    module: str


class IngestResult(BaseModel):
    rows_read: int
    rows_inserted: int
    rows_updated: int
    duplicates_flagged: int
    unmapped_values: dict[str, list[str]]
    pii_columns_dropped: list[str]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd apps/backend
uv run pytest tests/test_contracts.py -v
```

Expected: `7 passed`.

- [ ] **Step 5: Commit**

```bash
git add apps/backend/app/core/__init__.py apps/backend/app/core/contracts.py apps/backend/tests/test_contracts.py
git commit -m "backend: add core Fact/FactTable/Citation/MetricSpec/IngestResult contracts"
```

---

### Task 4: `DataModule` registry

**Files:**
- Create: `apps/backend/app/core/registry.py`
- Create: `apps/backend/tests/test_registry.py`

**Interfaces:**
- Consumes: `app.core.contracts.MetricSpec`, `app.core.contracts.Fact`, `app.core.contracts.IngestResult` (Task 3).
- Produces: `app.core.registry.DataModule` (a `typing.Protocol` with `name: str`, `def ingest(self, file_path: Path) -> IngestResult`, `def list_metrics(self) -> list[MetricSpec]`, `def run_metric(self, name: str, params: dict, session: Session) -> list[Fact]`), `app.core.registry.register_module(module: DataModule) -> None`, `app.core.registry.get_module(name: str) -> DataModule | None`, `app.core.registry.list_modules() -> list[DataModule]`, `app.core.registry.reset_registry() -> None` (test-only helper that clears registered modules). Task 5's `api/meta.py` calls `list_modules()` and, per module, `module.list_metrics()`.

- [ ] **Step 1: Write the failing tests**

Create `apps/backend/tests/test_registry.py`:

```python
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.core.contracts import Fact, IngestResult, MetricSpec
from app.core.registry import get_module, list_modules, register_module, reset_registry


class FakeModule:
    name = "fake_module"

    def ingest(self, file_path: Path) -> IngestResult:
        return IngestResult(
            rows_read=0,
            rows_inserted=0,
            rows_updated=0,
            duplicates_flagged=0,
            unmapped_values={},
            pii_columns_dropped=[],
        )

    def list_metrics(self) -> list[MetricSpec]:
        return []

    def run_metric(self, name: str, params: dict, session: Session) -> list[Fact]:
        return []


@pytest.fixture(autouse=True)
def _clean_registry():
    reset_registry()
    yield
    reset_registry()


def test_register_and_get_module():
    module = FakeModule()

    register_module(module)

    assert get_module("fake_module") is module


def test_get_unregistered_module_returns_none():
    assert get_module("does_not_exist") is None


def test_list_modules_reflects_registrations():
    assert list_modules() == []

    register_module(FakeModule())

    assert [m.name for m in list_modules()] == ["fake_module"]


def test_register_duplicate_name_raises():
    register_module(FakeModule())

    with pytest.raises(ValueError, match="fake_module"):
        register_module(FakeModule())
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd apps/backend
uv run pytest tests/test_registry.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.registry'`.

- [ ] **Step 3: Implement `app/core/registry.py`**

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

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd apps/backend
uv run pytest tests/test_registry.py -v
```

Expected: `4 passed`.

- [ ] **Step 5: Commit**

```bash
git add apps/backend/app/core/registry.py apps/backend/tests/test_registry.py
git commit -m "backend: add DataModule registry"
```

---

### Task 5: FastAPI app factory and `GET /modules`

**Files:**
- Create: `apps/backend/app/api/__init__.py`
- Create: `apps/backend/app/api/meta.py`
- Create: `apps/backend/app/main.py`
- Create: `apps/backend/tests/test_meta_api.py`

**Interfaces:**
- Consumes: `app.core.registry.list_modules`, `app.core.registry.register_module`, `app.core.registry.reset_registry` (Task 4); `app.core.contracts.MetricSpec` (Task 3).
- Produces: `app.api.meta.router` (a `fastapi.APIRouter` with `GET /modules`), `app.main.create_app() -> FastAPI` and module-level `app.main.app` (the booted instance, used by `uvicorn app.main:app` in Task 6's Dockerfile).

- [ ] **Step 1: Write the failing test**

Create `apps/backend/tests/test_meta_api.py`:

```python
import pytest
from fastapi.testclient import TestClient

from app.core.contracts import IngestResult, MetricSpec
from app.core.registry import register_module, reset_registry
from app.main import app


@pytest.fixture(autouse=True)
def _clean_registry():
    reset_registry()
    yield
    reset_registry()


class FakeModule:
    name = "fake_module"

    def ingest(self, file_path):
        return IngestResult(
            rows_read=0,
            rows_inserted=0,
            rows_updated=0,
            duplicates_flagged=0,
            unmapped_values={},
            pii_columns_dropped=[],
        )

    def list_metrics(self):
        return [
            MetricSpec(
                name="incident_count",
                description="Total incidents, breakdown by incident_type",
                params_schema={"type": "object", "properties": {}},
                module="fake_module",
            )
        ]

    def run_metric(self, name, params, session):
        return []


def test_list_modules_empty():
    client = TestClient(app)

    response = client.get("/modules")

    assert response.status_code == 200
    assert response.json() == []


def test_list_modules_returns_registered_module_with_metrics():
    register_module(FakeModule())
    client = TestClient(app)

    response = client.get("/modules")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["name"] == "fake_module"
    assert body[0]["metrics"][0]["name"] == "incident_count"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd apps/backend
uv run pytest tests/test_meta_api.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.main'`.

- [ ] **Step 3: Implement `app/api/meta.py` and `app/main.py`**

Create `apps/backend/app/api/__init__.py` (empty file).

Create `apps/backend/app/api/meta.py`:

```python
from fastapi import APIRouter
from pydantic import BaseModel

from app.core.contracts import MetricSpec
from app.core.registry import list_modules

router = APIRouter()


class ModuleInfo(BaseModel):
    name: str
    metrics: list[MetricSpec]


@router.get("/modules", response_model=list[ModuleInfo])
def get_modules() -> list[ModuleInfo]:
    return [ModuleInfo(name=module.name, metrics=module.list_metrics()) for module in list_modules()]
```

Create `apps/backend/app/main.py`:

```python
from fastapi import FastAPI

from app.api.meta import router as meta_router


def create_app() -> FastAPI:
    app = FastAPI(title="DMCU Reporting API")
    app.include_router(meta_router)
    return app


app = create_app()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd apps/backend
uv run pytest tests/test_meta_api.py -v
```

Expected: `2 passed`.

- [ ] **Step 5: Run the full test suite**

```bash
cd apps/backend
uv run pytest -v
```

Expected: all tests across `test_config.py`, `test_db.py`, `test_contracts.py`, `test_registry.py`, `test_meta_api.py` pass (17 total).

- [ ] **Step 6: Commit**

```bash
git add apps/backend/app/api/__init__.py apps/backend/app/api/meta.py apps/backend/app/main.py apps/backend/tests/test_meta_api.py
git commit -m "backend: boot FastAPI app with GET /modules"
```

---

### Task 6: Alembic scaffold, Dockerfile, docker-compose

**Files:**
- Create: `apps/backend/alembic.ini`
- Create: `apps/backend/alembic/env.py`
- Create: `apps/backend/alembic/script.py.mako`
- Create: `apps/backend/alembic/versions/.gitkeep`
- Create: `apps/backend/Dockerfile`
- Create: `apps/backend/.dockerignore`
- Create: `apps/backend/docker-compose.yml`

**Interfaces:**
- Consumes: `app.config.settings.database_url` (Task 1), `app.db.Base` (Task 2), `app.main.app` (Task 5, referenced by the Dockerfile's `uvicorn app.main:app` command).
- Produces: nothing importable — this task's deliverable is deployability, verified by `alembic current` running without error and `docker compose config` validating.

- [ ] **Step 1: Generate the Alembic scaffold**

```bash
cd apps/backend
uv run alembic init alembic
```

Expected: creates `alembic.ini` and `alembic/` (`env.py`, `script.py.mako`, `versions/`).

- [ ] **Step 2: Wire `alembic/env.py` to app config and metadata**

Replace the generated `apps/backend/alembic/env.py` with:

```python
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import settings
from app.db import Base

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

Leave `apps/backend/alembic/script.py.mako` as generated by `alembic init` — do not edit it.

Ensure `apps/backend/alembic/versions/` exists and is tracked by git even though it's empty:

```bash
touch apps/backend/alembic/versions/.gitkeep
```

- [ ] **Step 3: Verify Alembic wiring**

```bash
cd apps/backend
rm -f dev.db
uv run alembic current
```

Expected: exits 0, prints nothing (or a blank current-revision line) — no traceback. This confirms `env.py` imports `app.config`/`app.db` cleanly and can open the configured database.

```bash
rm -f apps/backend/dev.db
```

(Clean up the sqlite file created by the check above — it's git-ignored per Task 1 but no need to leave clutter.)

- [ ] **Step 4: Write the Dockerfile**

Create `apps/backend/Dockerfile`:

```dockerfile
FROM python:3.13-slim

RUN pip install --no-cache-dir uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 5: Write `.dockerignore`**

Create `apps/backend/.dockerignore`:

```
__pycache__/
*.pyc
.venv/
dev.db
tests/
.git
```

- [ ] **Step 6: Write `docker-compose.yml`**

Create `apps/backend/docker-compose.yml`:

```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: dmcu
      POSTGRES_PASSWORD: dmcu
      POSTGRES_DB: dmcu
    volumes:
      - dmcu_postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  backend:
    build: .
    depends_on:
      - db
    environment:
      DATABASE_URL: postgresql+psycopg://dmcu:dmcu@db:5432/dmcu
    ports:
      - "8000:8000"

volumes:
  dmcu_postgres_data:
```

- [ ] **Step 7: Validate the compose file**

```bash
cd apps/backend
docker compose config --quiet
```

Expected: exits 0 with no output (syntax and schema are valid). This validates the file only — it does not start containers; full container build/run is verified in Step 6 of `PLAN.md`'s build order, not this plan.

- [ ] **Step 8: Confirm the full test suite is still green**

```bash
cd apps/backend
uv run pytest -v
```

Expected: all 17 tests pass (Alembic/Docker files don't touch app code, but this confirms nothing in the working tree is broken before committing).

- [ ] **Step 9: Commit**

```bash
git add apps/backend/alembic.ini apps/backend/alembic/ apps/backend/Dockerfile \
        apps/backend/.dockerignore apps/backend/docker-compose.yml
git commit -m "backend: add Alembic scaffold, Dockerfile, docker-compose"
```

---

## Definition of Done (matches `PLAN.md` §6 Step 1)

- [ ] `cd apps/backend && uv run pytest -v` — all tests pass, 0 failures.
- [ ] `uv run python -c "from app.main import app; print(app.title)"` — app boots without error.
- [ ] `GET /modules` returns `[]` (proven by `test_list_modules_empty` in Task 5, with no data module registered anywhere in this plan).
- [ ] `docker compose config --quiet` validates without error.
- [ ] `uv run alembic current` runs cleanly against the configured database.
