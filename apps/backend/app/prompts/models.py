from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class PromptVersion(Base):
    """The exact text of every prompt that has been sent to a model.

    Keyed by the hash of the assembled text, so a turn recorded months ago can
    be traced to what the model was actually told, after the files in
    app/prompts have moved on. Written once, on first use."""

    __tablename__ = "prompt_versions"

    hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    prompt_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
