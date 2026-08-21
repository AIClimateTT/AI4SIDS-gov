from datetime import datetime

from app.core.llm import FakeLLMClient
from app.modules.capture.schemas import CaptureIncident, CaptureLog, CaptureWorkingSet
from app.modules.capture.sitrep import generate_working_set_sitrep, sitrep_preamble
from app.templates.loader import load_template
from pathlib import Path

TEMPLATE = load_template(
    Path(__file__).parent.parent / "app/templates/definitions/corp_sitrep_single.yaml"
)


def test_preamble_renders_verbatim_overview_and_logs():
    text = sitrep_preamble(
        event_title="Flooding in Arima",
        alert_level="yellow",
        as_at=datetime(2026, 8, 21, 12, 0),
        situation_overview="River overtopped overnight.",
        present_activity="Shelter open.",
        logs=[CaptureLog(row_id="1", category="activity", statement="Sandbagging on Queen Street")],
    )
    assert "Flooding in Arima" in text
    assert "River overtopped overnight." in text
    assert "Sandbagging on Queen Street" in text
    assert "None" not in text


def test_working_set_sitrep_markdown_cites_incident_count():
    working = CaptureWorkingSet(
        as_at=datetime(2026, 8, 21, 12),
        alert_level="yellow",
        present_activity="Shelter open.",
        situation_overview="River overtopped overnight.",
        incidents=[
            CaptureIncident(
                row_id="1",
                community="Arima",
                incident_type="flooding",
                incident_summary="Five houses flooded",
                injuries_count=0,
                deaths_count=0,
            )
        ],
        logs=[],
        manual_fields=[],
    )
    report = generate_working_set_sitrep(
        working,
        corporation="arima_borough_corporation",
        event_id=2,
        event_title="Flooding in Arima",
        template=TEMPLATE,
        llm_client=FakeLLMClient(),
        request_id="preview-test",
    )
    assert "Flooding in Arima" in report.markdown
    assert "River overtopped overnight." in report.markdown
    assert "[C001]" in report.markdown
    assert report.fact_table.facts[0].citation.cid == "C001"
