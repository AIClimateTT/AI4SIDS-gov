from datetime import datetime

from sqlalchemy.orm import sessionmaker

from app.db import Base, make_engine
from app.modules.sitreps.ingest import ingest_submission
from app.modules.sitreps.module import sitrep_module
from app.modules.sitreps.store import create_event
from app.modules.survey123.metrics import apply_common_filters
from app.modules.survey123.models import FieldObservation
from sqlalchemy import select

CORP = "diego_martin_regional_corporati"


def make_session(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _ingest(db, *, as_at: datetime, row_id: str, summary: str, event_id: int):
    return ingest_submission(
        db,
        corporation=CORP,
        as_at=as_at,
        event_id=event_id,
        alert_level="yellow",
        present_activity=None,
        situation_overview=None,
        source_name="test",
        incident_rows=[
            {
                "Row ID": row_id,
                "Community": "Petit Valley",
                "Incident Type": "flooding",
                "Incident Summary": summary,
                "Date of Event": "2026-08-18",
            }
        ],
        log_rows=[],
        structured_defaults=True,
    )


def test_incident_count_can_scope_to_one_submission(tmp_path):
    db = make_session(tmp_path)
    event = create_event(
        db,
        corporation=CORP,
        title="Flood",
        hazard_type="flood",
        started_at=datetime(2026, 8, 18),
    )
    first = _ingest(db, as_at=datetime(2026, 8, 18, 10), row_id="1", summary="A", event_id=event.id)
    second = _ingest(db, as_at=datetime(2026, 8, 18, 16), row_id="2", summary="B", event_id=event.id)

    all_facts = sitrep_module.run_metric(
        "incident_count", {"corporation": CORP, "date_from": "2026-08-01", "date_to": "2026-08-31"}, db
    )
    one = sitrep_module.run_metric(
        "incident_count",
        {"corporation": CORP, "submission_id": second.submission_id},
        db,
    )
    db.close()
    assert all_facts[0].value == 2
    assert one[0].value == 1
    assert f"submission_id={second.submission_id}" in one[0].citation.query_ref


def test_submission_id_is_ignored_when_the_model_has_no_such_column():
    stmt = apply_common_filters(select(FieldObservation), {"submission_id": 99}, FieldObservation)
    compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "submission_id" not in compiled
