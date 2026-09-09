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
        template="minister_situation_report",
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
    # Also trips empty_narrative — the narrative cites nothing at all — so
    # assert on the kind under test rather than the total count.
    assert "missing_citation" in [v.kind for v in result.violations]


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
    # Carries a citation so the subject under test stays ISO-date handling; a
    # narrative citing nothing now trips empty_narrative separately.
    fact_table = make_fact_table()
    narrative = (
        "This report covers the period from 2024-06-01 to 2024-06-30 "
        "[survey123-incident_count-0]."
    )

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


def test_prose_without_numbers_still_needs_to_cite_something():
    # Previously this passed: prose carrying no figures needed no citation. It
    # now fails, deliberately. A narrative that cites nothing while the fact
    # table holds facts has not reported them — and this one actively
    # contradicts a table containing 19 incidents. A corporation with genuinely
    # nothing to report is still expressible, by citing the zero-valued fact:
    # "No incidents were recorded [C001]".
    fact_table = make_fact_table()

    result = check_citations("No incidents were recorded this period.", fact_table)

    assert [v.kind for v in result.violations] == ["empty_narrative"]


def test_prose_without_numbers_passes_when_it_cites_a_fact():
    fact_table = make_fact_table()

    result = check_citations(
        f"No further incidents were recorded this period [{CID}].", fact_table
    )

    assert result.passed is True


def test_empty_fact_table_flags_any_stated_number():
    empty_fact_table = make_fact_table(facts=[])

    result = check_citations("There were 19 incidents.", empty_fact_table)

    assert result.passed is False
    kinds = {v.kind for v in result.violations}
    assert kinds == {"missing_citation", "invented_number"}


CID = "survey123-incident_count-0"


def test_module_name_containing_digits_is_not_a_figure():
    # "Survey123" yielded "123" five times in a real ministerial report.
    result = check_citations(
        f"Survey123 field observations corroborate the total [{CID}].", make_fact_table()
    )

    assert result.violations == []


def test_dotted_module_reference_is_not_a_figure():
    result = check_citations(
        f"No data returned for survey123.data_coverage [{CID}].", make_fact_table()
    )

    assert [v for v in result.violations if v.kind == "invented_number"] == []


def test_prose_date_with_day_month_year_is_not_a_figure():
    result = check_citations(
        f"This report covers June 1, 2023, to December 31, 2024 [{CID}].", make_fact_table()
    )

    assert result.violations == []


def test_prose_date_with_an_ordinal_day_is_not_a_figure():
    # 19, not 15: the figure has to belong to the fact it cites now, and the
    # subject under test here is date stripping, not attribution.
    result = check_citations(
        f"As of August 3rd, 2026, 19 incidents were recorded [{CID}].", make_fact_table()
    )

    assert result.violations == []


def test_day_first_prose_date_is_not_a_figure():
    result = check_citations(
        f"Filed 31 December 2024 by the corporation [{CID}].", make_fact_table()
    )

    assert result.violations == []


def test_month_and_year_alone_is_not_a_figure():
    result = check_citations(
        f"Situation Report - Diego Martin Regional Corporation - June 2023 [{CID}].",
        make_fact_table(),
    )

    assert result.violations == []


def test_iso_date_is_still_not_a_figure():
    result = check_citations(
        f"Window 2023-06-01 to 2023-06-30 covered 19 incidents [{CID}].", make_fact_table()
    )

    assert result.violations == []


def test_an_invented_number_in_a_cited_sentence_is_still_flagged():
    # The test that proves the precision fix did not simply disable the check.
    result = check_citations(
        f"A total of 99 incidents were recorded [{CID}].", make_fact_table()
    )

    assert [v.token for v in result.violations if v.kind == "invented_number"] == ["99"]


def test_a_bare_year_with_no_month_is_still_checked():
    # 2023 alone is indistinguishable from a figure, so it must not be excused.
    result = check_citations(
        f"The corporation recorded 2023 affected households [{CID}].", make_fact_table()
    )

    assert [v.token for v in result.violations if v.kind == "invented_number"] == ["2023"]


def test_a_figure_without_a_citation_is_still_flagged():
    # Also trips empty_narrative, correctly: this narrative cites nothing at
    # all. Assert on presence rather than the exact list.
    result = check_citations("A total of 15 incidents were recorded.", make_fact_table())

    assert "missing_citation" in [v.kind for v in result.violations]


def test_violation_sentence_keeps_the_original_text():
    # Date stripping happens on a throwaway copy; a reviewer must see what was written.
    result = check_citations(
        f"On June 1, 2023 there were 99 incidents [{CID}].", make_fact_table()
    )

    assert "June 1, 2023" in result.violations[0].sentence


