from datetime import datetime

from app.core.contracts import Citation, Fact, FactTable
from app.core.citation_check import check_citations


def make_citation(cid: str) -> Citation:
    return Citation(
        cid=cid,
        module="survey123",
        description="test citation",
        query_ref="test()",
        record_ids=["GUID-1"],
        as_of=datetime(2024, 7, 1),
    )


def make_fact_table(facts=None) -> FactTable:
    if facts is None:
        facts = [
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
            Fact(
                metric="data_coverage",
                value=15,
                unit="records",
                scope={"corporation": "sangre_grande_regional_corporat"},
                breakdown={"pct_validated": 66.7, "pct_duplicates": 13.3},
                verification="n/a",
                citation=make_citation("survey123-data_coverage-2"),
            ),
        ]
    return FactTable(
        request_id="req-1",
        template="minister_regional_comparison",
        params={"date_from": "2024-06-01", "date_to": "2024-06-30"},
        generated_at=datetime(2024, 7, 1),
        facts=facts,
        gaps=[],
    )


def test_passing_narrative_with_cited_matching_numbers():
    fact_table = make_fact_table()
    narrative = (
        "There were 19 incidents recorded [survey123-incident_count-0]. "
        "Estimated damage totaled $98,000 [survey123-estimated_damage_total-0]."
    )

    result = check_citations(narrative, fact_table)

    assert result.passed is True
    assert result.violations == []


def test_invented_number_is_flagged():
    fact_table = make_fact_table()
    narrative = "There were 20 incidents recorded [survey123-incident_count-0]."

    result = check_citations(narrative, fact_table)

    assert result.passed is False
    assert len(result.violations) == 1
    assert result.violations[0].kind == "invented_number"
    assert result.violations[0].token == "20"


def test_missing_citation_is_flagged():
    fact_table = make_fact_table()
    narrative = "There were 19 incidents recorded."

    result = check_citations(narrative, fact_table)

    assert result.passed is False
    assert len(result.violations) == 1
    assert result.violations[0].kind == "missing_citation"


def test_comma_formatted_number_matches():
    fact_table = make_fact_table()
    narrative = "Estimated damage totaled $98,000 [survey123-estimated_damage_total-0]."

    result = check_citations(narrative, fact_table)

    assert result.passed is True


def test_percentage_matches_breakdown_value():
    fact_table = make_fact_table()
    narrative = "66.7% of records in Sangre Grande were validated [survey123-data_coverage-2]."

    result = check_citations(narrative, fact_table)

    assert result.passed is True


def test_iso_dates_are_ignored_without_citation():
    fact_table = make_fact_table()
    narrative = "This report covers the period from 2024-06-01 to 2024-06-30."

    result = check_citations(narrative, fact_table)

    assert result.passed is True
    assert result.violations == []


def test_cid_embedded_digit_does_not_leak_as_invented_number():
    fact_table = make_fact_table()
    narrative = "15 records were reviewed for this corporation [survey123-data_coverage-2]."

    result = check_citations(narrative, fact_table)

    assert result.passed is True


def test_unrecognized_citation_marker_counts_as_missing():
    fact_table = make_fact_table()
    narrative = "There were 19 incidents recorded [fake-cid-99]."

    result = check_citations(narrative, fact_table)

    assert result.passed is False
    assert result.violations[0].kind == "missing_citation"


def test_number_genuinely_absent_from_fact_table_is_invented():
    fact_table = make_fact_table()
    narrative = "Officers responded within 9 hours [survey123-incident_count-0]."

    result = check_citations(narrative, fact_table)

    assert result.passed is False
    assert result.violations[0].kind == "invented_number"
    assert result.violations[0].token == "9"


def test_breakdown_value_from_a_different_fact_in_the_table_matches():
    fact_table = make_fact_table()
    narrative = "Of these, 7 were flooding incidents [survey123-incident_count-0]."

    result = check_citations(narrative, fact_table)

    assert result.passed is True


def test_multi_sentence_narrative_flags_only_the_problem_sentence():
    fact_table = make_fact_table()
    narrative = (
        "There were 19 incidents recorded [survey123-incident_count-0]. "
        "Officers responded within 9 hours. "
        "Estimated damage totaled $98,000 [survey123-estimated_damage_total-0]."
    )

    result = check_citations(narrative, fact_table)

    assert result.passed is False
    kinds = {v.kind for v in result.violations}
    assert kinds == {"missing_citation", "invented_number"}
    for violation in result.violations:
        assert violation.sentence == "Officers responded within 9 hours."


def test_two_numbers_one_sentence_mixed_validity():
    fact_table = make_fact_table()
    narrative = "There were 19 incidents and 42 fires recorded [survey123-incident_count-0]."

    result = check_citations(narrative, fact_table)

    assert result.passed is False
    assert len(result.violations) == 1
    assert result.violations[0].kind == "invented_number"
    assert result.violations[0].token == "42"


def test_empty_narrative_passes_trivially():
    fact_table = make_fact_table()

    result = check_citations("", fact_table)

    assert result.passed is True
    assert result.violations == []


def test_prose_without_numbers_needs_no_citation():
    fact_table = make_fact_table()

    result = check_citations("No incidents were recorded this period.", fact_table)

    assert result.passed is True
    assert result.violations == []


def test_empty_fact_table_flags_any_stated_number():
    empty_fact_table = make_fact_table(facts=[])

    result = check_citations("There were 19 incidents.", empty_fact_table)

    assert result.passed is False
    kinds = {v.kind for v in result.violations}
    assert kinds == {"missing_citation", "invented_number"}
