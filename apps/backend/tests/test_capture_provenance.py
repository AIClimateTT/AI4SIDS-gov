from app.modules.capture.provenance import (
    SESSION_FIELDS,
    incident_path,
    log_path,
    row_paths,
)


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
