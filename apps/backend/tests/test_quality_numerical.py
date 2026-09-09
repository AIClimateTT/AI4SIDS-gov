from datetime import datetime

from app.core.citation_check import check_citations
from app.core.contracts import Citation, Fact, FactTable
from app.quality.numerical import score_numerical


def make_table(*, deaths: int | None = None) -> FactTable:
    facts = [
        Fact(
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
    ]
    if deaths is not None:
        facts.append(
            Fact(
                metric="casualty_summary",
                value=deaths,
                unit="deaths",
                scope={"kind": "deaths"},
                breakdown=None,
                verification="validated",
                citation=Citation(
                    cid="C002",
                    module="sitreps",
                    description="deaths",
                    query_ref="q",
                    record_ids=["1"],
                    as_of=datetime(2024, 7, 1),
                ),
            )
        )
    return FactTable(
        request_id="r",
        template="t",
        params={},
        generated_at=datetime(2024, 7, 1),
        facts=facts,
        gaps=[],
    )


def test_critical_count_in_markdown_matches_the_fact():
    table = make_table()
    markdown = "There were 19 incidents [C001].\n"
    result = check_citations(markdown, table)
    score = score_numerical(table, markdown, result)
    assert score.passed
    assert score.rate == 1.0


def test_invented_critical_number_fails():
    table = make_table()
    markdown = "There were 99 incidents [C001].\n"
    result = check_citations(markdown, table)
    score = score_numerical(table, markdown, result)
    assert score.passed is False


def test_omitted_zero_deaths_fact_still_passes():
    table = make_table(deaths=0)
    markdown = "There were 19 incidents [C001].\n"
    result = check_citations(markdown, table)
    score = score_numerical(table, markdown, result)
    assert score.passed
    zero = next(item for item in score.items if item.metric == "casualty_summary")
    assert zero.appeared is False
    assert zero.matched is True
