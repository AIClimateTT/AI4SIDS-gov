from pathlib import Path

import pytest
from sqlalchemy.orm import sessionmaker

from app.db import Base, make_engine
from app.modules.sitreps.module import sitrep_module
from app.modules.survey123.module import survey123_module

SITREP_FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample_sitrep_small.csv"


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

    assert len(specs) == 8
    assert all(spec.module == "sitreps" for spec in specs)
    assert {spec.name for spec in specs} == {
        spec.name for spec in survey123_module.list_metrics()
    } - {"data_coverage"}


def test_sitrep_module_run_metric_raises_for_unknown_metric(tmp_path):
    session = make_session(tmp_path)

    with pytest.raises(ValueError, match="not_a_real_metric"):
        sitrep_module.run_metric("not_a_real_metric", {}, session)


def test_sitreps_does_not_advertise_a_metric_that_returns_nothing():
    # data_coverage measures validation status, which corp SITREP rows do not
    # have. Advertising it lets a template request a metric that can only ever
    # yield zero facts -- and a report with zero facts is marked "ok".
    from app.core.registry import ensure_default_modules_registered, get_module, reset_registry

    reset_registry()
    ensure_default_modules_registered()

    names = {spec.name for spec in get_module("sitreps").list_metrics()}

    assert "data_coverage" not in names


def test_sitrep_module_run_metric_still_serves_data_coverage(tmp_path):
    # list_metrics stops advertising it, but a previously stored template
    # naming it must not crash -- run_metric still serves it, returning [].
    session = make_session(tmp_path)

    facts = sitrep_module.run_metric("data_coverage", {}, session)

    assert facts == []
