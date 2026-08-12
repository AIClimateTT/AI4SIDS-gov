import csv
from datetime import datetime
from decimal import Decimal
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
    assert fields["incident_type"] == "unmapped"
    assert fields["raw_incident_type"] == "Roofing Damages"


def test_a_hand_typed_flooding_is_understood_as_a_home_affecting_type():
    # The reproduction: 20 corp rows typed "Flooding" were routed through
    # survey123's export vocabulary, became incident_type "unmapped", and
    # HOME_AFFECTING_INCIDENT_TYPES stopped matching —
    #   incident_count: 20 {'unmapped': 20}
    #   homes_affected_count: 0
    # "20 flooding incidents, 0 homes affected."
    from app.modules.survey123.metrics import HOME_AFFECTING_INCIDENT_TYPES

    row = dict(read_fixture_rows()[0])
    row["Incident Type"] = "Flooding"

    fields, error = parse_incident_row(row, 1)

    assert error is None
    assert fields["incident_type"] == "flooding_"
    assert fields["incident_type"] in HOME_AFFECTING_INCIDENT_TYPES
    # A recognised synonym is not an unmapped value: ingest must not report it
    # back to the corp as a cell it could not read.
    assert fields["raw_incident_type"] is None


def test_every_corp_incident_type_synonym_maps_to_the_metric_vocabulary():
    from app.modules.survey123.normalize import CANONICAL_INCIDENT_TYPES

    expected = {
        "Flooding": "flooding_",
        "flood": "flooding_",
        "Roof Damage": "blown_off_roof",
        "Blown Off Roof": "blown_off_roof",
        "Fallen Tree": "fallen_tree",
        "Land Slide": "landslide",
    }

    for typed, canonical in expected.items():
        row = dict(read_fixture_rows()[0])
        row["Incident Type"] = typed
        fields, error = parse_incident_row(row, 1)

        assert error is None, typed
        assert fields["incident_type"] == canonical, typed
        assert canonical in CANONICAL_INCIDENT_TYPES, typed


def test_corp_incident_type_synonyms_tolerate_case_and_whitespace():
    for typed in ("  FLOODING  ", "flOOd", "blown   off\troof", "  Land  Slide "):
        row = dict(read_fixture_rows()[0])
        row["Incident Type"] = typed
        fields, error = parse_incident_row(row, 1)

        assert error is None, typed
        assert fields["incident_type"] != "unmapped", typed


def test_a_canonical_export_value_still_normalises_unchanged():
    row = dict(read_fixture_rows()[0])
    row["Incident Type"] = "flooding_"

    fields, error = parse_incident_row(row, 1)

    assert error is None
    assert fields["incident_type"] == "flooding_"


def test_the_survey123_normaliser_is_left_alone():
    # The Survey123 export path depends on its exact vocabulary; the synonyms
    # are a corp-entry concern only.
    from app.modules.survey123.normalize import normalize_incident_type

    assert normalize_incident_type("Flooding") == ("unmapped", "Flooding")


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


def _incident_row(**overrides) -> dict:
    row = {
        "Row ID": "1",
        "Incident Type": "fire",
        "Date of Event": "2023-06-27",
        "Injuries Occurred": "False",
        "Deaths Occurred": "False",
        "Relief Supplied": "False",
        "Forwarded To Agency": "False",
        "Further Assessment Required": "False",
        "Other Follow Up": "False",
    }
    row.update(overrides)
    return row


def test_currency_formatted_damage_cost_parses():
    # What a person actually types into a spreadsheet.
    fields, error = parse_incident_row(_incident_row(**{"Estimated Damage Cost": "$12,500"}), 1)

    assert error is None
    assert int(fields["estimated_damage_cost"]) == 12500


def test_unparseable_damage_cost_is_a_row_error_not_a_silent_none():
    # Previously stored None, so the report said TTD 0 with no trace.
    fields, error = parse_incident_row(_incident_row(**{"Estimated Damage Cost": "about ten grand"}), 4)

    assert fields is None
    assert error == RowError(
        row_number=4, reason="Estimated Damage Cost is not a number: 'about ten grand'"
    )


