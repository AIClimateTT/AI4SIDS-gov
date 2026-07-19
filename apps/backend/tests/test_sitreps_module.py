from pathlib import Path

import pytest
from sqlalchemy.orm import sessionmaker

from app.db import Base, make_engine
from app.modules.sitreps.ingest import ingest_sitrep_csv
from app.modules.sitreps.module import sitrep_module
from app.modules.survey123.ingest import ingest_csv
from app.modules.survey123.module import survey123_module

SITREP_FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample_sitrep_small.csv"
SURVEY123_FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample_small.csv"
CORPORATION = "diego_martin_regional_corporati"


def make_session(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


def test_sitrep_module_has_correct_name():
    assert sitrep_module.name == "sitreps"


def test_sitrep_module_ingest_raises_not_implemented():
    with pytest.raises(NotImplementedError, match="sitreps"):
        sitrep_module.ingest(SITREP_FIXTURE)


def test_sitrep_module_list_metrics_reports_module_as_sitreps():
    specs = sitrep_module.list_metrics()

    assert len(specs) == 9
    assert all(spec.module == "sitreps" for spec in specs)
    assert {spec.name for spec in specs} == {spec.name for spec in survey123_module.list_metrics()}


def test_sitrep_module_run_metric_only_counts_sitrep_rows(tmp_path):
    session = make_session(tmp_path)
    ingest_csv(SURVEY123_FIXTURE, session, salt="test-salt")
    ingest_sitrep_csv(SITREP_FIXTURE, CORPORATION, session)

    facts = sitrep_module.run_metric("incident_count", {}, session)

    assert facts[0].value == 3
    assert facts[0].citation.module == "sitreps"
    assert facts[0].citation.cid == "sitreps-incident_count-0"


def test_survey123_module_run_metric_only_counts_survey123_rows_when_sitreps_also_present(tmp_path):
    session = make_session(tmp_path)
    ingest_csv(SURVEY123_FIXTURE, session, salt="test-salt")
    ingest_sitrep_csv(SITREP_FIXTURE, CORPORATION, session)

    facts = survey123_module.run_metric("incident_count", {}, session)

    assert facts[0].value == 19
    assert facts[0].citation.module == "survey123"


def test_sitrep_module_run_metric_raises_for_unknown_metric(tmp_path):
    session = make_session(tmp_path)

    with pytest.raises(ValueError, match="not_a_real_metric"):
        sitrep_module.run_metric("not_a_real_metric", {}, session)
