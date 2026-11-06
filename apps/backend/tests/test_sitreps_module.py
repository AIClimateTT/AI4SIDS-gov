from pathlib import Path

import pytest
from sqlalchemy.orm import sessionmaker

from app.core.metrics import run_metric
from app.db import Base, make_engine

SITREP_FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample_sitrep_small.csv"


def make_session(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


def test_sitrep_module_run_metric_raises_for_unknown_metric(tmp_path):
    session = make_session(tmp_path)

    with pytest.raises(ValueError, match="not_a_real_metric"):
        run_metric("sitreps", "not_a_real_metric", {}, session)


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

    counted = run_metric("sitreps", "incident_count", {}, session)[0]
    homes = run_metric("sitreps", "homes_affected_count", {}, session)[0]

    assert counted.value == 20
    assert any("20 rows" in gap for gap in counted.gaps)
    assert any("Volcanic Eruption" in gap for gap in counted.gaps)
    assert homes.value == 0
    assert any("20 rows" in gap for gap in homes.gaps)


def test_a_breakdown_never_shows_a_minister_the_word_unmapped(tmp_path):
    session = make_session(tmp_path)
    make_sitrep_rows(session, 3, incident_type="unmapped", raw="Volcanic Eruption")

    fact = run_metric("sitreps", "incident_count", {}, session)[0]

    assert fact.breakdown == {"Volcanic Eruption": 3}
    assert "unmapped" not in fact.breakdown


def test_an_unmapped_row_with_no_raw_value_gets_a_readable_label(tmp_path):
    session = make_session(tmp_path)
    make_sitrep_rows(session, 2, incident_type="unmapped", raw=None)

    fact = run_metric("sitreps", "incident_count", {}, session)[0]

    assert fact.breakdown == {"(unrecognised incident type)": 2}


def test_recognised_incident_types_raise_no_gap(tmp_path):
    session = make_session(tmp_path)
    make_sitrep_rows(session, 4, incident_type="flooding_", raw=None)

    counted = run_metric("sitreps", "incident_count", {}, session)[0]
    homes = run_metric("sitreps", "homes_affected_count", {}, session)[0]

    assert counted.gaps == []
    assert homes.gaps == []
    assert homes.value == 4


def test_a_metric_gap_reaches_the_fact_tables_data_gaps(tmp_path):
    # The caveat is only worth computing if it reaches the report; the prompt
    # points the model at FactTable.gaps and the renderer prints them.
    from app.core.contracts import DataRequirement, NarrationConfig, RenderConfig, Template
    from app.core.engine import assemble_fact_table


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

    facts = run_metric("sitreps", "data_coverage", {}, session)

    assert facts == []
