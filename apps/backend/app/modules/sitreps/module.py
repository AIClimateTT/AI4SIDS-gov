from pathlib import Path

from sqlalchemy.orm import Session

from app.core.contracts import Fact, IngestResult, MetricSpec
from app.modules.survey123.metrics import METRIC_FUNCTIONS, METRIC_SPECS


class SitrepModule:
    name = "sitreps"

    def ingest(self, file_path: Path) -> IngestResult:
        raise NotImplementedError(
            "sitreps ingestion requires a corporation argument; use the "
            "'ingest sitreps <corporation> <file>' CLI command instead"
        )

    def list_metrics(self) -> list[MetricSpec]:
        return [spec.model_copy(update={"module": "sitreps"}) for spec in METRIC_SPECS]

    def run_metric(self, name: str, params: dict, session: Session) -> list[Fact]:
        fn = METRIC_FUNCTIONS.get(name)
        if fn is None:
            raise ValueError(f"unknown metric for sitreps: {name}")
        return fn({**params, "source": "sitreps"}, session)


sitrep_module = SitrepModule()
