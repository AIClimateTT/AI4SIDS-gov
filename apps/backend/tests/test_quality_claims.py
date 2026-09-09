from datetime import datetime

from app.core.citation_check import check_citations
from app.core.contracts import Citation, Fact, FactTable
from app.quality.claims import extract_claims


def make_table(*facts: Fact) -> FactTable:
    return FactTable(
        request_id="r",
        template="t",
        params={},
        generated_at=datetime(2024, 7, 1),
        facts=list(facts),
        gaps=[],
    )


def count_fact() -> Fact:
    return Fact(
        metric="incident_count",
        value=19,
        unit="incidents",
        scope={"corporation": "all"},
        breakdown=None,
        verification="validated",
        citation=Citation(
            cid="C001",
            module="sitreps",
            description="count",
            query_ref="q",
            record_ids=["1"],
            as_of=datetime(2024, 7, 1),
        ),
    )


def test_cited_matching_number_is_supported():
    table = make_table(count_fact())
    narrative = "There were 19 incidents [C001]."
    result = check_citations(narrative, table)
    score = extract_claims(narrative, table, result)
    assert score.material_count == 1
    assert score.claims[0].auto_verdict == "supported"
    assert score.unsupported_rate == 0.0
    assert score.faithfulness_rate == 1.0


def test_invented_number_is_unsupported():
    table = make_table(count_fact())
    narrative = "There were 99 incidents [C001]."
    result = check_citations(narrative, table)
    score = extract_claims(narrative, table, result)
    assert score.claims[0].auto_verdict == "unsupported"
    assert score.unsupported_count == 1


def test_connective_prose_is_not_material():
    table = make_table(count_fact())
    narrative = "The situation remains dynamic."
    result = check_citations(narrative, table)
    score = extract_claims(narrative, table, result)
    assert score.material_count == 0
    assert score.claims == []


def test_no_deaths_without_a_zero_fact_is_critical_unsupported():
    table = make_table(count_fact())
    narrative = "There were no deaths."
    result = check_citations(narrative, table)
    score = extract_claims(narrative, table, result)
    assert score.claims[0].critical is True
    assert score.claims[0].auto_verdict == "unsupported"
    assert score.critical_unsupported_count == 1
    assert score.critical_hallucination_rate == 1.0


def test_cited_prose_without_digits_is_pending_semantic():
    table = make_table(count_fact())
    narrative = "Flooding affected Arima [C001]."
    result = check_citations(narrative, table)
    score = extract_claims(narrative, table, result)
    assert score.claims[0].auto_verdict == "pending_semantic"
    assert score.faithfulness_rate is None


def test_human_verdict_resolves_pending_semantic():
    from app.quality.claims import recompute_claim_rates

    table = make_table(count_fact())
    narrative = "Flooding affected Arima [C001]."
    result = check_citations(narrative, table)
    score = extract_claims(narrative, table, result)
    assert score.claims[0].auto_verdict == "pending_semantic"
    score.claims[0].human_verdict = "supported"
    updated = recompute_claim_rates(score)
    assert updated.faithfulness_rate == 1.0
    assert updated.unsupported_rate == 0.0
