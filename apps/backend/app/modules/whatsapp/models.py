from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class WhatsAppDraft(Base):
    """Officer working set from a WhatsApp extract. Not corp submissions."""

    __tablename__ = "whatsapp_drafts"

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    as_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pii_redacted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    incidents: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    logs: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    messages: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    manual_fields: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String, nullable=False, default="ready")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_kind: Mapped[str] = mapped_column(String, nullable=False, default="export")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
