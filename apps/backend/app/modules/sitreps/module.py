from pathlib import Path

from sqlalchemy.orm import Session

from app.core.contracts import Fact, IngestResult, MetricSpec
from app.modules.sitreps.models import SitrepIncident
from app.modules.survey123.metrics import METRIC_FUNCTIONS, METRIC_SPECS


class SitrepModule:
    name = "sitreps"

    def ingest(self, file_path: Path) -> IngestResult:
        raise NotImplementedError(
            "sitreps data arrives as a submission (corporation, as-at time and "
            "up to two CSVs); use POST /submissions or the 'submissions create' "
            "CLI command instead"
        )

    def list_metrics(self) -> list[MetricSpec]:
        return [spec.model_copy(update={"module": "sitreps"}) for spec in METRIC_SPECS]

    def run_metric(self, name: str, params: dict, session: Session) -> list[Fact]:
        fn = METRIC_FUNCTIONS.get(name)
        if fn is None:
            raise ValueError(f"unknown metric for sitreps: {name}")
        return fn(params, session, SitrepIncident)


sitrep_module = SitrepModule()
