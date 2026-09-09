from datetime import datetime

from app.core.citation_check import check_citations
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
from app.quality.score import score_quality


def test_score_quality_composes_all_sections():
    fact = Fact(
        metric="incident_count",
        value=19,
        unit="incidents",
        scope={"corporation": "all"},
        breakdown={"flooding_": 19},
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
    fact_table = FactTable(
        request_id="r",
        template="corp_situation_report",
        params={"corporation": "arima"},
        generated_at=datetime(2024, 7, 1),
        facts=[fact],
        gaps=[],
    )
    template = Template(
        name="corp_situation_report",
        title="Corporation Situation Report",
        description="test",
        params=[TemplateParam(name="corporation", required=True)],
        data_requirements=[DataRequirement(module="sitreps", metric="incident_count")],
        narration=NarrationConfig.of("compose", output_sections=["connective_prose"]),
        render=RenderConfig(layout="filing", include_citation_appendix=True),
    )
    narrative = "There were 19 incidents [C001]."
    markdown = (
        "# Corporation Situation Report\n\n"
        f"{narrative}\n\n"
        "## Situation summary\n\n"
        "| Type | Count |\n|---|---|\n| Flooding | 19 |\n\n"
        "## Citation Appendix\n- [C001] count\n"
    )
    result = check_citations(narrative, fact_table)
    eval_ = score_quality(template, fact_table, narrative, markdown, result)
    assert eval_.scorer_version == 1
    assert eval_.citations.rate == 1.0
    assert eval_.completeness.rate == 1.0
    assert eval_.numerical.passed
    assert eval_.claims.material_count >= 1
