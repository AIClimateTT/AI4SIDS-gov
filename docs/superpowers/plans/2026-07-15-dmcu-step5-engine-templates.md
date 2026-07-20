# DMCU Reporting — Step 5: Engine + Templates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire everything built in Steps 1–4 into a working end-to-end report generator: YAML report templates, an LLM client behind a swappable interface (with a fully-functional fake for offline testing), the engine that assembles a `FactTable` from a template's declared metrics, calls the LLM, runs Step 4's citation checker with one retry, and a deterministic markdown renderer — reachable via `cli.py generate minister_regional_comparison --date-from ... --date-to ...`.

**Architecture:** Seven pieces, built bottom-up so each task's dependencies already exist: template contracts + YAML loader, template registry, LLM client, engine fact-table assembly, renderer, engine narration/retry orchestration, then the two real YAML templates + CLI wiring that ties it all together. This plan has more open design surface than Steps 1–4 — `PLAN.md` §5 specifies the template YAML shape and the engine's *flow* precisely, but leaves several concrete mechanics unstated (how citation ids get assigned across a whole fact table, what a "fake LLM client" actually does when not given a canned response, how the deterministic per-corporation table gets extracted from facts). Every one of those decisions below was implemented as a draft and run end-to-end against the real Step 2/3/4 code during planning — see the verification note in Global Constraints.

