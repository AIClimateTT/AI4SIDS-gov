# DMCU Reporting — Step 6: API + Persistence + Docker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist generated reports to the database, expose the full flow over HTTP (`POST /ingest/{module}`, `GET /modules`, `GET /templates`, `POST /reports`, `GET /reports/{id}`), and get the whole stack running via `docker compose` — including a real fix for Ollama reachability from inside the container, since `OLLAMA_BASE_URL`'s default (`http://localhost:11434`, set in Step 5's `Ollama` swap) resolves to the container itself, not the host machine, when running under Docker.

**Architecture:** A new `Report` ORM table (`app/core/report_models.py`) plus persistence helpers (`app/core/report_store.py`) bridge the already-built `GeneratedReport` Pydantic result (Step 5) to storage. Three FastAPI routers — `app/api/ingest.py` (new), `app/api/reports.py` (new), `app/api/meta.py` (extended with `GET /templates`) — are thin wrappers around code that already exists and is already tested (`Survey123Module.ingest`, `generate_report`, the template/module registries). No new business logic; this step is wiring plus one real infrastructure fix.

**Tech Stack:** Adds `python-multipart` (required by FastAPI's `UploadFile` for the ingest endpoint — confirmed not currently installed). No other new dependencies.

## Global Constraints

- Everything in Steps 1–5's plans still applies (SQLAlchemy 2.0 style, PII policy, `apps/backend/` location).
- `PLAN.md` §5.5's API surface is the literal spec for this step: `POST /ingest/survey123`, `GET /modules`, `GET /templates`, `POST /reports {template, params}`, `GET /reports/{id}`. The repo-structure comment in `PLAN.md` §2 additionally mentions a `GET /metrics` endpoint, but §5.5's explicit MVP list does not include it, and `GET /modules` already returns each module's full metric list via its existing `ModuleInfo.metrics` field (Step 1) — a separate `/metrics` endpoint would be redundant. This plan follows §5.5 and does not add one.
- `POST /reports` returns `{id, status, markdown}` per `PLAN.md` §5.5's literal wording ("returns report id + markdown + status"); `GET /reports/{id}` returns the full record "incl. fact table + violations" — a materially richer response, matching the plan's explicit distinction between the two endpoints.
- **Docker/Ollama networking fix, verified conceptually against how Docker Desktop resolves host access:** `docker-compose.yml`'s `backend` service must NOT rely on `Settings.ollama_base_url`'s bare default (`http://localhost:11434`) — inside a container, `localhost` means the container itself, so the backend would try to reach an Ollama server running inside its own (Ollama-less) container and fail. The compose file sets `OLLAMA_BASE_URL: http://host.docker.internal:11434` explicitly for the `backend` service, which is Docker Desktop's documented mechanism for a container to reach services on the host — this is what makes local `docker compose up` testing able to reach the Ollama server actually running on the developer's machine. Production/Dokploy deployment will set this env var to wherever the real Ollama/`gpt-oss:20b` service actually runs; this compose file is for local testing, not a deployment manifest.
- This step's DoD is explicit and more demanding than earlier steps' Docker scaffolding (Step 1 only validated `docker compose config` syntax): `PLAN.md` §6 Step 6 literally requires "container builds and runs via compose" — Task 5 actually builds and runs the containers and exercises the API over real HTTP, not just a syntax check.
- Definition of done for this plan (`PLAN.md` §6 Step 6): full flow via HTTP (ingest → list modules/templates → generate a report → retrieve it by id); container builds and runs via `docker compose`.

---

### Task 1: `Report` model, migration, and persistence

**Files:**
- Create: `apps/backend/app/core/report_models.py`
- Modify: `apps/backend/alembic/env.py`
- Create: `apps/backend/app/core/report_store.py`
- Create: `apps/backend/tests/test_report_store.py`

**Interfaces:**
- Consumes: `app.core.engine.GeneratedReport` (Step 5), `app.db.Base` (Step 1).
- Produces: `app.core.report_models.Report` (SQLAlchemy ORM, `__tablename__ = "reports"`: `id: str` (pk, matches `GeneratedReport.request_id`), `template: str`, `params: dict` (JSON), `fact_table: dict` (JSON, `FactTable.model_dump(mode="json")`), `narrative: str` (Text), `markdown: str` (Text), `status: str`, `violations: list` (JSON), `created_at: datetime`). `app.core.report_store.save_report(report: GeneratedReport, session: Session) -> Report`, `app.core.report_store.get_report(report_id: str, session: Session) -> Report | None`. Task 2's API endpoints call both.

- [ ] **Step 1: Implement `app/core/report_models.py`**

```python
from datetime import datetime

from sqlalchemy import JSON, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    template: Mapped[str] = mapped_column(String, nullable=False)
    params: Mapped[dict] = mapped_column(JSON, nullable=False)
    fact_table: Mapped[dict] = mapped_column(JSON, nullable=False)
    narrative: Mapped[str] = mapped_column(Text, nullable=False)
    markdown: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    violations: Mapped[list] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
```

- [ ] **Step 2: Wire the model into Alembic's autogenerate metadata**

In `apps/backend/alembic/env.py`, add one import immediately after the existing `from app.modules.survey123 import models as survey123_models  # noqa: F401` line:

```python
from app.core import report_models as report_models  # noqa: F401
```

- [ ] **Step 3: Generate and verify the migration**

```bash
cd apps/backend
rm -f dev.db
uv run alembic revision --autogenerate -m "create reports table"
uv run alembic upgrade head
uv run alembic downgrade base
uv run alembic upgrade head
rm -f dev.db
```

Expected: all commands exit 0; the generated migration file creates a `reports` table with all 8 columns from Step 1 and a symmetric `downgrade()`. Do not hand-edit the generated migration's column definitions — if it looks wrong, fix `report_models.py` and regenerate.

- [ ] **Step 4: Write the failing tests**

Create `apps/backend/tests/test_report_store.py`:

```python
from datetime import datetime, timezone

from sqlalchemy.orm import sessionmaker

from app.core.citation_check import CitationViolation
from app.core.contracts import Citation, Fact, FactTable
from app.core.engine import GeneratedReport
from app.core.report_store import get_report, save_report
from app.db import Base, make_engine


def make_session(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


def make_generated_report(status="ok", violations=None) -> GeneratedReport:
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
        params={"date_from": "2024-06-01", "date_to": "2024-06-30"},
        generated_at=datetime(2024, 7, 1, tzinfo=timezone.utc),
        facts=[fact],
        gaps=[],
    )
    return GeneratedReport(
        request_id="req-1",
        template="minister_regional_comparison",
        params={"date_from": "2024-06-01", "date_to": "2024-06-30"},
        fact_table=fact_table,
        narrative="There were 19 incidents recorded [C001].",
        status=status,
        violations=violations or [],
        markdown="# Test Report\n\nThere were 19 incidents recorded [C001].",
    )


def test_save_report_persists_all_fields(tmp_path):
    session = make_session(tmp_path)
    report = make_generated_report()

    saved = save_report(report, session)

    assert saved.id == "req-1"
    assert saved.template == "minister_regional_comparison"
    assert saved.params == {"date_from": "2024-06-01", "date_to": "2024-06-30"}
    assert saved.status == "ok"
    assert saved.narrative == "There were 19 incidents recorded [C001]."
    assert saved.markdown.startswith("# Test Report")
    assert saved.fact_table["request_id"] == "req-1"
    assert saved.violations == []


def test_save_report_persists_violations(tmp_path):
    session = make_session(tmp_path)
    violation = CitationViolation(
        kind="invented_number", detail="test detail", sentence="Bad sentence.", token="999"
    )
    report = make_generated_report(status="needs_review", violations=[violation])

    saved = save_report(report, session)

    assert saved.status == "needs_review"
    assert len(saved.violations) == 1
    assert saved.violations[0]["kind"] == "invented_number"
    assert saved.violations[0]["token"] == "999"


def test_get_report_retrieves_saved_report(tmp_path):
    session = make_session(tmp_path)
    report = make_generated_report()
    save_report(report, session)

    fetched = get_report("req-1", session)

    assert fetched is not None
    assert fetched.id == "req-1"


def test_get_report_returns_none_for_unknown_id(tmp_path):
    session = make_session(tmp_path)

    assert get_report("does-not-exist", session) is None
```

- [ ] **Step 5: Run tests to verify they fail**

```bash
cd apps/backend
uv run pytest tests/test_report_store.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.report_store'`.

- [ ] **Step 6: Implement `app/core/report_store.py`**

```python
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.engine import GeneratedReport
from app.core.report_models import Report


def save_report(report: GeneratedReport, session: Session) -> Report:
    db_report = Report(
        id=report.request_id,
        template=report.template,
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


def get_report(report_id: str, session: Session) -> Report | None:
    return session.get(Report, report_id)
```

- [ ] **Step 7: Run tests to verify they pass**

```bash
cd apps/backend
uv run pytest tests/test_report_store.py -v
```

Expected: `4 passed`.

- [ ] **Step 8: Run the full suite**

```bash
cd apps/backend
uv run pytest -v
```

Expected: `185 passed`.

- [ ] **Step 9: Commit**

```bash
git add apps/backend/app/core/report_models.py apps/backend/alembic/env.py \
        apps/backend/alembic/versions/ apps/backend/app/core/report_store.py \
        apps/backend/tests/test_report_store.py
git commit -m "backend: add Report model, migration, and persistence"
```

---

### Task 2: `POST /reports` and `GET /reports/{id}`

**Files:**
- Create: `apps/backend/app/api/reports.py`
- Modify: `apps/backend/app/main.py`
- Create: `apps/backend/tests/test_api_reports.py`

**Interfaces:**
- Consumes: `generate_report`, `get_default_llm_client` (Step 5), `get_template` (Step 5), `save_report`/`get_report` (Task 1), `get_session` (Step 1).
- Produces: `router` (FastAPI `APIRouter`) with `POST /reports` (request body `{template: str, params: dict}` → `{id, status, markdown}`, `404` for an unknown template, `400` for a `ValueError` from missing required params) and `GET /reports/{report_id}` (→ `{id, template, params, fact_table, narrative, markdown, status, violations}`, `404` if not found). `app.main.create_app()` now includes this router.

- [ ] **Step 1: Write the failing tests**

Create `apps/backend/tests/test_api_reports.py`:

```python
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.registry import reset_registry, reset_template_registry
from app.db import Base, engine as db_engine
from app.main import create_app
from app.modules.survey123.ingest import ingest_csv

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "sample_small.csv"


@pytest.fixture(autouse=True)
def _clean_registry():
    reset_registry()
    reset_template_registry()
    yield
    reset_registry()
    reset_template_registry()


def make_client(monkeypatch) -> TestClient:
    monkeypatch.setattr("app.core.llm.settings.llm_provider", "fake")
    Base.metadata.create_all(db_engine)
    app = create_app()
    return TestClient(app)


def _ingest_fixture():
    from sqlalchemy.orm import sessionmaker

    Session = sessionmaker(bind=db_engine)
    session = Session()
    ingest_csv(FIXTURE_PATH, session, salt="test-salt")
    session.close()


def test_post_reports_returns_id_status_markdown(monkeypatch):
    client = make_client(monkeypatch)
    _ingest_fixture()

    response = client.post(
        "/reports",
        json={
            "template": "minister_regional_comparison",
            "params": {"date_from": "2024-06-01", "date_to": "2024-06-30"},
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"]
    assert body["status"] == "ok"
    assert "# " in body["markdown"]
    assert "## Citation Appendix" in body["markdown"]


def test_post_reports_unknown_template_returns_404(monkeypatch):
    client = make_client(monkeypatch)

    response = client.post("/reports", json={"template": "not_a_real_template", "params": {}})

    assert response.status_code == 404


def test_post_reports_missing_required_param_returns_400(monkeypatch):
    client = make_client(monkeypatch)
    _ingest_fixture()

    response = client.post(
        "/reports", json={"template": "minister_regional_comparison", "params": {"date_from": "2024-06-01"}}
    )

    assert response.status_code == 400


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
    assert "facts" in body["fact_table"]
    assert isinstance(body["violations"], list)


def test_get_reports_unknown_id_returns_404(monkeypatch):
    client = make_client(monkeypatch)

    response = client.get("/reports/does-not-exist")

    assert response.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd apps/backend
uv run pytest tests/test_api_reports.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.api.reports'`.

- [ ] **Step 3: Implement `app/api/reports.py`**

```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.engine import generate_report
from app.core.llm import get_default_llm_client
from app.core.registry import get_template
from app.core.report_store import get_report, save_report
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
    template = get_template(request.template)
    if template is None:
        raise HTTPException(status_code=404, detail=f"unknown template: {request.template}")

    try:
        report = generate_report(template, request.params, session, get_default_llm_client())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    save_report(report, session)

    return GenerateReportResponse(id=report.request_id, status=report.status, markdown=report.markdown)


class ReportDetail(BaseModel):
    id: str
    template: str
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
        params=db_report.params,
        fact_table=db_report.fact_table,
        narrative=db_report.narrative,
        markdown=db_report.markdown,
        status=db_report.status,
        violations=db_report.violations,
    )
```

- [ ] **Step 4: Wire the router into `app/main.py`**

Replace `apps/backend/app/main.py` with:

```python
from pathlib import Path

from fastapi import FastAPI

from app.api.meta import router as meta_router
from app.api.reports import router as reports_router
from app.core.registry import register_module, register_template
from app.modules.survey123.module import survey123_module
from app.templates.loader import load_templates_from_directory

TEMPLATES_DIR = Path(__file__).parent / "templates" / "definitions"


def create_app() -> FastAPI:
    app = FastAPI(title="DMCU Reporting API")
    app.include_router(meta_router)
    app.include_router(reports_router)
    register_module(survey123_module)
    for template in load_templates_from_directory(TEMPLATES_DIR):
        register_template(template)
    return app


app = create_app()
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd apps/backend
uv run pytest tests/test_api_reports.py -v
```

Expected: `5 passed`.

- [ ] **Step 6: Run the full suite**

```bash
cd apps/backend
uv run pytest -v
```

Expected: `190 passed`.

- [ ] **Step 7: Commit**

```bash
git add apps/backend/app/api/reports.py apps/backend/app/main.py apps/backend/tests/test_api_reports.py
git commit -m "backend: add POST /reports and GET /reports/:id endpoints"
```

---

### Task 3: `POST /ingest/{module}`

**Files:**
- Modify: `apps/backend/pyproject.toml` (add `python-multipart`)
- Create: `apps/backend/app/api/ingest.py`
- Modify: `apps/backend/app/main.py`
- Create: `apps/backend/tests/test_api_ingest.py`

**Interfaces:**
- Consumes: `get_module` (Step 1), `Survey123Module.ingest` (Step 2).
- Produces: `router` (FastAPI `APIRouter`) with `POST /ingest/{module_name}` accepting a multipart file upload, writing it to a temp file, calling `module.ingest(path)`, returning the `IngestResult` as JSON; `404` for an unknown module name.

- [ ] **Step 1: Add the `python-multipart` dependency**

FastAPI's `UploadFile` requires it to parse multipart form data — confirmed not currently installed.

```bash
cd apps/backend
uv add python-multipart
```

Expected: exits 0.

- [ ] **Step 2: Write the failing tests**

Create `apps/backend/tests/test_api_ingest.py`:

```python
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.registry import reset_registry, reset_template_registry
from app.db import Base, engine as db_engine
from app.main import create_app

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "sample_small.csv"


@pytest.fixture(autouse=True)
def _clean_registry():
    reset_registry()
    reset_template_registry()
    yield
    reset_registry()
    reset_template_registry()


def make_client() -> TestClient:
    Base.metadata.create_all(db_engine)
    app = create_app()
    return TestClient(app)


def test_post_ingest_survey123_returns_ingest_result():
    client = make_client()

    with open(FIXTURE_PATH, "rb") as f:
        response = client.post("/ingest/survey123", files={"file": ("sample_small.csv", f, "text/csv")})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["rows_read"] == 30
    assert body["rows_inserted"] == 30
    assert body["duplicates_flagged"] == 4
    assert "Name of Person" in body["pii_columns_dropped"]


def test_post_ingest_unknown_module_returns_404():
    client = make_client()

    with open(FIXTURE_PATH, "rb") as f:
        response = client.post("/ingest/not_a_real_module", files={"file": ("sample_small.csv", f, "text/csv")})

    assert response.status_code == 404
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd apps/backend
uv run pytest tests/test_api_ingest.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.api.ingest'`.

- [ ] **Step 4: Implement `app/api/ingest.py`**

```python
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile

from app.core.registry import get_module

router = APIRouter()


@router.post("/ingest/{module_name}")
async def ingest(module_name: str, file: UploadFile) -> dict:
    module = get_module(module_name)
    if module is None:
        raise HTTPException(status_code=404, detail=f"unknown module: {module_name}")

    contents = await file.read()
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
        tmp.write(contents)
        tmp_path = Path(tmp.name)

    try:
        result = module.ingest(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)

    return result.model_dump()
```

- [ ] **Step 5: Wire the router into `app/main.py`**

Add this import to the top of `apps/backend/app/main.py` (alongside the existing ones):

```python
from app.api.ingest import router as ingest_router
```

Add this line to `create_app()`, alongside the existing `app.include_router(...)` calls:

```python
    app.include_router(ingest_router)
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
cd apps/backend
uv run pytest tests/test_api_ingest.py -v
```

Expected: `2 passed`.

- [ ] **Step 7: Run the full suite**

```bash
cd apps/backend
uv run pytest -v
```

Expected: `192 passed`.

- [ ] **Step 8: Commit**

```bash
git add apps/backend/pyproject.toml apps/backend/uv.lock apps/backend/app/api/ingest.py \
        apps/backend/app/main.py apps/backend/tests/test_api_ingest.py
git commit -m "backend: add POST /ingest/:module endpoint"
```

---

### Task 4: `GET /templates`

**Files:**
- Modify: `apps/backend/app/api/meta.py`
- Create: `apps/backend/tests/test_api_templates.py`

**Interfaces:**
- Consumes: `list_templates` (Step 5).
- Produces: `GET /templates` (added to the existing `meta_router`, alongside `GET /modules` — untouched) → `list[TemplateInfo]` (`name`, `title`, `description`, `params: list[{name, required}]`).

- [ ] **Step 1: Write the failing tests**

Create `apps/backend/tests/test_api_templates.py`:

```python
import pytest
from fastapi.testclient import TestClient

from app.core.registry import reset_registry, reset_template_registry
from app.main import create_app


@pytest.fixture(autouse=True)
def _clean_registry():
    reset_registry()
    reset_template_registry()
    yield
    reset_registry()
    reset_template_registry()


def test_get_templates_returns_both_real_templates():
    app = create_app()
    client = TestClient(app)

    response = client.get("/templates")

    assert response.status_code == 200
    body = response.json()
    names = {t["name"] for t in body}
    assert names == {"minister_regional_comparison", "single_region_report"}


def test_get_templates_includes_params_with_required_flags():
    app = create_app()
    client = TestClient(app)

    response = client.get("/templates")

    body = response.json()
    minister = next(t for t in body if t["name"] == "minister_regional_comparison")
    param_names = {p["name"] for p in minister["params"]}
    assert param_names == {"date_from", "date_to"}
    assert all(p["required"] for p in minister["params"])
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd apps/backend
uv run pytest tests/test_api_templates.py -v
```

Expected: FAIL — `AssertionError: 404 != 200` (no `/templates` route registered yet).

- [ ] **Step 3: Update `app/api/meta.py`**

Replace `apps/backend/app/api/meta.py` with:

```python
from fastapi import APIRouter
from pydantic import BaseModel

from app.core.contracts import MetricSpec
from app.core.registry import list_modules, list_templates

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
    title: str
    description: str
    params: list[TemplateParamInfo]


@router.get("/templates", response_model=list[TemplateInfo])
def get_templates() -> list[TemplateInfo]:
    return [
        TemplateInfo(
            name=t.name,
            title=t.title,
            description=t.description,
            params=[TemplateParamInfo(name=p.name, required=p.required) for p in t.params],
        )
        for t in list_templates()
    ]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd apps/backend
uv run pytest tests/test_api_templates.py -v
```

Expected: `2 passed`.

- [ ] **Step 5: Run the full suite**

```bash
cd apps/backend
uv run pytest -v
```

Expected: `194 passed`.

- [ ] **Step 6: Commit**

```bash
git add apps/backend/app/api/meta.py apps/backend/tests/test_api_templates.py
git commit -m "backend: add GET /templates endpoint"
```

---

### Task 5: Docker fixes and full-stack verification

**Files:**
- Modify: `apps/backend/docker-compose.yml`

**Interfaces:**
- Produces: a `docker-compose.yml` whose `backend` service can actually reach the developer's local Ollama server, plus a live, actually-executed verification that the full stack builds, runs, and serves the complete flow over real HTTP.

- [ ] **Step 1: Update `docker-compose.yml`**

Replace `apps/backend/docker-compose.yml` with:

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
      # host.docker.internal is Docker Desktop's mechanism for a container to
      # reach services running on the host machine (e.g. a local Ollama
      # server). This is for local `docker compose up` testing only — a real
      # deployment (Dokploy) must set OLLAMA_BASE_URL to wherever the actual
      # Ollama/gpt-oss:20b service runs.
      OLLAMA_BASE_URL: http://host.docker.internal:11434
      OLLAMA_MODEL: gemma3:4b
    ports:
      - "8000:8000"
    extra_hosts:
      - "host.docker.internal:host-gateway"

volumes:
  dmcu_postgres_data:
```

**Note on `extra_hosts`:** `host.docker.internal` resolves automatically on Docker Desktop (macOS/Windows) but needs the explicit `host-gateway` mapping to also work on Linux Docker Engine — including it unconditionally makes this compose file portable to both without needing a platform check.

- [ ] **Step 2: Validate the compose file syntax**

```bash
cd apps/backend
docker compose config --quiet
```

Expected: exits 0, no output.

- [ ] **Step 3: Build and run the full stack**

```bash
cd apps/backend
docker compose up --build -d
```

Expected: exits 0; both `db` and `backend` containers report as running. If the build fails, read the actual error — do not silently work around it; report back with the specific failure if you cannot resolve it from context already established in this plan.

- [ ] **Step 4: Wait for the backend to be ready, then run the full flow over real HTTP**

```bash
cd apps/backend
for i in $(seq 1 30); do
  curl -sf http://localhost:8000/modules > /dev/null && break
  sleep 1
done

docker compose exec backend uv run alembic upgrade head

curl -s -X POST http://localhost:8000/ingest/survey123 \
  -F "file=@fixtures/sample_small.csv;type=text/csv" | tee /tmp/ingest_response.json
echo
curl -s http://localhost:8000/modules | tee /tmp/modules_response.json
echo
curl -s http://localhost:8000/templates | tee /tmp/templates_response.json
echo

REPORT_ID=$(curl -s -X POST http://localhost:8000/reports \
  -H "Content-Type: application/json" \
  -d '{"template": "minister_regional_comparison", "params": {"date_from": "2024-06-01", "date_to": "2024-06-30"}}' \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])")
