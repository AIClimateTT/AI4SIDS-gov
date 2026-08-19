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


def test_stale_manual_path_does_not_freeze_an_unrelated_row_after_id_recycling():
    """A row can vanish from `previous` while its manual_fields path lingers
    (e.g. it was deleted through some other flow). If that stale path is not
    dropped, a later turn's unrelated row can be assigned the same row_id by
    `_assign_row_ids` (which recycles the lowest free integer) and inherit a
    pin that was never about it, freezing that field forever.

    Pinning must drop a manual path the moment its row is absent from
    `previous`, so a recycled id starts clean rather than reactivating a
    stale pin on the next turn.
    """
    previous = CaptureWorkingSet(incidents=[], manual_fields=["incident:7.injuries_count"])
    model_said = CaptureWorkingSet(incidents=[CaptureIncident(row_id="7", injuries_count=2)])

    turn_1 = pin_manual_fields(model_said, previous)
    assert turn_1.incidents[0].injuries_count == 2
    assert turn_1.manual_fields == []

    turn_2 = pin_manual_fields(
        CaptureWorkingSet(incidents=[CaptureIncident(row_id="7", injuries_count=9)]),
        turn_1,
    )
    assert turn_2.incidents[0].injuries_count == 9


def test_KNOWN_LIMITATION_dropped_row_id_on_a_pinned_row_creates_a_duplicate():
    """If the model re-emits a manually-pinned incident but omits its
    row_id, intake (`_assign_row_ids`, in turn.py) treats it as a brand-new
    row and assigns it a fresh id. That fresh-id row has no prior under its
    new id, so it passes through unpinned, and the vanish-protection branch
    below also restores the original row under its old id — one incident
    becomes two, and any count field on it double-counts.

    This is a deliberate trade-off, not a bug: an officer-entered incident
    must never silently vanish, and a visible duplicate is recoverable while
    a silent deletion is not. A later review-before-filing step is
    responsible for surfacing duplicates to a human. Do not "fix" this with
    content-based row matching.
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
    # The model re-sends the same incident with no row_id; upstream row_id
    # assignment (not exercised here) would hand it a fresh id such as "2".
    model_said = CaptureWorkingSet(
        incidents=[
            CaptureIncident(
                row_id="2",
                community="Petit Valley",
                incident_summary="Petit Valley flooding",
                injuries_count=0,
            )
        ]
    )
    pinned = pin_manual_fields(model_said, previous)
    assert [row.row_id for row in pinned.incidents] == ["2", "1"]
    assert pinned.incidents[0].injuries_count == 0  # the new, unpinned duplicate
    assert pinned.incidents[1].injuries_count == 4  # the original, still pinned


def test_manual_path_naming_an_unknown_field_does_not_resurrect_a_dropped_row():
    previous = CaptureWorkingSet(
        incidents=[CaptureIncident(row_id="3", incident_summary="model wrote this")],
        manual_fields=["incident:3.not_a_real_field"],
    )
    model_said = CaptureWorkingSet(incidents=[])
    pinned = pin_manual_fields(model_said, previous)
    assert pinned.incidents == []


def test_pin_manual_fields_is_a_no_op_when_nothing_is_manual():
    previous = CaptureWorkingSet()
    model_said = CaptureWorkingSet(alert_level="yellow", present_activity="Heavy rainfall")
    pinned = pin_manual_fields(model_said, previous)
    assert pinned.alert_level == "yellow"
    assert pinned.present_activity == "Heavy rainfall"
    assert pinned.manual_fields == []


def test_a_dropped_row_with_no_manual_paths_is_not_restored():
    previous = CaptureWorkingSet(
        alert_level="red",
        incidents=[
            CaptureIncident(row_id="3", incident_summary="model wrote this, untouched")
        ],
        manual_fields=["alert_level"],
    )
    model_said = CaptureWorkingSet(alert_level="yellow", incidents=[])
    pinned = pin_manual_fields(model_said, previous)
    assert pinned.incidents == []