def test_a_narrative_that_cites_nothing_is_a_violation():
    # A real ministerial report returned exactly this and was saved status "ok".
    result = check_citations("**", make_fact_table())

    assert result.passed is False
    assert [v.kind for v in result.violations] == ["empty_narrative"]


def test_an_empty_narrative_is_a_violation():
    result = check_citations("", make_fact_table())

    assert [v.kind for v in result.violations] == ["empty_narrative"]


def test_prose_that_cites_nothing_is_a_violation():
    # "Cited nothing" rather than "wrote nothing": prose naming no fact is
    # equally a failure to report.
    result = check_citations("The situation remains under review.", make_fact_table())

    assert [v.kind for v in result.violations] == ["empty_narrative"]


def test_a_narrative_citing_a_fact_is_not_empty():
    result = check_citations(f"There were 19 incidents [{CID}].", make_fact_table())

    assert result.passed is True


def test_an_empty_narrative_with_no_facts_is_not_a_violation():
    # Nothing was requested, so nothing going unreported is correct.
    empty = make_fact_table()
    empty.facts.clear()

    result = check_citations("", empty)

    assert result.violations == []


def test_empty_narrative_violation_carries_a_readable_excerpt():
    result = check_citations("x" * 500, make_fact_table())

    assert len(result.violations[0].sentence) == 200


def test_a_four_digit_figure_after_a_month_name_is_still_checked():
    # PROSE_DATE_RE's MONTH+YEAR alternative erased these entirely: the
    # sentence ended up with no tokens, so the invented-number AND the
    # missing-citation checks were both skipped.
    result = check_citations(
        f"There were 19 incidents [{CID}]. In May 2500 households were affected.",
        make_fact_table(),
    )

    assert result.passed is False


def test_a_large_invented_figure_after_an_abbreviated_month_is_still_checked():
    result = check_citations(
        f"There were 19 incidents [{CID}]. Sept 1200 people were displaced.",
        make_fact_table(),
    )

    assert result.passed is False


def test_real_month_and_year_is_still_not_a_figure():
    result = check_citations(
        f"Situation Report for June 2023 covering 19 incidents [{CID}].", make_fact_table()
    )

    assert result.violations == []


# --- number-to-citation binding -------------------------------------------
#
# Before these, fact numbers were unioned across the whole table and a
# sentence passed if it carried ANY valid cid; the two were never related.


def make_two_source_fact_table() -> FactTable:
    """C001: unverified Survey123 field count of 12. C002: signed-off SITREP
    count of 7. The exact pairing the reviewer reproduced the defect with."""
    return FactTable(
        request_id="req-2",
        template="field_data_region_review",
        params={},
        generated_at=datetime(2024, 7, 1),
        facts=[
            Fact(
                metric="incident_count",
                value=12,
                unit="incidents",
                scope={"corporation": "sangre_grande_regional_corporat"},
                breakdown=None,
                verification="pending",
                citation=Citation(
                    cid="C001",
                    module="survey123",
                    description="Survey123 incident count",
                    query_ref="incident_count()",
                    record_ids=["GUID-1"],
                    as_of=datetime(2024, 7, 1),
                ),
            ),
            Fact(
                metric="incident_count",
                value=7,
                unit="incidents",
                scope={"corporation": "sangre_grande_regional_corporat"},
                breakdown=None,
                verification="validated",
                citation=Citation(
                    cid="C002",
                    module="sitreps",
                    description="SITREP incident count",
                    query_ref="incident_count()",
                    record_ids=["arima_borough_corporation:1:1"],
                    as_of=datetime(2024, 7, 1),
                ),
            ),
        ],
        gaps=[],
    )


def test_a_figure_published_under_another_facts_citation_is_flagged():
    # The reviewer's exact reproduction. 12 is real — it is C001's Survey123
    # field count, verification "pending" — but it is stated here under C002,
    # the corporation's signed-off SITREP citation. Nothing about the sentence
    # looks wrong; only its provenance is another fact's. This passed cleanly.
    result = check_citations(
        "Sangre Grande has confirmed 12 incidents in signed-off situation reports [C002].",
        make_two_source_fact_table(),
    )

    assert result.passed is False
    assert [v.kind for v in result.violations] == ["misattributed_number"]
    assert result.violations[0].token == "12"
    assert "C002" in result.violations[0].detail


def test_a_list_block_is_checked_line_by_line():
    # The reviewer's second reproduction. SENTENCE_SPLIT_RE split only on .!?,
    # so this whole block was one "sentence" and the single [C002] laundered
    # the 12 above it.
    result = check_citations(
        "- Incidents recorded: 12\n- Deaths: 7 [C002]", make_two_source_fact_table()
    )

    assert result.passed is False
    assert "missing_citation" in [v.kind for v in result.violations]
    assert result.violations[0].sentence == "- Incidents recorded: 12"


