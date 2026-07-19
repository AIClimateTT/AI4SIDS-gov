import sys
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.core.contracts import Fact, IngestResult, MetricSpec
from app.core.mcp_module import McpDataModule
from app.core.registry import DataModule
from app.modules.survey123.ingest import ingest_csv
from app.modules.survey123.metrics import METRIC_FUNCTIONS, METRIC_SPECS


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
        return METRIC_SPECS

    def run_metric(self, name: str, params: dict, session: Session) -> list[Fact]:
        fn = METRIC_FUNCTIONS.get(name)
        if fn is None:
            raise ValueError(f"unknown metric for survey123: {name}")
        return fn({**params, "source": "survey123"}, session)


survey123_module = Survey123Module()


def get_survey123_module() -> DataModule:
    if settings.survey123_transport == "mcp":
        return McpDataModule(
            name="survey123",
            command=sys.executable,
            args=["-m", "app.mcp_server.survey123_server"],
        )
    return survey123_module
