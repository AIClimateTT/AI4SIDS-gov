from datetime import datetime

from sqlalchemy.orm import sessionmaker

from app.db import Base, make_engine
from app.modules.sitreps.ingest import ingest_submission
from app.modules.sitreps.models import SitrepIncident, SituationLog, Submission
from app.modules.sitreps.store import create_event

CORP = "diego_martin_regional_corporati"


def make_session(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_ingests_in_memory_rows_without_a_csv(tmp_path):
    session = make_session(tmp_path)
    event = create_event(
        session,
        corporation=CORP,
        title="Storm",
        hazard_type="wind",
        started_at=datetime(2026, 8, 18),
    )

    result = ingest_submission(
        session,
        corporation=CORP,
        as_at=datetime(2026, 8, 18, 14, 0),
        event_id=event.id,
        alert_level="yellow",
        source_name="conversation",
        incident_rows=[
            {
                "Row ID": "1",
                "Community": "Petit Valley",
                "Incident Type": "flooding",
                "Date of Event": "2026-08-18",
                "Incident Summary": "5 houses flooded",
                "Injuries Count": "0",
                "Deaths Count": "0",
            }
        ],
        log_rows=[
            {
                "Category": "resource",
                "Statement": "200 sandbags remaining at depot",
                "Item": "sandbags",
                "Quantity": "200",
                "Unit": "bags",
                "Status": "available",
            }
        ],
        structured_defaults=True,
    )

    assert result.incidents_inserted == 1
    assert result.logs_inserted == 1
    assert result.row_errors == []
    incident = session.query(SitrepIncident).one()
    assert incident.incident_type == "flooding_"
    assert incident.community == "Petit Valley"
    log = session.query(SituationLog).one()
    assert log.quantity == 200
    assert session.get(Submission, result.submission_id).source_file == "conversation"


def test_structured_defaults_fill_date_and_casualty_flags(tmp_path):
    session = make_session(tmp_path)
    event = create_event(
        session,
        corporation=CORP,
        title="Storm",
        hazard_type="flood",
        started_at=datetime(2026, 8, 18),
    )

    result = ingest_submission(
        session,
        corporation=CORP,
        as_at=datetime(2026, 8, 18, 16, 30),
        event_id=event.id,
        incident_rows=[
            {
                "Row ID": "1",
                "Incident Type": "fallen tree",
                "Incident Summary": "Tree on the road",
                "Injuries Count": "2",
            }
        ],
        structured_defaults=True,
    )

    assert result.row_errors == []
    incident = session.query(SitrepIncident).one()
    assert incident.event_date.date().isoformat() == "2026-08-18"
    assert incident.injuries_occurred is True
    assert incident.injuries_count == 2
    assert incident.deaths_occurred is False
    assert incident.follow_up_flags["relief_supplied"] is False


def test_csv_path_stays_strict_when_date_is_missing(tmp_path):
    session = make_session(tmp_path)
    from pathlib import Path
    import csv

    path = Path(tmp_path) / "no-date.csv"
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Row ID", "Incident Type", "Incident Summary"])
        writer.writerow(["1", "fire", "Shed burned"])

    result = ingest_submission(
        session, corporation=CORP, as_at=datetime(2026, 8, 18), incidents_path=path
    )

    assert result.incidents_inserted == 0
    assert result.row_errors[0].reason.startswith("Date of Event")
