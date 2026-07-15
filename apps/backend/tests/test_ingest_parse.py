import logging

from app.modules.survey123.ingest import is_duplicate_marker, parse_row


def test_parse_row_never_includes_pii_values():
    row = {
        "GlobalID": "GUID-TEST",
        "ObjectID": "1",
        "Name of Person": "Real Name",
        "Contact Information": "8681234567",
        "Identification Card Number": "19900101999",
        "Name of Second Person": "Second Name",
        "Second Contact Information": "8687654321",
        "Second Identification Card Number": "19900101998",
        "Please list the names of the occupants and their relation": "Real Name (self)",
    }

    result = parse_row(row, salt="test-salt")

    serialized = " ".join(str(v) for v in result.values())
    for pii_value in [
        "Real Name",
        "8681234567",
        "19900101999",
        "Second Name",
        "8687654321",
        "19900101998",
    ]:
        assert pii_value not in serialized


def test_parse_row_maps_known_corporation_case_insensitively():
    row = {"GlobalID": "G1", "ObjectID": "1", "Municipal Boundary": "Sangre_Grande_Regional_Corporat"}

    result = parse_row(row, salt="s")

    assert result["corporation"] == "sangre_grande_regional_corporat"
    assert result["raw_corporation"] is None


def test_parse_row_blank_corporation_is_none():
    row = {"GlobalID": "G1", "ObjectID": "1", "Municipal Boundary": ""}

    result = parse_row(row, salt="s")

    assert result["corporation"] is None
    assert result["raw_corporation"] is None


def test_parse_row_unmapped_corporation_preserves_raw(caplog):
    row = {"GlobalID": "G1", "ObjectID": "1", "Municipal Boundary": "Unknown_Corp_Typo"}

    with caplog.at_level(logging.WARNING):
        result = parse_row(row, salt="s")

    assert result["corporation"] == "unmapped"
    assert result["raw_corporation"] == "Unknown_Corp_Typo"
    assert "Unknown_Corp_Typo" in caplog.text


def test_parse_row_occupants_other_with_numeric_overflow():
    row = {
        "GlobalID": "G1",
        "ObjectID": "1",
        "Household Occupants": "other",
        "If more than 6 persons - Household Occupants": "9",
    }

    result = parse_row(row, salt="s")

    assert result["occupants_count"] == 9


def test_parse_row_occupants_other_with_text_overflow():
    row = {
        "GlobalID": "G1",
        "ObjectID": "1",
        "Household Occupants": "other",
        "If more than 6 persons - Household Occupants": "12 persons",
    }

    result = parse_row(row, salt="s")

    assert result["occupants_count"] == 12


def test_parse_row_dedup_hash_stable_for_same_id_and_salt():
    row_a = {"GlobalID": "G1", "ObjectID": "1", "Identification Card Number": "19850315099"}
    row_b = {"GlobalID": "G2", "ObjectID": "2", "Identification Card Number": "19850315099"}

    result_a = parse_row(row_a, salt="fixed-salt")
    result_b = parse_row(row_b, salt="fixed-salt")

    assert result_a["dedup_hash"] == result_b["dedup_hash"]
    assert result_a["dedup_hash"] is not None


def test_parse_row_dedup_hash_none_when_id_blank():
    row = {"GlobalID": "G1", "ObjectID": "1"}

    result = parse_row(row, salt="s")

    assert result["dedup_hash"] is None


def test_parse_row_address_reduces_to_street():
    row = {"GlobalID": "G1", "ObjectID": "1", "Address": "#5 Ramlal Trace, Platanite Trace, Rochard Road"}

    result = parse_row(row, salt="s")

    assert result["street"] == "#5 Ramlal Trace"


def test_is_duplicate_marker_detects_literal_marker():
    assert is_duplicate_marker("Duplicate entry", None) is True
    assert is_duplicate_marker(None, "duplicate entry") is True
    assert is_duplicate_marker("Real Name", "Real summary") is False