def test_yes_and_y_are_accepted_as_true():
    # Previously coerced to False, silently zeroing relief counts.
    fields, error = parse_incident_row(
        _incident_row(**{"Injuries Occurred": "Yes", "Relief Supplied": "Y"}), 1
    )

    assert error is None
    assert fields["injuries_occurred"] is True
    assert fields["follow_up_flags"]["relief_supplied"] is True


def test_no_and_zero_are_accepted_as_false():
    fields, error = parse_incident_row(
        _incident_row(**{"Injuries Occurred": "No", "Deaths Occurred": "0"}), 1
    )

    assert error is None
    assert fields["injuries_occurred"] is False
    assert fields["deaths_occurred"] is False


def test_an_unrecognised_boolean_is_a_row_error():
    fields, error = parse_incident_row(_incident_row(**{"Injuries Occurred": "maybe"}), 6)

    assert fields is None
    assert error.row_number == 6
    assert "Injuries Occurred" in error.reason


def test_a_non_numeric_count_is_a_row_error():
    fields, error = parse_incident_row(_incident_row(**{"Injuries Count": "two"}), 7)

    assert fields is None
    assert error == RowError(row_number=7, reason="Injuries Count is not a whole number: 'two'")


def test_empty_cells_are_not_errors():
    # Blank must stay permissive — a corp leaves cells empty constantly.
    fields, error = parse_incident_row(
        _incident_row(**{"Estimated Damage Cost": "", "Injuries Count": "", "Injuries Occurred": ""}),
        1,
    )

    assert error is None
    assert fields["estimated_damage_cost"] is None
    assert fields["injuries_count"] is None
    assert fields["injuries_occurred"] is False


def test_dollar_and_grouped_thousands_still_parse():
    # Guard the intended cases: an unambiguous thousands separator must keep
    # working, or the fix for the ambiguous cases below would be too strict.
    fields, error = parse_incident_row(_incident_row(**{"Estimated Damage Cost": "$12,500"}), 1)

    assert error is None
    assert int(fields["estimated_damage_cost"]) == 12500


def test_grouped_thousands_with_decimal_still_parses():
    fields, error = parse_incident_row(_incident_row(**{"Estimated Damage Cost": "1,200.50"}), 1)

    assert error is None
    assert fields["estimated_damage_cost"] == Decimal("1200.50")


def test_ambiguous_comma_as_decimal_separator_is_a_row_error():
    # "12,5" read as European decimal notation means 12.5. Stripping the comma
    # would silently produce 125 -- a 10x-inflated, unflagged, plausible-looking
    # number reaching a Minister's report with no trace. That is worse than
    # rejecting the row, so this must be a RowError, not a guess.
    fields, error = parse_incident_row(_incident_row(**{"Estimated Damage Cost": "12,5"}), 1)

    assert fields is None
    assert error == RowError(row_number=1, reason="Estimated Damage Cost is not a number: '12,5'")


def test_european_grouping_with_comma_decimal_is_a_row_error():
    # "12.500,50" in European formatting means 12500.50. Naively treating every
    # comma as a thousands separator would silently produce 12.50050 -- roughly
    # 1000x wrong and unflagged. Reject rather than guess.
    fields, error = parse_incident_row(_incident_row(**{"Estimated Damage Cost": "12.500,50"}), 1)

    assert fields is None
    assert error == RowError(
        row_number=1, reason="Estimated Damage Cost is not a number: '12.500,50'"
    )


def test_wrongly_grouped_thousands_is_a_row_error():
    # "1,2345" has a comma but not in a 3-digit group, so it is not an
    # unambiguous thousands separator. Stripping it anyway would silently
    # produce 12345 with no trace it was ever ambiguous.
    fields, error = parse_incident_row(_incident_row(**{"Estimated Damage Cost": "1,2345"}), 1)

    assert fields is None
    assert error == RowError(
        row_number=1, reason="Estimated Damage Cost is not a number: '1,2345'"
    )


def test_ambiguous_comma_in_an_integer_cell_is_a_row_error():
    # Same rule applies to parse_corp_int: "1,2" silently stripped would
    # produce 12, a wrong count reaching the report with no trace.
    fields, error = parse_incident_row(_incident_row(**{"Injuries Count": "1,2"}), 1)

    assert fields is None
    assert error == RowError(row_number=1, reason="Injuries Count is not a whole number: '1,2'")
