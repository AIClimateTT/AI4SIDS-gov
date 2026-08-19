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
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
