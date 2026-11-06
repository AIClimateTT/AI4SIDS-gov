import re
from datetime import datetime, timezone

from app.core.contracts import Citation, Fact, FactTable
from app.core.renderer import render_report
from app.core.template_catalog import get_template
from app.modules.survey123.normalize import CORPORATION_LABELS

ARIMA = "arima_borough_corporation"
SIPARIA = "siparia_regional_corporation"
PARAMS = {
    "date_from": "2023-05-05",
    "date_to": "2023-05-05",
    "as_at": "2023-05-05T15:00:00",
    "hazard": "Adverse Weather",
    "present_activity": "Notification Alert",
    "alert_level": "Adverse Weather Alert #1 - Green Level",
    "situation_overview": "A tropical wave is approaching.",
    "ministry_response": "A coordinators' meeting was held at 1pm.",
}


def _citation(cid: str) -> Citation:
    return Citation(
        cid=cid,
        module="sitreps",
        description="d",
        query_ref="q",
        record_ids=["r"],
        as_of=datetime(2023, 5, 5, tzinfo=timezone.utc),
    )


def _log(corporation: str, statement: str, cid: str = "C001") -> Fact:
    return Fact(
        metric="corporation_status",
        value=statement,
        unit=None,
        scope={"corporation": corporation, "kind": "log"},
        breakdown=None,
        verification="pending",
        citation=_citation(cid),
    )


def _incidents(corporation: str, breakdown: dict, cid: str = "C002") -> Fact:
    return Fact(
        metric="corporation_status",
        value=sum(breakdown.values()),
        unit="incidents",
        scope={"corporation": corporation, "kind": "incidents"},
        breakdown=breakdown,
        verification="pending",
        citation=_citation(cid),
    )


def _render(facts=(), params=None, include_citations=False) -> str:
    table = FactTable(
        request_id="r",
        template="minister_situation_report",
        params=PARAMS if params is None else params,
        generated_at=datetime(2023, 5, 5, 19, tzinfo=timezone.utc),
        facts=list(facts),
        gaps=[],
    )
    return render_report(
        get_template("minister_situation_report"), table, "", include_citations=include_citations
    )


def test_header_follows_the_baseline():
    md = _render()

    assert md.startswith("# ADVERSE WEATHER SITUATION REPORT\n")
    assert "**As at:** 3:00 pm on 05/05/2023" in md
    assert "**Location:** Ministry of Rural Development and Local Government, Kent House" in md
    assert "**Present Activity:** Notification Alert" in md
    assert "**Alert Level:** Adverse Weather Alert #1 - Green Level" in md
    assert "## Situation Overview\n\nA tropical wave is approaching." in md


def test_every_corporation_has_a_section_in_order():
    md = _render()

    headings = re.findall(r"^## (.+)$", md, re.M)
    corporations = [h for h in headings if h in CORPORATION_LABELS.values()]
    assert corporations == list(CORPORATION_LABELS.values())
    assert len(corporations) == 14


def test_silent_corporation_reads_no_reports():
    md = _render([_log(ARIMA, "CERT on standby")])

    assert f"## {CORPORATION_LABELS[SIPARIA]}\n\n- No reports at this time." in md
    assert "No reports" not in md.split(f"## {CORPORATION_LABELS[ARIMA]}")[1].split("##")[0]


def test_log_statements_are_verbatim_bullets():
    md = _render([_log(ARIMA, "200 sandbags available for distribution")])

    assert (
        f"## {CORPORATION_LABELS[ARIMA]}\n\n- 200 sandbags available for distribution\n" in md
    )


def test_incident_line_orders_by_count():
    md = _render([_incidents(ARIMA, {"landslide": 2, "flooding_": 4})])

    assert "- Incidents reported: Flooding 4, Landslide 2" in md


def test_final_has_no_citations_and_draft_does():
    facts = [_log(ARIMA, "CERT on standby")]

    assert "[C" not in _render(facts)
    assert "- CERT on standby [C001]" in _render(facts, include_citations=True)


def test_ministry_response_closes_the_report():
    md = _render()

    assert md.index(CORPORATION_LABELS[SIPARIA]) < md.index("## Response from the Ministry")
    assert "A coordinators' meeting was held at 1pm." in md
    assert md.rstrip().endswith("END OF REPORT")


def test_blank_optional_fields_are_left_out():
    md = _render(params={"date_from": "2023-05-05", "date_to": "2023-05-05"})

    assert md.startswith("# SITUATION REPORT\n")
    assert "Present Activity" not in md
    assert "Alert Level" not in md
    assert "Situation Overview" not in md
    assert "Response from the Ministry" not in md


def test_missing_as_at_uses_the_generation_time():
    md = _render(params={"date_from": "2023-05-05", "date_to": "2023-05-05"})

    assert "**As at:** 3:00 pm on 05/05/2023" in md


def test_minister_template_reads_only_sitreps_and_skips_the_llm():
    template = get_template("minister_situation_report")

    assert {r.module for r in template.data_requirements} == {"sitreps"}
    assert [r.metric for r in template.data_requirements] == ["corporation_status"]
    assert template.narration.output_sections == []
    assert template.render.layout == "ministerial"


def test_long_text_params_are_multiline():
    params = {p.name: p for p in get_template("minister_situation_report").params}

    assert params["situation_overview"].multiline is True
    assert params["ministry_response"].multiline is True
    assert params["as_at"].multiline is False
