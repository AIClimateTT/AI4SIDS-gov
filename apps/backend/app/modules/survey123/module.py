from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.core.contracts import Fact, IngestResult, MetricSpec
from app.modules.survey123.ingest import ingest_csv


class Survey123Module:
    name = "survey123"

    def ingest(self, file_path: Path) -> IngestResult:
        from app.db import SessionLocal

        session = SessionLocal()
        try:
            return ingest_csv(file_path, session, settings.dedup_salt)
        finally:
            session.close()

    def list_metrics(self) -> list[MetricSpec]:
        return []

    def run_metric(self, name: str, params: dict, session: Session) -> list[Fact]:
        raise ValueError(f"unknown metric for survey123: {name}")


survey123_module = Survey123Module()
