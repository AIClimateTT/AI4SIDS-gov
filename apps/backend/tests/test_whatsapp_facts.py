from datetime import datetime

from app.modules.whatsapp.extract import DraftIncident, DraftLog
from app.modules.whatsapp.facts import facts_from_working_set

CORP = "diego_martin_regional_corporati"
OTHER = "sangre_grande_regional_corporat"
AS_AT = datetime(2026, 8, 15, 16, 0)


def test_skips_unattributed_and_excluded_rows():
    fact_table = facts_from_working_set(
        incidents=[
            DraftIncident(
                corporation=CORP,
                incident_summary="kept",
                injuries_count=1,
                source_index=1,
                source_quote="1 injury",
                included=True,
            ),
            DraftIncident(
                corporation=None,
                incident_summary="no corp",
                source_index=2,
                source_quote="no corp",
                included=True,
            ),
            DraftIncident(
                corporation=OTHER,
                incident_summary="dropped",
                source_index=3,
                source_quote="dropped",
                included=False,
            ),
        ],
        logs=[
            DraftLog(
                corporation=CORP,
                statement="200 sandbags remaining",
                quantity=200,
                unit="bags",
                source_index=4,
                source_quote="200 sandbags remaining",
                included=True,
            ),
            DraftLog(
                corporation=CORP,
                statement="old",
                quantity=50,
                source_index=5,
                source_quote="50",
                included=False,
            ),
        ],
        as_at=AS_AT,
        request_id="req-1",
    )

    assert len(fact_table.facts) == 2
    assert fact_table.facts[0].value == 1
    assert fact_table.facts[0].verification == "pending"
    assert fact_table.facts[0].citation.module == "whatsapp"
    assert fact_table.facts[1].value == 200
    assert "unconfirmed" in fact_table.facts[0].citation.description
