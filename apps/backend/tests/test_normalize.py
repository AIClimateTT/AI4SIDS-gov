import logging

from app.modules.survey123.normalize import (
    normalize_corporation,
    normalize_incident_type,
    normalize_validation_status,
    parse_follow_up_flags,
    parse_occupants,
)


def test_normalize_corporation_lowercases_known_variant():
    assert normalize_corporation("Sangre_Grande_Regional_Corporat") == (
        "sangre_grande_regional_corporat",
        None,
    )


def test_normalize_corporation_collapses_case_variant():
    assert normalize_corporation("mayaro_rio_claro_regional_corpo") == (
        "mayaro_rio_claro_regional_corpo",
        None,
    )
    assert normalize_corporation("Mayaro_Rio_Claro_Regional_Corpo") == (
        "mayaro_rio_claro_regional_corpo",
        None,
    )


def test_normalize_corporation_blank_is_none():
    assert normalize_corporation("") == (None, None)
    assert normalize_corporation(None) == (None, None)


def test_normalize_corporation_unmapped_logs_and_preserves_raw(caplog):
    with caplog.at_level(logging.WARNING):
        result = normalize_corporation("Unknown_Corp_Typo")

    assert result == ("unmapped", "Unknown_Corp_Typo")
    assert "Unknown_Corp_Typo" in caplog.text


def test_normalize_incident_type_lowercases_known_value():
    assert normalize_incident_type("Flooding_") == ("flooding_", None)
    assert normalize_incident_type("Over Grown Tree") == ("over grown tree", None)


def test_normalize_incident_type_unmapped_logs_and_preserves_raw(caplog):
    with caplog.at_level(logging.WARNING):
        result = normalize_incident_type("Volcanic_Eruption_Typo")

    assert result == ("unmapped", "Volcanic_Eruption_Typo")
    assert "Volcanic_Eruption_Typo" in caplog.text


def test_normalize_validation_status_validated():
    assert normalize_validation_status("Validated") == "validated"


def test_normalize_validation_status_blank_is_pending():
    assert normalize_validation_status("") == "pending"
    assert normalize_validation_status(None) == "pending"


def test_normalize_validation_status_unexpected_value_defaults_pending(caplog):
    with caplog.at_level(logging.WARNING):
        result = normalize_validation_status("Rejected")

    assert result == "pending"
    assert "Rejected" in caplog.text


def test_parse_occupants_direct_digit():
    assert parse_occupants("3", "") == 3


def test_parse_occupants_blank_is_none():
    assert parse_occupants("", "") is None
    assert parse_occupants(None, None) is None


def test_parse_occupants_other_with_numeric_overflow():
    assert parse_occupants("other", "9") == 9


def test_parse_occupants_other_with_text_overflow():
    assert parse_occupants("other", "12 persons") == 12


def test_parse_occupants_other_with_unparseable_overflow_logs(caplog):
    with caplog.at_level(logging.WARNING):
        result = parse_occupants("other", "many")

    assert result is None
    assert "many" in caplog.text


def test_parse_follow_up_flags_blank_all_false():
    assert parse_follow_up_flags("") == {
        "relief_supplied": False,
        "forwarded_to_agency": False,
        "further_assessment_required": False,
        "other": False,
    }


def test_parse_follow_up_flags_single_token():
    assert parse_follow_up_flags("Supply_Relief_Items_") == {
        "relief_supplied": True,
        "forwarded_to_agency": False,
        "further_assessment_required": False,
        "other": False,
    }


def test_parse_follow_up_flags_multi_token():
    assert parse_follow_up_flags(
        "Supply_Relief_Items_,Forward_to_Other_Agency,Further_Assessment_Required_"
    ) == {
        "relief_supplied": True,
        "forwarded_to_agency": True,
        "further_assessment_required": True,
        "other": False,
    }


def test_parse_follow_up_flags_unmapped_token_logs_and_ignores(caplog):
    with caplog.at_level(logging.WARNING):
        result = parse_follow_up_flags("Some_New_Token_")

    assert result == {
        "relief_supplied": False,
        "forwarded_to_agency": False,
        "further_assessment_required": False,
        "other": False,
    }
    assert "Some_New_Token_" in caplog.text
