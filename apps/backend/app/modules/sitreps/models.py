from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

ALERT_LEVELS = ("green", "yellow", "orange", "red", "discontinued", "none")
HAZARD_TYPES = ("flood", "landslide", "wind", "fire", "other")
LOG_CATEGORIES = (
    "resource",
    "personnel",
    "facility",
    "activity",
    "relief_distributed",
    "other",
)
LOG_STATUSES = (
    "available",
    "prepositioned",
    "in_stock",
    "inspected",
    "on_standby",
    "ongoing",
    "completed",
    "procuring",
)


class Event(Base):
    """A hazard event owned by one corporation and reused across submissions."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    corporation: Mapped[str] = mapped_column(String, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    hazard_type: Mapped[str] = mapped_column(String, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class Submission(Base):
    """One corp upload: who, as-at when, under what alert state."""

    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    corporation: Mapped[str] = mapped_column(String, nullable=False, index=True)
    event_id: Mapped[int | None] = mapped_column(
        ForeignKey("events.id"), nullable=True, index=True
    )
    as_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    alert_level: Mapped[str] = mapped_column(String, nullable=False, default="none")
    present_activity: Mapped[str | None] = mapped_column(Text, nullable=True)
    situation_overview: Mapped[str | None] = mapped_column(Text, nullable=True)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    source_file: Mapped[str | None] = mapped_column(String, nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class SitrepIncident(Base):
    """Corp-entered incident. Authoritative. Column names mirror FieldObservation
    wherever the shared metric core filters on them."""

    __tablename__ = "sitrep_incidents"
    __module_name__ = "sitreps"
    __source_label__ = "SITREP"
    __table_args__ = (
        UniqueConstraint(
            "corporation", "event_id", "row_id", name="uq_sitrep_incident_corp_event_row"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int] = mapped_column(
        ForeignKey("submissions.id"), nullable=False, index=True
    )
    corporation: Mapped[str] = mapped_column(String, nullable=False, index=True)
    event_id: Mapped[int | None] = mapped_column(
        ForeignKey("events.id"), nullable=True, index=True
    )
    row_id: Mapped[str] = mapped_column(String, nullable=False)

    community: Mapped[str | None] = mapped_column(String, nullable=True)
    street: Mapped[str | None] = mapped_column(String, nullable=True)

    incident_type: Mapped[str | None] = mapped_column(String, nullable=True)
    raw_incident_type: Mapped[str | None] = mapped_column(String, nullable=True)
    incident_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    event_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    injuries_occurred: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    injuries_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deaths_occurred: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deaths_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    building_damage: Mapped[str | None] = mapped_column(Text, nullable=True)
    special_needs_occupants: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_damage_cost: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)

    action_taken: Mapped[str | None] = mapped_column(Text, nullable=True)
    follow_up_flags: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    ingested_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    @property
    def record_ref(self) -> str:
        # submission_id included so one reference names exactly one row. Without
        # it, every event-less row rendered event_id as "-" and rows from
        # different submissions shared an identifier, making a cited figure
        # untraceable.
        return f"{self.corporation}:{self.event_id or '-'}:{self.submission_id}:{self.row_id}"


class SituationLog(Base):
    """Operational or preparedness state as at one submission. Never upserted."""

    __tablename__ = "situation_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int] = mapped_column(
        ForeignKey("submissions.id"), nullable=False, index=True
    )
    category: Mapped[str] = mapped_column(String, nullable=False, index=True)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    item: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    quantity: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    unit: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str | None] = mapped_column(String, nullable=True)
