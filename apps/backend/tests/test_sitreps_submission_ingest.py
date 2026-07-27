import csv
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import sessionmaker

from app.db import Base, make_engine
from app.modules.sitreps.ingest import ingest_submission
from app.modules.sitreps.models import SitrepIncident, SituationLog, Submission
from app.modules.sitreps.store import create_event

INCIDENTS = Path(__file__).parent.parent / "fixtures" / "sample_submission_incidents.csv"
LOGS = Path(__file__).parent.parent / "fixtures" / "sample_submission_logs.csv"
CORP = "diego_martin_regional_corporati"


def make_session(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def write_csv(tmp_path, name, header, rows):
    path = Path(tmp_path) / name
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
    return path


def test_ingests_both_files_under_one_submission(tmp_path):
    session = make_session(tmp_path)

    result = ingest_submission(
        session,
        corporation=CORP,
        as_at=datetime(2023, 6, 30, 16, 0),
        alert_level="discontinued",
        present_activity="Adverse Weather Alert",
        situation_overview="Heavy rainfall affected the Borough.",
        incidents_path=INCIDENTS,
        logs_path=LOGS,
    )

    assert result.incidents_read == 3
    assert result.incidents_inserted == 3
    assert result.logs_read == 5
    assert result.logs_inserted == 5
    assert result.row_errors == []

    submission = session.query(Submission).one()
    assert submission.id == result.submission_id
    assert submission.situation_overview == "Heavy rainfall affected the Borough."
    assert session.query(SitrepIncident).count() == 3
    assert session.query(SituationLog).count() == 5


def test_either_file_may_be_omitted(tmp_path):
    session = make_session(tmp_path)

    result = ingest_submission(
        session, corporation=CORP, as_at=datetime(2023, 5, 5, 15, 0), logs_path=LOGS
    )

    assert result.incidents_read == 0
    assert result.logs_read == 5
    assert session.query(SitrepIncident).count() == 0


def test_never_writes_pii(tmp_path):
    session = make_session(tmp_path)

    result = ingest_submission(
        session, corporation=CORP, as_at=datetime(2023, 6, 30), incidents_path=INCIDENTS
    )

    assert result.pii_columns_dropped == ["Name of Person", "Contact Information"]
    for incident in session.query(SitrepIncident).all():
        for value in vars(incident).values():
            assert "Cupidore" not in str(value)
            assert "793-9056" not in str(value)


def test_bad_rows_are_reported_and_good_rows_still_land(tmp_path):
    session = make_session(tmp_path)
    path = write_csv(
        tmp_path,
        "mixed.csv",
        ["Row ID", "Incident Type", "Date of Event", "Community"],
        [
            ["1", "fallen_tree", "2023-06-27", "Petit Valley"],
            ["", "landslide", "2023-06-27", "Maraval"],
            ["3", "flooding_", "27/06/2023", "Paramin"],
            ["4", "fire", "2023-06-28", "Diamond Vale"],
        ],
    )

    result = ingest_submission(
        session, corporation=CORP, as_at=datetime(2023, 6, 30), incidents_path=path
    )

    assert result.incidents_read == 4
    assert result.incidents_inserted == 2
    assert [(e.row_number, e.file) for e in result.row_errors] == [
        (2, "incidents"),
        (3, "incidents"),
    ]
    assert session.query(SitrepIncident).count() == 2


def test_reuploading_a_cumulative_table_supersedes_rather_than_duplicates(tmp_path):
    session = make_session(tmp_path)
    event = create_event(
        session, corporation=CORP, title="Storm", hazard_type="wind",
        started_at=datetime(2023, 6, 27),
    )
    header = ["Row ID", "Incident Type", "Date of Event", "Incident Summary"]

    first = write_csv(
        tmp_path, "first.csv", header,
        [["1", "fallen_tree", "2023-06-27", "Original summary"]],
    )
    ingest_submission(
        session, corporation=CORP, as_at=datetime(2023, 6, 27), event_id=event.id,
        incidents_path=first,
    )

    second = write_csv(
        tmp_path, "second.csv", header,
        [
            ["1", "fallen_tree", "2023-06-27", "Corrected summary"],
            ["2", "landslide", "2023-06-28", "New row"],
        ],
    )
    result = ingest_submission(
        session, corporation=CORP, as_at=datetime(2023, 6, 28), event_id=event.id,
        incidents_path=second,
    )

    assert result.incidents_inserted == 1
    assert result.incidents_updated == 1
    assert session.query(SitrepIncident).count() == 2
    row_one = (
        session.query(SitrepIncident).filter(SitrepIncident.row_id == "1").one()
    )
    assert row_one.incident_summary == "Corrected summary"


def test_event_less_submissions_do_not_supersede_each_other(tmp_path):
    session = make_session(tmp_path)
    header = ["Row ID", "Incident Type", "Date of Event"]
    path = write_csv(tmp_path, "routine.csv", header, [["1", "fire", "2024-01-05"]])

    ingest_submission(session, corporation=CORP, as_at=datetime(2024, 1, 5), incidents_path=path)
    ingest_submission(session, corporation=CORP, as_at=datetime(2024, 1, 6), incidents_path=path)

    assert session.query(SitrepIncident).count() == 2


def test_logs_are_never_superseded(tmp_path):
    session = make_session(tmp_path)
    event = create_event(
        session, corporation=CORP, title="Storm", hazard_type="wind",
        started_at=datetime(2023, 6, 27),
    )

    ingest_submission(
        session, corporation=CORP, as_at=datetime(2023, 6, 27), event_id=event.id,
        logs_path=LOGS,
    )
    ingest_submission(
        session, corporation=CORP, as_at=datetime(2023, 6, 28), event_id=event.id,
        logs_path=LOGS,
    )

    assert session.query(SituationLog).count() == 10
    assert session.query(Submission).count() == 2


def test_sequence_no_is_returned_for_report_numbering(tmp_path):
    session = make_session(tmp_path)
    event = create_event(
        session, corporation=CORP, title="Storm", hazard_type="wind",
        started_at=datetime(2023, 6, 27),
    )

    ingest_submission(session, corporation=CORP, as_at=datetime(2023, 6, 27), event_id=event.id)
    second = ingest_submission(
        session, corporation=CORP, as_at=datetime(2023, 6, 28), event_id=event.id
    )

    assert second.sequence_no == 2
