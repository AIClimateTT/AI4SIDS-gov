import inspect

from app.modules.survey123.metrics import (
    METRIC_FUNCTIONS,
    base_query,
    column_exists,
)
from app.modules.survey123.models import Incident


def test_every_metric_accepts_a_model_parameter():
    for name, fn in METRIC_FUNCTIONS.items():
        params = list(inspect.signature(fn).parameters)
        assert params[:3] == ["params", "session", "model"], (
            f"{name} does not take (params, session, model)"
        )


def test_model_defaults_to_incident_so_existing_callers_are_unaffected():
    for name, fn in METRIC_FUNCTIONS.items():
        default = inspect.signature(fn).parameters["model"].default
        assert default is Incident, f"{name} has the wrong default model"


def test_column_exists_reports_real_columns_only():
    assert column_exists(Incident, "validation_status") is True
    assert column_exists(Incident, "is_duplicate") is True
    assert column_exists(Incident, "not_a_column") is False


def test_base_query_selects_from_the_given_model():
    stmt = base_query({}, Incident)

    assert "incidents" in str(stmt)
