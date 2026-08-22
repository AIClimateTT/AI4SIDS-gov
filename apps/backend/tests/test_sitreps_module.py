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

    assert all(spec.module == "sitreps" for spec in specs)
    assert {spec.name for spec in specs} == (
        {spec.name for spec in survey123_module.list_metrics()} - {"data_coverage"}
    ) | {"relief_stock_summary", "activity_log"}


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


def make_sitrep_rows(session, count: int, *, incident_type: str, raw: str | None):
    from datetime import datetime

    from app.modules.sitreps.models import Event, SitrepIncident, Submission

    event = Event(
        corporation="arima_borough_corporation",
        title="June Flooding",
        hazard_type="flood",
        started_at=datetime(2024, 6, 1),
        created_at=datetime(2024, 6, 1),
    )
    session.add(event)
    session.flush()
    submission = Submission(
        corporation="arima_borough_corporation",
        event_id=event.id,
        as_at=datetime(2024, 6, 2),
        sequence_no=1,
        ingested_at=datetime(2024, 6, 2),
    )
    session.add(submission)
    session.flush()
    for index in range(count):
        session.add(
            SitrepIncident(
                submission_id=submission.id,
                corporation="arima_borough_corporation",
                event_id=event.id,
                row_id=str(index + 1),
                community="Arima",
                incident_type=incident_type,
                raw_incident_type=raw,
                event_date=datetime(2024, 6, 1),
                follow_up_flags={},
                ingested_at=datetime(2024, 6, 2),
            )
        )
    session.commit()


def test_unmapped_incident_type_rows_raise_a_gap_the_report_can_state(tmp_path):
    # 20 rows typed "Flooding" produced incident_count 20 {'unmapped': 20} and
    # homes_affected_count 0, with no caveat anywhere: "20 flooding incidents,
    # 0 homes affected". Incident type was the only unreadable corp cell that
    # degraded silently, and the only one feeding a selection predicate.
    session = make_session(tmp_path)
    make_sitrep_rows(session, 20, incident_type="unmapped", raw="Volcanic Eruption")

    counted = sitrep_module.run_metric("incident_count", {}, session)[0]
    homes = sitrep_module.run_metric("homes_affected_count", {}, session)[0]

    assert counted.value == 20
    assert any("20 rows" in gap for gap in counted.gaps)
    assert any("Volcanic Eruption" in gap for gap in counted.gaps)
    assert homes.value == 0
    assert any("20 rows" in gap for gap in homes.gaps)


def test_a_breakdown_never_shows_a_minister_the_word_unmapped(tmp_path):
    session = make_session(tmp_path)
    make_sitrep_rows(session, 3, incident_type="unmapped", raw="Volcanic Eruption")

    fact = sitrep_module.run_metric("incident_count", {}, session)[0]

    assert fact.breakdown == {"Volcanic Eruption": 3}
    assert "unmapped" not in fact.breakdown


def test_an_unmapped_row_with_no_raw_value_gets_a_readable_label(tmp_path):
    session = make_session(tmp_path)
    make_sitrep_rows(session, 2, incident_type="unmapped", raw=None)

    fact = sitrep_module.run_metric("incident_count", {}, session)[0]

    assert fact.breakdown == {"(unrecognised incident type)": 2}


def test_recognised_incident_types_raise_no_gap(tmp_path):
    session = make_session(tmp_path)
    make_sitrep_rows(session, 4, incident_type="flooding_", raw=None)

    counted = sitrep_module.run_metric("incident_count", {}, session)[0]
    homes = sitrep_module.run_metric("homes_affected_count", {}, session)[0]

    assert counted.gaps == []
    assert homes.gaps == []
    assert homes.value == 4


def test_a_metric_gap_reaches_the_fact_tables_data_gaps(tmp_path):
    # The caveat is only worth computing if it reaches the report; the prompt
    # points the model at FactTable.gaps and the renderer prints them.
    from app.core.contracts import DataRequirement, NarrationConfig, RenderConfig, Template
    from app.core.engine import assemble_fact_table
    from app.core.registry import ensure_default_modules_registered, reset_registry

    reset_registry()
    ensure_default_modules_registered()

    session = make_session(tmp_path)
    make_sitrep_rows(session, 20, incident_type="unmapped", raw="Volcanic Eruption")

    template = Template(
        name="t",
        title="T",
        description="d",
        params=[],
        data_requirements=[],
        narration=NarrationConfig.of("", output_sections=[]),
        render=RenderConfig(),
    )
    fact_table = assemble_fact_table(
        template,
        {},
        session,
        "req-1",
        [
            DataRequirement(module="sitreps", metric="incident_count"),
            DataRequirement(module="sitreps", metric="homes_affected_count"),
        ],
    )

    assert any("incident_count" in gap and "20 rows" in gap for gap in fact_table.gaps)
    assert any(
        "homes_affected_count" in gap and "20 rows" in gap for gap in fact_table.gaps
    )


def test_sitrep_module_run_metric_still_serves_data_coverage(tmp_path):
    # list_metrics stops advertising it, but a previously stored template
    # naming it must not crash -- run_metric still serves it, returning [].
    session = make_session(tmp_path)

    facts = sitrep_module.run_metric("data_coverage", {}, session)

    assert facts == []
