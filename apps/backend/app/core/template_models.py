from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class TemplateRecord(Base):
    __tablename__ = "report_templates"
    __table_args__ = (UniqueConstraint("name", "version", name="uq_report_templates_name_version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    params: Mapped[list] = mapped_column(JSON, nullable=False)
    data_requirements: Mapped[list] = mapped_column(JSON, nullable=False)
    narration: Mapped[dict] = mapped_column(JSON, nullable=False)
    render: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
