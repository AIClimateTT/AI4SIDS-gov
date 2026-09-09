from datetime import datetime

from app.core.contracts import (
    Citation,
    DataRequirement,
    Fact,
    FactTable,
    NarrationConfig,
    RenderConfig,
    Template,
    TemplateParam,
)
from app.quality.completeness import score_completeness


def make_citation(cid: str = "C001") -> Citation:
    return Citation(
        cid=cid,
        module="sitreps",
        description="count",
        query_ref="q",
        record_ids=["1"],
        as_of=datetime(2024, 7, 1),
    )


def make_count_fact() -> Fact:
    return Fact(
        metric="incident_count",
        value=3,
        unit="incidents",
        scope={"corporation": "all"},
        breakdown={"flooding_": 3},
        verification="validated",
        citation=make_citation(),
    )


def make_template(*metrics: str, layout: str = "filing") -> Template:
    return Template(
        name="corp_situation_report",
        title="Corporation Situation Report",
        description="test",
        params=[TemplateParam(name="corporation", required=True)],
        data_requirements=[
            DataRequirement(module="sitreps", metric=metric) for metric in metrics
        ],
        narration=NarrationConfig.of(
            "compose",
            output_sections=["connective_prose", "data_gaps"],
        ),
        render=RenderConfig(layout=layout, include_citation_appendix=True),
    )


COMPLETE_MARKDOWN = """# Corporation Situation Report

Three flooding incidents.

## Situation summary

| Type | Count | Cite |
|---|---|---|
| Flooding | 3 | [C001] |

## Citation Appendix
- [C001] count
"""


def test_filing_with_justified_sections_is_complete():
    template = make_template("incident_count")
    fact_table = FactTable(
        request_id="r",
        template="corp_situation_report",
        params={"corporation": "arima"},
        generated_at=datetime(2024, 7, 1),
        facts=[make_count_fact()],
        gaps=[],
    )
    score = score_completeness(template, fact_table, COMPLETE_MARKDOWN)
    assert score.missing == []
    assert score.rate == 1.0


def test_missing_metric_without_a_gap_is_incomplete():
    template = make_template("incident_count", "casualty_summary")
    fact_table = FactTable(
        request_id="r",
        template="corp_situation_report",
        params={"corporation": "arima"},
        generated_at=datetime(2024, 7, 1),
        facts=[make_count_fact()],
        gaps=[],
    )
    score = score_completeness(template, fact_table, COMPLETE_MARKDOWN)
    assert "sitreps.casualty_summary" in score.missing
    assert score.rate < 1.0


def test_gap_naming_the_metric_counts_as_present():
    template = make_template("incident_count", "casualty_summary")
    fact_table = FactTable(
        request_id="r",
        template="corp_situation_report",
        params={"corporation": "arima"},
        generated_at=datetime(2024, 7, 1),
        facts=[make_count_fact()],
        gaps=["No data returned for sitreps.casualty_summary with params {}"],
    )
    score = score_completeness(template, fact_table, COMPLETE_MARKDOWN)
    assert "sitreps.casualty_summary" not in score.missing
