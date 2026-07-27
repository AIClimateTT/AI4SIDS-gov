from datetime import datetime

from sqlalchemy.orm import sessionmaker

from app.core.registry import get_module, reset_registry, ensure_default_modules_registered
from app.db import Base, make_engine
from app.modules.sitreps.ingest import ingest_submission
from app.modules.survey123.models import FieldObservation

CORP = "diego_martin_regional_corporati"


def make_session(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_field_observation_has_no_source_column():
    assert "source" not in FieldObservation.__table__.columns
    assert FieldObservation.__tablename__ == "field_observations"


def test_sitrep_module_never_sees_field_observations(tmp_path):
    import csv
    from pathlib import Path

    session = make_session(tmp_path)
    session.add(
        FieldObservation(
            global_id="gid-1",
            object_id=1,
            corporation=CORP,
            incident_type="fire",
            event_date=datetime(2023, 6, 27),
            validation_status="validated",
            follow_up_flags={},
            source_file="x.csv",
            ingested_at=datetime(2023, 6, 27),
        )
    )
    session.commit()

    path = Path(tmp_path) / "inc.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Row ID", "Incident Type", "Date of Event"])
        writer.writerow(["1", "landslide", "2023-06-27"])
    ingest_submission(
        session, corporation=CORP, as_at=datetime(2023, 6, 27), incidents_path=path
    )

    reset_registry()
    ensure_default_modules_registered()

    sitreps = get_module("sitreps").run_metric(
        "incident_count", {"corporation": CORP}, session
    )
    survey123 = get_module("survey123").run_metric(
        "incident_count", {"corporation": CORP}, session
    )

    assert sitreps[0].value == 1
    assert sitreps[0].breakdown == {"landslide": 1}
    assert survey123[0].value == 1
    assert survey123[0].breakdown == {"fire": 1}


def test_each_module_tags_its_citations_with_its_own_name(tmp_path):
    # Restores the provenance half of the two isolation tests Task 5 deleted:
    # a sitreps fact must not claim to have come from survey123 now that the
    # module identity no longer travels in the params as "source".
    session = make_session(tmp_path)
    reset_registry()
    ensure_default_modules_registered()

    sitreps = get_module("sitreps").run_metric("incident_count", {}, session)
    survey123 = get_module("survey123").run_metric("incident_count", {}, session)

    assert sitreps[0].citation.module == "sitreps"
    assert sitreps[0].citation.cid == "sitreps-incident_count-0"
    assert survey123[0].citation.module == "survey123"
    assert survey123[0].citation.cid == "survey123-incident_count-0"


def test_sitreps_data_coverage_returns_no_facts(tmp_path):
    # SitrepIncident has no validation_status column, so data_coverage takes its
    # early return instead of querying a column that does not exist. The seeded
    # field observation is what a wrongly-wired sitreps module would report on.
    session = make_session(tmp_path)
    session.add(
        FieldObservation(
            global_id="gid-1",
            object_id=1,
            corporation=CORP,
            incident_type="fire",
            event_date=datetime(2023, 6, 27),
            creation_date=datetime(2023, 6, 27),
            validation_status="validated",
            is_duplicate=False,
            follow_up_flags={},
            source_file="x.csv",
            ingested_at=datetime(2023, 6, 27),
        )
    )
    session.commit()
    reset_registry()
    ensure_default_modules_registered()

    assert get_module("sitreps").run_metric("data_coverage", {}, session) == []
    assert len(get_module("survey123").run_metric("data_coverage", {}, session)) == 1


def test_sitreps_metrics_survive_the_missing_survey123_only_columns(tmp_path):
    # base_query() guards is_duplicate / validation_status with column_exists();
    # this drives the FALSE branch of both guards against a real query, and
    # proves an injected source param cannot filter a table without the column.
    session = make_session(tmp_path)
    path = tmp_path / "inc.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        import csv

        writer = csv.writer(f)
        writer.writerow(["Row ID", "Incident Type", "Date of Event"])
        writer.writerow(["1", "landslide", "2023-06-27"])
    ingest_submission(
        session, corporation=CORP, as_at=datetime(2023, 6, 27), incidents_path=path
    )

    reset_registry()
    ensure_default_modules_registered()
    module = get_module("sitreps")

    for metric in (
        "incident_count",
        "incidents_by_corporation",
        "homes_affected_count",
        "casualty_summary",
        "street_level_tally",
        "relief_actions_summary",
        "special_needs_count",
        "estimated_damage_total",
    ):
        facts = module.run_metric(metric, {"include_pending": False}, session)
        assert facts, f"{metric} returned no facts for the sitreps module"
        assert all(f.citation.module == "sitreps" for f in facts)