**Tech Stack:** Same as Steps 1–4 (Python 3.13, SQLAlchemy 2.0-style, Pydantic v2), plus `PyYAML` (template parsing — confirmed already present transitively but never declared; this plan declares it explicitly) and `anthropic` (the official SDK, confirmed against the installed version's real API shape during planning — see Task 3).

## Global Constraints

- Everything in Steps 1–4's plans still applies (SQLAlchemy 2.0 style, `apps/backend/` location, PII policy, "no LLM call anywhere except `core/llm.py`; everything else must be testable without a network" — `PLAN.md` §7).
- **This plan's entire engine/renderer/template flow was drafted and run end-to-end during planning** against the real Step 2 fixture, Step 3 metrics, and Step 4 citation checker (not just imagined) — six scenarios were verified: full pipeline producing a passing report, a missing-required-param error, a corrupted-narrative-twice `needs_review` result, a corrupted-then-recovered-on-retry `ok` result, an unknown-data-module error, and sequential citation-id renumbering across all facts in a table. The task-by-task code below reproduces exactly what was verified, not a redesign.
- **Citation id renumbering:** `PLAN.md` §5.4 says the engine must "assign citation ids sequentially" when assembling a `FactTable`. Each metric (Step 3) already emits a locally-unique cid like `"survey123-incident_count-0"`, scoped to that one metric call — the engine **overwrites** every fact's `Citation.cid` with a new table-wide sequential id, `f"C{i:03d}"` (`"C001"`, `"C002"`, ...), in the order `data_requirements` were declared and facts were returned. `PLAN.md`'s own citation-marker example (`[S123-003]`) is illustrative, not a format spec — this plan's system prompts reference the real `C001`-style format instead.
- **Deterministic table rendering:** `PLAN.md` §5.2 requires a "per-corporation comparison table (rendered from facts by the renderer, NOT written by the LLM)." Rather than have the renderer special-case "which one fact is THE table" per template (which would require extending the template schema with template-specific rendering hints `PLAN.md` never specifies), the renderer renders **every fact that has a non-null `breakdown`** as its own small markdown table. This is template-agnostic, requires no schema extension, and produces the comparison table `PLAN.md` describes for `minister_regional_comparison` (via `incidents_by_corporation`'s breakdown) and equally useful tables for `single_region_report`'s breakdown-bearing metrics.
- **Narrative structure:** the LLM is asked (via the template's `narration.system_prompt`, which lists `output_sections`) to write ONE markdown blob containing all its sections as `## Header`-style content. The engine does not parse this into separate named sections — `check_citations` (Step 4) validates the whole blob as one unit, and the renderer inserts it as-is between the report title and the deterministic data tables. This matches "the whole briefing fits on one page" (`PLAN.md` §5.1) and avoids a structured-section-parsing layer `PLAN.md` never specifies.
- **Retry policy** (`PLAN.md` §5.4 point 5): call the LLM once; if `check_citations` fails, call it again with the violations appended to the same fact-table content as feedback; if it fails a second time, the report's `status` is `"needs_review"` with the violations attached — never silently deliver a failing report, and never retry more than once.
- **Report persistence is explicitly out of scope for this plan.** `PLAN.md`'s own Build Order (§6) puts "Report storage" in Step 6 ("API + persistence + Docker"), not Step 5. `generate_report` returns an in-memory `GeneratedReport` (not written to any table); the CLI prints it. Do not add a `Report` SQLAlchemy model in this plan.
- **LLM client selection:** with no `ANTHROPIC_API_KEY` configured (confirmed absent from this environment during planning — no `.env`, no env var, `anthropic` SDK not yet installed), the CLI's `generate` command must still produce a complete, passing report per `PLAN.md`'s Step 5 DoD. `FakeLLMClient` therefore has two modes: given an explicit `responses` list (test-controlled, for exercising specific pass/fail/retry scenarios), or — its default — an **auto-narrative mode** that deterministically synthesizes a citation-correct narrative directly from the `FactTable` JSON it's given, with no canned text required. `get_default_llm_client()` returns `AnthropicLLMClient` when `settings.anthropic_api_key` is set, else `FakeLLMClient()` in auto-narrative mode. This is what makes the CLI's `generate` command work today without a key, while leaving the real client fully implemented and ready to use the moment a key is configured.
- **`AnthropicLLMClient`'s constructor and `messages.create` call shape were verified during planning against the installed `anthropic` SDK (v0.116.0)** via `inspect.signature` — `model`, `max_tokens`, `system`, and `messages` are all real keyword arguments, and a response's text lives at `response.content[0].text` (a `TextBlock` with a `.text` field). Because no API key exists in this environment, `AnthropicLLMClient` is tested via constructor-injected mock, never a real network call — consistent with the "testable without a network" guardrail.
- Money and timezone conventions from earlier steps still apply (TTD currency, UTC storage) — nothing in this plan changes them; `GeneratedReport.fact_table.generated_at` uses `datetime.now(timezone.utc)`, matching Step 2/3's convention.
- Definition of done for this plan (`PLAN.md` §6 Step 5, adapted — no Docker/API/persistence, those are Step 6): `cli.py generate minister_regional_comparison --date-from ... --date-to ...` against the ingested sample fixture produces a complete markdown report with a citation appendix; a deliberately-corrupted fake LLM response is caught and flagged `needs_review`.

---

### Task 1: Template contracts + YAML loader

**Files:**
- Modify: `apps/backend/app/core/contracts.py` (append)
- Modify: `apps/backend/pyproject.toml` (add `pyyaml`)
- Create: `apps/backend/app/templates/__init__.py`
- Create: `apps/backend/app/templates/loader.py`
- Create: `apps/backend/tests/test_template_loader.py`

**Interfaces:**
- Consumes: nothing new (Pydantic only).
- Produces (in `app.core.contracts`): `TemplateParam(name: str, required: bool = False)`, `DataRequirement(module: str, metric: str, params: dict = {})`, `NarrationConfig(system_prompt: str, output_sections: list[str])`, `RenderConfig(format: Literal["markdown"] = "markdown", include_citation_appendix: bool = True)`, `Template(name: str, title: str, description: str, params: list[TemplateParam], data_requirements: list[DataRequirement], narration: NarrationConfig, render: RenderConfig)`. Produces (in `app.templates.loader`): `load_template(path: Path) -> Template`, `load_templates_from_directory(directory: Path) -> list[Template]`. Task 2's registry stores `Template` instances; Tasks 4–7 build/consume them.
- **These models live in `contracts.py`, not a new `app/templates/contracts.py`, specifically to avoid a circular import**: Task 2's template registry (in `app/core/registry.py`) needs the `Template` type, and `app/templates/loader.py` needs to call the registry's `register_template` — if `Template` lived in `loader.py`, `registry.py` importing it would create `registry → loader → registry`. Defining it in the dependency-free `contracts.py` breaks the cycle (both `registry.py` and `loader.py` import from `contracts.py`, never from each other for types).

- [ ] **Step 1: Add the `pyyaml` dependency**

```bash
cd apps/backend
uv add pyyaml
```

Expected: exits 0; `pyproject.toml`'s `dependencies` list now includes `pyyaml`.

- [ ] **Step 2: Write the failing tests**

Create `apps/backend/tests/test_template_loader.py`:

```python
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.contracts import DataRequirement, NarrationConfig, RenderConfig, Template, TemplateParam
from app.templates.loader import load_template, load_templates_from_directory


def test_template_param_defaults_to_not_required():
    param = TemplateParam(name="community")

    assert param.required is False


def test_data_requirement_defaults_to_empty_params():
    req = DataRequirement(module="survey123", metric="incident_count")

    assert req.params == {}


def test_render_config_defaults():
    config = RenderConfig()

    assert config.format == "markdown"
    assert config.include_citation_appendix is True


def make_minimal_template_dict() -> dict:
    return {
        "name": "test_template",
        "title": "Test Template",
        "description": "A template for testing",
        "params": [{"name": "date_from", "required": True}],
        "data_requirements": [
            {"module": "survey123", "metric": "incident_count", "params": {"date_from": "{date_from}"}}
        ],
        "narration": {
            "system_prompt": "You are a test narrator.",
            "output_sections": ["headline"],
        },
        "render": {"format": "markdown", "include_citation_appendix": True},
    }


def test_template_validates_from_dict():
    template = Template.model_validate(make_minimal_template_dict())

    assert template.name == "test_template"
    assert template.params[0].name == "date_from"
    assert template.params[0].required is True
    assert template.data_requirements[0].module == "survey123"
    assert template.narration.output_sections == ["headline"]


def test_template_rejects_missing_required_field():
    raw = make_minimal_template_dict()
    del raw["narration"]

    with pytest.raises(ValidationError):
        Template.model_validate(raw)


def test_load_template_reads_and_validates_yaml_file(tmp_path):
    yaml_path = tmp_path / "test_template.yaml"
    yaml_path.write_text(
        """
name: test_template
title: Test Template
description: A template for testing
params:
  - name: date_from
    required: true
  - name: date_to
    required: true
data_requirements:
  - module: survey123
    metric: incident_count
    params: { date_from: "{date_from}", date_to: "{date_to}" }
narration:
  system_prompt: |
    You are a test narrator.
  output_sections: [headline]
render:
  format: markdown
  include_citation_appendix: true
"""
    )

    template = load_template(yaml_path)

    assert template.name == "test_template"
    assert len(template.params) == 2
    assert template.data_requirements[0].params == {"date_from": "{date_from}", "date_to": "{date_to}"}


def test_load_templates_from_directory_loads_all_yaml_files(tmp_path):
    (tmp_path / "a.yaml").write_text(
        """
name: template_a
title: A
description: d
params: []
data_requirements: []
narration:
  system_prompt: p
  output_sections: []
render: {}
"""
    )
    (tmp_path / "b.yaml").write_text(
        """
name: template_b
title: B
description: d
params: []
data_requirements: []
narration:
  system_prompt: p
  output_sections: []
render: {}
"""
    )

    templates = load_templates_from_directory(tmp_path)

    assert sorted(t.name for t in templates) == ["template_a", "template_b"]


def test_load_templates_from_directory_empty_directory_returns_empty_list(tmp_path):
    assert load_templates_from_directory(tmp_path) == []
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd apps/backend
uv run pytest tests/test_template_loader.py -v
```

Expected: FAIL — `ImportError: cannot import name 'TemplateParam' from 'app.core.contracts'`.

- [ ] **Step 4: Append to `app/core/contracts.py`**

Append at the end of the file:

```python
class TemplateParam(BaseModel):
    name: str
    required: bool = False


class DataRequirement(BaseModel):
    module: str
    metric: str
    params: dict = {}


class NarrationConfig(BaseModel):
    system_prompt: str
    output_sections: list[str]


class RenderConfig(BaseModel):
    format: Literal["markdown"] = "markdown"
    include_citation_appendix: bool = True


class Template(BaseModel):
    name: str
    title: str
    description: str
    params: list[TemplateParam]
    data_requirements: list[DataRequirement]
    narration: NarrationConfig
    render: RenderConfig
```

- [ ] **Step 5: Implement `app/templates/loader.py`**

Create `apps/backend/app/templates/__init__.py` (empty file).

Create `apps/backend/app/templates/loader.py`:

```python
from pathlib import Path

import yaml

from app.core.contracts import Template


def load_template(path: Path) -> Template:
    with open(path) as f:
        raw = yaml.safe_load(f)
    return Template.model_validate(raw)


def load_templates_from_directory(directory: Path) -> list[Template]:
    return [load_template(p) for p in sorted(directory.glob("*.yaml"))]
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
cd apps/backend
uv run pytest tests/test_template_loader.py -v
```

Expected: `8 passed`.

- [ ] **Step 7: Run the full suite**

```bash
cd apps/backend
uv run pytest -v
```

Expected: `148 passed`.

- [ ] **Step 8: Commit**

```bash
git add apps/backend/pyproject.toml apps/backend/uv.lock apps/backend/app/core/contracts.py \
        apps/backend/app/templates/__init__.py apps/backend/app/templates/loader.py \
        apps/backend/tests/test_template_loader.py
git commit -m "backend: add template contracts and YAML loader"
```

---

### Task 2: Template registry

**Files:**
- Modify: `apps/backend/app/core/registry.py` (append)
- Create: `apps/backend/tests/test_template_registry.py`

**Interfaces:**
- Consumes: `Template` (Task 1).
- Produces (appended to `app.core.registry`, alongside the existing `DataModule` registry — untouched): `register_template(template: Template) -> None`, `get_template(name: str) -> Template | None`, `list_templates() -> list[Template]`, `reset_template_registry() -> None`. Task 6's engine and Task 7's CLI look up templates by name via `get_template`.

- [ ] **Step 1: Write the failing tests**

Create `apps/backend/tests/test_template_registry.py`:

```python
import pytest

from app.core.contracts import DataRequirement, NarrationConfig, RenderConfig, Template
from app.core.registry import get_template, list_templates, register_template, reset_template_registry


def make_template(name: str = "test_template") -> Template:
    return Template(
        name=name,
        title="Test",
        description="test",
        params=[],
        data_requirements=[DataRequirement(module="survey123", metric="incident_count")],
        narration=NarrationConfig(system_prompt="p", output_sections=[]),
        render=RenderConfig(),
    )


@pytest.fixture(autouse=True)
def _clean_template_registry():
    reset_template_registry()
    yield
    reset_template_registry()


def test_register_and_get_template():
    template = make_template()

    register_template(template)

    assert get_template("test_template") is template


def test_get_unregistered_template_returns_none():
    assert get_template("does_not_exist") is None


def test_list_templates_reflects_registrations():
    assert list_templates() == []

    register_template(make_template())

    assert [t.name for t in list_templates()] == ["test_template"]


def test_register_duplicate_template_name_raises():
    register_template(make_template())

    with pytest.raises(ValueError, match="test_template"):
        register_template(make_template())
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd apps/backend
uv run pytest tests/test_template_registry.py -v
```

Expected: FAIL — `ImportError: cannot import name 'register_template' from 'app.core.registry'`.

- [ ] **Step 3: Append to `app/core/registry.py`**

Update the existing import line at the top of the file from:

```python
from app.core.contracts import Fact, IngestResult, MetricSpec
```

to:

```python
from app.core.contracts import Fact, IngestResult, MetricSpec, Template
```

Append at the end of the file:

```python
_templates: dict[str, Template] = {}


def register_template(template: Template) -> None:
    if template.name in _templates:
        raise ValueError(f"template already registered: {template.name}")
    _templates[template.name] = template


def get_template(name: str) -> Template | None:
    return _templates.get(name)


def list_templates() -> list[Template]:
    return list(_templates.values())


def reset_template_registry() -> None:
    _templates.clear()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd apps/backend
uv run pytest tests/test_template_registry.py -v
```

Expected: `4 passed`.

- [ ] **Step 5: Run the full suite**

```bash
cd apps/backend
uv run pytest -v
```

Expected: `152 passed`.

- [ ] **Step 6: Commit**

```bash
git add apps/backend/app/core/registry.py apps/backend/tests/test_template_registry.py
git commit -m "backend: add template registry"
```

---

### Task 3: LLM client

**Files:**
- Modify: `apps/backend/pyproject.toml` (add `anthropic`)
- Create: `apps/backend/app/core/llm.py`
- Create: `apps/backend/tests/test_llm.py`

**Interfaces:**
- Consumes: `app.config.settings` (Step 1).
- Produces (in `app.core.llm`): `LLMClient` (a `typing.Protocol` with `generate(self, system_prompt: str, user_content: str) -> str`), `FakeLLMClient(responses: list[str] | None = None)` (auto-narrative mode when `responses` is `None`; otherwise pops queued responses, repeating the last one forever once only one remains), `AnthropicLLMClient(api_key: str, model: str, client: "anthropic.Anthropic | None" = None)` (the optional `client` param is dependency injection for testing — real callers never pass it), `get_default_llm_client() -> LLMClient` (returns `AnthropicLLMClient` when `settings.anthropic_api_key` is set, else `FakeLLMClient()`). Task 6's `generate_report` takes an `LLMClient` as a parameter (never constructs one itself); Task 7's CLI calls `get_default_llm_client()`.
- `FakeLLMClient`'s auto-narrative mode expects `user_content` to be a `FactTable`'s `model_dump_json()` output — it parses it and emits one sentence per fact (`"{Metric Title}: {value} {unit} [{cid}]."`), which is guaranteed to pass `check_citations` since every number and citation it emits comes directly from the fact table it was given.

- [ ] **Step 1: Add the `anthropic` dependency**

```bash
cd apps/backend
uv add anthropic
```

Expected: exits 0; `pyproject.toml`'s `dependencies` list now includes `anthropic`.

- [ ] **Step 2: Write the failing tests**

Create `apps/backend/tests/test_llm.py`:

```python
from datetime import datetime, timezone
from unittest.mock import MagicMock

from app.core.contracts import Citation, Fact, FactTable
from app.core.llm import AnthropicLLMClient, FakeLLMClient, get_default_llm_client


def make_fact_table() -> FactTable:
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
    return FactTable(
        request_id="req-1",
        template="test_template",
        params={},
        generated_at=datetime(2024, 7, 1, tzinfo=timezone.utc),
        facts=[fact],
        gaps=[],
    )


def test_fake_llm_client_auto_narrative_mode_emits_matching_number_and_citation():
    client = FakeLLMClient()
    fact_table = make_fact_table()

    narrative = client.generate("system prompt", fact_table.model_dump_json())

    assert "19" in narrative
    assert "[C001]" in narrative


def test_fake_llm_client_custom_responses_are_consumed_in_order():
    client = FakeLLMClient(responses=["first", "second"])

    assert client.generate("p", "u") == "first"
    assert client.generate("p", "u") == "second"


def test_fake_llm_client_repeats_final_response_once_queue_has_one_left():
    client = FakeLLMClient(responses=["only"])

    assert client.generate("p", "u") == "only"
    assert client.generate("p", "u") == "only"


def test_anthropic_client_generate_calls_sdk_correctly():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="generated narrative")]
    mock_client.messages.create.return_value = mock_response

    client = AnthropicLLMClient(api_key="fake-key", model="claude-sonnet-5", client=mock_client)
    result = client.generate("system prompt", "user content")

    assert result == "generated narrative"
    mock_client.messages.create.assert_called_once_with(
        model="claude-sonnet-5",
        max_tokens=4096,
        system="system prompt",
        messages=[{"role": "user", "content": "user content"}],
    )


def test_get_default_llm_client_returns_fake_when_no_api_key(monkeypatch):
    monkeypatch.setattr("app.core.llm.settings", type("S", (), {"anthropic_api_key": None, "anthropic_model": "claude-sonnet-5"})())

    client = get_default_llm_client()

    assert isinstance(client, FakeLLMClient)


def test_get_default_llm_client_returns_anthropic_when_api_key_set(monkeypatch):
    monkeypatch.setattr(
        "app.core.llm.settings",
        type("S", (), {"anthropic_api_key": "sk-test-123", "anthropic_model": "claude-sonnet-5"})(),
    )

    client = get_default_llm_client()

    assert isinstance(client, AnthropicLLMClient)
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd apps/backend
uv run pytest tests/test_llm.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.llm'`.

- [ ] **Step 4: Implement `app/core/llm.py`**

```python
import json
from typing import Protocol

import anthropic

from app.config import settings


class LLMClient(Protocol):
    def generate(self, system_prompt: str, user_content: str) -> str: ...


class FakeLLMClient:
    def __init__(self, responses: list[str] | None = None):
        self._responses = list(responses) if responses is not None else None

    def generate(self, system_prompt: str, user_content: str) -> str:
        if self._responses is not None:
            if len(self._responses) > 1:
                return self._responses.pop(0)
            return self._responses[0]
        return self._auto_narrative(user_content)

    def _auto_narrative(self, user_content: str) -> str:
        data = json.loads(user_content)
        lines = []
        for fact in data["facts"]:
            unit = fact["unit"] or ""
            title = fact["metric"].replace("_", " ").title()
            lines.append(f"{title}: {fact['value']} {unit} [{fact['citation']['cid']}].")
        return "\n\n".join(lines)


class AnthropicLLMClient:
    def __init__(self, api_key: str, model: str, client: "anthropic.Anthropic | None" = None):
        self._client = client or anthropic.Anthropic(api_key=api_key)
        self._model = model

    def generate(self, system_prompt: str, user_content: str) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}],
        )
        return response.content[0].text


def get_default_llm_client() -> LLMClient:
    if settings.anthropic_api_key:
        return AnthropicLLMClient(api_key=settings.anthropic_api_key, model=settings.anthropic_model)
    return FakeLLMClient()
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd apps/backend
uv run pytest tests/test_llm.py -v
```

Expected: `6 passed`.

- [ ] **Step 6: Run the full suite**

```bash
cd apps/backend
uv run pytest -v
```

Expected: `158 passed`.

- [ ] **Step 7: Commit**

```bash
git add apps/backend/pyproject.toml apps/backend/uv.lock apps/backend/app/core/llm.py \
        apps/backend/tests/test_llm.py
git commit -m "backend: add LLM client interface with fake and Anthropic implementations"
```

---

### Task 4: Engine — fact-table assembly

**Files:**
- Create: `apps/backend/app/core/engine.py`
- Create: `apps/backend/tests/test_engine_assembly.py`

**Interfaces:**
- Consumes: `Template`, `DataRequirement`, `Fact`, `FactTable` (Steps 1/5-Task-1), `app.core.registry.get_module` (Step 1).
- Produces (in `app.core.engine`): `resolve_params(raw_params: dict, template_params: dict) -> dict` (replaces string values shaped exactly like `"{key}"` with `template_params[key]`; leaves everything else — literals, non-matching strings — untouched), `validate_params(template: Template, params: dict) -> None` (raises `ValueError` listing every missing required param name if any are absent or `None`), `assemble_fact_table(template: Template, params: dict, session: Session, request_id: str) -> FactTable` (validates params, calls `run_metric` for each `data_requirement` in declared order via the module registry, records a gap for any requirement that returns zero facts, then renumbers every fact's citation id sequentially as `C001`, `C002`, ... across the whole table). Task 6 calls `assemble_fact_table`; Task 7's CLI and tests use `resolve_params`/`validate_params` indirectly through it.

- [ ] **Step 1: Write the failing tests**

Create `apps/backend/tests/test_engine_assembly.py`:

```python
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy.orm import sessionmaker

from app.core.contracts import DataRequirement, NarrationConfig, RenderConfig, Template, TemplateParam
from app.core.engine import assemble_fact_table, resolve_params, validate_params
from app.core.registry import register_module, reset_registry
from app.db import Base, make_engine
from app.modules.survey123.ingest import ingest_csv
from app.modules.survey123.module import survey123_module

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "sample_small.csv"


def make_session(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    ingest_csv(FIXTURE_PATH, session, salt="test-salt")
    return session


@pytest.fixture(autouse=True)
def _clean_registry():
    reset_registry()
    register_module(survey123_module)
    yield
    reset_registry()


def make_minister_template() -> Template:
    return Template(
        name="minister_regional_comparison",
        title="Regional Comparison Briefing",
        description="test",
        params=[
            TemplateParam(name="date_from", required=True),
            TemplateParam(name="date_to", required=True),
        ],
        data_requirements=[
            DataRequirement(
                module="survey123",
                metric="incidents_by_corporation",
                params={"date_from": "{date_from}", "date_to": "{date_to}"},
            ),
            DataRequirement(
                module="survey123",
                metric="relief_actions_summary",
                params={"date_from": "{date_from}", "date_to": "{date_to}"},
            ),
            DataRequirement(
                module="survey123",
                metric="casualty_summary",
                params={"date_from": "{date_from}", "date_to": "{date_to}"},
            ),
            DataRequirement(
                module="survey123",
                metric="data_coverage",
                params={"date_from": "{date_from}", "date_to": "{date_to}"},
            ),
        ],
        narration=NarrationConfig(system_prompt="test", output_sections=["headline"]),
        render=RenderConfig(),
    )


def test_resolve_params_substitutes_exact_placeholder():
    resolved = resolve_params({"date_from": "{date_from}"}, {"date_from": "2024-06-01"})

    assert resolved == {"date_from": "2024-06-01"}


def test_resolve_params_leaves_literal_values_untouched():
    resolved = resolve_params({"corporation": "sangre_grande_regional_corporat"}, {})

    assert resolved == {"corporation": "sangre_grande_regional_corporat"}


def test_resolve_params_leaves_non_matching_strings_untouched():
    resolved = resolve_params({"note": "this has {braces} inside a sentence"}, {})

    assert resolved == {"note": "this has {braces} inside a sentence"}


def test_validate_params_passes_when_all_required_present():
    template = make_minister_template()

    validate_params(template, {"date_from": "2024-06-01", "date_to": "2024-06-30"})


def test_validate_params_raises_listing_missing_required_names():
    template = make_minister_template()

    with pytest.raises(ValueError, match="date_to"):
        validate_params(template, {"date_from": "2024-06-01"})


def test_assemble_fact_table_calls_all_data_requirements_and_renumbers_citations(tmp_path):
    session = make_session(tmp_path)
    template = make_minister_template()

    fact_table = assemble_fact_table(
        template, {"date_from": "2024-06-01", "date_to": "2024-06-30"}, session, "req-1"
    )

    assert fact_table.request_id == "req-1"
    assert fact_table.template == "minister_regional_comparison"
    assert len(fact_table.facts) == 8
    assert [f.citation.cid for f in fact_table.facts] == [f"C{i:03d}" for i in range(1, 9)]


def test_assemble_fact_table_raises_for_unknown_module(tmp_path):
    session = make_session(tmp_path)
    template = make_minister_template().model_copy(
        update={"data_requirements": [DataRequirement(module="not_real", metric="x")]}
    )

    with pytest.raises(ValueError, match="not_real"):
        assemble_fact_table(template, {"date_from": "2024-06-01", "date_to": "2024-06-30"}, session, "req-2")


def test_assemble_fact_table_records_gap_for_empty_metric_result(tmp_path):
    session = make_session(tmp_path)
    template = make_minister_template().model_copy(
        update={
            "data_requirements": [
                DataRequirement(
                    module="survey123",
                    metric="incident_count",
                    params={"corporation": "port_of_spain_city_corporation", "date_from": "2099-01-01", "date_to": "2099-01-02"},
                )
            ]
        }
    )

    fact_table = assemble_fact_table(
        template, {"date_from": "2024-06-01", "date_to": "2024-06-30"}, session, "req-3"
    )

    assert len(fact_table.facts) == 1
    assert fact_table.facts[0].value == 0
    assert fact_table.gaps == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd apps/backend
uv run pytest tests/test_engine_assembly.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.engine'`.

**Note on the last test:** `incident_count` always returns exactly 1 `Fact` (with `value=0` when nothing matches — Step 3's `incident_count` never returns an empty list), so this test intentionally checks that a genuinely-empty-result metric does NOT produce a false gap — Step 3's 9 metrics all return at least 1 `Fact` per call (only `data_coverage` can return a variable count, and it returns 0 facts only when literally zero rows exist in the corporation/community/date scope with no filtering at all, which the fixture data doesn't produce). This test's real purpose is proving `assemble_fact_table` doesn't over-report gaps for a metric that legitimately returns a single zero-valued fact.

- [ ] **Step 3: Implement `app/core/engine.py` (assembly portion — narration is added in Task 6)**

```python
import re
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.contracts import DataRequirement, Fact, FactTable, Template
from app.core.registry import get_module

PLACEHOLDER_RE = re.compile(r"^\{(\w+)\}$")


def resolve_params(raw_params: dict, template_params: dict) -> dict:
    resolved = {}
    for key, value in raw_params.items():
        if isinstance(value, str):
            match = PLACEHOLDER_RE.match(value)
            if match:
                resolved[key] = template_params.get(match.group(1))
                continue
        resolved[key] = value
    return resolved


def validate_params(template: Template, params: dict) -> None:
    missing = [p.name for p in template.params if p.required and params.get(p.name) is None]
    if missing:
        raise ValueError(f"missing required params for template {template.name!r}: {missing}")


def assemble_fact_table(template: Template, params: dict, session: Session, request_id: str) -> FactTable:
    validate_params(template, params)
    all_facts: list[Fact] = []
    gaps: list[str] = []

    for requirement in template.data_requirements:
        module = get_module(requirement.module)
        if module is None:
            raise ValueError(f"unknown data module: {requirement.module}")
        resolved = resolve_params(requirement.params, params)
        facts = module.run_metric(requirement.metric, resolved, session)
        if not facts:
            gaps.append(f"No data returned for {requirement.module}.{requirement.metric} with params {resolved}")
        all_facts.extend(facts)

    renumbered: list[Fact] = []
    for index, fact in enumerate(all_facts, start=1):
        new_citation = fact.citation.model_copy(update={"cid": f"C{index:03d}"})
        renumbered.append(fact.model_copy(update={"citation": new_citation}))

    return FactTable(
        request_id=request_id,
        template=template.name,
        params=params,
        generated_at=datetime.now(timezone.utc),
        facts=renumbered,
        gaps=gaps,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd apps/backend
uv run pytest tests/test_engine_assembly.py -v
```

Expected: `8 passed`.

- [ ] **Step 5: Run the full suite**

```bash
cd apps/backend
uv run pytest -v
```

Expected: `166 passed`.

- [ ] **Step 6: Commit**

```bash
git add apps/backend/app/core/engine.py apps/backend/tests/test_engine_assembly.py
git commit -m "backend: add engine fact-table assembly"
```

---

### Task 5: Renderer

**Files:**
- Create: `apps/backend/app/core/renderer.py`
- Create: `apps/backend/tests/test_renderer.py`

**Interfaces:**
- Consumes: `Template`, `FactTable` (Task 1/Step 1).
- Produces: `render_report(template: Template, fact_table: FactTable, narrative: str) -> str` — a complete markdown document: `# {template.title}`, the narrative verbatim, a `## Data Tables` section with one markdown table per fact that has a non-null `breakdown`, a `## Data Gaps` section if `fact_table.gaps` is non-empty, and a `## Citation Appendix` (one line per fact's citation) when `template.render.include_citation_appendix` is `True`. Task 6's `generate_report` calls this to build `GeneratedReport.markdown`.

- [ ] **Step 1: Write the failing tests**

Create `apps/backend/tests/test_renderer.py`:

```python
from datetime import datetime, timezone

from app.core.contracts import (
    Citation,
    Fact,
    FactTable,
    NarrationConfig,
    RenderConfig,
    Template,
)
from app.core.renderer import render_report


def make_citation(cid: str) -> Citation:
    return Citation(
        cid=cid,
        module="survey123",
        description=f"test citation {cid}",
        query_ref="test()",
        record_ids=["GUID-1"],
        as_of=datetime(2024, 7, 1, tzinfo=timezone.utc),
    )


def make_template(include_citation_appendix: bool = True) -> Template:
    return Template(
        name="test_template",
        title="Test Briefing",
        description="test",
        params=[],
        data_requirements=[],
        narration=NarrationConfig(system_prompt="p", output_sections=["headline"]),
        render=RenderConfig(include_citation_appendix=include_citation_appendix),
    )


def make_fact_table(facts=None, gaps=None) -> FactTable:
    return FactTable(
        request_id="req-1",
        template="test_template",
        params={},
        generated_at=datetime(2024, 7, 1, tzinfo=timezone.utc),
        facts=facts or [],
        gaps=gaps or [],
    )


def test_render_includes_title_and_narrative():
    fact_table = make_fact_table()

    markdown = render_report(make_template(), fact_table, "This is the narrative text.")

    assert "# Test Briefing" in markdown
    assert "This is the narrative text." in markdown


def test_render_includes_data_table_for_fact_with_breakdown():
    fact = Fact(
        metric="incidents_by_corporation",
        value=19,
        unit="incidents",
        scope={"corporation": "all"},
        breakdown={"sangre_grande_regional_corporat": 10, "san_fernando_city_corporation": 9},
        verification="validated",
        citation=make_citation("C001"),
    )
    fact_table = make_fact_table(facts=[fact])

    markdown = render_report(make_template(), fact_table, "narrative")

    assert "## Data Tables" in markdown
    assert "sangre_grande_regional_corporat" in markdown
    assert "| 10 |" in markdown


def test_render_skips_data_tables_section_when_no_fact_has_breakdown():
    fact = Fact(
        metric="special_needs_count",
        value=2,
        unit="persons",
        scope={"corporation": "all"},
        breakdown=None,
        verification="validated",
        citation=make_citation("C001"),
    )
    fact_table = make_fact_table(facts=[fact])

    markdown = render_report(make_template(), fact_table, "narrative")

    assert "## Data Tables" not in markdown


def test_render_includes_data_gaps_section_when_gaps_present():
    fact_table = make_fact_table(gaps=["No data returned for survey123.incident_count with params {}"])

    markdown = render_report(make_template(), fact_table, "narrative")

    assert "## Data Gaps" in markdown
    assert "No data returned for survey123.incident_count" in markdown


def test_render_skips_data_gaps_section_when_no_gaps():
    fact_table = make_fact_table(gaps=[])

    markdown = render_report(make_template(), fact_table, "narrative")

    assert "## Data Gaps" not in markdown


def test_render_includes_citation_appendix_by_default():
    fact = Fact(
        metric="incident_count",
        value=19,
        unit="incidents",
        scope={"corporation": "all"},
        breakdown=None,
        verification="validated",
        citation=make_citation("C001"),
    )
    fact_table = make_fact_table(facts=[fact])

    markdown = render_report(make_template(), fact_table, "narrative")

    assert "## Citation Appendix" in markdown
    assert "C001" in markdown
    assert "test citation C001" in markdown


def test_render_omits_citation_appendix_when_disabled():
    fact = Fact(
        metric="incident_count",
        value=19,
        unit="incidents",
        scope={"corporation": "all"},
        breakdown=None,
        verification="validated",
        citation=make_citation("C001"),
    )
    fact_table = make_fact_table(facts=[fact])

    markdown = render_report(make_template(include_citation_appendix=False), fact_table, "narrative")

    assert "## Citation Appendix" not in markdown
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd apps/backend
uv run pytest tests/test_renderer.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.renderer'`.

- [ ] **Step 3: Implement `app/core/renderer.py`**

```python
from app.core.contracts import FactTable, Template


def render_report(template: Template, fact_table: FactTable, narrative: str) -> str:
    parts = [f"# {template.title}", "", narrative.strip(), ""]

    table_blocks = []
    for fact in fact_table.facts:
        if not fact.breakdown:
            continue
        table_blocks.append(f"**{fact.metric}** ({fact.citation.cid})")
        table_blocks.append("")
        table_blocks.append("| Key | Value |")
        table_blocks.append("|---|---|")
        for key, value in fact.breakdown.items():
            table_blocks.append(f"| {key} | {value} |")
        table_blocks.append("")

    if table_blocks:
        parts.append("## Data Tables")
        parts.extend(table_blocks)

    if fact_table.gaps:
        parts.append("## Data Gaps")
        for gap in fact_table.gaps:
            parts.append(f"- {gap}")
        parts.append("")

    if template.render.include_citation_appendix:
        parts.append("## Citation Appendix")
        for fact in fact_table.facts:
            citation = fact.citation
            parts.append(
                f"- [{citation.cid}] {citation.description} "
                f"(query_ref: `{citation.query_ref}`, as_of: {citation.as_of})"
            )

    return "\n".join(parts)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd apps/backend
uv run pytest tests/test_renderer.py -v
```

Expected: `7 passed`.

- [ ] **Step 5: Run the full suite**

```bash
cd apps/backend
uv run pytest -v
```

Expected: `173 passed`.

- [ ] **Step 6: Commit**

```bash
git add apps/backend/app/core/renderer.py apps/backend/tests/test_renderer.py
git commit -m "backend: add deterministic markdown renderer"
```

---

### Task 6: Engine — narration, retry, and `generate_report`

**Files:**
- Modify: `apps/backend/app/core/engine.py` (append)
- Create: `apps/backend/tests/test_engine_generate.py`

**Interfaces:**
- Consumes: `assemble_fact_table` (Task 4), `render_report` (Task 5), `LLMClient` (Task 3), `check_citations` (Step 4).
- Produces: `GeneratedReport` (Pydantic `BaseModel`: `request_id: str`, `template: str`, `params: dict`, `fact_table: FactTable`, `narrative: str`, `status: Literal["ok", "needs_review"]`, `violations: list[CitationViolation]`, `markdown: str`), `build_retry_content(user_content: str, violations: list[CitationViolation]) -> str`, `generate_report(template: Template, params: dict, session: Session, llm_client: LLMClient) -> GeneratedReport` — the module's public entry point. Task 7's CLI calls `generate_report` directly.

- [ ] **Step 1: Write the failing tests**

Create `apps/backend/tests/test_engine_generate.py`:

```python
from pathlib import Path

import pytest
from sqlalchemy.orm import sessionmaker

from app.core.contracts import DataRequirement, NarrationConfig, RenderConfig, Template, TemplateParam
from app.core.engine import assemble_fact_table, generate_report
from app.core.llm import FakeLLMClient
from app.core.registry import register_module, reset_registry
from app.db import Base, make_engine
from app.modules.survey123.ingest import ingest_csv
from app.modules.survey123.module import survey123_module

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "sample_small.csv"


def make_session(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    ingest_csv(FIXTURE_PATH, session, salt="test-salt")
    return session


@pytest.fixture(autouse=True)
def _clean_registry():
    reset_registry()
    register_module(survey123_module)
    yield
    reset_registry()


def make_minister_template() -> Template:
    return Template(
        name="minister_regional_comparison",
        title="Regional Comparison Briefing",
        description="test",
        params=[
            TemplateParam(name="date_from", required=True),
            TemplateParam(name="date_to", required=True),
        ],
        data_requirements=[
            DataRequirement(
                module="survey123",
                metric="incidents_by_corporation",
                params={"date_from": "{date_from}", "date_to": "{date_to}"},
            ),
        ],
        narration=NarrationConfig(system_prompt="You are drafting a briefing.", output_sections=["headline"]),
        render=RenderConfig(),
    )


def test_generate_report_with_auto_narrative_fake_client_passes(tmp_path):
    session = make_session(tmp_path)
    template = make_minister_template()

    report = generate_report(
        template, {"date_from": "2024-06-01", "date_to": "2024-06-30"}, session, FakeLLMClient()
    )

    assert report.status == "ok"
    assert report.violations == []
    assert "# Regional Comparison Briefing" in report.markdown
    assert "## Citation Appendix" in report.markdown
    assert report.request_id


def test_generate_report_corrupted_narrative_twice_needs_review(tmp_path):
    session = make_session(tmp_path)
    template = make_minister_template()
    bad_narrative = "There were 999999 incidents recorded."

    report = generate_report(
        template,
        {"date_from": "2024-06-01", "date_to": "2024-06-30"},
        session,
        FakeLLMClient(responses=[bad_narrative]),
    )

    assert report.status == "needs_review"
    assert len(report.violations) > 0


def test_generate_report_recovers_on_retry(tmp_path):
    session = make_session(tmp_path)
    template = make_minister_template()

    fact_table = assemble_fact_table(
        template, {"date_from": "2024-06-01", "date_to": "2024-06-30"}, session, "req-preview"
    )
    good_fact = fact_table.facts[0]
    bad_narrative = "There were 999999 incidents recorded."
    good_narrative = f"There were {good_fact.value} incidents by corporation [{good_fact.citation.cid}]."

    report = generate_report(
        template,
        {"date_from": "2024-06-01", "date_to": "2024-06-30"},
        session,
        FakeLLMClient(responses=[bad_narrative, good_narrative]),
    )

    assert report.status == "ok"
    assert report.violations == []


def test_generate_report_raises_for_missing_required_param(tmp_path):
    session = make_session(tmp_path)
    template = make_minister_template()

    with pytest.raises(ValueError, match="date_to"):
        generate_report(template, {"date_from": "2024-06-01"}, session, FakeLLMClient())
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd apps/backend
uv run pytest tests/test_engine_generate.py -v
```

Expected: FAIL — `ImportError: cannot import name 'generate_report' from 'app.core.engine'`.

- [ ] **Step 3: Append to `app/core/engine.py`**

Add these imports to the top of the file (alongside the existing ones from Task 4):

```python
import uuid
from typing import Literal

from pydantic import BaseModel

from app.core.citation_check import CitationViolation, check_citations
from app.core.llm import LLMClient
from app.core.renderer import render_report
```

Append at the end of the file:

```python
class GeneratedReport(BaseModel):
    request_id: str
    template: str
    params: dict
    fact_table: FactTable
    narrative: str
    status: Literal["ok", "needs_review"]
    violations: list[CitationViolation]
    markdown: str


def build_retry_content(user_content: str, violations: list[CitationViolation]) -> str:
    violation_lines = "\n".join(f"- {v.kind}: {v.detail} (sentence: {v.sentence!r})" for v in violations)
    return (
        f"{user_content}\n\n"
        f"Your previous narrative had citation violations. Fix them and regenerate:\n{violation_lines}"
    )


def generate_report(template: Template, params: dict, session: Session, llm_client: LLMClient) -> GeneratedReport:
    request_id = str(uuid.uuid4())
    fact_table = assemble_fact_table(template, params, session, request_id)

    user_content = fact_table.model_dump_json()
    narrative = llm_client.generate(template.narration.system_prompt, user_content)
    result = check_citations(narrative, fact_table)

    if not result.passed:
        retry_content = build_retry_content(user_content, result.violations)
        narrative = llm_client.generate(template.narration.system_prompt, retry_content)
        result = check_citations(narrative, fact_table)

    status: Literal["ok", "needs_review"] = "ok" if result.passed else "needs_review"
    markdown = render_report(template, fact_table, narrative)

    return GeneratedReport(
        request_id=request_id,
        template=template.name,
        params=params,
        fact_table=fact_table,
        narrative=narrative,
        status=status,
        violations=result.violations,
        markdown=markdown,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd apps/backend
uv run pytest tests/test_engine_generate.py -v
```

Expected: `4 passed`.

- [ ] **Step 5: Run the full suite**

```bash
cd apps/backend
uv run pytest -v
```

Expected: `177 passed`.

- [ ] **Step 6: Commit**

```bash
git add apps/backend/app/core/engine.py apps/backend/tests/test_engine_generate.py
git commit -m "backend: add generate_report orchestration with retry-once citation checking"
```

---

### Task 7: Real templates, app wiring, and CLI

**Files:**
- Create: `apps/backend/app/templates/definitions/minister_regional_comparison.yaml`
- Create: `apps/backend/app/templates/definitions/single_region_report.yaml`
- Modify: `apps/backend/app/main.py`
- Modify: `apps/backend/tests/test_survey123_module.py` (fixture-only fix, required by the `main.py` change — see Step 5)
- Modify: `apps/backend/cli.py`
- Create: `apps/backend/tests/test_cli_generate.py`

**Interfaces:**
- Consumes: `load_templates_from_directory`, `register_template` (Tasks 1–2), `generate_report`, `get_default_llm_client` (Tasks 3/6).
- Produces: `apps/backend/app/templates/definitions/*.yaml` (the two real templates from `PLAN.md` §5.2/§5.3), `app.main.create_app()` now also loads and registers both templates at boot, `cli.py`'s `generate` command (`cli.py generate <template_name> [--date-from ...] [--date-to ...] [--corporation ...] [--community ...]`) and `list-templates` command.

- [ ] **Step 1: Write the failing tests**

Create `apps/backend/tests/test_cli_generate.py`:

```python
from pathlib import Path

from typer.testing import CliRunner

from app.core.registry import reset_registry, reset_template_registry
from app.db import Base, engine as db_engine
from cli import app

runner = CliRunner()

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "sample_small.csv"
DEV_DB_PATH = Path(__file__).parent.parent / "dev.db"


def _reset_state():
    reset_registry()
    reset_template_registry()
    if DEV_DB_PATH.exists():
        DEV_DB_PATH.unlink()


def test_list_templates_shows_both_real_templates():
    _reset_state()

    result = runner.invoke(app, ["list-templates"])

    assert result.exit_code == 0, result.stdout
    assert "minister_regional_comparison" in result.stdout
    assert "single_region_report" in result.stdout
    _reset_state()


def test_generate_minister_regional_comparison_produces_markdown_report():
    _reset_state()
    Base.metadata.create_all(db_engine)

    try:
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


def test_generate_missing_required_param_errors():
    _reset_state()
    Base.metadata.create_all(db_engine)

    try:
        result = runner.invoke(app, ["generate", "minister_regional_comparison", "--date-from", "2024-06-01"])

        assert result.exit_code == 1
    finally:
        _reset_state()


def test_generate_unknown_template_errors():
    _reset_state()

    result = runner.invoke(app, ["generate", "not_a_real_template"])

    assert result.exit_code == 1
    _reset_state()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd apps/backend
uv run pytest tests/test_cli_generate.py -v
```

Expected: FAIL — `AssertionError` (no `generate`/`list-templates` commands exist yet on the CLI, so Typer reports "No such command").

- [ ] **Step 3: Write `app/templates/definitions/minister_regional_comparison.yaml`**

```yaml
name: minister_regional_comparison
title: Ministerial Regional Comparison Briefing
description: One-page briefing comparing incident activity across corporations for a date window.
params:
  - name: date_from
    required: true
  - name: date_to
    required: true
data_requirements:
  - module: survey123
    metric: incidents_by_corporation
    params: { date_from: "{date_from}", date_to: "{date_to}" }
  - module: survey123
    metric: homes_affected_count
    params: { date_from: "{date_from}", date_to: "{date_to}" }
  - module: survey123
    metric: relief_actions_summary
    params: { date_from: "{date_from}", date_to: "{date_to}" }
  - module: survey123
    metric: casualty_summary
    params: { date_from: "{date_from}", date_to: "{date_to}" }
  - module: survey123
    metric: data_coverage
    params: { date_from: "{date_from}", date_to: "{date_to}" }
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
    - The whole briefing must fit on one page — be concise.
  output_sections: [headline, regional_comparison, actions_taken, data_gaps]
render:
  format: markdown
  include_citation_appendix: true
```

- [ ] **Step 4: Write `app/templates/definitions/single_region_report.yaml`**

```yaml
name: single_region_report
title: Single Region Deep Dive Report
description: Region-level incident deep dive for one corporation over a date window.
params:
  - name: corporation
    required: true
  - name: community
    required: false
  - name: date_from
    required: true
  - name: date_to
    required: true
data_requirements:
  - module: survey123
    metric: incident_count
    params: { corporation: "{corporation}", community: "{community}", date_from: "{date_from}", date_to: "{date_to}" }
  - module: survey123
    metric: street_level_tally
    params: { corporation: "{corporation}", community: "{community}", date_from: "{date_from}", date_to: "{date_to}" }
  - module: survey123
    metric: homes_affected_count
    params: { corporation: "{corporation}", community: "{community}", date_from: "{date_from}", date_to: "{date_to}" }
  - module: survey123
    metric: relief_actions_summary
    params: { corporation: "{corporation}", community: "{community}", date_from: "{date_from}", date_to: "{date_to}" }
  - module: survey123
    metric: special_needs_count
    params: { corporation: "{corporation}", community: "{community}", date_from: "{date_from}", date_to: "{date_to}" }
  - module: survey123
    metric: estimated_damage_total
    params: { corporation: "{corporation}", community: "{community}", date_from: "{date_from}", date_to: "{date_to}" }
  - module: survey123
    metric: data_coverage
    params: { corporation: "{corporation}", date_from: "{date_from}", date_to: "{date_to}" }
narration:
  system_prompt: |
    You are drafting a region-level deep-dive report for a government minister
    in Trinidad and Tobago's Disaster Management Coordinating Unit.

    RULES (absolute):
    - Use ONLY numbers present in the fact table you are given as JSON. Never
      compute, sum, estimate, or round a number that is not already present.
    - Every sentence containing a figure must end with its citation marker,
      e.g. [C001]. Citation markers look like C001, C002, etc.
    - The estimated damage total carries a coverage caveat (N of M records
      reporting a cost estimate) — state it plainly, never as a complete total.
    - If the fact table lists gaps, state them plainly in a Data Gaps section.
  output_sections: [headline, streets, actions_taken, damage_caveat, data_gaps]
render:
  format: markdown
  include_citation_appendix: true
```

**Note on `community: "{community}"` when the caller omits `community`:** `resolve_params` (Task 4) replaces the placeholder with `template_params.get("community")`, which is `None` when the caller didn't pass a `community` param — and Step 3's metric functions already treat `params.get("community")` being `None`/absent identically (no community filter applied), so an omitted optional param flows through correctly without special-casing here.

- [ ] **Step 5: Wire template loading into `app/main.py`**

Replace `apps/backend/app/main.py` with:

```python
from pathlib import Path

from fastapi import FastAPI

from app.api.meta import router as meta_router
from app.core.registry import register_module, register_template
from app.modules.survey123.module import survey123_module
from app.templates.loader import load_templates_from_directory

TEMPLATES_DIR = Path(__file__).parent / "templates" / "definitions"


def create_app() -> FastAPI:
    app = FastAPI(title="DMCU Reporting API")
    app.include_router(meta_router)
    register_module(survey123_module)
    for template in load_templates_from_directory(TEMPLATES_DIR):
        register_template(template)
    return app
```

**This requires a fix to an existing Step 2 test file.** `apps/backend/tests/test_survey123_module.py` has two tests (`test_create_app_registers_survey123_module`, `test_modules_endpoint_includes_survey123_after_create_app`) that each call `create_app()` directly, and its autouse fixture only resets the *module* registry (`reset_registry()`), never a template registry — because no template registry existed when that file was written. Now that `create_app()` also calls `register_template()` for both real templates, the second test's `create_app()` call will raise `ValueError: template already registered: minister_regional_comparison`, since nothing clears `_templates` between the two test functions. Fix the fixture to also reset the template registry.

Replace `apps/backend/tests/test_survey123_module.py`'s import and fixture block:

```python
from app.core.registry import get_module, reset_registry
```

with:

```python
from app.core.registry import get_module, reset_registry, reset_template_registry
```

and replace:

```python
@pytest.fixture(autouse=True)
def _clean_registry():
    reset_registry()
    yield
    reset_registry()
```

with:

```python
@pytest.fixture(autouse=True)
def _clean_registry():
    reset_registry()
    reset_template_registry()
    yield
    reset_registry()
    reset_template_registry()
```

Leave every test function in that file unchanged — this is a fixture-only fix, not a test-behavior change.


app = create_app()
```

- [ ] **Step 6: Add `generate` and `list-templates` commands to `cli.py`**

Replace `apps/backend/cli.py` with:

```python
from pathlib import Path

import typer

from app.core.engine import generate_report
from app.core.llm import get_default_llm_client
from app.core.registry import (
    get_module,
    get_template,
    list_templates,
    register_module,
    register_template,
)
from app.db import SessionLocal
from app.modules.survey123.module import survey123_module
from app.templates.loader import load_templates_from_directory

TEMPLATES_DIR = Path(__file__).parent / "app" / "templates" / "definitions"

app = typer.Typer()
ingest_app = typer.Typer()
app.add_typer(ingest_app, name="ingest")


def _ensure_templates_loaded() -> None:
    if not list_templates():
        for template in load_templates_from_directory(TEMPLATES_DIR):
            register_template(template)


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


@app.command("list-templates")
def list_templates_command() -> None:
    _ensure_templates_loaded()
    for template in list_templates():
        typer.echo(f"{template.name}: {template.title}")


@app.command()
def generate(
    template_name: str,
    date_from: str = typer.Option(None, "--date-from"),
    date_to: str = typer.Option(None, "--date-to"),
    corporation: str = typer.Option(None, "--corporation"),
    community: str = typer.Option(None, "--community"),
) -> None:
    _ensure_templates_loaded()
    if get_module("survey123") is None:
        register_module(survey123_module)

    template = get_template(template_name)
    if template is None:
        typer.echo(f"unknown template: {template_name}", err=True)
        raise typer.Exit(code=1)

    params = {
        "date_from": date_from,
        "date_to": date_to,
        "corporation": corporation,
        "community": community,
    }

    session = SessionLocal()
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

- [ ] **Step 7: Run tests to verify they pass**

```bash
cd apps/backend
uv run pytest tests/test_cli_generate.py -v
```

Expected: `4 passed`.

- [ ] **Step 8: Run the full suite**

```bash
cd apps/backend
uv run pytest -v
```

Expected: `181 passed`.

- [ ] **Step 9: Manual verification — the plan's actual Definition of Done**

```bash
cd apps/backend
rm -f dev.db
uv run alembic upgrade head
uv run python cli.py ingest survey123 fixtures/sample_small.csv
uv run python cli.py generate minister_regional_comparison --date-from 2024-06-01 --date-to 2024-06-30
rm -f dev.db
```

Expected: a complete markdown report prints to stdout, including a `# Ministerial Regional Comparison Briefing` heading, a narrative body, one or more `## Data Tables`, and a `## Citation Appendix` listing citations `C001` upward; `status: ok` prints to stderr. This is run against the committed fixture, not the real 14,942-row export — no PII risk, no `output.csv` involved, and `dev.db` is cleaned up either way.

- [ ] **Step 10: Commit**

```bash
git add apps/backend/app/templates/definitions/ apps/backend/app/main.py \
        apps/backend/tests/test_survey123_module.py \
        apps/backend/cli.py apps/backend/tests/test_cli_generate.py
git commit -m "backend: add real report templates and CLI generate command"
```

---

## Definition of Done (matches `PLAN.md` §6 Step 5, adapted — no Docker/API/persistence, those are Step 6)

- [ ] `cd apps/backend && uv run pytest -v` — all 181 tests pass, 0 failures.
- [ ] `cli.py generate minister_regional_comparison --date-from ... --date-to ...` against ingested sample data produces a complete markdown report with a citation appendix (Task 7 Step 9).
- [ ] A deliberately-corrupted fake LLM output is caught and flagged `needs_review` (`test_generate_report_corrupted_narrative_twice_needs_review`).
- [ ] The engine is fully testable offline: every test in this plan uses `FakeLLMClient`, never a real network call; `AnthropicLLMClient` is tested via constructor-injected mock only.
