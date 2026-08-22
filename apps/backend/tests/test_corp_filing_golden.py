from datetime import datetime

from app.core.llm import FakeLLMClient
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


def test_arima_filing_tables_match_the_working_set():
    report = generate_working_set_sitrep(
        _arima_working(),
        corporation="arima_borough_corporation",
        event_id=1,
        event_title="Flooding in Arima",
        template=TEMPLATE,
        llm_client=FakeLLMClient(
            responses=[
                "Flooding continues on Tumpuna Road, with roofs blown off and a fallen tree. "
                "Casualties: 2 injured and 3 dead [C005] [C006]."
            ]
        ),
        request_id="arima-golden",
    )
    text = report.markdown
    assert "Flooding in Arima" in text
    assert "| 10 |" in text
    assert "| 50 |" in text
    assert "| 20 |" in text
    assert "| 100 |" in text
    assert "Special Needs Count" not in text
    assert "Estimated Damage Total" not in text
    assert "Fallen tree caused 2 deaths" in text
    assert "Tumpuna Road" in text
    assert "Officers dispatched to aid injured individual for medical transport" in text
    lowered = text.lower()
    assert "no relief" not in lowered
    assert "unknown street" not in lowered
    assert "every category shows zero" not in lowered
    assert "## Data Gaps" in text
    assert "not recorded" in text
    assert "None." not in text.split("## Data Gaps", 1)[1].split("##", 1)[0]
