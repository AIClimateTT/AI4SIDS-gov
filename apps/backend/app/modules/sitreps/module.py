from pathlib import Path

from sqlalchemy.orm import Session

from app.core.contracts import Fact, IngestResult, MetricSpec
from app.modules.sitreps.log_metrics import LOG_METRIC_FUNCTIONS, LOG_METRIC_SPECS
from app.modules.sitreps.models import SitrepIncident
from app.modules.survey123.metrics import METRIC_FUNCTIONS, METRIC_SPECS


class SitrepModule:
    name = "sitreps"

    # data_coverage measures validation status (pct_validated, pct_duplicates),
    # which corp SITREP rows do not carry -- they are human-verified by
    # definition. run_metric still serves it (see below), returning [], so a
    # previously stored template naming it does not crash; it is just not
    # offered as something new templates can request.
    UNSUPPORTED_METRICS = frozenset({"data_coverage"})

    def ingest(self, file_path: Path) -> IngestResult:
        raise NotImplementedError(
            "sitreps data arrives as a submission (corporation, as-at time and "
            "up to two CSVs); use POST /submissions or the 'submissions create' "
            "CLI command instead"
        )

    def list_metrics(self) -> list[MetricSpec]:
        incident = [
            spec.model_copy(update={"module": "sitreps"})
            for spec in METRIC_SPECS
            if spec.name not in self.UNSUPPORTED_METRICS
        ]
        return incident + LOG_METRIC_SPECS

    def run_metric(self, name: str, params: dict, session: Session) -> list[Fact]:
        log_fn = LOG_METRIC_FUNCTIONS.get(name)
        if log_fn is not None:
            return log_fn(params, session)
        fn = METRIC_FUNCTIONS.get(name)
        if fn is None:
            raise ValueError(f"unknown metric for sitreps: {name}")
        return fn(params, session, SitrepIncident)


sitrep_module = SitrepModule()
