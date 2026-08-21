from types import SimpleNamespace
from datetime import datetime, timezone

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