echo "report id: $REPORT_ID"

curl -s "http://localhost:8000/reports/$REPORT_ID" | python3 -m json.tool | head -40
```

Expected: the ingest call returns `rows_read: 30`; `/modules` shows `survey123` with 9 metrics; `/templates` shows both templates; the `POST /reports` call returns a report id; the final `GET /reports/{id}` call returns the full stored record including `fact_table` and `violations`. This exercises the whole system exactly as `PLAN.md` §6 Step 6's DoD requires — a real HTTP round trip through a real containerized Postgres database, not sqlite, not `TestClient`.

**Note on the LLM provider inside the container:** `OLLAMA_MODEL` is set to `gemma3:4b` in the compose file to match what's actually available on this development machine for this verification — the report's `status` may legitimately come back `needs_review` (as it did in the equivalent CLI verification for the Ollama plan), which is valid evidence the safety system works end-to-end inside the container too, not a failure to chase.

- [ ] **Step 5: Tear down**

```bash
cd apps/backend
docker compose down -v
rm -f /tmp/ingest_response.json /tmp/modules_response.json /tmp/templates_response.json
```

Expected: exits 0; containers and the named volume are removed, so no state leaks into a later verification run.

- [ ] **Step 6: Commit**

```bash
git add apps/backend/docker-compose.yml
git commit -m "backend: fix Ollama container networking, verify full stack via docker compose"
```

---

## Definition of Done (matches `PLAN.md` §6 Step 6)

- [ ] `cd apps/backend && uv run pytest -v` — all 194 tests pass, 0 failures.
- [ ] Full flow via HTTP: ingest → `GET /modules` → `GET /templates` → `POST /reports` → `GET /reports/{id}`, all verified against a real running container stack (Task 5 Step 4), not just `TestClient`.
- [ ] Container builds and runs via `docker compose up --build` (Task 5 Step 3).
