from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(primary_key=True)
    global_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    object_id: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String, nullable=False, default="survey123")

    corporation: Mapped[str | None] = mapped_column(String, nullable=True)
    raw_corporation: Mapped[str | None] = mapped_column(String, nullable=True)
    community: Mapped[str | None] = mapped_column(String, nullable=True)
    street: Mapped[str | None] = mapped_column(String, nullable=True)

    incident_type: Mapped[str | None] = mapped_column(String, nullable=True)
    raw_incident_type: Mapped[str | None] = mapped_column(String, nullable=True)
    incident_type_other: Mapped[str | None] = mapped_column(String, nullable=True)

    incident_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    event_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    event_time: Mapped[str | None] = mapped_column(String, nullable=True)
    assessment_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    creation_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    edit_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    occupants_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    injuries_occurred: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    injuries_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deaths_occurred: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deaths_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    building_damage: Mapped[str | None] = mapped_column(Text, nullable=True)
    crops_livestock: Mapped[str | None] = mapped_column(Text, nullable=True)
    personal_items: Mapped[str | None] = mapped_column(Text, nullable=True)
    furniture_appliances: Mapped[str | None] = mapped_column(Text, nullable=True)

    action_taken: Mapped[str | None] = mapped_column(String, nullable=True)
    relief_items: Mapped[str | None] = mapped_column(Text, nullable=True)

    shelter: Mapped[str | None] = mapped_column(Text, nullable=True)
    special_needs_occupants: Mapped[int | None] = mapped_column(Integer, nullable=True)

    estimated_damage_cost: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)

    follow_up: Mapped[str | None] = mapped_column(String, nullable=True)
    follow_up_flags: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    validation_status: Mapped[str] = mapped_column(String, nullable=False)

    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    duplicate_reason: Mapped[str | None] = mapped_column(String, nullable=True)

    flood_type: Mapped[str | None] = mapped_column(String, nullable=True)
    flood_trigger: Mapped[str | None] = mapped_column(String, nullable=True)
    flood_height: Mapped[str | None] = mapped_column(String, nullable=True)

    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)

    officer_name: Mapped[str | None] = mapped_column(String, nullable=True)
    officer_position: Mapped[str | None] = mapped_column(String, nullable=True)

    dedup_hash: Mapped[str | None] = mapped_column(String, nullable=True, index=True)

    source_file: Mapped[str] = mapped_column(String, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
