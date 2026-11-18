from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
# Turns point at prompt_versions by hash; registering the table here keeps it
# in every metadata that has the capture tables.
from app.prompts import models as _prompt_models  # noqa: F401


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
    alert_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
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
    # The capture prompt this conversation runs on (prompt_versions.hash),
    # pinned at its first turn.
    prompt_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class CaptureTurn(Base):
    """What the working set looked like after each change to a capture session.

    One row per officer message, manual edit, CSV import, event attach,
    sitrep preview and issue. The model's raw output is kept so a turn the
    clerk "could not read" can be diagnosed, and each sitrep generation keeps
    its own copy instead of overwriting the last. Review data only: nothing
    reads it back into a filing."""

    __tablename__ = "capture_turns"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("capture_sessions.id"), nullable=False, index=True
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    user_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    assistant_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    parse_ok: Mapped[bool | None] = mapped_column(nullable=True)
    # Report layout version, on sitrep previews and issues.
    template_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Officer turns: which prompt and model produced this reply.
    prompt_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    prompt_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prompt_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model: Mapped[str | None] = mapped_column(String, nullable=True)
    retried: Mapped[bool | None] = mapped_column(nullable=True)
    # Guard name -> how many corrections it made to the model's reply.
    interventions: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    working: Mapped[dict] = mapped_column(JSON, nullable=False)
    missing: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    sitrep_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
