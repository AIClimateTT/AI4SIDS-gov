import json
from pathlib import Path

import pytest
from sqlalchemy.orm import sessionmaker

from app.core.contracts import DataRequirement, NarrationConfig, RenderConfig, Template, TemplateParam
from app.core.engine import assemble_fact_table, generate_report
from app.core.llm import FakeLLMClient
from app.db import Base, make_engine
from app.modules.survey123.ingest import ingest_csv

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "sample_small.csv"


class CapturingLLMClient:
    # Mirrors CapturingLLMClient in test_phase_b_templates.py, extended to
    # also capture user_content so a test can inspect exactly what payload
    # the LLM was sent.
    def __init__(self, narrative: str):
        self.last_system_prompt = ""
        self.last_user_content = ""
        self._narrative = narrative

    def generate(self, system_prompt: str, user_content: str) -> str:
        self.last_system_prompt = system_prompt
        self.last_user_content = user_content
        return self._narrative


def make_session(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    ingest_csv(FIXTURE_PATH, session, salt="test-salt")
    return session


@pytest.fixture(autouse=True)
def _clean_registry():
    yield


def make_minister_template() -> Template:
    return Template(
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
        narration=NarrationConfig.of("You are drafting a briefing."),
        render=RenderConfig(),
    )


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
    assert report.quality_eval is not None
    assert report.quality_eval.citations.rate >= 0.0


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
        template,
        {"date_from": "2024-06-01", "date_to": "2024-06-30"},
        session,
        "req-preview",
        template.data_requirements,
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


def test_llm_payload_omits_record_ids_but_report_keeps_them_in_full(tmp_path):
    # record_ids exist for storage and the citation appendix, not for the
    # LLM: left in, they run into hundreds of KB at realistic data volumes
    # and blow through ollama_num_ctx, silently returning an empty
    # narrative. The payload sent to the LLM must carry none of them while
    # the fact table returned to the caller (and passed to render_report)
    # keeps them in full.
    session = make_session(tmp_path)
    template = make_minister_template()

    preview_fact_table = assemble_fact_table(
        template,
        {"date_from": "2024-06-01", "date_to": "2024-06-30"},
        session,
        "req-preview",
        template.data_requirements,
    )
    good_fact = preview_fact_table.facts[0]
    assert good_fact.citation.record_ids  # sanity: fixture data yields real ids
    good_narrative = f"There were {good_fact.value} incidents by corporation [{good_fact.citation.cid}]."

    client = CapturingLLMClient(good_narrative)

    report = generate_report(
        template,
        {"date_from": "2024-06-01", "date_to": "2024-06-30"},
        session,
        client,
    )

    assert report.status == "ok"

    sent_payload = json.loads(client.last_user_content)
    assert sent_payload["facts"], "sanity: the payload actually carries facts"
    for fact in sent_payload["facts"]:
        assert fact["citation"]["record_ids"] is None

    assert report.fact_table.facts
    for fact in report.fact_table.facts:
        assert fact.citation.record_ids  # full provenance preserved for storage/rendering


def _prose_free_table():
    from datetime import datetime, timezone

    from app.core.contracts import Citation, Fact, FactTable

    return FactTable(
        request_id="r",
        template="t",
        params={},
        generated_at=datetime(2026, 8, 21, tzinfo=timezone.utc),
        facts=[
            Fact(
                metric="incident_count",
                value=3,
                unit="incidents",
                scope={},
                breakdown=None,
                verification="pending",
                citation=Citation(
                    cid="C001",
                    module="sitreps",
                    description="d",
                    query_ref="q",
                    record_ids=[],
                    as_of=datetime(2026, 8, 21, tzinfo=timezone.utc),
                ),
            )
        ],
        gaps=[],
    )


def _template_with_sections(sections: list[str]) -> Template:
    return Template(
        name="t",
        title="T",
        description="d",
        params=[],
        data_requirements=[],
        narration=NarrationConfig.of(output_sections=sections),
        render=RenderConfig(),
    )


class _RecordingLLM:
    def __init__(self):
        self.calls = 0

    def generate(self, system_prompt: str, user_content: str) -> str:
        self.calls += 1
        return "3 incidents were recorded [C001]."


def test_no_output_sections_skips_the_llm():
    from app.core.engine import narrate_fact_table

    llm = _RecordingLLM()

    report = narrate_fact_table(_template_with_sections([]), _prose_free_table(), llm)

    assert llm.calls == 0
    assert report.narrative == ""
    assert report.status == "ok"
    assert report.violations == []


def test_output_sections_still_call_the_llm():
    from app.core.engine import narrate_fact_table

    llm = _RecordingLLM()

    report = narrate_fact_table(_template_with_sections(["overview"]), _prose_free_table(), llm)

    assert llm.calls == 1
    assert "3 incidents" in report.narrative
