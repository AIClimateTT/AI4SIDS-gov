from pathlib import Path

from app.modules.capture.csv_import import import_csv_rows, read_csv_bytes
from app.modules.capture.schemas import CaptureIncident, CaptureLog, CaptureWorkingSet

INCIDENTS = Path(__file__).parent.parent / "fixtures" / "sample_submission_incidents.csv"
LOGS = Path(__file__).parent.parent / "fixtures" / "sample_submission_logs.csv"


def test_reads_utf8_and_strips_a_bom():
    rows = read_csv_bytes(b"\xef\xbb\xbfRow ID,Date of Event\n1,2026-08-18\n")
    assert rows == [{"Row ID": "1", "Date of Event": "2026-08-18"}]


def test_imports_fixture_incidents_into_an_empty_working_set():
    rows = read_csv_bytes(INCIDENTS.read_bytes())
    working, errors = import_csv_rows(
        CaptureWorkingSet(), kind="incidents", rows=rows
    )

    assert errors == []
    assert [item.row_id for item in working.incidents] == ["1", "2", "3"]
    assert working.incidents[0].community == "Petit Valley"
    assert working.incidents[0].incident_type == "fallen_tree"
    assert working.incidents[0].event_date == "2023-06-27"
    assert working.incidents[1].estimated_damage_cost == 1500
    assert working.incidents[2].injuries_occurred is True
    assert working.incidents[2].injuries_count == 1
    assert "incident:1.community" in working.manual_fields


def test_replaces_an_existing_incident_with_the_same_row_id():
    previous = CaptureWorkingSet(
        incidents=[
            CaptureIncident(
                row_id="1",
                community="Old Town",
                incident_type="flooding_",
                event_date="2026-01-01",
            )
        ]
    )
    working, errors = import_csv_rows(
        previous,
        kind="incidents",
        rows=read_csv_bytes(INCIDENTS.read_bytes()),
    )

    assert errors == []
    assert working.incidents[0].community == "Petit Valley"
    assert working.incidents[0].incident_type == "fallen_tree"
    assert len(working.incidents) == 3


def test_skips_bad_incident_rows_without_aborting():
    rows = [
        {
            "Row ID": "1",
            "Date of Event": "not-a-date",
            "Community": "Petit Valley",
            "Incident Type": "flooding",
        },
        {
            "Row ID": "2",
            "Date of Event": "2026-08-18",
            "Community": "Maraval",
            "Incident Type": "fallen tree",
        },
    ]
    working, errors = import_csv_rows(CaptureWorkingSet(), kind="incidents", rows=rows)

    assert len(errors) == 1
    assert errors[0].row_number == 2
    assert "ISO date" in errors[0].reason
    assert [item.row_id for item in working.incidents] == ["2"]


def test_appends_logs_and_assigns_row_ids():
    previous = CaptureWorkingSet(
        logs=[CaptureLog(row_id="1", category="other", statement="Already captured")]
    )
    working, errors = import_csv_rows(
        previous, kind="logs", rows=read_csv_bytes(LOGS.read_bytes())
    )

    assert errors == []
    assert working.logs[0].statement == "Already captured"
    assert working.logs[1].category == "activity"
    assert working.logs[2].item == "sandbags"
    assert working.logs[2].quantity == 200
    assert {row.row_id for row in working.logs} == {"1", "2", "3", "4", "5", "6"}
    assert "log:2.statement" in working.manual_fields
