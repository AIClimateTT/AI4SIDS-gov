from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.db import Base, make_engine
from app.modules.survey123.metrics import (
    base_query,
    build_citation,
    build_query_ref,
    build_scope,
    build_window_label,
    determine_verification,
    parse_date_param,
)
from app.modules.survey123.models import Incident


def test_parse_date_param_none_is_none():
    assert parse_date_param(None) is None


def test_parse_date_param_string_parses_to_datetime():
    assert parse_date_param("2024-06-15") == datetime(2024, 6, 15)


def test_parse_date_param_datetime_passes_through():
    dt = datetime(2024, 6, 15, 12, 30)
    assert parse_date_param(dt) is dt


def test_build_window_label_no_dates_is_all():
    assert build_window_label(None, None) == "all"


def test_build_window_label_from_only():
    assert build_window_label("2024-06-15", None) == "2024-06-15..latest"


def test_build_window_label_both_dates():
    assert build_window_label("2024-06-01", "2024-06-30") == "2024-06-01..2024-06-30"


def test_build_scope_defaults_to_all():
    assert build_scope({}) == {"corporation": "all", "community": "all", "window": "all"}


def test_build_scope_reflects_filters():
    scope = build_scope({"corporation": "sangre_grande_regional_corporat", "community": "Sangre Grande", "date_from": "2024-06-01"})
    assert scope == {
        "corporation": "sangre_grande_regional_corporat",
        "community": "Sangre Grande",
        "window": "2024-06-01..latest",
    }


def test_build_scope_extra_kwargs_override():
    scope = build_scope({}, category="injuries")
    assert scope["category"] == "injuries"
    assert scope["corporation"] == "all"


def test_build_query_ref_is_deterministic_and_excludes_none_values():
    ref_a = build_query_ref("incident_count", {"corporation": "sangre_grande_regional_corporat", "community": None, "date_from": None, "date_to": None, "include_pending": False})
    ref_b = build_query_ref("incident_count", {"corporation": "sangre_grande_regional_corporat"})
    assert ref_a == ref_b
    assert "community" not in ref_a


def test_build_query_ref_differs_for_different_params():
    ref_a = build_query_ref("incident_count", {"corporation": "sangre_grande_regional_corporat"})
    ref_b = build_query_ref("incident_count", {"corporation": "san_fernando_city_corporation"})
    assert ref_a != ref_b


def test_determine_verification_all_validated():
    assert determine_verification(["validated", "validated"]) == "validated"


def test_determine_verification_all_pending():
    assert determine_verification(["pending", "pending"]) == "pending"


def test_determine_verification_mixed():
    assert determine_verification(["validated", "pending"]) == "mixed"


def test_determine_verification_empty_is_na():
    assert determine_verification([]) == "n/a"


def test_build_citation_keeps_record_ids_at_or_below_200():
    global_ids = [f"GUID-{i:04d}" for i in range(200)]

    citation = build_citation("incident_count", 0, {}, global_ids, "test description")

    assert citation.record_ids is not None
    assert len(citation.record_ids) == 200
    assert citation.cid == "survey123-incident_count-0"
    assert citation.module == "survey123"
    assert citation.description == "test description"


def test_build_citation_caps_record_ids_above_200():
    global_ids = [f"GUID-{i:04d}" for i in range(250)]

    citation = build_citation("incident_count", 0, {}, global_ids, "test description")

    assert citation.record_ids is None


def make_session(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


def make_incident(**overrides) -> Incident:
    defaults = dict(
        global_id="GUID-DEFAULT",
        object_id=1,
        corporation="sangre_grande_regional_corporat",
        raw_corporation=None,
        community="Sangre Grande",
        street="Test Street",
        incident_type="flooding_",
        raw_incident_type=None,
        incident_type_other=None,
        incident_summary=None,
        event_date=datetime(2024, 6, 1),
        event_time=None,
        assessment_date=None,
        creation_date=datetime(2024, 6, 1),
        edit_date=datetime(2024, 6, 1),
        occupants_count=None,
        injuries_occurred=False,
        injuries_count=None,
        deaths_occurred=False,
        deaths_count=None,
        building_damage=None,
        crops_livestock=None,
        personal_items=None,
        furniture_appliances=None,
        action_taken=None,
        relief_items=None,
        shelter=None,
        special_needs_occupants=None,
        estimated_damage_cost=None,
        follow_up=None,
        follow_up_flags={"relief_supplied": False, "forwarded_to_agency": False, "further_assessment_required": False, "other": False},
        validation_status="validated",
        is_duplicate=False,
        duplicate_reason=None,
        flood_type=None,
        flood_trigger=None,
        flood_height=None,
        lon=None,
        lat=None,
        officer_name=None,
        officer_position=None,
        dedup_hash=None,
        source_file="test.csv",
        ingested_at=datetime(2024, 6, 1),
    )
    defaults.update(overrides)
    return Incident(**defaults)


def test_base_query_excludes_duplicates(tmp_path):
    session = make_session(tmp_path)
    session.add(make_incident(global_id="G1", is_duplicate=False))
    session.add(make_incident(global_id="G2", is_duplicate=True))
    session.commit()

    rows = session.execute(base_query({})).scalars().all()

    assert [r.global_id for r in rows] == ["G1"]


def test_base_query_excludes_pending_by_default(tmp_path):
    session = make_session(tmp_path)
    session.add(make_incident(global_id="G1", validation_status="validated"))
    session.add(make_incident(global_id="G2", validation_status="pending"))
    session.commit()

    rows = session.execute(base_query({})).scalars().all()

    assert [r.global_id for r in rows] == ["G1"]


def test_base_query_include_pending_true_includes_both(tmp_path):
    session = make_session(tmp_path)
    session.add(make_incident(global_id="G1", validation_status="validated"))
    session.add(make_incident(global_id="G2", validation_status="pending"))
    session.commit()

    rows = session.execute(base_query({"include_pending": True})).scalars().all()

    assert sorted(r.global_id for r in rows) == ["G1", "G2"]


def test_base_query_filters_by_corporation(tmp_path):
    session = make_session(tmp_path)
    session.add(make_incident(global_id="G1", corporation="sangre_grande_regional_corporat"))
    session.add(make_incident(global_id="G2", corporation="san_fernando_city_corporation"))
    session.commit()

    rows = session.execute(base_query({"corporation": "san_fernando_city_corporation"})).scalars().all()

    assert [r.global_id for r in rows] == ["G2"]


def test_base_query_filters_by_date_range(tmp_path):
    session = make_session(tmp_path)
    session.add(make_incident(global_id="G1", event_date=datetime(2024, 6, 1)))
    session.add(make_incident(global_id="G2", event_date=datetime(2024, 6, 20)))
    session.commit()

    rows = session.execute(base_query({"date_from": "2024-06-10"})).scalars().all()

    assert [r.global_id for r in rows] == ["G2"]
