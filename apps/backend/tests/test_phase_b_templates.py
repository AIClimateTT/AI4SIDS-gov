from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.core.contracts import DataRequirement, NarrationConfig, RenderConfig, Template, TemplateParam
from app.core.engine import CITATION_RULES, compose_system_prompt, generate_report, resolve_effective_requirements
from app.core.registry import reset_registry
from app.core.template_store import import_template_directory
from app.db import Base, engine as db_engine
from app import create_app
from app.modules.survey123.ingest import ingest_csv
from app.modules.survey123.module import survey123_module

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "sample_small.csv"
TEMPLATES_DIR = Path(__file__).parent.parent / "app" / "templates" / "definitions"
DEV_DB_PATH = Path(__file__).parent.parent / "dev.db"


class CapturingLLMClient:
    def __init__(self, narrative: str):
        self.last_system_prompt = ""
        self._narrative = narrative

    def generate(self, system_prompt: str, user_content: str) -> str:
        self.last_system_prompt = system_prompt
        return self._narrative


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


def make_client(monkeypatch) -> TestClient:
    from app.core.registry import register_module

    monkeypatch.setattr("app.core.llm.settings.llm_provider", "fake")
    register_module(survey123_module)
    Base.metadata.create_all(db_engine)
    Session = sessionmaker(bind=db_engine)
    session = Session()
    import_template_directory(TEMPLATES_DIR, session)
    ingest_csv(FIXTURE_PATH, session, salt="test-salt")
    session.close()
    return TestClient(create_app())


def test_compose_system_prompt_includes_citation_rules():
    template = Template(
        name="test",
        title="Test",
        description="test",
        params=[],
        data_requirements=[],
        narration=NarrationConfig.of("Write a briefing."),
        render=RenderConfig(),
    )

    prompt = compose_system_prompt(template)

    assert CITATION_RULES in prompt
    assert "Write a briefing." in prompt


def test_resolve_effective_requirements_rejects_empty():
    template = Template(
        name="test",
        title="Test",
        description="test",
        params=[],
        data_requirements=[],
        narration=NarrationConfig.of("x", output_sections=[]),
        render=RenderConfig(),
    )

    with pytest.raises(ValueError, match="at least one data requirement"):
        resolve_effective_requirements(template, None)


def test_post_templates_creates_new_version(monkeypatch):
    client = make_client(monkeypatch)

    response = client.post(
        "/templates",
        json={
            "name": "minister_situation_report",
            "title": "Minister Briefing v2",
            "description": "Updated",
            "params": [
                {"name": "date_from", "required": True},
                {"name": "date_to", "required": True},
            ],
            "data_requirements": [
                {
                    "module": "survey123",
                    "metric": "incident_count",
                    "params": {"date_from": "{date_from}", "date_to": "{date_to}"},
                }
            ],
            "narration": {
                "identity": "Minister writer",
                "skills": {"compose": "Situation overview for the minister."},
                "output_sections": ["situation_overview", "data_gaps"],
            },
        },
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["version"] == 2
    assert body["title"] == "Minister Briefing v2"


def test_get_template_versions_lists_all(monkeypatch):
    client = make_client(monkeypatch)
    client.post(
        "/templates",
        json={
            "name": "minister_situation_report",
            "title": "v2",
            "description": "d",
            "params": [
                {"name": "date_from", "required": True},
                {"name": "date_to", "required": True},
            ],
            "data_requirements": [
                {
                    "module": "survey123",
                    "metric": "incident_count",
                    "params": {"date_from": "{date_from}", "date_to": "{date_to}"},
                }
            ],
            "narration": {
                "identity": "Minister writer",
                "skills": {"compose": "x"},
                "output_sections": ["headline"],
            },
        },
    )

    response = client.get("/templates/minister_situation_report/versions")

    assert response.status_code == 200
    versions = [v["version"] for v in response.json()]
    assert versions == [2, 1]


def test_generate_with_metric_override_stores_effective_requirements(monkeypatch):
    client = make_client(monkeypatch)

    create = client.post(
        "/reports",
        json={
            "template": "minister_situation_report",
            "params": {"date_from": "2024-06-01", "date_to": "2024-06-30"},
            "data_requirements": [
                {
                    "module": "survey123",
                    "metric": "incident_count",
                    "params": {"date_from": "{date_from}", "date_to": "{date_to}"},
                }
            ],
        },
    )
    assert create.status_code == 202, create.text
    report_id = create.json()["id"]

    detail = client.get(f"/reports/{report_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert len(body["data_requirements"]) == 1
    assert body["data_requirements"][0]["metric"] == "incident_count"


def test_generate_with_empty_requirements_returns_400(monkeypatch):
    client = make_client(monkeypatch)

    response = client.post(
        "/reports",
        json={
            "template": "minister_situation_report",
            "params": {"date_from": "2024-06-01", "date_to": "2024-06-30"},
            "data_requirements": [],
        },
    )

    assert response.status_code == 400


def test_generate_includes_citation_rules_in_llm_prompt(tmp_path, monkeypatch):
    from app.core.registry import register_module

    reset_registry()
    register_module(survey123_module)
    engine = __import__("app.db", fromlist=["make_engine"]).make_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    ingest_csv(FIXTURE_PATH, session, salt="test-salt")

    template = Template(
        name="minister_situation_report",
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
        narration=NarrationConfig.of("Custom briefing tone."),
        render=RenderConfig(),
    )

    fact_table_preview = __import__("app.core.engine", fromlist=["assemble_fact_table"]).assemble_fact_table(
        template,
        {"date_from": "2024-06-01", "date_to": "2024-06-30"},
        session,
        "preview",
        template.data_requirements,
    )
    good = fact_table_preview.facts[0]
    narrative = f"Count is {good.value} [{good.citation.cid}]."
    client = CapturingLLMClient(narrative)

    generate_report(
        template,
        {"date_from": "2024-06-01", "date_to": "2024-06-30"},
        session,
        client,
    )

    assert CITATION_RULES in client.last_system_prompt
    assert "Custom briefing tone." in client.last_system_prompt
