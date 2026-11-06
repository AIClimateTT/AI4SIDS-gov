"""The two fixed data sources reports can read: corporation sitreps (unvalidated)
and Survey123 (verified). `source` is the label stored on templates and citations."""

from sqlalchemy.orm import Session

from app.core.contracts import Fact
from app.modules.sitreps.log_metrics import LOG_METRIC_FUNCTIONS
from app.modules.sitreps.minister_metrics import MINISTER_METRIC_FUNCTIONS
from app.modules.sitreps.models import SitrepIncident
from app.modules.survey123.metrics import METRIC_FUNCTIONS
from app.modules.survey123.models import FieldObservation

SOURCES = ("sitreps", "survey123")

# data_coverage measures validation status, which corporation rows do not carry.
# Running it on sitreps returns [] so an older report's definition cannot crash,
# but it is not offered to new templates.
_SITREP_UNSUPPORTED = frozenset({"data_coverage"})
_SITREP_OWN_METRICS = {**LOG_METRIC_FUNCTIONS, **MINISTER_METRIC_FUNCTIONS}


def _require_source(source: str) -> None:
    if source not in SOURCES:
        raise ValueError(f"unknown data source: {source}")


def metric_names(source: str) -> set[str]:
    _require_source(source)
    if source == "survey123":
        return set(METRIC_FUNCTIONS)
    return (set(METRIC_FUNCTIONS) - _SITREP_UNSUPPORTED) | set(_SITREP_OWN_METRICS)


def run_metric(source: str, name: str, params: dict, session: Session) -> list[Fact]:
    _require_source(source)
    if source == "survey123":
        fn = METRIC_FUNCTIONS.get(name)
        if fn is None:
            raise ValueError(f"unknown metric for survey123: {name}")
        return fn(params, session, FieldObservation)

    own = _SITREP_OWN_METRICS.get(name)
    if own is not None:
        return own(params, session)
    fn = METRIC_FUNCTIONS.get(name)
    if fn is None:
        raise ValueError(f"unknown metric for sitreps: {name}")
    return fn(params, session, SitrepIncident)
