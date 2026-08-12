from datetime import datetime

import pytest
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
from app.modules.survey123.models import FieldObservation


def test_parse_date_param_none_is_none():
    assert parse_date_param(None) is None


def test_parse_date_param_string_parses_to_datetime():
    assert parse_date_param("2024-06-15") == datetime(2024, 6, 15)


def test_parse_date_param_datetime_passes_through():
    dt = datetime(2024, 6, 15, 12, 30)
    assert parse_date_param(dt) is dt


def test_parse_date_param_blank_string_is_none():
    # The Generate Report form seeds every optional param to "".
    # datetime.fromisoformat("") raises ValueError, which the API turns into a
    # 400 — a blank date_from used to reject the whole request.
    assert parse_date_param("") is None


def test_build_window_label_no_dates_is_all():
    assert build_window_label(None, None) == "all"


def test_build_window_label_blank_dates_is_all():
    assert build_window_label("", "") == "all"


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


def test_build_query_ref_omits_blank_values():
    # A blank narrows nothing (apply_common_filters ignores it), so printing
    # "community=" would advertise a filter that never ran to the auditor
    # reproducing the figure.
    ref_blank = build_query_ref(
        "incident_count",
        {"corporation": "sangre_grande_regional_corporat", "community": "", "date_from": ""},
    )
    ref_omitted = build_query_ref(
        "incident_count", {"corporation": "sangre_grande_regional_corporat"}
    )

    assert ref_blank == ref_omitted
    assert "community" not in ref_blank
    assert "date_from" not in ref_blank


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

    citation = build_citation("incident_count", 0, {}, global_ids, "test description", FieldObservation)

    assert citation.record_ids is not None
    assert len(citation.record_ids) == 200
    assert citation.cid == "survey123-incident_count-0"
    assert citation.module == "survey123"
    assert citation.description == "test description"


def test_build_citation_keeps_all_record_ids_above_200():
    # No cap: the old `ordered[:200] if len(ordered) <= 200 else None` was a
    # no-op below 200 and discarded every id above it — silently erasing
    # provenance for large result sets, the opposite of what a citation is for.
    global_ids = [f"GUID-{i:04d}" for i in range(250)]

    citation = build_citation("incident_count", 0, {}, global_ids, "test description", FieldObservation)

    assert citation.record_ids is not None
    assert len(citation.record_ids) == 250


def make_session(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


def make_incident(**overrides) -> FieldObservation:
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
        action_taken="action_taken",
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
        dedup_hash=None,
        source_file="test.csv",
        ingested_at=datetime(2024, 6, 1),
    )
    defaults.update(overrides)
    return FieldObservation(**defaults)


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


def test_base_query_date_to_is_inclusive_of_the_whole_day(tmp_path):
    # Real Survey123 exports carry a time of day on event_date (e.g. 14:35:00),
    # not just midnight — a naive `event_date <= date_to` (parsed to midnight)
    # would silently drop every incident that happened later on the last day
    # of the window. This locks in that date_to must include the whole day.
    session = make_session(tmp_path)
    session.add(make_incident(global_id="G1", event_date=datetime(2024, 6, 30, 14, 35, 0)))
    session.add(make_incident(global_id="G2", event_date=datetime(2024, 7, 1, 0, 0, 0)))
    session.commit()

    rows = session.execute(base_query({"date_to": "2024-06-30"})).scalars().all()

    assert [r.global_id for r in rows] == ["G1"]


def test_base_query_returns_every_field_observation_by_default(tmp_path):
    # Replaces the two source-filter tests: field_observations holds Survey123
    # rows and nothing else, so there is no source column left to filter on.
    session = make_session(tmp_path)
    session.add(make_incident(global_id="G1"))
    session.add(make_incident(global_id="G2"))
    session.commit()

    rows = session.execute(base_query({})).scalars().all()

    assert sorted(r.global_id for r in rows) == ["G1", "G2"]


def test_base_query_treats_a_blank_community_as_no_filter(tmp_path):
    # Reproduction: three matching rows, community left blank on the form.
    # `WHERE community = ''` matched none of them and the report read
    # "0 incidents in Arima" with status ok.
    session = make_session(tmp_path)
    for suffix in ("G1", "G2", "G3"):
        session.add(make_incident(global_id=suffix, community="Sangre Grande"))
    session.commit()

    blank = session.execute(
        base_query({"corporation": "sangre_grande_regional_corporat", "community": ""})
    ).scalars().all()
    omitted = session.execute(
        base_query({"corporation": "sangre_grande_regional_corporat"})
    ).scalars().all()

    assert len(blank) == 3
    assert sorted(r.global_id for r in blank) == sorted(r.global_id for r in omitted)


def test_base_query_treats_a_blank_corporation_and_dates_as_no_filter(tmp_path):
    session = make_session(tmp_path)
    session.add(make_incident(global_id="G1"))
    session.add(make_incident(global_id="G2"))
    session.commit()

    rows = session.execute(
        base_query({"corporation": "", "community": "", "date_from": "", "date_to": ""})
    ).scalars().all()

    assert sorted(r.global_id for r in rows) == ["G1", "G2"]


def test_metrics_with_a_blank_community_agree_with_the_omitted_case(tmp_path):
    # The compounding half of the defect: incident_count and street_level_tally
    # returned 0 while data_coverage (whose requirement omits community)
    # returned 3, all in one fact table, all scoped "community: all".
    from app.modules.survey123.metrics import (
        data_coverage,
        incident_count,
        street_level_tally,
    )

    session = make_session(tmp_path)
    for suffix in ("G1", "G2", "G3"):
        session.add(make_incident(global_id=suffix, community="Sangre Grande"))
    session.commit()

    blank_params = {"corporation": "sangre_grande_regional_corporat", "community": ""}
    omitted_params = {"corporation": "sangre_grande_regional_corporat"}

    for metric in (incident_count, street_level_tally, data_coverage):
        blank_facts = metric(blank_params, session)
        omitted_facts = metric(omitted_params, session)
        assert [f.value for f in blank_facts] == [f.value for f in omitted_facts], metric.__name__
        assert [f.scope for f in blank_facts] == [f.scope for f in omitted_facts], metric.__name__

    assert incident_count(blank_params, session)[0].value == 3
    assert data_coverage(blank_params, session)[0].value == 3