def test_a_table_row_carrying_an_uncited_figure_is_checked_on_its_own():
    result = check_citations(
        "| Metric | Value |\n| Incidents | 12 |\n| Deaths | 7 [C002] |",
        make_two_source_fact_table(),
    )

    assert result.passed is False
    assert [v.sentence for v in result.violations] == ["| Incidents | 12 |"]


def test_each_figure_cited_against_its_own_fact_passes():
    result = check_citations(
        "Field observations record 12 incidents [C001]. "
        "Situation reports confirm 7 [C002].",
        make_two_source_fact_table(),
    )

    assert result.passed is True


def test_a_sentence_citing_both_facts_may_state_either_figure():
    result = check_citations(
        "Sources report 12 and 7 incidents respectively [C001] [C002].",
        make_two_source_fact_table(),
    )

    assert result.passed is True


def test_a_figure_from_the_cited_facts_breakdown_still_passes():
    # The behaviour that must survive: a fact's own decomposition is part of
    # what that fact says. 7 is incident_count's flooding_ breakdown entry.
    result = check_citations(
        f"Of these, 7 were flooding incidents [{CID}].", make_fact_table()
    )

    assert result.passed is True


def test_a_breakdown_figure_from_another_fact_is_misattributed():
    # 5 is estimated_damage_total's records_reporting_cost, not anything
    # incident_count reported.
    result = check_citations(
        f"Only 5 incidents were assessed [{CID}].", make_fact_table()
    )

    assert [v.kind for v in result.violations] == ["misattributed_number"]
    assert result.violations[0].token == "5"


def test_a_number_in_no_fact_at_all_is_still_invented_not_misattributed():
    # The two kinds must stay distinct: invented means the figure exists
    # nowhere, misattributed means it exists under a different citation.
    result = check_citations(
        f"Officers responded within 9 hours [{CID}].", make_fact_table()
    )

    assert [v.kind for v in result.violations] == ["invented_number"]


def test_an_uncited_sentence_is_reported_as_missing_citation_only():
    # No valid cid means there is no attribution to be wrong about; reporting
    # both would just duplicate the same defect.
    result = check_citations(
        f"There were 19 incidents [{CID}]. A further 15 records were reviewed.",
        make_fact_table(),
    )

    kinds = [v.kind for v in result.violations]
    assert kinds == ["missing_citation"]


def test_a_date_range_carrying_one_year_is_not_a_figure():
    # "June 1st - June 30th, 2023" only carries a year on the last part, so the
    # leading "1" leaked through as an invented figure on every report.
    result = check_citations(
        f"This report covers June 1st to June 30th, 2023 [{CID}].", make_fact_table()
    )

    assert result.violations == []


def test_a_bare_month_and_day_with_no_ordinal_is_still_checked():
    # "In June 88 homes were affected" — stripping this would hide a real
    # figure. 88 is absent from the fact table, so it must surface as invented.
    result = check_citations(
        f"In June 88 homes were affected [{CID}].", make_fact_table()
    )

    assert [v.token for v in result.violations if v.kind == "invented_number"] == ["88"]


def test_one_bracket_may_carry_several_cids():
    # "[C008, C009]" is how a model cites a figure drawn from more than one
    # fact. Matching only a single cid read the bracket as citing nothing.
    result = check_citations(
        "Coverage was 19 records "
        "[survey123-incident_count-0, survey123-estimated_damage_total-0].",
        make_fact_table(),
    )

    assert result.passed is True


def test_a_multi_cid_bracket_still_binds_the_number_to_those_facts():
    result = check_citations(
        "Officers responded within 9 hours "
        "[survey123-incident_count-0, survey123-data_coverage-2].",
        make_fact_table(),
    )

    assert [v.kind for v in result.violations] == ["invented_number"]


def test_spelled_out_invented_number_is_flagged():
    result = check_citations(
        "There were ninety homes affected [survey123-incident_count-0].",
        make_fact_table(),
    )
    kinds = {v.kind for v in result.violations}
    assert "invented_number" in kinds


def test_spelled_out_licensed_number_passes():
    result = check_citations(
        "There were fifteen records [survey123-data_coverage-2].",
        make_fact_table(),
    )
    assert [v for v in result.violations if v.kind == "invented_number"] == []


def test_digit_invented_number_still_flagged():
    result = check_citations(
        "There were 99 incidents [survey123-incident_count-0].",
        make_fact_table(),
    )
    assert any(v.kind == "invented_number" and v.token == "99" for v in result.violations)
