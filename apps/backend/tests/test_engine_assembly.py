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
