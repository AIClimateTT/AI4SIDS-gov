from datetime import datetime

from app.core.contracts import Citation, Fact, FactTable
from app.core.citation_check import (
    _collect_fact_numbers,
    _matches_any,
    _parse_number_token,
    _split_sentences,
    _strip_dates,
    _valid_cids,
)


def make_citation(cid: str) -> Citation:
    return Citation(
        cid=cid,
        module="survey123",
        description="test citation",
        query_ref="test()",
        record_ids=["GUID-1"],
        as_of=datetime(2024, 7, 1),
    )


def make_fact_table() -> FactTable:
    return FactTable(
        request_id="req-1",
        template="minister_regional_comparison",
        params={"date_from": "2024-06-01", "date_to": "2024-06-30"},
        generated_at=datetime(2024, 7, 1),
        facts=[
            Fact(
                metric="incident_count",
                value=19,
                unit="incidents",
                scope={"corporation": "all"},
                breakdown={"flooding_": 7, "other": 2},
                verification="validated",
                citation=make_citation("survey123-incident_count-0"),
            ),
            Fact(
                metric="estimated_damage_total",
                value=98000.0,
                unit="TTD",
                scope={"corporation": "all"},
                breakdown={"records_reporting_cost": 5, "records_total": 19},
                verification="validated",
                citation=make_citation("survey123-estimated_damage_total-0"),
            ),
        ],
        gaps=[],
    )


def test_parse_number_token_plain_integer():
    assert _parse_number_token("42") == 42.0


def test_parse_number_token_comma_formatted():
    assert _parse_number_token("14,942") == 14942.0


def test_parse_number_token_percentage():
    assert _parse_number_token("66.7%") == 66.7


def test_parse_number_token_comma_and_decimal():
    assert _parse_number_token("98,000.50") == 98000.50


def test_strip_dates_removes_iso_date():
    assert _strip_dates("from 2024-06-01 to 2024-06-30") == "from  to "


def test_strip_dates_leaves_text_without_dates_unchanged():
    assert _strip_dates("no dates here") == "no dates here"


def test_split_sentences_basic():
    assert _split_sentences("A. B! C?") == ["A.", "B!", "C?"]


def test_split_sentences_empty_string():
    assert _split_sentences("") == []


def test_split_sentences_whitespace_only():
    assert _split_sentences("   ") == []


def test_split_sentences_decimal_does_not_cause_false_split():
    assert _split_sentences("Rate was 66.7% of total. Next sentence.") == [
        "Rate was 66.7% of total.",
        "Next sentence.",
    ]


def test_collect_fact_numbers_includes_value_and_breakdown():
    fact_table = make_fact_table()

    numbers = _collect_fact_numbers(fact_table)

    assert numbers == {19.0, 7.0, 2.0, 98000.0, 5.0}


def test_collect_fact_numbers_skips_string_values():
    fact_table = FactTable(
        request_id="req-1",
        template="t",
        params={},
        generated_at=datetime(2024, 7, 1),
        facts=[
            Fact(
                metric="m",
                value="some string value",
                unit=None,
                scope={},
                breakdown=None,
                verification="n/a",
                citation=make_citation("m-0"),
            )
        ],
        gaps=[],
    )

    assert _collect_fact_numbers(fact_table) == set()


def test_valid_cids_returns_all_citation_ids():
    fact_table = make_fact_table()

    assert _valid_cids(fact_table) == {
        "survey123-incident_count-0",
        "survey123-estimated_damage_total-0",
    }


def test_matches_any_exact_match():
    assert _matches_any(19.0, {19.0, 7.0}) is True


def test_matches_any_no_match():
    assert _matches_any(20.0, {19.0, 7.0}) is False


def test_matches_any_within_epsilon():
    assert _matches_any(66.70000005, {66.7}) is True