def test_a_blank_scope_label_matches_the_query_that_actually_ran(tmp_path):
    # build_scope's `or "all"` is only truthful once a blank stops filtering:
    # the fact says "community: all" and the query really did span all
    # communities.
    session = make_session(tmp_path)
    session.add(make_incident(global_id="G1", community="Sangre Grande"))
    session.add(make_incident(global_id="G2", community="Cumuto"))
    session.commit()

    from app.modules.survey123.metrics import incident_count

    fact = incident_count({"community": ""}, session)[0]

    assert fact.scope["community"] == "all"
    assert fact.value == 2
    assert "community" not in fact.citation.query_ref


def test_build_citation_takes_module_and_cid_from_the_model():
    citation = build_citation("incident_count", 0, {}, ["GUID-1"], "test description", FieldObservation)

    assert citation.module == "survey123"
    assert citation.cid == "survey123-incident_count-0"


def test_build_citation_as_of_is_utc_aware():
    # renderer.py prints as_of verbatim into the ministerial citation
    # appendix. datetime.now() gave a naive local timestamp there while
    # FactTable.generated_at and every ingested_at were UTC-aware.
    from datetime import timezone

    citation = build_citation(
        "incident_count", 0, {}, ["GUID-1"], "test description", FieldObservation
    )

    assert citation.as_of.tzinfo is not None
    assert citation.as_of.utcoffset() == timezone.utc.utcoffset(None)


def test_build_citation_ignores_a_caller_supplied_source_param():
    # params is author-controlled (DataRequirement.params), so a "source" key
    # there must not be able to relabel where a citation came from.
    citation = build_citation(
        "incident_count", 0, {"source": "sitreps"}, ["GUID-1"], "test description", FieldObservation
    )

    assert citation.module == "survey123"
    assert citation.cid == "survey123-incident_count-0"


def test_build_citation_rejects_a_model_that_does_not_declare_its_module():
    class UnwiredModel:
        pass

    with pytest.raises(ValueError, match="__module_name__"):
        build_citation("incident_count", 0, {}, ["GUID-1"], "test description", UnwiredModel)


def test_query_ref_omits_params_the_query_never_applied():
    # A template carrying a legacy "source" key silently widened its result
    # set while query_ref still advertised the filter. query_ref is the string
    # an auditor uses to reproduce a number.
    from app.modules.survey123.metrics import build_query_ref

    ref = build_query_ref(
        "estimated_damage_total",
        {
            "corporation": "diego_martin_regional_corporati",
            "source": "sitreps",
            "incident_type": "flood",
        },
    )

    assert "source" not in ref
    assert "incident_type" not in ref
    assert "corporation=diego_martin_regional_corporati" in ref


def test_query_ref_still_names_every_applied_filter():
    from app.modules.survey123.metrics import build_query_ref

    ref = build_query_ref(
        "incident_count",
        {
            "corporation": "siparia_regional_corporation",
            "community": "Penal",
            "date_from": "2023-06-01",
            "date_to": "2023-06-30",
            "include_pending": True,
        },
    )

    for expected in (
        "corporation=siparia_regional_corporation",
        "community=Penal",
        "date_from=2023-06-01",
        "date_to=2023-06-30",
        "include_pending=True",
    ):
        assert expected in ref


def test_query_params_covers_every_key_the_query_layer_reads():
    # Guards the two from drifting in BOTH directions:
    #   - a name in QUERY_PARAMS that no query reads (checked first, below)
    #   - a params.get("...") call site the query layer reads that is not
    #     listed in QUERY_PARAMS (checked second, via regex) — this is the
    #     dangerous direction: it reproduces the exact defect Task 2 closed,
    #     a filter that silently vanishes from query_ref while still applying.
    import inspect
    import re

    from app.modules.survey123 import metrics

    source = inspect.getsource(metrics.apply_common_filters) + inspect.getsource(
        metrics.base_query
    )

    for name in metrics.QUERY_PARAMS:
        assert f'"{name}"' in source, f"{name} is in QUERY_PARAMS but no query reads it"

    read_keys = set(re.findall(r'params\.get\(\s*"([^"]+)"', source))
    for key in read_keys:
        assert key in metrics.QUERY_PARAMS, (
            f"{key} is read by apply_common_filters/base_query via params.get(...) "
            "but is missing from QUERY_PARAMS, so it would silently vanish from query_ref"
        )


def test_unmapped_type_gap_caps_the_values_it_lists():
    # FactTable.gaps reaches the LLM prompt unpared, so an unbounded list of
    # distinct hand-typed values would overflow the context and return an
    # empty narrative — a failure this codebase has already fixed twice.
    from app.modules.survey123.metrics import unmapped_incident_type_gaps

    class Row:
        def __init__(self, raw):
            self.incident_type = "unmapped"
            self.raw_incident_type = raw

    rows = [Row(f"Typo Type {i}") for i in range(40)]

    gaps = unmapped_incident_type_gaps("incident_count", rows, "Consequence.")

    assert len(gaps) == 1
    assert "and 30 others" in gaps[0]
    assert gaps[0].count("'") == 20  # 10 quoted values, two quotes each
    assert "40 rows in scope" in gaps[0]
