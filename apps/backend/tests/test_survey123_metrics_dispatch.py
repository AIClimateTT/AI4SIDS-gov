from pathlib import Path

import pytest
from sqlalchemy.orm import sessionmaker

from app.db import Base, make_engine
from app.modules.survey123.ingest import ingest_csv
from app.modules.survey123.module import survey123_module

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "sample_small.csv"

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
}


def make_session(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    ingest_csv(FIXTURE_PATH, session, salt="test-salt")
    return session


def test_list_metrics_returns_all_nine_with_correct_names():
    specs = survey123_module.list_metrics()

    assert {spec.name for spec in specs} == EXPECTED_METRIC_NAMES
    assert len(specs) == 9
    for spec in specs:
        assert spec.module == "survey123"
        assert spec.params_schema["type"] == "object"


def test_run_metric_dispatches_to_incident_count(tmp_path):
    session = make_session(tmp_path)

    facts = survey123_module.run_metric("incident_count", {}, session)

    assert len(facts) == 1
    assert facts[0].value == 19


def test_run_metric_dispatches_to_data_coverage_multi_fact(tmp_path):
    session = make_session(tmp_path)

    facts = survey123_module.run_metric("data_coverage", {}, session)

    assert len(facts) == 4


def test_run_metric_still_raises_for_unknown_metric(tmp_path):
    session = make_session(tmp_path)

    with pytest.raises(ValueError, match="not_a_real_metric"):
        survey123_module.run_metric("not_a_real_metric", {}, session)
