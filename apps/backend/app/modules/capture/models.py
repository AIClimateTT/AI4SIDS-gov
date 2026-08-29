from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class CaptureSession(Base):
    """Corp officer conversation working set. Not an authoritative submission until filed."""

    __tablename__ = "capture_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    corporation: Mapped[str] = mapped_column(String, nullable=False, index=True)
    event_id: Mapped[int | None] = mapped_column(
        ForeignKey("events.id"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String, nullable=False, default="draft")
    as_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    alert_level: Mapped[str] = mapped_column(String, nullable=False, default="none")
    present_activity: Mapped[str | None] = mapped_column(Text, nullable=True)
    situation_overview: Mapped[str | None] = mapped_column(Text, nullable=True)
    incidents: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    logs: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    manual_fields: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    messages: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    submission_id: Mapped[int | None] = mapped_column(
        ForeignKey("submissions.id"), nullable=True
    )
    report_id: Mapped[str | None] = mapped_column(
        ForeignKey("reports.id", name="fk_capture_sessions_report_id"),
        nullable=True,
    )
    sitrep_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    sitrep_final_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    sitrep_fact_table: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    sitrep_violations: Mapped[list | None] = mapped_column(
        JSON, nullable=True, default=list
    )
    sitrep_status: Mapped[str | None] = mapped_column(String, nullable=True)
    sitrep_generated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sitrep_source_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
