import csv
from datetime import datetime
from pathlib import Path

from app.modules.sitreps.parse import (
    INCIDENT_PII_COLUMNS,
    RowError,
    parse_incident_row,
    parse_log_row,
)

FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample_submission_incidents.csv"
LOGS_FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample_submission_logs.csv"


def read_fixture_rows() -> list[dict[str, str]]:
    with open(FIXTURE, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_parses_a_well_formed_row():
    row = read_fixture_rows()[0]

    fields, error = parse_incident_row(row, 1)

    assert error is None
    assert fields["row_id"] == "1"
    assert fields["community"] == "Petit Valley"
    assert fields["street"] == "Cameron Road"
    assert fields["incident_type"] == "fallen_tree"
    assert fields["event_date"] == datetime(2023, 6, 27)
    assert fields["action_taken"] == "DMU removed fallen tree."
    assert fields["follow_up_flags"] == {
        "relief_supplied": True,
        "forwarded_to_agency": False,
        "further_assessment_required": False,
        "other": False,
    }


def test_never_returns_pii_fields():
    rows = read_fixture_rows()

    for number, row in enumerate(rows, start=1):
        fields, error = parse_incident_row(row, number)
        assert error is None
        for key, value in fields.items():
            assert "Cupidore" not in str(value)
            assert "793-9056" not in str(value)
    assert INCIDENT_PII_COLUMNS == ["Name of Person", "Contact Information"]


def test_parses_counts_and_costs():
    row = read_fixture_rows()[2]

    fields, error = parse_incident_row(row, 3)

    assert error is None
    assert fields["injuries_occurred"] is True
    assert fields["injuries_count"] == 1
    assert fields["special_needs_occupants"] == 2
    assert int(fields["estimated_damage_cost"]) == 25000


def test_missing_row_id_is_a_row_error_not_an_exception():
    row = dict(read_fixture_rows()[0])
    row["Row ID"] = "  "

    fields, error = parse_incident_row(row, 7)

    assert fields is None
    assert error == RowError(row_number=7, reason="Row ID is required")


def test_non_numeric_row_id_is_accepted():
    # Corps number rows as "1a" / "12b" when they split an incident. This must
    # not be an error; the old int() coercion was the bug that aborted batches.
    row = dict(read_fixture_rows()[0])
    row["Row ID"] = "12b"

    fields, error = parse_incident_row(row, 1)

    assert error is None
    assert fields["row_id"] == "12b"


def test_missing_date_of_event_is_a_row_error():
    row = dict(read_fixture_rows()[0])
    row["Date of Event"] = ""

    fields, error = parse_incident_row(row, 4)

    assert fields is None
    assert error == RowError(row_number=4, reason="Date of Event is required")


def test_unparseable_date_of_event_is_a_row_error():
    row = dict(read_fixture_rows()[0])
    row["Date of Event"] = "27/06/2023"

    fields, error = parse_incident_row(row, 5)

    assert fields is None
    assert error == RowError(
        row_number=5, reason="Date of Event is not an ISO date: '27/06/2023'"
    )


def test_unmapped_incident_type_falls_through_to_raw():
    row = dict(read_fixture_rows()[0])
    row["Incident Type"] = "Roofing Damages"

    fields, error = parse_incident_row(row, 1)

    assert error is None
    assert fields["raw_incident_type"] == "Roofing Damages"


def read_log_rows() -> list[dict[str, str]]:
    with open(LOGS_FIXTURE, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_parses_a_log_row_with_no_quantity():
    fields, error = parse_log_row(read_log_rows()[0], 1)

    assert error is None
    assert fields["category"] == "activity"
    assert fields["statement"] == "Tree cutting team on stand by"
    assert fields["item"] is None
    assert fields["quantity"] is None
    assert fields["status"] == "on_standby"


def test_parses_a_log_row_with_a_quantity():
    fields, error = parse_log_row(read_log_rows()[1], 2)

    assert error is None
    assert fields["item"] == "sandbags"
    assert fields["quantity"] == 200
    assert fields["unit"] == "bags"


def test_missing_statement_is_a_row_error():
    row = dict(read_log_rows()[0])
    row["Statement"] = ""

    fields, error = parse_log_row(row, 3)

    assert fields is None
    assert error == RowError(row_number=3, reason="Statement is required")


def test_unknown_category_is_a_row_error():
    row = dict(read_log_rows()[0])
    row["Category"] = "logistics"

    fields, error = parse_log_row(row, 4)

    assert fields is None
    assert error.row_number == 4
    assert "logistics" in error.reason


def test_unparseable_quantity_is_a_row_error_not_a_silent_none():
    # A quantity that silently became None would drop a citable figure from the
    # report with no trace. That is the exact failure this system exists to stop.
    row = dict(read_log_rows()[1])
    row["Quantity"] = "about 200"

    fields, error = parse_log_row(row, 5)

    assert fields is None
    assert error == RowError(
        row_number=5, reason="Quantity is not a number: 'about 200'"
    )


def test_unknown_status_is_a_row_error():
    row = dict(read_log_rows()[0])
    row["Status"] = "maybe"

    fields, error = parse_log_row(row, 6)

    assert fields is None
    assert error.row_number == 6
    assert "maybe" in error.reason


def test_nan_quantity_is_a_row_error_not_a_silent_nan():
    # A NaN in SituationLog.quantity would poison a later cross-corporation sum
    # with no trace of which row caused it.
    row = dict(read_log_rows()[1])
    row["Quantity"] = "nan"

    fields, error = parse_log_row(row, 7)

    assert fields is None
    assert error == RowError(
        row_number=7, reason="Quantity is not a finite number: 'nan'"
    )


def test_inf_quantity_is_a_row_error_not_a_silent_inf():
    row = dict(read_log_rows()[1])
    row["Quantity"] = "inf"

    fields, error = parse_log_row(row, 8)

    assert fields is None
    assert error == RowError(
        row_number=8, reason="Quantity is not a finite number: 'inf'"
    )


def test_overflowing_quantity_is_a_row_error_not_a_silent_inf():
    # float("1e400") does not raise; it silently overflows to inf.
    row = dict(read_log_rows()[1])
    row["Quantity"] = "1e400"

    fields, error = parse_log_row(row, 9)

    assert fields is None
    assert error == RowError(
        row_number=9, reason="Quantity is not a finite number: '1e400'"
    )
