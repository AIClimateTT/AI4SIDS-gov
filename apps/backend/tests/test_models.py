from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.db import Base, make_engine
from app.modules.survey123.models import Incident

BANNED_COLUMN_NAMES = {
    "name_of_person",
    "person_name",
    "contact_information",
    "contact_info",
    "identification_card_number",
    "id_card_number",
    "name_of_second_person",
    "second_person_name",
    "second_contact_information",
    "second_contact_info",
    "second_identification_card_number",
    "second_id_card_number",
    "occupant_names",
    "occupant_names_and_relation",
}


def test_incident_model_has_no_pii_columns():
    columns = set(Incident.__table__.columns.keys())
    overlap = columns & BANNED_COLUMN_NAMES

    assert not overlap, f"PII-shaped columns found on Incident model: {overlap}"


def test_incident_round_trips_through_sqlite(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    incident = Incident(
        global_id="GUID-TEST",
        object_id=1,
        corporation="sangre_grande_regional_corporat",
        raw_corporation=None,
        community="Sangre Grande",
        street="Flood Street",
        incident_type="flooding_",
        raw_incident_type=None,
        incident_type_other=None,
        incident_summary="Test incident",
        event_date=datetime(2024, 6, 1, tzinfo=timezone.utc),
        event_time="06:00",
        assessment_date=None,
        creation_date=datetime(2024, 6, 1, tzinfo=timezone.utc),
        edit_date=datetime(2024, 6, 1, tzinfo=timezone.utc),
        occupants_count=3,
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
        follow_up_flags={
            "relief_supplied": False,
            "forwarded_to_agency": False,
            "further_assessment_required": False,
            "other": False,
        },
        validation_status="validated",
        is_duplicate=False,
        duplicate_reason=None,
        flood_type=None,
        flood_trigger=None,
        flood_height=None,
        lon=-61.13,
        lat=10.58,
        officer_name="Kevin Jagassar",
        officer_position="DMU Field Officer",
        dedup_hash=None,
        source_file="test.csv",
        ingested_at=datetime(2024, 6, 1, tzinfo=timezone.utc),
    )
    session.add(incident)
    session.commit()

    fetched = session.execute(select(Incident).where(Incident.global_id == "GUID-TEST")).scalar_one()

    assert fetched.corporation == "sangre_grande_regional_corporat"
    assert fetched.follow_up_flags == {
        "relief_supplied": False,
        "forwarded_to_agency": False,
        "further_assessment_required": False,
        "other": False,
    }
    session.close()
