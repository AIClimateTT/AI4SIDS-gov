import os
import sys
from pathlib import Path

import pytest
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


def test_mcp_module_run_metric_raises_cleanly_when_underlying_metric_fn_errors(tmp_path):
    """Resolves Task 6's open question: an exception raised inside a metric function
    (here, datetime.fromisoformat blowing up on a bad date string) surfaces to the MCP
    client as a clean CallToolResult with isError=True, not a hang or crash. McpDataModule
    must translate that into a normal Python exception raised from run_metric, without
    leaking any transport/session details.
    """
    make_session(tmp_path)
    module = make_mcp_module(tmp_path)

    with pytest.raises(ValueError, match="incident_count"):
        module.run_metric(
            "incident_count",
            {"date_from": "not-a-date", "date_to": "also-not-a-date"},
            session=None,
        )


def test_mcp_module_run_metric_raises_cleanly_for_unknown_metric_name(tmp_path):
    make_session(tmp_path)
    module = make_mcp_module(tmp_path)

    with pytest.raises(ValueError, match="not_a_real_metric"):
        module.run_metric("not_a_real_metric", {}, session=None)
