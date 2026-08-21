from types import SimpleNamespace
from datetime import datetime, timezone

from app.modules.capture.facts import assemble_working_set_facts
from app.modules.capture.schemas import CaptureIncident, CaptureWorkingSet
from app.modules.sitreps.models import SitrepIncident
from app.modules.survey123.metrics import incident_count


def test_incident_count_accepts_preloaded_rows():
    row = SimpleNamespace(
        corporation="diego_martin_regional_corporati",
        event_id=1,
        row_id="1",
        incident_type="flooding",
        community="Petit Valley",
        street=None,
        event_date=datetime(2026, 8, 18),
        injuries_occurred=False,
        injuries_count=0,
        deaths_occurred=False,
        deaths_count=0,
        building_damage=None,
        special_needs_occupants=0,
        estimated_damage_cost=None,
        follow_up_flags={},
        validation_status="validated",
        record_ref="diego_martin_regional_corporati:1:1",
        global_id=None,
    )
    facts = incident_count(
        {"corporation": "diego_martin_regional_corporati"},
        session=None,
        model=SitrepIncident,
        rows=[row],
    )
    assert facts[0].value == 1


def _working() -> CaptureWorkingSet:
    return CaptureWorkingSet(
        as_at=datetime(2026, 8, 21, 12),
        alert_level="yellow",
        present_activity="Shelter open",
        situation_overview="River overtopped",
        incidents=[
            CaptureIncident(
                row_id="1",
                community="Arima",
                street="Queen Street",
                incident_type="flooding",
                incident_summary="Five houses flooded",
                event_date="2026-08-21",
                injuries_occurred=True,
                injuries_count=1,
                deaths_occurred=False,
                deaths_count=0,
                special_needs_occupants=0,
                relief_supplied=True,
            )
        ],
        logs=[],
        manual_fields=[],
    )


def test_working_set_facts_count_the_captured_incident():
    facts = assemble_working_set_facts(
        _working(),
        corporation="arima_borough_corporation",
        event_id=2,
    )
    by_metric = {f.metric: f for f in facts}
    assert by_metric["incident_count"].value == 1
    injuries = next(
        f
        for f in facts
        if f.metric == "casualty_summary" and f.scope.get("category") == "injuries"
    )
    assert injuries.value == 1

