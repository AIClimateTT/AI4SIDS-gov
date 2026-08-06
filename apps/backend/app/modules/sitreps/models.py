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
    __table_args__ = (
        # NULL event_id does not collide in SQL's unique-constraint semantics
        # (each NULL is distinct), which is correct here: event-less
        # submissions all carry sequence_no 1 by design and are told apart by
        # (corporation, as_at) instead.
        UniqueConstraint(
            "corporation", "event_id", "sequence_no",
            name="uq_submission_corp_event_sequence",
        ),
    )

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
    # Persisted so an officer can reopen a filing and see what was rejected.
    # These are built during ingest anyway; keeping them only in the response
    # meant closing the tab lost them.
    row_errors: Mapped[list] = mapped_column(JSON, default=list, nullable=False)


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
        """Stable per-row identifier for citations.

        Deliberately excludes submission_id. Supersession rewrites
        existing.submission_id in place, so including it made a row's
        identifier change every time the corp restated the row — and reports
        are stored immutable, so a report issued before the restatement went on
        citing an identifier that matched no row. An identifier that moves is
        not an identifier.

        uq_sitrep_incident_corp_event_row already guarantees this triple is
        unique. submission_id was added to disambiguate event-less rows, but
        both entry points (POST /submissions and the CLI) reject an
        incident-bearing submission that names no event, so no such row exists.
        """
        return f"{self.corporation}:{self.event_id or '-'}:{self.row_id}"


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
