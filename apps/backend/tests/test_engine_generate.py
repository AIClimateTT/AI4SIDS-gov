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
