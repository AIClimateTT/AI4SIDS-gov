from datetime import datetime, timezone

from app.core.contracts import (
    Citation,
    Fact,
    FactTable,
    NarrationConfig,
    RenderConfig,
    Template,
)
from app.core.renderer import render_report


def make_citation(cid: str) -> Citation:
    return Citation(
        cid=cid,
        module="survey123",
        description=f"test citation {cid}",
        query_ref="test()",
        record_ids=["GUID-1"],
        as_of=datetime(2024, 7, 1, tzinfo=timezone.utc),
    )


def make_template(include_citation_appendix: bool = True) -> Template:
    return Template(
        name="test_template",
        title="Test Briefing",
        description="test",
        params=[],
        data_requirements=[],
        narration=NarrationConfig.of("p"),
        render=RenderConfig(include_citation_appendix=include_citation_appendix),
    )


def make_fact_table(facts=None, gaps=None) -> FactTable:
    return FactTable(
        request_id="req-1",
        template="test_template",
        params={},
        generated_at=datetime(2024, 7, 1, tzinfo=timezone.utc),
        facts=facts or [],
        gaps=gaps or [],
    )


def test_render_includes_title_and_narrative():
    fact_table = make_fact_table()

    markdown = render_report(make_template(), fact_table, "This is the narrative text.")

    assert "# Test Briefing" in markdown
    assert "This is the narrative text." in markdown


def test_render_includes_data_table_for_fact_with_breakdown():
    fact = Fact(
        metric="incidents_by_corporation",
        value=19,
        unit="incidents",
        scope={"corporation": "all"},
        breakdown={"sangre_grande_regional_corporat": 10, "san_fernando_city_corporation": 9},
        verification="validated",
        citation=make_citation("C001"),
    )
    fact_table = make_fact_table(facts=[fact])

    markdown = render_report(make_template(), fact_table, "narrative")

    assert "## Data Tables" in markdown
    assert "sangre_grande_regional_corporat" in markdown
    assert "| 10 |" in markdown


def test_render_skips_data_tables_section_when_no_fact_has_breakdown():
    fact = Fact(
        metric="special_needs_count",
        value=2,
        unit="persons",
        scope={"corporation": "all"},
        breakdown=None,
        verification="validated",
        citation=make_citation("C001"),
    )
    fact_table = make_fact_table(facts=[fact])

    markdown = render_report(make_template(), fact_table, "narrative")

    assert "## Data Tables" not in markdown


def test_render_includes_data_gaps_section_when_gaps_present():
    fact_table = make_fact_table(gaps=["No data returned for survey123.incident_count with params {}"])

    markdown = render_report(make_template(), fact_table, "narrative")

    assert "## Data Gaps" in markdown
    assert "No data returned for survey123.incident_count" in markdown


def test_render_skips_data_gaps_section_when_no_gaps():
    fact_table = make_fact_table(gaps=[])

    markdown = render_report(make_template(), fact_table, "narrative")

    assert "## Data Gaps" not in markdown


def test_render_includes_citation_appendix_by_default():
    fact = Fact(
        metric="incident_count",
        value=19,
        unit="incidents",
        scope={"corporation": "all"},
        breakdown=None,
        verification="validated",
        citation=make_citation("C001"),
    )
    fact_table = make_fact_table(facts=[fact])

    markdown = render_report(make_template(), fact_table, "narrative")

    assert "## Citation Appendix" in markdown
    assert "C001" in markdown
    assert "test citation C001" in markdown


def test_filing_layout_omits_zero_relief_and_unknown_street():
    template = make_template()
    template.render.layout = "filing"
    fact_table = make_fact_table(
        facts=[
            Fact(
                metric="incident_count",
                value=1,
                unit="incidents",
                scope={"corporation": "all"},
                breakdown={"flooding_": 1, "landslide": 0},
                verification="validated",
                citation=make_citation("C001"),
            ),
            Fact(
                metric="relief_stock_summary",
                value=10.0,
                unit="units",
                scope={"item": "tarpaulins", "status": "completed"},
                breakdown=None,
                verification="validated",
                citation=make_citation("C002"),
            ),
            Fact(
                metric="relief_stock_summary",
                value=0,
                unit="units",
                scope={"item": "blankets", "status": "completed"},
                breakdown=None,
                verification="validated",
                citation=make_citation("C003"),
            ),
            Fact(
                metric="incident_register",
                value=1,
                unit="incident",
                scope={
                    "date": "2026-08-21",
                    "community": "",
                    "street": "Tumpuna Road",
                    "type": "flooding_",
                    "summary": "Flooding on Tumpuna Road",
                    "injuries": "1",
                    "deaths": "",
                    "action": "",
                },
                breakdown=None,
                verification="validated",
                citation=make_citation("C004"),
            ),
        ]
    )

    markdown = render_report(template, fact_table, "Connective prose.")

    assert "## Situation summary" in markdown
    assert "| flooding_ | 1 |" in markdown
    assert "landslide" not in markdown
    assert "| 10 |" in markdown
    assert "blankets" not in markdown
    assert "Tumpuna Road" in markdown
    assert "unknown street" not in markdown.lower()
    assert "## Data Tables" not in markdown
    assert "Connective prose." in markdown


def test_filing_omits_data_gaps_when_the_only_gap_is_none():
    template = make_template()
    template.render.layout = "filing"
    markdown = render_report(template, make_fact_table(gaps=["None"]), "prose")
    assert "## Data Gaps" not in markdown


def test_render_omits_citation_appendix_when_disabled():
    fact = Fact(
        metric="incident_count",
        value=19,
        unit="incidents",
        scope={"corporation": "all"},
        breakdown=None,
        verification="validated",
        citation=make_citation("C001"),
    )
    fact_table = make_fact_table(facts=[fact])

    markdown = render_report(make_template(include_citation_appendix=False), fact_table, "narrative")

    assert "## Citation Appendix" not in markdown
