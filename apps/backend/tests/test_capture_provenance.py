from app.modules.capture.provenance import (
    SESSION_FIELDS,
    incident_path,
    log_path,
    pin_manual_fields,
    row_paths,
)
from app.modules.capture.schemas import CaptureIncident, CaptureLog, CaptureWorkingSet


def test_paths_are_namespaced_by_kind():
    assert incident_path("3", "injuries_count") == "incident:3.injuries_count"
    assert log_path("3", "quantity") == "log:3.quantity"


def test_session_fields_cover_the_editable_header():
    assert SESSION_FIELDS == (
        "as_at",
        "alert_level",
        "present_activity",
        "situation_overview",
    )


def test_row_paths_selects_only_the_named_row_and_kind():
    manual = {
        "incident:1.injuries_count",
        "incident:1.community",
        "incident:2.deaths_count",
        "log:1.quantity",
        "alert_level",
    }
    assert row_paths(manual, "incident", "1") == {"injuries_count", "community"}
    assert row_paths(manual, "log", "1") == {"quantity"}
    assert row_paths(manual, "incident", "9") == set()


def test_manual_session_field_survives_a_model_rewrite():
    previous = CaptureWorkingSet(
        alert_level="red",
        situation_overview="Officer's own words",
        manual_fields=["alert_level", "situation_overview"],
    )
    model_said = CaptureWorkingSet(
        alert_level="yellow", situation_overview="Rewritten by the model"
    )
    pinned = pin_manual_fields(model_said, previous)
    assert pinned.alert_level == "red"
    assert pinned.situation_overview == "Officer's own words"


def test_model_may_still_write_fields_never_touched_by_hand():
    previous = CaptureWorkingSet(alert_level="red", manual_fields=["alert_level"])
    model_said = CaptureWorkingSet(alert_level="yellow", present_activity="Heavy rainfall")
    pinned = pin_manual_fields(model_said, previous)
    assert pinned.alert_level == "red"
    assert pinned.present_activity == "Heavy rainfall"


def test_manual_incident_field_survives_and_siblings_do_not():
    previous = CaptureWorkingSet(
        incidents=[
            CaptureIncident(row_id="1", injuries_count=4, incident_summary="model text")
        ],
        manual_fields=["incident:1.injuries_count"],
    )
    model_said = CaptureWorkingSet(
        incidents=[
            CaptureIncident(row_id="1", injuries_count=0, incident_summary="new model text")
        ]
    )
    pinned = pin_manual_fields(model_said, previous)
    assert pinned.incidents[0].injuries_count == 4
    assert pinned.incidents[0].incident_summary == "new model text"


def test_a_hand_added_row_the_model_dropped_is_restored():
    previous = CaptureWorkingSet(
        incidents=[CaptureIncident(row_id="7", incident_summary="Typed by hand")],
        logs=[CaptureLog(row_id="2", statement="Typed by hand", category="resource")],
        manual_fields=["incident:7.incident_summary", "log:2.statement"],
    )
    model_said = CaptureWorkingSet(incidents=[], logs=[])
    pinned = pin_manual_fields(model_said, previous)
    assert [row.row_id for row in pinned.incidents] == ["7"]
    assert [row.row_id for row in pinned.logs] == ["2"]


def test_manual_fields_carry_forward_untouched():
    previous = CaptureWorkingSet(manual_fields=["alert_level"])
    pinned = pin_manual_fields(CaptureWorkingSet(), previous)
    assert pinned.manual_fields == ["alert_level"]


def test_KNOWN_LIMITATION_reused_row_id_for_a_different_row_inherits_the_manual_pin():
    """Pinning is id-based, not content-based. If the model reuses row_id "1"
    for a semantically different row (previous "1" was Petit Valley flooding,
    hand-corrected injuries_count=4; the model's new "1" is an unrelated tree
    down on Saddle Rd), the manual value is stamped onto the unrelated row.

    This is an accepted limitation of id-based pinning, not a bug: fixing it
    would require fuzzy content matching, which is worse. Do not "fix" this by
    changing pin_manual_fields — it documents intended behaviour.
    """
    previous = CaptureWorkingSet(
        incidents=[
            CaptureIncident(
                row_id="1",
                community="Petit Valley",
                incident_summary="Petit Valley flooding",
                injuries_count=4,
            )
        ],
        manual_fields=["incident:1.injuries_count"],
    )
    model_said = CaptureWorkingSet(
        incidents=[
            CaptureIncident(
                row_id="1",
                community="Saddle Rd",
                incident_summary="tree down on Saddle Rd",
                injuries_count=0,
            )
        ]
    )
    pinned = pin_manual_fields(model_said, previous)
    assert pinned.incidents[0].incident_summary == "tree down on Saddle Rd"
    assert pinned.incidents[0].injuries_count == 4
