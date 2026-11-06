from datetime import datetime

from app.core.citation_check import CITATION_MARKER_RE
from app.modules.capture.schemas import CaptureIncident, CaptureLog, CaptureWorkingSet
from app.modules.capture.sitrep import generate_working_set_sitrep
from app.templates.loader import load_template
from pathlib import Path

TEMPLATE = load_template(
    Path(__file__).parent.parent / "app/templates/definitions/corp_situation_report.yaml"
)


def _arima_working() -> CaptureWorkingSet:
    return CaptureWorkingSet(
        as_at=datetime(2026, 8, 21, 20, 3),
        alert_level="yellow",
        alert_detail="Flood Alert #1 - Yellow Level",
        present_activity="Officers dispatched to aid and transport an injured individual",
        situation_overview="The MET Office issued a yellow level warning for flooding on Tumpuna Road.",
        incidents=[
            CaptureIncident(
                row_id="1",
                street="Tumpuna Road",
                incident_type="flooding_",
                incident_summary="Flooding on streets of Tumpuna Road",
                event_date="2026-08-21",
                injuries_count=1,
                deaths_count=None,
            ),
            CaptureIncident(
                row_id="2",
                incident_type="blown_off_roof",
                incident_summary="5 roofs were blown off",
                event_date="2026-08-21",
                injuries_count=1,
                deaths_count=1,
            ),
            CaptureIncident(
                row_id="3",
                incident_type="fallen_tree",
                incident_summary="Fallen tree caused 2 deaths",
                event_date="2026-08-21",
                injuries_count=None,
                deaths_count=2,
            ),
        ],
        logs=[
            CaptureLog(
                row_id="1",
                category="relief_distributed",
                statement="Tarpaulin distribution",
                item="tarpaulins",
                quantity=10,
                unit="units",
                status="completed",
            ),
            CaptureLog(
                row_id="2",
                category="relief_distributed",
                statement="Sandbag distribution",
                item="sandbags",
                quantity=50,
                unit="bags",
                status="completed",
            ),
            CaptureLog(
                row_id="3",
                category="resource",
                statement="Tarpaulin stock remaining",
                item="tarpaulins",
                quantity=20,
                unit="units",
                status="in_stock",
            ),
            CaptureLog(
                row_id="4",
                category="resource",
                statement="Sandbag stock remaining",
                item="sandbags",
                quantity=100,
                unit="bags",
                status="in_stock",
            ),
            CaptureLog(
                row_id="5",
                category="activity",
                statement="Officers dispatched to aid injured individual for medical transport",
                status="completed",
            ),
        ],
        manual_fields=[],
    )


class _NoLLM:
    def generate(self, system_prompt: str, user_content: str) -> str:
        raise AssertionError("the corporation sitrep must not call the LLM")


def _report(working=None):
    return generate_working_set_sitrep(
        working or _arima_working(),
        corporation="arima_borough_corporation",
        event_id=1,
        hazard_type="adverse_weather",
        report_number=2,
        template=TEMPLATE,
        llm_client=_NoLLM(),
        request_id="arima-golden",
    )


def _section(text: str, heading: str) -> str:
    return text.split(f"## {heading}", 1)[1].split("\n## ", 1)[0]


def test_header_follows_the_baseline():
    text = _report().final_markdown

    assert text.startswith("# ADVERSE WEATHER SITUATION REPORT #2\n")
    assert "**As at:** 8:03 pm on 21/08/2026" in text
    assert "**Location:** Arima Borough Corporation" in text
    assert "**Present Activity:** Officers dispatched to aid and transport an injured individual" in text
    assert "**Alert Level:** Flood Alert #1 - Yellow Level" in text
    assert "## Situation Overview\n\nThe MET Office issued a yellow level warning" in text


def test_sections_appear_in_baseline_order():
    text = _report().final_markdown

    headings = [line[3:] for line in text.splitlines() if line.startswith("## ")]
    assert headings == [
        "Situation Overview",
        "Situation Summary",
        "Disaster Relief Distribution Summary",
        "Resources",
        "Summary of Activities",
        "Incidents",
    ]


def test_relief_distributed_is_separate_from_stock_on_hand():
    text = _report().final_markdown

    distributed = _section(text, "Disaster Relief Distribution Summary")
    resources = _section(text, "Resources")
    assert "| 10 |" in distributed and "| 50 |" in distributed
    assert "| 20 |" not in distributed and "| 100 |" not in distributed
    assert "| 20 |" in resources and "| 100 |" in resources
    assert "In Stock" in resources


def test_incidents_are_numbered_from_one():
    rows = [
        line
        for line in _section(_report().final_markdown, "Incidents").splitlines()
        if line.startswith("| ")
    ]

    assert rows[0].startswith("| No. | Date | Location | Type | Description |")
    assert "Action Taken" not in rows[0]  # the working set records no action
    assert rows[1].startswith("| 1 | 2026-08-21 | Tumpuna Road |")
    assert rows[3].startswith("| 3 |")


def test_issued_report_has_no_gaps_section_or_citations_but_the_draft_does():
    report = _report()

    assert "Data Gaps" not in report.final_markdown
    assert "Information not yet available" not in report.final_markdown
    assert not CITATION_MARKER_RE.search(report.final_markdown)
    assert "## Data Gaps" in report.markdown
    assert "not recorded" in report.markdown
    assert "[C" in report.markdown


def test_closing_line_marks_a_running_or_final_report():
    assert _report().final_markdown.rstrip().endswith("END OF REPORT")

    final = _arima_working().model_copy(update={"alert_level": "discontinued"})
    assert _report(final).final_markdown.rstrip().endswith(
        "No further reports to be submitted."
    )


def test_alert_level_is_used_when_the_officer_gave_no_wording():
    working = _arima_working().model_copy(update={"alert_detail": None})

    assert "**Alert Level:** Yellow" in _report(working).final_markdown


def test_officer_text_with_a_backslash_survives():
    working = _arima_working().model_copy(update={"situation_overview": r"Road C:\1 closed"})

    assert r"Road C:\1 closed" in _report(working).final_markdown
