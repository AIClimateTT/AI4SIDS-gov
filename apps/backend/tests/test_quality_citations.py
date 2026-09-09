from datetime import datetime

from app.core.citation_check import check_citations
from app.core.contracts import Citation, Fact, FactTable
from app.quality.citations import score_citations


def make_table() -> FactTable:
    fact = Fact(
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
    return FactTable(
        request_id="r",
        template="t",
        params={},
        generated_at=datetime(2024, 7, 1),
        facts=[fact],
        gaps=[],
    )


def test_perfect_citation_rate_is_one():
    narrative = "There were 19 incidents [C001]."
    result = check_citations(narrative, make_table())
    proxy = score_citations(result, narrative)
    assert result.passed
    assert proxy.citation_instances == 1
    assert proxy.rate == 1.0
    assert proxy.missing == 0
    assert proxy.misattributed == 0
    assert proxy.invented == 0


def test_missing_citation_drops_the_rate():
    narrative = "There were 19 incidents."
    result = check_citations(narrative, make_table())
    proxy = score_citations(result, narrative)
    assert proxy.missing >= 1
    assert proxy.rate < 1.0
