from datetime import datetime

from app.modules.whatsapp.extract import DraftIncident, DraftLog, WhatsAppWorkingSet
from app.modules.whatsapp.missing import missing_fields
from app.modules.whatsapp.provenance import (
    SESSION_FIELDS,
    incident_path,
    log_path,
    pin_manual_fields,
    row_paths,
)

CORP = "diego_martin_regional_corporati"


def _incident(**overrides) -> DraftIncident:
    base = dict(
        row_id="1",
        corporation=CORP,
        incident_summary="flooding on Main Street",
        source_index=1,
        source_quote="flooding on Main Street",
        included=True,
    )
    base.update(overrides)
    return DraftIncident(**base)


def test_paths_are_namespaced_by_kind():
    assert incident_path("3", "corporation") == "incident:3.corporation"
    assert log_path("3", "quantity") == "log:3.quantity"


def test_session_fields_cover_as_at_only():
    assert SESSION_FIELDS == ("as_at",)


def test_row_paths_selects_only_the_named_row_and_kind():
    manual = {
        "incident:1.corporation",
        "incident:1.injuries_count",
        "incident:2.deaths_count",
        "log:1.quantity",
        "as_at",
    }
    assert row_paths(manual, "incident", "1") == {"corporation", "injuries_count"}
    assert row_paths(manual, "log", "1") == {"quantity"}
    assert row_paths(manual, "incident", "9") == set()


def test_manual_corporation_survives_a_model_rewrite():
    previous = WhatsAppWorkingSet(
        incidents=[_incident(corporation=CORP)],
        manual_fields=["incident:1.corporation"],
    )
    model_said = WhatsAppWorkingSet(
        incidents=[_incident(corporation="siparia_regional_corporation")]
    )
    pinned = pin_manual_fields(model_said, previous)
    assert pinned.incidents[0].corporation == CORP


def test_manual_incident_field_survives_and_siblings_do_not():
    previous = WhatsAppWorkingSet(
        incidents=[_incident(injuries_count=4, incident_summary="model text")],
        manual_fields=["incident:1.injuries_count"],
    )
    model_said = WhatsAppWorkingSet(
        incidents=[_incident(injuries_count=0, incident_summary="new model text")]
    )
    pinned = pin_manual_fields(model_said, previous)
    assert pinned.incidents[0].injuries_count == 4
    assert pinned.incidents[0].incident_summary == "new model text"


def test_a_hand_added_row_the_model_dropped_is_restored():
    previous = WhatsAppWorkingSet(
        incidents=[_incident(row_id="7", incident_summary="Typed by hand")],
        logs=[
            DraftLog(
                row_id="2",
                corporation=CORP,
                statement="Typed by hand",
                source_index=2,
                source_quote="Typed by hand",
                included=True,
            )
        ],
        manual_fields=["incident:7.incident_summary", "log:2.statement"],
    )
    model_said = WhatsAppWorkingSet(incidents=[], logs=[])
    pinned = pin_manual_fields(model_said, previous)
    assert [row.row_id for row in pinned.incidents] == ["7"]
    assert [row.row_id for row in pinned.logs] == ["2"]


def test_stale_manual_path_does_not_freeze_an_unrelated_row_after_id_recycling():
    previous = WhatsAppWorkingSet(
        incidents=[], manual_fields=["incident:7.injuries_count"]
    )
    model_said = WhatsAppWorkingSet(incidents=[_incident(row_id="7", injuries_count=2)])

    turn_1 = pin_manual_fields(model_said, previous)
    assert turn_1.incidents[0].injuries_count == 2
    assert turn_1.manual_fields == []


def test_manual_as_at_survives_a_model_rewrite():
    previous = WhatsAppWorkingSet(
        as_at=datetime(2026, 8, 15, 16, 0),
        manual_fields=["as_at"],
    )
    model_said = WhatsAppWorkingSet(as_at=datetime(2026, 8, 16, 9, 0))
    pinned = pin_manual_fields(model_said, previous)
    assert pinned.as_at == datetime(2026, 8, 15, 16, 0)


def test_unattributed_row_is_reported_missing_corporation():
    working = WhatsAppWorkingSet(
        incidents=[_incident(corporation=None, included=False)]
    )
    paths = {item.path: item.message for item in missing_fields(working)}
    assert paths["incident:1.corporation"] == "Assign a corporation"
    assert not any("alert" in item.message.lower() for item in missing_fields(working))


def test_included_row_with_empty_summary_is_missing():
    working = WhatsAppWorkingSet(
        incidents=[_incident(incident_summary="   ")]
    )
    paths = {item.path for item in missing_fields(working)}
    assert "incident:1.incident_summary" in paths
